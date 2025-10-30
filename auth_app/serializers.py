# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from services.wallet_service import WalletService
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
        try:
            # Crear wallet después de crear el usuario
            self.create_user_wallet(user)
        except Exception as e:
            user.delete()
            raise serializers.ValidationError(
                "Error creando la billetera. Por favor intenta nuevamente."
            )
        return user
    
    def create_user_wallet(self, user):
        """Crear wallet para el usuario"""
        wallet_service = WalletService()
        
        try:
            # Generar nombres únicos para el wallet
            wallet_name = f"wallet_{user.username}_{user.id}"
            
            wallet_service.create_wallet(
                model=user,
                wallet_name=wallet_name
            )
            
            # Actualizar usuario con info del wallet
            
            # Opcional: Crear DID público
            # did_data = aca_py_service.create_public_did(
            #     wallet_data["wallet_id"], 
            #     wallet_key
            # )
            # user.save()
            
        except Exception as e:
            # Manejar error - podrías querer eliminar el usuario si falla
            logger.error(f"Error creating wallet for user {user.username}: {e}")
            # Opcional: user.delete() si quieres rollback completo
            raise serializers.ValidationError(
                "Error creando la billetera. Por favor intenta nuevamente."
            )