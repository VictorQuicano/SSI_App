#!/usr/bin/env python3
"""Ejecutor de B7/B8 para credenciales AnonCreds revocables del caso B."""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import run_case_b as base

REVOCABLE_CRED_DEF = "5rtvexuq6mGGkvikxen2qK:3:CL:10:case-b-revocable"
SCHEMA_ID = "5rtvexuq6mGGkvikxen2qK:2:user_credential:2.0"


def credential(role: str) -> dict:
    for item in base.holder_credentials():
        attrs = item.get("attrs", {})
        if item.get("cred_def_id") == REVOCABLE_CRED_DEF and attrs.get("apellidos") == role:
            return item
    raise RuntimeError(f"No se encontró credencial revocable con apellidos={role!r}.")


def one(case: str, run: int, connection_id: str, cred: dict) -> dict:
    now = int(time.time())
    row = {
        "case": case, "run": run, "credential_referent": cred["referent"],
        "rev_reg_id": cred.get("rev_reg_id"), "cred_rev_id": cred.get("cred_rev_id"),
        "non_revoked_to": now, "status": "error", "cryptographic_verification": None,
        "generation_ms": None, "verification_ms": None, "presentation_bytes": None,
        "error": None,
    }
    before = base.docker_snapshots()
    row.update({f"holder_before_{k}": v for k, v in before["acapy-case-b-holder"].items()})
    row.update({f"verifier_before_{k}": v for k, v in before["acapy-case-b-issuer"].items()})
    try:
        proof = {
            "name": f"case-b-{case.lower()}-{run:02d}", "version": "1.0",
            "requested_attributes": {
                "attr_can_ride": {
                    "name": "can_ride",
                    "restrictions": [{"cred_def_id": REVOCABLE_CRED_DEF}],
                    "non_revoked": {"to": now},
                }
            },
            "requested_predicates": {}, "non_revoked": {"to": now},
        }
        verifier, _ = base.post(base.ISSUER, "/present-proof-2.0/send-request", {
            "connection_id": connection_id, "presentation_request": {"indy": proof},
            "auto_verify": False, "auto_remove": False,
        })
        holder = base.wait_for_holder_thread(str(verifier["thread_id"]))
        holder_id = holder["pres_ex_id"]
        candidates, _ = base.get(base.HOLDER, f"/present-proof-2.0/records/{holder_id}/credentials")
        choices = [x for x in candidates if x.get("cred_info", {}).get("referent") == cred["referent"]]
        if not choices:
            row["status"] = "rejected_no_nonrevocation_candidate"
            row["cryptographic_verification"] = False
            return row
        payload = {"indy": {"requested_attributes": {
            "attr_can_ride": {"cred_id": cred["referent"], "revealed": True}
        }, "requested_predicates": {}, "self_attested_attributes": {}}, "auto_remove": False}
        started = time.perf_counter_ns()
        try:
            base.post(base.HOLDER, f"/present-proof-2.0/records/{holder_id}/send-presentation", payload)
        except Exception as exc:
            row["generation_ms"] = (time.perf_counter_ns() - started) / 1_000_000
            row["status"] = "rejected_during_nonrevocation_generation"
            row["cryptographic_verification"] = False
            row["error"] = str(exc)
            return row
        row["generation_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        verifier = base.wait_for_record(base.ISSUER, verifier["pres_ex_id"], {"presentation-received", "done"})
        pres = verifier.get("by_format", {}).get("pres", {}).get("indy", {})
        row["presentation_bytes"] = len(json.dumps(pres, separators=(",", ":")).encode())
        started = time.perf_counter_ns()
        verified, _ = base.post(base.ISSUER, f"/present-proof-2.0/records/{verifier['pres_ex_id']}/verify-presentation", {})
        row["verification_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        row["cryptographic_verification"] = verified.get("verified") == "true"
        row["status"] = "completed" if row["cryptographic_verification"] else "rejected_by_nonrevocation_verifier"
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        after = base.docker_snapshots()
        row.update({f"holder_after_{k}": v for k, v in after["acapy-case-b-holder"].items()})
        row.update({f"verifier_after_{k}": v for k, v in after["acapy-case-b-issuer"].items()})
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["B7", "B8"], required=True)
    parser.add_argument("--runs", type=int, default=30)
    parser.add_argument("--role", choices=["vigente", "revocar"], required=True)
    args = parser.parse_args()
    conn = base.active_issuer_connection()
    cred = credential(args.role)
    rows = []
    for run in range(1, args.runs + 1):
        row = one(args.case, run, conn, cred)
        rows.append(row)
        print(f"{args.case}-{run:02d}: {row['status']}", flush=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = Path(__file__).resolve().parent / "results" / f"{stamp}_{args.case.lower()}"
    target.mkdir(parents=True)
    (target / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
    with (target / "results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sorted({k for row in rows for k in row}))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"output_dir": str(target), "rows": len(rows)}, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
