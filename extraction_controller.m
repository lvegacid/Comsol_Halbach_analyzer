function summary = extraction_controller(model, datasets, outputDir, modelName, logFn, progressFn, fovInfo, options)
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

    nTotal = numel(datasets);
    nOK    = 0;
    nError = 0;

    for i = 1:nTotal
        ds = datasets(i);
        try
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('Preparando dataset %d de %d: %s', i, nTotal, ds.shortLabel));

            % Crear carpeta usando shortLabel
            folderPath = create_output_folder(outputDir, modelName, ds.shortLabel, ds.tag);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('Carpeta de salida lista: %s', folderPath));

            % Construir rutas de salida
            safeName = make_safe_name(ds.shortLabel);
            [histTxtPath, plot3dPngPath] = build_output_paths(folderPath, safeName, modelName);

            doMainExports = logical(options.enable3DPlot) || logical(options.enableHistogram);

            if doMainExports
                % Flujo historico estable: export_dataset + postproceso Python
                export_dataset(model, ds.tag, histTxtPath, plot3dPngPath);
            end

            if options.enableHistogram
                analysisName = ds.shortLabel;
                try
                    run_bfov_python_postprocess(histTxtPath, modelName, fovInfo, analysisName);
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('INFO', ts, ds.tag, 'Postproceso BFOV Python completado.');
                catch postErr
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ['Postproceso BFOV no ejecutado: ' compact_python_error(postErr.message)]);
                    ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                    logFn('WARN', ts, ds.tag, ...
                        'Instala dependencias Python (numpy, matplotlib). Ejemplo: python -m pip install numpy matplotlib');
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
                    logFn('INFO', ts, ds.tag, sprintf(['Iniciando exportación B_FOV Custom Coordinates ' ...
                        '(From file: %s | cols=%s)...'], sourceFileName, mat2str(options.coordConfig.coordColumns)));
                else
                    logFn('INFO', ts, ds.tag, sprintf(['Iniciando exportación B_FOV Custom Coordinates ' ...
                        '(nTheta=%d, nPhi=%d, R=%.6f m)...'], ...
                        options.coordConfig.nTheta, options.coordConfig.nPhi, options.coordConfig.R));
                end
                [coordTxtPath, coordPngPath] = export_custom_coordinates(model, ds.tag, folderPath, options.coordConfig);
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('INFO', ts, ds.tag, sprintf('B_FOV Custom Coordinates exportado: %s | %s', coordTxtPath, coordPngPath));
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
                    'LiveLink se desconecto del servidor COMSOL durante la exportacion. Se detiene el lote para evitar errores en cascada.');
                progressFn(i, nTotal);
                break;
            end
        end

        progressFn(i, nTotal);
    end

    summary.nOK      = nOK;
    summary.nError   = nError;
    summary.outputDir = outputDir;
end

% -------------------------------------------------------------------------
function options = default_extraction_options()
    options.enable3DPlot = true;
    options.enableHistogram = true;
    options.enableCustomCoordinates = false;
    options.enableMagnets3DPlot = false;
    options.enableMagnetsHistogram = false;
    options.histBins = 100;
    options.magnetsHistBins = 100;
    options.magnetsStepPercent = 2;
    options.magnetsBr = 1.4;
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

    if options.enableMagnetsHistogram
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        logFn('INFO', ts, ds.tag, sprintf('Iniciando exportación Magnets Histogram (bins=%d)...', options.magnetsHistBins));
        try
            export_magnets_histogram(model, ds.tag, magnetsHistTxtPath, magnetsHistPngPath, options.magnetsHistBins);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('Magnets Histogram exportado (PNG y TXT, bins=%d).', options.magnetsHistBins));

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
        catch err
            if is_not_connected_error(err)
                rethrow(err);
            end
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('WARN', ts, ds.tag, ['Magnets Histogram no se pudo exportar: ' err.message]);
        end
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
        [coordTxtPath, coordPngPath] = export_custom_coordinates(model, ds.tag, folderPath, options.coordConfig);
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
function run_bfov_python_postprocess(txtPath, magnetInfo, fovInfo, analysisName)
    if nargin < 3 || isempty(fovInfo)
        fovInfo = 'N/A';
    end
    if nargin < 4 || isempty(analysisName)
        analysisName = 'N/A';
    end

    scriptPath = fullfile(fileparts(mfilename('fullpath')), ...
        'Comsol_extracted_histograms_BFOV_Magnets.py');

    if ~isfile(scriptPath)
        error('No se encontro script Python de postproceso: %s', scriptPath);
    end

    [txtDir, txtName, ~] = fileparts(txtPath);
    outputPng = fullfile(txtDir, [txtName '.png']);

    [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(txtPath, outputPng);
    cleanupObj = onCleanup(@() cleanup_temp_folder(cleanupFolder)); %#ok<NASGU>

    args = [...
        ' --file-path '    q(txtPathForPython), ...
        ' --magnet-info '  q(magnetInfo), ...
        ' --fov-info '     q(fovInfo), ...
        ' --analysis '     q(analysisName), ...
        ' --output-png '   q(outputPngForPython), ...
        ' --bfov-only --no-show'];

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

    error('Fallo ejecutando postproceso Python BFOV: %s', strjoin(errors, ' | '));
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

    args = [...
        ' --file-path-m '    q(magnetsTxtPath), ...
        ' --magnet-info '    q(magnetInfo), ...
        ' --analysis '       q(analysisName), ...
        ' --output-png-m '   q(outputPng), ...
        ' --br '             q(num2str(br, '%.15g')), ...
        ' --step-percent '   q(num2str(stepPercent, '%.15g')), ...
        ' --magnets-only --no-show'];

    pyCandidates = {'python', 'python3'};
    errors = {};

    for i = 1:numel(pyCandidates)
        cmd = [pyCandidates{i} ' ' q(scriptPath) args];
        [status, out] = system(cmd);
        if status == 0
            return;
        end
        errors{end+1} = sprintf('%s: %s', pyCandidates{i}, strtrim(out)); %#ok<AGROW>
    end

    error('Fallo ejecutando postproceso Python Magnets: %s', strjoin(errors, ' | '));
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
    if numel(msg) > 350
        msg = [msg(1:350) ' ...'];
    end
end
