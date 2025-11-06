# Prueba Issuer ↔ Holder con ACA-Py (Archivos + Script)

## Requisitos
- VON Network (Indy) corriendo en el host y accesible en http://localhost:9000/genesis
- Docker instalado en Linux (estos compose usan `network_mode: host`)
- Python 3 + requests

## Pasos
1. Poner `docker-compose-agents.yml` y `connect_and_issue.py` en una carpeta.
2. Levantar los agentes:
   ```bash
   docker compose up -d
