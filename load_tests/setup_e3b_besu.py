"""
Setup para Escenario 3b — Stepped load con eVTOLs frescos

Qué hace:
  1. Registra 2 vertiports exclusivos para E3b con capacidad = 2*N cada uno.
  2. Registra N eVTOLs frescos (primer bloque libre a partir de 200).
  3. Marca N parkings ocupados en VP1 (refleja los N eVTOLs parqueados ahí).
  4. Genera N keypairs Ethereum autorizados.
  5. Guarda resultado en load_tests/resultados/e3b_setup.json

Ejecutar UNA VEZ antes del test E3b:
  cd SSI_App
  source venv/bin/activate
  python load_tests/setup_e3b_besu.py --users 30
"""

import argparse, json, pathlib, sys, uuid
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

BASE      = pathlib.Path("~/Documentos/TI3").expanduser()
ADDR_FILE = BASE / "BESU_project/smart_contracts/deployed_addresses.json"
ABI_DIR   = BASE / "BESU_project/smart_contracts/contracts"
OUT_FILE  = pathlib.Path(__file__).parent / "resultados/e3b_setup.json"

RPC_URL    = "http://localhost:8545"
DJANGO_URL = "http://localhost:8000"
DEV_KEY    = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
GAS        = 400_000
EVTOL_START = 200  # IDs reservados para E3b


def load_contract(w3, name):
    addr = json.loads(ADDR_FILE.read_text())[name]
    abi  = json.loads((ABI_DIR / f"{name}.json").read_text())["abi"]
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)


def send(w3, account, fn):
    nonce = w3.eth.get_transaction_count(account.address, "pending")
    tx = fn.build_transaction({
        "from": account.address, "nonce": nonce,
        "gas": GAS, "gasPrice": w3.eth.gas_price,
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


def fund(w3, dev, target, amount_eth=0.5):
    nonce = w3.eth.get_transaction_count(dev.address, "pending")
    tx = {
        "from": dev.address, "to": target,
        "value": w3.to_wei(amount_eth, "ether"),
        "gas": 21_000, "gasPrice": w3.eth.gas_price, "nonce": nonce,
    }
    signed  = dev.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    w3.eth.wait_for_transaction_receipt(tx_hash, timeout=30)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=30)
    args = parser.parse_args()
    N = args.users

    print(f"\n=== Setup E3b Besu — {N} usuarios (eVTOLs frescos) ===\n")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.is_connected():
        sys.exit("ERROR: Besu no disponible en " + RPC_URL)

    dev = w3.eth.account.from_key(DEV_KEY)
    vpm = load_contract(w3, "VertiportManagement")
    evm = load_contract(w3, "EVTOLManagement")
    uv  = load_contract(w3, "UserVerification")

    run_id = uuid.uuid4().hex[:6]
    VP1_ID = f"e3b-vp1-{run_id}"
    VP2_ID = f"e3b-vp2-{run_id}"
    print(f"  Vertiports: {VP1_ID}, {VP2_ID}")

    # Encontrar primer bloque libre de eVTOLs
    evtol_start = EVTOL_START
    while True:
        try:
            evm.functions.getEVTOL(evtol_start).call()
            evtol_start += N
        except Exception:
            break
    print(f"  eVTOLs: {evtol_start}–{evtol_start+N-1}\n")

    # 1. Registrar vertiports (n_parkings = 2*N)
    n_parkings = 2 * N
    print(f"[1/4] Registrando vertiports (airstrips={N}, parkings={n_parkings})...")
    for vpid in [VP1_ID, VP2_ID]:
        sig = get_attestation("/api/attest/vertiport/", {"vertiport_id": vpid})
        send(w3, dev, vpm.functions.registerVertiport(
            vpid, N, n_parkings, b"e3b-vertiport-cred", sig
        ))
        print(f"  ✓ {vpid}")

    # 2. Registrar eVTOLs (todos en VP1)
    print(f"\n[2/4] Registrando {N} eVTOLs...")
    for i in range(N):
        eid = evtol_start + i
        sig = get_attestation("/api/attest/evtol/", {"evtol_id": eid})
        send(w3, dev, evm.functions.registerEVTOL(
            eid, VP1_ID, b"e3b-evtol-cred", sig
        ))
        print(f"  ✓ eVTOL {eid}")

    # 2b. Marcar N parkings ocupados en VP1 (los N eVTOLs recién registrados)
    print(f"\n[2b/4] Ocupando {N} parkings en VP1...")
    send(w3, dev, vpm.functions.updateVertiportState(VP1_ID, b"", 0, -N))
    print(f"  ✓ VP1: {N}/{n_parkings} parkings libres")
    print(f"  ✓ VP2: {n_parkings}/{n_parkings} parkings libres")

    # 3. Generar keypairs y autorizar
    print(f"\n[3/4] Generando y autorizando {N} cuentas...")
    accounts = []
    for i in range(N):
        acct = w3.eth.account.create()
        fund(w3, dev, acct.address)
        sig = get_attestation("/api/attest/user/", {"rider": acct.address, "can_ride": True})
        send(w3, dev, uv.functions.setRiderPermission(acct.address, True, sig))
        accounts.append({
            "address":     acct.address,
            "private_key": acct.key.hex(),
            "evtol_id":    evtol_start + i,
        })
        print(f"  ✓ cuenta {i+1}/{N}: {acct.address[:12]}… (eVTOL {evtol_start+i})")

    # 4. Guardar
    print(f"\n[4/4] Guardando e3b_setup.json...")
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({
        "vp1": VP1_ID, "vp2": VP2_ID,
        "n_users": N, "n_parkings_per_vp": n_parkings,
        "evtol_start": evtol_start,
        "accounts": accounts,
    }, indent=2))
    print(f"  ✓ {OUT_FILE}")
    print(f"\n=== Setup E3b completado. Ejecuta: locust -f load_tests/03b_reservas_besu_stepped.py ===\n")


if __name__ == "__main__":
    main()
