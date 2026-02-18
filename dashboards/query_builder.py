"""
QueryBuilder - Camada Central de Geração Dinâmica de Queries

Responsável por transformar intenções analíticas (DataSource + DashboardBlock + filtros)
em queries SQL seguras e otimizadas.

Inspirado em: Looker, Metabase, Lightdash
"""

import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple


class SemanticType:
    """Tipos semânticos suportados."""

    DATETIME = "datetime"
    MEASURE = "measure"
    DIMENSION = "dimension"


class AggregationType:
    """Agregações suportadas."""

    SUM = "sum"
    AVG = "avg"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MIN = "min"
    MAX = "max"
    MEDIAN = "median"


class TimeGranularity:
    """Granularidades temporais suportadas."""

    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

    @classmethod
    def get_date_trunc_format(cls, granularity: str) -> str:
        """Retorna o formato de date_trunc para PostgreSQL."""
        mapping = {
            cls.HOUR: "hour",
            cls.DAY: "day",
            cls.WEEK: "week",
            cls.MONTH: "month",
            cls.QUARTER: "quarter",
            cls.YEAR: "year",
        }
        return mapping.get(granularity, "day")


class ColumnMetadata:
    """
    Representa metadados de uma coluna do dataset.

    Armazena tipo no banco, tipo semântico e operações permitidas.
    """

    def __init__(
        self,
        name: str,
        database_type: str,
        semantic_type: str,
        nullable: bool = True,
        allowed_aggregations: Optional[List[str]] = None,
        allowed_granularities: Optional[List[str]] = None,
    ):
        self.name = name
        self.database_type = database_type
        self.semantic_type = semantic_type
        self.nullable = nullable
        self.allowed_aggregations = allowed_aggregations or []
        self.allowed_granularities = allowed_granularities or []

    @classmethod
    def from_dict(cls, data: dict) -> "ColumnMetadata":
        """Cria instância a partir de dicionário."""
        return cls(
            name=data["name"],
            database_type=data["database_type"],
            semantic_type=data["semantic_type"],
            nullable=data.get("nullable", True),
            allowed_aggregations=data.get("allowed_aggregations", []),
            allowed_granularities=data.get("allowed_granularities", []),
        )

    def to_dict(self) -> dict:
        """Converte para dicionário."""
        return {
            "name": self.name,
            "database_type": self.database_type,
            "semantic_type": self.semantic_type,
            "nullable": self.nullable,
            "allowed_aggregations": self.allowed_aggregations,
            "allowed_granularities": self.allowed_granularities,
        }

    @staticmethod
    def infer_semantic_type(database_type: str) -> str:
        """
        Infere o tipo semântico a partir do tipo do banco de dados.

        Args:
            database_type: Tipo no PostgreSQL (ex: integer, timestamp, varchar)

        Returns:
            Tipo semântico (datetime, measure, dimension)
        """
        db_type = database_type.lower()

        # Tipos temporais
        datetime_types = [
            "timestamp",
            "timestamptz",
            "date",
            "time",
            "timetz",
            "interval",
        ]
        if any(dt in db_type for dt in datetime_types):
            return SemanticType.DATETIME

        # Tipos numéricos (medidas)
        numeric_types = [
            "integer",
            "int",
            "bigint",
            "smallint",
            "decimal",
            "numeric",
            "real",
            "double precision",
            "float",
            "money",
        ]
        if any(nt in db_type for nt in numeric_types):
            return SemanticType.MEASURE

        # Tipos textuais e categóricos (dimensões)
        return SemanticType.DIMENSION

    @staticmethod
    def get_allowed_aggregations(semantic_type: str) -> List[str]:
        """Retorna agregações permitidas para o tipo semântico."""
        if semantic_type == SemanticType.MEASURE:
            return [
                AggregationType.SUM,
                AggregationType.AVG,
                AggregationType.COUNT,
                AggregationType.COUNT_DISTINCT,
                AggregationType.MIN,
                AggregationType.MAX,
                AggregationType.MEDIAN,
            ]
        elif semantic_type == SemanticType.DIMENSION:
            return [
                AggregationType.COUNT,
                AggregationType.COUNT_DISTINCT,
            ]
        elif semantic_type == SemanticType.DATETIME:
            return [
                AggregationType.COUNT,
                AggregationType.MIN,
                AggregationType.MAX,
            ]
        return []

    @staticmethod
    def get_allowed_granularities(semantic_type: str) -> List[str]:
        """Retorna granularidades permitidas para o tipo semântico."""
        if semantic_type == SemanticType.DATETIME:
            return [
                TimeGranularity.HOUR,
                TimeGranularity.DAY,
                TimeGranularity.WEEK,
                TimeGranularity.MONTH,
                TimeGranularity.QUARTER,
                TimeGranularity.YEAR,
            ]
        return []


class QueryBuilder:
    """
    Construtor dinâmico de queries SQL analíticas.

    Responsável por:
    - Encapsular query base do DataSource
    - Aplicar agregações, group by, ordenação
    - Gerar aliases padronizados
    - Aplicar filtros estruturados
    - Proteger contra SQL injection
    """

    def __init__(
        self,
        base_query: str,
        columns_metadata: List[ColumnMetadata],
        connection_params: Optional[dict] = None,
    ):
        """
        Inicializa o QueryBuilder.

        Args:
            base_query: Query SQL base (SELECT sem agregações)
            columns_metadata: Metadados das colunas do dataset
            connection_params: Parâmetros de conexão (opcional, para validação)
        """
        self.base_query = base_query.strip()
        self.columns_metadata = columns_metadata
        self.connection_params = connection_params or {}

        # Cria índice de metadados por nome de coluna
        self._columns_index = {col.name: col for col in columns_metadata}

    def get_column_metadata(self, column_name: str) -> Optional[ColumnMetadata]:
        """Retorna metadados de uma coluna."""
        return self._columns_index.get(column_name)

    def validate_column(self, column_name: str) -> bool:
        """Valida se uma coluna existe no dataset."""
        return column_name in self._columns_index

    def validate_aggregation(self, column_name: str, aggregation: str) -> bool:
        """Valida se uma agregação é permitida para uma coluna."""
        metadata = self.get_column_metadata(column_name)
        if not metadata:
            return False
        return aggregation in metadata.allowed_aggregations

    def validate_granularity(self, column_name: str, granularity: str) -> bool:
        """Valida se uma granularidade é permitida para uma coluna."""
        metadata = self.get_column_metadata(column_name)
        if not metadata:
            return False
        return granularity in metadata.allowed_granularities

    def build_analytical_query(
        self,
        x_axis_field: Optional[str] = None,
        x_axis_granularity: Optional[str] = None,
        y_axis_metrics: Optional[List[Dict[str, str]]] = None,
        series_field: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = "metric_date",
        limit: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Gera query analítica completa.

        Args:
            x_axis_field: Campo do eixo X (opcional - se None, faz agregação total sem agrupamento)
            x_axis_granularity: Granularidade temporal (se aplicável)
            y_axis_metrics: Lista de métricas do eixo Y
                Formato: [{"field": "revenue", "aggregation": "sum", "label": "Total"}]
            series_field: Campo para legendas/séries (opcional)
            filters: Filtros estruturados
                Formato: {
                    "date_start": "2024-01-01",
                    "date_end": "2024-12-31",
                    "dimensions": {"category": ["A", "B"]},
                    "custom": "status = 'active'",
                    "block_filter": "status = 'ativo'"
                }
            order_by: Campo para ordenação (padrão: metric_date, None se sem eixo X)
            limit: Limite de registros (opcional)

        Returns:
            Tupla (query_sql, params_dict)
        """
        y_axis_metrics = y_axis_metrics or []

        # Valida campos (x_axis_field é opcional para métricas simples)
        if x_axis_field and not self.validate_column(x_axis_field):
            raise ValueError(f"Campo do eixo X '{x_axis_field}' não existe no dataset")

        if series_field and not self.validate_column(series_field):
            raise ValueError(f"Campo de série '{series_field}' não existe no dataset")

        # Valida métricas
        for metric in y_axis_metrics:
            field = metric.get("field")
            aggregation = metric.get("aggregation")

            if not self.validate_column(field):
                raise ValueError(f"Campo da métrica '{field}' não existe no dataset")

            if not self.validate_aggregation(field, aggregation):
                raise ValueError(
                    f"Agregação '{aggregation}' não permitida para '{field}'"
                )

        # Valida granularidade
        if x_axis_granularity and x_axis_field:
            if not self.validate_granularity(x_axis_field, x_axis_granularity):
                raise ValueError(
                    f"Granularidade '{x_axis_granularity}' não permitida para '{x_axis_field}'"
                )

        # Monta SELECT com aliases padronizados
        select_parts = []

        # Eixo X (com ou sem granularidade) - OPCIONAL para métricas simples
        if x_axis_field:
            x_metadata = self.get_column_metadata(x_axis_field)
            if x_metadata.semantic_type == SemanticType.DATETIME and x_axis_granularity:
                trunc_format = TimeGranularity.get_date_trunc_format(x_axis_granularity)
                select_parts.append(
                    f"DATE_TRUNC('{trunc_format}', {x_axis_field}) AS metric_date"
                )
            else:
                select_parts.append(f"{x_axis_field} AS metric_date")
        else:
            # Para métricas sem eixo X, usa valor fixo para compatibilidade com formato de resposta
            select_parts.append("'Total' AS metric_date")

        # Métricas do eixo Y
        for idx, metric in enumerate(y_axis_metrics):
            field = metric["field"]
            agg = metric["aggregation"].upper()
            alias = f"metric_value_{idx + 1}"

            if agg == "COUNT_DISTINCT":
                select_parts.append(f"COUNT(DISTINCT {field}) AS {alias}")
            elif agg == "MEDIAN":
                select_parts.append(
                    f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {field}) AS {alias}"
                )
            else:
                select_parts.append(f"{agg}({field}) AS {alias}")

        # Série/legenda (opcional)
        if series_field:
            select_parts.append(f"{series_field} AS series_key")

        # Monta query com CTE
        query_parts = []
        query_parts.append("WITH __base_data AS (")
        query_parts.append(f"  {self.base_query}")
        query_parts.append(")")
        query_parts.append("SELECT")
        query_parts.append("  " + ",\n  ".join(select_parts))
        query_parts.append("FROM __base_data")

        # Aplica filtros
        where_clauses = []
        params = {}

        if filters:
            # Filtro de data (formato antigo, mantido por compatibilidade)
            # Apenas aplicável se houver eixo X (para métricas simples, não há eixo temporal)
            date_start = filters.get("date_start")
            date_end = filters.get("date_end")

            if x_axis_field and date_start:
                where_clauses.append(f"{x_axis_field} >= %(date_start)s")
                params["date_start"] = date_start

            if x_axis_field and date_end:
                where_clauses.append(f"{x_axis_field} <= %(date_end)s")
                params["date_end"] = date_end

            # Filtros dimensionais (formato antigo, mantido por compatibilidade)
            dimension_filters = filters.get("dimensions", {})
            for dim_field, dim_values in dimension_filters.items():
                if not self.validate_column(dim_field):
                    continue

                param_name = f"dim_{dim_field}"
                where_clauses.append(f"{dim_field} = ANY(%({param_name})s)")
                params[param_name] = dim_values

            # Filtros dinâmicos (novo formato)
            # Estrutura: {"field": {"gte": "2024-01-01", "lte": "2024-12-31"}}
            #            {"field": {"in": [1, 2, 3]}}
            dynamic_filters = filters.get("dynamic_filters", {})
            for field, conditions in dynamic_filters.items():
                if not self.validate_column(field):
                    continue

                for operator, value in conditions.items():
                    param_name = f"dyn_{field}_{operator}"

                    if operator == "gte":
                        where_clauses.append(f"{field} >= %({param_name})s")
                        params[param_name] = value
                    elif operator == "lte":
                        where_clauses.append(f"{field} <= %({param_name})s")
                        params[param_name] = value
                    elif operator == "gt":
                        where_clauses.append(f"{field} > %({param_name})s")
                        params[param_name] = value
                    elif operator == "lt":
                        where_clauses.append(f"{field} < %({param_name})s")
                        params[param_name] = value
                    elif operator == "eq":
                        where_clauses.append(f"{field} = %({param_name})s")
                        params[param_name] = value
                    elif operator == "in":
                        # Para IN, value deve ser uma lista
                        if isinstance(value, list) and len(value) > 0:
                            where_clauses.append(f"{field} = ANY(%({param_name})s)")
                            params[param_name] = value

            # Filtro SQL customizado (from config.filter_sql or where_clause)
            custom_filter = filters.get("custom") or filters.get("where_clause")
            if custom_filter:
                # IMPORTANTE: Este filtro vem de configuração confiável (admin)
                # não do usuário final
                where_clauses.append(f"({custom_filter})")

            # Filtro específico do bloco (block_filter)
            # Permite criar múltiplos blocos da mesma fonte com filtros diferentes
            block_filter = filters.get("block_filter")
            if block_filter:
                # IMPORTANTE: Este filtro vem de configuração confiável (admin)
                # não do usuário final
                where_clauses.append(f"({block_filter})")

        if where_clauses:
            query_parts.append("WHERE")
            query_parts.append("  " + "\n  AND ".join(where_clauses))

        # GROUP BY (apenas se houver dimensões para agrupar)
        group_by_parts = []
        if x_axis_field:
            group_by_parts.append("metric_date")
        if series_field:
            group_by_parts.append("series_key")

        if group_by_parts:
            query_parts.append("GROUP BY " + ", ".join(group_by_parts))
        # Se não há GROUP BY, é agregação total (métricas simples)

        # ORDER BY
        if order_by and x_axis_field:
            # Só ordena se houver eixo X (senão é só um registro)
            query_parts.append(f"ORDER BY {order_by}")

        # LIMIT
        if limit:
            query_parts.append(f"LIMIT {int(limit)}")

        final_query = "\n".join(query_parts)
        return final_query, params

    def build_preview_query(self, limit: int = 100) -> str:
        """
        Gera query de preview simples do dataset.

        Args:
            limit: Número máximo de registros

        Returns:
            Query SQL de preview
        """
        return f"""
SELECT *
FROM ({self.base_query}) AS __preview
LIMIT {int(limit)}
        """.strip()

    @staticmethod
    def escape_identifier(identifier: str) -> str:
        """
        Escapa identificadores SQL (colunas, tabelas).

        Args:
            identifier: Nome do identificador

        Returns:
            Identificador escapado entre aspas duplas
        """
        # Remove caracteres perigosos
        safe_identifier = re.sub(r"[^a-zA-Z0-9_]", "", identifier)
        return f'"{safe_identifier}"'

    @staticmethod
    def validate_safe_query(query: str) -> Tuple[bool, Optional[str]]:
        """
        Valida se a query é segura (sem DDL/DML).

        Args:
            query: Query SQL a validar

        Returns:
            Tupla (is_safe, error_message)
        """
        query_lower = query.lower().strip()

        # Proíbe ponto-e-vírgula
        if ";" in query:
            return False, "Query não pode conter ponto-e-vírgula (múltiplos statements)"

        # Deve começar com SELECT ou WITH
        if not (query_lower.startswith("select") or query_lower.startswith("with")):
            return False, "Query deve começar com SELECT ou WITH"

        # Palavras-chave proibidas
        forbidden = [
            "insert",
            "update",
            "delete",
            "drop",
            "create",
            "alter",
            "truncate",
            "grant",
            "revoke",
            "execute",
            "call",
        ]

        for keyword in forbidden:
            if re.search(rf"\b{keyword}\b", query_lower):
                return False, f"Palavra-chave '{keyword.upper()}' não permitida"

        return True, None


class QueryExecutor:
    """
    Executor de queries com proteções e otimizações.

    Responsável por executar queries geradas pelo QueryBuilder
    com timeout, limite de memória e logs.
    """

    def __init__(self, connection):
        """
        Inicializa o executor.

        Args:
            connection: Instância do model Connection
        """
        self.connection = connection

    def execute_query(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
    ) -> Tuple[bool, Any]:
        """
        Executa query com proteções.

        Args:
            query: Query SQL a executar
            params: Parâmetros da query (opcional)
            timeout: Timeout em segundos

        Returns:
            Tupla (success, data_or_error)
        """
        import psycopg2
        import psycopg2.extras

        if not self.connection.ativo:
            return False, "Conexão está inativa"

        try:
            conn = psycopg2.connect(
                host=self.connection.host,
                port=self.connection.porta,
                database=self.connection.database,
                user=self.connection.usuario,
                password=self.connection.senha,
                connect_timeout=10,
            )

            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Define timeout
            cursor.execute(f"SET statement_timeout = '{timeout}s'")

            # Executa query
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            # Busca resultados
            results = cursor.fetchall()
            data = [dict(row) for row in results]

            cursor.close()
            conn.close()

            return True, data

        except psycopg2.OperationalError as e:
            return False, f"Erro de conexão: {str(e)}"

        except psycopg2.ProgrammingError as e:
            return False, f"Erro na query: {str(e)}"

        except Exception as e:
            error_str = str(e)
            if "timeout" in error_str.lower() or "canceled" in error_str.lower():
                return False, f"Query cancelada (timeout de {timeout}s excedido)"
            return False, f"Erro ao executar query: {error_str}"
