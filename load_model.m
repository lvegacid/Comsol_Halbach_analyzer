% Carga un modelo COMSOL desde mph_path usando mphload.
% Si COMSOL ya esta en ejecucion, reutiliza la sesion existente.
%
% Entradas:
%   mph_path  (char) - ruta absoluta al archivo .mph
%
% Salidas:
%   model     (com.comsol.model.Model) - objeto modelo COMSOL
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:loadModel' si falla
function model = load_model(mph_path)
    preflight_livelink_connection();

    try
        model = mphload(mph_path);
    catch cause
        if is_livelink_connection_error(cause)
            preflight_livelink_connection();
            try
                model = mphload(mph_path);
                return;
            catch retryCause
                cause = retryCause;
            end
        end

        err = MException('ComsolAnalyzer:loadModel', ...
            'No se pudo cargar el modelo COMSOL desde "%s": %s', ...
            mph_path, cause.message);
        err = addCause(err, cause);
        throw(err);
    end
end

function preflight_livelink_connection()
    if exist('comsol_livelink_connection', 'file') == 0
        return;
    end

    try
        comsol_livelink_connection('connect');
    catch
        % mphload below will report the actionable COMSOL/LiveLink error.
    end
end

function tf = is_livelink_connection_error(err)
    tf = false;
    if isempty(err)
        return;
    end

    if message_mentions_livelink_disconnect(err.message)
        tf = true;
        return;
    end

    for i = 1:numel(err.cause)
        try
            if message_mentions_livelink_disconnect(err.cause{i}.message)
                tf = true;
                return;
            end
        catch
        end
    end
end

function tf = message_mentions_livelink_disconnect(message)
    msg = lower(message);
    tf = contains(msg, 'not connected to a server') || ...
         contains(msg, 'no conectado a un servidor') || ...
         contains(msg, 'connection refused') || ...
         contains(msg, 'failed to connect') || ...
         contains(msg, 'connection reset') || ...
         contains(msg, 'connection timed out') || ...
         contains(msg, 'broken pipe') || ...
         contains(msg, 'java.rmi');
end
