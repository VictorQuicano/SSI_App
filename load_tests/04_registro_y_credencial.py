"""
Escenario 4 — Flujo completo de onboarding (Registro + Credencial SSI)
con holder multitenant

Qué mide este test:
  Throughput y latencia del flujo completo de incorporación de un usuario:
    1. POST /api/user/         — Registro + creación de sub-wallet multitenant
    2. POST /api/credentials/issue/ — Emisión de credencial via DIDComm

  Cada usuario virtual de Locust es completamente INDEPENDIENTE:
  - Crea su propio usuario Django (username único)
  - Recibe su propio sub-wallet con JWT propio en el agente holder multitenant
  - La emisión de credencial usa su conexión DIDComm exclusiva con el issuer

  Diferencia con Escenario 2:
  - Esc. 2: un usuario compartido hace peticiones repetidas (mide throughput del issuer)
  - Esc. 4: cada usuario virtual es un usuario nuevo independiente (mide onboarding real)

Prerequisito:
  Sistema completo activo, incluyendo el agente holder multitenant:
    docker compose -f agents/docker-compose.yml up -d holder

Cómo ejecutar (recomendado: escalar gradualmente):
  locust -f load_tests/04_registro_y_credencial.py --host=http://localhost:8000 \\
         --users 5 --spawn-rate 1 --run-time 120s --headless \\
         --html load_tests/resultados/multitenant_5u.html

  locust -f load_tests/04_registro_y_credencial.py --host=http://localhost:8000 \\
         --users 10 --spawn-rate 1 --run-time 180s --headless \\
         --html load_tests/resultados/multitenant_10u.html

  locust -f load_tests/04_registro_y_credencial.py --host=http://localhost:8000 \\
         --users 20 --spawn-rate 1 --run-time 240s --headless \\
         --html load_tests/resultados/multitenant_20u.html
"""

import uuid
from locust import HttpUser, task, between


def unique_username() -> str:
    return f"u{uuid.uuid4().hex[:10]}"


class OnboardingUser(HttpUser):
    # Pausa entre tareas: simula el tiempo que tarda un usuario real
    # en revisar su credencial antes de hacer otra acción (2-5 segundos)
    wait_time = between(2, 5)

    def on_start(self):
        """
        Cada usuario virtual registra una cuenta nueva con su propio wallet.
        Si el registro falla, el usuario queda inactivo (no ejecuta tareas).
        """
        self.username = unique_username()
        self.password = "testpass123"
        self.registered = False
        self.credential_issued = False

        resp = self.client.post(
            "/api/user/",
            json={
                "username": self.username,
                "email": f"{self.username}@test.com",
                "password": self.password,
                "password_confirm": self.password,
                "first_name": "Test",
                "last_name": "User",
            },
            name="[setup] POST /api/user/ (registro + sub-wallet)",
        )
        if resp.status_code not in (200, 201):
            return

        login = self.client.post(
            "/api/auth/login/",
            json={"username": self.username, "password": self.password},
            name="[setup] POST /api/auth/login/",
        )
        self.registered = login.status_code == 200

    @task(1)
    def emitir_credencial(self):
        """
        Emite la credencial SSI para este usuario.
        Se ejecuta una sola vez (el flag evita re-emisiones en el mismo ciclo).
        """
        if not self.registered:
            return
        if self.credential_issued:
            return

        resp = self.client.post(
            "/api/credentials/issue/",
            json={
                "nombres": "Test",
                "apellidos": "Multitenant",
                "fecha_nacimiento": "1995-06-15",
            },
            name="POST /api/credentials/issue/ (DIDComm multitenant)",
        )
        if resp.status_code == 200:
            self.credential_issued = True
