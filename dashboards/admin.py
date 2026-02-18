"""
Admin configuration for dashboards app.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    ComponentType,
    Connection,
    DashboardBlock,
    DashboardInstance,
    DashboardTemplate,
    DataSource,
    TemplateComponent,
)


@admin.register(ComponentType)
class ComponentTypeAdmin(admin.ModelAdmin):
    """Admin para o modelo ComponentType."""

    list_display = ["nome", "descricao", "ativo", "num_componentes", "criado_em"]
    list_filter = ["ativo", "criado_em"]
    search_fields = ["nome", "descricao"]
    readonly_fields = ["id", "criado_em", "atualizado_em"]

    fieldsets = (
        (
            "Informações",
            {"fields": ("nome", "descricao", "ativo")},
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def num_componentes(self, obj):
        """Retorna o número de componentes deste tipo."""
        return obj.componentes.count()

    num_componentes.short_description = "Componentes"


class TemplateComponentInline(admin.TabularInline):
    """Inline para adicionar componentes ao template - LEGADO."""

    model = TemplateComponent
    extra = 0
    fields = ["nome", "component_type", "datasource", "ordem", "ativo", "edit_config"]
    readonly_fields = ["edit_config"]
    ordering = ["ordem", "nome"]

    def edit_config(self, obj):
        """Link para editar configurações detalhadas."""
        if obj.id:
            return format_html(
                '<a href="/admin/dashboards/templatecomponent/{}/change/" target="_blank">Editar Config</a>',
                obj.id,
            )
        return "-"

    edit_config.short_description = "Config"


class DashboardBlockInline(admin.TabularInline):
    """Inline para adicionar blocos ao template - NOVA ARQUITETURA."""

    model = DashboardBlock
    extra = 1
    fields = [
        "title",
        "order",
        "chart_type",
        "datasource",
        "col_span",
        "row_span",
        "ativo",
        "edit_config",
    ]
    readonly_fields = ["edit_config"]
    ordering = ["order", "title"]

    # Configure os campos na página de edição detalhada do bloco
    exclude = []
    verbose_name = "Bloco de Dashboard"
    verbose_name_plural = (
        "Blocos (Configure os eixos X/Y clicando em 'Editar Eixos' após salvar)"
    )

    def edit_config(self, obj):
        """Link para editar configurações detalhadas."""
        if obj.id:
            return format_html(
                '<a href="/admin/dashboards/dashboardblock/{}/change/" target="_blank" style="font-weight: bold; color: #417690;">⚙️ Configurar Eixos</a>',
                obj.id,
            )
        return format_html('<span style="color: #999;">Salve primeiro</span>')

    edit_config.short_description = "Configuração"


@admin.register(TemplateComponent)
class TemplateComponentAdmin(admin.ModelAdmin):
    """Admin para o modelo TemplateComponent - LEGADO.

    ⚠️ SISTEMA LEGADO - Não use para novos dashboards!
    Este modelo está mantido apenas para compatibilidade com dashboards antigos.

    Para novos dashboards, use: DashboardBlock (Dashboard > Blocos de Dashboard)
    """

    list_display = [
        "nome",
        "template",
        "component_type",
        "datasource",
        "ordem",
        "ativo",
    ]
    list_filter = ["ativo", "component_type", "template"]
    search_fields = ["nome", "template__nome", "datasource__nome"]
    readonly_fields = ["id", "criado_em", "atualizado_em", "preview_config"]

    fieldsets = (
        (
            "Informações Básicas",
            {
                "fields": (
                    "template",
                    "nome",
                    "component_type",
                    "datasource",
                    "ordem",
                    "ativo",
                )
            },
        ),
        (
            "Configurações do Componente",
            {
                "fields": ("config", "preview_config"),
                "description": "Configurações JSON específicas do componente (cores, labels, opções, etc)",
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def preview_config(self, obj):
        """Mostra preview formatado das configurações."""
        if obj.config:
            import json

            try:
                formatted = json.dumps(obj.config, indent=2, ensure_ascii=False)
                # Escapa as chaves para format_html
                formatted = formatted.replace("{", "{{").replace("}", "}}")
                return format_html(
                    '<pre style="max-height: 300px; overflow: auto;">{}</pre>',
                    formatted,
                )
            except:
                return str(obj.config)
        return "-"

    preview_config.short_description = "Preview das Configurações"


@admin.register(DashboardBlock)
class DashboardBlockAdmin(admin.ModelAdmin):
    """
    Admin para o modelo DashboardBlock - NOVA ARQUITETURA.

    Este é o modelo central para criação de dashboards.
    """

    class Media:
        js = ("dashboards/admin/js/dashboard_block_dynamic_fields.js",)

    list_display = [
        "title",
        "template",
        "chart_type",
        "datasource",
        "order",
        "draft_status_badge",
        "layout_info",
        "ativo",
        "test_block",
    ]
    list_filter = ["ativo", "is_draft", "chart_type", "template"]
    search_fields = ["title", "template__nome", "datasource__nome"]
    readonly_fields = [
        "id",
        "criado_em",
        "atualizado_em",
        "preview_y_axis_aggregations",
        "preview_config",
        "test_block_preview",
    ]
    list_editable = ["order", "ativo"]

    fieldsets = (
        (
            "Informações Básicas",
            {
                "fields": (
                    "template",
                    "title",
                    "order",
                    "chart_type",
                    "datasource",
                    "ativo",
                    "is_draft",
                ),
                "description": "Configure as informações básicas do bloco.",
            },
        ),
        (
            "🎯 Configuração Semântica (Semantic Layer)",
            {
                "fields": (
                    "x_axis_field",
                    "x_axis_granularity",
                    "series_field",
                    "series_label",
                    "y_axis_aggregations",
                ),
                "description": format_html(
                    "<div style='background: #d4edda; border-left: 4px solid #28a745; padding: 12px;'>"
                    "<strong>🚀 Semantic Layer - Queries Dinâmicas</strong><br/><br/>"
                    "<strong>⚠️ Importante:</strong> Campos exibidos variam conforme o tipo de gráfico selecionado.<br/><br/>"
                    "<strong>Para Métricas/KPI:</strong> Apenas 'Agregações Y' é necessário (eixo X fica oculto).<br/>"
                    "<strong>Para Bar/Line/Area:</strong> Configure eixo X (categorias ou data) + agregações Y.<br/>"
                    "<strong>Para Pizza:</strong> Configure eixo X (categorias) + agregações Y.<br/>"
                    "<strong>Para Tabela:</strong> Configure 'Legenda (série)' como coluna de agrupamento + 'Agregações Y' como métricas (colunas da tabela). Eixo X é ignorado.<br/><br/>"
                    "<strong>Eixo X:</strong> Campo da query (ex: 'data_venda', 'produto')<br/>"
                    "<strong>Granularidade do Eixo X:</strong> Se for DATETIME, escolha: hour, day, week, month, quarter, year<br/>"
                    "<strong>Campo de Série (Legenda):</strong> (Opcional) Para múltiplas séries (ex: 'unidade_nome'). <span style='color: #d9534f; font-weight: bold;'>Para TABELA: Campo OBRIGATÓRIO que define as linhas (ex: 'seller_name', 'product_name')</span><br/>"
                    "<strong>Agregações do Eixo Y:</strong> Formato JSON:<br/>"
                    "<pre>[{{\n"
                    '  "field": "valor_venda",\n'
                    '  "aggregation": "sum",\n'
                    '  "label": "Total de Vendas",\n'
                    '  "axis": "y1"\n'
                    "}},\n"
                    "{{\n"
                    '  "field": "valor_venda",\n'
                    '  "aggregation": "avg",\n'
                    '  "label": "Ticket Médio",\n'
                    '  "axis": "y2"\n'
                    "}}]</pre>"
                    "<strong>Para TABELA:</strong> Cada agregação será uma coluna da tabela.<br/>"
                    "<strong>Agregações disponíveis:</strong> sum, avg, count, count_distinct, min, max, median"
                    "</div>"
                ),
            },
        ),
        (
            "🔍 Filtro e Ordenação do bloco",
            {
                "fields": ("block_filter", "block_order_by"),
                "description": format_html(
                    "<div style='background: #d1ecf1; border-left: 4px solid #17a2b8; padding: 12px;'>"
                    "<strong>💡 Filtro e Ordenação ao nível do bloco</strong><br/><br/>"
                    "Permite criar múltiplos blocos da mesma fonte de dados com filtros e ordenações diferentes, "
                    "sem precisar duplicar o DataSource.<br/><br/>"
                    "<strong>Filtro SQL - Exemplos:</strong><br/>"
                    "<code>status = 'cancelado'</code><br/>"
                    "<code>status = 'ativo' AND payment_method = 'PIX'</code><br/><br/>"
                    "<strong>Ordenação - Exemplos:</strong><br/>"
                    "<code>total_vendas DESC</code><br/>"
                    "<code>data_venda DESC, unidade_id ASC</code><br/><br/>"
                    "⚠️ Use apenas cláusulas WHERE válidas (sem DDL/DML)."
                    "</div>"
                ),
            },
        ),
        (
            "📊 Configuração de Métrica/KPI",
            {
                "fields": ("metric_prefix", "metric_suffix", "metric_decimal_places"),
                "description": format_html(
                    "<div style='background: #f8d7da; border-left: 4px solid #dc3545; padding: 12px;'>"
                    "<strong>📈 Formatação de Métricas</strong><br/><br/>"
                    "Campos usados apenas quando o tipo de gráfico é 'Métrica/KPI'.<br/><br/>"
                    "<strong>Prefixo:</strong> Texto exibido antes do valor (ex: 'R$ ', 'Total: ')<br/>"
                    "<strong>Sufixo:</strong> Texto exibido depois do valor (ex: '%', ' vendas')<br/>"
                    "<strong>Casas Decimais:</strong> Quantidade de dígitos após a vírgula (0-10)"
                    "</div>"
                ),
            },
        ),
        (
            "Layout",
            {
                "fields": ("col_span", "row_span"),
                "description": "Grid de 12 colunas. Ex: col_span=6 ocupa metade da largura, col_span=12 ocupa largura total.",
            },
        ),
        (
            "Configurações Extras (Opcional)",
            {
                "fields": ("config", "preview_config"),
                "classes": ("collapse",),
                "description": "Configurações adicionais como cores, legendas, tooltips, etc. Formato JSON livre.",
            },
        ),
        (
            "Testar Bloco",
            {
                "fields": ("test_block_preview",),
                "classes": ("collapse",),
                "description": "Teste a execução da query e validação de campos (sem filtros de instância).",
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def layout_info(self, obj):
        """Mostra informações de layout."""
        return f"{obj.col_span}x{obj.row_span}"

    layout_info.short_description = "Layout (WxH)"

    def draft_status_badge(self, obj):
        """Mostra badge de status do bloco (rascunho ou pronto)."""
        if obj.is_draft:
            return format_html(
                '<span style="background: #ffc107; color: #000; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">🟡 RASCUNHO</span>'
            )
        else:
            is_complete, _ = obj.is_configuration_complete()
            if is_complete:
                return format_html(
                    '<span style="background: #28a745; color: #fff; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">🟢 PRONTO</span>'
                )
            else:
                return format_html(
                    '<span style="background: #dc3545; color: #fff; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold;">🔴 INCOMPLETO</span>'
                )

    draft_status_badge.short_description = "Status"

    actions = ["mark_as_ready", "mark_as_draft"]

    def mark_as_ready(self, request, queryset):
        """Marca blocos selecionados como prontos (valida antes)."""
        success = 0
        errors = []

        for block in queryset:
            try:
                block.mark_as_ready()
                success += 1
            except Exception as e:
                errors.append(f"{block.title}: {str(e)}")

        if success > 0:
            self.message_user(
                request, f"{success} bloco(s) marcado(s) como pronto com sucesso."
            )

        if errors:
            self.message_user(request, "Erros: " + "; ".join(errors), level="error")

    mark_as_ready.short_description = "✅ Marcar selecionados como PRONTO"

    def mark_as_draft(self, request, queryset):
        """Marca blocos selecionados como rascunho."""
        updated = queryset.update(is_draft=True)
        self.message_user(request, f"{updated} bloco(s) marcado(s) como rascunho.")

    mark_as_draft.short_description = "🟡 Marcar selecionados como RASCUNHO"

    def test_block(self, obj):
        """Link para testar o bloco."""
        if obj.id:
            return format_html(
                '<a href="javascript:void(0)" onclick="alert(\'Use a seção Testar Bloco abaixo para executar a query\')">Testar</a>'
            )
        return "-"

    test_block.short_description = "Testar"

    def preview_y_axis_aggregations(self, obj):
        """Mostra preview formatado das agregações do eixo Y."""
        if obj.y_axis_aggregations:
            import json

            try:
                formatted = json.dumps(
                    obj.y_axis_aggregations, indent=2, ensure_ascii=False
                )
                return format_html(
                    '<pre style="max-height: 200px; overflow: auto;">{}</pre>',
                    formatted,
                )
            except:
                return str(obj.y_axis_aggregations)
        return "-"

    preview_y_axis_aggregations.short_description = "Preview Agregações"

    def preview_config(self, obj):
        """Mostra preview formatado das configurações extras."""
        if obj.config:
            import json

            try:
                formatted = json.dumps(obj.config, indent=2, ensure_ascii=False)
                return format_html(
                    '<pre style="max-height: 200px; overflow: auto;">{}</pre>',
                    formatted,
                )
            except:
                return str(obj.config)
        return "-"

    preview_config.short_description = "Preview Config"

    def test_block_preview(self, obj):
        """Executa a query usando Semantic Layer e mostra preview dos dados."""
        if not obj.id:
            return "Salve o bloco primeiro para testá-lo."

        html_parts = []

        # 1. Mostra a query SQL gerada
        try:
            generated_sql = obj.get_generated_sql()
            html_parts.append(
                format_html(
                    """
                    <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin-bottom: 15px;">
                        <strong>⚠️ IMPORTANTE:</strong> A query abaixo é atualizada apenas quando você <strong>salva</strong> o bloco.
                    </div>
                    <details open>
                        <summary style="cursor: pointer; font-weight: bold; padding: 8px; background: #f0f0f0; margin-bottom: 10px;">
                            📝 Query SQL Gerada (Clique para expandir/recolher)
                        </summary>
                        <pre style="background: #2d2d2d; color: #f8f8f2; padding: 15px; border-radius: 4px; overflow-x: auto; font-size: 12px; line-height: 1.5;">{}</pre>
                    </details>
                    """,
                    generated_sql,
                )
            )
        except Exception as e:
            html_parts.append(
                format_html(
                    '<div style="color: red; margin-bottom: 15px;"><strong>Erro ao gerar SQL:</strong><br>{}</div>',
                    str(e),
                )
            )

        # 2. Executa a query e mostra resultados
        try:
            success, result = obj.get_data()

            if not success:
                html_parts.append(
                    format_html(
                        '<div style="color: red; background: #ffebee; padding: 12px; border-left: 4px solid #f44336;"><strong>❌ Erro ao executar query:</strong><br>{}</div>',
                        result,
                    )
                )
            elif not result or len(result) == 0:
                html_parts.append(
                    format_html(
                        '<div style="color: orange; background: #fff3e0; padding: 12px; border-left: 4px solid #ff9800;"><strong>⚠️ Query retornou 0 resultados</strong></div>'
                    )
                )
            else:
                import json

                # result agora é um dict normalizado {"x": [...], "series": [...]}
                # Vamos mostrar de forma mais amigável
                result_json = json.dumps(
                    result, indent=2, ensure_ascii=False, default=str
                )

                num_x_values = len(result.get("x", []))
                num_series = len(result.get("series", []))

                html_parts.append(
                    format_html(
                        """
                        <div style="color: green; background: #e8f5e9; padding: 12px; border-left: 4px solid #4caf50; margin-bottom: 15px;">
                            <strong>✓ Bloco válido!</strong><br>
                            <strong>{}</strong> valores no eixo X • <strong>{}</strong> série(s)
                        </div>
                        <details open>
                            <summary style="cursor: pointer; font-weight: bold; padding: 8px; background: #f0f0f0; margin-bottom: 10px;">
                                📊 Dados Normalizados (formato final para o frontend)
                            </summary>
                            <pre style="max-height: 400px; overflow: auto; background: #f5f5f5; padding: 15px; border-radius: 4px; font-size: 12px;">{}</pre>
                        </details>
                        """,
                        num_x_values,
                        num_series,
                        result_json[:3000] + ("..." if len(result_json) > 3000 else ""),
                    )
                )

        except Exception as e:
            import traceback

            error_detail = traceback.format_exc()
            html_parts.append(
                format_html(
                    """
                    <div style="color: red; background: #ffebee; padding: 12px; border-left: 4px solid #f44336;">
                        <strong>❌ Erro inesperado:</strong><br>
                        <code>{}</code>
                    </div>
                    <details style="margin-top: 10px;">
                        <summary style="cursor: pointer; color: #666;">Ver stacktrace completo</summary>
                        <pre style="background: #f5f5f5; padding: 10px; font-size: 11px; overflow-x: auto;">{}</pre>
                    </details>
                    """,
                    str(e),
                    error_detail,
                )
            )

        return mark_safe("".join(str(part) for part in html_parts))

    test_block_preview.short_description = "Resultado do Teste"


@admin.register(DashboardTemplate)
class DashboardTemplateAdmin(admin.ModelAdmin):
    """Admin para o modelo DashboardTemplate."""

    list_display = [
        "nome",
        "ativo",
        "num_blocks",
        "num_componentes",
        "num_instances",
        "criado_em",
    ]
    list_filter = ["ativo", "criado_em"]
    search_fields = ["nome", "descricao"]
    readonly_fields = [
        "id",
        "criado_em",
        "atualizado_em",
        "preview_schema",
        "preview_componentes_data",
        "architecture_info",
    ]
    inlines = [DashboardBlockInline]  # Sistema NOVO - use DashboardBlock
    # TemplateComponentInline removido - apenas para dashboards legados (edite diretamente se necessário)

    fieldsets = (
        (
            "ℹ️ Arquitetura",
            {
                "fields": ("architecture_info",),
                "description": "Informações sobre o sistema de dashboards.",
            },
        ),
        ("Informações Básicas", {"fields": ("nome", "descricao", "ativo")}),
        (
            "🎯 Filtros Dinâmicos",
            {
                "fields": ("filterable_fields",),
                "classes": ("collapse",),
                "description": (
                    "Configure campos filtráveis enviados ao frontend. "
                    "Formato JSON: "
                    '{"temporal": {"field": "sold_at", "label": "Data da Venda"}, '
                    '"categorical": [{"field": "seller_id", "label": "Vendedor", "limit": 100}]}'
                ),
            },
        ),
        (
            "Estrutura do Dashboard (Opcional)",
            {
                "fields": ("schema", "preview_schema"),
                "classes": ("collapse",),
                "description": "JSON avançado - use apenas se precisar de configurações complexas não cobertas pelos blocos.",
            },
        ),
        (
            "Preview dos Componentes",
            {
                "fields": ("preview_componentes_data",),
                "classes": ("collapse",),
                "description": "Visualize os dados retornados pelas queries dos componentes (sem filtros de instância).",
            },
        ),
        (
            "Metadados",
            {"fields": ("id", "criado_em", "atualizado_em"), "classes": ("collapse",)},
        ),
    )

    def architecture_info(self, obj):
        """Mostra informações sobre qual sistema usar."""
        num_blocks = obj.blocks.filter(ativo=True).count()
        num_componentes = obj.componentes.filter(ativo=True).count()

        if num_blocks > 0 and num_componentes > 0:
            return format_html(
                '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">'
                "<strong>⚠️ Template Misto</strong><br>"
                "Este template tem <strong>{} blocos</strong> e <strong>{} componentes estruturados</strong>.<br>"
                "Recomendação: <strong>Use apenas Blocos</strong> para melhor manutenção."
                "</div>",
                num_blocks,
                num_componentes,
            )
        elif num_componentes > 0:
            return format_html(
                '<div style="padding: 10px; background: #e7f3ff; border-left: 4px solid #0066cc;">'
                "<strong>📊 Dashboard com Componentes</strong><br>"
                "Este template usa <strong>{} componentes estruturados</strong>.<br>"
                "Endpoint: <code>/api/dashboards/{{id}}/data/</code>"
                "</div>",
                num_componentes,
            )
        elif num_blocks > 0:
            return format_html(
                '<div style="padding: 10px; background: #d4edda; border-left: 4px solid #28a745;">'
                "<strong>✅ Dashboard com Blocos</strong><br>"
                "Este template usa <strong>{} blocos</strong> com semantic layer.<br>"
                "Endpoint: <code>/api/dashboards/{{id}}/data/</code><br>"
                "Dados normalizados e frontend desacoplado."
                "</div>",
                num_blocks,
            )
        else:
            return format_html(
                '<div style="padding: 10px; background: #e7f3ff; border-left: 4px solid #007bff;">'
                "<strong>📝 Template Vazio</strong><br>"
                "Adicione blocos abaixo para configurar o dashboard."
                "</div>"
            )

    architecture_info.short_description = "Sistema Usado"

    def num_blocks(self, obj):
        """Retorna o número de blocos ativos deste template."""
        count = obj.blocks.filter(ativo=True).count()
        if count > 0:
            return format_html('<strong style="color: #28a745;">{} ✓</strong>', count)
        return format_html('<span style="color: #999;">0</span>')

    num_blocks.short_description = "Blocos (Novo)"

    def num_componentes(self, obj):
        """Retorna o número de componentes estruturados deste template."""
        return obj.componentes.filter(ativo=True).count()

    num_componentes.short_description = "Componentes"

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

    def preview_componentes_data(self, obj):
        """Executa e mostra os resultados dos blocos do template."""
        import json
        from datetime import date, datetime
        from decimal import Decimal
        from uuid import UUID

        if not obj.id:
            return "Salve o template primeiro para visualizar os resultados."

        def json_serializer(obj_value):
            """Serializa tipos especiais para JSON."""
            if isinstance(obj_value, (datetime, date)):
                return obj_value.isoformat()
            elif isinstance(obj_value, Decimal):
                return float(obj_value)
            elif isinstance(obj_value, UUID):
                return str(obj_value)
            raise TypeError(f"Type {type(obj_value)} not serializable")

        try:
            # Busca blocos do template (arquitetura refatorada)
            blocks = (
                DashboardBlock.objects.filter(template=obj, ativo=True)
                .select_related("datasource", "datasource__connection")
                .order_by("order")
            )

            # Se não tem blocos, tenta componentes legados
            if not blocks.exists():
                componentes = TemplateComponent.objects.filter(
                    template=obj, ativo=True
                ).select_related(
                    "datasource", "component_type", "datasource__connection"
                )

                if not componentes.exists():
                    return format_html(
                        '<div style="padding: 15px; background: #fff3cd; border-radius: 5px;">'
                        "⚠️ Nenhum bloco ou componente adicionado ao template ainda. "
                        "Adicione blocos usando a seção acima."
                        "</div>"
                    )

                # Usa componentes legados
                return self._preview_structured_components(
                    componentes, obj, json_serializer
                )

            # Formata os resultados dos blocos
            html_parts = []
            html_parts.append(
                '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
            )

            # Informações gerais
            html_parts.append('<h3 style="margin-top: 0;">📊 Preview dos Blocos</h3>')
            html_parts.append(f"<p><strong>Template:</strong> {obj.nome}</p>")
            html_parts.append(
                f"<p><strong>Total de Blocos:</strong> {blocks.count()}</p>"
            )
            html_parts.append(
                '<p style="color: #666; font-size: 12px;">Nota: Dados mostrados SEM filtros de instância</p>'
            )
            html_parts.append("<hr>")

            # Executa cada bloco
            for block in blocks:
                html_parts.append(
                    f"<h4>📊 {block.title} ({block.get_chart_type_display()})</h4>"
                )
                html_parts.append(
                    f"<p><strong>DataSource:</strong> {block.datasource.nome}</p>"
                )
                html_parts.append(
                    f"<p><strong>Eixo X:</strong> <code>{block.x_axis_field or '(não configurado)'}</code></p>"
                )

                if block.y_axis_aggregations:
                    y_axis_str = json.dumps(
                        block.y_axis_aggregations, ensure_ascii=False
                    )
                    html_parts.append(
                        f"<p><strong>Agregações Y:</strong> <code>{y_axis_str}</code></p>"
                    )

                try:
                    # Executa a query usando Semantic Layer
                    success, result = block.get_data()

                    if success:
                        num_records = len(result) if isinstance(result, list) else 0
                        html_parts.append(
                            f'<p style="color: green;"><strong>✅ {num_records} registro(s) retornado(s)</strong></p>'
                        )

                        # Mostra preview dos dados
                        if num_records > 0:
                            try:
                                preview_data = result[:3]
                                formatted_json = json.dumps(
                                    preview_data,
                                    indent=2,
                                    ensure_ascii=False,
                                    default=json_serializer,
                                )
                                formatted_json = formatted_json.replace(
                                    "{", "{{"
                                ).replace("}", "}}")

                                html_parts.append("<details open>")
                                html_parts.append(
                                    '<summary style="cursor: pointer; font-weight: bold; margin: 10px 0;">📄 Preview dos Dados (primeiros 3):</summary>'
                                )
                                html_parts.append(
                                    f'<pre style="background: white; padding: 10px; border: 1px solid #ddd; border-radius: 3px; overflow: auto; max-height: 300px;">{formatted_json}</pre>'
                                )
                                html_parts.append("</details>")

                                if num_records > 3:
                                    html_parts.append(
                                        f'<p style="color: #666; font-size: 12px;">... e mais {num_records - 3} registro(s)</p>'
                                    )
                            except Exception as e:
                                html_parts.append(
                                    f'<p style="color: orange;">⚠️ Erro ao exibir preview: {str(e)}</p>'
                                )
                        else:
                            # Bloco não configurado
                            html_parts.append(
                                '<p style="color: orange;">⚠️ Configure o bloco para visualizar dados</p>'
                            )
                    else:
                        html_parts.append(
                            f'<div style="color: red; background: #ffebee; padding: 10px; border-radius: 3px; margin: 10px 0;">'
                        )
                        html_parts.append(f"<strong>❌ Erro:</strong> {result}")
                        html_parts.append("</div>")

                except Exception as e:
                    html_parts.append(
                        f'<div style="color: red; background: #ffebee; padding: 10px; border-radius: 3px; margin: 10px 0;">'
                    )
                    html_parts.append(f"<strong>❌ Erro:</strong> {str(e)}")
                    html_parts.append("</div>")

                html_parts.append("<hr>")

            html_parts.append("</div>")

            return format_html("".join(html_parts))

        except Exception as e:
            import traceback

            return format_html(
                '<div style="color: red; background: #ffebee; padding: 15px; border-radius: 5px;">'
                "<strong>❌ Erro ao executar queries:</strong><br><pre>{}</pre>"
                "</div>",
                traceback.format_exc(),
            )

    def _preview_structured_components(self, componentes, obj, json_serializer):
        """Preview para componentes legados."""
        import json

        html_parts = []
        html_parts.append(
            '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
        )
        html_parts.append(
            '<h3 style="margin-top: 0;">🔴 Preview dos Componentes LEGADOS</h3>'
        )
        html_parts.append(f"<p><strong>Template:</strong> {obj.nome}</p>")
        html_parts.append(f"<p><strong>Total:</strong> {componentes.count()}</p>")
        html_parts.append(
            '<p style="color: #dc3545;">⚠️ Este template usa sistema LEGADO. Recomenda-se migrar para Blocos.</p>'
        )
        html_parts.append("<hr>")

        for componente in componentes:
            html_parts.append(
                f"<h4>📁 {componente.nome} ({componente.component_type.nome})</h4>"
            )
            html_parts.append(
                f"<p><strong>DataSource:</strong> {componente.datasource.nome}</p>"
            )

            try:
                success, result = componente.datasource.execute_query(params=None)
                if success:
                    num_records = len(result) if isinstance(result, list) else 0
                    html_parts.append(
                        f'<p style="color: green;"><strong>✅ {num_records} registro(s)</strong></p>'
                    )
                    if num_records > 0:
                        preview_data = result[:3]
                        formatted_json = json.dumps(
                            preview_data,
                            indent=2,
                            ensure_ascii=False,
                            default=json_serializer,
                        )
                        formatted_json = formatted_json.replace("{", "{{").replace(
                            "}", "}}"
                        )
                        html_parts.append("<details>")
                        html_parts.append(
                            '<summary style="cursor: pointer;">📄 Dados (3 primeiros)</summary>'
                        )
                        html_parts.append(
                            f'<pre style="background: white; padding: 10px; border: 1px solid #ddd; overflow: auto; max-height: 200px;">{formatted_json}</pre>'
                        )
                        html_parts.append("</details>")
                else:
                    html_parts.append(f'<p style="color: red;">❌ Erro: {result}</p>')
            except Exception as e:
                html_parts.append(f'<p style="color: red;">❌ Erro: {str(e)}</p>')

            html_parts.append("<hr>")

        html_parts.append("</div>")
        return format_html("".join(html_parts))

    preview_componentes_data.short_description = "Preview dos Dados"


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
        from datetime import date, datetime
        from decimal import Decimal
        from uuid import UUID

        from dashboards.views import DashboardInstanceViewSet

        if not obj.id:
            return "Salve a instância primeiro para visualizar os resultados."

        def json_serializer(obj):
            """Serializa tipos especiais para JSON."""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            elif isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, UUID):
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")

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
                    html_parts.append(f"<h4>📁 Componente: {datasource_name}</h4>")

                    # Verifica se é um componente estruturado (com type, config, data)
                    if isinstance(data, dict) and "type" in data:
                        # Componente estruturado
                        html_parts.append(
                            f'<p><strong>Tipo:</strong> {data.get("type", "N/A")}</p>'
                        )

                        if data.get("error"):
                            html_parts.append(
                                f'<div style="color: red; background: #ffebee; padding: 10px; border-radius: 3px; margin: 10px 0;">'
                            )
                            html_parts.append(
                                f'<strong>❌ Erro:</strong> {data["error"]}'
                            )
                            html_parts.append("</div>")
                        else:
                            component_data = data.get("data", [])
                            num_records = (
                                len(component_data)
                                if isinstance(component_data, list)
                                else 0
                            )
                            html_parts.append(
                                f'<p style="color: green;"><strong>✅ {num_records} registro(s) encontrado(s)</strong></p>'
                            )

                            # Mostra config do componente
                            if data.get("config"):
                                config_str = json.dumps(
                                    data["config"], indent=2, ensure_ascii=False
                                )
                                config_str = config_str.replace("{", "{{").replace(
                                    "}", "}}"
                                )
                                html_parts.append('<details style="margin: 10px 0;">')
                                html_parts.append(
                                    '<summary style="cursor: pointer; font-weight: bold;">⚙️ Configurações</summary>'
                                )
                                html_parts.append(
                                    f'<pre style="background: white; padding: 10px; border: 1px solid #ddd; border-radius: 3px; overflow: auto; max-height: 200px;">{config_str}</pre>'
                                )
                                html_parts.append("</details>")

                            # Mostra preview dos dados (primeiros 5 registros)
                            if num_records > 0:
                                preview_data = component_data[:5]
                                formatted_json = json.dumps(
                                    preview_data,
                                    indent=2,
                                    ensure_ascii=False,
                                    default=json_serializer,
                                )
                                formatted_json = formatted_json.replace(
                                    "{", "{{"
                                ).replace("}", "}}")
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
                    elif isinstance(data, dict) and data.get("error"):
                        # Formato antigo - erro
                        html_parts.append(
                            f'<div style="color: red; background: #ffebee; padding: 10px; border-radius: 3px; margin: 10px 0;">'
                        )
                        html_parts.append(f'<strong>❌ Erro:</strong> {data["error"]}')
                        html_parts.append("</div>")
                    else:
                        # Formato antigo - lista direta
                        num_records = len(data) if isinstance(data, list) else 0
                        html_parts.append(
                            f'<p style="color: green;"><strong>✅ {num_records} registro(s) encontrado(s)</strong></p>'
                        )

                        # Mostra preview dos dados (primeiros 5 registros)
                        if num_records > 0:
                            preview_data = data[:5]
                            formatted_json = json.dumps(
                                preview_data,
                                indent=2,
                                ensure_ascii=False,
                                default=json_serializer,
                            )
                            # Escapa as chaves para evitar erro no format_html
                            formatted_json = formatted_json.replace("{", "{{").replace(
                                "}", "}}"
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
            import traceback

            return format_html(
                '<div style="color: red; background: #ffebee; padding: 15px; border-radius: 5px;">'
                "<strong>❌ Erro ao executar queries:</strong><br><pre>{}</pre>"
                "</div>",
                traceback.format_exc(),
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


class DataSourceAdmin(admin.ModelAdmin):
    """
    Admin customizado para DataSource com experiência guiada.

    FLUXO:
    1. Usuário define query SQL e salva
    2. Sistema valida automaticamente e extrai colunas
    3. Usuário visualiza colunas detectadas
    4. Usuário configura contrato semântico (mapeia colunas)
    5. Sistema valida o contrato
    """

    list_display = [
        "nome",
        "connection",
        "display_validation_status",
        "display_contract_status",
        "ativo",
        "criado_em",
    ]
    list_filter = ["ativo", "contract_validated", "criado_em", "connection"]
    search_fields = ["nome", "descricao"]
    readonly_fields = [
        "id",
        "criado_em",
        "atualizado_em",
        "detected_columns",
        "last_validation_at",
        "last_validation_error",
        "contract_validated",
        "display_detected_columns",
        "display_semantic_types",
        "display_validation_status_detail",
        "display_contract_status_detail",
        "action_validate_query",
        "action_test_normalized_query",
    ]

    fieldsets = (
        (
            "1️⃣ Informações Básicas",
            {
                "fields": ("nome", "descricao", "ativo"),
                "description": "Defina o nome e descrição desta fonte de dados.",
            },
        ),
        (
            "2️⃣ Conexão",
            {
                "fields": ("connection",),
                "description": "Selecione a conexão ao banco de dados que será utilizada.",
            },
        ),
        (
            "3️⃣ Query SQL",
            {
                "fields": ("sql",),
                "description": format_html(
                    "<div style='background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; margin-bottom: 10px;'>"
                    "<strong>⚠️ IMPORTANTE - Regras de Segurança:</strong><br/>"
                    "• Apenas queries SELECT ou WITH (CTEs) são permitidas<br/>"
                    "• Não use ponto-e-vírgula (;) - apenas uma query<br/>"
                    "• Palavras proibidas: INSERT, UPDATE, DELETE, DROP, CREATE, etc<br/>"
                    "</div>"
                    "<div style='background: #d1ecf1; border-left: 4px solid #0c5460; padding: 12px;'>"
                    "<strong>💡 DICA:</strong><br/>"
                    "Após salvar, o sistema validará automaticamente sua query e extrairá as colunas.<br/>"
                    "Use o botão 'Validar Query Manualmente' para testar antes de salvar."
                    "</div>"
                ),
            },
        ),
        (
            "4️⃣ Validação da Query",
            {
                "fields": (
                    "display_validation_status_detail",
                    "action_validate_query",
                    "display_detected_columns",
                    "last_validation_at",
                    "last_validation_error",
                ),
                "classes": ("wide",),
                "description": "Status da validação e colunas detectadas.",
            },
        ),
        (
            "🎯 Semantic Layer (Novo)",
            {
                "fields": ("display_semantic_types",),
                "classes": ("wide",),
                "description": format_html(
                    "<div style='background: #e7f3ff; border-left: 4px solid #0066cc; padding: 12px;'>"
                    "<strong>🚀 Classificação Automática de Tipos Semânticos</strong><br/>"
                    "O sistema analisa automaticamente cada coluna e a classifica em:<br/><br/>"
                    "<strong>📅 DATETIME:</strong> Campos temporais (date, timestamp, time)<br/>"
                    "• Permite agregações temporais: hour, day, week, month, quarter, year<br/><br/>"
                    "<strong>📊 MEASURE:</strong> Campos numéricos agregáveis (int, numeric, float)<br/>"
                    "• Permite agregações: sum, avg, count, count_distinct, min, max, median<br/><br/>"
                    "<strong>🏷️ DIMENSION:</strong> Campos categóricos (text, varchar, uuid, bool)<br/>"
                    "• Usados para agrupamento (GROUP BY) em queries analíticas<br/>"
                    "</div>"
                ),
            },
        ),
        (
            "Metadados",
            {
                "fields": ("id", "criado_em", "atualizado_em", "detected_columns"),
                "classes": ("collapse",),
            },
        ),
    )

    def display_validation_status(self, obj):
        """Status de validação para list_display."""
        if not obj.sql:
            return format_html('<span style="color: #999;">⚪ Sem Query</span>')

        if obj.last_validation_error:
            return format_html('<span style="color: #dc3545;">❌ Erro</span>')

        if obj.detected_columns:
            return format_html(
                '<span style="color: #28a745;">✅ OK ({} cols)</span>',
                len(obj.detected_columns),
            )

        return format_html('<span style="color: #ffc107;">⚠️ Não Validado</span>')

    display_validation_status.short_description = "Validação"

    def display_contract_status(self, obj):
        """Status do contrato para list_display."""
        if obj.contract_validated:
            return format_html('<span style="color: #28a745;">✅ Validado</span>')

        has_contract = any(
            [
                obj.metric_date_column,
                obj.metric_value_column,
                obj.series_key_column,
                obj.unit_id_column,
            ]
        )

        if has_contract:
            return format_html('<span style="color: #ffc107;">⚠️ Incompleto</span>')

        return format_html('<span style="color: #999;">⚪ Não Configurado</span>')

    display_contract_status.short_description = "Contrato"

    def display_validation_status_detail(self, obj):
        """Status detalhado da validação."""
        if not obj.sql:
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">'
                "<strong>⚪ Nenhuma query definida</strong><br/>"
                "Defina a query SQL acima e salve para validar."
                "</div>"
            )

        if obj.last_validation_error:
            return format_html(
                '<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 10px; border-radius: 4px;">'
                '<strong style="color: #721c24;">❌ Erro de Validação:</strong><br/>'
                '<code style="color: #721c24;">{}</code>'
                "</div>",
                obj.last_validation_error,
            )

        if obj.detected_columns:
            return format_html(
                '<div style="background: #d4edda; border-left: 4px solid #28a745; padding: 10px; border-radius: 4px;">'
                '<strong style="color: #155724;">✅ Query Validada com Sucesso!</strong><br/>'
                "{} colunas detectadas (veja abaixo)"
                "</div>",
                len(obj.detected_columns),
            )

        return format_html(
            '<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; border-radius: 4px;">'
            '<strong style="color: #856404;">⚠️ Query não validada</strong><br/>'
            "Salve para validar automaticamente ou use o botão abaixo."
            "</div>"
        )

    display_validation_status_detail.short_description = "Status da Validação"

    def display_detected_columns(self, obj):
        """Exibe as colunas detectadas de forma visual."""
        if not obj.detected_columns:
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px; color: #6c757d;">'
                "Nenhuma coluna detectada ainda.<br/>"
                "Valide a query primeiro."
                "</div>"
            )

        columns_html = "<br/>".join(
            f'<code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px; margin: 2px;">{col}</code>'
            for col in obj.detected_columns
        )

        return mark_safe(
            f'<div style="background: #e7f3ff; border: 1px solid #b3d9ff; padding: 12px; border-radius: 4px;">'
            f'<strong style="color: #004085;">📋 Colunas Disponíveis ({len(obj.detected_columns)}):</strong><br/><br/>'
            f"{columns_html}"
            f"</div>"
        )

    display_detected_columns.short_description = "Colunas Detectadas"

    def display_semantic_types(self, obj):
        """
        Exibe as colunas agrupadas por tipo semântico (DATETIME, MEASURE, DIMENSION).

        Usa columns_metadata (novo) se disponível, senão mostra mensagem explicativa.
        """
        if not obj.columns_metadata:
            # Se não tem metadata ainda, mostra mensagem explicativa
            if obj.detected_columns:
                return format_html(
                    '<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; border-radius: 4px;">'
                    '<strong style="color: #856404;">⚠️ Metadata Semântica não disponível</strong><br/>'
                    "Re-salve o DataSource para extrair metadados semânticos automaticamente."
                    "</div>"
                )
            else:
                return format_html(
                    '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px; color: #6c757d;">'
                    "Nenhuma coluna detectada ainda.<br/>"
                    "Valide a query primeiro."
                    "</div>"
                )

        # Agrupa colunas por tipo semântico
        grouped = {"datetime": [], "measure": [], "dimension": []}

        for col_name, col_info in obj.columns_metadata.items():
            semantic_type = col_info.get("semantic_type", "dimension")
            pg_type = col_info.get("pg_type", "unknown")

            grouped[semantic_type].append(
                {
                    "name": col_name,
                    "pg_type": pg_type,
                }
            )

        # Monta HTML com cards por tipo
        html_parts = []

        # DATETIME (Temporal)
        if grouped["datetime"]:
            cols_html = "<br/>".join(
                f'<code style="background: #fff; padding: 4px 8px; border-radius: 3px; margin: 2px; display: inline-block;">'
                f'📅 {col["name"]} <span style="color: #6c757d; font-size: 0.85em;">({col["pg_type"]})</span>'
                f"</code>"
                for col in grouped["datetime"]
            )
            html_parts.append(
                f'<div style="background: #e7f3ff; border-left: 4px solid #0066cc; padding: 12px; border-radius: 4px; margin-bottom: 10px;">'
                f'<strong style="color: #004085;">🕐 DATETIME ({len(grouped["datetime"])})</strong><br/>'
                f'<span style="font-size: 0.9em; color: #666;">Campos temporais (date, timestamp, etc)</span><br/><br/>'
                f"{cols_html}</div>"
            )

        # MEASURE (Numérico/Agregável)
        if grouped["measure"]:
            cols_html = "<br/>".join(
                f'<code style="background: #fff; padding: 4px 8px; border-radius: 3px; margin: 2px; display: inline-block;">'
                f'📊 {col["name"]} <span style="color: #6c757d; font-size: 0.85em;">({col["pg_type"]})</span>'
                f"</code>"
                for col in grouped["measure"]
            )
            html_parts.append(
                f'<div style="background: #d4edda; border-left: 4px solid #28a745; padding: 12px; border-radius: 4px; margin-bottom: 10px;">'
                f'<strong style="color: #155724;">📈 MEASURE ({len(grouped["measure"])})</strong><br/>'
                f'<span style="font-size: 0.9em; color: #666;">Campos numéricos agregáveis (sum, avg, count)</span><br/><br/>'
                f"{cols_html}</div>"
            )

        # DIMENSION (Categórico/Textual)
        if grouped["dimension"]:
            cols_html = "<br/>".join(
                f'<code style="background: #fff; padding: 4px 8px; border-radius: 3px; margin: 2px; display: inline-block;">'
                f'🏷️ {col["name"]} <span style="color: #6c757d; font-size: 0.85em;">({col["pg_type"]})</span>'
                f"</code>"
                for col in grouped["dimension"]
            )
            html_parts.append(
                f'<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px; border-radius: 4px; margin-bottom: 10px;">'
                f'<strong style="color: #856404;">🔤 DIMENSION ({len(grouped["dimension"])})</strong><br/>'
                f'<span style="font-size: 0.9em; color: #666;">Campos categóricos (text, varchar, uuid)</span><br/><br/>'
                f"{cols_html}</div>"
            )

        final_html = "".join(html_parts)

        return format_html(
            '<div style="border: 1px solid #dee2e6; padding: 15px; border-radius: 6px; background: #f8f9fa;">'
            '<h4 style="margin-top: 0; color: #495057;">🎯 Classificação Semântica</h4>'
            '<p style="margin-bottom: 15px; color: #6c757d; font-size: 0.95em;">'
            "As colunas foram classificadas automaticamente por tipo semântico. "
            "Use estas classificações para configurar agregações no DashboardBlock."
            "</p>"
            "{}"
            "</div>",
            final_html,
        )

    display_semantic_types.short_description = "Tipos Semânticos (Semantic Layer)"

    def action_validate_query(self, obj):
        """Botão para validar query manualmente."""
        if not obj.id:
            return format_html('<span style="color: #999;">Salve primeiro</span>')

        if not obj.sql or not obj.connection:
            return format_html(
                '<span style="color: #999;">Configure SQL e Conexão primeiro</span>'
            )

        return format_html(
            '<a href="/admin/dashboards/datasource/{}/validate/" '
            'class="button" style="background: #0c5460; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">'
            "🔍 Validar Query Manualmente"
            "</a>",
            obj.id,
        )

    action_validate_query.short_description = "Ação"

    def display_contract_status_detail(self, obj):
        """Status detalhado do contrato semântico."""
        if not obj.detected_columns:
            return format_html(
                '<div style="background: #f8f9fa; padding: 10px; border-radius: 4px;">'
                "<strong>⚪ Contrato não disponível</strong><br/>"
                "Valide a query primeiro para configurar o contrato."
                "</div>"
            )

        if obj.contract_validated:
            return format_html(
                '<div style="background: #d4edda; border-left: 4px solid #28a745; padding: 10px; border-radius: 4px;">'
                '<strong style="color: #155724;">✅ Contrato Semântico Validado!</strong><br/>'
                "Esta fonte de dados está pronta para uso em dashboards.<br/><br/>"
                "<strong>Mapeamento:</strong><br/>"
                "• metric_date ← <code>{}</code><br/>"
                "• metric_value ← <code>{}</code><br/>"
                "• series_key ← <code>{}</code><br/>"
                "• unit_id ← <code>{}</code>"
                "</div>",
                obj.metric_date_column,
                obj.metric_value_column,
                obj.series_key_column or "NULL",
                obj.unit_id_column or "NULL",
            )

        # Valida o contrato para mostrar erros
        is_valid, errors = obj.validate_semantic_contract()

        if errors:
            errors_html = "<br/>".join(f"• {error}" for error in errors)
            return format_html(
                '<div style="background: #f8d7da; border-left: 4px solid #dc3545; padding: 10px; border-radius: 4px;">'
                '<strong style="color: #721c24;">❌ Contrato Inválido:</strong><br/>'
                "{}"
                "</div>",
                errors_html,
            )

        return format_html(
            '<div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 10px; border-radius: 4px;">'
            '<strong style="color: #856404;">⚠️ Configure o Contrato</strong><br/>'
            "Preencha os campos obrigatórios acima (Coluna de Data/Tempo e Coluna de Valor Métrico)."
            "</div>"
        )

    display_contract_status_detail.short_description = "Status do Contrato"

    def action_test_normalized_query(self, obj):
        """Botão para testar a query normalizada."""
        if not obj.id:
            return format_html('<span style="color: #999;">Salve primeiro</span>')

        if not obj.contract_validated:
            return format_html(
                '<span style="color: #999;">Valide o contrato primeiro</span>'
            )

        return format_html(
            '<a href="/admin/dashboards/datasource/{}/test-normalized/" '
            'class="button" style="background: #28a745; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">'
            "🧪 Testar Query Normalizada"
            "</a>",
            obj.id,
        )

    action_test_normalized_query.short_description = "Ação"

    def get_urls(self):
        """Adiciona URLs customizadas para validação e teste."""
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/validate/",
                self.admin_site.admin_view(self.validate_query_view),
                name="dashboards_datasource_validate",
            ),
            path(
                "<path:object_id>/test-normalized/",
                self.admin_site.admin_view(self.test_normalized_query_view),
                name="dashboards_datasource_test_normalized",
            ),
        ]
        return custom_urls + urls

    def validate_query_view(self, request, object_id):
        """View para validar a query manualmente."""
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        from django.urls import reverse

        # Busca o objeto
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Fonte de dados não encontrada.", level="error")
            return HttpResponseRedirect(
                reverse("admin:dashboards_datasource_changelist")
            )

        # Executa a validação
        success, message, columns = obj.validate_and_extract_columns()

        if success:
            # Salva os metadados atualizados
            obj.save()
            self.message_user(
                request,
                f"✅ {message}",
                level=messages.SUCCESS,
            )
            self.message_user(
                request,
                f"📋 Colunas detectadas: {', '.join(columns)}",
                level=messages.INFO,
            )
        else:
            self.message_user(
                request,
                f"❌ Erro na validação: {message}",
                level=messages.ERROR,
            )

        # Redireciona de volta para a página de edição
        return HttpResponseRedirect(
            reverse("admin:dashboards_datasource_change", args=[object_id])
        )

    def test_normalized_query_view(self, request, object_id):
        """View para testar a query normalizada."""
        from django.contrib import messages
        from django.http import HttpResponseRedirect
        from django.shortcuts import render
        from django.urls import reverse

        # Busca o objeto
        obj = self.get_object(request, object_id)
        if obj is None:
            self.message_user(request, "Fonte de dados não encontrada.", level="error")
            return HttpResponseRedirect(
                reverse("admin:dashboards_datasource_changelist")
            )

        # Verifica se o contrato está validado
        if not obj.contract_validated:
            self.message_user(
                request,
                "❌ Contrato semântico não validado. Configure os campos obrigatórios primeiro.",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:dashboards_datasource_change", args=[object_id])
            )

        # Gera preview da query normalizada
        try:
            normalized_query = obj.generate_normalized_query()
        except Exception as e:
            self.message_user(
                request,
                f"❌ Erro ao gerar query normalizada: {str(e)}",
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse("admin:dashboards_datasource_change", args=[object_id])
            )

        # Executa a query com LIMIT para preview
        # Adiciona LIMIT à query para não retornar muitos dados no teste
        import psycopg2
        import psycopg2.extras

        success = False
        data = []

        try:
            if obj.ativo and obj.connection.ativo:
                conn = psycopg2.connect(
                    host=obj.connection.host,
                    port=obj.connection.porta,
                    database=obj.connection.database,
                    user=obj.connection.usuario,
                    password=obj.connection.senha,
                    connect_timeout=10,
                )

                cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cursor.execute("SET statement_timeout = '10s'")

                # Adiciona LIMIT para preview
                query_with_limit = f"{normalized_query}\nLIMIT 100"
                cursor.execute(query_with_limit)

                results = cursor.fetchall()
                data = [dict(row) for row in results]

                cursor.close()
                conn.close()

                success = True
        except Exception as e:
            success = False
            data = str(e)

        context = {
            **self.admin_site.each_context(request),
            "title": f"Teste de Query Normalizada: {obj.nome}",
            "datasource": obj,
            "normalized_query": normalized_query,
            "success": success,
            "data": data if success else None,
            "error": data if not success else None,
            "opts": self.model._meta,
        }

        return render(
            request,
            "admin/dashboards/datasource_test_normalized.html",
            context,
        )

    def save_model(self, request, obj, form, change):
        """Override para mostrar mensagens úteis após o save."""
        try:
            super().save_model(request, obj, form, change)

            # Mensagens baseadas no status
            if obj.last_validation_error:
                self.message_user(
                    request,
                    f"⚠️ Query salva, mas validação falhou: {obj.last_validation_error}",
                    level="warning",
                )
            elif obj.detected_columns:
                self.message_user(
                    request,
                    f"✅ Query validada com sucesso! {len(obj.detected_columns)} colunas detectadas.",
                    level="success",
                )

                if not obj.contract_validated:
                    self.message_user(
                        request,
                        "💡 Próximo passo: Configure o Contrato Semântico abaixo (seção 5️⃣).",
                        level="info",
                    )
            else:
                self.message_user(
                    request,
                    "DataSource salvo. Configure a conexão e query SQL.",
                    level="info",
                )

        except Exception as e:
            self.message_user(request, f"❌ Erro ao salvar: {str(e)}", level="error")


admin.site.register(DataSource, DataSourceAdmin)
