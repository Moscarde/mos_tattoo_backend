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
        verbose_name="Schema",
        help_text="Estrutura JSON do dashboard (blocos, gráficos, etc.)",
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
