# aca_py/client.py
import requests
from django.conf import settings

class ACApyClient:
    def __init__(self):
        self.admin_url = settings.ACA_PY_CONFIG['admin_url']
        self.headers = {
            #'X-API-Key': settings.ACA_PY_CONFIG['api_key'],
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
    
    def create_wallet(self, wallet_name, wallet_key):
        """Crear un nuevo wallet"""
        url = f"{self.admin_url}/wallet/did/create"
        payload = {
            "method": "sov",
            "options": {
                "key_type": "ed25519"
            }
        }
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def create_invitation(self, alias=None):
        """Crear invitación de conexión"""
        url = f"{self.admin_url}/connections/create-invitation"
        payload = {"alias": alias} if alias else {}
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()
    
    def send_message(self, connection_id, content):
        """Enviar mensaje a través de una conexión"""
        url = f"{self.admin_url}/connections/{connection_id}/send-message"
        payload = {"content": content}
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()