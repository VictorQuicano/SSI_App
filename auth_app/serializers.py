# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from auth_app.services.wallet_service import WalletService
from auth_app.models import EVTOL, Vertiport
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm', 'first_name', 'last_name')

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Las contraseñas no coinciden")
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        try:
            self.create_user_wallet(user)
        except Exception:
            user.delete()
            raise serializers.ValidationError(
                "Error creando la billetera. Por favor intenta nuevamente."
            )
        return user

    def create_user_wallet(self, user):
        wallet_service = WalletService()
        try:
            wallet_service.create_wallet(owner_model=user, agent_key='holder')
        except Exception as e:
            logger.error(f"Error creating wallet for user {user.username}: {e}")
            raise serializers.ValidationError(
                "Error creando la billetera. Por favor intenta nuevamente."
            )


class EvtolRegistrationSerializer(serializers.ModelSerializer):
    agent_key = serializers.CharField(write_only=True)

    class Meta:
        model = EVTOL
        fields = ('name', 'model', 'manufacturer', 'serial_number', 'state', 'version', 'agent_key')

    def create(self, validated_data):
        agent_key = validated_data.pop('agent_key')
        evtol = EVTOL.objects.create(**validated_data)
        try:
            WalletService().create_wallet(owner_model=evtol, agent_key=agent_key)
        except Exception as e:
            evtol.delete()
            logger.error(f"Error creating wallet for EVTOL {evtol.serial_number}: {e}")
            raise serializers.ValidationError("Error creando la billetera del eVTOL.")
        return evtol


class VertiportRegistrationSerializer(serializers.ModelSerializer):
    agent_key = serializers.CharField(write_only=True)

    class Meta:
        model = Vertiport
        fields = ('vertiport_id', 'name', 'location', 'capacity', 'state', 'agent_key')

    def create(self, validated_data):
        agent_key = validated_data.pop('agent_key')
        vertiport = Vertiport.objects.create(**validated_data)
        try:
            WalletService().create_wallet(owner_model=vertiport, agent_key=agent_key)
        except Exception as e:
            vertiport.delete()
            logger.error(f"Error creating wallet for Vertiport {vertiport.vertiport_id}: {e}")
            raise serializers.ValidationError("Error creando la billetera del vertiport.")
        return vertiport
