% export_magnets_histogram  Extrae histograma de Magnets (mu0_const*mfnc.normM en T).
% Flujo identico a export_dataset para BFOV, solo cambia la seleccion (Magnets
% en lugar de FOV) y la expresion (mu0_const*mfnc.normM en T en lugar de mfnc.By en mT).
%
% Entradas:
%   model       (com.comsol.model.Model)
%   datasetTag  (char) - tag del dataset original, e.g. 'dset1'
%   outputPath  (char) - ruta completa del archivo TXT de salida
%   pngPath     (char, opcional) - ruta PNG del histograma
%   nBins       (double, opcional) - numero de bins (default 100)
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:exportMagnetsHistogram'
function export_magnets_histogram(model, datasetTag, outputPath, pngPath, nBins)
    if nargin < 4
        pngPath = '';
    end
    if nargin < 5 || isempty(nBins)
        nBins = 100;
    end

    nBins = floor(double(nBins));
    if ~isfinite(nBins) || nBins < 1
        nBins = 100;
    end

    newDsetTag  = ['dset_magnets_hist_' datasetTag];
    pg1dTag     = ['pg1d_magnets_hist_' datasetTag];
    plotHistTag = ['plothist_magnets_'  datasetTag];

    try
        cleanup_nodes(model, newDsetTag, pg1dTag, plotHistTag);

        % 1) Buscar selection Magnets en comp1 (mismo enfoque que FOV en export_dataset)
        magnetsTag = find_magnets_selection_tag(model);
        if isempty(magnetsTag)
            avail = list_comp1_selections(model);
            error(['No se encontro selection con label "Magnets" en Definitions (comp1).\n' ...
                   'Selections comp1: %s'], avail);
        end

        % 2) Duplicar dataset
        model.result.dataset.duplicate(newDsetTag, datasetTag);

        % 3) Asignar selection Magnets (identico a BFOV: geom1 dim3 + named)
        model.result.dataset(newDsetTag).selection.geom('geom1', 3);
        model.result.dataset(newDsetTag).selection.named(magnetsTag);

        % 4) PlotGroup1D con histograma (mismo patron que BFOV)
        model.result.create(pg1dTag, 'PlotGroup1D');
        try; model.result(pg1dTag).run; catch; end
        model.result(pg1dTag).set('data', newDsetTag);
        model.result(pg1dTag).create('hist1', 'Histogram');
        model.result(pg1dTag).feature('hist1').set('markerpos', 'datapoints');
        model.result(pg1dTag).feature('hist1').set('linewidth', 'preference');
        model.result(pg1dTag).feature('hist1').set('evaluationsettings', 'parent');
        model.result(pg1dTag).feature('hist1').set('expr', 'mu0_const*mfnc.normM');
        model.result(pg1dTag).feature('hist1').set('unit', 'T');
        model.result(pg1dTag).feature('hist1').set('number', nBins);
        model.result(pg1dTag).feature('hist1').set('function', 'discrete');
        model.result(pg1dTag).run;

        % TXT (mismo Plot export de hist1 que BFOV)
        model.result.export.create(plotHistTag, pg1dTag, 'hist1', 'Plot');
        model.result.export(plotHistTag).set('filename', outputPath);
        model.result.export(plotHistTag).run;

        % PNG via mphplot (COMSOL Image export no es estable en PlotGroup1D)
        if ~isempty(pngPath)
            export_hist_png_via_mphplot(model, pg1dTag, pngPath);
        end

    catch cause
        cleanup_nodes(model, newDsetTag, pg1dTag, plotHistTag);
        throw(MException('ComsolAnalyzer:exportMagnetsHistogram', ...
            'Error al exportar histograma Magnets para dataset "%s": %s', ...
            datasetTag, cause.message));
    end

    cleanup_nodes(model, newDsetTag, pg1dTag, plotHistTag);
end

% -------------------------------------------------------------------------
function cleanup_nodes(model, newDsetTag, pg1dTag, plotHistTag)
    try; model.result.export.remove(plotHistTag); catch; end
    try; model.result.remove(pg1dTag); catch; end
    try; model.result.dataset.remove(newDsetTag); catch; end
end

% -------------------------------------------------------------------------
% Busca selection con label "Magnets" en comp1.
% Mismo patron que find_fov_selection_tag en export_dataset:
% prioriza tipo Explicit, acepta cualquier tipo con label exacto.
% -------------------------------------------------------------------------
function magnetsTag = find_magnets_selection_tag(model)
    magnetsTag = '';
    try; tags = model.component('comp1').selection.tags(); catch; tags = []; end
    for i = 1:numel(tags)
        t   = char(tags(i));
        lbl = ''; typ = '';
        try; lbl = char(model.component('comp1').selection(t).label()); catch; end
        try; typ = char(model.component('comp1').selection(t).getType()); catch; end
        if strcmpi(strtrim(lbl), 'Magnets')
            if isempty(typ) || strcmpi(strtrim(typ), 'Explicit')
                magnetsTag = t;
                return;
            end
            if isempty(magnetsTag); magnetsTag = t; end
        end
    end
end

% -------------------------------------------------------------------------
function str = list_comp1_selections(model)
    parts = {};
    try; tags = model.component('comp1').selection.tags(); catch; tags = []; end
    for i = 1:numel(tags)
        t = char(tags(i));
        lbl = '?'; typ = '?';
        try; lbl = char(model.component('comp1').selection(t).label()); catch; end
        try; typ = char(model.component('comp1').selection(t).getType()); catch; end
        parts{end+1} = sprintf('%s(%s|%s)', t, lbl, typ); %#ok<AGROW>
    end
    if isempty(parts)
        str = '(ninguna encontrada)';
    else
        str = strjoin(parts, ', ');
    end
end

% -------------------------------------------------------------------------
function export_hist_png_via_mphplot(model, pg1dTag, pngPath)
    existingFigures = findall(0, 'Type', 'figure');
    fig = [];
    try
        mphplot(model, pg1dTag);
        drawnow;
        currentFigures = findall(0, 'Type', 'figure');
        newFigures = setdiff(currentFigures, existingFigures);
        if ~isempty(newFigures); fig = newFigures(1); else; fig = gcf; end
        try; set(fig, 'Visible', 'off'); catch; end
        drawnow;
        try
            exportgraphics(fig, pngPath, 'Resolution', 96);
        catch
            saveas(fig, pngPath);
        end
    catch cause
        try; if ~isempty(fig) && isvalid(fig); close(fig); end; catch; end
        rethrow(cause);
    end
    try; if ~isempty(fig) && isvalid(fig); close(fig); end; catch; end
end
