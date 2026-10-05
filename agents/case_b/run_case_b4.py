#!/usr/bin/env python3
"""Ejecuta B4: verificación AnonCreds de 30 presentaciones CL manipuladas.

Lee presentaciones B1 ya recibidas por el verifier, altera ``a_prime`` en una
copia y llama ``anoncreds.Presentation.verify`` dentro del contenedor ACA-Py,
donde está instalada la misma biblioteca AnonCreds usada por el agente.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

ISSUER = "http://localhost:8131"
SCHEMA_ID = "5rtvexuq6mGGkvikxen2qK:2:user_credential:2.0"
CRED_DEF_ID = "5rtvexuq6mGGkvikxen2qK:3:CL:10:case-b"
ISSUER_DID = "5rtvexuq6mGGkvikxen2qK"


def get(path: str):
    with urlopen(ISSUER + path, timeout=45) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=30)
    args = parser.parse_args()
    records = get("/present-proof-2.0/records?" + urlencode({"limit": 500}))
    eligible = [
        record for record in records.get("results", [])
        if record.get("by_format", {}).get("pres_request", {}).get("indy", {}).get("name", "").startswith("case-b-b1-")
        and record.get("by_format", {}).get("pres", {}).get("indy")
    ]
    if len(eligible) < args.runs:
        raise RuntimeError(f"Se requieren {args.runs} presentaciones B1; ACA-Py devolvió {len(eligible)}.")
    schema = get("/schemas/" + SCHEMA_ID)["schema"]
    cred_def = get("/credential-definitions/" + CRED_DEF_ID)["credential_definition"]
    # La biblioteca anoncreds moderna usa issuerId; los objetos Indy del ledger
    # local lo infieren del identificador, por lo que se añade en la copia usada
    # exclusivamente por este harness.
    schema["issuerId"] = ISSUER_DID
    cred_def["issuerId"] = ISSUER_DID
    payload = {
        "schema": schema,
        "creddef": cred_def,
        "samples": [
            {
                "presentation": record["by_format"]["pres"]["indy"],
                "request": record["by_format"]["pres_request"]["indy"],
                "source_pres_ex_id": record["pres_ex_id"],
            }
            for record in eligible[:args.runs]
        ],
    }
    local = Path("/tmp/case_b4_inputs.json")
    local.write_text(json.dumps(payload), encoding="utf-8")
    subprocess.run(["docker", "cp", str(local), "acapy-case-b-issuer:/tmp/case_b4_inputs.json"], check=True)
    code = r'''
import copy,json,time,anoncreds
d=json.load(open("/tmp/case_b4_inputs.json")); schemas={d["schema"]["id"]:d["schema"]}; defs={d["creddef"]["id"]:d["creddef"]}; out=[]
for i,s in enumerate(d["samples"],1):
    valid=anoncreds.Presentation.load(s["presentation"])
    v0=time.perf_counter_ns(); valid_result=valid.verify(s["request"],schemas,defs); valid_ms=(time.perf_counter_ns()-v0)/1e6
    altered=copy.deepcopy(s["presentation"]); a=altered["proof"]["proofs"][0]["primary_proof"]["eq_proof"]["a_prime"]
    altered["proof"]["proofs"][0]["primary_proof"]["eq_proof"]["a_prime"]=a[:-1]+("1" if a[-1]!="1" else "2")
    tampered=anoncreds.Presentation.load(altered)
    t0=time.perf_counter_ns(); tampered_result=tampered.verify(s["request"],schemas,defs); tampered_ms=(time.perf_counter_ns()-t0)/1e6
    out.append({"case":"B4","run":i,"source_pres_ex_id":s["source_pres_ex_id"],"valid_proof_verifies":valid_result,"tampered_proof_verifies":tampered_result,"valid_verification_ms":valid_ms,"tampered_verification_ms":tampered_ms,"altered_component":"proof.proofs[0].primary_proof.eq_proof.a_prime"})
print(json.dumps(out))
'''
    completed = subprocess.run(
        ["docker", "exec", "acapy-case-b-issuer", "python", "-c", code],
        check=True, capture_output=True, text=True,
    )
    rows = json.loads(completed.stdout)
    if not all(row["valid_proof_verifies"] and not row["tampered_proof_verifies"] for row in rows):
        raise RuntimeError("B4 produjo un resultado inesperado; no se guardaron resultados como válidos.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = Path(__file__).resolve().parent / "results" / f"{stamp}_b4"
    output.mkdir(parents=True)
    (output / "results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    with (output / "results.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"output_dir": str(output), "count": len(rows)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
