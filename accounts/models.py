"""
Models para o app accounts.

Este módulo define o modelo de Profile que estende o usuário Django,
incluindo papéis e relacionamento com unidades.
"""

import uuid

from django.contrib.auth.models import User
from django.db import models


class UserRole(models.TextChoices):
    """Papéis disponíveis no sistema."""

    ADMIN_TECNICO = "ADMIN_TECNICO", "Administrador Técnico"
    GERENTE_GERAL = "GERENTE_GERAL", "Gerente Geral"
    GERENTE_UNIDADE = "GERENTE_UNIDADE", "Gerente de Unidade"


class Profile(models.Model):
    """
    Extensão do modelo User do Django.

    Adiciona informações de papel (role) e relacionamento com unidades.
    Um usuário pode estar associado a múltiplas unidades.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile", verbose_name="Usuário"
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.GERENTE_UNIDADE,
        verbose_name="Papel",
    )
    unidades = models.ManyToManyField(
        "core.Unidade", related_name="usuarios", blank=True, verbose_name="Unidades"
    )
    ativo = models.BooleanField(default=True, verbose_name="Ativo")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Perfil"
        verbose_name_plural = "Perfis"
        ordering = ["user__username"]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def is_admin_tecnico(self):
        """Verifica se o usuário é admin técnico."""
        return self.role == UserRole.ADMIN_TECNICO

    def is_gerente_geral(self):
        """Verifica se o usuário é gerente geral."""
        return self.role == UserRole.GERENTE_GERAL

    def is_gerente_unidade(self):
        """Verifica se o usuário é gerente de unidade."""
        return self.role == UserRole.GERENTE_UNIDADE

    def pode_acessar_unidade(self, unidade):
        """
        Verifica se o usuário pode acessar uma unidade específica.

        Admin técnico e gerente geral têm acesso a todas as unidades.
        Gerente de unidade só tem acesso às suas unidades associadas.
        """
        if self.is_admin_tecnico() or self.is_gerente_geral():
            return True
        return self.unidades.filter(id=unidade.id).exists()

    def get_unidades_permitidas(self):
        """
        Retorna todas as unidades que o usuário pode acessar.

        Admin técnico e gerente geral: todas as unidades ativas.
        Gerente de unidade: apenas suas unidades associadas.
        """
        from core.models import Unidade

        if self.is_admin_tecnico() or self.is_gerente_geral():
            return Unidade.objects.filter(ativa=True)
        return self.unidades.filter(ativa=True)
        return self.unidades.filter(ativa=True)
