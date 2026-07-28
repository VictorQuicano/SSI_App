from auth_app.views import user_views, credential_views, evtol_views, vertiport_views, attestation_views
from django.contrib import admin
from django.urls import path


urlpatterns = [
    path('admin/', admin.site.urls),

    # Usuario
    path('api/user/', user_views.create_user, name='create_user'),
    path('api/auth/login/', user_views.login_user, name='login_user'),

    # Credenciales de usuario
    path('api/credentials/issue/', credential_views.issue_user_credential, name='issue_user_credential'),
    path('api/credentials/my/', credential_views.get_my_credentials, name='get_my_credentials'),
    path('api/credentials/<str:credential_exchange_id>/status/', credential_views.get_credential_status, name='get_credential_status'),
    path('webhooks/credentials/', credential_views.credential_webhook, name='credential_webhook'),

    # eVTOL
    path('api/evtol/', evtol_views.evtol_list_create, name='evtol_list_create'),
    path('api/evtol/<int:evtol_id>/credential/', evtol_views.issue_evtol_credential, name='issue_evtol_credential'),
    path('api/evtol/<int:evtol_id>/credentials/', evtol_views.get_evtol_credentials, name='get_evtol_credentials'),

    # Vertiport
    path('api/vertiport/', vertiport_views.vertiport_list_create, name='vertiport_list_create'),
    path('api/vertiport/<int:vertiport_id>/credential/', vertiport_views.issue_vertiport_credential, name='issue_vertiport_credential'),
    path('api/vertiport/<int:vertiport_id>/credentials/', vertiport_views.get_vertiport_credentials, name='get_vertiport_credentials'),

    # Atestaciones Trusted Verifier (SSI → Besu)
    path('api/attest/user/', attestation_views.attest_user, name='attest_user'),
    path('api/attest/vertiport/', attestation_views.attest_vertiport, name='attest_vertiport'),
    path('api/attest/evtol/', attestation_views.attest_evtol, name='attest_evtol'),
]
