"""
Serializers para o app accounts.
"""
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Profile
from core.serializers import UnidadeSerializer


class UserSerializer(serializers.ModelSerializer):
    """Serializer para User."""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer para Profile."""
    user = UserSerializer(read_only=True)
    unidades = UnidadeSerializer(many=True, read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'role', 'role_display', 
            'unidades', 'ativo', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']
