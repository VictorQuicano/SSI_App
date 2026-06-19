# services/wallet_service.py
from auth_app.aca_py.client import ACApyClient
from auth_app.models import Wallet, Connection
from django.conf import settings

class WalletService:
    def __init__(self, agent_key: str = 'issuer'):
          admin_url = settings.ACA_PY_AGENTS[agent_key]
          self.client = ACApyClient(admin_url)                                  
          self.agent_admin_url = admin_url
    
    def create_wallet(self, owner_model, agent_key: str) -> Wallet:           
        """
        Registra en Django la asociación entre una entidad y su agente ACA-Py.
        Crea un DID en ese agente y lo guarda como public_did.                
        """                                                                   
        admin_url = settings.ACA_PY_AGENTS[agent_key]                         
        client = ACApyClient(admin_url)                                       
                
        did_data = client.create_did()                                        
        did = did_data.get('result', {}).get('did')
                                                                            
        wallet = Wallet.objects.create(                                       
            owner=owner_model,
            wallet_id=agent_key,
            agent_admin_url=admin_url,                                        
            public_did=did,
        )                                                                     
        return wallet
    
    def create_connection_invitation(self, wallet: Wallet, alias: str = None) -> Connection:
        client = ACApyClient(wallet.agent_admin_url)
        inv_data = client.create_oob_invitation(alias)
        return Connection.objects.create(
            wallet=wallet,
            connection_id=inv_data['invi_msg_id'],
            their_label=alias or '',
            state='invited',
            invitation_url=inv_data.get('invitation_url', ''),
        )