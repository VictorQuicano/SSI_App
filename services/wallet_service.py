# services/wallet_service.py
from aca_py.client import ACApyClient
from auth_app.models import Wallet, Connection

class WalletService:
    def __init__(self):
        self.client = ACApyClient()
    
    def create_wallet(self, model, wallet_name):
        """Crear wallet para usuario"""
        wallet_key = self._generate_wallet_key()
        
        # Crear wallet en ACA-Py
        wallet_data = self.client.create_wallet(wallet_name, wallet_key)
        
        # Guardar en base de datos Django
        wallet = Wallet.objects.create(
            owner=model,
            wallet_id=wallet_name,
            wallet_key=wallet_key,
            public_did=wallet_data.get('result', {}).get('did')
        )
        
        return wallet
    
    def create_connection_invitation(self, wallet, alias=None):
        """Crear invitación de conexión"""
        invitation_data = self.client.create_invitation(alias)
        
        connection = Connection.objects.create(
            wallet=wallet,
            connection_id=invitation_data['connection_id'],
            their_label=alias or '',
            state='invited',
            invitation_url=invitation_data['invitation_url']
        )
        
        return connection
    
    def _generate_wallet_key(self):
        """Generar clave segura para el wallet"""
        import secrets
        import string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(32))