# CLAUDE.md — SSI_App

## Qué hace este sub-proyecto

Django REST API + ACA-Py que gestiona wallets de identidad digital y emite/verifica
Verifiable Credentials sobre Hyperledger Indy (VON Network).

---

## Estructura del proyecto

```
SSI_App/
├── config/                        # Configuración del proyecto Django
│   ├── settings.py                #   Variables globales, BD, ACA_PY_AGENTS
│   ├── urls.py                    #   Routing raíz de la API
│   ├── wsgi.py / asgi.py
├── auth_app/                      # Única app Django del proyecto
│   ├── aca_py/
│   │   └── client.py              #   Wrapper HTTP para el Admin API de ACA-Py
│   ├── services/
│   │   ├── base_entity_service.py      #   Lógica OOB + emisión común a todas las entidades
│   │   ├── credential_service.py       #   Schema + cred_def + emisión (RFC 0453)
│   │   ├── user_credential_service.py  #   Flujo completo: usuario → credencial
│   │   ├── evtol_credential_service.py #   Flujo completo: eVTOL → credencial
│   │   ├── vertiport_credential_service.py # Flujo completo: vertiport → credencial
│   │   └── wallet_service.py           #   Crea wallets y conexiones OOB
│   ├── views/
│   │   ├── credential_views.py    #   Endpoints de credenciales de usuario
│   │   ├── user_views.py          #   POST /api/user/ y POST /api/auth/login/
│   │   ├── evtol_views.py         #   CRUD eVTOL + emisión de credencial
│   │   └── vertiport_views.py     #   CRUD Vertiport + emisión de credencial
│   ├── migrations/                #   Migraciones de BD (no editar manualmente)
│   ├── models.py                  #   User, EVTOL, Vertiport, Wallet, Connection, CredentialIssuance
│   ├── serializers.py             #   UserRegistrationSerializer, EvtolRegistrationSerializer, VertiportRegistrationSerializer
│   ├── admin.py                   #   Registra todos los modelos en el panel admin
│   └── tests.py                   #   22 tests unitarios (sin ACA-Py, con mocks)
├── agents/                        # Infraestructura ACA-Py (agentes + scripts)
│   ├── genesis/
│   │   └── genesis.txn            #   Genesis file de la VON Network local
│   ├── scripts/
│   │   ├── test_all.py            #   Prueba integral: Django user + eVTOL + vertiports
│   │   └── connect_and_issue.py   #   Emite una credencial a un agente (parametrizado)
│   ├── docker-compose.yml         #   Define los 5 contenedores ACA-Py
│   ├── start.sh                   #   Registra DID del issuer + levanta los 5 agentes
│   └── README.md
├── manage.py
├── requirements.txt
└── .env.example
```

---

## Flujo de capas

```
HTTP Request
    └── config/urls.py
          └── auth_app/views/
                └── auth_app/services/          ← lógica de negocio
                      └── auth_app/aca_py/client.py  ← HTTP al Admin API de ACA-Py
                            └── ACA-Py Agent (Docker)
                                  └── Indy Ledger (VON Network :9000)
```

---

## Comandos de uso frecuente

### Django
```bash
cd SSI_App
source venv/bin/activate
python manage.py migrate
python manage.py runserver          # API en localhost:8000

# Tests unitarios (no requieren ACA-Py ni VON Network)
python manage.py test auth_app
```

### Agentes ACA-Py
```bash
# Levanta 5 agentes y registra DID del issuer en la VON Network
bash agents/start.sh

# Bajar agentes (conserva wallets)
bash agents/start.sh --down
```

### Prueba de integración completa
```bash
# Desde SSI_App/ (requiere todos los servicios activos)
python agents/scripts/test_all.py

# Emitir un tipo de credencial específico a un agente:
python agents/scripts/connect_and_issue.py \
  --holder http://localhost:8051 \
  --schema-name evtol_credential --schema-version 3.0 \
  --attributes '{"id_puerto":"p1","state":"ACTIVE","version":"v1","name":"EVTOL-1","can_fly":"true"}'
```

---

## Endpoints activos

### Usuario
| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/api/user/` | Crea usuario + wallet ACA-Py (`agent_key` fijo: `user_1`) |
| POST | `/api/auth/login/` | Login (sesión por cookies) |
| POST | `/api/credentials/issue/` | Emite `user_credential` al usuario autenticado |
| GET  | `/api/credentials/my/` | Lista credenciales del usuario autenticado |
| GET  | `/api/credentials/<id>/status/` | Estado de una credencial |
| POST | `/webhooks/credentials/` | Webhook ACA-Py → actualiza estado en BD |

### eVTOL
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/api/evtol/` | Lista todos los eVTOLs |
| POST | `/api/evtol/` | Crea eVTOL + wallet (body: `agent_key` requerido) |
| POST | `/api/evtol/<id>/credential/` | Emite `evtol_credential` (body: `{"id_puerto": "p1"}`) |
| GET  | `/api/evtol/<id>/credentials/` | Lista credenciales del eVTOL |

### Vertiport
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET  | `/api/vertiport/` | Lista todos los vertiports |
| POST | `/api/vertiport/` | Crea Vertiport + wallet (body: `agent_key` requerido) |
| POST | `/api/vertiport/<id>/credential/` | Emite `vertiport_credential` |
| GET  | `/api/vertiport/<id>/credentials/` | Lista credenciales del vertiport |

---

## Agentes ACA-Py

| Contenedor | Rol | Inbound | Admin |
|------------|-----|---------|-------|
| `acapy-issuer` | Emisor de credenciales | 8030 | 8031 |
| `acapy-user1` | Holder usuario | 8040 | 8041 |
| `acapy-evtol1` | Holder eVTOL | 8050 | 8051 |
| `acapy-vertiport1` | Holder vertiport | 8060 | 8061 |
| `acapy-vertiport2` | Holder vertiport | 8070 | 8071 |

DID del issuer: `Utwqp5cpEATQpGZL5WSQZJ`

---

## Schemas en el ledger

| Schema | Versión | Atributos |
|--------|---------|-----------|
| `user_credential` | 2.0 | nombres, apellidos, fecha_nacimiento, can_ride |
| `evtol_credential` | 3.0 | id_puerto, state, version, name, can_fly |
| `vertiport_credential` | 4.0 | id_vertiport, name, location, capacity, state |

---

## Notas de diseño

- **`Wallet` usa GenericForeignKey**: cualquier modelo (User, EVTOL, Vertiport) puede tener wallet.
  Filtra siempre con `wallet__object_id=<pk>`, no con `user=`.
- **`BaseEntityCredentialService`**: clase base en `services/base_entity_service.py` que encapsula
  la lógica OOB (RFC 0023) + espera de conexión + emisión (RFC 0453). Las 3 subclases sólo
  definen `SCHEMA_NAME`, `SCHEMA_VERSION` y `SCHEMA_ATTRS`.
- **`agent_key`**: al crear eVTOL o Vertiport, el caller especifica qué agente ACA-Py asignar
  (p.ej. `evtol_1`, `vertiport_1`, `vertiport_2`). El valor debe existir en `settings.ACA_PY_AGENTS`.
- **Verificación on-chain mockeada**: los contratos Besu aceptan parámetros SSI pero
  devuelven `true`. El bridge real usará `web3.py`.

Para instrucciones de arranque completo: `../docs/08_como_ejecutar_prueba_ssi.md`
