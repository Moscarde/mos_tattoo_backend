"""
Serializers para o app dashboards.
"""

from rest_framework import serializers

from core.serializers import UnidadeSerializer

from .models import DashboardInstance, DashboardTemplate, DataSource


class DashboardTemplateSerializer(serializers.ModelSerializer):
    """Serializer para DashboardTemplate."""

    class Meta:
        model = DashboardTemplate
        fields = [
            "id",
            "nome",
            "descricao",
            "ativo",
            "schema",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class DashboardInstanceSerializer(serializers.ModelSerializer):
    """Serializer para DashboardInstance."""

    template = DashboardTemplateSerializer(read_only=True)
    unidade = UnidadeSerializer(read_only=True)

    class Meta:
        model = DashboardInstance
        fields = ["id", "template", "unidade", "ativo", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class DashboardInstanceListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagem de DashboardInstance."""

    template_nome = serializers.CharField(source="template.nome", read_only=True)
    unidade_nome = serializers.CharField(source="unidade.nome", read_only=True)
    unidade_codigo = serializers.CharField(source="unidade.codigo", read_only=True)

    class Meta:
        model = DashboardInstance
        fields = ["id", "template_nome", "unidade_nome", "unidade_codigo", "ativo"]


class DataSourceSerializer(serializers.ModelSerializer):
    """Serializer para DataSource."""

    class Meta:
        model = DataSource
        fields = [
            "id",
            "nome",
            "descricao",
            "sql",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
