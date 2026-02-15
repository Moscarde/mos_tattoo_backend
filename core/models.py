"""
Models para o app core.

Este módulo define os modelos centrais da aplicação,
como Unidade (estabelecimentos/lojas/filiais).
"""
import uuid
from django.db import models


class Unidade(models.Model):
    """
    Representa uma unidade de negócio (loja, filial, estabelecimento).
    
    Cada unidade pode ter dashboards e usuários associados.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nome = models.CharField(max_length=100, verbose_name='Nome')
    codigo = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Código',
        help_text='Código único da unidade (ex: UNI001)'
    )
    ativa = models.BooleanField(default=True, verbose_name='Ativa')
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name='Atualizado em')

    class Meta:
        verbose_name = 'Unidade'
        verbose_name_plural = 'Unidades'
        ordering = ['nome']

    def __str__(self):
        return f'{self.codigo} - {self.nome}'
