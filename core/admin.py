"""
Admin configuration for core app.
"""
from django.contrib import admin
from .models import Unidade


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    """Admin para o modelo Unidade."""
    list_display = ['codigo', 'nome', 'ativa', 'criado_em']
    list_filter = ['ativa', 'criado_em']
    search_fields = ['codigo', 'nome']
    readonly_fields = ['id', 'criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'codigo', 'ativa')
        }),
        ('Metadados', {
            'fields': ('id', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
