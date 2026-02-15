"""
Models para o app dashboards.

Este módulo define os modelos relacionados a dashboards:
- DashboardTemplate: templates globais de dashboards
- DashboardInstance: instâncias de dashboards por unidade
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


class DataSource(models.Model):
    """
    Fonte de dados (query SQL) para alimentar dashboards.

    Armazena queries SQL que são executadas para buscar dados.
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
