"""
Escenario 1b — Registro único por usuario (onboarding en ráfaga)

Cada usuario virtual se registra UNA SOLA VEZ y se detiene.
Mide cuánto tiempo tarda en completarse el onboarding de N usuarios
que llegan simultáneamente — escenario más cercano a la realidad.

Métricas clave:
  - Latencia p50/p95/p99 por usuario (crece con N porque ACA-Py es serial)
  - Throughput real de creación de wallets (~1 wallet/s asyncio)
  - Tasa de error (debe ser 0% — si hay fallos es timeout real)

Cómo ejecutar (headless):
  locust -f load_tests/01b_registro_unico.py --host=http://localhost:8000 \
         --users 50 --spawn-rate 50 --run-time 180s --headless \
         --csv resultados/e1b_mt_u50
"""

import random
import string
from locust import HttpUser, task, constant
from locust.exception import StopUser


def _sufijo():
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


class UsuarioRegistroUnico(HttpUser):
    # Sin pausa entre tareas — el usuario se registra y para
    wait_time = constant(0)

    @task
    def registrar_una_vez(self):
        sufijo = _sufijo()
        self.client.post(
            "/api/user/",
            json={
                "username":         f"e1b_{sufijo}",
                "email":            f"e1b_{sufijo}@test.com",
                "password":         "test1234",
                "password_confirm": "test1234",
            },
            name="POST /api/user/",
            # Sin timeout explícito: esperamos toda la cola de ACA-Py
        )
        raise StopUser()
