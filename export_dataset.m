% export_dataset  Exporta PNG y TXT para un dataset usando el flujo COMSOL
% validado por el usuario.
%
% Flujo aplicado:
%   1) Buscar selection en Definitions con label "FOV" (comp1)
%   2) Duplicar dataset seleccionado
%   3) Asignar selection FOV al dataset duplicado
%   4) Crear PlotGroup3D y exportar PNG
%   5) Exportar TXT del plot 3D (vol1)
%   6) Crear PlotGroup1D (Histogram) y exportar TXT
%
% Entradas:
%   model       (com.comsol.model.Model)
%   datasetTag  (char)  tag del dataset original (ej. dset1)
%   txtPath     (char)  ruta TXT principal (histograma)
%   pngPath     (char)  ruta PNG
%
% Nota:
%   Ademas del TXT principal (histograma), se genera un TXT extra para el
%   plot 3D con sufijo "_plot3d".
function export_dataset(model, datasetTag, txtPath, pngPath)

    newDsetTag   = ['dset_fov_' datasetTag];
    pg3dTag      = ['pg3d_' datasetTag];
    imgTag       = ['img_' datasetTag];
    plot3dTag    = ['plot3d_' datasetTag];
    pg1dTag      = ['pg1d_' datasetTag];
    plotHistTag  = ['plothist_' datasetTag];

    try
        cleanup(model, newDsetTag, pg3dTag, imgTag, plot3dTag, pg1dTag, plotHistTag);

        % Validar conexion del modelo antes de comenzar.
        assert_model_connected(model, 'inicio export_dataset');

        % Validar dataset origen recibido desde la GUI.
        assert_dataset_exists(model, datasetTag, 'origen');

        % 1) FOV en Definitions (comp1)
        fovTag = find_fov_selection_tag(model);
        if isempty(fovTag)
            avail = list_comp1_selections(model);
            error(['No se encontro selection con label "FOV" en Definitions (comp1).\n' ...
                   'Selections comp1: %s'], avail);
        end

        % 2) Duplicar dataset
        try
            model.result.dataset.duplicate(newDsetTag, datasetTag);
        catch errStage
            error('Fallo al duplicar dataset (%s -> %s): %s', datasetTag, newDsetTag, errStage.message);
        end

        assert_dataset_exists(model, newDsetTag, 'duplicado');

        % 3) Asignar selection FOV al dataset duplicado
        try
            model.result.dataset(newDsetTag).selection.geom('geom1', 3);
            model.result.dataset(newDsetTag).selection.named(fovTag);
        catch errStage
            error('Fallo al asignar selection FOV (%s) al dataset %s: %s', fovTag, newDsetTag, errStage.message);
        end

        % 4) PlotGroup3D + PNG (mismo flujo del script de referencia)
        try
            model.result.create(pg3dTag, 'PlotGroup3D');
        catch errStage
            error('Fallo al crear PlotGroup3D (%s): %s', pg3dTag, errStage.message);
        end

        % Este run inicial forma parte del script de referencia, pero en
        % algunos datasets puede fallar sin afectar el flujo principal.
        try
            model.result(pg3dTag).run;
        catch
        end

        try
            model.result(pg3dTag).set('data', newDsetTag);
            model.result(pg3dTag).create('vol1', 'Volume');
            model.result(pg3dTag).feature('vol1').set('evaluationsettings', 'parent');
            model.result(pg3dTag).feature('vol1').set('expr', 'mfnc.By');
            model.result(pg3dTag).feature('vol1').set('unit', 'mT');
            model.result(pg3dTag).feature('vol1').set('colortable', 'Inferno');
            model.result(pg3dTag).run;
        catch errStage
            error('Fallo al configurar/ejecutar PlotGroup3D %s: %s', pg3dTag, errStage.message);
        end

        % Marker y runs extra: mantener logica del script, pero como paso
        % opcional para evitar caidas en datasets que no soporten marker.
        try
            model.result(pg3dTag).feature('vol1').create('mrkr1', 'Marker');
            model.result(pg3dTag).run;
            model.result(pg3dTag).run;
            model.result(pg3dTag).run;
            model.result(pg3dTag).run;
        catch
        end

        try
            ensure_parent_dir_exists(pngPath);
            pngTempPath = build_temp_export_path('png', datasetTag);
            export_png_with_strategies(model, pg3dTag, imgTag, pngTempPath);
            try
                model.result(pg3dTag).run;
                model.result(pg3dTag).run;
            catch
            end
            move_file_overwrite(pngTempPath, pngPath);
        catch errStage
            error('Fallo al exportar PNG (%s): %s', pngPath, errStage.message);
        end

        % 5) TXT del plot 3D (vol1)
        try
            txtPlot3dPath = derive_plot3d_txt_path_from_png(pngPath);
            model.result.export.create(plot3dTag, pg3dTag, 'vol1', 'Plot');
            model.result.export(plot3dTag).set('filename', txtPlot3dPath);
            model.result.export(plot3dTag).run;
        catch errStage
            error('Fallo al exportar TXT 3D (%s): %s', datasetTag, errStage.message);
        end

        % 6) PlotGroup1D Hist + TXT principal
        try
            model.result.create(pg1dTag, 'PlotGroup1D');
            model.result(pg1dTag).run;
            model.result(pg1dTag).set('data', newDsetTag);
            model.result(pg1dTag).create('hist1', 'Histogram');
            model.result(pg1dTag).feature('hist1').set('markerpos', 'datapoints');
            model.result(pg1dTag).feature('hist1').set('linewidth', 'preference');
            model.result(pg1dTag).feature('hist1').set('evaluationsettings', 'parent');
            model.result(pg1dTag).feature('hist1').set('expr', 'mfnc.By');
            model.result(pg1dTag).feature('hist1').set('unit', 'mT');
            model.result(pg1dTag).feature('hist1').set('number', 100);
            model.result(pg1dTag).feature('hist1').set('function', 'discrete');
            model.result(pg1dTag).run;

            model.result.export.create(plotHistTag, pg1dTag, 'hist1', 'Plot');
            model.result.export(plotHistTag).set('filename', txtPath);
            model.result.export(plotHistTag).run;
        catch errStage
            error('Fallo al exportar histograma TXT (%s): %s', datasetTag, errStage.message);
        end

    catch cause
        cleanup(model, newDsetTag, pg3dTag, imgTag, plot3dTag, pg1dTag, plotHistTag);
        throw(MException('ComsolAnalyzer:exportDataset', ...
            'Error exportando dataset "%s": %s', datasetTag, cause.message));
    end

    cleanup(model, newDsetTag, pg3dTag, imgTag, plot3dTag, pg1dTag, plotHistTag);
end

% -------------------------------------------------------------------------
function fovTag = find_fov_selection_tag(model)
    fovTag = '';

    try
        tags = model.component('comp1').selection.tags();
    catch
        tags = [];
    end

    for i = 1:numel(tags)
        t = char(tags(i));

        lbl = '';
        typ = '';
        try
            lbl = char(model.component('comp1').selection(t).label());
        catch
        end
        try
            typ = char(model.component('comp1').selection(t).getType());
        catch
        end

        if strcmpi(strtrim(lbl), 'FOV')
            % Priorizar Explicit, pero aceptar si el label coincide exacto.
            if isempty(typ) || strcmpi(strtrim(typ), 'Explicit')
                fovTag = t;
                return;
            end
            if isempty(fovTag)
                fovTag = t;
            end
        end
    end
end

% -------------------------------------------------------------------------
function str = list_comp1_selections(model)
    parts = {};

    try
        tags = model.component('comp1').selection.tags();
    catch
        tags = [];
    end

    for i = 1:numel(tags)
        t = char(tags(i));
        lbl = '?';
        typ = '?';
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
function outPath = derive_plot3d_txt_path_from_png(pngPath)
    [folder, name, ~] = fileparts(pngPath);
    % Ejemplo: BFOV_Linear_model.png -> BFOV_Linear_model.txt
    outPath = fullfile(folder, [name '.txt']);
end

% -------------------------------------------------------------------------
function ensure_parent_dir_exists(filePath)
    parentDir = fileparts(filePath);
    if isempty(parentDir)
        return;
    end
    if ~exist(parentDir, 'dir')
        [ok, msg] = mkdir(parentDir);
        if ~ok
            error('No se pudo crear directorio de salida para PNG: %s', msg);
        end
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
        model.result.export(imgTag).set('fontsize', '9');
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
        model.result.export(imgTag).set('options3d', 'off');
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
        if ~isempty(newFigures)
            fig = newFigures(1);
        else
            fig = gcf;
        end

        try
            set(fig, 'Visible', 'off');
        catch
        end

        ensure_color_scale_visible(fig);
        drawnow;
        try
            exportgraphics(fig, pngOutPath, 'Resolution', 96);
        catch
            saveas(fig, pngOutPath);
        end
    catch cause
        try
            if ~isempty(fig) && isvalid(fig)
                close(fig);
            end
        catch
        end
        rethrow(cause);
    end
    try
        if ~isempty(fig) && isvalid(fig)
            close(fig);
        end
    catch
    end
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
function assert_dataset_exists(model, tag, whichOne)
    assert_model_connected(model, ['validacion dataset ' whichOne]);
    if ~dataset_exists(model, tag)
        availDsets = list_result_datasets(model);
        error('El dataset %s "%s" no existe en model.result.dataset. Datasets disponibles: %s', ...
            whichOne, tag, availDsets);
    end
end

% -------------------------------------------------------------------------
function tf = dataset_exists(model, tag)
    tf = false;
    try
        model.result.dataset(tag);
        tf = true;
    catch
        tf = false;
    end
end

% -------------------------------------------------------------------------
function assert_model_connected(model, context)
    try
        model.result.dataset.tags();
    catch err
        error('Sesion COMSOL no conectada durante "%s": %s', context, err.message);
    end
end

% -------------------------------------------------------------------------
function str = list_result_datasets(model)
    parts = {};
    try
        tags = model.result.dataset.tags();
    catch err
        str = ['(no disponible: ' err.message ')'];
        return;
    end

    for i = 1:numel(tags)
        t = char(tags(i));
        lbl = '?';
        try
            lbl = char(model.result.dataset(t).label());
        catch
        end
        parts{end+1} = sprintf('%s(%s)', t, lbl); %#ok<AGROW>
    end

    if isempty(parts)
        str = '(ninguno encontrado)';
    else
        str = strjoin(parts, ', ');
    end
end

% -------------------------------------------------------------------------
function cleanup(model, newDsetTag, pg3dTag, imgTag, plot3dTag, pg1dTag, plotHistTag)
    try; model.result.export.remove(plotHistTag); catch; end
    try; model.result.export.remove(plot3dTag);   catch; end
    try; model.result.export.remove(imgTag);      catch; end
    try; model.result.remove(pg1dTag);            catch; end
    try; model.result.remove(pg3dTag);            catch; end
    try; model.result.dataset.remove(newDsetTag); catch; end
end
