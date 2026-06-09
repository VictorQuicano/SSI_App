import time
from .credential_service import CredentialService
from .wallet_service import WalletService
from aca_py.client import ACApyClient
from auth_app.models import CredentialIssuance, Connection, Wallet
from django.conf import settings


POLL_INTERVAL = 2
POLL_TIMEOUT  = 60


class UserCredentialService:

    def __init__(self):
        self.credential_service = CredentialService()

    def issue_credential_to_user(self, user, user_data: dict) -> CredentialIssuance:
        wallet = self._get_user_wallet(user)
        connection = self._establish_connection(wallet)

        result = self.credential_service.issue_credential(
            connection.connection_id, user_data
        )

        record = CredentialIssuance.objects.create(
            wallet=wallet,
            connection=connection,
            credential_exchange_id=result['credential_exchange_id'],
            credential_definition_id=result['credential_definition_id'],
            state=result['state'],
            attributes=user_data,
        )
        return record

    def _get_user_wallet(self, user) -> Wallet:
        wallets = user.wallets.all()
        if not wallets.exists():
            raise ValueError(f"El usuario {user} no tiene wallet registrado.")
        return wallets.first()

    def _establish_connection(self, holder_wallet: Wallet) -> Connection:
        existing = Connection.objects.filter(
            wallet=holder_wallet, state='complete'
        ).first()
        if existing:
            return existing

        issuer_client = ACApyClient(settings.ACA_PY_AGENTS['issuer'])
        inv_data = issuer_client.create_invitation(alias=f"holder-{holder_wallet.wallet_id}")
        issuer_conn_id = inv_data['connection_id']

        holder_client = ACApyClient(holder_wallet.agent_admin_url)
        holder_client.receive_invitation(inv_data['invitation'])

        connection = Connection.objects.create(
            wallet=holder_wallet,
            connection_id=issuer_conn_id,
            their_label='issuer',
            state='invited',
            invitation_url=inv_data.get('invitation_url', ''),
        )
        self._wait_for_active(issuer_client, issuer_conn_id)
        connection.state = 'complete'
        connection.save()
        return connection

    def _wait_for_active(self, client: ACApyClient, conn_id: str):
        start = time.time()
        while time.time() - start < POLL_TIMEOUT:
            data = client.get_connection(conn_id)
            if data.get('state') == 'active':
                return
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(f"Conexión {conn_id} no llegó a 'active' en {POLL_TIMEOUT}s")

    def get_user_credentials(self, user, state: str = None):
        wallet = self._get_user_wallet(user)
        qs = CredentialIssuance.objects.filter(wallet=wallet)
        if state:
            qs = qs.filter(state=state)
        return qs
