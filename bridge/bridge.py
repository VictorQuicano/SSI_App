#!/usr/bin/env python3
"""
Bridge SSI → Besu

Lee credenciales almacenadas en los wallets ACA-Py y las usa para registrar
entidades en los contratos Besu y ejecutar un viaje completo.

Uso:
    cd SSI_App
    source venv/bin/activate
    python bridge/bridge.py

Prerequisitos:
    1. VON Network corriendo (localhost:9000)
    2. Agentes ACA-Py corriendo: bash agents/start.sh
    3. Django corriendo y credenciales emitidas: python agents/scripts/test_all.py
    4. Red Besu corriendo: cd BESU_project && ./run.sh
    5. Contratos desplegados: cd BESU_project/smart_contracts && node scripts/deploy_system.js
"""
import json, sys, time, uuid
from pathlib import Path
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

# ── Rutas absolutas ───────────────────────────────────────────────────────────

BRIDGE_DIR    = Path(__file__).parent
SSI_APP_DIR   = BRIDGE_DIR.parent
TI3_DIR       = SSI_APP_DIR.parent
BESU_DIR      = TI3_DIR / "BESU_project" / "smart_contracts"
CONTRACTS_DIR = BESU_DIR / "contracts"
ADDRESSES_FILE = BESU_DIR / "deployed_addresses.json"

# ── Configuración ─────────────────────────────────────────────────────────────

BESU_RPC      = "http://localhost:8545"
PRIVATE_KEY   = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

DJANGO_API  = "http://localhost:8000"

AGENTS = {
    "user1":      "http://localhost:8041",
    "evtol1":     "http://localhost:8051",
    "vertiport1": "http://localhost:8061",
    "vertiport2": "http://localhost:8071",
}

POLL_INTERVAL = 2
POLL_TIMEOUT  = 90

# ── Helpers ───────────────────────────────────────────────────────────────────

def banner(msg: str):
    print(f"\n{'─' * 60}\n  {msg}\n{'─' * 60}")


def attrs_to_bytes(attrs: dict) -> bytes:
    """Serializa atributos de credencial como JSON bytes para pasarlos on-chain."""
    return json.dumps(attrs, sort_keys=True).encode("utf-8")


# ── Fase 0: Atestaciones Trusted Verifier ────────────────────────────────────

def get_attestation(endpoint: str, payload: dict) -> bytes:
    """Pide a Django que firme una atestación y devuelve los 65 bytes de firma."""
    resp = requests.post(f"{DJANGO_API}{endpoint}", json=payload, timeout=10)
    resp.raise_for_status()
    sig_hex = resp.json()["signature"]
    return bytes.fromhex(sig_hex.removeprefix("0x"))


def get_user_attestation(rider: str, can_ride: bool) -> bytes:
    return get_attestation("/api/attest/user/", {"rider": rider, "can_ride": can_ride})


def get_vertiport_attestation(vertiport_id: str) -> bytes:
    return get_attestation("/api/attest/vertiport/", {"vertiport_id": vertiport_id})


def get_evtol_attestation(evtol_id: int) -> bytes:
    return get_attestation("/api/attest/evtol/", {"evtol_id": evtol_id})


# ── Fase 1: Leer credenciales de ACA-Py ──────────────────────────────────────

def read_credential(agent_url: str, schema_name: str, timeout: int = POLL_TIMEOUT) -> dict:
    """
    Espera hasta que el agente tenga almacenada una credencial del schema dado.
    Devuelve el dict de atributos {nombre: valor}.
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{agent_url}/credentials", timeout=10)
            results = resp.json().get("results", [])
            for cred in results:
                if schema_name in cred.get("schema_id", ""):
                    # /credentials devuelve attrs como dict {nombre: valor}
                    return cred["attrs"]
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Credencial '{schema_name}' no encontrada en {agent_url} ({timeout}s)")


def read_all_credentials() -> dict:
    banner("FASE 1 — Leyendo credenciales de los agentes ACA-Py")

    print("  Leyendo user_credential (user1)...")
    user_attrs = read_credential(AGENTS["user1"], "user_credential")
    print(f"  ✅ user1: can_ride={user_attrs.get('can_ride')}")

    print("  Leyendo evtol_credential (evtol1)...")
    evtol_attrs = read_credential(AGENTS["evtol1"], "evtol_credential")
    print(f"  ✅ evtol1: id_puerto={evtol_attrs.get('id_puerto')}, name={evtol_attrs.get('name')}")

    print("  Leyendo vertiport_credential (vertiport1)...")
    vp1_attrs = read_credential(AGENTS["vertiport1"], "vertiport_credential")
    print(f"  ✅ vertiport1: id={vp1_attrs.get('id_vertiport')}, capacity={vp1_attrs.get('capacity')}")

    print("  Leyendo vertiport_credential (vertiport2)...")
    vp2_attrs = read_credential(AGENTS["vertiport2"], "vertiport_credential")
    print(f"  ✅ vertiport2: id={vp2_attrs.get('id_vertiport')}, capacity={vp2_attrs.get('capacity')}")

    return {
        "user":       user_attrs,
        "evtol":      evtol_attrs,
        "vertiport1": vp1_attrs,
        "vertiport2": vp2_attrs,
    }


# ── Carga de contratos ────────────────────────────────────────────────────────

def load_contract(w3: Web3, name: str, address: str):
    abi = json.loads((CONTRACTS_DIR / f"{name}.json").read_text())["abi"]
    return w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)


def setup_web3():
    if not ADDRESSES_FILE.exists():
        raise FileNotFoundError(
            f"No se encontró {ADDRESSES_FILE}\n"
            "Ejecuta primero: cd BESU_project/smart_contracts && node scripts/deploy_system.js"
        )
    addresses = json.loads(ADDRESSES_FILE.read_text())

    w3 = Web3(Web3.HTTPProvider(BESU_RPC))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.is_connected():
        raise ConnectionError(f"No se puede conectar a Besu en {BESU_RPC}")

    account = w3.eth.account.from_key(PRIVATE_KEY)
    w3.eth.default_account = account.address

    contracts = {
        "user_verification":    load_contract(w3, "UserVerification",    addresses["UserVerification"]),
        "vertiport_management": load_contract(w3, "VertiportManagement", addresses["VertiportManagement"]),
        "evtol_management":     load_contract(w3, "EVTOLManagement",     addresses["EVTOLManagement"]),
        "flight_reservation":   load_contract(w3, "FlightReservation",   addresses["FlightReservation"]),
    }
    return w3, account, contracts


def send_tx(w3: Web3, account, fn):
    """Construye, firma y envía una transacción; lanza excepción si revierte."""
    nonce = w3.eth.get_transaction_count(account.address)
    tx = fn.build_transaction({
        "from":     account.address,
        "nonce":    nonce,
        "gas":      500_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status == 0:
        raise Exception(f"Transacción revirtió (hash={tx_hash.hex()})")
    return receipt


# ── Fase 2: Registrar entidades en Besu ──────────────────────────────────────

def register_entities(w3: Web3, account, contracts: dict, creds: dict):
    banner("FASE 2 — Registrando entidades en Besu")

    uv  = contracts["user_verification"]
    vpm = contracts["vertiport_management"]
    evm = contracts["evtol_management"]

    rider_addr = account.address  # en el demo, el admin es también el rider
    can_ride   = creds["user"].get("can_ride", "false").lower() == "true"

    # 2a. Autorizar usuario — atestación firmada por Django (Trusted Verifier)
    print(f"  [2a] Solicitando atestación de usuario a Django...")
    user_sig = get_user_attestation(rider_addr, can_ride)
    print(f"  [2a] setRiderPermission({rider_addr[:10]}…, {can_ride}) + atestación")
    send_tx(w3, account, uv.functions.setRiderPermission(rider_addr, can_ride, user_sig))
    stored = uv.functions.canUserRide(rider_addr).call()
    assert stored == can_ride, f"canUserRide mismatch: {stored} != {can_ride}"
    print(f"  ✅ Usuario autorizado (can_ride={can_ride})")

    def _register_vertiport(vp_label, vp_id, vp_cap, vp_bytes, step):
        print(f"  [{step}] registerVertiport({vp_id}, airstrips=1, parkings={vp_cap})")
        try:
            vpm.functions.getVertiportState(vp_id).call()
            print(f"  ⚠️  {vp_id} ya registrado — saltando")
            return False  # ya existía
        except Exception:
            pass  # no existe → registrar
        print(f"  [{step}] Solicitando atestación de vertiport a Django...")
        vp_sig = get_vertiport_attestation(vp_id)
        send_tx(w3, account, vpm.functions.registerVertiport(vp_id, 1, vp_cap, vp_bytes, vp_sig))
        print(f"  ✅ {vp_label} registrado ({vp_id})")
        return True  # recién registrado

    # 2b. Registrar vertiport1
    vp1 = creds["vertiport1"]
    vp1_id    = vp1["id_vertiport"]
    vp1_cap   = int(vp1["capacity"])
    vp1_bytes = attrs_to_bytes(vp1)
    vp1_new   = _register_vertiport("Vertiport1", vp1_id, vp1_cap, vp1_bytes, "2b")

    # 2c. Registrar vertiport2
    vp2 = creds["vertiport2"]
    vp2_id    = vp2["id_vertiport"]
    vp2_cap   = int(vp2["capacity"])
    vp2_bytes = attrs_to_bytes(vp2)
    _register_vertiport("Vertiport2", vp2_id, vp2_cap, vp2_bytes, "2c")

    # 2d. Registrar eVTOL (idempotente)
    # id_puerto en la credencial es un valor demo ("p1"); el eVTOL se ubica en vp1_id
    evtol       = creds["evtol"]
    evtol_vp    = vp1_id
    evtol_bytes = attrs_to_bytes(evtol)
    evtol_id    = 1
    print(f"  [2d] registerEVTOL(id={evtol_id}, vertiport={evtol_vp})")
    try:
        evm.functions.getEVTOL(evtol_id).call()
        print(f"  ⚠️  eVTOL id={evtol_id} ya registrado — saltando")
        vp1_new = False  # no pre-ocupar parking de nuevo
    except Exception:
        print(f"  [2d] Solicitando atestación de eVTOL a Django...")
        evtol_sig = get_evtol_attestation(evtol_id)
        send_tx(w3, account, evm.functions.registerEVTOL(evtol_id, evtol_vp, evtol_bytes, evtol_sig))
        print(f"  ✅ eVTOL registrado (id={evtol_id})")

    # 2e. Pre-ocupar 1 parking solo si el eVTOL se registró ahora
    if vp1_new:
        print(f"  [2e] updateVertiportState({evtol_vp}, parkingDelta=-1) — pre-ocupar parking del eVTOL")
        send_tx(w3, account, vpm.functions.updateVertiportState(evtol_vp, vp1_bytes, 0, -1))
        print(f"  ✅ Parking pre-ocupado en {evtol_vp}")
    else:
        print(f"  [2e] Parking ya pre-ocupado — saltando")

    return {
        "rider_addr":   rider_addr,
        "evtol_id":     evtol_id,
        "evtol_vp":     evtol_vp,
        "vp1_id":       vp1_id,
        "vp1_bytes":    vp1_bytes,
        "vp2_id":       vp2_id,
        "vp2_bytes":    vp2_bytes,
        "evtol_bytes":  evtol_bytes,
        "user_bytes":   attrs_to_bytes(creds["user"]),
    }


# ── Fase 3: Ejecutar viaje completo via FlightReservation ────────────────────

def execute_trip(w3: Web3, account, contracts: dict, state: dict):
    banner("FASE 3 — Ejecutando viaje vía FlightReservation")

    fr = contracts["flight_reservation"]

    trip_id    = f"TRIP-BRIDGE-{uuid.uuid4().hex[:8].upper()}"
    rider      = state["rider_addr"]
    origin_vp  = state["evtol_vp"]
    # destino: el otro vertiport
    dest_vp    = state["vp2_id"] if origin_vp == state["vp1_id"] else state["vp1_id"]
    evtol_id   = state["evtol_id"]
    user_bytes = state["user_bytes"]
    orig_bytes = state["vp1_bytes"] if origin_vp == state["vp1_id"] else state["vp2_bytes"]
    dest_bytes = state["vp2_bytes"] if dest_vp   == state["vp2_id"] else state["vp1_bytes"]
    evtol_bytes = state["evtol_bytes"]

    print(f"  Trip ID  : {trip_id}")
    print(f"  Rider    : {rider}")
    print(f"  Origen   : {origin_vp}  →  Destino: {dest_vp}")
    print(f"  eVTOL    : id={evtol_id}")

    # 3a. Crear reserva (CONFIRMED)
    print(f"\n  [3a] createReservation...")
    send_tx(w3, account, fr.functions.createReservation(
        trip_id, rider, origin_vp, dest_vp, evtol_id,
        user_bytes, orig_bytes, evtol_bytes,
    ))
    trip = fr.functions.getTrip(trip_id).call()
    print(f"  ✅ Reserva creada — status={trip[5]} (1=CONFIRMED)")

    # 3b. Pre-ocupar el parking del origen (el eVTOL estaba aparcado ahí)
    #     startTrip libera ese parking con +1; si no lo pre-ocupamos revierte.
    vp_state = contracts["vertiport_management"].functions.getVertiportState(origin_vp).call()
    n_free, n_total = vp_state[4], vp_state[2]   # n_parkings_free, n_parkings
    if n_free == n_total:
        print(f"\n  [3b-pre] Pre-ocupando parking en {origin_vp} ({n_free}/{n_total})...")
        send_tx(w3, account, contracts["vertiport_management"].functions.updateVertiportState(
            origin_vp, orig_bytes, 0, -1
        ))

    # Iniciar viaje (IN_PROGRESS)
    print(f"\n  [3b] startTrip...")
    send_tx(w3, account, fr.functions.startTrip(trip_id, orig_bytes))
    trip = fr.functions.getTrip(trip_id).call()
    print(f"  ✅ Viaje iniciado — status={trip[5]} (2=IN_PROGRESS)")

    # 3c. Completar viaje (COMPLETED)
    print(f"\n  [3c] completeTrip...")
    send_tx(w3, account, fr.functions.completeTrip(trip_id, dest_bytes))
    trip = fr.functions.getTrip(trip_id).call()
    print(f"  ✅ Viaje completado — status={trip[5]} (3=COMPLETED)")

    return trip_id


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  Bridge SSI → Besu")
    print("=" * 60)

    try:
        creds = read_all_credentials()
    except TimeoutError as e:
        print(f"\n❌ {e}")
        print("  Asegúrate de haber ejecutado primero: python agents/scripts/test_all.py")
        sys.exit(1)

    try:
        w3, account, contracts = setup_web3()
        print(f"\n  Conectado a Besu: {BESU_RPC}")
        print(f"  Cuenta admin   : {account.address}")
    except (FileNotFoundError, ConnectionError) as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    state   = register_entities(w3, account, contracts, creds)
    trip_id = execute_trip(w3, account, contracts, state)

    banner("RESULTADO")
    print(f"  Trip ID  : {trip_id}")
    print(f"  Estado   : COMPLETED ✅")
    print(f"\n  El flujo SSI → Besu funcionó de extremo a extremo.")
    print(f"  Credenciales SSI reales usadas como bytes en los contratos.")


if __name__ == "__main__":
    main()
