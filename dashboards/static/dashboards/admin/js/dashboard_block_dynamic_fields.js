/**
 * Script para tornar os campos do DashboardBlock dinâmicos no Django Admin
 * 
 * Funcionalidades:
 * - Transforma campos de texto em select boxes populados com metadados da fonte
 * - Mostra/esconde granularidade baseado no tipo do campo selecionado
 * - Atualiza campos de série e agregações dinamicamente
 */

(function ($) {
    'use strict';

    console.log('🚀 Dashboard Block Dynamic Fields - Script carregado');

    // Cache de metadados das fontes de dados
    const metadataCache = {};

    /**
     * Obtém o CSRF token do Django
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Busca metadados da fonte de dados via API
     */
    async function fetchDataSourceMetadata(datasourceId) {
        console.log('📡 Buscando metadados para DataSource ID:', datasourceId);

        if (metadataCache[datasourceId]) {
            console.log('✅ Usando metadados do cache');
            return metadataCache[datasourceId];
        }

        try {
            const csrftoken = getCookie('csrftoken');
            const response = await fetch(`/api/datasources/${datasourceId}/metadata/`, {
                method: 'GET',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin'
            });

            console.log('📥 Response status:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('✅ Metadados recebidos:', data);

            metadataCache[datasourceId] = data;
            return data;
        } catch (error) {
            console.error('❌ Erro ao buscar metadados:', error);
            return null;
        }
    }

    /**
     * Cria um select box a partir de um input text
     */
    function createSelectFromInput(inputElement, options, placeholder = '--- Selecione ---') {
        const currentValue = inputElement.value;
        const select = $('<select>')
            .attr('id', inputElement.id)
            .attr('name', inputElement.name)
            .addClass(inputElement.className);

        // Opção placeholder
        select.append($('<option>').val('').text(placeholder));

        // Adiciona as opções
        options.forEach(opt => {
            const option = $('<option>')
                .val(opt.value)
                .text(opt.label)
                .data('meta', opt.meta || {});

            if (opt.value === currentValue) {
                option.prop('selected', true);
            }

            select.append(option);
        });

        // Substitui o input pelo select
        $(inputElement).replaceWith(select);
        return select;
    }

    /**
     * Atualiza o campo x_axis_field com select dinâmico
     */
    function updateXAxisField(metadata) {
        console.log('🔄 Atualizando campo X Axis...');

        const xAxisInput = $('#id_x_axis_field')[0];

        if (!xAxisInput) {
            console.log('⚠️ Campo x_axis_field não encontrado no DOM');
            return;
        }

        if (xAxisInput.tagName === 'SELECT') {
            console.log('⚠️ Campo x_axis_field já é um SELECT');
            return; // Já foi transformado
        }

        console.log('✅ Transformando x_axis_field em SELECT...');

        const options = metadata.columns.map(col => ({
            value: col.name,
            label: `${col.name} (${col.semantic_type})`,
            meta: col
        }));

        const select = createSelectFromInput(xAxisInput, options, '--- Selecione o campo do eixo X ---');

        console.log('✅ SELECT criado com', options.length, 'opções');

        // Quando mudar, atualiza a granularidade
        select.on('change', function () {
            console.log('📊 X Axis alterado:', $(this).val());
            updateGranularityField($(this).find(':selected').data('meta'));
        });

        // Dispara a atualização inicial se houver valor
        if (select.val()) {
            updateGranularityField(select.find(':selected').data('meta'));
        }
    }

    /**
     * Atualiza o campo series_field com select dinâmico
     */
    function updateSeriesField(metadata) {
        const seriesInput = $('#id_series_field')[0];
        if (!seriesInput || seriesInput.tagName === 'SELECT') {
            return; // Já foi transformado
        }

        // Para séries, aceitamos dimensions E campos que podem ser agrupados (não measures puros)
        // Isso inclui IDs (unit_id, customer_id, etc.) que são úteis para criar legendas
        const options = [
            { value: '', label: '(Sem agrupamento por série)', meta: {} }
        ].concat(
            metadata.columns
                .filter(col => {
                    // Aceita dimensions
                    if (col.semantic_type === 'dimension') return true;

                    // Aceita campos sem agregações definidas (provavelmente IDs ou categorias)
                    if (!col.allowed_aggregations || col.allowed_aggregations.length === 0) return true;

                    // Aceita measures que sejam inteiros (podem ser IDs ou contadores)
                    if (col.semantic_type === 'measure' && col.database_type &&
                        (col.database_type.includes('int') || col.database_type.includes('id'))) {
                        return true;
                    }

                    return false;
                })
                .map(col => ({
                    value: col.name,
                    label: `${col.name} (${col.semantic_type || 'field'})`,
                    meta: col
                }))
        );

        createSelectFromInput(seriesInput, options, '--- Opcional: campo para séries ---');
    }

    /**
     * Mostra/esconde o campo de granularidade baseado no tipo do campo X
     */
    function updateGranularityField(columnMeta) {
        const granularityRow = $('.form-row.field-x_axis_granularity');
        const granularityInput = $('#id_x_axis_granularity');

        if (!columnMeta || columnMeta.semantic_type !== 'datetime') {
            // Esconde e limpa se não for datetime
            granularityRow.hide();
            granularityInput.val('');
        } else {
            // Mostra e transforma em select se for datetime
            granularityRow.show();

            if (granularityInput[0] && granularityInput[0].tagName !== 'SELECT') {
                const currentValue = granularityInput.val();
                const options = [
                    { value: 'hour', label: 'Hora (DD/MM/YYYY HH:00)' },
                    { value: 'day', label: 'Dia (DD/MM/YYYY)' },
                    { value: 'week', label: 'Semana (Semana W, YYYY)' },
                    { value: 'month', label: 'Mês (MM/YYYY)' },
                    { value: 'quarter', label: 'Trimestre (QN/YYYY)' },
                    { value: 'year', label: 'Ano (YYYY)' }
                ];

                const select = createSelectFromInput(granularityInput[0], options, '--- Selecione a granularidade ---');

                // Se tinha valor anterior, restaura
                if (currentValue) {
                    select.val(currentValue);
                }
            }
        }
    }

    /**
     * Adiciona botão de helper para y_axis_aggregations
     */
    function enhanceYAxisAggregations(metadata) {
        const textareaWrapper = $('.form-row.field-y_axis_aggregations');
        if (!textareaWrapper.length) return;

        // Remove botão anterior se existir
        textareaWrapper.find('.aggregation-helper').remove();

        // Cria interface de helper
        const helperDiv = $('<div>')
            .addClass('aggregation-helper')
            .css({
                'margin-top': '10px',
                'padding': '15px',
                'background': '#f8f9fa',
                'border': '1px solid #dee2e6',
                'border-radius': '4px'
            });

        const title = $('<h4>')
            .text('📊 Assistente de Agregações')
            .css({ 'margin-top': '0', 'color': '#495057' });

        const addButton = $('<button>')
            .attr('type', 'button')
            .addClass('button')
            .css({ 'margin-bottom': '10px' })
            .text('➕ Adicionar Métrica')
            .on('click', function () {
                showAggregationDialog(metadata);
            });

        const info = $('<p>')
            .css({ 'margin': '10px 0 0 0', 'font-size': '12px', 'color': '#6c757d' })
            .html('<strong>Dica:</strong> Clique no botão para adicionar métricas de forma visual, ou edite o JSON diretamente.');

        helperDiv.append(title, addButton, info);
        textareaWrapper.append(helperDiv);
    }

    /**
     * Mostra diálogo para adicionar agregação
     */
    function showAggregationDialog(metadata) {
        const measureFields = metadata.columns.filter(col => col.semantic_type === 'measure');

        if (measureFields.length === 0) {
            alert('⚠️ Nenhum campo do tipo "measure" encontrado na fonte de dados.');
            return;
        }

        // Cria overlay
        const overlay = $('<div>')
            .css({
                'position': 'fixed',
                'top': '0',
                'left': '0',
                'width': '100%',
                'height': '100%',
                'background': 'rgba(0,0,0,0.5)',
                'z-index': '9999',
                'display': 'flex',
                'align-items': 'center',
                'justify-content': 'center'
            });

        const dialog = $('<div>')
            .css({
                'background': 'white',
                'padding': '30px',
                'border-radius': '8px',
                'min-width': '500px',
                'max-width': '600px',
                'box-shadow': '0 4px 6px rgba(0,0,0,0.1)'
            });

        const dialogTitle = $('<h3>').text('➕ Adicionar Métrica').css({ 'margin-top': '0' });

        // Campo: field
        const fieldLabel = $('<label>').text('Campo:').css({ 'display': 'block', 'margin-top': '15px', 'font-weight': 'bold' });
        const fieldSelect = $('<select>').css({ 'width': '100%', 'padding': '8px', 'margin-top': '5px' });
        fieldSelect.append($('<option>').val('').text('--- Selecione o campo ---'));
        measureFields.forEach(col => {
            fieldSelect.append($('<option>').val(col.name).text(`${col.name} (${col.data_type})`));
        });

        // Campo: aggregation
        const aggLabel = $('<label>').text('Agregação:').css({ 'display': 'block', 'margin-top': '15px', 'font-weight': 'bold' });
        const aggSelect = $('<select>').css({ 'width': '100%', 'padding': '8px', 'margin-top': '5px' });
        const aggregations = [
            { value: 'sum', label: 'Soma (sum)' },
            { value: 'avg', label: 'Média (avg)' },
            { value: 'count', label: 'Contagem (count)' },
            { value: 'count_distinct', label: 'Contagem Distinta (count_distinct)' },
            { value: 'min', label: 'Mínimo (min)' },
            { value: 'max', label: 'Máximo (max)' },
            { value: 'median', label: 'Mediana (median)' }
        ];
        aggregations.forEach(agg => {
            aggSelect.append($('<option>').val(agg.value).text(agg.label));
        });

        // Campo: label
        const labelLabel = $('<label>').text('Rótulo:').css({ 'display': 'block', 'margin-top': '15px', 'font-weight': 'bold' });
        const labelInput = $('<input>').attr('type', 'text').css({ 'width': '100%', 'padding': '8px', 'margin-top': '5px' });

        // Campo: axis
        const axisLabel = $('<label>').text('Eixo:').css({ 'display': 'block', 'margin-top': '15px', 'font-weight': 'bold' });
        const axisSelect = $('<select>').css({ 'width': '100%', 'padding': '8px', 'margin-top': '5px' });
        ['y1', 'y2'].forEach(axis => {
            axisSelect.append($('<option>').val(axis).text(axis.toUpperCase()));
        });

        // Botões
        const buttonContainer = $('<div>').css({ 'margin-top': '25px', 'text-align': 'right' });
        const cancelButton = $('<button>')
            .attr('type', 'button')
            .addClass('button')
            .text('Cancelar')
            .css({ 'margin-right': '10px' })
            .on('click', () => overlay.remove());

        const addButton = $('<button>')
            .attr('type', 'button')
            .addClass('button default')
            .text('Adicionar')
            .on('click', function () {
                const field = fieldSelect.val();
                const aggregation = aggSelect.val();
                const label = labelInput.val();
                const axis = axisSelect.val();

                if (!field || !aggregation || !label) {
                    alert('⚠️ Preencha todos os campos obrigatórios.');
                    return;
                }

                addAggregationToTextarea({ field, aggregation, label, axis });
                overlay.remove();
            });

        buttonContainer.append(cancelButton, addButton);

        dialog.append(
            dialogTitle,
            fieldLabel, fieldSelect,
            aggLabel, aggSelect,
            labelLabel, labelInput,
            axisLabel, axisSelect,
            buttonContainer
        );

        overlay.append(dialog);
        $('body').append(overlay);

        // Auto-preenche label quando selecionar campo
        fieldSelect.on('change', function () {
            if (!labelInput.val()) {
                const selectedField = $(this).val();
                const selectedAgg = aggSelect.val() || 'sum';
                labelInput.val(`${selectedAgg} de ${selectedField}`);
            }
        });

        aggSelect.on('change', function () {
            if (fieldSelect.val() && !labelInput.val()) {
                labelInput.val(`${$(this).val()} de ${fieldSelect.val()}`);
            }
        });
    }

    /**
     * Adiciona agregação ao textarea JSON
     */
    function addAggregationToTextarea(aggregation) {
        const textarea = $('#id_y_axis_aggregations');
        let currentValue = textarea.val().trim();
        let aggregations = [];

        // Parse do JSON atual
        if (currentValue) {
            try {
                aggregations = JSON.parse(currentValue);
            } catch (e) {
                console.error('JSON inválido no campo y_axis_aggregations:', e);
                aggregations = [];
            }
        }

        // Adiciona nova agregação
        aggregations.push(aggregation);

        // Atualiza o textarea com JSON formatado
        textarea.val(JSON.stringify(aggregations, null, 2));
    }

    /**
     * Inicializa os campos dinâmicos
     */
    async function initDynamicFields() {
        console.log('🔧 Inicializando campos dinâmicos...');

        const datasourceSelect = $('#id_datasource');

        if (!datasourceSelect.length) {
            console.log('⚠️ Campo datasource não encontrado');
            return;
        }

        console.log('✅ Campo datasource encontrado');

        const datasourceId = datasourceSelect.val();

        if (!datasourceId) {
            console.log('⚠️ Nenhuma fonte de dados selecionada');
            return;
        }

        console.log('✅ DataSource selecionado:', datasourceId);

        // Busca metadados
        const metadata = await fetchDataSourceMetadata(datasourceId);

        if (!metadata || !metadata.columns) {
            console.error('❌ Metadados inválidos ou não encontrados:', metadata);
            return;
        }

        console.log('✅ Metadados válidos, atualizando campos...');

        // Atualiza os campos
        updateXAxisField(metadata);
        updateSeriesField(metadata);
        enhanceYAxisAggregations(metadata);

        // Dispara atualização de granularidade se x_axis já estiver preenchido
        const xAxisSelect = $('#id_x_axis_field');
        if (xAxisSelect.val()) {
            const selectedMeta = xAxisSelect.find(':selected').data('meta');
            updateGranularityField(selectedMeta);
        }

        console.log('✅ Campos dinâmicos inicializados com sucesso!');
    }

    /**
     * Listener para mudança de DataSource
     */
    function setupDataSourceListener() {
        $('#id_datasource').on('change', function () {
            const datasourceId = $(this).val();

            if (datasourceId) {
                // Limpa cache e recarrega
                delete metadataCache[datasourceId];

                // Restaura campos para inputs normais antes de reprocessar
                ['#id_x_axis_field', '#id_series_field', '#id_x_axis_granularity'].forEach(selector => {
                    const field = $(selector);
                    if (field.length && field[0].tagName === 'SELECT') {
                        const input = $('<input>')
                            .attr('type', 'text')
                            .attr('id', field.attr('id'))
                            .attr('name', field.attr('name'))
                            .addClass(field.attr('class'))
                            .val(field.val());
                        field.replaceWith(input);
                    }
                });

                // Reinicializa
                initDynamicFields();
            }
        });
    }

    /**
     * Mostra/esconde campos baseado no tipo de gráfico selecionado
     */
    function updateFieldsVisibilityByChartType() {
        const chartType = $('#id_chart_type').val();
        console.log('📊 Chart type alterado para:', chartType);

        // Limpa mensagens de ajuda contextuais anteriores
        $('.table-help-text').remove();

        // Fieldsets e campos para controle de visibilidade
        const semanticFieldset = $('.form-row.field-x_axis_field').closest('fieldset');
        const metricFieldset = $('.form-row.field-metric_prefix').closest('fieldset');

        // Campos individuais da configuração semântica
        const xAxisRow = $('.form-row.field-x_axis_field');
        const granularityRow = $('.form-row.field-x_axis_granularity');
        const seriesRow = $('.form-row.field-series_field');
        const seriesLabelRow = $('.form-row.field-series_label');
        const yAxisRow = $('.form-row.field-y_axis_aggregations');

        // Campos de métrica
        const metricPrefixRow = $('.form-row.field-metric_prefix');
        const metricSuffixRow = $('.form-row.field-metric_suffix');
        const metricDecimalRow = $('.form-row.field-metric_decimal_places');

        if (chartType === 'metric') {
            // Tipo MÉTRICA/KPI
            console.log('🎯 Configurando para tipo Métrica/KPI');

            // Métricas/KPIs exibem apenas UM valor total agregado
            // Não precisam de eixo X (não há categorias/dimensões)
            // Apenas precisam de agregação Y (qual valor calcular)
            xAxisRow.hide();
            granularityRow.hide();
            seriesRow.hide();
            seriesLabelRow.hide();

            // Y axis é OBRIGATÓRIO (define qual métrica calcular)
            yAxisRow.show();

            // Mostra campos específicos de métrica
            metricFieldset.show();
            metricPrefixRow.show();
            metricSuffixRow.show();
            metricDecimalRow.show();

        } else if (chartType === 'bar' || chartType === 'barh' || chartType === 'line' || chartType === 'area') {
            // Tipos de gráfico com eixos X/Y tradicionais
            console.log('📊 Configurando para tipo Bar/BarH/Line/Area');

            // Mostra todos os campos semânticos
            xAxisRow.show();
            seriesRow.show();
            seriesLabelRow.show();
            yAxisRow.show();

            // Granularidade é mostrada condicionalmente pelo updateGranularityField
            // (se x_axis_field for datetime)
            const xAxisSelect = $('#id_x_axis_field');
            if (xAxisSelect.length && xAxisSelect[0].tagName === 'SELECT') {
                const selectedMeta = xAxisSelect.find(':selected').data('meta');
                updateGranularityField(selectedMeta);
            }

            // Esconde fieldset e campos de métrica
            metricFieldset.hide();
            metricPrefixRow.hide();
            metricSuffixRow.hide();
            metricDecimalRow.hide();

        } else if (chartType === 'pie') {
            // Tipo PIZZA
            console.log('🍰 Configurando para tipo Pizza');

            // Pizza usa x_axis como categorias e y_axis como valores
            xAxisRow.show();
            yAxisRow.show();

            // Esconde campos não utilizados
            granularityRow.hide();
            seriesRow.hide();
            seriesLabelRow.hide();

            // Esconde fieldset e campos de métrica
            metricFieldset.hide();
            metricPrefixRow.hide();
            metricSuffixRow.hide();
            metricDecimalRow.hide();

        } else if (chartType === 'table') {
            // Tipo TABELA
            console.log('📋 Configurando para tipo Tabela');

            // Tabela NÃO usa x_axis (é ignorado pelo QueryBuilder)
            xAxisRow.hide();
            granularityRow.hide();

            // series_field é OBRIGATÓRIO para tabelas (define as linhas)
            seriesRow.show();
            seriesLabelRow.show();  // Label amigável para a coluna de agrupamento

            // y_axis define as colunas (métricas)
            yAxisRow.show();

            // Esconde fieldset e campos de métrica
            metricFieldset.hide();
            metricPrefixRow.hide();
            metricSuffixRow.hide();
            metricDecimalRow.hide();

            // Adiciona mensagem de ajuda contextual para tabelas
            const seriesLabel = seriesRow.find('label.required');
            if (seriesLabel.length && !seriesLabel.find('.table-help-text').length) {
                seriesLabel.append(
                    '<span class="table-help-text" style="color: #d9534f; font-weight: bold; margin-left: 8px;">' +
                    '(Define as linhas da tabela - OBRIGATÓRIO para tabelas)' +
                    '</span>'
                );
            }

        } else {
            // Tipo desconhecido ou não selecionado - mostra campos semânticos, esconde métrica
            console.log('❓ Tipo desconhecido, mostrando campos padrão');

            xAxisRow.show();
            yAxisRow.show();
            seriesRow.show();
            seriesLabelRow.show();
            granularityRow.hide();

            // Esconde fieldset e campos de métrica por padrão
            metricFieldset.hide();
            metricPrefixRow.hide();
            metricSuffixRow.hide();
            metricDecimalRow.hide();
        }
    }

    /**
     * Configura listener para mudanças no campo chart_type
     */
    function setupChartTypeListener() {
        const chartTypeSelect = $('#id_chart_type');

        if (!chartTypeSelect.length) {
            console.log('⚠️ Campo chart_type não encontrado');
            return;
        }

        console.log('✅ Configurando listener para chart_type');

        // Listener para mudanças
        chartTypeSelect.on('change', updateFieldsVisibilityByChartType);

        // Executa imediatamente para configurar estado inicial
        updateFieldsVisibilityByChartType();
    }

    // Inicializa quando o DOM estiver pronto
    $(document).ready(function () {
        console.log('📄 DOM pronto, aguardando carregamento do Django Admin...');

        // Aguarda um pouco para garantir que o admin do Django carregou
        setTimeout(() => {
            console.log('⏰ Timeout completado, iniciando setup...');
            setupChartTypeListener();
            setupDataSourceListener();
            initDynamicFields();
        }, 500);
    });

})(django.jQuery || jQuery);
