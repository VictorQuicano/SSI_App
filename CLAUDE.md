# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SSI_App is a **Self-Sovereign Identity (SSI) credential management system** built on Django + ACA-Py (Aries Cloud Agent Python). It manages digital identity wallets and Verifiable Credentials using the Hyperledger Indy/Aries stack and a VON Network ledger.

## Common Commands

### Django Application
```bash
python manage.py migrate          # Apply database migrations
python manage.py runserver        # Start dev server on port 8000
python manage.py makemigrations   # Generate new migrations after model changes
python manage.py createsuperuser  # Create admin user for /admin/
```

### Docker Agent Setup (Architecture A — credential_test/)
```bash
# Start VON Network first (in SSI_Project/)
cd ~/Documentos/TI3/SSI_Project && ./manage start --wait

# Register issuer DID on ledger (only needed after ./manage down)
curl -X POST http://localhost:9000/register \
  -H "Content-Type: application/json" \
  -d '{"did":"Utwqp5cpEATQpGZL5WSQZJ","verkey":"GCqSzwWVsRumDY67zkBACHs92zQJpg71WKmFEHnTreUQ","alias":"issuer","role":"TRUST_ANCHOR"}'

# Start agents
cd credential_test
docker compose -f docker-compose-agents.yml up issuer user1
```

### Integration Testing
```bash
cd credential_test
python connect_and_issue.py       # issuer→holder credential flow (evtol_credential:3.0)
```

For full deployment steps see `docs/08_como_ejecutar_prueba_ssi.md`.
For the complete system flow explanation see `docs/09_flujo_completo_arranque_hasta_credencial.md`.

## Architecture

### Request Flow
```
Django REST API (port 8000)
  └── Service Layer (services/)
        └── ACApyClient (aca_py/client.py) — HTTP to ACA-Py Admin API
              └── ACA-Py Agents (issuer admin: 8031, user1 admin: 8041)
                    └── Indy Ledger (VON Network port 9000)
```

### Key Layers

**`auth_app/`** — Django app with all models and views:
- `models.py` — `User`, `Wallet` (polymorphic owner via GenericForeignKey), `Connection` (DIDComm state machine), `CredentialIssuance` (credential lifecycle), `EVTOL`
- `views/user_views.py` — `POST /api/user/` creates user + wallet
- `views/credential_views.py` — credential endpoints (currently commented out pending testing)

**`services/`** — Business logic separated from Django views:
- `wallet_service.py` — `WalletService`: creates wallets, generates keys, creates invitations
- `credential_service.py` — `CredentialService`: schema creation, credential definitions, issuance, retrieval
- `user_credential_service.py` — `UserCredentialService`: high-level orchestration for user credential flow (wallet → connection → issuance → DB record)

**`aca_py/client.py`** — `ACApyClient`: thin HTTP wrapper around ACA-Py Admin API endpoints

**`wallet/settings.py`** — Django config + `ACA_PY_AGENTS` dict mapping agent keys to admin URLs

### Agent Containers (credential_test/)
- **`acapy-issuer`** — Issuer agent (inbound: 8030, admin: 8031), seed: `issuer00000000000000000000000001`
- **`acapy-user1`** — User holder agent (inbound: 8040, admin: 8041)
- **`acapy-evtol1`** — eVTOL holder agent (inbound: 8050, admin: 8051)
- **`acapy-vertiport1`** — Vertiport holder agent (inbound: 8060, admin: 8061)
- **`acapy-vertiport2`** — Vertiport holder agent (inbound: 8070, admin: 8071)
- **`aries_client/`** — Legacy multi-tenant ACA-Py setup (not used in Architecture A)

### Wallet Polymorphism
`Wallet` uses Django's `GenericForeignKey` so any model (User, EVTOL, etc.) can own a wallet. Always use `ContentType` framework when querying wallet ownership.

## Active API Endpoints

```
POST /api/user/    → Creates user + ACA-Py wallet (user_views.create_user)
```

Credential endpoints exist in `credential_views.py` but are commented out in `wallet/urls.py`.

## Environment Setup

Copy `.env.example` to `.env` and configure:
```
BLOCKCHAIN_API_URL=http://localhost:9000/
```

Agent admin URLs are set via environment variables or default to localhost. See `wallet/settings.py` → `ACA_PY_AGENTS` for the full mapping.

## Testing Infrastructure

`credential_test/` contains:
- `connect_and_issue.py` — standalone issuer→holder flow (evtol_credential:3.0, Architecture A)
- `docker-compose-agents.yml` — defines all 5 ACA-Py agent containers
- Jupyter notebooks (`test_credentials.ipynb`, `multitenant_test.ipynb`) — legacy multitenant approach, kept for reference

Note: `connect_and_issue.py` currently uses RFC 0036 (Issue Credential 1.0) and RFC 0160 (Connection Protocol) — both deprecated. Migration to RFC 0453 / RFC 0023 is pending.
