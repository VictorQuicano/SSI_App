"""
Setup para Escenario 3c — Llegadas Poisson, 100 usuarios

Qué hace:
  1. Registra 2 vertiports exclusivos para E3c (200 parkings, 50 airstrips c/u).
  2. Registra 100 eVTOLs frescos (IDs desde 300, primer bloque libre).
  3. Pre-ocupa 50 parkings en VP1 (mitad de eVTOLs parqueados al inicio).
  4. Genera 100 keypairs Ethereum autorizados.
  5. Usa envío batch (sin esperar receipt por TX) → completa en ~2-3 min
     en lugar de 15+ min con TX secuenciales.
  6. Guarda resultado en load_tests/resultados/e3c_setup.json

Ejecutar UNA VEZ antes del test E3c:
  cd SSI_App
  source venv/bin/activate
  python load_tests/setup_e3c_besu.py --users 100
"""

import argparse, json, pathlib, sys, time, uuid
import requests
from web3 import Web3
from web3.middleware import geth_poa_middleware

BASE      = pathlib.Path("~/Documentos/TI3").expanduser()
ADDR_FILE = BASE / "BESU_project/smart_contracts/deployed_addresses.json"
ABI_DIR   = BASE / "BESU_project/smart_contracts/contracts"
OUT_FILE  = pathlib.Path(__file__).parent / "resultados/e3c_setup.json"

RPC_URL     = "http://localhost:8545"
DJANGO_URL  = "http://localhost:8000"
DEV_KEY     = "0x8f2a55949038a9610f50fb23b5883af3b4ecb3c3bb792cbcefbd1542c692be63"
GAS         = 400_000
EVTOL_START = 300  # bloque de IDs reservados para E3c


def load_contract(w3, name):
    addr = json.loads(ADDR_FILE.read_text())[name]
    abi  = json.loads((ABI_DIR / f"{name}.json").read_text())["abi"]
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)


def get_attestation(endpoint, payload):
    r = requests.post(f"{DJANGO_URL}{endpoint}", json=payload, timeout=15)
    r.raise_for_status()
    return bytes.fromhex(r.json()["signature"].removeprefix("0x"))


class BatchSender:
    """
    Envía múltiples TXs con nonces consecutivos sin esperar receipts.
    Llama a wait_all() al final de cada grupo para confirmar el bloque.

    Ventaja: 100 TXs se minan en 100/40 = 3 bloques × 5s = ~15s
             en lugar de 100 × 5s = 500s con envío secuencial.
    """

    def __init__(self, w3, account):
        self.w3      = w3
        self.account = account
        self._nonce  = w3.eth.get_transaction_count(account.address, "pending")
        self._hashes = []

    def send(self, fn, gas=GAS):
        tx = fn.build_transaction({
            "from":     self.account.address,
            "nonce":    self._nonce,
            "gas":      gas,
            "gasPrice": self.w3.eth.gas_price,
        })
        signed  = self.account.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        self._hashes.append(h)
        self._nonce += 1
        return h

    def send_eth(self, to, value_eth=0.5):
        tx = {
            "from":     self.account.address,
            "to":       to,
            "value":    self.w3.to_wei(value_eth, "ether"),
            "gas":      21_000,
            "gasPrice": self.w3.eth.gas_price,
            "nonce":    self._nonce,
        }
        signed  = self.account.sign_transaction(tx)
        h = self.w3.eth.send_raw_transaction(signed.rawTransaction)
        self._hashes.append(h)
        self._nonce += 1
        return h

    def wait_all(self, label="", timeout=300):
        n = len(self._hashes)
        if not n:
            return
        t0 = time.time()
        for i, h in enumerate(self._hashes):
            receipt = self.w3.eth.wait_for_transaction_receipt(h, timeout=timeout)
            if receipt.status != 1:
                raise RuntimeError(f"TX revertida: {h.hex()}")
            if (i + 1) % 25 == 0 or (i + 1) == n:
                print(f"    {i+1}/{n} confirmadas ({time.time()-t0:.0f}s)")
        self._hashes.clear()
        print(f"  ✓ {n} TXs confirmadas en {time.time()-t0:.1f}s")

    def refresh_nonce(self):
        self._nonce = self.w3.eth.get_transaction_count(self.account.address, "pending")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=100)
    args = parser.parse_args()
    N = args.users

    print(f"\n=== Setup E3c Besu — {N} usuarios Poisson (batch TX) ===\n")

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    if not w3.is_connected():
        sys.exit("ERROR: Besu no disponible en " + RPC_URL)

    dev   = w3.eth.account.from_key(DEV_KEY)
    vpm   = load_contract(w3, "VertiportManagement")
    evm   = load_contract(w3, "EVTOLManagement")
    uv    = load_contract(w3, "UserVerification")
    batch = BatchSender(w3, dev)

    run_id  = uuid.uuid4().hex[:6]
    VP1_ID  = f"e3c-vp1-{run_id}"
    VP2_ID  = f"e3c-vp2-{run_id}"
    N_PARK  = N * 2        # 200 parkings por vertiport (suficiente para N eVTOLs + margen)
    N_AIR   = N // 2       # 50 airstrips (límite de operaciones simultáneas)

    print(f"  Vertiports: {VP1_ID}, {VP2_ID}")

    # Buscar primer bloque libre de eVTOLs a partir de EVTOL_START
    evtol_start = EVTOL_START
    while True:
        try:
            evm.functions.getEVTOL(evtol_start).call()
            evtol_start += N  # ocupado: saltar al siguiente bloque
        except Exception:
            break
    print(f"  eVTOLs: {evtol_start}–{evtol_start + N - 1}\n")

    # ── 1. Vertiports ──────────────────────────────────────────────────────────
    print(f"[1/5] Registrando vertiports (airstrips={N_AIR}, parkings={N_PARK})...")
    for vpid in [VP1_ID, VP2_ID]:
        sig = get_attestation("/api/attest/vertiport/", {"vertiport_id": vpid})
        batch.send(vpm.functions.registerVertiport(vpid, N_AIR, N_PARK, b"e3c-vp-cred", sig))
    batch.wait_all("2 vertiports")
    print(f"  ✓ {VP1_ID}, {VP2_ID}")

    # ── 2. eVTOLs (attestations primero, luego batch TX) ──────────────────────
    print(f"\n[2/5] Obteniendo {N} attestations eVTOL de Django...")
    sigs_evtol = []
    for i in range(N):
        sig = get_attestation("/api/attest/evtol/", {"evtol_id": evtol_start + i})
        sigs_evtol.append(sig)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{N} attestations")

    print(f"\n  Enviando {N} eVTOLs en batch...")
    batch.refresh_nonce()
    for i in range(N):
        batch.send(evm.functions.registerEVTOL(
            evtol_start + i, VP1_ID, b"e3c-evtol-cred", sigs_evtol[i]
        ))
    batch.wait_all(f"{N} eVTOLs")
    print(f"  ✓ eVTOLs {evtol_start}–{evtol_start + N - 1} en {VP1_ID}")

    # ── 3. Pre-ocupar mitad de parkings en VP1 ────────────────────────────────
    half = N // 2
    print(f"\n[3/5] Pre-ocupando {half} parkings en VP1...")
    batch.refresh_nonce()
    batch.send(vpm.functions.updateVertiportState(VP1_ID, b"", 0, -half))
    batch.wait_all("updateVertiport VP1")
    print(f"  ✓ VP1: {N_PARK - half}/{N_PARK} parkings libres")
    print(f"  ✓ VP2: {N_PARK}/{N_PARK} parkings libres")

    # ── 4. Generar cuentas + attestations Django ───────────────────────────────
    print(f"\n[4/5] Generando {N} cuentas y obteniendo attestations rider...")
    accounts   = []
    sigs_rider = []
    for i in range(N):
        acct = w3.eth.account.create()
        sig  = get_attestation("/api/attest/user/", {"rider": acct.address, "can_ride": True})
        accounts.append({
            "address":     acct.address,
            "private_key": acct.key.hex(),
            "evtol_id":    evtol_start + i,
        })
        sigs_rider.append(sig)
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{N} cuentas generadas")

    # Fondear en batch
    print(f"\n  Fondeando {N} cuentas (0.5 ETH c/u) en batch...")
    batch.refresh_nonce()
    for acct in accounts:
        batch.send_eth(acct["address"], 0.5)
    batch.wait_all(f"fondear {N} cuentas")

    # setRiderPermission en batch
    print(f"\n[5/5] Autorizando {N} riders en batch...")
    batch.refresh_nonce()
    for i, acct in enumerate(accounts):
        batch.send(uv.functions.setRiderPermission(acct["address"], True, sigs_rider[i]))
    batch.wait_all(f"setRiderPermission {N} riders")

    # ── Guardar ───────────────────────────────────────────────────────────────
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({
        "vp1":               VP1_ID,
        "vp2":               VP2_ID,
        "n_users":           N,
        "n_parkings_per_vp": N_PARK,
        "n_airstrips":       N_AIR,
        "evtol_start":       evtol_start,
        "accounts":          accounts,
    }, indent=2))

    print(f"\n  ✓ {OUT_FILE}")
    print(f"\n=== Setup E3c completado ({N} eVTOLs, {N} riders). ===")
    print(f"    Ejecuta: locust -f load_tests/03c_reservas_besu_poisson.py ...")


if __name__ == "__main__":
    main()
