"""
Escenario 3 — Throughput de reservas de vuelo en Besu

Qué mide:
  Latencia de confirmación de bloque (ms desde envío hasta receipt) y
  transacciones por segundo que la red Besu puede procesar para el ciclo
  completo createReservation → startTrip → completeTrip.

Nota de diseño:
  Todas las transacciones salen de la misma cuenta (dev key de Besu), por lo
  que los nonces deben ser estrictamente secuenciales. Un lock global serializa
  la asignación de nonce — el paralelismo real en Besu es a nivel de bloque,
  no de submission. Los usuarios concurrentes comparten un único EVTOL, por lo
  que solo un viaje puede estar activo a la vez (lógica del contrato).
  Los fallos a >1 usuario reflejan esta restricción del contrato, no una
  limitación de la red Besu.

Prerequisito:
  - Besu corriendo (localhost:8545)
  - Contratos desplegados (deployed_addresses.json)
  - bridge.py ejecutado (registra user, vertiports, EVTOL)

Cómo ejecutar:
  cd SSI_App
  locust -f load_tests/03_reservas_besu.py --host=http://localhost:8545 \\
         --users 1 --spawn-rate 1 --run-time 120s --headless \\
         --html load_tests/resultados/besu_1u.html
"""

import threading
import time
import uuid
from pathlib import Path
import json

from locust import User, task, constant, events

from web3 import Web3
from web3.middleware import geth_poa_middleware

# ── Configuración ─────────────────────────────────────────────────────────────

BASE = Path("~/Documentos/TI3").expanduser()
_addr     = json.loads((BASE / "BESU_project/smart_contracts/deployed_addresses.json").read_text())
_fr_abi   = json.loads((BASE / "BESU_project/smart_contracts/contracts/FlightReservation.json").read_text())["abi"]
_evtol_abi = json.loads((BASE / "BESU_project/smart_contracts/contracts/EVTOLManagement.json").read_text())["abi"]

KEY     = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
RPC_URL = "http://localhost:8545"

# Los dos vertiports registrados por bridge.py
VP_A = "vp1-7805"
VP_B = "vp2-7805"

# ── Nonce centralizado (todas las tx de una sola cuenta) ─────────────────────

_nonce_lock  = threading.Lock()
_nonce_value = [None]

def _next_nonce(w3, account):
    with _nonce_lock:
        if _nonce_value[0] is None:
            _nonce_value[0] = w3.eth.get_transaction_count(account.address)
        n = _nonce_value[0]
        _nonce_value[0] += 1
    return n

# ── Alternancia de vertiports (el EVTOL viaja A→B, luego B→A, etc.) ─────────
# Al arrancar, recupera cualquier EVTOL atascado (EXPECTING/IN_USE) de una
# corrida anterior y luego detecta la ubicación para sincronizar la dirección.

def _recover_and_detect() -> int:
    """Completa viajes activos atascados y devuelve la dirección inicial correcta."""
    try:
        _w3 = Web3(Web3.HTTPProvider(RPC_URL))
        _w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        _account = _w3.eth.account.from_key(KEY)

        _evtol_abi = json.loads(
            (BASE / "BESU_project/smart_contracts/contracts/EVTOLManagement.json").read_text()
        )["abi"]
        _evtol = _w3.eth.contract(
            address=Web3.to_checksum_address(_addr["EVTOLManagement"]),
            abi=_evtol_abi,
        )
        _fr = _w3.eth.contract(
            address=Web3.to_checksum_address(_addr["FlightReservation"]),
            abi=_fr_abi,
        )

        def _send_recovery(fn):
            nonce = _w3.eth.get_transaction_count(_account.address)
            tx = fn.build_transaction({
                "from": _account.address, "nonce": nonce,
                "gas": 350_000, "gasPrice": _w3.eth.gas_price,
            })
            signed = _account.sign_transaction(tx)
            txh = _w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = _w3.eth.wait_for_transaction_receipt(txh, timeout=30)
            return receipt.status == 1

        evtol_data = _evtol.functions.getEVTOL(1).call()
        state     = evtol_data[1]   # 0=PARKED, 1=EXPECTING, 2=IN_USE
        active_id = evtol_data[3]   # activeTripId
        location  = evtol_data[2]   # currentVertiportId (read before if block)

        if state in (1, 2) and active_id:
            print(f"[recovery] EVTOL en estado {state} ({active_id}), reseteando via evtolManagement...")
            if state == 1:  # EXPECTING → forzar IN_USE sin checar vertiports
                _send_recovery(_evtol.functions.startTrip(1))
            # Completar en la ubicación actual (no mover el EVTOL)
            _send_recovery(_evtol.functions.completeTrip(1, location))
            evtol_data = _evtol.functions.getEVTOL(1).call()
            location  = evtol_data[2]  # re-leer tras recovery
        return 0 if location == VP_A else 1  # 0=vp1→vp2 si en vp1, 1=vp2→vp1 si en vp2
    except Exception as exc:
        print(f"[recovery] error: {exc}")
        return 1

# Recover any stuck trips, then detect initial direction (run once at startup).
_recover_and_detect()

# ── Usuario Locust ────────────────────────────────────────────────────────────

class BesuUser(User):
    wait_time = constant(0)   # máximo throughput, sin pausa entre tareas

    def on_start(self):
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
        self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        self.account = self.w3.eth.account.from_key(KEY)
        self.fr = self.w3.eth.contract(
            address=Web3.to_checksum_address(_addr["FlightReservation"]),
            abi=_fr_abi,
        )
        self.evtol = self.w3.eth.contract(
            address=Web3.to_checksum_address(_addr["EVTOLManagement"]),
            abi=_evtol_abi,
        )

    # ── helper: build, sign, send, wait ──────────────────────────────────────

    def _send(self, fn, name: str):
        start = time.time()
        try:
            nonce = _next_nonce(self.w3, self.account)
            tx = fn.build_transaction({
                "from":      self.account.address,
                "nonce":     nonce,
                "gas":       350_000,
                "gasPrice":  self.w3.eth.gas_price,
            })
            signed  = self.account.sign_transaction(tx)
            txh     = self.w3.eth.send_raw_transaction(signed.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(txh, timeout=30)
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

    # ── tarea principal: ciclo completo de viaje ──────────────────────────────

    @task
    def ciclo_viaje(self):
        # Lee la ubicación real del EVTOL para garantizar que origin coincida
        # con su posición actual. Esto evita que startTrip revierta por intentar
        # liberar un parking en un vertiport que ya está lleno.
        try:
            evtol_data = self.evtol.functions.getEVTOL(1).call()
        except Exception:
            return
        location = evtol_data[2]   # currentVertiportId
        origin   = location
        dest     = VP_B if location == VP_A else VP_A

        trip_id   = f"LD-{uuid.uuid4().hex[:8].upper()}"
        user_addr = self.account.address

        # 1 — createReservation
        r = self._send(
            self.fr.functions.createReservation(
                trip_id, user_addr, origin, dest, 1, b"u", b"e", b"v"
            ),
            "createReservation",
        )
        if not r:
            return

        # 2 — startTrip
        r = self._send(
            self.fr.functions.startTrip(trip_id, b"v"),
            "startTrip",
        )
        if not r:
            return

        # 3 — completeTrip
        self._send(
            self.fr.functions.completeTrip(trip_id, b"v"),
            "completeTrip",
        )
