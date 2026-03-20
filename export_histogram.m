% Extrae el histograma BFOV (mfnc.By en mT) para el dataset dado
% y lo exporta como TXT tabulado en outputPath.
%
% Entradas:
%   model       (com.comsol.model.Model)
%   datasetTag  (char) — tag del dataset original, e.g. 'dset1'
%   outputPath  (char) — ruta completa del archivo TXT de salida
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:exportHistogram'
function export_histogram(model, datasetTag, outputPath)
    newDsetTag = ['dset_fov_' datasetTag];
    pg1dTag    = ['pg1d_hist_' datasetTag];
    exportTag  = ['plot_hist_' datasetTag];
    try
        % 1. Limpiar nodos previos si existen
        try; model.result.dataset.remove(newDsetTag); catch; end
        try; model.result.remove(pg1dTag);            catch; end
        try; model.result.export.remove(exportTag);   catch; end

        % 2. Encontrar el tag de la selección cuyo label es 'FOV'
        %    Las selecciones viven en model.component('comp1').selection
        %    o directamente en model.selection según la versión
        fovSelTag = find_selection_tag(model, 'FOV');
        if isempty(fovSelTag)
            error('No se encontró ninguna selección con label "FOV" en el modelo.');
        end

        % 3. Duplicar dataset: duplicate(newTag, sourceTag)
        model.result.dataset.duplicate(newDsetTag, datasetTag);

        % 4. Asignar selección FOV al dataset duplicado usando el tag real
        model.result.dataset(newDsetTag).selection.geom('geom1', 3);
        model.result.dataset(newDsetTag).selection.named(fovSelTag);

        % 5. Crear PlotGroup1D con histograma
        model.result.create(pg1dTag, 'PlotGroup1D');
        model.result(pg1dTag).set('data', newDsetTag);
        model.result(pg1dTag).create('hist1', 'Histogram');
        model.result(pg1dTag).feature('hist1').set('expr',     'mfnc.By');
        model.result(pg1dTag).feature('hist1').set('unit',     'mT');
        model.result(pg1dTag).feature('hist1').set('function', 'discrete');
        model.result(pg1dTag).feature('hist1').set('method',   'number');
        model.result(pg1dTag).feature('hist1').set('number',   100);
        model.result(pg1dTag).run;

        % 6. Exportar a TXT
        model.result.export.create(exportTag, pg1dTag, 'hist1', 'Plot');
        model.result.export(exportTag).set('filename', outputPath);
        model.result.export(exportTag).run;

    catch cause
        try; model.result.export.remove(exportTag);   catch; end
        try; model.result.remove(pg1dTag);            catch; end
        try; model.result.dataset.remove(newDsetTag); catch; end
        throw(MException('ComsolAnalyzer:exportHistogram', ...
            'Error al exportar histograma BFOV para dataset "%s": %s', ...
            datasetTag, cause.message));
    end

    % 7. Limpiar nodos temporales
    try; model.result.export.remove(exportTag);   catch; end
    try; model.result.remove(pg1dTag);            catch; end
    try; model.result.dataset.remove(newDsetTag); catch; end
end

% -------------------------------------------------------------------------
% Busca el tag de la selección cuyo label coincide con labelName.
% Busca primero en model.component('comp1').selection, luego en
% model.selection (para modelos sin componente explícito).
% -------------------------------------------------------------------------
function selTag = find_selection_tag(model, labelName)
    selTag = '';

    % Intentar vía componente comp1
    try
        tags = model.component('comp1').selection.tags();
        for i = 1:numel(tags)
            t = char(tags(i));
            lbl = char(model.component('comp1').selection(t).label());
            if strcmpi(strtrim(lbl), labelName)
                selTag = t;
                return;
            end
        end
    catch
    end

    % Fallback: vía model.selection directamente
    try
        tags = model.selection.tags();
        for i = 1:numel(tags)
            t = char(tags(i));
            lbl = char(model.selection(t).label());
            if strcmpi(strtrim(lbl), labelName)
                selTag = t;
                return;
            end
        end
    catch
    end
end
