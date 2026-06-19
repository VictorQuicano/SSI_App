from django.contrib import admin
from .models import User, EVTOL, Vertiport, Wallet, Connection, CredentialIssuance

admin.site.register(User)
admin.site.register(EVTOL)
admin.site.register(Vertiport)
admin.site.register(Wallet)
admin.site.register(Connection)
admin.site.register(CredentialIssuance)
