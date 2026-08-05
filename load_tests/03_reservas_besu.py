"""
Escenario 3 — Throughput de reservas de vuelo en Besu (eVTOLs independientes)

Prerrequisito:
  Ejecutar primero el script de setup para preparar cuentas y eVTOLs:
    python load_tests/setup_e3_besu.py --users <N>

Qué mide:
  Throughput y latencia de transacciones Besu para el ciclo completo
  createReservation → startTrip → completeTrip.

  Diseño del test:
  - Las transacciones las firma la cuenta admin (dev key), igual que lo
    haría el backend Django en producción.
  - Cada usuario virtual tiene su propio rider address, su propio eVTOL
    y sus propios trip_ids. No hay contención de estado de eVTOL.
  - El nonce se serializa con un lock porque un solo account firma todo,
    reflejo fiel de cómo Django enviaría txs en producción.
  - El límite medido es la red Besu (QBFT, tiempo de bloque, throughput
    de txs por bloque) sin el cuello de botella artificial de un eVTOL único.

Cómo ejecutar (N debe coincidir con el setup):
  locust -f load_tests/03_reservas_besu.py --host=http://localhost:8545 \\
         --users 5 --spawn-rate 1 --run-time 120s --headless \\
         --html load_tests/resultados/besu_5u.html

  locust -f load_tests/03_reservas_besu.py --host=http://localhost:8545 \\
         --users 10 --spawn-rate 1 --run-time 180s --headless \\
         --html load_tests/resultados/besu_10u.html
"""

import json
import pathlib
import time
import threading
import uuid

import gevent.lock
from locust import User, task, between, events
from web3 import Web3
from web3.middleware import geth_poa_middleware

# ── Cargar setup ──────────────────────────────────────────────────────────────

SETUP_FILE = pathlib.Path(__file__).parent / "resultados/e3_setup.json"
if not SETUP_FILE.exists():
    raise FileNotFoundError(
        f"Archivo de setup no encontrado: {SETUP_FILE}\n"
        "Ejecuta primero: python load_tests/setup_e3_besu.py --users <N>"
    )

_setup   = json.loads(SETUP_FILE.read_text())
VP1_ID   = _setup["vp1"]
VP2_ID   = _setup["vp2"]
_ACCOUNTS = _setup["accounts"]   # lista de {address, private_key, evtol_id}

# ── Contratos ─────────────────────────────────────────────────────────────────

BASE     = pathlib.Path("~/Documentos/TI3").expanduser()
_addr    = json.loads((BASE / "BESU_project/smart_contracts/deployed_addresses.json").read_text())
_fr_abi  = json.loads((BASE / "BESU_project/smart_contracts/contracts/FlightReservation.json").read_text())["abi"]

RPC_URL  = "http://localhost:8545"
# La cuenta admin (dev key) es la única que puede llamar al contrato — igual
# que el backend Django en producción.
ADMIN_KEY = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

# ── Nonce centralizado (todas las tx usan la cuenta admin) ────────────────────
#
# Con un único firmante (admin key), los nonces deben ser estrictamente
# secuenciales. La estrategia correcta con gevent (coroutines concurrentes):
#
#   1. El lock cubre TANTO la obtención del nonce COMO el send_raw_transaction.
#      Esto garantiza que el nonce N+1 sólo se asigne DESPUÉS de que la tx con
#      nonce N ya está en el mempool. Si separamos las dos operaciones, una
#      coroutine puede obtener nonce N+1 antes de que la anterior (con nonce N)
#      llegue siquiera a send_raw_transaction, creando potenciales huecos.
#
#   2. El receipt-wait (wait_for_transaction_receipt) se hace FUERA del lock.
#      Todos los usuarios esperan sus recibos en paralelo; no hay razón para
#      serializar esa parte — el mempool ya tiene todos los txs ordenados.
#
#   IMPORTANTE: usar gevent.lock.Semaphore, NO threading.Lock.
#   Locust corre en gevent (coroutines cooperativas en un solo OS thread).
#   threading.Lock NO es gevent-aware: dos greenlets en el mismo OS thread
#   pueden entrar al lock simultáneamente porque Python ve un único thread.
#   gevent.lock.Semaphore SÍ es greenlet-aware: bloquea la coroutine que
#   intenta adquirir el semáforo si ya está ocupado, cediendo al hub.
#
_send_lock = gevent.lock.Semaphore(1)

import logging as _logging
_log = _logging.getLogger("locust.nonce")

def _locked_send(w3, account, tx_fn, gas=400_000):
    """Obtiene el nonce y envía el tx bajo el lock. Devuelve tx_hash."""
    _send_lock.acquire()
    try:
        nonce = w3.eth.get_transaction_count(account.address, "pending")
        tx = tx_fn.build_transaction({
            "from":     account.address,
            "nonce":    nonce,
            "gas":      gas,
            "gasPrice": w3.eth.gas_price,
        })
        signed  = account.sign_transaction(tx)
        try:
            tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        except Exception as e:
            _log.warning(f"send_raw_tx FAILED nonce={nonce} confirmed={w3.eth.get_transaction_count(account.address,'latest')}: {e}")
            raise
    finally:
        _send_lock.release()
    return tx_hash

# ── Asignación de configuración por índice de usuario ────────────────────────
# Cada Locust user toma un rider_address y evtol_id distintos del setup.
_slot_lock  = gevent.lock.Semaphore(1)
_slot_index = [0]

def _claim_slot():
    with _slot_lock:
        idx = _slot_index[0]
        _slot_index[0] += 1
    if idx >= len(_ACCOUNTS):
        raise IndexError(
            f"Solo hay {len(_ACCOUNTS)} slots en el setup pero se intentaron "
            f"asignar {idx+1}. Vuelve a correr setup_e3_besu.py con --users mayor."
        )
    return _ACCOUNTS[idx]


# ── Usuario Locust ────────────────────────────────────────────────────────────

class BesuUser(User):
    # 1-2s de pausa entre ciclos evita el spin-loop cuando un tx falla a mitad
    # de ciclo (el task retorna None). Sin esta pausa, un usuario volvería a
    # llamar ciclo_viaje inmediatamente con un nonce nuevo, creando un hueco
    # en la secuencia que bloquea todos los nonces siguientes.
    wait_time = between(1, 2)

    def on_start(self):
        slot = _claim_slot()

        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        # Admin account firma todas las txs (como lo haría Django)
        self.admin   = self.w3.eth.account.from_key(ADMIN_KEY)
        # Rider y eVTOL propios de este usuario virtual
        self.rider   = Web3.to_checksum_address(slot["address"])
        self.evtol_id = slot["evtol_id"]
        self.fr      = self.w3.eth.contract(
            address=Web3.to_checksum_address(_addr["FlightReservation"]),
            abi=_fr_abi,
        )
        self._going_to_vp2 = True

    # ── helper: firmar desde admin, esperar recibo ────────────────────────────

    def _send(self, fn, name: str):
        start = time.time()
        try:
            tx_hash = _locked_send(self.w3, self.admin, fn)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            elapsed = int((time.time() - start) * 1000)
            ok      = receipt.status == 1
            events.request.fire(
                request_type="ETH", name=name,
                response_time=elapsed, response_length=0,
                exception=None if ok else Exception("tx reverted"),
            )
            return receipt if ok else None
        except Exception as exc:
            elapsed = int((time.time() - start) * 1000)
            events.request.fire(
                request_type="ETH", name=name,
                response_time=elapsed, response_length=0, exception=exc,
            )
            return None

    # ── tarea: ciclo completo de viaje ────────────────────────────────────────

    @task
    def ciclo_viaje(self):
        origin  = VP1_ID if self._going_to_vp2 else VP2_ID
        dest    = VP2_ID if self._going_to_vp2 else VP1_ID
        trip_id = f"E3-{uuid.uuid4().hex[:8].upper()}"

        r = self._send(
            self.fr.functions.createReservation(
                trip_id, self.rider,
                origin, dest, self.evtol_id,
                b"u", b"e", b"v",
            ),
            "createReservation",
        )
        if not r:
            return

        r = self._send(
            self.fr.functions.startTrip(trip_id, b"v"),
            "startTrip",
        )
        if not r:
            return

        r = self._send(
            self.fr.functions.completeTrip(trip_id, b"v"),
            "completeTrip",
        )
        if r:
            self._going_to_vp2 = not self._going_to_vp2
