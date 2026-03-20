% Carga un modelo COMSOL desde mph_path usando mphload.
% Si COMSOL ya está en ejecución, reutiliza la sesión existente.
%
% Entradas:
%   mph_path  (char) — ruta absoluta al archivo .mph
%
% Salidas:
%   model     (com.comsol.model.Model) — objeto modelo COMSOL
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:loadModel' si falla
function model = load_model(mph_path)
    try
        model = mphload(mph_path);
    catch cause
        err = MException('ComsolAnalyzer:loadModel', ...
            'No se pudo cargar el modelo COMSOL desde "%s": %s', ...
            mph_path, cause.message);
        throw(err);
    end
end
