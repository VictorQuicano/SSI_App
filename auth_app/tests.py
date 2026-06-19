"""
Tests unitarios para los modelos y endpoints de Django.
Estos tests NO requieren ACA-Py ni VON Network activos — usan mocks.

Para ejecutar:
    python manage.py test auth_app
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from auth_app.models import EVTOL, Vertiport, Wallet, Connection, CredentialIssuance
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _mock_wallet_service():
    """Devuelve un mock de WalletService.create_wallet que no llama a ACA-Py."""
    mock = MagicMock()
    mock.create_wallet.side_effect = lambda owner_model, agent_key: Wallet.objects.create(
        owner=owner_model,
        wallet_id=agent_key,
        agent_admin_url=f'http://localhost:9999',
        public_did='did:sov:test123',
    )
    return mock


# ─── Modelo: User ─────────────────────────────────────────────────────────────

class UserModelTest(TestCase):

    def test_create_user(self):
        user = User.objects.create_user(username='alice', password='pass123')
        self.assertEqual(user.username, 'alice')
        self.assertTrue(user.check_password('pass123'))

    def test_user_str(self):
        user = User.objects.create_user(username='bob', password='x')
        self.assertEqual(str(user), 'bob')


# ─── Modelo: EVTOL ────────────────────────────────────────────────────────────

class EvtolModelTest(TestCase):

    def test_create_evtol(self):
        evtol = EVTOL.objects.create(
            name='Eagle-1', model='X200', manufacturer='AeroCorp',
            serial_number='SN-001',
        )
        self.assertEqual(evtol.state, 'ACTIVE')
        self.assertTrue(evtol.can_fly)
        self.assertEqual(evtol.version, 'v1')

    def test_evtol_str(self):
        evtol = EVTOL.objects.create(
            name='Eagle-1', model='X200', manufacturer='AeroCorp',
            serial_number='SN-002',
        )
        self.assertIn('Eagle-1', str(evtol))
        self.assertIn('SN-002', str(evtol))

    def test_serial_number_unique(self):
        EVTOL.objects.create(
            name='A', model='M', manufacturer='C', serial_number='UNIQUE-1'
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            EVTOL.objects.create(
                name='B', model='M', manufacturer='C', serial_number='UNIQUE-1'
            )


# ─── Modelo: Vertiport ────────────────────────────────────────────────────────

class VertiportModelTest(TestCase):

    def test_create_vertiport(self):
        vp = Vertiport.objects.create(
            vertiport_id='VP-01', name='Norte', location='Lat 0, Lon 0', capacity=10
        )
        self.assertEqual(vp.state, 'ACTIVE')
        self.assertEqual(vp.capacity, 10)

    def test_vertiport_str(self):
        vp = Vertiport.objects.create(
            vertiport_id='VP-02', name='Sur', location='x', capacity=5
        )
        self.assertIn('Sur', str(vp))
        self.assertIn('VP-02', str(vp))

    def test_vertiport_id_unique(self):
        Vertiport.objects.create(
            vertiport_id='VP-U', name='A', location='x', capacity=1
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Vertiport.objects.create(
                vertiport_id='VP-U', name='B', location='y', capacity=2
            )


# ─── Modelo: Wallet polimórfico ───────────────────────────────────────────────

class WalletPolymorphicTest(TestCase):

    def test_wallet_for_user(self):
        user = User.objects.create_user(username='carol', password='x')
        wallet = Wallet.objects.create(
            owner=user, wallet_id='user_1',
            agent_admin_url='http://localhost:8041',
        )
        self.assertEqual(wallet.owner, user)
        self.assertEqual(user.wallets.count(), 1)

    def test_wallet_for_evtol(self):
        evtol = EVTOL.objects.create(
            name='E1', model='M', manufacturer='C', serial_number='SN-W1'
        )
        Wallet.objects.create(
            owner=evtol, wallet_id='evtol_1',
            agent_admin_url='http://localhost:8051',
        )
        self.assertEqual(evtol.wallets.count(), 1)

    def test_wallet_for_vertiport(self):
        vp = Vertiport.objects.create(
            vertiport_id='VP-W1', name='V', location='x', capacity=3
        )
        Wallet.objects.create(
            owner=vp, wallet_id='vertiport_1',
            agent_admin_url='http://localhost:8061',
        )
        self.assertEqual(vp.wallets.count(), 1)


# ─── Endpoint: POST /api/user/ ────────────────────────────────────────────────

class UserEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()

    @patch('auth_app.serializers.WalletService')
    def test_create_user_success(self, MockWS):
        MockWS.return_value = _mock_wallet_service()
        payload = {
            'username': 'dave', 'email': 'dave@test.com',
            'password': 'secret123', 'password_confirm': 'secret123',
            'first_name': 'Dave', 'last_name': 'Test',
        }
        resp = self.client.post(
            '/api/user/', data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')
        self.assertTrue(User.objects.filter(username='dave').exists())

    def test_create_user_password_mismatch(self):
        payload = {
            'username': 'eve', 'email': 'eve@test.com',
            'password': 'abc', 'password_confirm': 'xyz',
        }
        resp = self.client.post(
            '/api/user/', data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_user_missing_fields(self):
        resp = self.client.post(
            '/api/user/', data=json.dumps({'username': 'frank'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)


# ─── Endpoint: POST /api/evtol/ ───────────────────────────────────────────────

class EvtolEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()

    @patch('auth_app.serializers.WalletService')
    def test_create_evtol_success(self, MockWS):
        MockWS.return_value = _mock_wallet_service()
        payload = {
            'name': 'Eagle-2', 'model': 'X300', 'manufacturer': 'AeroCorp',
            'serial_number': 'SN-E2', 'agent_key': 'evtol_1',
        }
        resp = self.client.post(
            '/api/evtol/', data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['status'], 'success')
        self.assertTrue(EVTOL.objects.filter(serial_number='SN-E2').exists())

    def test_create_evtol_missing_fields(self):
        resp = self.client.post(
            '/api/evtol/', data=json.dumps({'name': 'X'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    @patch('auth_app.serializers.WalletService')
    def test_list_evtols(self, MockWS):
        MockWS.return_value = _mock_wallet_service()
        EVTOL.objects.create(
            name='List-1', model='M', manufacturer='C', serial_number='SN-L1'
        )
        resp = self.client.get('/api/evtol/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('evtols', resp.json())


# ─── Endpoint: POST /api/vertiport/ ──────────────────────────────────────────

class VertiportEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()

    @patch('auth_app.serializers.WalletService')
    def test_create_vertiport_success(self, MockWS):
        MockWS.return_value = _mock_wallet_service()
        payload = {
            'vertiport_id': 'VP-T1', 'name': 'Test Port',
            'location': 'Lat -16, Lon -71', 'capacity': 8,
            'agent_key': 'vertiport_1',
        }
        resp = self.client.post(
            '/api/vertiport/', data=json.dumps(payload), content_type='application/json'
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()['status'], 'success')
        self.assertTrue(Vertiport.objects.filter(vertiport_id='VP-T1').exists())

    def test_create_vertiport_missing_fields(self):
        resp = self.client.post(
            '/api/vertiport/', data=json.dumps({'name': 'X'}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 400)

    @patch('auth_app.serializers.WalletService')
    def test_list_vertiports(self, MockWS):
        MockWS.return_value = _mock_wallet_service()
        Vertiport.objects.create(
            vertiport_id='VP-L1', name='Norte', location='x', capacity=5
        )
        resp = self.client.get('/api/vertiport/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('vertiports', resp.json())


# ─── Endpoint: login ──────────────────────────────────────────────────────────

class LoginEndpointTest(TestCase):

    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='grace', password='mypass')

    def test_login_success(self):
        resp = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': 'grace', 'password': 'mypass'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')

    def test_login_wrong_password(self):
        resp = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': 'grace', 'password': 'wrong'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 401)
