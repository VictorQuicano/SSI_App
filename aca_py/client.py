# aca_py/client.py
import requests
from django.conf import settings

class ACApyClient:
    def __init__(self, admin_url: str):
        self.admin_url = admin_url.rstrip('/')                                
        self.headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
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
    
    # ── conexiones ────────────────────────────────────────────────────────  
   
    def create_invitation(self, alias: str = None) -> dict:                   
        payload = {"alias": alias} if alias else {}
        return self._make_request('POST', '/connections/create-invitation', payload)
                                                                            
    def receive_invitation(self, invitation: dict) -> dict:                   
        return self._make_request('POST', '/connections/receive-invitation', invitation)                                                                   
                
    def get_connection(self, connection_id: str) -> dict:
        return self._make_request('GET', f"/connections/{connection_id}")
                                                                            
    def get_connections(self) -> dict:
        return self._make_request('GET', '/connections')                      
                
    def send_message(self, connection_id: str, content: str) -> dict:         
        return self._make_request('POST', f"/connections/{connection_id}/send-message", {"content": content})
    
    # ── schemas ───────────────────────────────────────────────────────────
                                                                                
    def get_schemas_created(self) -> dict:
        return self._make_request('GET', '/schemas/created')
                                                                            
    def create_schema(self, name: str, version: str, attributes: list) -> dict:                                                                         
        return self._make_request('POST', '/schemas', {
            "schema_name": name,                                              
            "schema_version": version,
            "attributes": attributes,
        })
    
    # ── credential definitions ────────────────────────────────────────────  
   
    def get_credential_definitions_created(self) -> dict:                     
        return self._make_request('GET', '/credential-definitions/created')
                                                                            
    def create_credential_definition(self, schema_id: str, tag: str = "default", support_revocation: bool = False) -> dict:           
        return self._make_request('POST', '/credential-definitions', {
            "schema_id": schema_id,
            "tag": tag,
            "support_revocation": support_revocation,                         
        })
    
    # ── emisión de credenciales ───────────────────────────────────────────  
   
    def send_credential_offer(self, connection_id: str, cred_def_id: str, attributes: list) -> dict:
        return self._make_request('POST', '/issue-credential/send-offer', {
            "connection_id": connection_id,                                   
            "cred_def_id": cred_def_id,
            "credential_preview": {                                           
                "@type": "issue-credential/1.0/credential-preview",           
                "attributes": attributes,                                     
            },                                                                
            "auto_issue": True,                                               
            "auto_remove": False,
        })                                                                    
   
    def get_issue_credential_records(self, connection_id: str = None, state: str = None) -> dict:
        path = '/issue-credential/records'                                    
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