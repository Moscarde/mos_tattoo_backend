"""
Serializers para o app core.
"""

from rest_framework import serializers

from .models import Unidade


class UnidadeSerializer(serializers.ModelSerializer):
    """Serializer para Unidade."""

    class Meta:
        model = Unidade
        fields = ["id", "nome", "codigo", "ativa", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
