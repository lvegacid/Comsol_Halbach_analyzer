% export_magnets_3d_plot  Exporta PNG y TXT 3D para Magnets.
% Flujo alineado con el export 3D BFOV (export_dataset):
%   1) Duplicar dataset
%   2) Asignar selection Magnets
%   3) Crear PlotGroup3D temporal
%   4) Asignar dataset duplicado
%   5) Crear Volume
%   6) expr = mu0_const*mfnc.normM
%   7) run del plot
%   8) Crear Marker en vol1
%   9) pointradius = 5
%  10) Exportar PNG con la misma estrategia de BFOV
%  11) Reutilizar cleanup
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

        % Marker requerido en el Volume plot
        model.result(pg3dTag).feature('vol1').create('mrkr1', 'Marker');
        model.result(pg3dTag).feature('vol1').feature('mrkr1').set('pointradius', 5);
        model.result(pg3dTag).run;

        % PNG con la misma estrategia usada por BFOV
        ensure_parent_dir_exists(outputPngPath);
        pngTempPath = build_temp_export_path('png', datasetTag);
        export_png_with_strategies(model, pg3dTag, imgTag, pngTempPath);
        try
            model.result(pg3dTag).run;
            model.result(pg3dTag).run;
        catch
        end
        move_file_overwrite(pngTempPath, outputPngPath);

        % Extiende con vistas ortograficas sin alterar el flujo 3D existente.
        try
            export_orthographic_views(model, pg3dTag, imgTag, outputPngPath, datasetTag);
        catch
        end

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
function tempPath = build_temp_export_path(ext, datasetTag)
    safeTag = regexprep(datasetTag, '[^a-zA-Z0-9_]', '_');
    stamp = char(java.util.UUID.randomUUID());
    stamp = regexprep(stamp, '-', '');
    fname = sprintf('comsol_%s_%s.%s', safeTag, stamp, ext);
    tempPath = fullfile(tempdir, fname);
end

% -------------------------------------------------------------------------
function move_file_overwrite(srcPath, dstPath)
    if ~exist(srcPath, 'file')
        error('El archivo temporal de export no existe: %s', srcPath);
    end

    dstDir = fileparts(dstPath);
    if ~isempty(dstDir) && ~exist(dstDir, 'dir')
        [ok, msg] = mkdir(dstDir);
        if ~ok
            error('No se pudo crear directorio destino: %s', msg);
        end
    end

    if exist(dstPath, 'file')
        delete(dstPath);
    end

    [ok, msg] = movefile(srcPath, dstPath, 'f');
    if ~ok
        error('No se pudo mover PNG temporal a destino final: %s', msg);
    end
end

% -------------------------------------------------------------------------
function export_orthographic_views(model, pg3dTag, imgTag, mainPngPath, datasetTag)
    [xyPath, yzPath, xzPath] = derive_orthographic_png_paths(mainPngPath);

    ensure_parent_dir_exists(xyPath);
    ensure_parent_dir_exists(yzPath);
    ensure_parent_dir_exists(xzPath);

    ensure_view2_exists(model);

    % Forzar que el PlotGroup3D use la misma vista de camara que ajustamos.
    try; model.result(pg3dTag).set('view', 'view2'); catch; end

    try; model.result.export.remove(imgTag); catch; end
    model.result.export.create(imgTag, pg3dTag, 'Image');
    model.result.export(imgTag).set('size', 'current');
    model.result.export(imgTag).set('unit', 'px');
    model.result.export(imgTag).set('height', '600');
    model.result.export(imgTag).set('width', '800');
    model.result.export(imgTag).set('lockratio', 'off');
    model.result.export(imgTag).set('resolution', '96');
    model.result.export(imgTag).set('antialias', 'on');
    model.result.export(imgTag).set('zoomextents', 'off');
    model.result.export(imgTag).set('fontsize', '12');
    model.result.export(imgTag).set('colortheme', 'globaltheme');
    model.result.export(imgTag).set('customcolor', [1 1 1]);
    model.result.export(imgTag).set('background', 'color');
    model.result.export(imgTag).set('gltfincludelines', 'on');
    model.result.export(imgTag).set('title1d', 'on');
    model.result.export(imgTag).set('legend1d', 'on');
    model.result.export(imgTag).set('logo1d', 'on');
    model.result.export(imgTag).set('options1d', 'on');
    model.result.export(imgTag).set('title2d', 'on');
    model.result.export(imgTag).set('legend2d', 'on');
    model.result.export(imgTag).set('logo2d', 'on');
    model.result.export(imgTag).set('options2d', 'off');
    model.result.export(imgTag).set('title3d', 'on');
    model.result.export(imgTag).set('legend3d', 'on');
    model.result.export(imgTag).set('logo3d', 'on');
    model.result.export(imgTag).set('options3d', 'on');
    model.result.export(imgTag).set('axisorientation', 'on');
    model.result.export(imgTag).set('grid', 'on');
    model.result.export(imgTag).set('axes1d', 'on');
    model.result.export(imgTag).set('axes2d', 'on');
    model.result.export(imgTag).set('showgrid', 'on');
    model.result.export(imgTag).set('target', 'file');
    model.result.export(imgTag).set('qualitylevel', '92');
    model.result.export(imgTag).set('qualityactive', 'off');
    model.result.export(imgTag).set('imagetype', 'png');
    model.result.export(imgTag).set('lockview', 'on');
    model.result.export(imgTag).set('highprecisioncolor', 'off');
    try; model.result.export(imgTag).set('view', 'view2'); catch; end

    % XY view
    model.component("comp1").view("view2").camera().set("projection", "orthographic");
    model.component("comp1").view("view2").camera().set("up", [0, 1, 0]);
    model.component("comp1").view("view2").camera().set("position", [0, 0, 1]);
    model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
    try; model.result(pg3dTag).run; catch; end
    export_orthographic_png_with_existing_export(model, imgTag, xyPath, [datasetTag '_xy']);

    % YZ view
    model.component("comp1").view("view2").camera().set("projection", "orthographic");
    model.component("comp1").view("view2").camera().set("position", [1, 0, 0]);
    model.component("comp1").view("view2").camera().set("up", [0, 0, 1]);
    model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
    try; model.result(pg3dTag).run; catch; end
    export_orthographic_png_with_existing_export(model, imgTag, yzPath, [datasetTag '_yz']);

    % XZ view
    model.component("comp1").view("view2").camera().set("projection", "orthographic");
    model.component("comp1").view("view2").camera().set("position", [0, 1, 0]);
    model.component("comp1").view("view2").camera().set("up", [0, 1, 0]);
    model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
    try; model.result(pg3dTag).run; catch; end
    export_orthographic_png_with_existing_export(model, imgTag, xzPath, [datasetTag '_xz']);

    try; model.result.export.remove(imgTag); catch; end
end

% -------------------------------------------------------------------------
function export_orthographic_png_with_existing_export(model, imgTag, finalPath, tempTag)
    pngTempPath = build_temp_export_path('png', tempTag);
    model.result.export(imgTag).set('pngfilename', pngTempPath);
    model.result.export(imgTag).run;
    move_file_overwrite(pngTempPath, finalPath);
end

% -------------------------------------------------------------------------
function [xyPath, yzPath, xzPath] = derive_orthographic_png_paths(mainPngPath)
    [folder, name, ext] = fileparts(mainPngPath);

    baseName = regexprep(name, '_3DPlot$', '');
    if strcmp(baseName, name)
        baseName = regexprep(name, '3DPlot$', '');
    end

    if strcmp(baseName, name)
        baseName = name;
    end

    xyPath = fullfile(folder, [baseName '_XY' ext]);
    yzPath = fullfile(folder, [baseName '_YZ' ext]);
    xzPath = fullfile(folder, [baseName '_XZ' ext]);
end

% -------------------------------------------------------------------------
function ensure_view2_exists(model)
    try
        model.component('comp1').view('view2');
    catch
        model.component('comp1').view().create('view2', 'geom1');
    end
end

% -------------------------------------------------------------------------
function export_png_with_strategies(model, pg3dTag, imgTag, pngOutPath)
    % Estrategia A: COMSOL Image export nativo con legend3d=on (incluye escala de color).
    try
        try; model.result.export.remove(imgTag); catch; end
        model.result.export.create(imgTag, pg3dTag, 'Image');
        model.result.export(imgTag).set('size', 'current');
        model.result.export(imgTag).set('unit', 'px');
        model.result.export(imgTag).set('height', '600');
        model.result.export(imgTag).set('width', '800');
        model.result.export(imgTag).set('lockratio', 'off');
        model.result.export(imgTag).set('resolution', '96');
        model.result.export(imgTag).set('antialias', 'on');
        model.result.export(imgTag).set('zoomextents', 'off');
        model.result.export(imgTag).set('fontsize', '12');
        model.result.export(imgTag).set('colortheme', 'globaltheme');
        model.result.export(imgTag).set('customcolor', [1 1 1]);
        model.result.export(imgTag).set('background', 'color');
        model.result.export(imgTag).set('gltfincludelines', 'on');
        model.result.export(imgTag).set('title1d', 'on');
        model.result.export(imgTag).set('legend1d', 'on');
        model.result.export(imgTag).set('logo1d', 'on');
        model.result.export(imgTag).set('options1d', 'on');
        model.result.export(imgTag).set('title2d', 'on');
        model.result.export(imgTag).set('legend2d', 'on');
        model.result.export(imgTag).set('logo2d', 'on');
        model.result.export(imgTag).set('options2d', 'off');
        model.result.export(imgTag).set('title3d', 'on');
        model.result.export(imgTag).set('legend3d', 'on');
        model.result.export(imgTag).set('logo3d', 'on');
        model.result.export(imgTag).set('options3d', 'on');
        model.result.export(imgTag).set('axisorientation', 'on');
        model.result.export(imgTag).set('grid', 'on');
        model.result.export(imgTag).set('axes1d', 'on');
        model.result.export(imgTag).set('axes2d', 'on');
        model.result.export(imgTag).set('showgrid', 'on');
        model.result.export(imgTag).set('target', 'file');
        model.result.export(imgTag).set('qualitylevel', '92');
        model.result.export(imgTag).set('qualityactive', 'off');
        model.result.export(imgTag).set('imagetype', 'png');
        model.result.export(imgTag).set('lockview', 'off');
        model.result.export(imgTag).set('highprecisioncolor', 'off');
        model.result.export(imgTag).set('pngfilename', pngOutPath);
        model.result.export(imgTag).run;
        try; model.result.export.remove(imgTag); catch; end
        return;
    catch errA
        try; model.result.export.remove(imgTag); catch; end
    end

    % Estrategia B (fallback): mphplot + exportgraphics.
    try
        export_png_via_mphplot(model, pg3dTag, pngOutPath);
        return;
    catch errB
        error('PNG COMSOL export.run fallo: %s | PNG mphplot fallo: %s', errA.message, errB.message);
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

        apply_export_axes_style(fig);
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

% -------------------------------------------------------------------------
function apply_export_axes_style(fig)
    if isempty(fig) || ~isvalid(fig)
        return;
    end

    ax = findall(fig, 'Type', 'Axes');
    if isempty(ax)
        return;
    end

    for i = 1:numel(ax)
        try
            grid(ax(i), 'on');
        catch
        end
        try
            ax(i).XGrid = 'on';
            ax(i).YGrid = 'on';
            ax(i).ZGrid = 'on';
        catch
        end
        try
            ax(i).Visible = 'on';
            box(ax(i), 'on');
        catch
        end
    end
end
