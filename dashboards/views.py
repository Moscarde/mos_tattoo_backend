"""
Views para o app dashboards.
"""

from django.db import connection
from rest_framework import status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

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

        # Parse filtros aplicados via query params
        applied_filters = self._parse_applied_filters(request, dashboard.template)

        # Processa cada bloco
        blocks_data = []
        for block in blocks:
            block_data = self._process_dashboard_block(
                block, dashboard, applied_filters
            )
            blocks_data.append(block_data)

        # Monta schema de grid (padrão 12 colunas)
        schema = dashboard.template.schema or {}
        if "grid" not in schema:
            schema["grid"] = {"columns": 12}

        # Obtém metadados de filtros disponíveis (com filtros interdependentes)
        filter_metadata = dashboard.template.get_filter_metadata(
            instance_filter_sql=dashboard.filtro_sql, applied_filters=applied_filters
        )

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
            "filters": {
                "available": filter_metadata,
                "applied": applied_filters,
            },
        }

        # Valida com serializer (garante formato correto)
        serializer = DashboardInstanceDataSerializer(data=response_data)
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data)

    def _parse_applied_filters(self, request, template):
        """
        Parse query params para extrair filtros aplicados.

        Suporta:
        - Temporal: ?field__gte=2024-01-01&field__lte=2024-12-31
        - Categórico: ?field__in=1,2,3

        IMPORTANTE: O frontend deve enviar TODOS os filtros ativos em cada requisição.
        Filtros não enviados são considerados "removidos" (API stateless).

        Args:
            request: Request object
            template: DashboardTemplate instance

        Returns:
            dict: Filtros parseados {field: {operator: value}}
        """
        import logging

        logger = logging.getLogger(__name__)

        if not template.filterable_fields:
            return {}

        filters = {}
        allowed_fields = set()
        categorical_fields = {}

        # Coleta campos permitidos
        if template.filterable_fields.get("temporal"):
            allowed_fields.add(template.filterable_fields["temporal"]["field"])

        for cat in template.filterable_fields.get("categorical", []):
            field_name = cat["field"]
            allowed_fields.add(field_name)
            categorical_fields[field_name] = cat

        # Obtém metadata das colunas para type casting
        # Pega primeiro datasource do template como referência
        datasource = (
            DashboardBlock.objects.filter(template=template)
            .select_related("datasource")
            .first()
        )

        columns_metadata = {}
        if datasource and datasource.datasource.columns_metadata:
            for col in datasource.datasource.columns_metadata:
                columns_metadata[col["name"]] = col

        # Parse query params
        logger.info(f"Query params recebidos: {dict(request.query_params)}")

        for param, value in request.query_params.items():
            # Ignora params que não são filtros
            if "__" not in param:
                continue

            parts = param.split("__")
            if len(parts) != 2:
                continue

            field, operator = parts

            # Valida se campo é permitido
            if field not in allowed_fields:
                logger.warning(
                    f"Campo '{field}' não está em filterable_fields configurados"
                )
                continue

            # Parse valor baseado no operador
            if operator in ["gte", "lte", "gt", "lt", "eq"]:
                # Temporal ou numérico
                if field not in filters:
                    filters[field] = {}
                filters[field][operator] = value

            elif operator == "in":
                # Categórico (lista) - precisa de type casting
                if field not in filters:
                    filters[field] = {}

                # Converte string "1,2,3" em lista
                raw_values = [v.strip() for v in value.split(",") if v.strip()]

                # Type casting baseado no metadata
                col_meta = columns_metadata.get(field, {})
                db_type = col_meta.get("database_type", "").lower()

                typed_values = []
                for v in raw_values:
                    try:
                        # Se é numérico (int, bigint, etc)
                        if "int" in db_type:
                            typed_values.append(int(v))
                        # Se é float/decimal
                        elif any(
                            t in db_type
                            for t in ["float", "double", "decimal", "numeric"]
                        ):
                            typed_values.append(float(v))
                        # Se é boolean
                        elif "bool" in db_type:
                            typed_values.append(v.lower() in ["true", "1", "yes"])
                        # Caso contrário, mantém como string
                        else:
                            typed_values.append(v)
                    except (ValueError, TypeError):
                        # Se falhar conversão, mantém como string
                        typed_values.append(v)

                filters[field]["in"] = typed_values

        logger.info(f"Filtros parseados: {filters}")
        return filters

    def _process_dashboard_block(self, block, dashboard_instance, applied_filters=None):
        """
        Processa um DashboardBlock: executa query usando Semantic Layer.

        Args:
            block: Instância de DashboardBlock
            dashboard_instance: Instância de DashboardInstance (para filtro SQL)
            applied_filters: Dict de filtros aplicados via query params

        Returns:
            dict: Dados do bloco formatados para o frontend
        """
        try:
            # Executa query usando Semantic Layer com filtros
            # Aplica filtro global da instância (ex: unit_code = 'SP-01') a todos os blocos
            success, result = block.get_data(
                applied_filters=applied_filters,
                instance_filter_sql=dashboard_instance.filtro_sql if dashboard_instance else None
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

            # Monta configuração do chart
            chart_config = {
                "type": block.chart_type,
                **block.config,  # Merge com configurações extras
            }

            # Adiciona configurações específicas de Métrica/KPI
            if block.chart_type == "metric":
                if block.metric_prefix:
                    chart_config["metricPrefix"] = block.metric_prefix
                if block.metric_suffix:
                    chart_config["metricSuffix"] = block.metric_suffix
                if block.metric_decimal_places is not None:
                    chart_config["metricDecimalPlaces"] = block.metric_decimal_places

            # Retorna bloco com dados
            return {
                "id": str(block.id),
                "title": block.title,
                "chart": chart_config,
                "layout": {"colSpan": block.col_span, "rowSpan": block.row_span},
                "data": result,
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

    # Permite autenticação via JWT (API) ou Session (Django Admin)
    authentication_classes = [JWTAuthentication, SessionAuthentication]
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

    @action(detail=True, methods=["post"])
    def execute_analytical(self, request, pk=None):
        """
        Executa query analítica usando a Semantic Layer (QueryBuilder).

        Endpoint: /api/datasources/{id}/execute_analytical/

        Body exemplo:
        {
            "fields": ["produto", "categoria"],
            "aggregations": [
                {
                    "field": "valor_venda",
                    "aggregation": "sum",
                    "alias": "total_vendas"
                },
                {
                    "field": "valor_venda",
                    "aggregation": "avg",
                    "alias": "ticket_medio"
                }
            ],
            "granularity": {
                "field": "data_venda",
                "level": "month"
            },
            "filters": {
                "where_clause": "categoria = 'Eletrônicos'"
            },
            "group_by": ["produto"],
            "order_by": ["total_vendas DESC"],
            "limit": 100
        }

        Returns:
            {
                "success": true,
                "row_count": 50,
                "columns": ["produto", "mes", "total_vendas", "ticket_medio"],
                "data": [
                    {
                        "produto": "Notebook",
                        "mes": "2024-01",
                        "total_vendas": 50000,
                        "ticket_medio": 2500
                    },
                    ...
                ]
            }
        """
        datasource = self.get_object()

        # Apenas admin técnico pode executar queries analíticas
        try:
            profile = request.user.profile
            if not profile.is_admin_tecnico():
                return Response(
                    {
                        "error": "Apenas administradores técnicos podem executar queries analíticas."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
        except:
            return Response(
                {"error": "Perfil de usuário não encontrado."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Valida se DataSource tem columns_metadata (semantic layer)
        if not datasource.columns_metadata:
            return Response(
                {
                    "success": False,
                    "error": "Este DataSource não possui metadata semântica. Re-salve o DataSource para extrair metadata.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Extrai parâmetros da requisição
        fields = request.data.get("fields", [])
        aggregations = request.data.get("aggregations", [])
        granularity = request.data.get("granularity")
        filters = request.data.get("filters", {})
        group_by = request.data.get("group_by", [])
        order_by = request.data.get("order_by", [])
        limit = request.data.get("limit", 1000)

        try:
            # Executa query analítica
            results = datasource.execute_analytical_query(
                fields=fields,
                aggregations=aggregations,
                granularity=granularity,
                filters=filters,
                group_by=group_by,
                order_by=order_by,
                limit=limit,
            )

            # Extrai colunas da primeira linha
            columns = list(results[0].keys()) if results else []

            return Response(
                {
                    "success": True,
                    "row_count": len(results),
                    "columns": columns,
                    "data": results,
                }
            )
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"])
    def metadata(self, request, pk=None):
        """
        Retorna os metadados (colunas) da fonte de dados.

        Endpoint: /api/datasources/{id}/metadata/

        Returns:
            {
                "success": true,
                "columns": [
                    {
                        "name": "data_venda",
                        "semantic_type": "datetime",
                        "data_type": "timestamp",
                        "pg_type": "timestamp without time zone"
                    },
                    {
                        "name": "valor_venda",
                        "semantic_type": "measure",
                        "data_type": "numeric",
                        "pg_type": "numeric"
                    },
                    {
                        "name": "produto",
                        "semantic_type": "dimension",
                        "data_type": "text",
                        "pg_type": "character varying"
                    }
                ]
            }
        """
        # Busca o DataSource diretamente sem restrições de get_queryset
        # para permitir acesso no Django Admin
        try:
            datasource = DataSource.objects.get(pk=pk, ativo=True)
        except DataSource.DoesNotExist:
            return Response(
                {"success": False, "error": "DataSource não encontrado", "columns": []},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not datasource.columns_metadata:
            return Response(
                {
                    "success": False,
                    "error": "Este DataSource não possui metadata semântica. Re-salve o DataSource para extrair metadata.",
                    "columns": [],
                },
                status=status.HTTP_200_OK,  # Retorna 200 mesmo sem metadata
            )

        # columns_metadata já é uma lista de dicionários com estrutura:
        # [{"name": "col1", "semantic_type": "datetime", "database_type": "timestamp", ...}, ...]
        columns = []
        for col_info in datasource.columns_metadata:
            columns.append(
                {
                    "name": col_info.get("name", ""),
                    "semantic_type": col_info.get("semantic_type", "dimension"),
                    "data_type": col_info.get(
                        "semantic_type", "unknown"
                    ),  # Usa semantic_type como data_type
                    "pg_type": col_info.get("database_type", "unknown"),
                }
            )

        # Ordena colunas: datetime primeiro, depois measure, depois dimension
        type_order = {"datetime": 0, "measure": 1, "dimension": 2}
        columns.sort(key=lambda x: (type_order.get(x["semantic_type"], 3), x["name"]))

        return Response(
            {
                "success": True,
                "columns": columns,
            }
        )


class DashboardBlockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para DashboardBlock.

    Permite executar queries e obter dados para blocos de dashboard.
    """

    # Permite autenticação via JWT (API) ou Session (Django Admin)
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]
    queryset = DashboardBlock.objects.filter(ativo=True)

    def get_queryset(self):
        """Filtra blocos baseado nas permissões do usuário."""
        user = self.request.user
        try:
            profile = user.profile
            if profile.is_admin_tecnico():
                return self.queryset
        except:
            pass

        return DashboardBlock.objects.none()

    @action(detail=True, methods=["get"])
    def data(self, request, pk=None):
        """
        Obtém os dados do bloco executando sua query via Semantic Layer.

        Endpoint: /api/dashboard-blocks/{id}/data/

        Returns:
            {
                "success": true,
                "data": {
                    "x": ["2024-01", "2024-02", "2024-03"],
                    "series": [
                        {
                            "axis": "y1",
                            "label": "Total de Vendas",
                            "values": [50000, 60000, 55000]
                        },
                        {
                            "axis": "y2",
                            "label": "Ticket Médio",
                            "values": [2500, 2800, 2600]
                        }
                    ]
                }
            }
        """
        block = self.get_object()

        # Valida se bloco está configurado
        if not block.x_axis_field:
            return Response(
                {
                    "success": False,
                    "error": "Bloco não está configurado (x_axis_field não definido).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Valida se tem métricas configuradas
        if not block.y_axis_aggregations:
            return Response(
                {
                    "success": False,
                    "error": "Bloco não possui métricas configuradas (y_axis_aggregations).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Executa query via Semantic Layer
            normalized_data = block.get_data()

            return Response(
                {
                    "success": True,
                    "data": normalized_data,
                }
            )
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST
            )
