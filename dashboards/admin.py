"""
Admin configuration for dashboards app.
"""

from django.contrib import admin
from django.utils.html import format_html

from .models import Connection, DashboardInstance, DashboardTemplate, DataSource


@admin.register(DashboardTemplate)
class DashboardTemplateAdmin(admin.ModelAdmin):
    """Admin para o modelo DashboardTemplate."""

    list_display = ["nome", "ativo", "num_instances", "criado_em"]
    list_filter = ["ativo", "criado_em"]
    search_fields = ["nome", "descricao"]
    readonly_fields = ["id", "criado_em", "atualizado_em", "preview_schema"]

    fieldsets = (
        ("Informações Básicas", {"fields": ("nome", "descricao", "ativo")}),
        (
            "Estrutura do Dashboard",
            {
                "fields": ("schema", "preview_schema"),
                "description": 'Defina a estrutura JSON do dashboard. Exemplo: {"blocks": [{"type": "chart", "dataSource": "nome_datasource"}]}',
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def num_instances(self, obj):
        """Retorna o número de instâncias deste template."""
        return obj.instances.count()

    num_instances.short_description = "Instâncias"

    def preview_schema(self, obj):
        """Mostra preview formatado do schema JSON."""
        if obj.schema:
            import json

            try:
                formatted = json.dumps(obj.schema, indent=2, ensure_ascii=False)
                return format_html(
                    '<pre style="max-height: 300px; overflow: auto;">{}</pre>',
                    formatted,
                )
            except:
                return obj.schema
        return "-"

    preview_schema.short_description = "Preview do Schema"


@admin.register(DashboardInstance)
class DashboardInstanceAdmin(admin.ModelAdmin):
    """Admin para o modelo DashboardInstance."""

    list_display = ["template", "unidade", "ativo", "num_users", "criado_em"]
    list_filter = ["ativo", "criado_em", "template", "unidade"]
    search_fields = ["template__nome", "unidade__nome", "unidade__codigo"]
    filter_horizontal = ["usuarios_com_acesso"]
    readonly_fields = ["id", "criado_em", "atualizado_em"]

    fieldsets = (
        ("Configuração", {"fields": ("template", "unidade", "ativo")}),
        (
            "Controle de Acesso",
            {
                "fields": ("usuarios_com_acesso",),
                "description": "Usuários específicos que podem acessar este dashboard. Deixe vazio para permitir todos os usuários da unidade.",
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def num_users(self, obj):
        """Retorna o número de usuários com acesso."""
        count = obj.usuarios_com_acesso.count()
        return count if count > 0 else "Todos"

    num_users.short_description = "Usuários"


@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    """Admin para o modelo Connection."""

    list_display = ["nome", "host", "porta", "database", "ativo", "status_conexao"]
    list_filter = ["ativo", "criado_em"]
    search_fields = ["nome", "host", "database", "descricao"]
    readonly_fields = ["id", "criado_em", "atualizado_em", "test_connection_result"]

    fieldsets = (
        ("Informações Básicas", {"fields": ("nome", "descricao", "ativo")}),
        (
            "Configuração da Conexão",
            {
                "fields": ("host", "porta", "database", "usuario", "senha"),
                "description": "Configure os dados de acesso ao banco PostgreSQL externo.",
            },
        ),
        (
            "Teste de Conexão",
            {
                "fields": ("test_connection_result",),
                "description": "Clique em 'Salvar e continuar editando' para testar a conexão.",
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def status_conexao(self, obj):
        """Retorna um ícone indicando o status da conexão."""
        if obj.pk:  # Apenas para objetos salvos
            success, msg = obj.test_connection()
            if success:
                return format_html(
                    '<span style="color: green;">✓ Ativo</span>',
                )
            else:
                return format_html(
                    '<span style="color: red;">✗ Erro</span>',
                )
        return "-"

    status_conexao.short_description = "Status"

    def test_connection_result(self, obj):
        """Mostra o resultado do teste de conexão."""
        if obj.pk:  # Apenas para objetos salvos
            success, msg = obj.test_connection()
            color = "green" if success else "red"
            icon = "✓" if success else "✗"
            return format_html(
                '<div style="padding: 10px; background-color: #f0f0f0; border-left: 4px solid {};">'
                '<strong style="color: {};">{} {}</strong>'
                "</div>",
                color,
                color,
                icon,
                msg,
            )
        return format_html(
            '<div style="padding: 10px; background-color: #fff3cd;">'
            "Salve a conexão para testar."
            "</div>"
        )

    test_connection_result.short_description = "Resultado do Teste"

    def get_form(self, request, obj=None, **kwargs):
        """Customiza o form para usar widget de senha."""
        form = super().get_form(request, obj, **kwargs)
        if "senha" in form.base_fields:
            form.base_fields["senha"].widget = admin.widgets.AdminTextInputWidget(
                attrs={"type": "password"}
            )
        return form


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    """Admin para o modelo DataSource."""

    list_display = ["nome", "connection", "ativo", "criado_em"]
    list_filter = ["ativo", "criado_em", "connection"]
    search_fields = ["nome", "descricao"]
    readonly_fields = ["id", "criado_em", "atualizado_em", "preview_query"]

    fieldsets = (
        ("Informações Básicas", {"fields": ("nome", "descricao", "ativo")}),
        (
            "Conexão",
            {
                "fields": ("connection",),
                "description": "Selecione a conexão ao banco de dados que será utilizada.",
            },
        ),
        (
            "Query SQL",
            {
                "fields": ("sql", "preview_query"),
                "description": format_html(
                    "<strong>⚠️ IMPORTANTE:</strong><br/>"
                    "• Apenas queries SELECT são permitidas<br/>"
                    "• Use %(parametro)s para parâmetros dinâmicos<br/>"
                    "• Exemplo: SELECT * FROM vendas WHERE unidade_id = %(unidade_id)s"
                ),
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def preview_query(self, obj):
        """Mostra preview formatado da query SQL."""
        if obj.sql:
            return format_html(
                '<pre style="background-color: #f5f5f5; padding: 10px; border-radius: 4px; max-height: 300px; overflow: auto;">{}</pre>',
                obj.sql,
            )
        return "-"

    preview_query.short_description = "Preview da Query"

    def save_model(self, request, obj, form, change):
        """Override para exibir mensagem de validação."""
        try:
            super().save_model(request, obj, form, change)
            self.message_user(
                request,
                "DataSource salvo com sucesso. Lembre-se de testar a query!",
                level="success",
            )
        except Exception as e:
            self.message_user(request, f"Erro ao salvar: {str(e)}", level="error")
