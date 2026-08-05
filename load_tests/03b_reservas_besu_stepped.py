"""
Escenario 3b — Stepped load de reservas Besu (eVTOLs independientes, sin batch)

Diferencias clave respecto al Escenario 3 original:
  - LoadTestShape escalonado: 1→3→5→10→15→20→30 usuarios
    Los usuarios se SUMAN en cada paso; nadie se mata entre pasos.
    Esto elimina el artefacto de eVTOLs bloqueados que contaminaba E3.
  - wait_time = constant(0): sin pausa entre ciclos, máxima presión sobre el nonce.
  - Lee e3b_setup.json (30 eVTOLs frescos, 200–229).

Cómo ejecutar (requiere setup previo con setup_e3b_besu.py):
  locust -f load_tests/03b_reservas_besu_stepped.py \\
         --host=http://localhost:8545 --headless \\
         --csv=load_tests/resultados/e3b \\
         --html=load_tests/resultados/e3b_stepped.html

  El test dura ~17 min (7 pasos × 120-180 s cada uno) y luego para solo.
  Los resultados por paso se extraen del archivo e3b_stats_history.csv.
"""

import json, pathlib, time, uuid
import gevent.lock
from locust import User, task, constant, events, LoadTestShape
from web3 import Web3
from web3.middleware import geth_poa_middleware

# ── Cargar setup ──────────────────────────────────────────────────────────────
SETUP_FILE = pathlib.Path(__file__).parent / "resultados/e3b_setup.json"
if not SETUP_FILE.exists():
    raise FileNotFoundError(
        "Archivo e3b_setup.json no encontrado.\n"
        "Ejecuta primero: python load_tests/setup_e3b_besu.py --users 30"
    )

_setup    = json.loads(SETUP_FILE.read_text())
VP1_ID    = _setup["vp1"]
VP2_ID    = _setup["vp2"]
_ACCOUNTS = _setup["accounts"]

# ── Contratos ─────────────────────────────────────────────────────────────────
BASE    = pathlib.Path("~/Documentos/TI3").expanduser()
_addr   = json.loads((BASE / "BESU_project/smart_contracts/deployed_addresses.json").read_text())
_fr_abi = json.loads((BASE / "BESU_project/smart_contracts/contracts/FlightReservation.json").read_text())["abi"]
RPC_URL = "http://localhost:8545"
ADMIN_KEY = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

# ── Nonce centralizado ────────────────────────────────────────────────────────
_send_lock = gevent.lock.Semaphore(1)

import logging as _logging
_log = _logging.getLogger("locust.nonce")

def _locked_send(w3, account, tx_fn, gas=400_000):
    """Obtiene nonce y envía TX bajo lock. Receipt wait se hace fuera del lock."""
    _send_lock.acquire()
    try:
        nonce = w3.eth.get_transaction_count(account.address, "pending")
        tx = tx_fn.build_transaction({
            "from": account.address, "nonce": nonce,
            "gas": gas, "gasPrice": w3.eth.gas_price,
        })
        signed  = account.sign_transaction(tx)
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
            f"Solo hay {len(_ACCOUNTS)} slots pero se pidió {idx+1}. "
            "Regenera el setup con más usuarios."
        )
    return _ACCOUNTS[idx]

# ── Usuario Locust ────────────────────────────────────────────────────────────

class BesuUser(User):
    # Sin pausa: maximiza la presión sobre el nonce y expone el techo de throughput
    wait_time = constant(0)

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
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=90)
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
        trip_id = f"E3B-{uuid.uuid4().hex[:8].upper()}"

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


# ── Stepped load shape ────────────────────────────────────────────────────────

class SteppedShape(LoadTestShape):
    """
    Escalona el número de usuarios activos:
      1u (120s) → 3u (120s) → 5u (120s) → 10u (150s) → 15u (150s) → 20u (180s) → 30u (180s)

    Los usuarios existentes NUNCA se matan entre pasos: sólo se agregan nuevos.
    Esto garantiza que los eVTOLs no queden bloqueados entre niveles de carga.

    Duración total: ~1020 s (~17 min)
    """

    stages = [
        {"users":  1, "spawn_rate":  1, "duration": 120},
        {"users":  3, "spawn_rate":  2, "duration": 120},
        {"users":  5, "spawn_rate":  2, "duration": 120},
        {"users": 10, "spawn_rate":  5, "duration": 150},
        {"users": 15, "spawn_rate":  5, "duration": 150},
        {"users": 20, "spawn_rate":  5, "duration": 180},
        {"users": 30, "spawn_rate": 10, "duration": 180},
    ]

    def tick(self):
        run_time = self.get_run_time()
        elapsed  = 0
        for stage in self.stages:
            elapsed += stage["duration"]
            if run_time < elapsed:
                return (stage["users"], stage["spawn_rate"])
        return None   # detener el test
