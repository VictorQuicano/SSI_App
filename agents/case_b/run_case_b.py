#!/usr/bin/env python3
"""Ejecutor reproducible del Experimento B: AnonCreds CL/ZK off-chain.

El programa mide el flujo DIDComm completo con ACA-Py 1.2.0 en el entorno
aislado ``case_b``. Usa solamente el esquema actual ``user_credential:2.0``.

Ejemplos:
  python3 run_case_b.py --runs 3                 # comprobación inicial
  python3 run_case_b.py --runs 30                # protocolo del paper
  python3 run_case_b.py --runs 30 --cases B1,B2,B3,B5,B6

Los resultados se escriben en results/<marca-de-tiempo>/{metadata,results}.json
y en results/<marca-de-tiempo>/results.csv. No se sobrescriben ejecuciones.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ISSUER = "http://localhost:8131"
HOLDER = "http://localhost:8141"
SCHEMA_NAME = "user_credential"
SCHEMA_VERSION = "2.0"
SCHEMA_ATTRIBUTES = ["nombres", "apellidos", "fecha_nacimiento", "can_ride"]
POLL_SECONDS = 0.20
POLL_TIMEOUT_SECONDS = 45


class ApiError(RuntimeError):
    """Error devuelto por un Admin API de ACA-Py."""


def request(base: str, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[dict[str, Any] | list[Any], float]:
    """Hace una petición JSON y devuelve respuesta más tiempo de la petición."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(
        f"{base}{path}", data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    started = time.perf_counter_ns()
    try:
        with urlopen(req, timeout=60) as response:
            raw = response.read()
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            return json.loads(raw.decode("utf-8")) if raw else {}, elapsed_ms
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise ApiError(f"{method} {path}: HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ApiError(f"{method} {path}: {exc}") from exc


def get(base: str, path: str) -> tuple[dict[str, Any] | list[Any], float]:
    return request(base, "GET", path)


def post(base: str, path: str, body: dict[str, Any]) -> tuple[dict[str, Any] | list[Any], float]:
    return request(base, "POST", path, body)


def docker_snapshots() -> dict[str, dict[str, str | None]]:
    """Toma CPU/memoria de ambos agentes en una única muestra de Docker."""
    command = [
        "docker", "stats", "--no-stream", "--format",
        "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}",
        "acapy-case-b-holder", "acapy-case-b-issuer",
    ]
    empty = {"cpu": None, "memory": None, "memory_pct": None}
    try:
        lines = subprocess.run(command, check=True, capture_output=True, text=True, timeout=15).stdout.splitlines()
        snapshots: dict[str, dict[str, str | None]] = {}
        for line in lines:
            name, cpu, memory, memory_pct = line.split("|", 3)
            snapshots[name] = {"cpu": cpu, "memory": memory, "memory_pct": memory_pct}
        return {
            "acapy-case-b-holder": snapshots.get("acapy-case-b-holder", empty),
            "acapy-case-b-issuer": snapshots.get("acapy-case-b-issuer", empty),
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return {"acapy-case-b-holder": empty, "acapy-case-b-issuer": empty}


def wait_for_record(base: str, pres_ex_id: str, wanted_states: set[str]) -> dict[str, Any]:
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        record, _ = get(base, f"/present-proof-2.0/records/{pres_ex_id}")
        state = str(record.get("state", ""))
        if state in wanted_states:
            return record
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"Tiempo agotado esperando {wanted_states} para {pres_ex_id}")


def wait_for_holder_thread(thread_id: str) -> dict[str, Any]:
    encoded = urlencode({"thread_id": thread_id})
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        records, _ = get(HOLDER, f"/present-proof-2.0/records?{encoded}")
        if isinstance(records, dict) and records.get("results"):
            return records["results"][0]
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"El holder no recibió el hilo {thread_id}")


def exact_schema_id() -> str:
    data, _ = get(ISSUER, "/schemas/created?" + urlencode({
        "schema_name": SCHEMA_NAME, "schema_version": SCHEMA_VERSION,
    }))
    ids = data.get("schema_ids", []) if isinstance(data, dict) else []
    if not ids:
        raise RuntimeError("No existe el schema actual user_credential:2.0 en el issuer aislado.")
    return ids[-1]


def exact_cred_def_id(schema_id: str) -> str:
    data, _ = get(ISSUER, "/credential-definitions/created?" + urlencode({"schema_id": schema_id}))
    ids = data.get("credential_definition_ids", []) if isinstance(data, dict) else []
    if not ids:
        raise RuntimeError(f"No existe una credential definition para {schema_id}.")
    return ids[-1]


def active_issuer_connection() -> str:
    data, _ = get(ISSUER, "/connections")
    for connection in data.get("results", []):
        if connection.get("state") == "active" and connection.get("their_label") == "Case B Holder":
            return str(connection["connection_id"])
    raise RuntimeError("No hay conexión activa entre Case B Issuer y Case B Holder.")


def holder_credentials() -> list[dict[str, Any]]:
    data, _ = get(HOLDER, "/credentials")
    return data.get("results", []) if isinstance(data, dict) else []


def find_credential(cred_def_id: str, can_ride: str) -> dict[str, Any] | None:
    for credential in holder_credentials():
        if credential.get("cred_def_id") == cred_def_id and credential.get("attrs", {}).get("can_ride") == can_ride:
            return credential
    return None


def issue_if_missing(connection_id: str, cred_def_id: str, can_ride: str) -> dict[str, Any]:
    existing = find_credential(cred_def_id, can_ride)
    if existing:
        return existing
    attributes = [
        {"name": "nombres", "value": "Usuario"},
        {"name": "apellidos", "value": "Prueba"},
        {"name": "fecha_nacimiento", "value": "1990-01-01"},
        {"name": "can_ride", "value": can_ride},
    ]
    payload = {
        "connection_id": connection_id,
        "credential_preview": {
            "@type": "https://didcomm.org/issue-credential/2.0/credential-preview",
            "attributes": attributes,
        },
        "filter": {"indy": {"cred_def_id": cred_def_id}},
        "auto_issue": True,
        "auto_remove": False,
    }
    post(ISSUER, "/issue-credential-2.0/send-offer", payload)
    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        existing = find_credential(cred_def_id, can_ride)
        if existing:
            return existing
        time.sleep(POLL_SECONDS)
    raise TimeoutError(f"La credencial can_ride={can_ride} no llegó al holder.")


def proof_request(case_id: str, run: int, restriction: dict[str, str]) -> dict[str, Any]:
    return {
        "name": f"case-b-{case_id.lower()}-{run:02d}",
        "version": "1.0",
        "requested_attributes": {
            "attr_can_ride": {"name": "can_ride", "restrictions": [restriction]},
        },
        "requested_predicates": {},
    }


def lookup_timings(schema_id: str, cred_def_id: str) -> tuple[float | None, float | None]:
    # Se mide el endpoint del agente que resuelve el objeto. En la configuración
    # actual no existe registro de revocación, por lo que esa métrica se deja nula.
    try:
        _, schema_ms = get(ISSUER, "/schemas/" + schema_id)
    except ApiError:
        schema_ms = None
    try:
        _, cred_def_ms = get(ISSUER, "/credential-definitions/" + cred_def_id)
    except ApiError:
        cred_def_ms = None
    return schema_ms, cred_def_ms


def execute_presentation(
    case_id: str, run: int, issuer_connection_id: str, schema_id: str,
    expected_cred_def_id: str, credential: dict[str, Any] | None,
    restriction: dict[str, str], policy_should_allow: bool | None,
) -> dict[str, Any]:
    """Ejecuta una repetición o registra el rechazo por no haber credencial candidata."""
    row: dict[str, Any] = {
        "case": case_id, "run": run, "schema_id": schema_id,
        "expected_cred_def_id": expected_cred_def_id,
        "requested_restriction": json.dumps(restriction, sort_keys=True),
        "status": "error", "cryptographic_verification": None,
        "policy_authorized": None, "error": None,
        "generation_ms": None, "verification_ms": None, "presentation_bytes": None,
        "revealed_attribute_count": 0, "predicate_count": 0,
        "schema_lookup_ms": None, "cred_def_lookup_ms": None, "revocation_lookup_ms": None,
    }
    schema_ms, cred_def_ms = lookup_timings(schema_id, expected_cred_def_id)
    row["schema_lookup_ms"], row["cred_def_lookup_ms"] = schema_ms, cred_def_ms
    before = docker_snapshots()
    row.update({f"holder_before_{key}": value for key, value in before["acapy-case-b-holder"].items()})
    row.update({f"verifier_before_{key}": value for key, value in before["acapy-case-b-issuer"].items()})
    try:
        request_payload = {
            "connection_id": issuer_connection_id,
            "presentation_request": {"indy": proof_request(case_id, run, restriction)},
            "auto_verify": False,
            "auto_remove": False,
        }
        verifier_record, _ = post(ISSUER, "/present-proof-2.0/send-request", request_payload)
        holder_record = wait_for_holder_thread(str(verifier_record["thread_id"]))
        holder_id = str(holder_record["pres_ex_id"])
        candidates, _ = get(HOLDER, f"/present-proof-2.0/records/{holder_id}/credentials")
        candidates = candidates if isinstance(candidates, list) else []
        wanted_referent = credential.get("referent") if credential else None
        matching = [item for item in candidates if item.get("cred_info", {}).get("referent") == wanted_referent]
        if not matching:
            row["status"] = "rejected_no_matching_credential"
            row["cryptographic_verification"] = False
            row["policy_authorized"] = False
            row["error"] = "El holder no posee una credencial que satisfaga la restricción de la solicitud."
            return row
        presentation_payload = {
            "indy": {
                "requested_attributes": {
                    "attr_can_ride": {"cred_id": wanted_referent, "revealed": True},
                },
                "requested_predicates": {},
                "self_attested_attributes": {},
            },
            "auto_remove": False,
        }
        started = time.perf_counter_ns()
        post(HOLDER, f"/present-proof-2.0/records/{holder_id}/send-presentation", presentation_payload)
        row["generation_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        verifier_record = wait_for_record(ISSUER, str(verifier_record["pres_ex_id"]), {"presentation-received", "done"})
        presentation = verifier_record.get("by_format", {}).get("pres", {}).get("indy", {})
        row["presentation_bytes"] = len(json.dumps(presentation, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        revealed = presentation.get("requested_proof", {}).get("revealed_attrs", {})
        row["revealed_attribute_count"] = len(revealed)
        row["predicate_count"] = len(presentation.get("requested_proof", {}).get("predicates", {}))
        started = time.perf_counter_ns()
        verified_record, _ = post(ISSUER, f"/present-proof-2.0/records/{verifier_record['pres_ex_id']}/verify-presentation", {})
        row["verification_ms"] = (time.perf_counter_ns() - started) / 1_000_000
        crypto_ok = verified_record.get("verified") == "true"
        row["cryptographic_verification"] = crypto_ok
        raw_value = revealed.get("attr_can_ride", {}).get("raw")
        row["revealed_can_ride"] = raw_value
        row["policy_authorized"] = bool(crypto_ok and raw_value == "true") if policy_should_allow is not None else None
        row["status"] = "completed"
        if policy_should_allow is not None and row["policy_authorized"] != policy_should_allow:
            row["status"] = "unexpected_policy_result"
            row["error"] = f"Esperado policy_authorized={policy_should_allow}, obtenido {row['policy_authorized']}."
    except Exception as exc:  # La fila conserva el motivo para análisis de errores.
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        after = docker_snapshots()
        row.update({f"holder_after_{key}": value for key, value in after["acapy-case-b-holder"].items()})
        row.update({f"verifier_after_{key}": value for key, value in after["acapy-case-b-issuer"].items()})
    return row


def median_or_none(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return statistics.median(values) if values else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=30, help="Repeticiones independientes por caso (por defecto: 30).")
    parser.add_argument("--cases", default="B1,B2,B3,B5,B6", help="Casos a ejecutar, separados por comas.")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs debe ser al menos 1")
    requested_cases = [item.strip().upper() for item in args.cases.split(",") if item.strip()]
    supported = {"B1", "B2", "B3", "B5", "B6"}
    unknown = set(requested_cases) - supported
    if unknown:
        parser.error("Casos no automatizados en este entorno: " + ", ".join(sorted(unknown)))

    # Comprobación explícita del entorno y provisión de las dos credenciales.
    get(ISSUER, "/status")
    get(HOLDER, "/status")
    connection_id = active_issuer_connection()
    schema_id = exact_schema_id()
    cred_def_id = exact_cred_def_id(schema_id)
    true_credential = issue_if_missing(connection_id, cred_def_id, "true")
    false_credential = issue_if_missing(connection_id, cred_def_id, "false")

    configurations: dict[str, tuple[dict[str, str], dict[str, Any] | None, bool | None]] = {
        "B1": ({"cred_def_id": cred_def_id}, true_credential, True),
        "B2": ({"cred_def_id": cred_def_id}, false_credential, False),
        # B3 revela solamente can_ride; nombres, apellidos y fecha_nacimiento
        # quedan criptográficamente ocultos. El schema actual representa el
        # permiso como texto, por lo que no permite un predicado ZK booleano.
        "B3": ({"cred_def_id": cred_def_id}, true_credential, True),
        "B5": ({"cred_def_id": cred_def_id.rsplit(":", 1)[0] + ":incorrecta"}, None, False),
        "B6": ({"schema_name": "user_credential_incorrecto", "schema_version": SCHEMA_VERSION}, None, False),
    }
    rows: list[dict[str, Any]] = []
    for case_id in requested_cases:
        restriction, credential, expected_policy = configurations[case_id]
        print(f"Ejecutando {case_id}: {args.runs} repeticiones", flush=True)
        for run in range(1, args.runs + 1):
            row = execute_presentation(
                case_id, run, connection_id, schema_id, cred_def_id, credential,
                restriction, expected_policy,
            )
            rows.append(row)
            print(f"  {case_id}-{run:02d}: {row['status']}", flush=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = Path(__file__).resolve().parent / "results" / timestamp
    output_dir.mkdir(parents=True, exist_ok=False)
    metadata = {
        "executed_at_utc": timestamp,
        "runs_per_case": args.runs,
        "cases": requested_cases,
        "issuer_admin": ISSUER,
        "holder_admin": HOLDER,
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "schema_attributes": SCHEMA_ATTRIBUTES,
        "schema_id": schema_id,
        "cred_def_id": cred_def_id,
        "notes": [
            "B1 y B3 revelan can_ride y mantienen ocultos los otros tres atributos.",
            "El atributo can_ride del schema actual es texto; este experimento no afirma un predicado ZK booleano sin revelación.",
            "La credential definition actual no es revocable. B7 y B8 requieren un entorno revocable y se ejecutarán separadamente.",
            "B4 requiere inyectar una prueba manipulada antes de la verificación; ACA-Py Admin API construye y entrega la presentación de forma atómica, por lo que se implementará con un verificador AnonCreds de bajo nivel separado.",
        ],
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (output_dir / "results.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    fieldnames = sorted({key for row in rows for key in row})
    with (output_dir / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        case_id: {
            "count": len([row for row in rows if row["case"] == case_id]),
            "completed": len([row for row in rows if row["case"] == case_id and row["status"] == "completed"]),
            "median_generation_ms": median_or_none([row for row in rows if row["case"] == case_id], "generation_ms"),
            "median_verification_ms": median_or_none([row for row in rows if row["case"] == case_id], "verification_ms"),
        }
        for case_id in requested_cases
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(output_dir), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
