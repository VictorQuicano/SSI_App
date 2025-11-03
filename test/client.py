# aca_py/client.py
import requests
import settings
import json

class ACApyClient:
    def __init__(self):
        self.admin_url = settings.ACA_PY_CONFIG['admin_url']
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    # ------------------------
    # 🪪 DIDs y Wallet
    # ------------------------
    def create_local_did(self):
        """Crea un DID local dentro del wallet del agente"""
        url = f"{self.admin_url}/wallet/did/create"
        payload = {"method": "sov", "options": {"key_type": "ed25519"}}
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json().get("result", {})

    def register_did_in_ledger(self, did, verkey):
        """Registrar el DID en el ledger de Indy"""
        url = f"{self.admin_url}/ledger/register-nym"
        payload = {
            "did": did,
            "verkey": verkey,
            "alias": "AriesCLI",
            "role": "ENDORSER"
        }

        print(f"📤 Enviando request a: {url}")
        print(f"📝 Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, json=payload, headers=self.headers)
        print(f"📥 Status: {response.status_code}")
        print(f"📥 Body: {response.text}")

        if response.ok:
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"raw_response": response.text}
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "raw_response": response.text
            }

    def register_wallet(self):
        """Crea un DID local y lo registra en el ledger"""
        did_info = self.create_local_did()
        did = did_info["did"]
        verkey = did_info["verkey"]
        ledger_response = self.register_did_in_ledger(did, verkey)
        return {"did": did, "verkey": verkey, "ledger_tx": ledger_response}

    # ------------------------
    # 📜 Schemas y CredDefs
    # ------------------------
    def register_credential_schema(self, name, version, attributes):
        """Registra un nuevo schema en el ledger"""
        schema_payload = {
            "schema_name": name,
            "schema_version": version,
            "attributes": attributes
        }
        url = f"{self.admin_url}/schemas"
        response = requests.post(url, json=schema_payload, headers=self.headers)
        response.raise_for_status()
        result = response.json()
        return result.get("schema", result.get("sent", {}))

    def create_credential_definition(self, schema_id, tag="default", support_revocation=False):
        """Crea una credential definition basada en un schema existente"""
        url = f"{self.admin_url}/credential-definitions"
        payload = {
            "schema_id": schema_id,
            "tag": tag,
            "support_revocation": support_revocation
        }
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        data = response.json()
        return data.get("credential_definition_id")

    # ------------------------
    # 🔗 Conexiones
    # ------------------------
    def create_invitation(self):
        """Crea una invitación de conexión"""
        url = f"{self.admin_url}/connections/create-invitation"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    # ------------------------
    # 🎓 Emisión de Credenciales
    # ------------------------
    def send_credential_offer(self, cred_def_id, attributes):
        """
        Envía una oferta de credencial usando una cred_def existente.
        attributes: lista de dicts [{"name": "campo", "value": "valor"}]
        """
        invitation = self.create_invitation()
        connection_id = invitation["connection_id"]

        offer_payload = {
            "connection_id": connection_id,
            "cred_def_id": cred_def_id,
            "credential_preview": {
                "@type": "issue-credential/1.0/credential-preview",
                "attributes": attributes
            },
            "auto_issue": True,
            "auto_remove": True
        }

        print(f"📤 Enviando oferta de credencial: {json.dumps(offer_payload, indent=2)}")

        url = f"{self.admin_url}/issue-credential/send-offer"
        response = requests.post(url, json=offer_payload, headers=self.headers)
        print(f"📥 Status: {response.status_code}")
        print(f"📥 Body: {response.text}")

        if response.ok:
            return response.json()
        else:
            return {
                "error": f"HTTP {response.status_code}",
                "raw_response": response.text
            }
