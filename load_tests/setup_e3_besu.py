"""
Setup para Escenario 3 — Reservas Besu con cuentas independientes

Qué hace:
  1. Registra 2 vertiports exclusivos para E3 (e3-vp1, e3-vp2) con
     capacidad = N_USERS, usando la firma del TrustedVerifier via Django.
  2. Registra N_USERS eVTOLs (IDs 10 … 10+N-1) en EVTOLManagement.
  3. Genera N_USERS keypairs Ethereum, los financia desde la dev account
     y llama setRiderPermission(address, true) para cada uno.
  4. Guarda el resultado en load_tests/resultados/e3_setup.json

Ejecutar UNA VEZ antes de correr el test E3:
  cd SSI_App
  source venv/bin/activate
  python load_tests/setup_e3_besu.py --users 10
"""

import argparse
import json
import pathlib
import sys
import time
import uuid

import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

# ── Configuración ─────────────────────────────────────────────────────────────

BASE       = pathlib.Path("~/Documentos/TI3").expanduser()
ADDR_FILE  = BASE / "BESU_project/smart_contracts/deployed_addresses.json"
ABI_DIR    = BASE / "BESU_project/smart_contracts/contracts"
OUT_FILE   = pathlib.Path(__file__).parent / "resultados/e3_setup.json"

RPC_URL    = "http://localhost:8545"
DJANGO_URL = "http://localhost:8000"
DEV_KEY    = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"

EVTOL_ID_START = 10   # IDs 10, 11, 12, … para no chocar con el eVTOL 1 del bridge

GAS     = 400_000
GAS_P   = None        # se obtiene del nodo


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_contract(w3, name):
    addr = json.loads(ADDR_FILE.read_text())[name]
    abi  = json.loads((ABI_DIR / f"{name}.json").read_text())["abi"]
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)


def send(w3, account, fn):
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    tx = fn.build_transaction({
        "from": account.address,
        "nonce": nonce,
        "gas": GAS,
        "gasPrice": w3.eth.gas_price,
    })
    signed  = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
    if receipt.status != 1:
        raise RuntimeError(f"tx revertida: {tx_hash.hex()}")
    return receipt


def get_attestation(endpoint, payload):
    r = requests.post(f"{DJANGO_URL}{endpoint}", json=payload, timeout=15)
    r.raise_for_status()
    sig_hex = r.json()["signature"]
    return bytes.fromhex(sig_hex.removeprefix("0x"))


def fund(w3, dev_account, target_address, amount_eth=0.1):
    nonce = w3.eth.get_transaction_count(dev_account.address, "pending")
    tx = {
        "from":     dev_account.address,
        "to":       target_address,
        "value":    w3.to_wei(amount_eth, "ether"),
        "gas":      21_000,
        "gasPrice": w3.eth.gas_price,
        "nonce":    nonce,
    }
    signed  = dev_account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)


# ── Pasos de setup ────────────────────────────────────────────────────────────

def register_vertiport(w3, account, vpm, vp_id, n_users):
    """Registra un vertiport con n_parkings=2*N para que los viajes VP1↔VP2 no desborden.

    El contrato modela n_parkings_free como spots disponibles:
      - startTrip  en origen: +1 parking (eVTOL sale, libera spot)
      - completeTrip en destino: -1 parking (eVTOL llega, ocupa spot)
    Con n_parkings=2*N y N eVTOLs ya "parqueados" (decrementados en paso 2b),
    VP1 empieza con n_free=N y oscila entre N y 2*N durante los viajes.
    """
    sig = get_attestation("/api/attest/vertiport/", {"vertiport_id": vp_id})
    n_parkings = 2 * n_users
    send(w3, account, vpm.functions.registerVertiport(
        vp_id, n_users, n_parkings, b"e3-vertiport-cred", sig
    ))
    print(f"  ✓ {vp_id} registrado (airstrips={n_users}, parkings={n_parkings})")


def register_evtol(w3, account, evm, evtol_id, initial_vp):
    try:
        evm.functions.getEVTOL(evtol_id).call()
        print(f"  ✓ eVTOL {evtol_id} ya registrado, omitiendo.")
        return
    except Exception:
        pass

    sig = get_attestation("/api/attest/evtol/", {"evtol_id": evtol_id})
    send(w3, account, evm.functions.registerEVTOL(
        evtol_id, initial_vp, b"e3-evtol-cred", sig
    ))
    print(f"  ✓ eVTOL {evtol_id} registrado en {initial_vp}")


def authorize_rider(w3, account, uv, rider_address):
    already = uv.functions.canUserRide(rider_address).call()
    if already:
        return
    sig = get_attestation("/api/attest/user/", {"rider": rider_address, "can_ride": True})
    send(w3, account, uv.functions.setRiderPermission(rider_address, True, sig))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=10,
                        help="Número de usuarios (keypairs + eVTOLs) a preparar")
    args = parser.parse_args()
    N = args.users

    print(f"\n=== Setup E3 Besu — {N} usuarios independientes ===\n")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.is_connected():
        sys.exit("ERROR: Besu no disponible en " + RPC_URL)

    dev_account = w3.eth.account.from_key(DEV_KEY)
    vpm = load_contract(w3, "VertiportManagement")
    evm = load_contract(w3, "EVTOLManagement")
    uv  = load_contract(w3, "UserVerification")

    # IDs únicos por corrida para evitar colisiones con runs anteriores
    run_id = uuid.uuid4().hex[:6]
    VP1_ID = f"e3a-{run_id}"
    VP2_ID = f"e3b-{run_id}"
    print(f"  IDs de vertiport para esta corrida: {VP1_ID}, {VP2_ID}")

    # IDs de eVTOL: buscar el primer bloque libre a partir de EVTOL_ID_START
    evtol_start = EVTOL_ID_START
    while True:
        try:
            evm.functions.getEVTOL(evtol_start).call()
            evtol_start += N  # saltar al siguiente bloque libre
        except Exception:
            break  # evtol_start no está registrado → bloque libre encontrado
    print(f"  IDs de eVTOL para esta corrida: {evtol_start}–{evtol_start+N-1}")

    # 1. Registrar vertiports con n_parkings=2*N para que los viajes no desborden
    print(f"\n[1/4] Registrando vertiports (airstrips={N}, parkings={2*N})...")
    register_vertiport(w3, dev_account, vpm, VP1_ID, N)
    register_vertiport(w3, dev_account, vpm, VP2_ID, N)

    # 2. Registrar N eVTOLs (todos en VP1 inicialmente)
    print(f"\n[2/4] Registrando {N} eVTOLs (IDs {evtol_start}–{evtol_start+N-1})...")
    for i in range(N):
        evtol_id = evtol_start + i
        register_evtol(w3, dev_account, evm, evtol_id, VP1_ID)

    # 2b. Consumir N parkings en VP1 para reflejar los N eVTOLs parqueados ahí.
    #     Sin esto, VP1 empieza con n_parkings_free=2*N y startTrip intenta
    #     llevarlo a 2*N+1, desbordando el máximo.
    print(f"\n[2b/4] Marcando {N} parkings ocupados en VP1 ({VP1_ID})...")
    send(w3, dev_account, vpm.functions.updateVertiportState(
        VP1_ID, b"", 0, -N
    ))
    print(f"  ✓ VP1: n_parkings_free = {N} de {2*N} (los {N} eVTOLs ocupan {N} spots)")

    # 3. Generar keypairs, financiarlos y autorizarlos
    print(f"\n[3/4] Generando y autorizando {N} cuentas Ethereum (VP2 empieza vacío, {2*N} parkings libres)...")
    accounts = []
    for i in range(N):
        acct = w3.eth.account.create()
        fund(w3, dev_account, acct.address, amount_eth=0.5)
        authorize_rider(w3, dev_account, uv, acct.address)
        accounts.append({
            "address":     acct.address,
            "private_key": acct.key.hex(),
            "evtol_id":    evtol_start + i,
        })
        print(f"  ✓ cuenta {i+1}/{N}: {acct.address[:12]}… (eVTOL {evtol_start+i})")

    # 4. Guardar resultados
    print(f"\n[4/4] Guardando configuración...")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    setup_data = {
        "vp1": VP1_ID,
        "vp2": VP2_ID,
        "n_users": N,
        "n_parkings_per_vp": 2 * N,
        "vp1_initial_free": N,
        "vp2_initial_free": 2 * N,
        "accounts": accounts,
    }
    OUT_FILE.write_text(json.dumps(setup_data, indent=2))
    print(f"  ✓ Guardado en {OUT_FILE}")

    print(f"\n=== Setup completado. Ejecuta el test E3 con --users {N} ===\n")


if __name__ == "__main__":
    main()
