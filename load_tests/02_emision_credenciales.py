"""
Escenario 2 — Throughput de emisión de credenciales SSI (holder multitenant)

Qué mide:
  Cuántas credenciales por segundo puede emitir el issuer cuando cada usuario
  tiene su propio sub-wallet independiente en el agente holder multitenant.
  El cuello de botella medido es el issuer (firma CL + escritura en Indy),
  no el holder — cada holder opera en paralelo sin serialización.

Setup (on_start):
  Cada usuario virtual registra una cuenta nueva en Django, lo que crea
  un sub-wallet propio en acapy-holder con su JWT. Luego hace login.
  Este setup ocurre una sola vez por usuario virtual.

Tarea repetida (@task):
  POST /api/credentials/issue/ con el JWT del sub-wallet propio.
  Se repite mientras el test esté activo. Mide el throughput sostenido.

Cómo ejecutar:
  locust -f load_tests/02_emision_credenciales.py --host=http://localhost:8000 \\
         --users 5 --spawn-rate 1 --run-time 180s --headless \\
         --html load_tests/resultados/emision_5u.html

  locust -f load_tests/02_emision_credenciales.py --host=http://localhost:8000 \\
         --users 10 --spawn-rate 1 --run-time 240s --headless \\
         --html load_tests/resultados/emision_10u.html
"""

import uuid
from locust import HttpUser, task, constant


def unique_username() -> str:
    return f"e2u{uuid.uuid4().hex[:10]}"


class EmisionCredencial(HttpUser):
    wait_time = constant(0)  # máximo throughput — sin pausa entre emisiones

    def on_start(self):
        self.ready = False
        username = unique_username()
        password = "testpass123"

        reg = self.client.post(
            "/api/user/",
            json={
                "username": username,
                "email": f"{username}@test.com",
                "password": password,
                "password_confirm": password,
                "first_name": "E2",
                "last_name": "User",
            },
            name="[setup] POST /api/user/",
        )
        if reg.status_code not in (200, 201):
            return

        login = self.client.post(
            "/api/auth/login/",
            json={"username": username, "password": password},
            name="[setup] POST /api/auth/login/",
        )
        self.ready = login.status_code == 200

    @task
    def emitir_credencial(self):
        if not self.ready:
            return
        self.client.post(
            "/api/credentials/issue/",
            json={
                "nombres": "Test",
                "apellidos": "Emision",
                "fecha_nacimiento": "1990-01-01",
            },
            name="POST /api/credentials/issue/",
        )
