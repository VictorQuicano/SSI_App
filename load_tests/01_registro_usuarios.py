"""
Escenario 1 — Registro masivo de usuarios en Django

Qué mide:
  - Throughput (req/s) de POST /api/user/
  - Latencia p50/p95/p99
  - Tasa de error bajo carga concurrente

Cómo ejecutar:
  cd SSI_App
  source venv/bin/activate
  locust -f load_tests/01_registro_usuarios.py --host=http://localhost:8000

Luego abrir http://localhost:8089 y configurar:
  - Number of users: 50
  - Spawn rate:      5  (usuarios/s)
  - Run time:        60s

O en modo headless (sin UI):
  locust -f load_tests/01_registro_usuarios.py --host=http://localhost:8000 \
         --users 50 --spawn-rate 5 --run-time 60s --headless \
         --html resultados/01_registro_usuarios.html

Prerequisito: Django corriendo en localhost:8000
"""

import random
import string
from locust import HttpUser, task, between


def _sufijo():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))


class UsuarioRegistro(HttpUser):
    wait_time = between(0.5, 1.5)

    @task
    def registrar_usuario(self):
        sufijo = _sufijo()
        self.client.post(
            "/api/user/",
            json={
                "username":         f"load_{sufijo}",
                "email":            f"load_{sufijo}@test.com",
                "password":         "test1234",
                "password_confirm": "test1234",
            },
            name="POST /api/user/",
        )
