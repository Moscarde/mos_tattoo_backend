"""
Views para o app dashboards.
"""

from django.db import connection
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DashboardInstance, DashboardTemplate, DataSource
from .serializers import (
    DashboardInstanceListSerializer,
    DashboardInstanceSerializer,
    DashboardTemplateSerializer,
    DataSourceSerializer,
)


class DashboardInstanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para DashboardInstance.

    Retorna apenas os dashboards que o usuário tem permissão para acessar.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DashboardInstanceSerializer

    def get_queryset(self):
        """
        Filtra dashboards baseado nas permissões do usuário.

        - Admin técnico e gerente geral: todos os dashboards ativos
        - Gerente de unidade: apenas dashboards de suas unidades
        """
        user = self.request.user

        try:
            profile = user.profile
        except:
            return DashboardInstance.objects.none()

        queryset = DashboardInstance.objects.filter(ativo=True)

        # Admin técnico e gerente geral veem tudo
        if profile.is_admin_tecnico() or profile.is_gerente_geral():
            return queryset

        # Gerente de unidade vê apenas suas unidades
        unidades_permitidas = profile.get_unidades_permitidas()
        queryset = queryset.filter(unidade__in=unidades_permitidas)

        return queryset.select_related("template", "unidade")

    def get_serializer_class(self):
        """Usa serializer simplificado para list action."""
        if self.action == "list":
            return DashboardInstanceListSerializer
        return DashboardInstanceSerializer

    def _execute_datasources(self, schema, unidade):
        """
        Processa o schema e executa todas as queries de datasources.

        Args:
            schema: Schema do template (dict com blocks, etc)
            unidade: Instância de Unidade para filtrar os dados

        Returns:
            dict: Mapeamento {datasource_nome: dados}
        """
        datasources_data = {}

        # Parâmetros que serão injetados em todas as queries
        params = {
            "unidade_id": str(unidade.id),
            "unidade_codigo": unidade.codigo,
        }

        # Procura por dataSource nos blocos
        blocks = schema.get("blocks", [])
        datasource_names = set()

        for block in blocks:
            if isinstance(block, dict):
                datasource_name = block.get("dataSource")
                if datasource_name:
                    datasource_names.add(datasource_name)

        # Executa cada datasource encontrado
        for datasource_name in datasource_names:
            try:
                datasource = DataSource.objects.get(nome=datasource_name, ativo=True)
                success, result = datasource.execute_query(params=params)

                if success:
                    datasources_data[datasource_name] = result
                else:
                    datasources_data[datasource_name] = {
                        "error": result,
                        "success": False,
                    }
            except DataSource.DoesNotExist:
                datasources_data[datasource_name] = {
                    "error": f"DataSource '{datasource_name}' não encontrado",
                    "success": False,
                }
            except Exception as e:
                datasources_data[datasource_name] = {
                    "error": str(e),
                    "success": False,
                }

        return datasources_data

    @action(detail=True, methods=["get"])
    def data(self, request, pk=None):
        """
        Retorna os dados de um dashboard específico.

        Endpoint: /api/dashboards/{id}/data/

        Executa as queries definidas no schema do template e retorna os dados.
        Os parâmetros unidade_id e unidade_codigo são injetados automaticamente.
        """
        dashboard = self.get_object()

        # Verifica se o usuário tem permissão para acessar este dashboard
        try:
            profile = request.user.profile
            if not profile.pode_acessar_unidade(dashboard.unidade):
                return Response(
                    {"error": "Você não tem permissão para acessar este dashboard."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except:
            return Response(
                {"error": "Perfil de usuário não encontrado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Processa o schema e executa as datasources
        schema = dashboard.template.schema
        datasources_data = self._execute_datasources(schema, dashboard.unidade)

        return Response(
            {
                "id": dashboard.id,
                "template_nome": dashboard.template.nome,
                "unidade": {
                    "id": dashboard.unidade.id,
                    "nome": dashboard.unidade.nome,
                    "codigo": dashboard.unidade.codigo,
                },
                "schema": schema,
                "data": datasources_data,
            }
        )


class DataSourceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para DataSource.

    Apenas admin técnico pode acessar.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DataSourceSerializer
    queryset = DataSource.objects.filter(ativo=True)

    def get_queryset(self):
        """Apenas admin técnico pode listar data sources."""
        user = self.request.user
        try:
            profile = user.profile
            if profile.is_admin_tecnico():
                return self.queryset
        except:
            pass

        return DataSource.objects.none()

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """
        Testa a execução de uma query de DataSource.

        Endpoint: /api/datasources/{id}/test/
        Body: {"params": {"unidade_id": "123"}}
        """
        datasource = self.get_object()

        # Apenas admin técnico pode testar
        try:
            profile = request.user.profile
            if not profile.is_admin_tecnico():
                return Response(
                    {"error": "Apenas administradores técnicos podem testar queries."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except:
            return Response(
                {"error": "Perfil de usuário não encontrado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        params = request.data.get("params", {})

        try:
            with connection.cursor() as cursor:
                cursor.execute(datasource.sql, params)
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()

                # Converte para lista de dicts
                results = [dict(zip(columns, row)) for row in rows]

                return Response(
                    {
                        "success": True,
                        "row_count": len(results),
                        "columns": columns,
                        "data": results[
                            :10
                        ],  # Retorna apenas 10 primeiros registros no teste
                    }
                )
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
