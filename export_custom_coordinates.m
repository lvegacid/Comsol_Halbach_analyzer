function [outputDataPath, outputPngPath] = export_custom_coordinates(model, datasetTag, outputDir, coordCfg)
% export_custom_coordinates  Exporta B_FOV en coordenadas custom (esféricas).
%
% Entradas:
%   model       (com.comsol.model.Model)
%   datasetTag  (char)
%   outputDir   (char) — directorio destino del dataset
%   coordCfg    (struct) con campos:
%       .model  (char)   — solo "Spherical coordinates"
%       .nTheta (double)
%       .nPhi   (double)
%       .R      (double)  [m]
%
% Salidas:
%   outputDataPath  (char) — TXT con Bx, By, Bz, normB
%   outputPngPath   (char) — PNG de visualización rápida

    if nargin < 4 || ~isstruct(coordCfg)
        error('Se requiere coordCfg con model, nTheta, nPhi y R.');
    end

    coordModel = 'Spherical coordinates';
    if isfield(coordCfg, 'model') && ~isempty(coordCfg.model)
        coordModel = char(coordCfg.model);
    end
    if ~strcmpi(strtrim(coordModel), 'Spherical coordinates')
        error('Solo se soporta "Spherical coordinates" en esta versión.');
    end

    nTheta = get_struct_value(coordCfg, 'nTheta', 100);
    nPhi   = get_struct_value(coordCfg, 'nPhi', 100);
    rMeters = get_struct_value(coordCfg, 'R', 0.1);

    nTheta = floor(double(nTheta));
    nPhi   = floor(double(nPhi));
    rMeters = double(rMeters);

    if ~isfinite(nTheta) || nTheta < 1 || ~isfinite(nPhi) || nPhi < 1 || ...
       ~isfinite(rMeters) || rMeters <= 0
        error('Parámetros inválidos de coordenadas: nTheta, nPhi y R deben ser positivos.');
    end

    rMmToken = format_mm_token(rMeters * 1000);
    baseTag = sprintf('Spherical_coord_ntheta_%d_nphi_%d_R%smm', nTheta, nPhi, rMmToken);

    coordFileName = ['Coordinates_' baseTag '.txt'];
    dataFileName  = ['B_coordinates_' baseTag '.txt'];
    pngFileName   = ['B_coordinates_' baseTag '.png'];

    outputDataPath = fullfile(outputDir, dataFileName);
    outputPngPath  = fullfile(outputDir, pngFileName);
    coordFilePath  = build_temp_export_path('txt', ['coord_' datasetTag]);
    tempDataPath   = build_temp_export_path('txt', ['data_' datasetTag]);

    exportTag = ['data_' regexprep(datasetTag, '[^a-zA-Z0-9_]', '_')];

    try
        ensure_parent_dir_exists(outputDataPath);
        ensure_parent_dir_exists(outputPngPath);

        generate_spherical_coordinates_file(coordFilePath, nTheta, nPhi, rMeters);
        validate_generated_coordinate_file(coordFilePath, rMeters);

        try; model.result.export.remove(exportTag); catch; end

        model.result.export.create(exportTag, 'Data');
        model.result.export(exportTag).set('data', datasetTag);
        model.result.export(exportTag).set('location', 'file');
        model.result.export(exportTag).set('coordfilename', coordFilePath);
        model.result.export(exportTag).set('expr', {'mfnc.Bx' 'mfnc.By' 'mfnc.Bz' 'mfnc.normB'});
        model.result.export(exportTag).set('unit', {'mT' 'mT' 'mT' 'mT'});
        model.result.export(exportTag).set('descr', {'Bx' 'By' 'Bz' 'normB'});
        model.result.export(exportTag).set('filename', tempDataPath);
        model.result.export(exportTag).run;

        validate_exported_coordinate_radius(tempDataPath, rMeters);
        create_custom_coordinates_png(tempDataPath, outputPngPath);
        move_file_overwrite(tempDataPath, outputDataPath);

    catch cause
        try; model.result.export.remove(exportTag); catch; end
        try
            if exist(coordFilePath, 'file')
                delete(coordFilePath);
            end
        catch
        end
        try
            if exist(tempDataPath, 'file')
                delete(tempDataPath);
            end
        catch
        end
        throw(MException('ComsolAnalyzer:exportCustomCoordinates', ...
            'Error exportando coordenadas custom para dataset "%s": %s', ...
            datasetTag, cause.message));
    end

    try; model.result.export.remove(exportTag); catch; end

    % El archivo Coordinates_*.txt es temporal y se elimina al finalizar.
    try
        if exist(coordFilePath, 'file')
            delete(coordFilePath);
        end
    catch
    end
    try
        if exist(tempDataPath, 'file')
            delete(tempDataPath);
        end
    catch
    end
end

% -------------------------------------------------------------------------
function generate_spherical_coordinates_file(filePath, nTheta, nPhi, rMeters)
    theta = linspace(0, 2*pi, nTheta);
    phi = linspace(0, pi, nPhi);

    [thetaGrid, phiGrid] = meshgrid(theta, phi);

    x = rMeters .* sin(phiGrid) .* cos(thetaGrid);
    y = rMeters .* sin(phiGrid) .* sin(thetaGrid);
    z = rMeters .* cos(phiGrid);

    coords = [x(:), y(:), z(:)];
    writematrix(coords, filePath, 'Delimiter', 'tab');
end

% -------------------------------------------------------------------------
function validate_generated_coordinate_file(filePath, expectedRadiusMeters)
    coords = readmatrix(filePath, 'FileType', 'text');
    if isempty(coords) || size(coords, 2) < 3
        error('No se pudieron validar las coordenadas generadas en %s.', filePath);
    end

    radius = sqrt(sum(coords(:, 1:3).^2, 2));
    tolerance = max(1e-9, expectedRadiusMeters * 1e-9);
    maxDelta = max(abs(radius - expectedRadiusMeters));
    if ~isfinite(maxDelta) || maxDelta > tolerance
        error(['Las coordenadas generadas no corresponden a una esfera de radio %.9g m ' ...
            '(desviacion maxima %.3e m).'], expectedRadiusMeters, maxDelta);
    end
end

% -------------------------------------------------------------------------
function validate_exported_coordinate_radius(inputTxtPath, expectedRadiusMeters)
    data = readmatrix(inputTxtPath, 'FileType', 'text', 'CommentStyle', '%');

    if isempty(data) || size(data, 2) < 3
        error('No se pudieron validar las coordenadas exportadas en %s.', inputTxtPath);
    end

    coords = data(:, 1:3);
    radius = sqrt(sum(coords.^2, 2));
    maxRadius = max(radius);
    minRadius = min(radius);
    tolerance = max(5e-4, expectedRadiusMeters * 5e-3);

    if ~isfinite(maxRadius) || ~isfinite(minRadius)
        error('La exportacion de coordenadas contiene radios no finitos en %s.', inputTxtPath);
    end

    if abs(maxRadius - expectedRadiusMeters) > tolerance || ...
       abs(minRadius - expectedRadiusMeters) > tolerance
        error(['Radio exportado por COMSOL fuera de tolerancia. ' ...
            'R solicitado = %.6f m, radio minimo = %.6f m, radio maximo = %.6f m. ' ...
            'Revisa la unidad de longitud del modelo y las columnas exportadas.'], ...
            expectedRadiusMeters, minRadius, maxRadius);
    end
end

% -------------------------------------------------------------------------
function create_custom_coordinates_png(inputTxtPath, outputPngPath)
    data = readmatrix(inputTxtPath, 'FileType', 'text', 'CommentStyle', '%');

    if isempty(data) || size(data, 2) < 7
        error('No se pudo generar PNG de coordenadas: datos insuficientes en %s', inputTxtPath);
    end

    x = data(:, 1);
    y = data(:, 2);
    z = data(:, 3);
    byField = data(:, 5);

    fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 900 700]);
    ax = axes(fig);
    scatter3(ax, x, y, z, 48, byField, 'filled');
    grid(ax, 'on');
    xlabel(ax, 'X [m]');
    ylabel(ax, 'Y [m]');
    zlabel(ax, 'Z [m]');
    title(ax, 'B_FOV Custom Coordinates (By)', 'Interpreter', 'none');
    colormap(ax, inferno_colormap(256));
    cb = colorbar(ax);
    cb.Label.String = 'By [mT]';
    axis(ax, 'equal');
    view(ax, 3);

    exportgraphics(fig, outputPngPath, 'Resolution', 140);
    close(fig);
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
            error('No se pudo crear directorio de salida: %s', msg);
        end
    end
end

% -------------------------------------------------------------------------
function tempPath = build_temp_export_path(ext, tag)
    safeTag = regexprep(tag, '[^a-zA-Z0-9_]', '_');
    stamp = char(java.util.UUID.randomUUID());
    stamp = regexprep(stamp, '-', '');
    tempPath = fullfile(tempdir, sprintf('comsol_%s_%s.%s', safeTag, stamp, ext));
end

% -------------------------------------------------------------------------
function move_file_overwrite(srcPath, dstPath)
    if ~exist(srcPath, 'file')
        error('El archivo temporal de export no existe: %s', srcPath);
    end

    ensure_parent_dir_exists(dstPath);

    if exist(dstPath, 'file')
        delete(dstPath);
    end

    [ok, msg] = movefile(srcPath, dstPath, 'f');
    if ~ok
        error('No se pudo mover archivo temporal a destino final: %s', msg);
    end
end

% -------------------------------------------------------------------------
function value = get_struct_value(s, fieldName, defaultValue)
    if isfield(s, fieldName) && ~isempty(s.(fieldName))
        value = s.(fieldName);
    else
        value = defaultValue;
    end
end

% -------------------------------------------------------------------------
function token = format_mm_token(rMm)
    if abs(rMm - round(rMm)) < 1e-9
        token = sprintf('%d', round(rMm));
        return;
    end

    token = sprintf('%.6f', rMm);
    token = regexprep(token, '0+$', '');
    token = regexprep(token, '\.$', '');
    token = strrep(token, '.', 'p');
end
