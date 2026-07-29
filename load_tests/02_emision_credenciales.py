"""
Escenario 2 — Throughput de emisión de credenciales SSI

Hallazgo de diseño:
  ACA-Py procesa solicitudes de forma secuencial por agente. Con N usuarios
  concurrentes intentando establecer conexiones OOB simultáneamente, ACA-Py
  devuelve respuestas vacías para N-1 de ellas. El sistema NO admite
  emisión paralela de credenciales desde un único agente.

Qué mide este test:
  Throughput SECUENCIAL — cuántas credenciales puede emitir ACA-Py por
  minuto con 1 usuario haciendo peticiones continuas. Esto establece el
  techo teórico del sistema actual.

Prerequisito:
  Correr primero test_all.py para que el usuario de prueba tenga
  una conexión ya establecida:
    python agents/scripts/test_all.py

Cómo ejecutar:
  locust -f load_tests/02_emision_credenciales.py --host=http://localhost:8000 \
         --users 1 --spawn-rate 1 --run-time 120s --headless \
         --html load_tests/resultados/emision_credenciales_1u.html

  Luego con 3 usuarios para comparar degradación:
  locust -f load_tests/02_emision_credenciales.py --host=http://localhost:8000 \
         --users 3 --spawn-rate 1 --run-time 120s --headless \
         --html load_tests/resultados/emision_credenciales_3u.html
"""

import os
from locust import HttpUser, task, constant

# Usuario pre-creado con conexión establecida por test_all.py
# Ajustar si el nombre cambia entre corridas (ver salida de test_all.py)
TEST_USERNAME = os.getenv("LOCUST_USER", "testuser_2d51f3")
TEST_PASSWORD = "testpass123"


class EmisionCredencial(HttpUser):
    # Espera fija de 1s entre tareas — queremos medir throughput real
    wait_time = constant(1)

    def on_start(self):
        """Login con el usuario pre-establecido."""
        resp = self.client.post(
            "/api/auth/login/",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
            name="[setup] POST /api/auth/login/",
        )
        self.ready = resp.status_code == 200

    @task
    def emitir_credencial(self):
        if not self.ready:
            return
        self.client.post(
            "/api/credentials/issue/",
            json={
                "nombres": "Test",
                "apellidos": "Load",
                "fecha_nacimiento": "1990-01-01",
            },
            name="POST /api/credentials/issue/",
        )
