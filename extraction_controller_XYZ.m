function summary = extraction_controller_XYZ(model, datasets, outputDir, modelName, logFn, progressFn, fovInfo, options)
% extraction_controller  Orquesta la extracción para cada dataset seleccionado.
%
% Para cada dataset: crea carpeta, construye rutas, llama a export_dataset
% (que duplica el dataset, asigna FOV, exporta PNG y TXT).
% Errores por dataset son capturados: se loguean y se continúa.
%
% Entradas:
%   model       (com.comsol.model.Model)
%   datasets    (struct array) con campos .tag, .label, .shortLabel
%   outputDir   (char)
%   modelName   (char) — nombre del .mph sin extensión
%   logFn       (function_handle) — logFn(level, timestamp, tag, message)
%   progressFn  (function_handle) — progressFn(current, total)
%   fovInfo     (char, opcional) — texto para FOV_info en postproceso Python
%
% Salidas:
%   summary.nOK, summary.nError, summary.outputDir

    if nargin < 8 || isempty(options)
        options = default_extraction_options();
    else
        options = normalize_extraction_options(options);
    end

    recoveryFn = [];
    if isfield(options, 'connectionRecoveryFn') && isa(options.connectionRecoveryFn, 'function_handle')
        recoveryFn = options.connectionRecoveryFn;
    end

    nTotal = numel(datasets);
    nOK    = 0;
    nError = 0;

    for i = 1:nTotal
        ds = datasets(i);

        % Pre-dataset connection probe: detect stale connection before any export call
        connStatus = comsol_livelink_connection('status');
        if ~connStatus.connected
            recovered = false;
            if ~isempty(recoveryFn)
                [recovered, model, recoveryDetail] = try_recover_model(recoveryFn, model);
                if recovered
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('INFO', ts, ds.tag, 'Reconexion y recarga de modelo exitosas antes de exportar dataset.');
                else
                    connStatus = comsol_livelink_connection('connect');
                    if ~connStatus.connected && ~isempty(strtrim(recoveryDetail))
                        connStatus.detail = recoveryDetail;
                    end
                end
            else
                connStatus = comsol_livelink_connection('connect');
            end

            if ~recovered && ~connStatus.connected
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('WARN', ts, ds.tag, ...
                    'LiveLink desconectado al inicio del dataset. No se pudo reconectar. Se detiene el lote.');
                if ~isempty(strtrim(connStatus.detail))
                    logFn('WARN', ts, ds.tag, ['Detalle de reconexion: ' connStatus.detail]);
                end
                progressFn(i, nTotal);
                break;
            end
            if ~recovered
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('INFO', ts, ds.tag, 'Reconexion LiveLink exitosa antes de exportar dataset.');
            end
        end

        try
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('Preparando dataset %d de %d: %s', i, nTotal, ds.shortLabel));

            % Crear carpeta usando shortLabel
            folderPath = create_output_folder(outputDir, modelName, ds.shortLabel, ds.tag);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('Carpeta de salida lista: %s', folderPath));

            if options.domainMode
                for selIdx = 1:numel(options.domainSelections)
                    selectedDomain = options.domainSelections(selIdx);
                    run_bfov_exports(model, ds, folderPath, modelName, fovInfo, options, logFn, selectedDomain);
                end
            else
                run_bfov_exports(model, ds, folderPath, modelName, fovInfo, options, logFn, []);
            end

            if options.enableMagnets3DPlot || options.enableMagnetsHistogram
                run_magnets_exports(model, ds, folderPath, modelName, options, logFn);
            end

            nOK = nOK + 1;
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('OK → %s', folderPath));

        catch err
            nError = nError + 1;
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('ERROR', ts, ds.tag, err.message);

            if is_not_connected_error(err)
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('WARN', ts, ds.tag, ...
                    'LiveLink se desconecto durante la exportacion. Intentando reconexion...');

                recovered = false;
                recoveryDetail = '';
                if ~isempty(recoveryFn)
                    [recovered, model, recoveryDetail] = try_recover_model(recoveryFn, model);
                end

                if recovered
                    nError = nError - 1;  % undo error count; will retry this dataset
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('INFO', ts, ds.tag, 'Reconexion y recarga de modelo exitosas. Reintentando dataset...');
                    progressFn(i, nTotal);
                    continue;
                else
                    reconnStatus = comsol_livelink_connection('connect');
                    if ~reconnStatus.connected && ~isempty(strtrim(recoveryDetail))
                        reconnStatus.detail = recoveryDetail;
                    end

                    if reconnStatus.connected
                        nError = nError - 1;  % undo error count; will retry this dataset
                        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                        logFn('INFO', ts, ds.tag, 'Reconexion exitosa. Reintentando dataset...');
                        progressFn(i, nTotal);
                        continue;
                    end

                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ...
                        'No se pudo reconectar con el servidor COMSOL. Se detiene el lote.');
                    if ~isempty(strtrim(reconnStatus.detail))
                        logFn('WARN', ts, ds.tag, ['Detalle de reconexion: ' reconnStatus.detail]);
                    end
                    progressFn(i, nTotal);
                    break;
                end
            end
        end

        progressFn(i, nTotal);
    end

    summary.nOK      = nOK;
    summary.nError   = nError;
    summary.outputDir = outputDir;
end

% -------------------------------------------------------------------------
function [ok, modelOut, detail] = try_recover_model(recoveryFn, modelIn)
    ok = false;
    modelOut = modelIn;
    detail = '';

    try
        recoveryResult = recoveryFn();
        if isstruct(recoveryResult)
            if isfield(recoveryResult, 'connected') && logical(recoveryResult.connected)
                ok = true;
            end
            if isfield(recoveryResult, 'model') && ~isempty(recoveryResult.model)
                modelOut = recoveryResult.model;
            end
            if isfield(recoveryResult, 'detail')
                detail = char(string(recoveryResult.detail));
            end
        elseif islogical(recoveryResult) || isnumeric(recoveryResult)
            ok = logical(recoveryResult);
        end
    catch err
        detail = err.message;
    end
end

% -------------------------------------------------------------------------
function options = default_extraction_options()
    options.enable3DPlot = true;
    options.enableHistogram = true;
    options.enableCustomCoordinates = false;
    options.fieldAxis = 'Z'; % 'X' | 'Y' | 'Z' — componente de B a extraer
    options.enableMagnets3DPlot = false;
    options.enableMagnetsHistogram = false;
    options.projectionOrthoScale = 0.35;
    options.domainMode = false;
    options.domainSelections = struct('tag', {}, 'label', {});
    options.histBins = 100;
    options.magnetsHistBins = 100;
    options.magnetsStepPercent = 2;
    options.magnetsBr = 1.4;
    options.magnetsHistogram = struct( ...
        'bins', 100, ...
        'stepPercent', 2, ...
        'br', 1.4, ...
        'normMEnabled', true, ...
        'normHEnabled', false, ...
        'normH', struct( ...
            'enabled', false, ...
            'Hcb', [], ...
            'Hcj', [], ...
            'Hknee', [], ...
            'Hlinear_end', [], ...
            'extraH', struct('name', {}, 'value', {})));
    options.normH = options.magnetsHistogram.normH;
    options.coordConfig = struct('model', 'Spherical coordinates', ...
        'source', 'spherical', ...
        'nTheta', 100, 'nPhi', 100, 'R', 0.1, ...
        'coordFilePath', '', ...
        'coordColumns', [1 2 3], ...
        'sourceFilePath', '');
end

% -------------------------------------------------------------------------
function options = normalize_extraction_options(options)
    defaults = default_extraction_options();
    fields = fieldnames(defaults);
    for i = 1:numel(fields)
        f = fields{i};
        if ~isfield(options, f)
            options.(f) = defaults.(f);
        end
    end

    if ~isstruct(options.coordConfig)
        options.coordConfig = defaults.coordConfig;
    end

    cfgFields = fieldnames(defaults.coordConfig);
    for i = 1:numel(cfgFields)
        f = cfgFields{i};
        if ~isfield(options.coordConfig, f)
            options.coordConfig.(f) = defaults.coordConfig.(f);
        end
    end

    if isfield(options.coordConfig, 'coordColumns')
        options.coordConfig.coordColumns = double(options.coordConfig.coordColumns(:).');
    end

    if ~isstruct(options.magnetsHistogram)
        options.magnetsHistogram = defaults.magnetsHistogram;
    end

    mhFields = fieldnames(defaults.magnetsHistogram);
    for i = 1:numel(mhFields)
        f = mhFields{i};
        if ~isfield(options.magnetsHistogram, f)
            options.magnetsHistogram.(f) = defaults.magnetsHistogram.(f);
        end
    end

    if ~isstruct(options.magnetsHistogram.normH)
        options.magnetsHistogram.normH = defaults.magnetsHistogram.normH;
    end

    normHFields = fieldnames(defaults.magnetsHistogram.normH);
    for i = 1:numel(normHFields)
        f = normHFields{i};
        if ~isfield(options.magnetsHistogram.normH, f)
            options.magnetsHistogram.normH.(f) = defaults.magnetsHistogram.normH.(f);
        end
    end

    if ~isfield(options, 'normH') || ~isstruct(options.normH)
        options.normH = options.magnetsHistogram.normH;
    end

    if ~isfield(options, 'fieldAxis') || isempty(options.fieldAxis) || ...
            ~ismember(upper(char(options.fieldAxis)), {'X', 'Y', 'Z'})
        options.fieldAxis = 'Z';
    else
        options.fieldAxis = upper(char(options.fieldAxis));
    end

    options.magnetsHistogram.bins = options.magnetsHistBins;
    options.magnetsHistogram.stepPercent = options.magnetsStepPercent;
    options.magnetsHistogram.br = options.magnetsBr;
end

% -------------------------------------------------------------------------
function run_bfov_exports(model, ds, folderPath, modelName, fovInfo, options, logFn, selectedDomain)
    useDomainSelection = ~isempty(selectedDomain);

    safeDatasetName = make_safe_name(ds.shortLabel);
    [histTxtPath, plot3dPngPath] = build_output_paths(folderPath, safeDatasetName, modelName);
    selectionTag = '';
    selectionLabel = '';
    titleText = '';
    customCoordPrefix = '';
    customLogPrefix = 'B_FOV';
    fovInfoForPython = fovInfo;
    analysisName = ds.shortLabel;

    if useDomainSelection
        selectionTag = selectedDomain.tag;
        selectionLabel = selectedDomain.label;
        titleText = selectionLabel;
        safeSelectionLabel = make_safe_name(selectionLabel);
        if isempty(safeSelectionLabel)
            safeSelectionLabel = make_safe_name(selectionTag);
        end

        histTxtPath = fullfile(folderPath, sprintf('B_%s_Histogram_%s.txt', safeSelectionLabel, modelName));
        plot3dPngPath = fullfile(folderPath, sprintf('B_%s_3DPlot_%s.png', safeSelectionLabel, modelName));
        customCoordPrefix = sprintf('B_%s_CustomCoordinates_%s', safeSelectionLabel, modelName);
        customLogPrefix = ['B_' selectionLabel];
        fovInfoForPython = selectionLabel;
        analysisName = selectionLabel;
    end

    doMainExports = logical(options.enable3DPlot) || logical(options.enableHistogram);
    if doMainExports
        % Flujo historico estable: export_dataset + postproceso Python
        if useDomainSelection
            export_dataset_XYZ(model, ds.tag, histTxtPath, plot3dPngPath, selectionTag, titleText, options.histBins, options.projectionOrthoScale, options.fieldAxis);
        else
            export_dataset_XYZ(model, ds.tag, histTxtPath, plot3dPngPath, '', '', options.histBins, options.projectionOrthoScale, options.fieldAxis);
        end
    end

    if options.enableHistogram
        try
            run_bfov_python_postprocess(histTxtPath, modelName, fovInfoForPython, analysisName, options.fieldAxis);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, 'Postproceso BFOV Python completado.');
        catch postErr
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('WARN', ts, ds.tag, ['Postproceso BFOV no ejecutado (PNG del histograma NO generado): ' ...
                compact_python_error(postErr.message)]);
            if contains(lower(postErr.message), 'modulenotfounderror') || ...
               contains(lower(postErr.message), 'importerror') || ...
               contains(lower(postErr.message), 'no module named')
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('WARN', ts, ds.tag, ...
                    'Instala dependencias Python (numpy, matplotlib). Ejemplo: python -m pip install numpy matplotlib');
            end
        end
    end

    if options.enableCustomCoordinates
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        if isfield(options.coordConfig, 'source') && strcmpi(options.coordConfig.source, 'file')
            sourceFileName = '';
            if isfield(options.coordConfig, 'sourceFilePath') && ~isempty(options.coordConfig.sourceFilePath)
                [~, sourceFileName, ext] = fileparts(options.coordConfig.sourceFilePath);
                sourceFileName = [sourceFileName ext];
            end
            logFn('INFO', ts, ds.tag, sprintf(['Iniciando exportación %s Custom Coordinates ' ...
                '(From file: %s | cols=%s)...'], customLogPrefix, sourceFileName, mat2str(options.coordConfig.coordColumns)));
        else
            logFn('INFO', ts, ds.tag, sprintf(['Iniciando exportación %s Custom Coordinates ' ...
                '(nTheta=%d, nPhi=%d, R=%.6f m)...'], ...
                customLogPrefix, options.coordConfig.nTheta, options.coordConfig.nPhi, options.coordConfig.R));
        end

        coordCfg = options.coordConfig;
        coordCfg.fieldAxis = options.fieldAxis;
        if useDomainSelection
            coordCfg.plotTitle = titleText;
            coordCfg.outputBaseName = customCoordPrefix;
            [coordTxtPath, coordPngPath] = export_custom_coordinates_XYZ(model, ds.tag, folderPath, coordCfg, selectionTag);
        else
            [coordTxtPath, coordPngPath] = export_custom_coordinates_XYZ(model, ds.tag, folderPath, coordCfg);
        end

        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf('%s Custom Coordinates exportado: %s | %s', ...
            customLogPrefix, coordTxtPath, coordPngPath));
    end
end

% -------------------------------------------------------------------------
function run_magnets_exports(model, ds, folderPath, modelName, options, logFn)
    safeName = make_safe_name(ds.shortLabel);
    if isempty(safeName)
        safeName = make_safe_name(ds.tag);
    end

    magnets3dPngPath = fullfile(folderPath, sprintf('Magnets_%s_%s.png', safeName, modelName));
    magnets3dTxtPath = fullfile(folderPath, sprintf('Magnets_%s_%s.txt', safeName, modelName));
    magnetsHistTxtPath = fullfile(folderPath, sprintf('Magnets_histogram_%s_%s.txt', safeName, modelName));
    magnetsHistPngPath = fullfile(folderPath, sprintf('Magnets_histogram_%s_%s.png', safeName, modelName));
    magnetsHistNormHTxtPath = fullfile(folderPath, sprintf('Magnets_histogram_normH_%s_%s.txt', safeName, modelName));
    magnetsHistNormHPngPath = fullfile(folderPath, sprintf('Magnets_histogram_normH_%s_%s.png', safeName, modelName));

    normMEnabled = true;
    normHEnabled = false;
    if isstruct(options.magnetsHistogram)
        normMEnabled = logical(options.magnetsHistogram.normMEnabled);
        normHEnabled = logical(options.magnetsHistogram.normHEnabled);
    end

    if options.enableMagnets3DPlot
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, 'Iniciando exportación Magnets 3D Plot...');
        try
            export_magnets_3d_plot(model, ds.tag, magnets3dPngPath, magnets3dTxtPath);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, 'Magnets 3D Plot exportado (PNG y TXT).');
        catch err
            if is_not_connected_error(err)
                rethrow(err);
            end
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('WARN', ts, ds.tag, ['Magnets 3D Plot no se pudo exportar: ' err.message]);
        end
    end

    if options.enableMagnetsHistogram && (normMEnabled || normHEnabled)
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf('Iniciando exportación Magnets Histogram (bins=%d)...', options.magnetsHistBins));
        try
            if normMEnabled
                export_magnets_histogram(model, ds.tag, magnetsHistTxtPath, magnetsHistPngPath, options.magnetsHistBins);
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('INFO', ts, ds.tag, sprintf('Magnets Histogram normM exportado (PNG y TXT, bins=%d).', options.magnetsHistBins));

                try
                    run_magnets_python_postprocess(magnetsHistTxtPath, modelName, ds.shortLabel, options.magnetsBr, options.magnetsStepPercent);
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('INFO', ts, ds.tag, sprintf('Postproceso Magnets Python completado (Br=%.6g T, step=%.6g%%).', ...
                        options.magnetsBr, options.magnetsStepPercent));
                catch postErr
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ['Postproceso Magnets no ejecutado: ' compact_python_error(postErr.message)]);
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ...
                        'Instala dependencias en el entorno Linux: python3 -m pip install --user numpy matplotlib');
                end
            end

            if normHEnabled
                export_magnets_histogram(model, ds.tag, magnetsHistNormHTxtPath, magnetsHistNormHPngPath, ...
                    options.magnetsHistBins, 'mfnc.normH', 'kA/m');
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('INFO', ts, ds.tag, sprintf('Magnets Histogram normH exportado (PNG y TXT, bins=%d).', options.magnetsHistBins));

                try
                    run_magnets_h_python_postprocess(magnetsHistNormHTxtPath, options.normH);
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('INFO', ts, ds.tag, 'Postproceso Magnets normH Python completado.');
                catch postErr
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ['Postproceso Magnets normH no ejecutado: ' compact_python_error(postErr.message)]);
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ...
                        'Instala dependencias en el entorno Linux: python3 -m pip install --user numpy matplotlib');
                end
            end
        catch err
            if is_not_connected_error(err)
                rethrow(err);
            end
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('WARN', ts, ds.tag, ['Magnets Histogram no se pudo exportar: ' err.message]);
        end
    elseif options.enableMagnetsHistogram
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('WARN', ts, ds.tag, 'Magnets Histogram habilitado pero sin selección de normM/normH.');
    end
end

% -------------------------------------------------------------------------
function run_optional_exports(model, ds, folderPath, modelName, histTxtPath, plot3dPngPath, options, logFn)
    [~, plot3dBase, ~] = fileparts(plot3dPngPath);
    plot3dTxtPath = fullfile(folderPath, [plot3dBase '.txt']);

    [histDir, histBase, ~] = fileparts(histTxtPath);
    histPngPath = fullfile(histDir, [histBase '.png']);

    if options.enable3DPlot
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, 'Iniciando exportación B_FOV 3D Plot...');
        export_3d_plot(model, ds.tag, plot3dPngPath, plot3dTxtPath);
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, 'B_FOV 3D Plot exportado (PNG y TXT).');
    end

    if options.enableHistogram
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf('Iniciando exportación B_FOV Histogram (bins=%d)...', options.histBins));
        export_histogram(model, ds.tag, histTxtPath, histPngPath, options.histBins);
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf('B_FOV Histogram exportado (PNG y TXT, bins=%d).', options.histBins));
    end

    if options.enableCustomCoordinates
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf(['Iniciando exportación B_FOV Custom Coordinates ' ...
            '(nTheta=%d, nPhi=%d, R=%.6f m)...'], ...
            options.coordConfig.nTheta, options.coordConfig.nPhi, options.coordConfig.R));
        [coordTxtPath, coordPngPath] = export_custom_coordinates_XYZ(model, ds.tag, folderPath, options.coordConfig);
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf('B_FOV Custom Coordinates exportado: %s | %s', coordTxtPath, coordPngPath));
    end

    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
    logFn('INFO', ts, ds.tag, sprintf('Dataset completado: %s', ds.shortLabel));
end

% -------------------------------------------------------------------------
function tf = is_not_connected_error(err)
    tf = false;

    if isempty(err)
        return;
    end

    msg = lower(err.message);
    if contains(msg, 'not connected to a server') || contains(msg, 'no conectado a un servidor')
        tf = true;
        return;
    end

    for i = 1:numel(err.cause)
        try
            cmsg = lower(err.cause{i}.message);
            if contains(cmsg, 'not connected to a server') || contains(cmsg, 'no conectado a un servidor')
                tf = true;
                return;
            end
        catch
        end
    end
end

% -------------------------------------------------------------------------
function tf = is_top_level_not_connected_error(err)
    tf = false;
    if isempty(err)
        return;
    end

    msg = lower(err.message);
    if contains(msg, 'not connected to a server') || contains(msg, 'no conectado a un servidor')
        tf = true;
    end
end

% -------------------------------------------------------------------------
function run_bfov_python_postprocess(txtPath, magnetInfo, fovInfo, analysisName, fieldAxis)
    if nargin < 3 || isempty(fovInfo)
        fovInfo = 'N/A';
    end
    if nargin < 4 || isempty(analysisName)
        analysisName = 'N/A';
    end
    if nargin < 5 || isempty(fieldAxis) || ~ismember(upper(char(fieldAxis)), {'X', 'Y', 'Z'})
        fieldAxis = 'Y';
    end
    fieldAxis = upper(char(fieldAxis));

    scriptPath = fullfile(fileparts(mfilename('fullpath')), ...
        'Comsol_extracted_histograms_BFOV_Magnets_XYZ.py');

    if ~isfile(scriptPath)
        error('No se encontro script Python de postproceso: %s', scriptPath);
    end

    [txtDir, txtName, ~] = fileparts(txtPath);
    outputPng = fullfile(txtDir, [txtName '.png']);

    [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(txtPath, outputPng);
    cleanupObj = onCleanup(@() cleanup_temp_folder(cleanupFolder)); %#ok<NASGU>

    baseArgs = [...
        ' --file-path '    q(txtPathForPython), ...
        ' --magnet-info '  q(magnetInfo), ...
        ' --fov-info '     q(fovInfo), ...
        ' --analysis '     q(analysisName), ...
        ' --output-png '   q(outputPngForPython), ...
        ' --bfov-only --no-show'];

    fieldAxisArgs = [' --field-axis ' q(fieldAxis)];

    % Primer intento: con --field-axis (necesario para que el PNG etiquete
    % correctamente Bx/By/Bz). Si el script .py aun no soporta este flag,
    % reintentamos sin el para no perder la generacion del PNG, y avisamos
    % explicitamente de que el .py necesita actualizarse.
    [ok, errors] = try_run_python_candidates(scriptPath, [baseArgs fieldAxisArgs]);
    if ok
        finalize_png_output(outputPngForPython, outputPng);
        return;
    end

    if any(cellfun(@(e) contains(lower(e), 'unrecognized argument') || ...
                          contains(lower(e), 'unrecognized arguments') || ...
                          (contains(lower(e), 'field-axis') && contains(lower(e), 'error')), errors))
        warning('ComsolAnalyzer:PythonFieldAxisUnsupported', ...
            ['El script %s no reconoce "--field-axis". Se reintenta sin ese flag ' ...
             '(el PNG se generara, pero probablemente con la etiqueta de eje anterior). ' ...
             'Actualiza el script Python para soportar --field-axis y que el eje mostrado ' ...
             'coincida siempre con el eje realmente exportado.'], scriptPath);

        [ok2, errors2] = try_run_python_candidates(scriptPath, baseArgs);
        if ok2
            finalize_png_output(outputPngForPython, outputPng);
            return;
        end
        errors = [errors, errors2]; %#ok<AGROW>
    end

    error('Fallo ejecutando postproceso Python BFOV: %s', strjoin(errors, ' | '));
end

% -------------------------------------------------------------------------
function [ok, errors] = try_run_python_candidates(scriptPath, args)
    ok = false;
    errors = {};

    pyCandidates = get_python_command_candidates();
    for i = 1:numel(pyCandidates)
        cmd = [pyCandidates{i} ' ' q(scriptPath) args];
        [status, out] = system(cmd);
        if status == 0
            ok = true;
            return;
        end
        errors{end+1} = sprintf('%s: %s', pyCandidates{i}, strtrim(out)); %#ok<AGROW>
    end
end

% -------------------------------------------------------------------------
function finalize_png_output(outputPngForPython, outputPng)
    if ~strcmp(outputPngForPython, outputPng)
        [okCopy, copyMsg] = copyfile(outputPngForPython, outputPng, 'f');
        if ~okCopy
            error('PNG generado por Python, pero no se pudo copiar al destino final: %s', copyMsg);
        end
    end
end

% -------------------------------------------------------------------------
function run_magnets_python_postprocess(magnetsTxtPath, magnetInfo, analysisName, br, stepPercent)
    if nargin < 3 || isempty(analysisName)
        analysisName = 'N/A';
    end
    if nargin < 4 || isempty(br)
        br = 1.4;
    end
    if nargin < 5 || isempty(stepPercent)
        stepPercent = 2;
    end

    scriptPath = fullfile(fileparts(mfilename('fullpath')), ...
        'Comsol_extracted_magnets_histogram.py');

    if ~isfile(scriptPath)
        error('No se encontro script Python de postproceso: %s', scriptPath);
    end

    [txtDir, txtName, ~] = fileparts(magnetsTxtPath);
    outputPng = fullfile(txtDir, [txtName '.png']);

    [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(magnetsTxtPath, outputPng);
    cleanupObj = onCleanup(@() cleanup_temp_folder(cleanupFolder)); %#ok<NASGU>

    args = [...
        ' --file-path-m '    q(txtPathForPython), ...
        ' --magnet-info '    q(magnetInfo), ...
        ' --analysis '       q(analysisName), ...
        ' --output-png-m '   q(outputPngForPython), ...
        ' --br '             q(num2str(br, '%.15g')), ...
        ' --step-percent '   q(num2str(stepPercent, '%.15g')), ...
        ' --no-show'];

    pyCandidates = get_python_command_candidates();
    errors = {};

    for i = 1:numel(pyCandidates)
        cmd = [pyCandidates{i} ' ' q(scriptPath) args];
        [status, out] = system(cmd);
        if status == 0
            if ~strcmp(outputPngForPython, outputPng)
                [okCopy, copyMsg] = copyfile(outputPngForPython, outputPng, 'f');
                if ~okCopy
                    error('PNG generado por Python, pero no se pudo copiar al destino final: %s', copyMsg);
                end
            end
            return;
        end
        errors{end+1} = sprintf('%s: %s', pyCandidates{i}, strtrim(out)); %#ok<AGROW>
    end

    error('Fallo ejecutando postproceso Python Magnets: %s', strjoin(errors, ' | '));
end

% -------------------------------------------------------------------------
function run_magnets_h_python_postprocess(magnetsTxtPath, normHOptions)
    if nargin < 2 || ~isstruct(normHOptions)
        normHOptions = struct();
    end

    scriptPath = fullfile(fileparts(mfilename('fullpath')), ...
        'Histogram_H_Postprocess.py');

    if ~isfile(scriptPath)
        error('No se encontro script Python de postproceso normH: %s', scriptPath);
    end

    [txtDir, txtName, ~] = fileparts(magnetsTxtPath);
    outputPng = fullfile(txtDir, [txtName '_Hfield.png']);

    [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(magnetsTxtPath, outputPng);
    cleanupObj = onCleanup(@() cleanup_temp_folder(cleanupFolder)); %#ok<NASGU>

    args = [...
        ' --file-path '  q(txtPathForPython), ...
        ' --output-png ' q(outputPngForPython), ...
        build_optional_h_arg('Hlinear_end', get_struct_field(normHOptions, 'Hlinear_end', [])), ...
        build_optional_h_arg('Hknee', get_struct_field(normHOptions, 'Hknee', [])), ...
        build_optional_h_arg('Hcb', get_struct_field(normHOptions, 'Hcb', [])), ...
        build_optional_h_arg('Hcj', get_struct_field(normHOptions, 'Hcj', [])), ...
        build_extra_h_args(get_struct_field(normHOptions, 'extraH', struct('name', {}, 'value', {}))), ...
        ' --no-show'];

    pyCandidates = get_python_command_candidates();
    errors = {};

    for i = 1:numel(pyCandidates)
        cmd = [pyCandidates{i} ' ' q(scriptPath) args];
        [status, out] = system(cmd);
        if status == 0
            if ~strcmp(outputPngForPython, outputPng)
                [okCopy, copyMsg] = copyfile(outputPngForPython, outputPng, 'f');
                if ~okCopy
                    error('PNG generado por Python, pero no se pudo copiar al destino final: %s', copyMsg);
                end
            end
            return;
        end
        errors{end+1} = sprintf('%s: %s', pyCandidates{i}, strtrim(out)); %#ok<AGROW>
    end

    error('Fallo ejecutando postproceso Python Magnets normH: %s', strjoin(errors, ' | '));
end

% -------------------------------------------------------------------------
function value = get_struct_field(s, fieldName, defaultValue)
    value = defaultValue;
    if isstruct(s) && isfield(s, fieldName)
        value = s.(fieldName);
    end
end

% -------------------------------------------------------------------------
function arg = build_optional_h_arg(flagName, value)
    arg = '';
    if isempty(value)
        return;
    end

    if ischar(value) || isstring(value)
        candidate = str2double(char(value));
    else
        candidate = double(value);
    end

    if ~isfinite(candidate)
        return;
    end

    arg = [' --' flagName ' ' q(num2str(candidate, '%.15g'))];
end

% -------------------------------------------------------------------------
function args = build_extra_h_args(extraH)
    args = '';
    if isempty(extraH)
        return;
    end

    if isstruct(extraH)
        for idx = 1:numel(extraH)
            name = strtrim(char(string(get_struct_field(extraH(idx), 'name', ''))));
            value = get_struct_field(extraH(idx), 'value', []);
            token = build_single_extra_h_arg(name, value);
            if ~isempty(token)
                args = [args token]; %#ok<AGROW>
            end
        end
        return;
    end

    if iscell(extraH)
        for idx = 1:numel(extraH)
            item = extraH{idx};
            if isstruct(item)
                name = strtrim(char(string(get_struct_field(item, 'name', ''))));
                value = get_struct_field(item, 'value', []);
            elseif iscell(item) && numel(item) >= 2
                name = strtrim(char(string(item{1})));
                value = item{2};
            else
                continue;
            end
            token = build_single_extra_h_arg(name, value);
            if ~isempty(token)
                args = [args token]; %#ok<AGROW>
            end
        end
    end
end

% -------------------------------------------------------------------------
function arg = build_single_extra_h_arg(name, value)
    arg = '';
    if isempty(name)
        return;
    end

    if ischar(value) || isstring(value)
        candidate = str2double(char(value));
    else
        candidate = double(value);
    end

    if ~isfinite(candidate)
        return;
    end

    arg = [' --extra ' q([char(name) '=' num2str(candidate, '%.15g')])];
end

% -------------------------------------------------------------------------
function pyCandidates = get_python_command_candidates()
    pyCandidates = {};

    % 1) Prefer Python configured in MATLAB.
    try
        pe = pyenv;
        if isprop(pe, 'Executable')
            exePath = char(pe.Executable);
            if endsWith(lower(exePath), 'pythonw.exe')
                altExe = [exePath(1:end-11) 'python.exe'];
                if isfile(altExe)
                    exePath = altExe;
                end
            end
            if ~isempty(strtrim(exePath)) && isfile(exePath)
                pyCandidates{end+1} = q(exePath); %#ok<AGROW>
            end
        end
    catch
    end

    % 2) Common command names.
    defaults = {'python', 'python3', 'py -3', 'py'};
    for i = 1:numel(defaults)
        if ~any(strcmp(pyCandidates, defaults{i}))
            pyCandidates{end+1} = defaults{i}; %#ok<AGROW>
        end
    end
end

% -------------------------------------------------------------------------
function [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(txtPath, outputPng)
    txtPathForPython = txtPath;
    outputPngForPython = outputPng;
    cleanupFolder = '';

    % Use short temp paths on Windows to avoid MAX_PATH failures in Python.
    if ispc
        cleanupFolder = tempname;
        mkdir(cleanupFolder);

        txtPathForPython = fullfile(cleanupFolder, 'BFOV_histogram_input.txt');
        outputPngForPython = fullfile(cleanupFolder, 'BFOV_histogram_output.png');

        [okCopy, copyMsg] = copyfile(txtPath, txtPathForPython, 'f');
        if ~okCopy
            error('No se pudo copiar el BFOV histogram TXT a ruta temporal corta: %s', copyMsg);
        end
    end
end

% -------------------------------------------------------------------------
function cleanup_temp_folder(folderPath)
    if isempty(folderPath)
        return;
    end
    if isfolder(folderPath)
        try
            rmdir(folderPath, 's');
        catch
        end
    end
end

% -------------------------------------------------------------------------
function out = q(str)
    if isempty(str)
        out = '""';
        return;
    end
    str = strrep(str, '"', '\"');
    out = ['"' str '"'];
end

% -------------------------------------------------------------------------
function msg = compact_python_error(msgIn)
    msg = strtrim(msgIn);
    msg = strrep(msg, newline, ' | ');
    if numel(msg) > 800
        msg = [msg(1:800) ' ...'];
    end
end
