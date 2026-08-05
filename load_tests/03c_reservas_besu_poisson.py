"""
Escenario 3c — Llegadas Poisson: reservas Besu hasta 100 usuarios

Diferencias clave respecto a E3b:

  wait_time = exponential(media=3s)
    En E3b, constant(0) hacía que todos los usuarios terminaran su TX al mismo
    tiempo (mismo bloque) y volvieran a enviar juntos → oleadas sincronizadas.
    Aquí, cada usuario espera un tiempo aleatorio de distribución exponencial
    (media 3s) antes de su próximo ciclo. Las llegadas al mempool siguen
    aproximadamente un proceso de Poisson con tasa λ = N/18 TXs/s por usuario.

  Escala hasta 100 usuarios
    Techo teórico: 16,234,336 gas / 400,000 gas/TX / 5s bloque = 8 TXs/s.
    Con exponential(3): ciclo ~18s por usuario → techo en ~48 usuarios.
    Por encima: TXs se encolan → latencia pasa de ~5s a ~10s, ~15s, etc.

Cómo ejecutar (desde SSI_App/):
  locust -f load_tests/03c_reservas_besu_poisson.py \\
         --host=http://localhost:8545 --headless \\
         --csv=load_tests/resultados/e3c \\
         --html=load_tests/resultados/e3c_poisson.html

  Duración total: ~35 min (9 pasos de 180–360 s c/u).
"""

import json, pathlib, time, uuid, random
import gevent.lock
from locust import User, task, events, LoadTestShape
from web3 import Web3
from web3.middleware import geth_poa_middleware

MEAN_WAIT = 3.0  # segundos (distribución exponencial entre ciclos)

# ── Cargar setup ──────────────────────────────────────────────────────────────
SETUP_FILE = pathlib.Path(__file__).parent / "resultados/e3c_setup.json"
if not SETUP_FILE.exists():
    raise FileNotFoundError(
        "e3c_setup.json no encontrado.\n"
        "Ejecuta primero: python load_tests/setup_e3c_besu.py --users 100"
    )

_setup    = json.loads(SETUP_FILE.read_text())
VP1_ID    = _setup["vp1"]
VP2_ID    = _setup["vp2"]
_ACCOUNTS = _setup["accounts"]

# ── Contratos ─────────────────────────────────────────────────────────────────
BASE    = pathlib.Path("~/Documentos/TI3").expanduser()
_addr   = json.loads((BASE / "BESU_project/smart_contracts/deployed_addresses.json").read_text())
_fr_abi = json.loads((BASE / "BESU_project/smart_contracts/contracts/FlightReservation.json").read_text())["abi"]
RPC_URL   = "http://localhost:8545"
ADMIN_KEY = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

# ── Nonce lock global (todos los usuarios comparten la cuenta admin) ───────────
_send_lock = gevent.lock.Semaphore(1)

import logging as _logging
_log = _logging.getLogger("locust.nonce")


def _locked_send(w3, account, tx_fn, gas=400_000):
    """Obtiene nonce y envía TX bajo lock. Receipt wait fuera del lock."""
    _send_lock.acquire()
    try:
        nonce = w3.eth.get_transaction_count(account.address, "pending")
        tx = tx_fn.build_transaction({
            "from": account.address, "nonce": nonce,
            "gas": gas, "gasPrice": w3.eth.gas_price,
        })
        signed = account.sign_transaction(tx)
        try:
            return w3.eth.send_raw_transaction(signed.rawTransaction)
        except Exception as e:
            _log.warning(f"send_raw_tx FAILED nonce={nonce}: {e}")
            raise
    finally:
        _send_lock.release()


# ── Asignación de slots ───────────────────────────────────────────────────────
_slot_lock  = gevent.lock.Semaphore(1)
_slot_index = [0]


def _claim_slot():
    with _slot_lock:
        idx = _slot_index[0]
        _slot_index[0] += 1
    if idx >= len(_ACCOUNTS):
        raise IndexError(
            f"Solo hay {len(_ACCOUNTS)} slots pero se pidió {idx + 1}. "
            "Regenera el setup con más usuarios."
        )
    return _ACCOUNTS[idx]


# ── Usuario Locust ────────────────────────────────────────────────────────────

class BesuUser(User):

    def wait_time(self):
        """
        Distribución exponencial con media MEAN_WAIT segundos.
        Produce llegadas al mempool que aproximan un proceso de Poisson:
        intervalos entre envíos aleatorios e independientes, sin sincronización.
        """
        return random.expovariate(1.0 / MEAN_WAIT)

    def on_start(self):
        slot = _claim_slot()
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.admin    = self.w3.eth.account.from_key(ADMIN_KEY)
        self.rider    = Web3.to_checksum_address(slot["address"])
        self.evtol_id = slot["evtol_id"]
        self.fr = self.w3.eth.contract(
            address=Web3.to_checksum_address(_addr["FlightReservation"]),
            abi=_fr_abi,
        )
        self._going_to_vp2 = True

    def _send(self, fn, name: str):
        start = time.time()
        try:
            tx_hash = _locked_send(self.w3, self.admin, fn)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            elapsed = int((time.time() - start) * 1000)
            ok = receipt.status == 1
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

    @task
    def ciclo_viaje(self):
        origin  = VP1_ID if self._going_to_vp2 else VP2_ID
        dest    = VP2_ID if self._going_to_vp2 else VP1_ID
        trip_id = f"E3C-{uuid.uuid4().hex[:8].upper()}"

        r = self._send(
            self.fr.functions.createReservation(
                trip_id, self.rider, origin, dest, self.evtol_id,
                b"u", b"e", b"v",
            ), "createReservation"
        )
        if not r:
            return

        r = self._send(self.fr.functions.startTrip(trip_id, b"v"), "startTrip")
        if not r:
            return

        r = self._send(self.fr.functions.completeTrip(trip_id, b"v"), "completeTrip")
        if r:
            self._going_to_vp2 = not self._going_to_vp2


# ── Stepped load shape (Poisson, 1→100 usuarios) ─────────────────────────────

class PoissonSteppedShape(LoadTestShape):
    """
    Escala de 1 a 100 usuarios cruzando el techo teórico (~48 usuarios).

    Techo: gas_limit / gas_per_TX / block_time = 16.2M / 400k / 5 = 8 TXs/s
    Con exponential(3): tasa efectiva = N × 3 / (15+3) = N × 0.167 TXs/s
    → techo en N ≈ 48 usuarios.

    Pasos con duración extra en la zona de saturación (50-100u) para dar tiempo
    a que la cola del mempool alcance estado estacionario y la latencia se estabilice.

    Duración total: ~2120 s (~35 min)
    """

    stages = [
        {"users":   1, "spawn_rate":  1, "duration": 180},   # lineal
        {"users":   5, "spawn_rate":  2, "duration": 180},   # lineal
        {"users":  10, "spawn_rate":  5, "duration": 180},   # lineal
        {"users":  20, "spawn_rate":  5, "duration": 200},   # lineal
        {"users":  30, "spawn_rate":  5, "duration": 200},   # lineal
        {"users":  40, "spawn_rate": 10, "duration": 240},   # cerca del techo
        {"users":  50, "spawn_rate": 10, "duration": 300},   # justo sobre el techo
        {"users":  70, "spawn_rate": 10, "duration": 300},   # bien sobre el techo
        {"users": 100, "spawn_rate": 15, "duration": 360},   # saturación clara
    ]

    def tick(self):
        run_time = self.get_run_time()
        elapsed  = 0
        for stage in self.stages:
            elapsed += stage["duration"]
            if run_time < elapsed:
                return (stage["users"], stage["spawn_rate"])
        return None   # test terminado
