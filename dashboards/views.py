"""
Views para o app dashboards.
"""

from django.db import connection
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import DashboardBlock, DashboardInstance, DashboardTemplate, DataSource
from .serializers import (
    DashboardBlockDataSerializer,
    DashboardInstanceDataSerializer,
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

    def _execute_datasources(self, schema, dashboard_instance):
        """
        Processa o schema e executa todas as queries de datasources.

        Processa tanto componentes estruturados quanto schema JSON livre (legado).

        Args:
            schema: Schema do template (dict com blocks, etc) - opcional/legado
            dashboard_instance: Instância do dashboard com o filtro SQL

        Returns:
            dict: Mapeamento {datasource_nome: dados}
        """
        from .models import TemplateComponent

        datasources_data = {}
        template = dashboard_instance.template

        # 1. Processa componentes estruturados (PRIORITÁRIO)
        componentes = TemplateComponent.objects.filter(
            template=template, ativo=True
        ).select_related("datasource", "component_type")

        for componente in componentes:
            try:
                # Aplica o filtro SQL da instância
                sql_modificado = self._aplicar_filtro_sql(
                    componente.datasource.sql, dashboard_instance.filtro_sql
                )

                # Executa a query modificada
                success, result = self._executar_query_customizada(
                    componente.datasource.connection, sql_modificado
                )

                if success:
                    # Inclui metadados do componente junto com os dados
                    datasources_data[componente.nome] = {
                        "type": componente.component_type.nome,
                        "config": componente.config,
                        "data": result,
                    }
                else:
                    datasources_data[componente.nome] = {
                        "type": componente.component_type.nome,
                        "error": result,
                        "success": False,
                    }
            except Exception as e:
                datasources_data[componente.nome] = {
                    "type": (
                        componente.component_type.nome
                        if componente.component_type
                        else "unknown"
                    ),
                    "error": str(e),
                    "success": False,
                }

        # 2. Processa schema JSON livre (LEGADO - para compatibilidade)
        if schema and isinstance(schema, dict):
            blocks = schema.get("blocks", [])
            datasource_names = set()

            for block in blocks:
                if isinstance(block, dict):
                    datasource_name = block.get("dataSource")
                    if datasource_name and datasource_name not in datasources_data:
                        datasource_names.add(datasource_name)

            # Executa datasources do schema JSON que ainda não foram processados
            for datasource_name in datasource_names:
                try:
                    from .models import DataSource

                    datasource = DataSource.objects.get(
                        nome=datasource_name, ativo=True
                    )

                    # Aplica o filtro SQL da instância
                    sql_modificado = self._aplicar_filtro_sql(
                        datasource.sql, dashboard_instance.filtro_sql
                    )

                    # Executa a query modificada
                    success, result = self._executar_query_customizada(
                        datasource.connection, sql_modificado
                    )

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

    def _aplicar_filtro_sql(self, sql_original, filtro_sql):
        """
        Aplica o filtro SQL customizado à query original.

        Remove o ponto-e-vírgula final e adiciona WHERE + filtro.
        Se já houver WHERE na query, usa AND para concatenar.

        Args:
            sql_original: Query SQL original
            filtro_sql: Filtro SQL da instância (ex: "id = 1")

        Returns:
            str: SQL modificado
        """
        # Remove ponto-e-vírgula final
        sql = sql_original.strip()
        if sql.endswith(";"):
            sql = sql[:-1]

        # Se não houver filtro, retorna o SQL original
        if not filtro_sql or not filtro_sql.strip():
            return sql + ";"

        # Verifica se já existe WHERE na query (case-insensitive)
        sql_lower = sql.lower()
        has_where = " where " in sql_lower

        # Adiciona o filtro apropriadamente
        if has_where:
            # Se já tem WHERE, usa AND
            sql_modificado = f"{sql} AND ({filtro_sql.strip()});"
        else:
            # Se não tem WHERE, adiciona WHERE
            sql_modificado = f"{sql} WHERE {filtro_sql.strip()};"

        return sql_modificado

    def _executar_query_customizada(self, connection, sql):
        """
        Executa uma query SQL customizada.

        Args:
            connection: Objeto Connection
            sql: Query SQL a ser executada

        Returns:
            tuple: (sucesso: bool, dados: list|str)
        """
        import psycopg2
        import psycopg2.extras

        if not connection or not connection.ativo:
            return False, "Connection inativa ou não configurada"

        try:
            conn = psycopg2.connect(
                host=connection.host,
                port=connection.porta,
                database=connection.database,
                user=connection.usuario,
                password=connection.senha,
                connect_timeout=10,
            )

            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cursor.execute(sql)
            results = cursor.fetchall()

            # Converte RealDictRow para dict comum
            data = [dict(row) for row in results]

            cursor.close()
            conn.close()

            return True, data

        except psycopg2.OperationalError as e:
            return False, f"Erro de conexão: {str(e)}"
        except psycopg2.ProgrammingError as e:
            return False, f"Erro na query SQL: {str(e)}"
        except Exception as e:
            return False, f"Erro ao executar query: {str(e)}"

    @action(detail=True, methods=["get"], url_path="data-legacy")
    def data_legacy(self, request, pk=None):
        """
        Retorna os dados de um dashboard usando sistema LEGADO (TemplateComponent).

        Endpoint: /api/dashboards/{id}/data-legacy/

        LEGADO: Mantido apenas para compatibilidade com dashboards antigos.
        Use o endpoint /api/dashboards/{id}/data/ para a arquitetura refatorada.
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
        datasources_data = self._execute_datasources(schema, dashboard)

        return Response(
            {
                "id": dashboard.id,
                "template_nome": dashboard.template.nome,
                "unidade": {
                    "id": dashboard.unidade.id,
                    "nome": dashboard.unidade.nome,
                    "codigo": dashboard.unidade.codigo,
                },
                "filtro_sql": dashboard.filtro_sql,
                "schema": schema,
                "data": datasources_data,
            }
        )

    @action(detail=True, methods=["get"])
    def data(self, request, pk=None):
        """
        Retorna os dados de um dashboard com DashboardBlocks (arquitetura refatorada).

        Endpoint: /api/dashboards/{id}/data/

        Arquitetura refatorada:
        - Usa DashboardBlock ao invés de schema JSON livre
        - Normaliza os dados antes de expor
        - Retorna formato padronizado e previsível
        - Valida campos antes de retornar dados

        Formato de resposta:
        {
            "id": "uuid",
            "template_nome": "Dashboard Vendas",
            "unidade": {"id": "uuid", "nome": "São Paulo", "codigo": "SP"},
            "schema": {"grid": {"columns": 12}},
            "blocks": [
                {
                    "id": "uuid",
                    "title": "Vendas por dia",
                    "chart": {"type": "bar"},
                    "layout": {"colSpan": 6, "rowSpan": 1},
                    "data": {
                        "x": ["2026-02-14", "2026-02-15"],
                        "series": [
                            {
                                "axis": "y1",
                                "label": "Vendas",
                                "values": [31, 48]
                            }
                        ]
                    },
                    "success": true
                }
            ]
        }
        """
        dashboard = self.get_object()

        # Verifica permissões
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

        # Busca todos os blocos ativos do template
        blocks = (
            DashboardBlock.objects.filter(template=dashboard.template, ativo=True)
            .select_related("datasource", "datasource__connection")
            .order_by("order")
        )

        # Processa cada bloco
        blocks_data = []
        for block in blocks:
            block_data = self._process_dashboard_block(block, dashboard)
            blocks_data.append(block_data)

        # Monta schema de grid (padrão 12 colunas)
        schema = dashboard.template.schema or {}
        if "grid" not in schema:
            schema["grid"] = {"columns": 12}

        # Monta resposta final
        response_data = {
            "id": str(dashboard.id),
            "template_nome": dashboard.template.nome,
            "unidade": {
                "id": str(dashboard.unidade.id),
                "nome": dashboard.unidade.nome,
                "codigo": dashboard.unidade.codigo,
            },
            "schema": schema,
            "blocks": blocks_data,
        }

        # Valida com serializer (garante formato correto)
        serializer = DashboardInstanceDataSerializer(data=response_data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)

    def _process_dashboard_block(self, block, dashboard_instance):
        """
        Processa um DashboardBlock: executa query, normaliza dados.

        Args:
            block: Instância de DashboardBlock
            dashboard_instance: Instância de DashboardInstance (para filtro SQL)

        Returns:
            dict: Dados do bloco normalizados
        """
        try:
            # 1. Aplica filtro SQL da instância
            sql_modificado = self._aplicar_filtro_sql(
                block.datasource.sql, dashboard_instance.filtro_sql
            )

            # 2. Executa query
            success, result = self._executar_query_customizada(
                block.datasource.connection, sql_modificado
            )

            if not success:
                return {
                    "id": str(block.id),
                    "title": block.title,
                    "chart": {"type": block.chart_type},
                    "layout": {"colSpan": block.col_span, "rowSpan": block.row_span},
                    "data": None,
                    "error": result,
                    "success": False,
                }

            # 3. Normaliza os dados
            try:
                normalized_data = block.normalize_data(result)
            except ValueError as e:
                # Erro de validação de campos
                return {
                    "id": str(block.id),
                    "title": block.title,
                    "chart": {"type": block.chart_type},
                    "layout": {"colSpan": block.col_span, "rowSpan": block.row_span},
                    "data": None,
                    "error": str(e),
                    "success": False,
                }

            # 4. Retorna bloco normalizado
            return {
                "id": str(block.id),
                "title": block.title,
                "chart": {
                    "type": block.chart_type,
                    **block.config,  # Merge com configurações extras
                },
                "layout": {"colSpan": block.col_span, "rowSpan": block.row_span},
                "data": normalized_data,
                "success": True,
            }

        except Exception as e:
            # Erro inesperado
            return {
                "id": str(block.id),
                "title": block.title,
                "chart": {"type": block.chart_type},
                "layout": {"colSpan": block.col_span, "rowSpan": block.row_span},
                "data": None,
                "error": f"Erro ao processar bloco: {str(e)}",
                "success": False,
            }


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
