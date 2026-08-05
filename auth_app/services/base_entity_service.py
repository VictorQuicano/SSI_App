import time
from .credential_service import CredentialService
from auth_app.aca_py.client import ACApyClient
from auth_app.models import CredentialIssuance, Connection, Wallet
from django.conf import settings

POLL_INTERVAL = 2
POLL_TIMEOUT  = 60


class BaseEntityCredentialService:
    """
    Servicio base para emitir credenciales a cualquier entidad del sistema
    (User, EVTOL, Vertiport, etc.).

    Las subclases deben definir SCHEMA_NAME, SCHEMA_VERSION y SCHEMA_ATTRS.
    La lógica de conexión DIDComm y espera es idéntica para todas.
    """

    SCHEMA_NAME    = None
    SCHEMA_VERSION = None
    SCHEMA_ATTRS   = []

    def __init__(self):
        self.credential_service = CredentialService(
            schema_name=self.SCHEMA_NAME,
            schema_version=self.SCHEMA_VERSION,
            schema_attrs=self.SCHEMA_ATTRS,
        )

    # ── wallet ────────────────────────────────────────────────────────────────

    def _get_wallet(self, entity) -> Wallet:
        wallets = entity.wallets.all()
        if not wallets.exists():
            raise ValueError(f"La entidad '{entity}' no tiene wallet registrado.")
        return wallets.first()

    # ── conexión DIDComm ──────────────────────────────────────────────────────

    def _establish_connection(self, holder_wallet: Wallet) -> Connection:
        existing = Connection.objects.filter(
            wallet=holder_wallet, state='complete'
        ).first()
        if existing:
            return existing

        issuer_client = ACApyClient(settings.ACA_PY_AGENTS['issuer'])
        inv_data      = issuer_client.create_oob_invitation(
            alias=f"holder-{holder_wallet.wallet_id}"
        )
        invi_msg_id = inv_data['invi_msg_id']

        # Para sub-wallets multitenant el JWT identifica el wallet correcto
        holder_client = ACApyClient(holder_wallet.agent_admin_url,
                                    jwt=holder_wallet.wallet_token)
        holder_client.receive_oob_invitation(inv_data['invitation'])

        issuer_conn_id = self._wait_for_connection_by_invitation(issuer_client, invi_msg_id)

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

    def _wait_for_connection_by_invitation(self, client: ACApyClient, invi_msg_id: str) -> str:
        start = time.time()
        while time.time() - start < POLL_TIMEOUT:
            data    = client.get_connections(invitation_msg_id=invi_msg_id)
            results = data.get('results', [])
            if results:
                return results[0]['connection_id']
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(
            f"No se encontró conexión para invitation_msg_id={invi_msg_id} en {POLL_TIMEOUT}s"
        )

    def _wait_for_active(self, client: ACApyClient, conn_id: str):
        start = time.time()
        while time.time() - start < POLL_TIMEOUT:
            data = client.get_connection(conn_id)
            if data.get('state') == 'active':
                return
            time.sleep(POLL_INTERVAL)
        raise TimeoutError(f"Conexión {conn_id} no llegó a 'active' en {POLL_TIMEOUT}s")

    # ── emisión ───────────────────────────────────────────────────────────────

    def issue_credential(self, entity, attributes: dict) -> CredentialIssuance:
        wallet     = self._get_wallet(entity)
        connection = self._establish_connection(wallet)
        result     = self.credential_service.issue_credential(
            connection.connection_id, attributes
        )
        return CredentialIssuance.objects.create(
            wallet=wallet,
            connection=connection,
            credential_exchange_id=result['credential_exchange_id'],
            credential_definition_id=result['credential_definition_id'],
            state=result['state'],
            attributes=attributes,
        )

    def get_credentials(self, entity, state: str = None):
        wallet = self._get_wallet(entity)
        qs = CredentialIssuance.objects.filter(wallet=wallet)
        if state:
            qs = qs.filter(state=state)
        return qs
