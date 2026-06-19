#!/usr/bin/env python3
"""
Emite una credencial de cualquier tipo desde el issuer a un holder específico.

Uso:
  python connect_and_issue.py --holder <URL> --schema-name <NAME> \
      --schema-version <VER> --attributes '<JSON>'

Ejemplos:
  python connect_and_issue.py \
      --holder http://localhost:8041 \
      --schema-name evtol_credential --schema-version 3.0 \
      --attributes '{"id_puerto":"p1","state":"ACTIVE","version":"v1","name":"EVTOL-1","can_fly":"true"}'

  python connect_and_issue.py \
      --holder http://localhost:8061 \
      --schema-name vertiport_credential --schema-version 4.0 \
      --attributes '{"id_vertiport":"vp1","name":"Vertiport Norte","location":"Lima","capacity":"10","state":"ACTIVE"}'

Protocolos: RFC 0023 (DID Exchange / OOB), RFC 0453 (Issue Credential 2.0)
"""
import argparse, requests, time, json, sys

ISSUER_ADMIN  = "http://localhost:8031"
POLL_INTERVAL = 2
POLL_TIMEOUT  = 60


def pretty(o):
    print(json.dumps(o, indent=2, ensure_ascii=False))


def post(url, payload=None):
    r = requests.post(url, json=payload, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def get(url):
    r = requests.get(url, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def wait_for_connection_active(admin_url, conn_id):
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        sc, body = get(f"{admin_url}/connections/{conn_id}")
        if isinstance(body, dict):
            state = body.get("state") or body.get("connection", {}).get("state")
            print(f"  [wait] conexión {conn_id[:8]}... estado={state}")
            if state == "active":
                return True
        time.sleep(POLL_INTERVAL)
    return False


def get_or_create_schema(schema_name, schema_version, attr_names):
    sc, existing = get(f"{ISSUER_ADMIN}/schemas/created?schema_name={schema_name}&schema_version={schema_version}")
    if isinstance(existing, dict) and existing.get("schema_ids"):
        schema_id = existing["schema_ids"][0]
        print(f"  Schema ya existe: {schema_id}")
        return schema_id
    sc, resp = post(f"{ISSUER_ADMIN}/schemas", {
        "schema_name": schema_name,
        "schema_version": schema_version,
        "attributes": attr_names,
    })
    if sc not in (200, 201):
        print(f"  Error creando schema: {sc} {resp}")
        sys.exit(1)
    schema_id = resp.get("schema_id") or resp.get("sent", {}).get("schema_id")
    print(f"  Schema creado: {schema_id}")
    time.sleep(2)  # propagación entre nodos Indy
    return schema_id


def get_or_create_cred_def(schema_id):
    sc, existing = get(f"{ISSUER_ADMIN}/credential-definitions/created?schema_id={schema_id}")
    if isinstance(existing, dict) and existing.get("credential_definition_ids"):
        cred_def_id = existing["credential_definition_ids"][0]
        print(f"  Cred def ya existe: {cred_def_id}")
        return cred_def_id
    sc, resp = post(f"{ISSUER_ADMIN}/credential-definitions", {
        "schema_id": schema_id,
        "support_revocation": False,
        "tag": "default",
    })
    if sc not in (200, 201):
        print(f"  Error creando cred def: {sc} {resp}")
        sys.exit(1)
    cred_def_id = resp.get("credential_definition_id") or resp.get("sent", {}).get("credential_definition_id")
    print(f"  Cred def creada: {cred_def_id}")
    return cred_def_id


def main():
    parser = argparse.ArgumentParser(description="Emite una credencial issuer → holder")
    parser.add_argument("--holder",         required=True, help="URL admin del holder (ej. http://localhost:8051)")
    parser.add_argument("--schema-name",    required=True, help="Nombre del schema (ej. evtol_credential)")
    parser.add_argument("--schema-version", required=True, help="Versión del schema (ej. 3.0)")
    parser.add_argument("--attributes",     required=True, help='JSON con los atributos (ej. \'{"name":"X"}\')')
    args = parser.parse_args()

    holder_admin  = args.holder.rstrip("/")
    schema_name   = args.schema_name
    schema_version = args.schema_version
    attributes    = json.loads(args.attributes)
    attr_names    = list(attributes.keys())

    print(f"\n{'='*55}")
    print(f"  Issuer : {ISSUER_ADMIN}")
    print(f"  Holder : {holder_admin}")
    print(f"  Schema : {schema_name}:{schema_version}")
    print(f"  Attrs  : {attr_names}")
    print(f"{'='*55}\n")

    # ── 1. Invitación OOB (RFC 0023) ─────────────────────────────
    print("1) Crear invitación OOB")
    sc, inv = post(f"{ISSUER_ADMIN}/out-of-band/create-invitation", {
        "handshake_protocols": ["https://didcomm.org/didexchange/1.0"]
    })
    if sc != 200:
        print(f"  Error: {sc} {inv}"); sys.exit(1)
    invi_msg_id = inv["invi_msg_id"]
    print(f"  invi_msg_id={invi_msg_id[:8]}...")

    # ── 2. Holder recibe la invitación ───────────────────────────
    print("2) Holder recibe la invitación")
    sc, rec = post(f"{holder_admin}/out-of-band/receive-invitation", inv["invitation"])
    if sc not in (200, 201):
        print(f"  Error: {sc} {rec}"); sys.exit(1)

    # ── 3. Esperar conexión activa ───────────────────────────────
    print("3) Esperando conexión activa...")
    issuer_conn_id = None
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        sc, conns = get(f"{ISSUER_ADMIN}/connections?invitation_msg_id={invi_msg_id}")
        results = conns.get("results", []) if isinstance(conns, dict) else []
        if results:
            issuer_conn_id = results[0]["connection_id"]
            break
        time.sleep(POLL_INTERVAL)
    if not issuer_conn_id:
        print("  No se encontró conexión en el issuer."); sys.exit(1)

    if not wait_for_connection_active(ISSUER_ADMIN, issuer_conn_id):
        print("  Timeout esperando estado active."); sys.exit(1)
    print(f"  Conexión activa ✅  conn_id={issuer_conn_id[:8]}...")

    # ── 4. Schema ────────────────────────────────────────────────
    print(f"4) Schema {schema_name}:{schema_version}")
    schema_id = get_or_create_schema(schema_name, schema_version, attr_names)

    # ── 5. Credential definition ─────────────────────────────────
    print("5) Credential definition")
    cred_def_id = get_or_create_cred_def(schema_id)

    # ── 6. Oferta de credencial (RFC 0453) ───────────────────────
    print("6) Enviando oferta de credencial (RFC 0453 — v2.0)")
    attr_list = [{"name": k, "value": str(v)} for k, v in attributes.items()]
    offer_payload = {
        "connection_id": issuer_conn_id,
        "credential_preview": {
            "@type": "https://didcomm.org/issue-credential/2.0/credential-preview",
            "attributes": attr_list,
        },
        "filter": {"indy": {"cred_def_id": cred_def_id}},
        "auto_issue": True,
        "auto_remove": False,
    }
    sc, resp = post(f"{ISSUER_ADMIN}/issue-credential-2.0/send-offer", offer_payload)
    if sc not in (200, 201):
        print(f"  Error enviando oferta: {sc} {resp}"); sys.exit(1)
    record = resp.get("cred_ex_record", resp)
    print(f"  Estado: {record.get('state')}  cred_ex_id={record.get('cred_ex_id','?')[:8]}...")

    # ── 7. Verificar credencial en wallet del holder ─────────────
    print("7) Esperando credencial en wallet del holder...")
    start = time.time()
    stored = None
    while time.time() - start < POLL_TIMEOUT:
        sc, creds = get(f"{holder_admin}/credentials")
        if isinstance(creds, dict) and creds.get("results"):
            # buscar la que coincide con el cred_def_id actual
            match = [c for c in creds["results"] if c.get("cred_def_id") == cred_def_id]
            if match:
                stored = match[0]
                break
        time.sleep(2)

    if stored:
        print("\n✅ Credencial almacenada en el holder:")
        pretty(stored)
    else:
        print("\n❌ No se encontró la credencial en el tiempo esperado.")
        sc, recs = get(f"{holder_admin}/issue-credential-2.0/records")
        print("Registros de issue-credential-2.0 en holder:")
        pretty(recs)
        sys.exit(1)


if __name__ == "__main__":
    main()
