function summary = extraction_controller(model, datasets, outputDir, modelName, logFn, progressFn, fovInfo)
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

    nTotal = numel(datasets);
    nOK    = 0;
    nError = 0;

    for i = 1:nTotal
        ds = datasets(i);
        try
            % Crear carpeta usando shortLabel
            folderPath = create_output_folder(outputDir, modelName, ds.shortLabel, ds.tag);

            % Construir rutas de salida
            safeName = make_safe_name(ds.shortLabel);
            [txtPath, pngPath] = build_output_paths(folderPath, safeName, modelName);

            % Exportar PNG (3D plot) y TXT (histograma) en una sola llamada
            export_dataset(model, ds.tag, txtPath, pngPath);

            nOK = nOK + 1;
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            logFn('INFO', ts, ds.tag, sprintf('OK → %s', folderPath));

            % Postproceso BFOV en Python a partir del TXT de histograma.
            analysisName = ds.shortLabel;
            try
                run_bfov_python_postprocess(txtPath, modelName, fovInfo, analysisName);
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('INFO', ts, ds.tag, 'Postproceso BFOV Python completado.');
            catch postErr
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('WARN', ts, ds.tag, ['Postproceso BFOV no ejecutado: ' compact_python_error(postErr.message)]);
                ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
                logFn('WARN', ts, ds.tag, ...
                    'Instala dependencias en el entorno Linux: python3 -m pip install --user numpy matplotlib');
            end

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

    args = [...
        ' --file-path '    q(txtPath), ...
        ' --magnet-info '  q(magnetInfo), ...
        ' --fov-info '     q(fovInfo), ...
        ' --analysis '     q(analysisName), ...
        ' --output-png '   q(outputPng), ...
        ' --bfov-only --no-show'];

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

    error('Fallo ejecutando postproceso Python BFOV: %s', strjoin(errors, ' | '));
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
