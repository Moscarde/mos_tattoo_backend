"""
Admin configuration for dashboards app.
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import DashboardTemplate, DashboardInstance, DataSource


@admin.register(DashboardTemplate)
class DashboardTemplateAdmin(admin.ModelAdmin):
    """Admin para o modelo DashboardTemplate."""
    list_display = ['nome', 'ativo', 'num_instances', 'criado_em']
    list_filter = ['ativo', 'criado_em']
    search_fields = ['nome', 'descricao']
    readonly_fields = ['id', 'criado_em', 'atualizado_em', 'preview_schema']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativo')
        }),
        ('Estrutura do Dashboard', {
            'fields': ('schema', 'preview_schema'),
            'description': 'Defina a estrutura JSON do dashboard. Exemplo: {"blocks": [{"type": "chart", "dataSource": "nome_datasource"}]}'
        }),
        ('Metadados', {
            'fields': ('id', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    def num_instances(self, obj):
        """Retorna o número de instâncias deste template."""
        return obj.instances.count()
    num_instances.short_description = 'Instâncias'
    
    def preview_schema(self, obj):
        """Mostra preview formatado do schema JSON."""
        if obj.schema:
            import json
            try:
                formatted = json.dumps(obj.schema, indent=2, ensure_ascii=False)
                return format_html('<pre style="max-height: 300px; overflow: auto;">{}</pre>', formatted)
            except:
                return obj.schema
        return '-'
    preview_schema.short_description = 'Preview do Schema'


@admin.register(DashboardInstance)
class DashboardInstanceAdmin(admin.ModelAdmin):
    """Admin para o modelo DashboardInstance."""
    list_display = ['template', 'unidade', 'ativo', 'num_users', 'criado_em']
    list_filter = ['ativo', 'criado_em', 'template', 'unidade']
    search_fields = ['template__nome', 'unidade__nome', 'unidade__codigo']
    filter_horizontal = ['usuarios_com_acesso']
    readonly_fields = ['id', 'criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Configuração', {
            'fields': ('template', 'unidade', 'ativo')
        }),
        ('Controle de Acesso', {
            'fields': ('usuarios_com_acesso',),
            'description': 'Usuários específicos que podem acessar este dashboard. Deixe vazio para permitir todos os usuários da unidade.'
        }),
        ('Metadados', {
            'fields': ('id', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    def num_users(self, obj):
        """Retorna o número de usuários com acesso."""
        count = obj.usuarios_com_acesso.count()
        return count if count > 0 else 'Todos'
    num_users.short_description = 'Usuários'


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    """Admin para o modelo DataSource."""
    list_display = ['nome', 'ativo', 'criado_em']
    list_filter = ['ativo', 'criado_em']
    search_fields = ['nome', 'descricao']
    readonly_fields = ['id', 'criado_em', 'atualizado_em']
    
    fieldsets = (
        ('Informações Básicas', {
            'fields': ('nome', 'descricao', 'ativo')
        }),
        ('Query SQL', {
            'fields': ('sql',),
            'description': format_html(
                '<strong>⚠️ IMPORTANTE:</strong><br/>'
                '• Apenas queries SELECT são permitidas<br/>'
                '• Use %(parametro)s para parâmetros dinâmicos<br/>'
                '• Exemplo: SELECT * FROM fat_vendas WHERE unidade_id = %(unidade_id)s<br/>'
                '• Tabelas disponíveis: fat_* (do banco externo de BI)'
            )
        }),
        ('Metadados', {
            'fields': ('id', 'criado_em', 'atualizado_em'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Override para exibir mensagem de validação."""
        try:
            super().save_model(request, obj, form, change)
            self.message_user(request, 'DataSource salvo com sucesso. Lembre-se de testar a query!', level='success')
        except Exception as e:
            self.message_user(request, f'Erro ao salvar: {str(e)}', level='error')
