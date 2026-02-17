"""
Models para o app dashboards.

Este módulo define os modelos relacionados a dashboards:
- DashboardTemplate: templates globais de dashboards
- DashboardInstance: instâncias de dashboards por unidade
- Connection: conexões a bancos de dados externos
- DataSource: fontes de dados (queries SQL) para os dashboards
"""

import uuid
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.models import User
from django.db import models

from core.models import Unidade


class ComponentType(models.Model):
    """
    Tipo de componente/gráfico disponível.

    Define os tipos de visualizações que podem ser usados nos dashboards
    (bar-chart, line-chart, pie-chart, table, etc).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Nome",
        help_text="Identificador do tipo (ex: bar-chart, line-chart, pie-chart)",
    )
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Tipo de Componente"
        verbose_name_plural = "Tipos de Componentes"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class DashboardTemplate(models.Model):
    """
    Template global de dashboard.

    Define a estrutura e layout de um dashboard que pode ser
    instanciado para diferentes unidades.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, verbose_name="Nome")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    schema = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Schema",
        help_text="Estrutura JSON do dashboard (blocos, gráficos, etc.) - Opcional",
    )
    filterable_fields = models.JSONField(
        blank=True,
        null=True,
        verbose_name="Campos Filtráveis",
        help_text=(
            "Configuração de filtros dinâmicos. Exemplo: "
            '{"temporal": {"field": "sold_at", "label": "Data da Venda"}, '
            '"categorical": [{"field": "seller_id", "label": "Vendedor"}]}'
        ),
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Template de Dashboard"
        verbose_name_plural = "Templates de Dashboards"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome

    def _build_dynamic_where_clauses(self, applied_filters, exclude_field=None):
        """
        Constrói cláusulas WHERE baseado em filtros aplicados.

        Args:
            applied_filters: Dict de filtros {field: {operator: value}}
            exclude_field: Campo a ser excluído (para evitar filtro circular)

        Returns:
            tuple: (where_clauses: list, params: dict)
        """
        import logging

        logger = logging.getLogger(__name__)

        where_clauses = []
        params = {}

        if not applied_filters:
            logger.debug("Nenhum filtro aplicado")
            return where_clauses, params

        logger.info(
            f"Construindo WHERE com applied_filters={applied_filters}, exclude_field={exclude_field}"
        )

        for field, conditions in applied_filters.items():
            # Pula o campo sendo calculado (evita circular filter)
            if field == exclude_field:
                logger.debug(f"Pulando campo {field} (exclude_field)")
                continue

            for operator, value in conditions.items():
                param_name = f"filter_{field}_{operator}"

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
                elif operator == "in" and isinstance(value, list) and len(value) > 0:
                    where_clauses.append(f"{field} = ANY(%({param_name})s)")
                    params[param_name] = value

        logger.info(f"WHERE construído: {where_clauses} com params: {params}")
        return where_clauses, params

    def get_filter_metadata(self, instance_filter_sql=None, applied_filters=None):
        """
        Gera metadados dos campos filtráveis configurados no template.

        Para filtros temporais: retorna min e max dates
        Para filtros categóricos: retorna lista de valores distintos

        FILTROS INTERDEPENDENTES: Ao calcular metadados de um campo, aplica
        os outros filtros já selecionados (exceto o próprio campo).

        Args:
            instance_filter_sql: SQL WHERE adicional da instância (opcional)
            applied_filters: Filtros já aplicados pelo usuário {field: {op: value}}

        Returns:
            dict: Metadados estruturados dos filtros
            {
                "temporal": {"field": "sold_at", "label": "Data", "min": "2024-01-01", "max": ...},
                "categorical": [{"field": "seller_id", "label": "Vendedor", "values": [1,2,3]}]
            }
        """
        import logging

        logger = logging.getLogger(__name__)

        if not self.filterable_fields:
            return {"temporal": None, "categorical": []}

        # Pega todas as datasources únicas dos blocos deste template
        datasources = DataSource.objects.filter(blocks__template=self).distinct()

        if not datasources.exists():
            logger.warning(f"Template {self.nome} não tem datasources associadas")
            return {"temporal": None, "categorical": []}

        # Usa a primeira datasource como referência
        # (em dashboards bem projetados, filtros globais devem estar em todos os datasources)
        datasource = datasources.first()

        metadata = {"temporal": None, "categorical": []}

        # Processa filtro temporal
        temporal_config = self.filterable_fields.get("temporal")
        if temporal_config:
            field = temporal_config.get("field")
            label = temporal_config.get("label", field)

            try:
                import psycopg2
                import psycopg2.extras

                # Query diretamente na base query (sem subconsultas desnecessárias)
                min_max_query = f"""
                    SELECT 
                        MIN({field}) as min_value,
                        MAX({field}) as max_value
                    FROM ({datasource.sql}) AS base_data
                """

                # Constrói WHERE clauses (instance + filtros interdependentes)
                all_where_clauses = []
                query_params = {}

                # Filtro de instância
                if instance_filter_sql:
                    all_where_clauses.append(f"({instance_filter_sql})")

                # Filtros dinâmicos (exceto o próprio campo temporal)
                dynamic_where, dynamic_params = self._build_dynamic_where_clauses(
                    applied_filters, exclude_field=field
                )
                all_where_clauses.extend(dynamic_where)
                query_params.update(dynamic_params)

                if all_where_clauses:
                    min_max_query += "\n    WHERE " + " AND ".join(all_where_clauses)

                logger.info(
                    f"Executando query temporal: {min_max_query} com params: {query_params}"
                )

                # Executa usando psycopg2 diretamente
                conn = psycopg2.connect(
                    host=datasource.connection.host,
                    port=datasource.connection.porta,
                    database=datasource.connection.database,
                    user=datasource.connection.usuario,
                    password=datasource.connection.senha,
                    connect_timeout=10,
                )

                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(min_max_query, query_params)
                result = cursor.fetchall()
                cursor.close()
                conn.close()

                logger.info(f"Resultado temporal: result={result}")

                if result and len(result) > 0:
                    row = dict(result[0])
                    metadata["temporal"] = {
                        "field": field,
                        "label": label,
                        "min": (
                            str(row.get("min_value")) if row.get("min_value") else None
                        ),
                        "max": (
                            str(row.get("max_value")) if row.get("max_value") else None
                        ),
                    }
            except Exception as e:
                logger.error(
                    f"Erro ao processar filtro temporal {field}: {str(e)}",
                    exc_info=True,
                )

        # Processa filtros categóricos
        categorical_configs = self.filterable_fields.get("categorical", [])
        for cat_config in categorical_configs:
            field = cat_config.get("field")
            label = cat_config.get("label", field)
            limit = cat_config.get(
                "limit", 100
            )  # Limit para evitar queries muito grandes

            try:
                import psycopg2
                import psycopg2.extras

                # Query diretamente na base query
                distinct_query = f"""
                    SELECT DISTINCT {field} as value
                    FROM ({datasource.sql}) AS base_data
                    WHERE {field} IS NOT NULL
                """

                # Constrói WHERE clauses adicionais (instance + filtros interdependentes)
                additional_where = []
                query_params = {}

                # Filtro de instância
                if instance_filter_sql:
                    additional_where.append(f"({instance_filter_sql})")

                # Filtros dinâmicos (exceto o próprio campo categórico sendo calculado)
                dynamic_where, dynamic_params = self._build_dynamic_where_clauses(
                    applied_filters, exclude_field=field
                )
                additional_where.extend(dynamic_where)
                query_params.update(dynamic_params)

                if additional_where:
                    distinct_query = (
                        distinct_query.rstrip()
                        + "\n      AND "
                        + " AND ".join(additional_where)
                    )

                distinct_query += f"\n    ORDER BY {field}\n    LIMIT {limit}"

                logger.info(
                    f"Executando query categórica: {distinct_query} com params: {query_params}"
                )

                # Executa usando psycopg2 diretamente
                conn = psycopg2.connect(
                    host=datasource.connection.host,
                    port=datasource.connection.porta,
                    database=datasource.connection.database,
                    user=datasource.connection.usuario,
                    password=datasource.connection.senha,
                    connect_timeout=10,
                )

                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute(distinct_query, query_params)
                result = cursor.fetchall()
                cursor.close()
                conn.close()

                logger.info(
                    f"Resultado categórico: len(result)={len(result) if result else 0}"
                )

                if result:
                    values = [dict(row).get("value") for row in result]
                    metadata["categorical"].append(
                        {
                            "field": field,
                            "label": label,
                            "values": values,
                        }
                    )
            except Exception as e:
                logger.error(
                    f"Erro ao processar filtro categórico {field}: {str(e)}",
                    exc_info=True,
                )

        return metadata


class DashboardInstance(models.Model):
    """
    Instância de um dashboard para uma unidade específica.

    Relaciona um template de dashboard a uma unidade e define
    quais usuários têm acesso.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        DashboardTemplate,
        on_delete=models.PROTECT,
        related_name="instances",
        verbose_name="Template",
    )
    unidade = models.ForeignKey(
        Unidade,
        on_delete=models.CASCADE,
        related_name="dashboards",
        verbose_name="Unidade",
    )
    filtro_sql = models.TextField(
        blank=True,
        verbose_name="Filtro SQL",
        help_text="Cláusula WHERE customizada (ex: unidade_codigo = 'SP-01' OR status = 'ativo')",
    )
    usuarios_com_acesso = models.ManyToManyField(
        User,
        related_name="dashboards_acessiveis",
        blank=True,
        verbose_name="Usuários com Acesso",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Instância de Dashboard"
        verbose_name_plural = "Instâncias de Dashboards"
        ordering = ["-criado_em"]
        unique_together = ["template", "unidade"]

    def __str__(self):
        return f"{self.template.nome} - {self.unidade.codigo}"


class Connection(models.Model):
    """
    Conexão a um banco de dados externo (PostgreSQL).

    Armazena as credenciais e informações necessárias para
    conectar a bancos de dados externos para consultas.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome",
        help_text="Nome identificador da conexão",
    )
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    host = models.CharField(
        max_length=255,
        verbose_name="Host",
        help_text="Endereço do servidor (ex: localhost, 192.168.1.10)",
    )
    porta = models.IntegerField(
        default=5432,
        verbose_name="Porta",
        help_text="Porta do PostgreSQL (padrão: 5432)",
    )
    database = models.CharField(
        max_length=100,
        verbose_name="Database",
        help_text="Nome do banco de dados",
    )
    usuario = models.CharField(
        max_length=100,
        verbose_name="Usuário",
        help_text="Usuário para autenticação",
    )
    senha = models.CharField(
        max_length=255,
        verbose_name="Senha",
        help_text="Senha do usuário (armazenada de forma segura)",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Conexão"
        verbose_name_plural = "Conexões"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.host}:{self.porta}/{self.database})"

    def get_connection_string(self):
        """
        Retorna a string de conexão PostgreSQL.
        """
        return (
            f"postgresql://{self.usuario}:{self.senha}@"
            f"{self.host}:{self.porta}/{self.database}"
        )

    def test_connection(self):
        """
        Testa a conexão com o banco de dados.

        Returns:
            tuple: (sucesso: bool, mensagem: str)
        """
        import psycopg2

        try:
            # Tenta conectar com timeout de 5 segundos
            conn = psycopg2.connect(
                host=self.host,
                port=self.porta,
                database=self.database,
                user=self.usuario,
                password=self.senha,
                connect_timeout=5,
            )

            # Testa uma query simples
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()

            return True, "Conexão estabelecida com sucesso!"
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            hint = ""

            # Dá dicas baseadas no erro
            if "Connection refused" in error_msg:
                hint = " | DICA: Se estiver rodando no Docker, use 'host.docker.internal' ou '172.17.0.1' em vez de 'localhost'"
            elif "timeout" in error_msg.lower():
                hint = " | DICA: Verifique se o firewall está bloqueando a porta ou se o servidor está acessível"
            elif "password authentication failed" in error_msg:
                hint = " | DICA: Verifique o usuário e senha"
            elif "database" in error_msg and "does not exist" in error_msg:
                hint = " | DICA: Verifique se o nome do banco está correto"

            return False, f"Erro ao conectar: {error_msg}{hint}"
        except Exception as e:
            return False, f"Erro inesperado: {str(e)}"


class DataSource(models.Model):
    """
    Fonte de dados (dataset base) para alimentar dashboards.

    NOVA ARQUITETURA (Semantic Layer):
    ===================================
    O DataSource representa um DATASET BASE, não uma query agregada.

    Conceito:
    - Query SQL deve ser simples: SELECT * FROM table ou view limpa
    - SEM agregações, GROUP BY ou filtros analíticos
    - O sistema extrai metadados e classifica colunas automaticamente
    - Cada coluna recebe um tipo semântico (datetime, measure, dimension)
    - DashboardBlocks reutilizam o mesmo DataSource com intenções diferentes
    - As agregações são geradas dinamicamente pelo QueryBuilder

    FLUXO DE TRABALHO:
    1. Usuário define query SQL base (SELECT simples, sem agregações)
    2. Sistema valida e extrai metadados das colunas (nome, tipo DB, tipo semântico)
    3. Colunas são classificadas automaticamente (datetime, measure, dimension)
    4. DataSource fica pronto para ser reutilizado em múltiplos blocos
    5. Cada DashboardBlock define: campo X, métricas Y, agregações, granularidade
    6. QueryBuilder gera SQL dinâmico combinando intenção + dataset base

    Inspirado em: Looker (LookML), Metabase (Models), Lightdash (dbt metrics)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome",
        help_text="Nome único para identificar o dataset (ex: 'Sales Data', 'Customer Events')",
    )
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    connection = models.ForeignKey(
        Connection,
        on_delete=models.PROTECT,
        related_name="datasources",
        verbose_name="Conexão",
        help_text="Conexão ao banco de dados onde a query será executada",
        null=True,  # Temporário para a migração
        blank=True,
    )
    sql = models.TextField(
        verbose_name="Query SQL Base",
        help_text=(
            "Query SQL SIMPLES do dataset base. "
            "Use SELECT * FROM table ou view limpa. "
            "NÃO inclua agregações (SUM, COUNT), GROUP BY ou filtros analíticos. "
            "Exemplo: SELECT * FROM sales ou SELECT order_date, customer_id, amount FROM orders"
        ),
    )

    # === METADADOS AUTOMÁTICOS (SEMANTIC LAYER) ===
    columns_metadata = models.JSONField(
        default=list,
        blank=True,
        editable=False,
        verbose_name="Metadados das Colunas",
        help_text=(
            "Metadados completos de cada coluna extraídos automaticamente. "
            "Inclui: nome, tipo no banco, tipo semântico (datetime/measure/dimension), "
            "agregações permitidas, granularidades temporais."
        ),
    )

    # Campos de suporte
    detected_columns = models.JSONField(
        default=list,
        blank=True,
        editable=False,
        verbose_name="Colunas Detectadas",
        help_text="Lista simples de nomes de colunas. Para metadata completa, use columns_metadata.",
    )

    last_validation_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        verbose_name="Última Validação",
        help_text="Data/hora da última validação bem-sucedida da query",
    )

    last_validation_error = models.TextField(
        blank=True,
        editable=False,
        verbose_name="Último Erro de Validação",
        help_text="Mensagem do último erro de validação (se houver)",
    )

    # === CONTRATO SEMÂNTICO ===
    metric_date_column = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Coluna de Data/Tempo",
        help_text="Campo temporal obrigatório (ex: data_venda, created_at, mes_ano)",
    )

    metric_value_column = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Coluna de Valor Métrico",
        help_text="Campo numérico obrigatório (ex: total_vendas, quantidade, receita)",
    )

    series_key_column = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Coluna de Série/Legenda",
        help_text="Campo categórico opcional para legendas (ex: produto, vendedor, unidade)",
    )

    unit_id_column = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Coluna de ID da Unidade",
        help_text="Campo identificador opcional (ex: unidade_id, cod_unidade)",
    )

    contract_validated = models.BooleanField(
        default=False,
        editable=False,
        verbose_name="Contrato Validado",
        help_text="Indica se o contrato semântico foi validado com sucesso",
    )

    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Fonte de Dados"
        verbose_name_plural = "Fontes de Dados"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def _validate_sql_security(self, sql):
        """
        Valida regras de segurança da query SQL.

        Protege contra:
        - Múltiplos statements (;)
        - DDL/DML (INSERT, UPDATE, DELETE, etc)
        - Queries que não sejam SELECT ou WITH

        Args:
            sql (str): Query SQL a validar

        Raises:
            ValidationError: Se a query violar alguma regra de segurança
        """
        from django.core.exceptions import ValidationError

        if not sql:
            return

        # Remove espaços e converte para minúsculo
        sql_clean = sql.strip().lower()

        # Proíbe ponto-e-vírgula (múltiplos statements)
        if ";" in sql:
            raise ValidationError(
                "A query SQL não pode conter ponto-e-vírgula (;). "
                "Apenas um único SELECT é permitido."
            )

        # Verifica se começa com SELECT ou WITH (para CTEs)
        if not (sql_clean.startswith("select") or sql_clean.startswith("with")):
            raise ValidationError(
                "A query SQL deve começar com SELECT ou WITH (Common Table Expression). "
                "Apenas consultas de leitura são permitidas."
            )

        # Palavras-chave proibidas (DDL/DML)
        forbidden_keywords = [
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

        for keyword in forbidden_keywords:
            # Usa word boundary para evitar falsos positivos (ex: 'updated_at')
            import re

            if re.search(rf"\b{keyword}\b", sql_clean):
                raise ValidationError(
                    f'A query SQL não pode conter a palavra-chave "{keyword.upper()}". '
                    "Apenas consultas de leitura (SELECT) são permitidas."
                )

    def validate_and_extract_columns(self):
        """
        Valida a query SQL executando-a com LIMIT 1 e extrai as colunas retornadas.

        Este método:
        1. Executa a query de forma segura (statement_timeout, LIMIT 1)
        2. Verifica sintaxe, permissões e conectividade
        3. Extrai os nomes das colunas retornadas
        4. Atualiza os metadados do DataSource

        Returns:
            tuple: (success: bool, message: str, columns: list)
        """
        import psycopg2
        import psycopg2.extras
        from django.utils import timezone

        if not self.connection:
            return False, "Nenhuma conexão configurada", []

        if not self.connection.ativo:
            return False, "Conexão está inativa", []

        try:
            # Conecta ao banco
            conn = psycopg2.connect(
                host=self.connection.host,
                port=self.connection.porta,
                database=self.connection.database,
                user=self.connection.usuario,
                password=self.connection.senha,
                connect_timeout=5,
            )

            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Define timeout curto para segurança
            cursor.execute("SET statement_timeout = '5s'")

            # Encapsula a query em um subselect com LIMIT 1
            # Isso garante que a query seja executada de forma segura
            safe_query = f"SELECT * FROM ({self.sql}) AS __validation_subquery LIMIT 1"

            cursor.execute(safe_query)

            # Extrai nomes das colunas
            column_names = [desc[0] for desc in cursor.description]

            cursor.close()
            conn.close()

            # Atualiza metadados
            self.detected_columns = column_names
            self.last_validation_at = timezone.now()
            self.last_validation_error = ""

            return (
                True,
                f"Query validada com sucesso. {len(column_names)} colunas detectadas.",
                column_names,
            )

        except psycopg2.OperationalError as e:
            error_msg = f"Erro de conexão: {str(e)}"
            self.last_validation_error = error_msg
            return False, error_msg, []

        except psycopg2.ProgrammingError as e:
            error_msg = f"Erro de sintaxe SQL: {str(e)}"
            self.last_validation_error = error_msg
            return False, error_msg, []

        except Exception as e:
            # Captura timeout e outros erros
            error_str = str(e)
            if "timeout" in error_str.lower() or "canceled" in error_str.lower():
                error_msg = "Query cancelada (timeout de 5s excedido)"
            else:
                error_msg = f"Erro inesperado ao validar query: {error_str}"
            self.last_validation_error = error_msg
            return False, error_msg, []

    def extract_columns_metadata(self):
        """
        Extrai metadados COMPLETOS das colunas e classifica semanticamente.

        Este é o método PRINCIPAL da nova arquitetura semantic layer.

        Extrai para cada coluna:
        - Nome
        - Tipo no banco de dados (PostgreSQL type)
        - Tipo semântico inferido (datetime, measure, dimension)
        - Operações permitidas (agregações para measures, granularidades para datetime)
        - Nullabilidade

        Returns:
            tuple: (success: bool, message: str, metadata: list)
        """
        import psycopg2
        import psycopg2.extras
        from django.utils import timezone

        from .query_builder import ColumnMetadata

        if not self.connection:
            return False, "Nenhuma conexão configurada", []

        if not self.connection.ativo:
            return False, "Conexão está inativa", []

        try:
            # Conecta ao banco
            conn = psycopg2.connect(
                host=self.connection.host,
                port=self.connection.porta,
                database=self.connection.database,
                user=self.connection.usuario,
                password=self.connection.senha,
                connect_timeout=5,
            )

            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Define timeout curto
            cursor.execute("SET statement_timeout = '5s'")

            # Encapsula a query com LIMIT 1 para extrair metadados
            safe_query = f"SELECT * FROM ({self.sql}) AS __metadata_extraction LIMIT 1"

            cursor.execute(safe_query)

            # Extrai informações detalhadas das colunas
            columns_metadata = []

            for desc in cursor.description:
                column_name = desc[0]
                type_code = desc[1]

                # Mapeia type_code para nome do tipo PostgreSQL
                cursor_pg = conn.cursor()
                cursor_pg.execute(
                    "SELECT typname FROM pg_type WHERE oid = %s", (type_code,)
                )
                type_result = cursor_pg.fetchone()
                db_type = type_result[0] if type_result else "unknown"
                cursor_pg.close()

                # Infere tipo semântico
                semantic_type = ColumnMetadata.infer_semantic_type(db_type)

                # Define operações permitidas
                allowed_aggregations = ColumnMetadata.get_allowed_aggregations(
                    semantic_type
                )
                allowed_granularities = ColumnMetadata.get_allowed_granularities(
                    semantic_type
                )

                # Cria metadata
                metadata = ColumnMetadata(
                    name=column_name,
                    database_type=db_type,
                    semantic_type=semantic_type,
                    nullable=True,  # PostgreSQL não fornece isso facilmente via cursor
                    allowed_aggregations=allowed_aggregations,
                    allowed_granularities=allowed_granularities,
                )

                columns_metadata.append(metadata.to_dict())

            cursor.close()
            conn.close()

            # Atualiza metadados
            self.columns_metadata = columns_metadata
            self.detected_columns = [
                col["name"] for col in columns_metadata
            ]  # Compatibilidade
            self.last_validation_at = timezone.now()
            self.last_validation_error = ""

            # Estatísticas
            stats = {
                "total": len(columns_metadata),
                "datetime": sum(
                    1 for c in columns_metadata if c["semantic_type"] == "datetime"
                ),
                "measure": sum(
                    1 for c in columns_metadata if c["semantic_type"] == "measure"
                ),
                "dimension": sum(
                    1 for c in columns_metadata if c["semantic_type"] == "dimension"
                ),
            }

            message = (
                f"✅ Dataset validado com sucesso! "
                f"{stats['total']} colunas detectadas: "
                f"{stats['datetime']} datetime, "
                f"{stats['measure']} measures, "
                f"{stats['dimension']} dimensions"
            )

            return True, message, columns_metadata

        except psycopg2.OperationalError as e:
            error_msg = f"Erro de conexão: {str(e)}"
            self.last_validation_error = error_msg
            return False, error_msg, []

        except psycopg2.ProgrammingError as e:
            error_msg = f"Erro de sintaxe SQL: {str(e)}"
            self.last_validation_error = error_msg
            return False, error_msg, []

        except Exception as e:
            error_str = str(e)
            if "timeout" in error_str.lower() or "canceled" in error_str.lower():
                error_msg = "Query cancelada (timeout de 5s excedido)"
            else:
                error_msg = f"Erro inesperado: {error_str}"
            self.last_validation_error = error_msg
            return False, error_msg, []

    def get_query_builder(self):
        """
        Retorna uma instância do QueryBuilder configurada para este DataSource.

        Returns:
            QueryBuilder instance
        """
        from .query_builder import ColumnMetadata, QueryBuilder

        if not self.columns_metadata:
            raise ValueError(
                "Metadados de colunas não disponíveis. Execute extract_columns_metadata() primeiro."
            )

        # Converte metadata de dict para objetos ColumnMetadata
        columns_metadata = [
            ColumnMetadata.from_dict(col) for col in self.columns_metadata
        ]

        return QueryBuilder(
            base_query=self.sql,
            columns_metadata=columns_metadata,
            connection_params=(
                {
                    "host": self.connection.host,
                    "port": self.connection.porta,
                    "database": self.connection.database,
                }
                if self.connection
                else None
            ),
        )

    def build_analytical_query(
        self,
        x_axis_field: str,
        x_axis_granularity: Optional[str] = None,
        y_axis_metrics: Optional[List[Dict[str, str]]] = None,
        series_field: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = "metric_date",
        limit: Optional[int] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Gera query analítica usando o QueryBuilder.

        Este é o método PRINCIPAL para geração dinâmica de SQL.

        Args:
            x_axis_field: Campo do eixo X
            x_axis_granularity: Granularidade temporal (hour, day, week, month, quarter, year)
            y_axis_metrics: Lista de métricas
                Formato: [{"field": "revenue", "aggregation": "sum", "label": "Total"}]
            series_field: Campo para legendas (opcional)
            filters: Filtros estruturados
            order_by: Campo de ordenação
            limit: Limite de registros

        Returns:
            Tupla (query_sql, params_dict)
        """
        from typing import Any, Dict, List, Optional, Tuple

        builder = self.get_query_builder()

        return builder.build_analytical_query(
            x_axis_field=x_axis_field,
            x_axis_granularity=x_axis_granularity,
            y_axis_metrics=y_axis_metrics,
            series_field=series_field,
            filters=filters,
            order_by=order_by,
            limit=limit,
        )

    def execute_analytical_query(
        self,
        x_axis_field: str,
        x_axis_granularity: Optional[str] = None,
        y_axis_metrics: Optional[List[Dict[str, str]]] = None,
        series_field: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = "metric_date",
        limit: Optional[int] = None,
        timeout: int = 30,
    ) -> Tuple[bool, Any]:
        """
        Gera e executa query analítica.

        Args:
            (mesmos de build_analytical_query)
            timeout: Timeout em segundos

        Returns:
            Tupla (success: bool, data_or_error: list|str)
        """
        from typing import Any, Dict, List, Optional, Tuple

        from .query_builder import QueryExecutor

        try:
            # Gera a query
            query, params = self.build_analytical_query(
                x_axis_field=x_axis_field,
                x_axis_granularity=x_axis_granularity,
                y_axis_metrics=y_axis_metrics,
                series_field=series_field,
                filters=filters,
                order_by=order_by,
                limit=limit,
            )

            # Executa
            executor = QueryExecutor(self.connection)
            return executor.execute_query(query, params, timeout=timeout)

        except Exception as e:
            return False, f"Erro ao gerar/executar query: {str(e)}"

    def validate_semantic_contract(self):
        """
        Valida o contrato semântico.

        Verifica se:
        - Campos obrigatórios estão preenchidos (metric_date, metric_value)
        - Campos mapeados existem nas colunas detectadas
        - Não há duplicatas nos mapeamentos

        Returns:
            tuple: (is_valid: bool, errors: list)
        """
        errors = []

        # Verifica se há colunas detectadas
        if not self.detected_columns:
            errors.append(
                "Nenhuma coluna detectada. Execute a validação da query primeiro."
            )
            return False, errors

        detected_set = set(self.detected_columns)

        # Valida campos obrigatórios
        if not self.metric_date_column:
            errors.append(
                "Campo 'Coluna de Data/Tempo' é obrigatório no contrato semântico."
            )
        elif self.metric_date_column not in detected_set:
            errors.append(
                f"Coluna de data '{self.metric_date_column}' não existe na query. "
                f"Colunas disponíveis: {', '.join(sorted(self.detected_columns))}"
            )

        if not self.metric_value_column:
            errors.append(
                "Campo 'Coluna de Valor Métrico' é obrigatório no contrato semântico."
            )
        elif self.metric_value_column not in detected_set:
            errors.append(
                f"Coluna de valor '{self.metric_value_column}' não existe na query. "
                f"Colunas disponíveis: {', '.join(sorted(self.detected_columns))}"
            )

        # Valida campos opcionais (se preenchidos)
        if self.series_key_column and self.series_key_column not in detected_set:
            errors.append(
                f"Coluna de série '{self.series_key_column}' não existe na query. "
                f"Colunas disponíveis: {', '.join(sorted(self.detected_columns))}"
            )

        if self.unit_id_column and self.unit_id_column not in detected_set:
            errors.append(
                f"Coluna de unidade '{self.unit_id_column}' não existe na query. "
                f"Colunas disponíveis: {', '.join(sorted(self.detected_columns))}"
            )

        # Valida duplicatas
        mapped_columns = [
            col
            for col in [
                self.metric_date_column,
                self.metric_value_column,
                self.series_key_column,
                self.unit_id_column,
            ]
            if col  # Ignora valores vazios
        ]

        if len(mapped_columns) != len(set(mapped_columns)):
            errors.append(
                "Não é permitido mapear a mesma coluna para múltiplos campos do contrato."
            )

        is_valid = len(errors) == 0

        # Atualiza flag de validação
        self.contract_validated = is_valid

        return is_valid, errors

    def clean(self):
        """
        Valida o modelo antes de salvar.
        """
        from django.core.exceptions import ValidationError

        # Valida segurança da SQL
        if self.sql:
            self._validate_sql_security(self.sql)

        # Valida contrato semântico (se campos estiverem preenchidos)
        has_contract_fields = any(
            [
                self.metric_date_column,
                self.metric_value_column,
                self.series_key_column,
                self.unit_id_column,
            ]
        )

        if has_contract_fields:
            is_valid, errors = self.validate_semantic_contract()
            if not is_valid:
                raise ValidationError({"__all__": errors})

    def save(self, *args, **kwargs):
        """
        Override save para executar validação e extração de metadados.

        FLUXO (Nova Arquitetura):
        1. Valida segurança da SQL
        2. Se a SQL mudou, extrai metadados COMPLETOS das colunas
        3. Classifica colunas automaticamente (datetime, measure, dimension)
        4. Salva o modelo com metadados preenchidos
        """
        # Verifica se é uma criação ou atualização
        is_new = self.pk is None

        # Se é update, verifica se a SQL mudou
        sql_changed = False
        if not is_new:
            try:
                old_instance = DataSource.objects.get(pk=self.pk)
                sql_changed = old_instance.sql != self.sql
            except DataSource.DoesNotExist:
                pass

        # Valida segurança (sempre)
        self.clean()

        # Se a SQL mudou ou é novo, extrai metadados COMPLETOS das colunas
        # Usa o novo método que classifica tipos semânticos
        # Não bloqueia o save se falhar (permite salvar SQL em desenvolvimento)
        if (is_new or sql_changed) and self.sql and self.connection:
            # Tenta o novo método de extração completa
            success, message, metadata = self.extract_columns_metadata()
            if not success:
                # Fallback: tenta método antigo se o novo falhar
                self.validate_and_extract_columns()

        super().save(*args, **kwargs)

    def generate_normalized_query(
        self,
        date_start=None,
        date_end=None,
        series_filter=None,
        unit_id_filter=None,
        additional_filters=None,
    ):
        """
        Gera a query SQL normalizada com aliases padronizados.

        Encapsula a query original como CTE e aplica:
        - Aliases padronizados (metric_date, metric_value, series_key, unit_id)
        - Filtros dinâmicos no WHERE (sempre no SQL, nunca em memória)
        - Ordenação por metric_date

        Args:
            date_start (str/date): Data inicial para filtro (opcional)
            date_end (str/date): Data final para filtro (opcional)
            series_filter (list): Lista de valores para filtrar series_key (opcional)
            unit_id_filter (list): Lista de IDs de unidade para filtrar (opcional)
            additional_filters (str): Cláusula WHERE adicional customizada (opcional)

        Returns:
            str: Query SQL normalizada

        Raises:
            ValueError: Se o contrato semântico não estiver validado
        """
        if not self.contract_validated:
            raise ValueError(
                "Contrato semântico não validado. Configure os campos obrigatórios primeiro."
            )

        # Monta SELECT com aliases padronizados
        select_parts = [
            f"{self.metric_date_column} AS metric_date",
            f"{self.metric_value_column} AS metric_value",
        ]

        if self.series_key_column:
            select_parts.append(f"{self.series_key_column} AS series_key")
        else:
            # Se não tem series_key, usa NULL
            select_parts.append("NULL AS series_key")

        if self.unit_id_column:
            select_parts.append(f"{self.unit_id_column} AS unit_id")
        else:
            # Se não tem unit_id, usa NULL
            select_parts.append("NULL AS unit_id")

        # Monta a query usando CTE
        query_parts = []
        query_parts.append("WITH __source_data AS (")
        query_parts.append(f"  {self.sql}")
        query_parts.append(")")
        query_parts.append("SELECT")
        query_parts.append("  " + ",\n  ".join(select_parts))
        query_parts.append("FROM __source_data")

        # Monta filtros WHERE
        where_clauses = []

        if date_start:
            where_clauses.append(f"metric_date >= '{date_start}'")

        if date_end:
            where_clauses.append(f"metric_date <= '{date_end}'")

        if series_filter and self.series_key_column:
            # Escapa valores para evitar SQL injection
            escaped_values = [str(v).replace("'", "''") for v in series_filter]
            values_str = "', '".join(escaped_values)
            where_clauses.append(f"series_key IN ('{values_str}')")

        if unit_id_filter and self.unit_id_column:
            # Escapa valores para evitar SQL injection
            escaped_values = [str(v).replace("'", "''") for v in unit_id_filter]
            values_str = "', '".join(escaped_values)
            where_clauses.append(f"unit_id IN ('{values_str}')")

        if additional_filters:
            where_clauses.append(f"({additional_filters})")

        if where_clauses:
            query_parts.append("WHERE")
            query_parts.append("  " + "\n  AND ".join(where_clauses))

        # Ordena por data
        query_parts.append("ORDER BY metric_date")

        return "\n".join(query_parts)

    def execute_normalized_query(
        self,
        date_start=None,
        date_end=None,
        series_filter=None,
        unit_id_filter=None,
        additional_filters=None,
        timeout=30,
    ):
        """
        Executa a query normalizada com filtros aplicados no SQL.

        Args:
            date_start (str/date): Data inicial para filtro (opcional)
            date_end (str/date): Data final para filtro (opcional)
            series_filter (list): Lista de valores para filtrar series_key (opcional)
            unit_id_filter (list): Lista de IDs de unidade para filtrar (opcional)
            additional_filters (str): Cláusula WHERE adicional customizada (opcional)
            timeout (int): Timeout em segundos (padrão: 30)

        Returns:
            tuple: (success: bool, data: list|str)
                   Se sucesso, data é lista de dicionários com colunas padronizadas.
                   Se erro, data é a mensagem de erro.
        """
        import psycopg2
        import psycopg2.extras

        if not self.ativo or not self.connection.ativo:
            return False, "DataSource ou Connection está inativo"

        try:
            # Gera a query normalizada
            normalized_query = self.generate_normalized_query(
                date_start=date_start,
                date_end=date_end,
                series_filter=series_filter,
                unit_id_filter=unit_id_filter,
                additional_filters=additional_filters,
            )

            # Conecta ao banco
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

            # Executa a query normalizada
            cursor.execute(normalized_query)

            # Busca todos os resultados
            results = cursor.fetchall()

            # Converte RealDictRow para dict comum
            data = [dict(row) for row in results]

            cursor.close()
            conn.close()

            return True, data

        except ValueError as e:
            # Erro de contrato não validado
            return False, str(e)

        except psycopg2.OperationalError as e:
            return False, f"Erro de conexão: {str(e)}"

        except psycopg2.ProgrammingError as e:
            return False, f"Erro na query SQL: {str(e)}"

        except Exception as e:
            # Captura timeout e outros erros
            error_str = str(e)
            if "timeout" in error_str.lower() or "canceled" in error_str.lower():
                return False, f"Query cancelada (timeout de {timeout}s excedido)"
            return False, f"Erro ao executar query: {error_str}"

    def execute_query(self, params=None):
        """
        Executa a query SQL ORIGINAL (não normalizada) usando a conexão configurada.

        NOTA: Para uso em dashboards, prefira execute_normalized_query().
        Este método é mantido para compatibilidade e debug.

        Args:
            params (dict): Parâmetros para a query (opcional)

        Returns:
            tuple: (sucesso: bool, dados: list|str)
                   Se sucesso, dados é uma lista de dicionários.
                   Se erro, dados é a mensagem de erro.
        """
        import psycopg2
        import psycopg2.extras

        if not self.ativo or not self.connection.ativo:
            return False, "DataSource ou Connection está inativo"

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

            # Executa a query com parâmetros se fornecidos
            if params:
                cursor.execute(self.sql, params)
            else:
                cursor.execute(self.sql)

            # Busca todos os resultados
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


class TemplateComponent(models.Model):
    """
    Componente individual dentro de um template de dashboard.

    Cada componente representa um elemento visual (gráfico, tabela, etc)
    com suas configurações e fonte de dados específicas.

    LEGADO: Mantido para compatibilidade. Novos dashboards devem usar DashboardBlock.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        DashboardTemplate,
        on_delete=models.CASCADE,
        related_name="componentes",
        verbose_name="Template",
    )
    component_type = models.ForeignKey(
        ComponentType,
        on_delete=models.PROTECT,
        related_name="componentes",
        verbose_name="Tipo de Componente",
    )
    datasource = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="componentes",
        verbose_name="Fonte de Dados",
    )
    nome = models.CharField(
        max_length=100,
        verbose_name="Nome",
        help_text="Nome identificador do componente no template",
    )
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configurações",
        help_text="Configurações específicas do componente (cores, labels, eixos, etc)",
    )
    ordem = models.IntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Ordem de exibição do componente no dashboard",
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Componente do Template"
        verbose_name_plural = "Componentes dos Templates"
        ordering = ["template", "ordem", "nome"]
        unique_together = ["template", "nome"]

    def __str__(self):
        return f"{self.template.nome} - {self.nome} ({self.component_type.nome})"


class DashboardBlock(models.Model):
    """
    Bloco de dashboard - unidade renderizável de um gráfico/componente.

    ARQUITETURA SEMÂNTICA (Semantic Layer):
    =======================================
    Este modelo segue o padrão de "separation of concerns" usado em
    ferramentas como Looker, Metabase e Lightdash:

    1. DataSource = DATASET BASE (tabela ou query reutilizável)
       - Define os dados brutos disponíveis
       - Extrai metadata automática (tipos, semânticas)
       - Não contém agregações pré-definidas

    2. DashboardBlock = INTENÇÃO ANALÍTICA (o que visualizar)
       - Define COMO agregar os dados do DataSource
       - Especifica campos, agregações, granularidades, filtros
       - QueryBuilder gera SQL dinamicamente

    3. Benefícios:
       - Um DataSource serve múltiplos blocos
       - Mudança no DataSource propaga automaticamente
       - Sem duplicação de queries SQL
       - Contratos semânticos garantem consistência

    CONFIGURAÇÃO:
    ========================
    - x_axis_field: Campo do eixo X (dimensão ou datetime)
    - x_axis_granularity: Granularidade temporal (hour/day/week/month/quarter/year)
    - series_field: Campo de agrupamento/legenda (opcional)
    - y_axis_aggregations: Lista de agregações [{field, aggregation, label, axis}]
      * Agregações disponíveis: sum, avg, count, count_distinct, min, max, median

    O QueryBuilder gera dinamicamente o SQL baseado nessas configurações.
    """

    # Tipos de gráficos suportados
    CHART_TYPE_BAR = "bar"
    CHART_TYPE_LINE = "line"
    CHART_TYPE_PIE = "pie"
    CHART_TYPE_AREA = "area"
    CHART_TYPE_TABLE = "table"
    CHART_TYPE_METRIC = "metric"

    CHART_TYPE_CHOICES = [
        (CHART_TYPE_BAR, "Gráfico de Barras"),
        (CHART_TYPE_LINE, "Gráfico de Linhas"),
        (CHART_TYPE_PIE, "Gráfico de Pizza"),
        (CHART_TYPE_AREA, "Gráfico de Área"),
        (CHART_TYPE_TABLE, "Tabela"),
        (CHART_TYPE_METRIC, "Métrica/KPI"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relacionamentos
    template = models.ForeignKey(
        DashboardTemplate,
        on_delete=models.CASCADE,
        related_name="blocks",
        verbose_name="Template",
        help_text="Template de dashboard ao qual este bloco pertence",
    )

    datasource = models.ForeignKey(
        DataSource,
        on_delete=models.PROTECT,
        related_name="blocks",
        verbose_name="Fonte de Dados",
        help_text="DataSource (query SQL) que alimenta este bloco",
    )

    # Identificação e ordenação
    title = models.CharField(
        max_length=200,
        verbose_name="Título",
        help_text="Título exibido no bloco (ex: 'Vendas por dia', 'Top 10 produtos')",
    )

    order = models.IntegerField(
        default=0,
        verbose_name="Ordem",
        help_text="Ordem de exibição do bloco no dashboard (menor número = primeiro)",
    )

    # Tipo de visualização
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPE_CHOICES,
        default=CHART_TYPE_BAR,
        verbose_name="Tipo de Gráfico",
        help_text="Tipo de visualização do bloco",
    )

    # ========================================================================
    # SEMANTIC LAYER - CONFIGURAÇÃO DE EIXOS
    # ========================================================================

    x_axis_field = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Campo do Eixo X",
        help_text="Nome do campo do DataSource para o eixo X (ex: 'data_venda', 'produto', 'mes')",
    )

    x_axis_granularity = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Granularidade do Eixo X",
        help_text="""
        (OPCIONAL) Se x_axis_field for DATETIME, especifica a granularidade temporal:
        - hour: agrupa por hora
        - day: agrupa por dia
        - week: agrupa por semana
        - month: agrupa por mês
        - quarter: agrupa por trimestre
        - year: agrupa por ano
        
        Se não especificado, usa o valor bruto do campo.
        """,
    )

    series_field = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Campo de Série/Legenda",
        help_text="""
        (OPCIONAL) Campo do DataSource para agrupar séries/legendas (ex: 'unidade', 'produto', 'vendedor').
        Gera uma série distinta para cada valor único do campo.
        """,
    )

    y_axis_aggregations = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Agregações do Eixo Y",
        help_text="""
        Lista de agregações analíticas. Formato:
        [
          {
            "field": "valor_venda",
            "aggregation": "sum",
            "label": "Total de Vendas",
            "axis": "y1"
          },
          {
            "field": "valor_venda",
            "aggregation": "avg",
            "label": "Ticket Médio",
            "axis": "y2"
          }
        ]
        
        Agregações disponíveis:
        - sum: soma dos valores
        - avg: média dos valores
        - count: contagem de registros
        - count_distinct: contagem de valores únicos
        - min: valor mínimo
        - max: valor máximo
        - median: mediana dos valores
        
        O QueryBuilder gera SQL dinamicamente baseado nessas configurações.
        """,
    )

    # Layout
    col_span = models.IntegerField(
        default=6,
        verbose_name="Largura (colunas)",
        help_text="Largura do bloco em colunas (1-12). Grid padrão: 12 colunas",
    )

    row_span = models.IntegerField(
        default=1,
        verbose_name="Altura (linhas)",
        help_text="Altura do bloco em unidades de linha",
    )

    # Configurações adicionais (opcional)
    config = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Configurações Extras",
        help_text="Configurações adicionais (cores, legendas, tooltips, etc). Formato JSON livre",
    )

    # Status
    ativo = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Se False, o bloco não será exibido",
    )

    # Timestamps
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Bloco de Dashboard"
        verbose_name_plural = "Blocos de Dashboard"
        ordering = ["template", "order", "title"]
        indexes = [
            models.Index(fields=["template", "order"]),
            models.Index(fields=["template", "ativo"]),
        ]

    def __str__(self):
        return f"{self.template.nome} - {self.title} ({self.get_chart_type_display()})"

    def clean(self):
        """
        Valida a configuração do bloco.
        """
        from django.core.exceptions import ValidationError

        errors = {}

        # Valida col_span
        if self.col_span and not (1 <= self.col_span <= 12):
            errors["col_span"] = "Largura deve estar entre 1 e 12 colunas"

        # Valida row_span
        if self.row_span and self.row_span < 1:
            errors["row_span"] = "Altura deve ser no mínimo 1"

        # Valida y_axis_aggregations se estiver preenchido
        if (
            hasattr(self, "y_axis_aggregations")
            and self.y_axis_aggregations is not None
            and len(self.y_axis_aggregations) > 0
        ):
            if not isinstance(self.y_axis_aggregations, list):
                errors["y_axis_aggregations"] = "Deve ser uma lista"
            else:
                # Valida estrutura de cada agregação
                for idx, agg in enumerate(self.y_axis_aggregations):
                    if not isinstance(agg, dict):
                        errors["y_axis_aggregations"] = (
                            f"Item {idx} deve ser um objeto JSON"
                        )
                        break

                    required_keys = ["field", "aggregation", "label", "axis"]
                    missing_keys = [key for key in required_keys if key not in agg]

                    if missing_keys:
                        errors["y_axis_aggregations"] = (
                            f"Item {idx} está faltando as chaves: {', '.join(missing_keys)}"
                        )
                        break

        if errors:
            raise ValidationError(errors)

    # ========================================================================
    # SEMANTIC LAYER METHODS
    # ========================================================================

    def get_analytical_query_params(self, applied_filters=None):
        """
        Converte a configuração do bloco para parâmetros do execute_analytical_query().

        Args:
            applied_filters: Filtros aplicados via query params (opcional)
                            {field: {operator: value}}

        Returns:
            dict: Parâmetros para execute_analytical_query()
        """
        # Monta lista de métricas
        y_axis_metrics = []
        for agg_config in self.y_axis_aggregations:
            field = agg_config.get("field")
            aggregation = agg_config.get("aggregation", "sum")
            label = agg_config.get("label", field)

            y_axis_metrics.append(
                {
                    "field": field,
                    "aggregation": aggregation,
                    "label": label,
                }
            )

        params = {
            "x_axis_field": self.x_axis_field,
            "x_axis_granularity": (
                self.x_axis_granularity if self.x_axis_granularity else None
            ),
            "y_axis_metrics": y_axis_metrics,
            "series_field": self.series_field if self.series_field else None,
            "filters": {},
            "order_by": "metric_date",
            "limit": 1000,
        }

        # Filtros SQL (se configurado em config)
        if self.config.get("filter_sql"):
            params["filters"]["where_clause"] = self.config["filter_sql"]

        # Adiciona filtros dinâmicos aplicados
        if applied_filters:
            params["filters"]["dynamic_filters"] = applied_filters

        return params

    def get_generated_sql(self):
        """
        Retorna a query SQL gerada pelo QueryBuilder (para debug/visualização).

        Returns:
            str: Query SQL formatada
        """
        if not self.y_axis_aggregations or len(self.y_axis_aggregations) == 0:
            return (
                "-- Configure pelo menos uma agregação no campo 'y_axis_aggregations'."
            )

        if (
            not self.datasource.columns_metadata
            or len(self.datasource.columns_metadata) == 0
        ):
            return "-- DataSource não possui metadados. Re-salve o DataSource para extrair metadados."

        try:
            # Obtém parâmetros analíticos
            params = self.get_analytical_query_params()

            # Gera a query SQL usando build_analytical_query
            sql_query, sql_params = self.datasource.build_analytical_query(**params)

            # Formata com disclaimer
            return (
                "-- QUERY GERADA PELA SEMANTIC LAYER\n"
                "-- Esta query é gerada dinamicamente baseada na configuração do bloco\n"
                "-- IMPORTANTE: Salve o bloco para atualizar esta visualização\n\n"
                f"{sql_query}"
            )
        except Exception as e:
            return f"-- Erro ao gerar query: {str(e)}"

    def execute_query(self, applied_filters=None):
        """
        Executa a query usando a Semantic Layer (QueryBuilder).

        Args:
            applied_filters: Filtros aplicados via query params (opcional)

        Returns:
            tuple: (success: bool, data: list|str)
                   Se sucesso, data é lista de dicionários com os dados.
                   Se erro, data é a mensagem de erro.

        Raises:
            ValueError: Se configuração estiver inválida
        """
        if not self.y_axis_aggregations or len(self.y_axis_aggregations) == 0:
            return (
                False,
                "Configure pelo menos uma agregação no campo 'y_axis_aggregations'.",
            )

        if (
            not self.datasource.columns_metadata
            or len(self.datasource.columns_metadata) == 0
        ):
            return (
                False,
                "DataSource não possui metadados. Execute extract_columns_metadata() no DataSource.",
            )

        # Obtém parâmetros analíticos com filtros aplicados
        params = self.get_analytical_query_params(applied_filters=applied_filters)

        # Executa query através do DataSource
        return self.datasource.execute_analytical_query(**params)

    def get_data(self, applied_filters=None):
        """
        Método principal para obter dados do bloco.

        Executa a query usando Semantic Layer (QueryBuilder) e retorna
        os dados prontos para o frontend.

        Args:
            applied_filters: Filtros aplicados via query params (opcional)

        Returns:
            tuple: (success: bool, data: dict|str)
                   Se success=True, data é dict normalizado {"x": [...], "series": [...]}
                   Se success=False, data é mensagem de erro (str)
        """
        success, raw_data = self.execute_query(applied_filters=applied_filters)

        if not success:
            return False, raw_data

        # Normaliza dados para formato do frontend
        normalized_data = self.normalize_query_results(raw_data)
        return True, normalized_data

    def format_x_axis_value(self, value):
        """
        Formata o valor do eixo X baseado na granularidade configurada.

        Args:
            value: Valor bruto do eixo X (geralmente datetime ou string)

        Returns:
            str: Valor formatado para exibição
        """
        from datetime import datetime

        # Se não há granularidade ou valor vazio, retorna string direta
        if not self.x_axis_granularity or not value:
            return str(value)

        # Tenta parsear como datetime
        try:
            if isinstance(value, str):
                # Tenta vários formatos comuns
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S.%f"]:
                    try:
                        dt = datetime.strptime(value, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    # Se nenhum formato funcionou, retorna string original
                    return str(value)
            elif hasattr(value, "strftime"):
                dt = value
            else:
                return str(value)
        except Exception:
            return str(value)

        # Formata baseado na granularidade
        granularity = self.x_axis_granularity.lower()

        if granularity == "hour":
            return dt.strftime("%d/%m/%Y %H:00")
        elif granularity == "day":
            return dt.strftime("%d/%m/%Y")
        elif granularity == "week":
            week_num = dt.isocalendar()[1]
            return f"Semana {week_num}, {dt.year}"
        elif granularity == "month":
            return dt.strftime("%m/%Y")
        elif granularity == "quarter":
            quarter = (dt.month - 1) // 3 + 1
            return f"Q{quarter}/{dt.year}"
        elif granularity == "year":
            return str(dt.year)
        else:
            return str(value)

    def normalize_query_results(self, query_results):
        """
        Normaliza os resultados da query para o formato esperado pelo frontend.

        Converte de:
        [
            {"metric_date": "2024-01", "series_key": "A", "metric_value_1": 100},
            {"metric_date": "2024-01", "series_key": "B", "metric_value_1": 150},
            {"metric_date": "2024-02", "series_key": "A", "metric_value_1": 120},
        ]

        Para:
        {
            "x": ["2024-01", "2024-02"],
            "series": [
                {
                    "axis": "y1",
                    "label": "A - Total Valor",
                    "values": [100, 120]
                },
                {
                    "axis": "y1",
                    "label": "B - Total Valor",
                    "values": [150, null]
                }
            ]
        }

        Args:
            query_results: Lista de dicionários retornada pela query

        Returns:
            dict: Dados normalizados no formato {"x": [...], "series": [...]}
        """
        if not query_results or len(query_results) == 0:
            return {"x": [], "series": []}

        # QueryBuilder sempre usa 'metric_date' para o eixo X
        x_field = "metric_date"

        # Extrai valores únicos do eixo X e formata baseado na granularidade
        raw_x_values = sorted(list(set(row.get(x_field, "") for row in query_results)))
        x_values = [self.format_x_axis_value(val) for val in raw_x_values]

        # Cria mapeamento de valor bruto -> valor formatado para lookup
        x_value_map = {
            str(raw): formatted for raw, formatted in zip(raw_x_values, x_values)
        }

        # Identifica se há série (QueryBuilder usa 'series_key')
        has_series = "series_key" in query_results[0]

        # Cria estrutura de séries
        series_data = {}

        for row in query_results:
            # Usa valor bruto para lookup interno, mas exibe formatado
            x_val_raw = str(row.get(x_field, ""))
            x_val = x_value_map.get(x_val_raw, x_val_raw)
            series_key = str(row.get("series_key", "")) if has_series else "default"

            if series_key not in series_data:
                series_data[series_key] = {}

            # Adiciona cada métrica do y_axis_aggregations
            # QueryBuilder usa aliases: metric_value_1, metric_value_2, etc.
            for idx, agg_config in enumerate(self.y_axis_aggregations):
                label = agg_config.get("label", agg_config.get("field"))
                axis = agg_config.get("axis", "y1")

                # Alias do QueryBuilder: metric_value_1, metric_value_2, ...
                alias = f"metric_value_{idx + 1}"

                # Chave única da série (combina série + métrica)
                # Se há série e apenas UMA métrica, usa apenas o nome da série para evitar redundância
                # Se há várias métricas, adiciona o label da métrica para diferenciar
                if has_series:
                    if len(self.y_axis_aggregations) == 1:
                        serie_label = series_key  # Ex: "Unidade São Paulo - Centro"
                    else:
                        serie_label = (
                            f"{series_key} - {label}"  # Ex: "Unidade SP - Total"
                        )
                else:
                    serie_label = label

                # Inicializa série se não existir
                if serie_label not in series_data[series_key]:
                    series_data[series_key][serie_label] = {
                        "axis": axis,
                        "label": serie_label,
                        "values_dict": {},
                    }

                # Adiciona valor para este x
                value = row.get(alias)
                series_data[series_key][serie_label]["values_dict"][x_val] = value

        # Converte para formato final
        series_list = []
        for series_key in sorted(series_data.keys()):
            for serie_label, serie_info in series_data[series_key].items():
                # Preenche valores na ordem do eixo X (None para valores faltantes)
                values = [serie_info["values_dict"].get(x_val) for x_val in x_values]

                series_list.append(
                    {
                        "axis": serie_info["axis"],
                        "label": serie_info["label"],
                        "values": values,
                    }
                )

        return {
            "x": x_values,
            "series": series_list,
        }
