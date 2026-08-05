# services/wallet_service.py
import uuid
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
        Registra la asociación entre una entidad y su agente ACA-Py.
        Si agent_key == 'holder', crea un sub-wallet multitenant con JWT propio.
        Para los demás agentes, crea un DID en el agente compartido.
        """
        admin_url = settings.ACA_PY_AGENTS[agent_key]

        if agent_key == 'holder':
            return self._create_multitenant_wallet(owner_model, admin_url)

        client = ACApyClient(admin_url)
        did_data = client.create_did()
        did = did_data.get('result', {}).get('did')

        return Wallet.objects.create(
            owner=owner_model,
            wallet_id=agent_key,
            agent_admin_url=admin_url,
            public_did=did,
        )

    def _create_multitenant_wallet(self, owner_model, admin_url: str) -> Wallet:
        """Crea un sub-wallet aislado en el agente holder multitenant."""
        wallet_name = f"user-{uuid.uuid4().hex[:16]}"
        wallet_key  = uuid.uuid4().hex

        client = ACApyClient(admin_url)
        data = client.create_subwallet(wallet_name, wallet_key)

        # ACA-Py devuelve wallet_id y token JWT para este sub-wallet
        sub_wallet_id = data.get('wallet_id', wallet_name)
        token         = data.get('token', '')

        # Crear un DID dentro del sub-wallet usando su JWT
        holder_client = ACApyClient(admin_url, jwt=token)
        did_data = holder_client.create_did()
        did = did_data.get('result', {}).get('did')

        return Wallet.objects.create(
            owner=owner_model,
            wallet_id=sub_wallet_id,
            agent_admin_url=admin_url,
            public_did=did,
            wallet_token=token,
        )
    
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