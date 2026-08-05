# aca_py/client.py
import requests
from django.conf import settings

class ACApyClient:
    def __init__(self, admin_url: str, jwt: str = None):
        self.admin_url = admin_url.rstrip('/')
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if jwt:
            self.headers['Authorization'] = f'Bearer {jwt}'
    
    # ── base ──────────────────────────────────────────────────────────────  
                  
    def _make_request(self, method: str, path: str, payload: dict = None) -> dict:
        url = f"{self.admin_url}{path}"                                       
        method = method.upper()

        if method == 'GET':
            r = requests.get(url, headers=self.headers, timeout=30)
        elif method == 'POST':                                                
            r = requests.post(url, json=payload or {}, headers=self.headers, timeout=30)                                                                   
        elif method == 'DELETE':
            r = requests.delete(url, headers=self.headers, timeout=30)        
        else:   
            raise ValueError(f"Unsupported HTTP method: {method}")

        r.raise_for_status()
        return r.json()

    # ── DID / wallet ──────────────────────────────────────────────────────

    def create_did(self) -> dict:
        """Crea un DID local dentro del wallet del agente."""
        return self._make_request('POST', '/wallet/did/create', {
            "method": "sov",
            "options": {"key_type": "ed25519"}
        })

    # ── multitenant ────────────────────────────────────────────────────────

    def create_subwallet(self, wallet_name: str, wallet_key: str) -> dict:
        """Crea un sub-wallet en un agente multitenant. Devuelve wallet_id y token JWT."""
        return self._make_request('POST', '/multitenancy/wallet', {
            "wallet_name": wallet_name,
            "wallet_key": wallet_key,
            "wallet_type": "askar",
            "wallet_dispatch_type": "default",
        })
    
    # ── conexiones ────────────────────────────────────────────────────────  
   
    def create_oob_invitation(self, alias: str = None) -> dict:
        payload = {"handshake_protocols": ["https://didcomm.org/didexchange/1.0"]}
        if alias:
            payload["alias"] = alias
        return self._make_request('POST', '/out-of-band/create-invitation', payload)

    def receive_oob_invitation(self, invitation: dict) -> dict:
        return self._make_request('POST', '/out-of-band/receive-invitation', invitation)

    def get_connection(self, connection_id: str) -> dict:
        return self._make_request('GET', f"/connections/{connection_id}")

    def get_connections(self, invitation_msg_id: str = None) -> dict:
        path = '/connections'
        if invitation_msg_id:
            path += f'?invitation_msg_id={invitation_msg_id}'
        return self._make_request('GET', path)                      
                
    def send_message(self, connection_id: str, content: str) -> dict:         
        return self._make_request('POST', f"/connections/{connection_id}/send-message", {"content": content})
    
    # ── schemas ───────────────────────────────────────────────────────────
                                                                                
    def get_schemas_created(self, name: str = None, version: str = None) -> dict:
        params = []
        if name:
            params.append(f"schema_name={name}")
        if version:
            params.append(f"schema_version={version}")
        path = '/schemas/created'
        if params:
            path += '?' + '&'.join(params)
        return self._make_request('GET', path)

    def create_schema(self, name: str, version: str, attributes: list) -> dict:
        return self._make_request('POST', '/schemas', {
            "schema_name": name,
            "schema_version": version,
            "attributes": attributes,
        })

    # ── credential definitions ────────────────────────────────────────────

    def get_credential_definitions_created(self, schema_id: str = None) -> dict:
        path = '/credential-definitions/created'
        if schema_id:
            path += f'?schema_id={schema_id}'
        return self._make_request('GET', path)
                                                                            
    def create_credential_definition(self, schema_id: str, tag: str = "default", support_revocation: bool = False) -> dict:           
        return self._make_request('POST', '/credential-definitions', {
            "schema_id": schema_id,
            "tag": tag,
            "support_revocation": support_revocation,                         
        })
    
    # ── emisión de credenciales ───────────────────────────────────────────  
   
    def send_credential_offer(self, connection_id: str, cred_def_id: str, attributes: list) -> dict:
        return self._make_request('POST', '/issue-credential-2.0/send-offer', {
            "connection_id": connection_id,
            "credential_preview": {
                "@type": "https://didcomm.org/issue-credential/2.0/credential-preview",
                "attributes": attributes,
            },
            "filter": {
                "indy": {
                    "cred_def_id": cred_def_id,
                }
            },
            "auto_issue": True,
            "auto_remove": False,
        })

    def get_issue_credential_records(self, connection_id: str = None, state: str = None) -> dict:
        path = '/issue-credential-2.0/records'
        params = []
        if connection_id:
            params.append(f"connection_id={connection_id}")
        if state:
            params.append(f"state={state}")
        if params:
            path += '?' + '&'.join(params)
        return self._make_request('GET', path)
                                                                                
    def get_holder_credentials(self) -> dict:
        """Credenciales ya almacenadas en el wallet del holder."""            
        return self._make_request('GET', '/credentials')