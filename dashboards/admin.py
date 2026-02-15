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

    list_display = [
        "template",
        "unidade",
        "filtro_preview",
        "ativo",
        "num_users",
        "criado_em",
        "preview_data_link",
    ]
    list_filter = ["ativo", "criado_em", "template", "unidade"]
    search_fields = ["template__nome", "unidade__nome", "unidade__codigo", "filtro_sql"]
    filter_horizontal = ["usuarios_com_acesso"]
    readonly_fields = ["id", "criado_em", "atualizado_em", "preview_resultados"]

    fieldsets = (
        ("Configuração", {"fields": ("template", "unidade", "ativo")}),
        (
            "Filtro SQL",
            {
                "fields": ("filtro_sql",),
                "description": "Cláusula WHERE customizada para filtrar os dados. Exemplo: unidade_codigo = 'SP-01' OR status = 'ativo'. Deixe vazio para não aplicar filtro.",
            },
        ),
        (
            "Controle de Acesso",
            {
                "fields": ("usuarios_com_acesso",),
                "description": "Usuários específicos que podem acessar este dashboard. Deixe vazio para permitir todos os usuários da unidade.",
            },
        ),
        (
            "Desenvolvimento - Preview dos Dados",
            {
                "fields": ("preview_resultados",),
                "classes": ("collapse",),
                "description": "Visualize os dados retornados pelas queries desta instância.",
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

    def filtro_preview(self, obj):
        """Mostra preview do filtro SQL."""
        if obj.filtro_sql:
            return (
                obj.filtro_sql[:50] + "..."
                if len(obj.filtro_sql) > 50
                else obj.filtro_sql
            )
        return "-"

    filtro_preview.short_description = "Filtro SQL"

    def preview_data_link(self, obj):
        """Link para visualizar os dados."""
        return format_html(
            '<a href="#" onclick="document.getElementById(\'preview_resultados\').scrollIntoView(); return false;">🔍 Ver Dados</a>'
        )

    preview_data_link.short_description = "Preview"

    def preview_resultados(self, obj):
        """Executa e mostra os resultados das queries."""
        import json

        from dashboards.views import DashboardInstanceViewSet

        if not obj.id:
            return "Salve a instância primeiro para visualizar os resultados."

        try:
            # Simula a execução da view
            viewset = DashboardInstanceViewSet()
            schema = obj.template.schema
            datasources_data = viewset._execute_datasources(schema, obj)

            # Formata os resultados
            html_parts = []
            html_parts.append(
                '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
            )

            # Informações gerais
            html_parts.append(
                '<h3 style="margin-top: 0;">📊 Resultados da Instância</h3>'
            )
            html_parts.append(f"<p><strong>Template:</strong> {obj.template.nome}</p>")
            html_parts.append(
                f"<p><strong>Unidade:</strong> {obj.unidade.nome} ({obj.unidade.codigo})</p>"
            )
            html_parts.append(
                f'<p><strong>Filtro SQL:</strong> <code>{obj.filtro_sql or "Nenhum"}</code></p>'
            )
            html_parts.append("<hr>")

            # Dados de cada datasource
            if datasources_data:
                for datasource_name, data in datasources_data.items():
                    html_parts.append(f"<h4>📁 DataSource: {datasource_name}</h4>")

                    if isinstance(data, dict) and data.get("error"):
                        html_parts.append(
                            f'<div style="color: red; background: #ffebee; padding: 10px; border-radius: 3px; margin: 10px 0;">'
                        )
                        html_parts.append(f'<strong>❌ Erro:</strong> {data["error"]}')
                        html_parts.append("</div>")
                    else:
                        # Mostra quantidade de registros
                        num_records = len(data) if isinstance(data, list) else 0
                        html_parts.append(
                            f'<p style="color: green;"><strong>✅ {num_records} registro(s) encontrado(s)</strong></p>'
                        )

                        # Mostra preview dos dados (primeiros 5 registros)
                        if num_records > 0:
                            preview_data = data[:5]
                            formatted_json = json.dumps(
                                preview_data, indent=2, ensure_ascii=False
                            )
                            html_parts.append("<details open>")
                            html_parts.append(
                                '<summary style="cursor: pointer; font-weight: bold; margin: 10px 0;">Dados (primeiros 5 registros):</summary>'
                            )
                            html_parts.append(
                                f'<pre style="background: white; padding: 10px; border: 1px solid #ddd; border-radius: 3px; overflow: auto; max-height: 400px;">{formatted_json}</pre>'
                            )
                            html_parts.append("</details>")

                            if num_records > 5:
                                html_parts.append(
                                    f'<p style="color: #666; font-size: 12px;">... e mais {num_records - 5} registro(s)</p>'
                                )

                    html_parts.append("<hr>")
            else:
                html_parts.append(
                    '<p style="color: orange;">⚠️ Nenhum DataSource encontrado no schema do template.</p>'
                )

            html_parts.append("</div>")

            return format_html("".join(html_parts))

        except Exception as e:
            return format_html(
                '<div style="color: red; background: #ffebee; padding: 15px; border-radius: 5px;">'
                "<strong>❌ Erro ao executar queries:</strong><br><pre>{}</pre>"
                "</div>",
                str(e),
            )

    preview_resultados.short_description = "Preview dos Dados"


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
            self.message_user(request, f"Erro ao salvar: {str(e)}", level="error")
