function status = comsol_livelink_connection(action)
% comsol_livelink_connection  Consulta o intenta conectar LiveLink con COMSOL.
%
% action:
%   'status'  -> solo consulta el estado actual de la sesion MATLAB
%   'connect' -> en Linux intenta conectar con mphstart y, si hace falta,
%                lanzar `comsol mphserver` desacoplado de la terminal

    if nargin < 1 || isempty(action)
        action = 'status';
    end

    status = struct(...
        'connected', false, ...
        'platform', detect_platform(), ...
        'hasLiveLink', false, ...
        'canAutoConnect', false, ...
        'message', '', ...
        'detail', '', ...
        'version', '', ...
        'serverStartAttempted', false, ...
        'serverPort', [], ...
        'serverLog', '');

    status.hasLiveLink = has_livelink_functions();
    status.canAutoConnect = strcmp(status.platform, 'linux');
    if strcmp(status.platform, 'linux')
        [status.serverPort, status.serverLog] = linux_mphserver_settings();
    end

    if ~status.hasLiveLink
        status.message = ['LiveLink for MATLAB no esta disponible en esta sesion. ' ...
            'Abre MATLAB desde COMSOL o revisa la instalacion de LiveLink.'];
        return;
    end

    [connected, detail, versionText] = probe_connection();
    if connected
        status.connected = true;
        status.version = versionText;
        status.message = build_connected_message(versionText);
        return;
    end

    status.detail = detail;

    if strcmpi(action, 'connect') && strcmp(status.platform, 'linux')
        [connected, detail, versionText, startAttempted] = connect_on_linux();
        status.serverStartAttempted = startAttempted;
        status.connected = connected;
        status.detail = detail;
        status.version = versionText;

        if connected
            status.message = ['Servidor COMSOL conectado en Linux. ' ...
                build_connected_message(versionText)];
            return;
        end
    end

    status.message = build_disconnected_message(status.platform, status.serverStartAttempted);
end

function platform = detect_platform()
    if ispc
        platform = 'windows';
    elseif isunix && ~ismac
        platform = 'linux';
    elseif ismac
        platform = 'mac';
    else
        platform = 'unknown';
    end
end

function tf = has_livelink_functions()
    tf = exist('mphload', 'file') ~= 0 || ...
         exist('mphstart', 'file') ~= 0 || ...
         exist('mphversion', 'file') ~= 0;
end

function [connected, detail, versionText] = probe_connection()
    connected = false;
    detail = '';
    versionText = '';

    if exist('mphversion', 'file') ~= 0
        try
            versionValue = mphversion;
            versionText = normalize_value(versionValue);
            connected = true;
            return;
        catch err
            detail = err.message;
            if is_not_connected_error(err)
                return;
            end
            % Transient error: retry mphversion once after a short pause
            pause(0.5);
            try
                versionValue = mphversion;
                versionText = normalize_value(versionValue);
                connected = true;
                return;
            catch retryErr
                detail = retryErr.message;
                if is_not_connected_error(retryErr)
                    return;
                end
                % Retry also failed with a transient error — fall through to ModelUtil probes
            end
        end
    end

    probeMethods = {@probe_modelutil_tags, @probe_modelutil_modeltags};
    for idx = 1:numel(probeMethods)
        try
            probeMethods{idx}();
            connected = true;
            return;
        catch err
            detail = err.message;
            if is_missing_method_error(err)
                continue;
            end
            if is_not_connected_error(err)
                return;
            end
        end
    end
end

function probe_modelutil_tags()
    com.comsol.model.util.ModelUtil.tags();
end

function probe_modelutil_modeltags()
    com.comsol.model.util.ModelUtil.modelTags();
end

function [connected, detail, versionText, startAttempted] = connect_on_linux()
    startAttempted = false;
    [serverPort, serverLog] = linux_mphserver_settings();

    if exist('mphstart', 'file') == 0
        detail = 'mphstart no esta disponible en esta sesion MATLAB.';
        return;
    end

    % Prefer explicit host+port on Linux to avoid IPv4/IPv6 localhost drift
    % and random attachment to a different COMSOL server instance.
    [connected, detail, versionText] = try_mphstart_retries(2, 0.5, serverPort);
    if connected
        return;
    end

    startAttempted = true;
    [statusCode, output] = launch_linux_mphserver(serverPort, serverLog);

    if statusCode ~= 0
        detail = strtrim(output);
        if isempty(detail)
            detail = sprintf('No se pudo lanzar `comsol mphserver` en el puerto %d.', serverPort);
        end
        return;
    end

    [connected, detail, versionText] = try_mphstart_retries(12, 5.0, serverPort);
    if ~connected && isempty(strtrim(detail))
        detail = sprintf(['Se lanzo `comsol mphserver` en el puerto %d, ' ...
            'pero MATLAB no pudo conectar. Revisa %s.'], serverPort, serverLog);
    end
end

function [connected, detail, versionText] = try_mphstart_retries(maxTries, pauseSeconds, serverPort)
    if nargin < 3
        serverPort = [];
    end

    connected = false;
    detail = '';
    versionText = '';

    for attempt = 1:maxTries
        try
            if isempty(serverPort)
                mphstart();
            else
                start_mph_on_port(serverPort);
            end
        catch err
            detail = err.message;
        end

        [connected, probeDetail, versionText] = probe_connection();
        if connected
            return;
        end

        if ~isempty(strtrim(probeDetail))
            detail = probeDetail;
        end

        if attempt < maxTries && pauseSeconds > 0
            pause(pauseSeconds);
        end
    end
end

function start_mph_on_port(serverPort)
    host = linux_mphserver_host();
    try
        mphstart(serverPort);
    catch firstErr
        try
            mphstart(host, serverPort);
        catch secondErr
            err = MException('ComsolAnalyzer:LiveLinkConnect', ...
                'mphstart no pudo conectar a %s:%d: %s | %s', ...
                host, serverPort, firstErr.message, secondErr.message);
            throw(err);
        end
    end
end

function [statusCode, output] = launch_linux_mphserver(serverPort, serverLog)
    logDir = fileparts(serverLog);
    marker = sprintf('[c]omsol.*mphserver.*%d', serverPort);

    % Build session-detached launch command with fallback chain:
    %   1. setsid (creates new Unix session — preferred)
    %   2. systemd-run --user (systemd-based session detachment)
    %   3. nohup (legacy fallback)
    command = sprintf(['mkdir -p %s; ' ...
        'if command -v pgrep >/dev/null 2>&1 && pgrep -f %s >/dev/null 2>&1; then exit 0; fi; ' ...
        'if command -v setsid >/dev/null 2>&1; then ' ...
        'echo "[ComsolAnalyzer] Launching comsol mphserver via setsid"; ' ...
        'setsid comsol mphserver -port %d > %s 2>&1 < /dev/null & ' ...
        'elif command -v systemd-run >/dev/null 2>&1; then ' ...
        'echo "[ComsolAnalyzer] Launching comsol mphserver via systemd-run"; ' ...
        'systemd-run --user --no-block -- comsol mphserver -port %d >> %s 2>&1; ' ...
        'else ' ...
        'echo "[ComsolAnalyzer] Launching comsol mphserver via nohup (fallback)"; ' ...
        'nohup comsol mphserver -port %d > %s 2>&1 < /dev/null & fi'], ...
        shell_quote(logDir), shell_quote(marker), ...
        serverPort, shell_quote(serverLog), ...
        serverPort, shell_quote(serverLog), ...
        serverPort, shell_quote(serverLog));
    [statusCode, output] = system(['bash -lc ' shell_quote(command)]);
end

function [serverPort, serverLog] = linux_mphserver_settings()
    portText = strtrim(getenv('COMSOL_ANALYZER_MPHSERVER_PORT'));
    serverPort = str2double(portText);
    if isnan(serverPort) || serverPort <= 0
        serverPort = 2036;
    end

    baseDir = strtrim(getenv('COMSOL_ANALYZER_STATE_DIR'));
    if isempty(baseDir)
        baseDir = fullfile(char(java.lang.System.getProperty('user.home')), '.comsol_analyzer');
    end
    if isempty(strtrim(baseDir))
        baseDir = fullfile(tempdir, 'comsol_analyzer');
    end
    serverLog = fullfile(baseDir, sprintf('mphserver_%d.log', serverPort));
end

function host = linux_mphserver_host()
    host = strtrim(getenv('COMSOL_ANALYZER_MPHSERVER_HOST'));
    if isempty(host)
        host = '127.0.0.1';
    end
end

function quoted = shell_quote(value)
    value = char(value);
    quoted = ['''' strrep(value, '''', '''"''"''') ''''];
end

function tf = is_not_connected_error(err)
    tf = false;
    if isempty(err)
        return;
    end

    msg = lower(err.message);
    tf = contains(msg, 'not connected to a server') || ...
         contains(msg, 'no conectado a un servidor') || ...
         contains(msg, 'connection reset') || ...
         contains(msg, 'connection timed out') || ...
         contains(msg, 'broken pipe') || ...
         contains(msg, 'java.rmi') || ...
         contains(msg, 'connection refused') || ...
         contains(msg, 'failed to connect');
end

function tf = is_missing_method_error(err)
    msg = lower(err.message);
    tf = contains(msg, 'no appropriate method') || ...
         contains(msg, 'undefined function') || ...
         contains(msg, 'unrecognized method');
end

function out = normalize_value(value)
    if ischar(value)
        out = strtrim(value);
    elseif isstring(value)
        out = strtrim(char(value));
    else
        out = strtrim(char(string(value)));
    end
end

function msg = build_connected_message(versionText)
    if isempty(strtrim(versionText))
        msg = 'Sesion MATLAB conectada a COMSOL Server.';
    else
        msg = ['Sesion MATLAB conectada a COMSOL Server (' versionText ').'];
    end
end

function msg = build_disconnected_message(platform, startAttempted)
    switch platform
        case 'windows'
            msg = ['Sin conexion. En Windows abre COMSOL with MATLAB manualmente ' ...
                'y vuelve a pulsar "Check / Connect LiveLink".'];
        case 'linux'
            if startAttempted
                [serverPort, serverLog] = linux_mphserver_settings();
                msg = sprintf(['Sin conexion tras intentar lanzar `comsol mphserver` ' ...
                    'en el puerto %d. Revisa que COMSOL este en PATH y consulta %s.'], ...
                    serverPort, serverLog);
            else
                [serverPort, ~] = linux_mphserver_settings();
                msg = sprintf(['Sin conexion. Pulsa "Check / Connect LiveLink" para ' ...
                    'lanzar `comsol mphserver` estable en el puerto %d y conectar MATLAB.'], ...
                    serverPort);
            end
        otherwise
            msg = 'Sin conexion al servidor COMSOL desde MATLAB.';
    end
end
