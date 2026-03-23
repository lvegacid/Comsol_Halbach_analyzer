function [ok, message] = validate_output_directory(outputDir, modelName)
% validate_output_directory  Comprueba que el directorio de salida sea escribible.

    ok = false;
    message = '';

    outputDir = strtrim(outputDir);
    if isempty(outputDir)
        message = 'Debe especificar un directorio de salida.';
        return;
    end

    if ~isfolder(outputDir)
        message = ['El directorio de salida no existe o no es accesible: ' outputDir];
        return;
    end

    safeModel = make_safe_name(modelName);
    if isempty(safeModel)
        safeModel = 'comsol_output';
    end

    probeDir = fullfile(outputDir, safeModel);
    [mkOk, mkMsg] = mkdir(probeDir);
    if ~mkOk
        message = ['No se puede crear o acceder a la carpeta del modelo en el destino: ' ...
            probeDir ' (' mkMsg ').'];
        return;
    end

    probeFile = fullfile(probeDir, ['.__write_test_' char(java.util.UUID.randomUUID()) '.tmp']);
    fid = fopen(probeFile, 'w');
    if fid == -1
        message = ['El directorio existe pero no tiene permisos de escritura: ' probeDir];
        return;
    end

    cleanupObj = onCleanup(@() cleanup_probe_file(fid, probeFile)); %#ok<NASGU>
    fwrite(fid, 'ok');
    ok = true;
end

function cleanup_probe_file(fid, probeFile)
    try
        fclose(fid);
    catch
    end

    if isfile(probeFile)
        try
            delete(probeFile);
        catch
        end
    end
end