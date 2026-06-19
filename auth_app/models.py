from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.auth.models import User as DjangoUser
from django.contrib.contenttypes.fields import GenericRelation


class Wallet(models.Model):
    wallet_id = models.CharField(max_length=255)
    public_did = models.CharField(max_length=255, blank=True, null=True)
    agent_admin_url = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    # --- Relación polimórfica ---
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    owner = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"Wallet for {self.owner.__str__()}"

class User(AbstractUser):
    is_wallet_created = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    wallets = GenericRelation(Wallet, content_type_field='content_type', object_id_field='object_id')

    def __str__(self):
        return self.username

class EVTOL(models.Model):
    STATES = [('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('MAINTENANCE', 'Maintenance')]

    name = models.CharField(max_length=100, default='')
    model = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    serial_number = models.CharField(max_length=100, unique=True)
    state = models.CharField(max_length=20, choices=STATES, default='ACTIVE')
    version = models.CharField(max_length=20, default='v1')
    can_fly = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    wallets = GenericRelation(Wallet, content_type_field='content_type', object_id_field='object_id')

    def __str__(self):
        return f"EVTOL {self.name} ({self.serial_number})"


class Vertiport(models.Model):
    STATES = [('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('MAINTENANCE', 'Maintenance')]

    vertiport_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField()
    state = models.CharField(max_length=20, choices=STATES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)
    wallets = GenericRelation(Wallet, content_type_field='content_type', object_id_field='object_id')

    def __str__(self):
        return f"Vertiport {self.name} ({self.vertiport_id})"

class Connection(models.Model):
    CONNECTION_STATES = [
        ('invited', 'Invited'),
        ('requested', 'Requested'),
        ('responded', 'Responded'),
        ('complete', 'Complete'),
    ]
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    connection_id = models.CharField(max_length=255)
    their_label = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=20, choices=CONNECTION_STATES)
    invitation_url = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']


class CredentialIssuance(models.Model):
    CREDENTIAL_STATES = [
        ('proposal_sent', 'Proposal Sent'),
        ('proposal_received', 'Proposal Received'),
        ('offer_sent', 'Offer Sent'),
        ('offer_received', 'Offer Received'),
        ('request_sent', 'Request Sent'),
        ('request_received', 'Request Received'),
        ('credential_issued', 'Credential Issued'),
        ('credential_received', 'Credential Received'),
        ('done', 'Done'),
        ('abandoned', 'Abandoned'),
    ]
    
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    connection = models.ForeignKey('Connection', on_delete=models.CASCADE)
    credential_exchange_id = models.CharField(max_length=255)
    credential_definition_id = models.CharField(max_length=255)
    state = models.CharField(max_length=20, choices=CREDENTIAL_STATES)
    attributes = models.JSONField()  # Almacena los datos de la credencial
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"DNI Credential for {self.wallet.owner.__str__()} - {self.state}"