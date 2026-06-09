#!/usr/bin/env python3
"""
Script que:
- Crea conexión Issuer -> Holder
- Crea schema y cred def por Issuer (evtol_credential)
- Emite una credencial al Holder y espera que sea almacenada
"""
import requests, time, json, sys

ISSUER_ADMIN = "http://localhost:8031"
HOLDER_ADMIN = "http://localhost:8041"
POLL_INTERVAL = 2
POLL_TIMEOUT = 60

def pretty(o):
    print(json.dumps(o, indent=2, ensure_ascii=False))

def post(url, payload=None, headers=None):
    r = requests.post(url, json=payload, headers=headers, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text

def get(url, headers=None):
    r = requests.get(url, headers=headers, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text

def wait_for_connection_active(admin_url, conn_id, timeout=POLL_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        sc, body = get(f"{admin_url}/connections/{conn_id}")
        if isinstance(body, dict):
            state = body.get("state") or body.get("connection", {}).get("state")
            print(f"[wait] estado connection {conn_id} = {state}")
            if state == "active":
                return True, body
        time.sleep(POLL_INTERVAL)
    return False, None

def wait_for_cred_record(admin_url, cred_def_id, timeout=POLL_TIMEOUT):
    start = time.time()
    while time.time() - start < timeout:
        sc, body = get(f"{admin_url}/issue-credential/records")
        results = body.get("results") if isinstance(body, dict) and "results" in body else (body if isinstance(body, list) else [])
        for r in results:
            if r.get("cred_def_id") == cred_def_id:
                return r
        time.sleep(POLL_INTERVAL)
    return None

def main():
    print("1) Crear invitación desde Issuer")
    sc, inv = post(f"{ISSUER_ADMIN}/connections/create-invitation")
    if sc != 200:
        print("Error creando invitación en Issuer:", sc, inv)
        sys.exit(1)
    print("Invitation creada (Issuer):")
    pretty(inv)

    invitation = inv.get("invitation")
    if not invitation:
        print("No se obtuvo 'invitation' en la respuesta.")
        sys.exit(1)

    print("\n2) Holder recibe la invitación")
    sc, rec = post(f"{HOLDER_ADMIN}/connections/receive-invitation", payload=invitation)
    if sc not in (200,201):
        print("Error holder receive invitation:", sc, rec)
        sys.exit(1)
    pretty(rec)
    issuer_conn_id = inv.get("connection_id")
    holder_conn_id = rec.get("connection_id")
    print(f"Issuer_conn_id={issuer_conn_id}  Holder_conn_id={holder_conn_id}")

    print("\n3) Esperar a que la conexión esté activa (Issuer side)")
    ok, info = wait_for_connection_active(ISSUER_ADMIN, issuer_conn_id, timeout=60)
    if not ok:
        print("La conexión no pasó a 'active' en el tiempo esperado.")
        pretty(info)
        sys.exit(1)
    print("Conexión activa ✅")

    # Registrar schema y cred def (Issuer)
    print("\n4) Registrar schema (evtol_credential)")
    schema_id = None
    sc, existing = get(f"{ISSUER_ADMIN}/schemas/created?schema_name=evtol_credential&schema_version=3.0")
    if isinstance(existing, dict) and existing.get("schema_ids"):
        schema_id = existing["schema_ids"][0]
        print(f"Schema ya existe: {schema_id}")
    else:
        schema_payload = {
            "schema_name": "evtol_credential",
            "schema_version": "3.0",
            "attributes": ["id_puerto", "state", "version", "name", "can_fly"]
        }
        sc, schema_resp = post(f"{ISSUER_ADMIN}/schemas", payload=schema_payload)
        if sc not in (200, 201):
            print("Error creando schema:", sc, schema_resp)
            sys.exit(1)
        pretty(schema_resp)
        schema_id = (schema_resp.get("schema_id") or schema_resp.get("id") or
                     (schema_resp.get("sent") and schema_resp["sent"].get("schema_id")))
    print("schema_id =", schema_id)

    print("\n5) Crear credential definition")
    cred_def_id = None
    sc, existing_cd = get(f"{ISSUER_ADMIN}/credential-definitions/created?schema_id={schema_id}")
    if isinstance(existing_cd, dict) and existing_cd.get("credential_definition_ids"):
        cred_def_id = existing_cd["credential_definition_ids"][0]
        print(f"Cred def ya existe: {cred_def_id}")
    else:
        creddef_payload = {
            "schema_id": schema_id,
            "support_revocation": False,
            "tag": "default"
        }
        sc, creddef_resp = post(f"{ISSUER_ADMIN}/credential-definitions", payload=creddef_payload)
        if sc not in (200, 201):
            print("Error creando cred def:", sc, creddef_resp)
            sys.exit(1)
        pretty(creddef_resp)
        cred_def_id = (creddef_resp.get("credential_definition_id") or
                       (creddef_resp.get("sent") and creddef_resp["sent"].get("credential_definition_id")))
    print("cred_def_id =", cred_def_id)

    # Obtener connection id actual del issuer (buscar la conexión creada)
    sc, connections = get(f"{ISSUER_ADMIN}/connections")
    connection_list = connections.get("results", []) if isinstance(connections, dict) and "results" in connections else connections
    # Buscar la conexión que coincida con el holder por state
    conn_id = None
    for c in connection_list:
        if c.get("connection_id") == issuer_conn_id:
            conn_id = c.get("connection_id")
            break
    if not conn_id:
        conn_id = issuer_conn_id
    print("Usando connection_id:", conn_id)

    print("\n6) Enviar oferta de credencial (Issuer -> Holder)")
    credential_preview = [
        {"name":"id_puerto","value":"puerto_42"},
        {"name":"state","value":"ACTIVE"},
        {"name":"version","value":"v1"},
        {"name":"name","value":"EVTOL-Alpha"},
        {"name":"can_fly","value":"true"}
    ]
    offer_payload = {
        "connection_id": conn_id,
        "cred_def_id": cred_def_id,
        "credential_preview": {
            "@type": "issue-credential/1.0/credential-preview",
            "attributes": credential_preview
        },
        "auto_issue": True,
        "auto_remove": False
    }
    sc, resp_offer = post(f"{ISSUER_ADMIN}/issue-credential/send-offer", payload=offer_payload)
    print("offer status", sc)
    pretty(resp_offer)

    print("\n7) Esperar a que Holder reciba y guarde la credencial")
    # polling en el holder para ver cred records o cred almacenadas
    start = time.time()
    stored = None
    while time.time() - start < POLL_TIMEOUT:
        sc, creds = get(f"{HOLDER_ADMIN}/credentials")
        if isinstance(creds, dict) and "results" in creds:
            if len(creds["results"]) > 0:
                stored = creds["results"]
                break
        time.sleep(2)
    if stored:
        print("Credenciales guardadas en Holder:")
        pretty(stored)
    else:
        print("No se encontró credencial almacenada en Holder en el tiempo esperado.")
        sc, recs = get(f"{HOLDER_ADMIN}/issue-credential/records")
        print("Registros de issue-credential en Holder:")
        pretty(recs)

if __name__ == "__main__":
    main()
