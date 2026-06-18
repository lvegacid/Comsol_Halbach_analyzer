% export_magnets_3d_plot  Exporta PNG y TXT 3D para Magnets (mu0_const*mfnc.normM en T).
% Flujo identico a export_dataset para BFOV, solo cambia la seleccion (Magnets
% en lugar de FOV) y la expresion (mu0_const*mfnc.normM en T en lugar de mfnc.By en mT).
%
% Entradas:
%   model         (com.comsol.model.Model)
%   datasetTag    (char) - tag del dataset fuente
%   outputPngPath (char) - ruta completa del PNG de salida
%   outputTxtPath (char, opcional) - ruta completa del TXT de salida
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:exportMagnets3DPlot'
function export_magnets_3d_plot(model, datasetTag, outputPngPath, outputTxtPath)
    if nargin < 4
        outputTxtPath = '';
    end

    newDsetTag = ['dset_magnets3d_' datasetTag];
    pg3dTag    = ['pg3d_magnets_'   datasetTag];
    imgTag     = ['img_magnets_'    datasetTag];
    plot3dTag  = ['plot3d_magnets_' datasetTag];

    try
        cleanup_nodes(model, newDsetTag, pg3dTag, imgTag, plot3dTag);

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

        % 4) Crear PlotGroup3D (mismo patron que BFOV)
        model.result.create(pg3dTag, 'PlotGroup3D');
        try; model.result(pg3dTag).run; catch; end
        model.result(pg3dTag).set('data', newDsetTag);
        model.result(pg3dTag).set('titletype', 'manual');
        model.result(pg3dTag).set('title', 'M (T)');
        model.result(pg3dTag).create('vol1', 'Volume');
        model.result(pg3dTag).feature('vol1').set('evaluationsettings', 'parent');
        model.result(pg3dTag).feature('vol1').set('expr', 'mu0_const*mfnc.normM');
        model.result(pg3dTag).feature('vol1').set('unit', 'T');
        model.result(pg3dTag).feature('vol1').set('colortable', 'Inferno');
        model.result(pg3dTag).run;

        % PNG via mphplot (COMSOL Image export.run en PlotGroup3D provoca NPE
        % que desconecta el servidor, inutilizando cualquier fallback posterior)
        ensure_parent_dir_exists(outputPngPath);
        export_png_via_mphplot(model, pg3dTag, outputPngPath);

        % TXT (mismo Plot export de vol1 que BFOV)
        if ~isempty(outputTxtPath)
            ensure_parent_dir_exists(outputTxtPath);
            model.result.export.create(plot3dTag, pg3dTag, 'vol1', 'Plot');
            model.result.export(plot3dTag).set('filename', outputTxtPath);
            model.result.export(plot3dTag).run;
        end

    catch cause
        cleanup_nodes(model, newDsetTag, pg3dTag, imgTag, plot3dTag);
        throw(MException('ComsolAnalyzer:exportMagnets3DPlot', ...
            'Error al exportar Magnets 3D plot para dataset "%s": %s', ...
            datasetTag, cause.message));
    end

    cleanup_nodes(model, newDsetTag, pg3dTag, imgTag, plot3dTag);
end

% -------------------------------------------------------------------------
function cleanup_nodes(model, newDsetTag, pg3dTag, imgTag, plot3dTag)
    try; model.result.export.remove(plot3dTag); catch; end
    try; model.result.export.remove(imgTag); catch; end
    try; model.result.remove(pg3dTag); catch; end
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
function ensure_parent_dir_exists(filePath)
    parentDir = fileparts(filePath);
    if isempty(parentDir); return; end
    if ~exist(parentDir, 'dir')
        [ok, msg] = mkdir(parentDir);
        if ~ok; error('No se pudo crear directorio de salida: %s', msg); end
    end
end


% -------------------------------------------------------------------------
function export_png_via_mphplot(model, pg3dTag, pngOutPath)
    existingFigures = findall(0, 'Type', 'figure');
    fig = [];
    try
        mphplot(model, pg3dTag);
        drawnow;
        currentFigures = findall(0, 'Type', 'figure');
        newFigures = setdiff(currentFigures, existingFigures);
        if ~isempty(newFigures); fig = newFigures(1); else; fig = gcf; end
        try; set(fig, 'Visible', 'off'); catch; end
        ensure_color_scale_visible(fig);
        drawnow;
        try
            exportgraphics(fig, pngOutPath, 'Resolution', 96);
        catch
            saveas(fig, pngOutPath);
        end
    catch cause
        try; if ~isempty(fig) && isvalid(fig); close(fig); end; catch; end
        rethrow(cause);
    end
    try; if ~isempty(fig) && isvalid(fig); close(fig); end; catch; end
end

% -------------------------------------------------------------------------
function ensure_color_scale_visible(fig)
    if isempty(fig) || ~isvalid(fig)
        return;
    end

    hasColorBar = ~isempty(findall(fig, 'Type', 'ColorBar'));
    if hasColorBar
        return;
    end

    ax = findall(fig, 'Type', 'Axes');
    if isempty(ax)
        return;
    end

    for i = 1:numel(ax)
        try
            colorbar(ax(i));
            return;
        catch
        end
    end
end
