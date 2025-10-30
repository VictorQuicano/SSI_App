# views.py
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from services.wallet_service import WalletService
from auth_app.models import Wallet, Connection
from auth_app.serializers import UserRegistrationSerializer
from django.views.decorators.csrf import csrf_exempt
import json


@csrf_exempt
def create_user(request):
    """Vista para registrar un nuevo usuario"""
    if request.method == 'POST':
        
        data = json.loads(request.body)
        serializer = UserRegistrationSerializer(data=data)
        
        if serializer.is_valid():
            user = serializer.save()
            return JsonResponse({'status': 'success', 'user_id': user.id})
        else:
            return JsonResponse({'status': 'error', 'errors': serializer.errors}, status=400)
    return JsonResponse({'error': 'Invalid request method'}, status=405)
