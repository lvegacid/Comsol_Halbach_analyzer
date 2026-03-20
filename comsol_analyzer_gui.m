function comsol_analyzer_gui()
% comsol_analyzer_gui  GUI principal para COMSOL Analyzer.
%
% Crea una interfaz gráfica programática (uifigure) que permite:
%   - Seleccionar un archivo .mph mediante diálogo o ruta manual
%   - Seleccionar un directorio de salida
%   - Descubrir y seleccionar datasets del modelo COMSOL cargado
%   - Ejecutar la extracción BFOV para los datasets seleccionados
%
% Uso:
%   comsol_analyzer_gui()
%
% Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1–2.6, 4.1, 4.5, 6.3–6.5

% -------------------------------------------------------------------------
% Task 8.1 — Crear figura y controles base
% -------------------------------------------------------------------------

fig = uifigure('Name', 'COMSOL Analyzer', ...
               'Position', [100 100 700 520], ...
               'Resize', 'on');

% Estado compartido almacenado en UserData de la figura
state.model    = [];      % objeto modelo COMSOL cargado
state.datasets = [];      % struct array con .tag y .label
fig.UserData   = state;

% --- Panel: MPH File ---
uilabel(fig, 'Text', 'MPH File:', ...
    'Position', [20 470 80 22], 'FontWeight', 'bold');

mphField = uieditfield(fig, 'text', ...
    'Position', [105 470 460 22], ...
    'Placeholder', 'Ruta al archivo .mph...');

btnBrowseMph = uibutton(fig, 'push', ...
    'Text', 'Browse MPH', ...
    'Position', [575 470 105 22]);

% --- Panel: Output Directory ---
uilabel(fig, 'Text', 'Output Dir:', ...
    'Position', [20 435 80 22], 'FontWeight', 'bold');

outputField = uieditfield(fig, 'text', ...
    'Position', [105 435 460 22], ...
    'Placeholder', 'Directorio de salida...');

btnBrowseOut = uibutton(fig, 'push', ...
    'Text', 'Browse Output', ...
    'Position', [575 435 105 22]);

% --- Panel: FOV Info (texto libre para postproceso Python) ---
uilabel(fig, 'Text', 'FOV Info:', ...
    'Position', [20 400 80 22], 'FontWeight', 'bold');

fovInfoField = uieditfield(fig, 'text', ...
    'Position', [105 400 575 22], ...
    'Placeholder', 'Ej: Sphere(340 mm)');

% --- Panel: Datasets ---
uilabel(fig, 'Text', 'Datasets disponibles:', ...
    'Position', [20 370 200 22], 'FontWeight', 'bold');

datasetList = uilistbox(fig, ...
    'Position', [20 220 660 145], ...
    'Items', {}, ...
    'MultiSelect', 'on');

% --- Botón Run ---
btnRun = uibutton(fig, 'push', ...
    'Text', 'Run Extraction', ...
    'Position', [20 180 150 30], ...
    'Enable', 'off', ...
    'FontWeight', 'bold');

% --- Panel: Log ---
uilabel(fig, 'Text', 'Log:', ...
    'Position', [20 148 60 22], 'FontWeight', 'bold');

btnCopyLog = uibutton(fig, 'push', ...
    'Text', 'Copy Log', ...
    'Position', [575 148 105 22]);

logArea = uitextarea(fig, ...
    'Position', [20 20 660 125], ...
    'Editable', 'on', ...
    'Value', '');

% -------------------------------------------------------------------------
% Task 8.3 — Callback "Browse MPH"
% -------------------------------------------------------------------------
btnBrowseMph.ButtonPushedFcn = @(~,~) browseMphCallback();

% -------------------------------------------------------------------------
% Task 8.4 — Validación manual de ruta MPH (foco perdido / Enter)
% -------------------------------------------------------------------------
mphField.ValueChangedFcn = @(src,~) validateMphPath(src.Value);

% -------------------------------------------------------------------------
% Task 8.7 — Callback "Browse Output"
% -------------------------------------------------------------------------
btnBrowseOut.ButtonPushedFcn = @(~,~) browseOutputCallback();

% -------------------------------------------------------------------------
% Task 8.8 — Callback "Run Extraction"
% -------------------------------------------------------------------------
btnRun.ButtonPushedFcn = @(~,~) runExtractionCallback();

% -------------------------------------------------------------------------
% Callback "Copy Log"
% -------------------------------------------------------------------------
btnCopyLog.ButtonPushedFcn = @(~,~) copyLogCallback();

% =========================================================================
% Funciones internas (closures)
% =========================================================================

    % --- Añadir línea al log ---
    function appendLog(level, timestamp, datasetTag, message)
        if nargin == 1
            % Llamada simple: appendLog('texto')
            line = level;
        else
            line = sprintf('[%s] [%s] [%s] %s', timestamp, level, datasetTag, message);
        end
        current = logArea.Value;
        if ischar(current)
            current = {current};
        elseif isstring(current)
            current = cellstr(current);
        end
        if isempty(current) || (numel(current) == 1 && isempty(current{1}))
            logArea.Value = {line};
        else
            logArea.Value = [current; {line}];
        end
        % Scroll al final
        scroll(logArea, 'bottom');
        drawnow;
    end

    % --- Poblar lista de datasets ---
    function populateDatasets(datasets)
        s = fig.UserData;
        s.datasets = datasets;
        fig.UserData = s;

        if isempty(datasets)
            datasetList.Items = {};
            return;
        end

        items = cell(numel(datasets), 1);
        for k = 1:numel(datasets)
            items{k} = sprintf('%s: %s', datasets(k).tag, datasets(k).label);
        end
        datasetList.Items = items;
    end

    % --- Cargar modelo y datasets desde una ruta MPH ---
    function loadModelFromPath(mphPath)
        % Limpiar estado previo
        s = fig.UserData;
        s.model    = [];
        s.datasets = [];
        fig.UserData = s;
        populateDatasets([]);
        btnRun.Enable = 'off';

        % Cargar modelo
        try
            mdl = load_model(mphPath);
        catch err
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('ERROR', ts, '', err.message);
            return;
        end

        % Obtener datasets
        try
            datasets = get_datasets(mdl);
        catch err
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('ERROR', ts, '', err.message);
            return;
        end

        % Guardar modelo en estado
        s = fig.UserData;
        s.model = mdl;
        fig.UserData = s;

        if isempty(datasets)
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('WARN', ts, '', 'No se encontraron datasets en el modelo.');
            btnRun.Enable = 'off';
        else
            populateDatasets(datasets);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('INFO', ts, '', sprintf('Modelo cargado. %d dataset(s) encontrado(s).', numel(datasets)));
            btnRun.Enable = 'on';
        end
    end

    % -----------------------------------------------------------------
    % Task 8.3 — Browse MPH callback
    % -----------------------------------------------------------------
    function browseMphCallback()
        % Bring figure to front and flush event queue before opening dialog
        figure(fig);
        drawnow;
        [fname, fpath] = uigetfile({'*.mph','COMSOL Model (*.mph)'}, ...
                                   'Seleccionar archivo MPH');
        % Restore focus to uifigure after dialog closes
        figure(fig);
        drawnow;
        if isequal(fname, 0)
            return;  % usuario canceló
        end
        fullPath = fullfile(fpath, fname);
        mphField.Value = fullPath;
        loadModelFromPath(fullPath);
    end

    % -----------------------------------------------------------------
    % Task 8.4 — Validación manual de ruta MPH
    % -----------------------------------------------------------------
    function validateMphPath(mphPath)
        mphPath = strtrim(mphPath);
        if isempty(mphPath)
            return;
        end

        [~, ~, ext] = fileparts(mphPath);
        if ~strcmpi(ext, '.mph')
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('ERROR', ts, '', ...
                sprintf('Ruta inválida: la extensión "%s" no es .mph.', ext));
            btnRun.Enable = 'off';
            return;
        end

        if ~isfile(mphPath)
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('ERROR', ts, '', ...
                sprintf('Ruta inválida: el archivo no existe: %s', mphPath));
            btnRun.Enable = 'off';
            return;
        end

        % Ruta válida — cargar modelo
        loadModelFromPath(mphPath);
    end

    % -----------------------------------------------------------------
    % Task 8.7 — Browse Output callback
    % -----------------------------------------------------------------
    function browseOutputCallback()
        figure(fig);
        drawnow;
        selDir = uigetdir('', 'Seleccionar directorio de salida');
        figure(fig);
        drawnow;
        if isequal(selDir, 0)
            return;  % usuario canceló
        end
        outputField.Value = selDir;
    end

    % -----------------------------------------------------------------
    % Task 8.8 — Run Extraction callback
    % -----------------------------------------------------------------
    function runExtractionCallback()
        % Verificar selección de datasets
        selectedItems = datasetList.Value;
        if isempty(selectedItems)
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('WARN', ts, '', ...
                'Debe seleccionar al menos un dataset antes de ejecutar la extracción.');
            return;
        end

        % Verificar directorio de salida
        outputDir = strtrim(outputField.Value);
        if isempty(outputDir)
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('WARN', ts, '', ...
                'Debe especificar un directorio de salida.');
            return;
        end

        % Obtener modelo y datasets del estado
        s = fig.UserData;
        mdl      = s.model;
        allDsets = s.datasets;

        if isempty(mdl)
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('WARN', ts, '', 'No hay modelo cargado.');
            return;
        end

        % Mapear items seleccionados → structs de dataset
        if ischar(selectedItems)
            selectedItems = {selectedItems};
        end
        selectedDatasets = struct('tag', {}, 'label', {}, 'shortLabel', {});
        for k = 1:numel(selectedItems)
            item = selectedItems{k};
            % Formato: "<tag>: <label>"
            colonIdx = strfind(item, ': ');
            if ~isempty(colonIdx)
                tag = strtrim(item(1:colonIdx(1)-1));
            else
                tag = strtrim(item);
            end
            % Buscar en allDsets
            for j = 1:numel(allDsets)
                if strcmp(allDsets(j).tag, tag)
                    selectedDatasets(end+1) = allDsets(j); %#ok<AGROW>
                    break;
                end
            end
        end

        if isempty(selectedDatasets)
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('WARN', ts, '', 'No se pudieron resolver los datasets seleccionados.');
            return;
        end

        % Derivar modelName desde la ruta MPH
        mphPath = strtrim(mphField.Value);
        [~, modelName, ~] = fileparts(mphPath);

        % Metadata para postproceso Python
        fovInfo = strtrim(fovInfoField.Value);
        if isempty(fovInfo)
            fovInfo = 'N/A';
        end

        % Deshabilitar Run durante la extracción
        btnRun.Enable = 'off';
        drawnow;

        % Callbacks para extraction_controller
        logFn      = @(level, ts, tag, msg) appendLog(level, ts, tag, msg);
        progressFn = @(current, total) appendLog('INFO', ...
            datestr(now, 'yyyy-mm-dd HH:MM:SS'), '', ...
            sprintf('Progreso: %d / %d datasets procesados.', current, total));

        % Ejecutar extracción
        try
            summary = extraction_controller(mdl, selectedDatasets, outputDir, ...
                                            modelName, logFn, progressFn, fovInfo);
        catch err
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('ERROR', ts, '', ...
                sprintf('Error inesperado en extraction_controller: %s', err.message));
            btnRun.Enable = 'on';
            return;
        end

        % Mostrar resumen final
        ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
        appendLog('INFO', ts, '', '--- Resumen de extracción ---');
        appendLog('INFO', ts, '', sprintf('  Datasets OK:    %d', summary.nOK));
        appendLog('INFO', ts, '', sprintf('  Datasets error: %d', summary.nError));
        appendLog('INFO', ts, '', sprintf('  Directorio:     %s', summary.outputDir));

        % Rehabilitar Run
        btnRun.Enable = 'on';
    end

    function copyLogCallback()
        lines = logArea.Value;

        if ischar(lines)
            lines = {lines};
        elseif isstring(lines)
            lines = cellstr(lines);
        end

        if isempty(lines)
            payload = '';
        else
            payload = strjoin(lines, newline);
        end

        try
            clipboard('copy', payload);
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('INFO', ts, '', 'Log copiado al portapapeles.');
        catch err
            ts = datestr(now, 'yyyy-mm-dd HH:MM:SS');
            appendLog('ERROR', ts, '', ['No se pudo copiar el log: ' err.message]);
        end
    end

end
