"""
Admin configuration for dashboards app.
"""

from django.contrib import admin
from django.utils.html import format_html

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
    
    # Não inclui x_axis_field e y_axis_fields no inline
    # Eles devem ser configurados na página de edição detalhada do bloco
    exclude = []
    verbose_name = "Bloco de Dashboard"
    verbose_name_plural = "Blocos (Configure os eixos X/Y clicando em 'Editar Eixos' após salvar)"

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
        "legacy_warning",
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
    
    def legacy_warning(self, obj):
        """Aviso de que é sistema legado."""
        return format_html(
            '<span style="color: #dc3545; font-weight: bold;">⚠️ LEGADO</span>'
        )
    
    legacy_warning.short_description = "Status"


@admin.register(DashboardBlock)
class DashboardBlockAdmin(admin.ModelAdmin):
    """
    Admin para o modelo DashboardBlock - NOVA ARQUITETURA.

    Este é o modelo central para criação de dashboards.
    """

    list_display = [
        "title",
        "template",
        "chart_type",
        "datasource",
        "order",
        "layout_info",
        "ativo",
        "test_block",
    ]
    list_filter = ["ativo", "chart_type", "template"]
    search_fields = ["title", "template__nome", "datasource__nome"]
    readonly_fields = [
        "id",
        "criado_em",
        "atualizado_em",
        "preview_y_axis_fields",
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
                ),
                "description": "Configure as informações básicas do bloco.",
            },
        ),
        (
            "Configuração de Eixos",
            {
                "fields": ("x_axis_field", "series_field", "y_axis_fields", "preview_y_axis_fields"),
                "description": """
                <strong>Eixo X:</strong> Campo da query que representa o eixo X (ex: "data", "produto").<br>
                <strong>Campo de Série/Legenda (Opcional):</strong> Campo que define múltiplas séries/legendas (ex: "nome_unidade", "produto").<br>
                <strong>Eixo Y:</strong> Lista de métricas em formato JSON:<br>
                <pre>[
  {"field": "total_vendas", "label": "Vendas Totais", "axis": "y1"},
  {"field": "ticket_medio", "label": "Ticket Médio", "axis": "y2"}
]</pre>
                """,
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

    def test_block(self, obj):
        """Link para testar o bloco."""
        if obj.id:
            return format_html(
                '<a href="javascript:void(0)" onclick="alert(\'Use a seção Testar Bloco abaixo para executar a query\')">Testar</a>'
            )
        return "-"

    test_block.short_description = "Testar"

    def preview_y_axis_fields(self, obj):
        """Mostra preview formatado dos campos do eixo Y."""
        if obj.y_axis_fields:
            import json

            try:
                formatted = json.dumps(obj.y_axis_fields, indent=2, ensure_ascii=False)
                return format_html(
                    '<pre style="max-height: 200px; overflow: auto;">{}</pre>',
                    formatted,
                )
            except:
                return str(obj.y_axis_fields)
        return "-"

    preview_y_axis_fields.short_description = "Preview Eixo Y"

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
        """Executa a query e valida os campos configurados."""
        if not obj.id:
            return "Salve o bloco primeiro para testá-lo."

        try:
            # Executa a query
            success, result = obj.datasource.execute_query()

            if not success:
                return format_html(
                    '<div style="color: red;"><strong>Erro ao executar query:</strong><br>{}</div>',
                    result,
                )

            if not result or len(result) == 0:
                return format_html(
                    '<div style="color: orange;"><strong>Query retornou 0 resultados</strong></div>'
                )

            # Valida campos
            is_valid, errors = obj.validate_fields_against_query(result)

            if not is_valid:
                return format_html(
                    '<div style="color: red;"><strong>Erros de validação:</strong><ul>{}</ul></div>',
                    format_html("".join([f"<li>{err}</li>" for err in errors])),
                )

            # Normaliza dados
            try:
                normalized = obj.normalize_data(result)

                import json

                normalized_json = json.dumps(normalized, indent=2, ensure_ascii=False)

                return format_html(
                    """
                    <div style="color: green;">
                        <strong>✓ Bloco válido!</strong><br>
                        Query retornou <strong>{}</strong> registros.<br>
                        Campos disponíveis: <code>{}</code>
                    </div>
                    <br>
                    <strong>Preview dos dados normalizados (primeiros 5 registros):</strong>
                    <pre style="max-height: 400px; overflow: auto; background: #f5f5f5; padding: 10px;">{}</pre>
                    """,
                    len(result),
                    ", ".join(sorted(result[0].keys())),
                    normalized_json[:2000]
                    + ("..." if len(normalized_json) > 2000 else ""),
                )
            except Exception as e:
                return format_html(
                    '<div style="color: red;"><strong>Erro ao normalizar dados:</strong><br>{}</div>',
                    str(e),
                )

        except Exception as e:
            return format_html(
                '<div style="color: red;"><strong>Erro inesperado:</strong><br>{}</div>',
                str(e),
            )

    test_block_preview.short_description = "Resultado do Teste"


@admin.register(DashboardTemplate)
class DashboardTemplateAdmin(admin.ModelAdmin):
    """Admin para o modelo DashboardTemplate."""

    list_display = [
        "nome",
        "ativo",
        "num_blocks",
        "num_componentes_legacy",
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
        num_legacy = obj.componentes.filter(ativo=True).count()
        
        if num_blocks > 0 and num_legacy > 0:
            return format_html(
                '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">'
                '<strong>⚠️ Template Misto</strong><br>'
                'Este template tem <strong>{} blocos novos</strong> e <strong>{} componentes legados</strong>.<br>'
                'Recomendação: <strong>Use apenas Blocos</strong> (nova arquitetura) ou migre os componentes legados.'
                '</div>',
                num_blocks, num_legacy
            )
        elif num_legacy > 0:
            return format_html(
                '<div style="padding: 10px; background: #f8d7da; border-left: 4px solid #dc3545;">'
                '<strong>🔴 Dashboard Legado</strong><br>'
                'Este template usa <strong>{} componentes legados</strong>.<br>'
                'Endpoint: <code>/api/dashboards/{{id}}/data/</code><br>'
                'Recomendação: <strong>Migre para Blocos</strong> (nova arquitetura).'
                '</div>',
                num_legacy
            )
        elif num_blocks > 0:
            return format_html(
                '<div style="padding: 10px; background: #d4edda; border-left: 4px solid #28a745;">'
                '<strong>✅ Arquitetura Refatorada</strong><br>'
                'Este template usa <strong>{} blocos</strong> da arquitetura refatorada.<br>'
                'Endpoint: <code>/api/dashboards/{{id}}/data/</code><br>'
                'Dados normalizados e frontend desacoplado.'
                '</div>',
                num_blocks
            )
        else:
            return format_html(
                '<div style="padding: 10px; background: #e7f3ff; border-left: 4px solid #007bff;">'
                '<strong>📝 Template Vazio</strong><br>'
                'Adicione blocos abaixo para configurar o dashboard.<br>'
                '<strong>Use a seção "Blocos"</strong> (arquitetura refatorada).'
                '</div>'
            )
    
    architecture_info.short_description = "Sistema Usado"

    def num_blocks(self, obj):
        """Retorna o número de blocos ativos deste template."""
        count = obj.blocks.filter(ativo=True).count()
        if count > 0:
            return format_html('<strong style="color: #28a745;">{} ✓</strong>', count)
        return format_html('<span style="color: #999;">0</span>')

    num_blocks.short_description = "Blocos (Novo)"

    def num_componentes_legacy(self, obj):
        """Retorna o número de componentes legados deste template."""
        return obj.componentes.filter(ativo=True).count()

    num_componentes_legacy.short_description = "Componentes (Legacy)"

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
            blocks = DashboardBlock.objects.filter(
                template=obj, ativo=True
            ).select_related("datasource", "datasource__connection").order_by("order")

            # Se não tem blocos, tenta componentes legados
            if not blocks.exists():
                componentes = TemplateComponent.objects.filter(
                    template=obj, ativo=True
                ).select_related("datasource", "component_type", "datasource__connection")
                
                if not componentes.exists():
                    return format_html(
                        '<div style="padding: 15px; background: #fff3cd; border-radius: 5px;">'
                        "⚠️ Nenhum bloco ou componente adicionado ao template ainda. "
                        "Adicione blocos usando a seção acima."
                        "</div>"
                    )
                
                # Usa componentes legados
                return self._preview_legacy_components(componentes, obj, json_serializer)

            # Formata os resultados dos blocos
            html_parts = []
            html_parts.append(
                '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
            )

            # Informações gerais
            html_parts.append(
                '<h3 style="margin-top: 0;">📊 Preview dos Blocos</h3>'
            )
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
                
                if block.y_axis_fields:
                    y_axis_str = json.dumps(block.y_axis_fields, ensure_ascii=False)
                    html_parts.append(
                        f"<p><strong>Eixo Y:</strong> <code>{y_axis_str}</code></p>"
                    )

                try:
                    # Executa a query SEM filtro
                    success, result = block.datasource.execute_query(params=None)

                    if success:
                        num_records = len(result) if isinstance(result, list) else 0
                        html_parts.append(
                            f'<p style="color: green;"><strong>✅ {num_records} registro(s) encontrado(s)</strong></p>'
                        )

                        # Valida campos apenas se estiverem configurados
                        if block.x_axis_field and block.y_axis_fields and len(block.y_axis_fields) > 0 and num_records > 0:
                            is_valid, errors = block.validate_fields_against_query(result)
                            if is_valid:
                                html_parts.append(
                                    '<p style="color: green;">✓ Campos validados com sucesso</p>'
                                )
                                
                                # Mostra dados normalizados
                                try:
                                    normalized = block.normalize_data(result)
                                    normalized_preview = {
                                        "x": normalized["x"][:3] if len(normalized["x"]) > 0 else [],
                                        "series": [
                                            {
                                                **s,
                                                "values": s["values"][:3] if len(s["values"]) > 0 else []
                                            }
                                            for s in normalized["series"]
                                        ]
                                    }
                                    
                                    formatted_json = json.dumps(
                                        normalized_preview,
                                        indent=2,
                                        ensure_ascii=False,
                                        default=json_serializer,
                                    )
                                    formatted_json = formatted_json.replace("{", "{{").replace("}", "}}")
                                    
                                    html_parts.append("<details open>")
                                    html_parts.append(
                                        '<summary style="cursor: pointer; font-weight: bold; margin: 10px 0;">📄 Dados Normalizados (primeiros 3):</summary>'
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
                                        f'<p style="color: orange;">⚠️ Erro ao normalizar: {str(e)}</p>'
                                    )
                            else:
                                html_parts.append(
                                    '<div style="color: red; background: #ffebee; padding: 10px; border-radius: 3px; margin: 10px 0;">'
                                )
                                html_parts.append("<strong>❌ Erros de validação:</strong><ul>")
                                for error in errors:
                                    html_parts.append(f"<li>{error}</li>")
                                html_parts.append("</ul></div>")
                        elif num_records > 0:
                            # Bloco não configurado, mostra dados brutos
                            html_parts.append(
                                '<p style="color: orange;">⚠️ Configure os eixos X e Y para ver dados normalizados</p>'
                            )
                            preview_data = result[:3]
                            formatted_json = json.dumps(
                                preview_data,
                                indent=2,
                                ensure_ascii=False,
                                default=json_serializer,
                            )
                            formatted_json = formatted_json.replace("{", "{{").replace("}", "}}")
                            html_parts.append("<details>")
                            html_parts.append(
                                '<summary style="cursor: pointer; font-weight: bold; margin: 10px 0;">📄 Dados Brutos (primeiros 3):</summary>'
                            )
                            html_parts.append(
                                f'<pre style="background: white; padding: 10px; border: 1px solid #ddd; border-radius: 3px; overflow: auto; max-height: 300px;">{formatted_json}</pre>'
                            )
                            html_parts.append("</details>")
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
    
    def _preview_legacy_components(self, componentes, obj, json_serializer):
        """Preview para componentes legados."""
        import json
        
        html_parts = []
        html_parts.append(
            '<div style="font-family: monospace; background: #f5f5f5; padding: 15px; border-radius: 5px;">'
        )
        html_parts.append('<h3 style="margin-top: 0;">🔴 Preview dos Componentes LEGADOS</h3>')
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
            html_parts.append(f"<p><strong>DataSource:</strong> {componente.datasource.nome}</p>")
            
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
                            preview_data, indent=2, ensure_ascii=False, default=json_serializer
                        )
                        formatted_json = formatted_json.replace("{", "{{").replace("}", "}}")
                        html_parts.append("<details>")
                        html_parts.append('<summary style="cursor: pointer;">📄 Dados (3 primeiros)</summary>')
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
