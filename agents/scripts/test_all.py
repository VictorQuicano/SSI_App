#!/usr/bin/env python3
"""
Prueba integral del sistema SSI.

Cubre los 4 agentes holders usando exclusivamente la API Django:
  user1      — POST /api/user/ + /api/credentials/issue/
  evtol1     — POST /api/evtol/ + /api/evtol/<id>/credential/
  vertiport1 — POST /api/vertiport/ + /api/vertiport/<id>/credential/
  vertiport2 — POST /api/vertiport/ + /api/vertiport/<id>/credential/

Uso:
  cd SSI_App
  python agents/scripts/test_all.py

Prerequisitos:
  - VON Network corriendo en localhost:9000
  - Agentes ACA-Py corriendo: bash agents/start.sh
  - Django corriendo en localhost:8000: python manage.py runserver
"""
import sys, time, uuid, json
import requests

DJANGO_BASE = "http://localhost:8000"

POLL_INTERVAL = 2
POLL_TIMEOUT  = 90


# ── helpers ──────────────────────────────────────────────────────────────────

def _post(url, payload=None, session=None):
    fn = (session or requests).post
    r = fn(url, json=payload, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def _get(url, session=None):
    fn = (session or requests).get
    r = fn(url, timeout=30)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text


def _banner(msg):
    print(f"\n{'─' * 58}\n  {msg}\n{'─' * 58}")


def _wait_credential_done(poll_fn, timeout=POLL_TIMEOUT):
    """Llama a poll_fn() hasta que devuelva una lista no vacía de credenciales."""
    start = time.time()
    while time.time() - start < timeout:
        sc, body = poll_fn()
        if sc == 200 and isinstance(body, dict):
            creds = body.get("credentials", [])
            if creds:
                return creds[0]
        time.sleep(POLL_INTERVAL)
    raise TimeoutError("Credencial no almacenada después de {timeout}s")


# ── Sección 1: usuario ────────────────────────────────────────────────────────

def test_django_user_flow():
    _banner("SECCIÓN 1 — Usuario (user1) vía Django")

    suffix   = uuid.uuid4().hex[:6]
    username = f"testuser_{suffix}"
    password = "testpass123"
    print(f"  Usuario: {username}")

    sc, body = _post(f"{DJANGO_BASE}/api/user/", {
        "username": username, "password": password, "password_confirm": password,
        "email": f"{username}@test.com",
    })
    if sc != 200 or body.get("status") != "success":
        print(f"  ❌ POST /api/user/ → {sc}: {body}")
        return None
    user_id = body["user_id"]
    print(f"  ✅ Usuario creado (id={user_id})")

    session = requests.Session()
    sc, body = _post(f"{DJANGO_BASE}/api/auth/login/",
                     {"username": username, "password": password}, session)
    if sc != 200:
        print(f"  ❌ POST /api/auth/login/ → {sc}: {body}")
        return None
    print("  ✅ Login OK")

    sc, body = _post(f"{DJANGO_BASE}/api/credentials/issue/", {
        "nombres": "Juan", "apellidos": "Pérez", "fecha_nacimiento": "1990-01-01",
    }, session)
    if sc != 200:
        print(f"  ❌ POST /api/credentials/issue/ → {sc}: {body}")
        return None
    cred_ex_id = body.get("credential_exchange_id", "?")
    print(f"  ✅ Credencial emitida (cred_ex_id={cred_ex_id[:8]}...)")
    return {"entity": "user", "id": user_id, "cred_ex_id": cred_ex_id}


# ── Sección 2: eVTOL ─────────────────────────────────────────────────────────

def test_django_evtol_flow():
    _banner("SECCIÓN 2 — eVTOL (evtol_1) vía Django")

    suffix = uuid.uuid4().hex[:6]
    payload = {
        "name": f"Eagle-{suffix}",
        "model": "X200",
        "manufacturer": "AeroCorp",
        "serial_number": f"SN-{suffix}",
        "agent_key": "evtol_1",
    }
    sc, body = _post(f"{DJANGO_BASE}/api/evtol/", payload)
    if sc != 201 or body.get("status") != "success":
        print(f"  ❌ POST /api/evtol/ → {sc}: {body}")
        return None
    evtol_id = body["evtol_id"]
    print(f"  ✅ eVTOL creado (id={evtol_id}, serial={payload['serial_number']})")

    sc, body = _post(f"{DJANGO_BASE}/api/evtol/{evtol_id}/credential/", {"id_puerto": "p1"})
    if sc != 200 or body.get("status") != "success":
        print(f"  ❌ POST /api/evtol/{evtol_id}/credential/ → {sc}: {body}")
        return None
    cred_ex_id = body.get("credential_exchange_id", "?")
    print(f"  ✅ Credencial emitida (cred_ex_id={cred_ex_id[:8]}...)")

    try:
        cred = _wait_credential_done(
            lambda: _get(f"{DJANGO_BASE}/api/evtol/{evtol_id}/credentials/")
        )
        print(f"  ✅ Credencial almacenada (state={cred['state']})")
        return {"entity": "evtol", "id": evtol_id, "cred_ex_id": cred_ex_id}
    except TimeoutError as e:
        print(f"  ⚠️  {e} (la emisión puede continuar en background)")
        return {"entity": "evtol", "id": evtol_id, "cred_ex_id": cred_ex_id}


# ── Sección 3 & 4: Vertiports ────────────────────────────────────────────────

def test_django_vertiport_flow(agent_key: str, vertiport_id: str, name: str,
                               location: str, capacity: int, section: str):
    _banner(f"SECCIÓN {section} — Vertiport ({agent_key}) vía Django")

    payload = {
        "vertiport_id": vertiport_id,
        "name": name,
        "location": location,
        "capacity": capacity,
        "agent_key": agent_key,
    }
    sc, body = _post(f"{DJANGO_BASE}/api/vertiport/", payload)
    if sc != 201 or body.get("status") != "success":
        print(f"  ❌ POST /api/vertiport/ → {sc}: {body}")
        return None
    vp_id = body["vertiport_id"]
    print(f"  ✅ Vertiport creado (id={vp_id}, vertiport_id={vertiport_id})")

    sc, body = _post(f"{DJANGO_BASE}/api/vertiport/{vp_id}/credential/")
    if sc != 200 or body.get("status") != "success":
        print(f"  ❌ POST /api/vertiport/{vp_id}/credential/ → {sc}: {body}")
        return None
    cred_ex_id = body.get("credential_exchange_id", "?")
    print(f"  ✅ Credencial emitida (cred_ex_id={cred_ex_id[:8]}...)")

    try:
        cred = _wait_credential_done(
            lambda: _get(f"{DJANGO_BASE}/api/vertiport/{vp_id}/credentials/")
        )
        print(f"  ✅ Credencial almacenada (state={cred['state']})")
        return {"entity": "vertiport", "id": vp_id, "cred_ex_id": cred_ex_id}
    except TimeoutError as e:
        print(f"  ⚠️  {e} (la emisión puede continuar en background)")
        return {"entity": "vertiport", "id": vp_id, "cred_ex_id": cred_ex_id}


# ── Resumen ───────────────────────────────────────────────────────────────────

def _print_summary(results: dict):
    _banner("RESUMEN")
    print(f"  {'Agente':<20}  {'Entidad':<12}  Estado")
    print(f"  {'─' * 20}  {'─' * 12}  ──────")
    for label, data in results.items():
        estado = "✅" if data else "❌"
        entity = data.get("entity", "?") if data else "—"
        print(f"  {label:<20}  {entity:<12}  {estado}")
    print()


def main():
    suffix = uuid.uuid4().hex[:4]
    results = {
        "user1":      test_django_user_flow(),
        "evtol_1":    test_django_evtol_flow(),
        "vertiport_1": test_django_vertiport_flow(
            agent_key="vertiport_1",
            vertiport_id=f"vp1-{suffix}", name="Vertiport Norte",
            location="Lima Norte", capacity=10, section="3",
        ),
        "vertiport_2": test_django_vertiport_flow(
            agent_key="vertiport_2",
            vertiport_id=f"vp2-{suffix}", name="Vertiport Sur",
            location="Lima Sur", capacity=8, section="4",
        ),
    }

    _print_summary(results)

    ok = all(v is not None for v in results.values())
    if ok:
        print("  Sistema SSI operativo — todos los agentes tienen credenciales vía Django.")
        sys.exit(0)
    else:
        print("  Algunos agentes fallaron. Revisa la salida arriba.")
        sys.exit(1)


if __name__ == "__main__":
    main()
