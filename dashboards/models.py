"""
Models para o app dashboards.

Este módulo define os modelos relacionados a dashboards:
- DashboardTemplate: templates globais de dashboards
- DashboardInstance: instâncias de dashboards por unidade
- Connection: conexões a bancos de dados externos
- DataSource: fontes de dados (queries SQL) para os dashboards
"""

import uuid

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
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Template de Dashboard"
        verbose_name_plural = "Templates de Dashboards"
        ordering = ["-criado_em"]

    def __str__(self):
        return self.nome


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
    Fonte de dados (query SQL) para alimentar dashboards.

    Armazena queries SQL que são executadas para buscar dados de uma conexão específica.
    IMPORTANTE: Apenas SELECT é permitido por questões de segurança.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome",
        help_text="Nome único para identificar a fonte de dados",
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
        verbose_name="Query SQL",
        help_text="Query SQL (apenas SELECT). Use %(param)s para parâmetros.",
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

    def clean(self):
        """
        Valida que a query SQL é apenas SELECT.
        """
        from django.core.exceptions import ValidationError

        if self.sql:
            # Remove espaços e converte para minúsculo
            sql_clean = self.sql.strip().lower()

            # Verifica se começa com SELECT ou WITH (para CTEs)
            if not (sql_clean.startswith("select") or sql_clean.startswith("with")):
                raise ValidationError(
                    "A query SQL deve começar com SELECT ou WITH (Common Table Expression). "
                    "Apenas consultas de leitura são permitidas."
                )

            # Palavras-chave proibidas
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
            ]

            for keyword in forbidden_keywords:
                if keyword in sql_clean:
                    raise ValidationError(
                        f'A query SQL não pode conter a palavra-chave "{keyword.upper()}". '
                        "Apenas consultas de leitura (SELECT) são permitidas."
                    )

    def save(self, *args, **kwargs):
        """Override save para executar validação."""
        self.clean()
        super().save(*args, **kwargs)

    def execute_query(self, params=None):
        """
        Executa a query SQL usando a conexão configurada.

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

    Este é o modelo CENTRAL da nova arquitetura de dashboards.

    Cada bloco define:
    - Tipo de gráfico (bar, line, pie, area)
    - Eixos (x_axis_field, y_axis_fields)
    - Layout (col_span, row_span)
    - Fonte de dados (DataSource)

    O Django Admin é a única fonte de verdade para a configuração.
    O backend normaliza os dados e o frontend apenas renderiza.
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

    # Configuração de eixos
    x_axis_field = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Campo do Eixo X",
        help_text="Nome do campo da query que representa o eixo X (ex: 'data', 'produto', 'mes')",
    )

    series_field = models.CharField(
        max_length=100,
        blank=True,
        default="",
        verbose_name="Campo de Série/Legenda",
        help_text="""(OPCIONAL) Nome do campo da query que define as séries do gráfico (ex: 'nome_unidade', 'produto', 'vendedor').
        Quando configurado, o backend agrupa os dados por este campo, gerando uma série distinta para cada valor único.
        Útil para gráficos de barras com múltiplas séries/legendas.
        Se não configurado, o gráfico terá uma única série.""",
    )

    y_axis_fields = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Campos do Eixo Y",
        help_text="""
        Lista de métricas para o eixo Y. Formato:
        [
          {"field": "total_sales", "label": "Vendas", "axis": "y1"},
          {"field": "avg_ticket", "label": "Ticket Médio", "axis": "y2"}
        ]
        
        - field: nome do campo na query
        - label: rótulo exibido no gráfico
        - axis: y1, y2, etc (para eixos múltiplos)
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
        
        Nota: Os campos x_axis_field e y_axis_fields são opcionais para permitir
        criar blocos no inline e configurá-los depois na página de detalhe.
        """
        from django.core.exceptions import ValidationError

        errors = {}

        # Valida col_span
        if self.col_span and not (1 <= self.col_span <= 12):
            errors["col_span"] = "Largura deve estar entre 1 e 12 colunas"

        # Valida row_span
        if self.row_span and self.row_span < 1:
            errors["row_span"] = "Altura deve ser no mínimo 1"

        # Valida y_axis_fields APENAS se estiver preenchido (não vazio)
        # Permite salvar com lista vazia para configurar depois
        if hasattr(self, 'y_axis_fields') and self.y_axis_fields is not None and len(self.y_axis_fields) > 0:
            if not isinstance(self.y_axis_fields, list):
                errors["y_axis_fields"] = "Deve ser uma lista"
            else:
                # Valida estrutura de cada métrica
                for idx, metric in enumerate(self.y_axis_fields):
                    if not isinstance(metric, dict):
                        errors["y_axis_fields"] = f"Item {idx} deve ser um objeto JSON"
                        break

                    required_keys = ["field", "label", "axis"]
                    missing_keys = [key for key in required_keys if key not in metric]

                    if missing_keys:
                        errors["y_axis_fields"] = (
                            f"Item {idx} está faltando as chaves: {', '.join(missing_keys)}"
                        )
                        break

        if errors:
            raise ValidationError(errors)

    def validate_fields_against_query(self, query_result):
        """
        Valida se os campos configurados existem no resultado da query.

        Args:
            query_result: Lista de dicionários retornados pela query

        Returns:
            tuple: (is_valid: bool, errors: list)
        """
        if not query_result or len(query_result) == 0:
            return True, []  # Query vazia é válida

        errors = []
        available_fields = set(query_result[0].keys())

        # Valida x_axis_field
        if self.x_axis_field not in available_fields:
            errors.append(
                f"Campo do eixo X '{self.x_axis_field}' não encontrado na query. "
                f"Campos disponíveis: {', '.join(sorted(available_fields))}"
            )

        # Valida series_field (se configurado)
        if self.series_field and self.series_field not in available_fields:
            errors.append(
                f"Campo de série/legenda '{self.series_field}' não encontrado na query. "
                f"Campos disponíveis: {', '.join(sorted(available_fields))}"
            )

        # Valida y_axis_fields
        for metric in self.y_axis_fields:
            field = metric.get("field")
            if field and field not in available_fields:
                errors.append(
                    f"Campo da métrica '{field}' ('{metric.get('label')}') não encontrado na query. "
                    f"Campos disponíveis: {', '.join(sorted(available_fields))}"
                )

        return len(errors) == 0, errors

    def normalize_data(self, query_result):
        """
        Normaliza os dados da query para o formato esperado pelo frontend.

        Args:
            query_result: Lista de dicionários retornados pela query

        Returns:
            dict: Dados normalizados no formato:
            {
                "x": [...],
                "series": [
                    {"axis": "y1", "label": "...", "values": [...]},
                    ...
                ]
            }
        """
        if not query_result:
            return {"x": [], "series": []}

        # Valida campos antes de normalizar
        is_valid, errors = self.validate_fields_against_query(query_result)
        if not is_valid:
            raise ValueError(f"Erro de validação: {'; '.join(errors)}")

        # Se series_field estiver configurado, usa lógica de múltiplas séries
        if self.series_field:
            return self._normalize_data_with_series(query_result)
        else:
            return self._normalize_data_single_series(query_result)

    def _normalize_data_single_series(self, query_result):
        """
        Normalização para gráficos de série única (comportamento original).
        
        Args:
            query_result: Lista de dicionários retornados pela query
            
        Returns:
            dict: Dados normalizados
        """
        # Extrai valores do eixo X
        x_values = [row.get(self.x_axis_field) for row in query_result]

        # Extrai valores das séries (eixo Y)
        series = []
        for metric in self.y_axis_fields:
            field = metric.get("field")
            label = metric.get("label", field)
            axis = metric.get("axis", "y1")

            values = [row.get(field) for row in query_result]

            series.append(
                {
                    "axis": axis,
                    "label": label,
                    "values": values,
                }
            )

        return {
            "x": x_values,
            "series": series,
        }

    def _normalize_data_with_series(self, query_result):
        """
        Normalização para gráficos com múltiplas séries/legendas.
        
        Agrupa os dados pelo campo series_field, gerando uma série distinta
        para cada valor único encontrado. Alinha os valores pelo eixo X,
        preenchendo com null quando uma série não possuir dados para um
        determinado valor de X.
        
        Args:
            query_result: Lista de dicionários retornados pela query
            
        Returns:
            dict: Dados normalizados com múltiplas séries
        """
        from collections import defaultdict

        # 1. Extrai todos os valores únicos do eixo X e ordena
        x_values_set = set()
        for row in query_result:
            x_values_set.add(row.get(self.x_axis_field))
        
        x_values = sorted(list(x_values_set))
        x_value_to_index = {val: idx for idx, val in enumerate(x_values)}

        # 2. Extrai todos os valores únicos do campo de série
        series_values_set = set()
        for row in query_result:
            series_values_set.add(row.get(self.series_field))
        
        series_values = sorted(list(series_values_set))

        # 3. Para cada métrica do eixo Y, cria uma série para cada valor de series_field
        all_series = []
        
        for metric in self.y_axis_fields:
            field = metric.get("field")
            base_label = metric.get("label", field)
            axis = metric.get("axis", "y1")

            # Agrupa os dados por series_field
            data_by_series = defaultdict(lambda: defaultdict(lambda: None))
            
            for row in query_result:
                x_val = row.get(self.x_axis_field)
                series_val = row.get(self.series_field)
                y_val = row.get(field)
                
                # Armazena o valor na estrutura agrupada
                data_by_series[series_val][x_val] = y_val

            # 4. Gera uma série para cada valor de series_field
            for series_val in series_values:
                # Monta o array de valores alinhado com x_values
                values = []
                for x_val in x_values:
                    val = data_by_series[series_val].get(x_val)
                    values.append(val)

                # Define o label da série
                # Se houver apenas uma métrica, usa apenas o nome da série
                # Se houver múltiplas métricas, combina: "base_label - series_val"
                if len(self.y_axis_fields) == 1:
                    series_label = str(series_val)
                else:
                    series_label = f"{base_label} - {series_val}"

                all_series.append(
                    {
                        "axis": axis,
                        "label": series_label,
                        "values": values,
                        "series_value": str(series_val),  # Valor original da série para referência
                    }
                )

        return {
            "x": x_values,
            "series": all_series,
        }
