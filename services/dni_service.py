# services/dni_service.py
from .credential_service import CredentialService
from .wallet_service import WalletService
from auth_app.models import CredentialIssuance, Connection

class DNIService:
    def __init__(self):
        self.credential_service = CredentialService()
        self.wallet_service = WalletService()
    
    def issue_dni_to_user(self, user, user_data):
        """Emitir credencial DNI a un usuario"""
        try:
            # Obtener o crear conexión para el usuario
            connection = self._get_user_connection(user)
            
            # Emitir la credencial
            credential_result = self.credential_service.issue_dni_credential(
                connection.connection_id, 
                user_data
            )
            
            # Guardar el registro de emisión
            credential_record = CredentialIssuance.objects.create(
                user=user,
                connection=connection,
                credential_exchange_id=credential_result['credential_exchange_id'],
                credential_definition_id=credential_result['credential_definition_id'],
                state=credential_result['state'],
                attributes=user_data
            )
            
            return credential_record
            
        except Exception as e:
            print(f"Error emitiendo credencial DNI: {e}")
            raise
    
    def _get_user_connection(self, user):
        """Obtener o crear conexión para el usuario"""
        try:
            # Buscar conexión existente
            wallet = user.wallet
            connections = Connection.objects.filter(wallet=wallet, state='complete')
            
            if connections.exists():
                return connections.first()
            else:
                # Crear nueva conexión
                return self.wallet_service.create_connection_for_user(user)
                
        except Exception as e:
            print(f"Error obteniendo conexión del usuario: {e}")
            raise
    
    def get_user_credentials(self, user, state=None):
        """Obtener credenciales de un usuario"""
        credentials = CredentialIssuance.objects.filter(user=user)
        
        if state:
            credentials = credentials.filter(state=state)
            
        return credentials
    
    def check_credential_status(self, credential_exchange_id):
        """Verificar estado de una credencial específica"""
        return self.credential_service.get_credential_records()