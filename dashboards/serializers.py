"""
Serializers para o app dashboards.
"""

from rest_framework import serializers

from core.serializers import UnidadeSerializer

from .models import (
    ComponentType,
    DashboardBlock,
    DashboardInstance,
    DashboardTemplate,
    DataSource,
    TemplateComponent,
)


class ComponentTypeSerializer(serializers.ModelSerializer):
    """Serializer para ComponentType."""

    class Meta:
        model = ComponentType
        fields = ["id", "nome", "descricao"]


class DataSourceSerializer(serializers.ModelSerializer):
    """Serializer para DataSource."""

    connection_nome = serializers.CharField(source="connection.nome", read_only=True)

    class Meta:
        model = DataSource
        fields = [
            "id",
            "nome",
            "descricao",
            "connection",
            "connection_nome",
            "sql",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class TemplateComponentSerializer(serializers.ModelSerializer):
    """Serializer para TemplateComponent."""

    component_type = ComponentTypeSerializer(read_only=True)
    datasource_nome = serializers.CharField(source="datasource.nome", read_only=True)

    class Meta:
        model = TemplateComponent
        fields = [
            "id",
            "nome",
            "component_type",
            "datasource_nome",
            "config",
            "ordem",
        ]


class DashboardTemplateSerializer(serializers.ModelSerializer):
    """Serializer para DashboardTemplate."""

    componentes = TemplateComponentSerializer(many=True, read_only=True)

    class Meta:
        model = DashboardTemplate
        fields = [
            "id",
            "nome",
            "descricao",
            "ativo",
            "componentes",
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
        fields = [
            "id",
            "template",
            "unidade",
            "filtro_sql",
            "ativo",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]


class DashboardInstanceListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listagem de DashboardInstance."""

    template_nome = serializers.CharField(source="template.nome", read_only=True)
    unidade_nome = serializers.CharField(source="unidade.nome", read_only=True)
    unidade_codigo = serializers.CharField(source="unidade.codigo", read_only=True)
    filtro_sql_preview = serializers.SerializerMethodField()

    class Meta:
        model = DashboardInstance
        fields = [
            "id",
            "template_nome",
            "unidade_nome",
            "unidade_codigo",
            "filtro_sql_preview",
            "ativo",
        ]

    def get_filtro_sql_preview(self, obj):
        """Retorna preview do filtro SQL (primeiros 50 chars)."""
        if obj.filtro_sql:
            return (
                obj.filtro_sql[:50] + "..."
                if len(obj.filtro_sql) > 50
                else obj.filtro_sql
            )
        return None


class DashboardBlockSerializer(serializers.ModelSerializer):
    """
    Serializer para DashboardBlock.

    Usado para administração e leitura simples dos blocos.
    """

    datasource_nome = serializers.CharField(source="datasource.nome", read_only=True)
    chart_type_display = serializers.CharField(
        source="get_chart_type_display", read_only=True
    )

    class Meta:
        model = DashboardBlock
        fields = [
            "id",
            "title",
            "order",
            "chart_type",
            "chart_type_display",
            "x_axis_field",
            "x_axis_granularity",
            "series_field",
            "y_axis_aggregations",
            "col_span",
            "row_span",
            "datasource_nome",
            "config",
            "ativo",
        ]


class DashboardBlockDataSerializer(serializers.Serializer):
    """
    Serializer para dados normalizados de um DashboardBlock.

    Este é o formato FINAL que o frontend recebe.
    Segue o contrato da API definido na especificação.
    """

    id = serializers.UUIDField(help_text="ID único do bloco")
    title = serializers.CharField(help_text="Título do bloco")

    chart = serializers.DictField(
        help_text="Configuração do gráfico",
        child=serializers.CharField(),
    )

    layout = serializers.DictField(
        help_text="Configuração de layout (colSpan, rowSpan)",
    )

    data = serializers.DictField(
        help_text="Dados normalizados (x, series)",
        allow_null=True,
    )

    error = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Mensagem de erro, se houver",
    )

    success = serializers.BooleanField(
        default=True,
        help_text="Indica se o bloco foi carregado com sucesso",
    )


class DashboardInstanceDataSerializer(serializers.Serializer):
    """
    Serializer para o payload completo da API /api/v2/dashboards/{id}/data.

    Este é o CONTRATO FINAL da API - estável e versionável.
    """

    id = serializers.UUIDField(help_text="ID da instância do dashboard")
    template_nome = serializers.CharField(help_text="Nome do template")

    unidade = serializers.DictField(
        help_text="Informações da unidade",
    )

    schema = serializers.DictField(
        help_text="Configuração de grid e layout global",
    )

    blocks = DashboardBlockDataSerializer(
        many=True,
        help_text="Lista de blocos com dados normalizados",
    )

    filters = serializers.DictField(
        required=False,
        allow_null=True,
        help_text="Metadados de filtros disponíveis e aplicados",
    )
