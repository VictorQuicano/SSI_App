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

### Docker Agent Setup
```bash
# Start individual agents
cd issuer && docker-compose up -d
cd holder1 && docker-compose up -d

# Orchestrated startup with genesis file download
bash start_aries.sh --url http://localhost:9000/genesis --rebuild
```

### Integration Testing
```bash
cd credential_test
bash start_test.sh                # Full automated test setup with VON Network
python connect_and_issue.py       # Manual issuer→holder credential flow test
```

## Architecture

### Request Flow
```
Django REST API (port 8000)
  └── Service Layer (services/)
        └── ACApyClient (aca_py/client.py) — HTTP to ACA-Py Admin API
              └── ACA-Py Agents (issuer port 9041, holder port 9031)
                    └── Indy Ledger (VON Network port 9000)
```

### Key Layers

**`auth_app/`** — Django app with all models and views:
- `models.py` — `User`, `Wallet` (polymorphic owner via GenericForeignKey), `Connection` (DIDComm state machine), `CredentialIssuance` (credential lifecycle), `EVTOL`
- `views/user_views.py` — `POST /api/user/` creates user + wallet
- `views/credential_views.py` — credential endpoints (currently commented out)

**`services/`** — Business logic separated from Django views:
- `wallet_service.py` — `WalletService`: creates wallets, generates keys, creates invitations
- `credential_service.py` — `CredentialService`: schema creation, credential definitions, issuance, retrieval
- `dni_service.py` — `DNIService`: high-level orchestration for DNI credential flow

**`aca_py/client.py`** — `ACApyClient`: thin HTTP wrapper around ACA-Py Admin API endpoints

**`wallet/settings.py`** — Django config + ACA-Py agent configuration dict (`ACA_PY_CONFIG`). Key env vars: `INDY_API_URL`, `ARIES_API_URL`, `ARIES_WALLET_NAME`, `ARIES_WALLET_KEY`, `ARIES_AGENT_ENDPOINT`

### Agent Containers
- **`issuer/`** — Issuer agent (ports 9040/9041), wallet `issuer_wallet`
- **`holder1/`** — Holder agent (ports 9030/9031)
- **`aries_client/`** — Multi-tenant ACA-Py setup with PostgreSQL backend

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

Additional ACA-Py vars (`ARIES_API_URL`, `ARIES_WALLET_NAME`, `ARIES_WALLET_KEY`, `ARIES_AGENT_ENDPOINT`) must also be set — see `wallet/settings.py` for the full list.

## Testing Infrastructure

`credential_test/` contains integration test scripts and Jupyter notebooks (`test_credentials.ipynb`, `multitenant_test.ipynb`) for interactive testing of credential issuance flows against a running VON Network + ACA-Py setup.
