from auth_app.views import user_views
from auth_app.views import credential_views
from django.contrib import admin
from django.urls import path


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/user/', user_views.create_user, name='create_user'),
    #path('api/credentials/dni/issue/', credential_views.issue_dni_credential, name='issue_dni_credential'),
    #path('api/credentials/my/', credential_views.get_my_credentials, name='get_my_credentials'),
    #path('api/credentials/<str:credential_exchange_id>/status/', credential_views.get_credential_status, name='get_credential_status'),
    #path('webhooks/credentials/', credential_views.credential_webhook, name='credential_webhook'),
]