INDY_API_URL = "http://localhost:9000"

#TODO: Configurar para Prod
ACA_PY_CONFIG = {
    # URL del Admin API (puerto 9031 en tu configuración)
    'admin_url': "http://localhost:9031",
    
    # Como usas --admin-insecure-mode, no necesitas API key
    'api_key': None,
    
    # Configuración del wallet
    'wallet_name': "postgres_wallet",
    'wallet_key': "walletkey123",
    
    # Configuración de base de datos
    'wallet_storage_type': 'postgres_storage',
    'wallet_storage_config': {
        'url': 'postgres:5432/postgres_wallet',
        'max_connections': 5
    },
    'wallet_storage_creds': {
        'account': 'acapy_user',
        'password': 'acapy_password',
        'admin_account': 'acapy_user', 
        'admin_password': 'acapy_password'
    },
    
    # Endpoint público del agente
    'endpoint': "http://localhost:9000",
    
    # Label del agente
    'label': 'Agent with Local Genesis',
    
    # Configuración adicional
    'genesis_file': '/home/indy/genesis.txn',
    'wallet_type': 'askar',
    'auto_provision': True,
    'log_level': 'INFO',

    'seeder': '000000000000000000000000Trustee1'
}