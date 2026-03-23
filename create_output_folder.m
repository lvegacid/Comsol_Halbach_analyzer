function folderPath = create_output_folder(outputDir, modelName, datasetLabel, datasetTag)
% create_output_folder  Create the output folder structure for a dataset.
%
% Creates the directory tree:
%   <outputDir>/<safe(modelName)>/<safe(datasetLabel)>/
%
% If mkdir fails with the dataset label, retries using the dataset tag.
% If both attempts fail, throws an MException.
%
% Syntax:
%   folderPath = create_output_folder(outputDir, modelName, datasetLabel, datasetTag)
%
% Inputs:
%   outputDir     (char) — root output directory
%   modelName     (char) — model name (will be made safe)
%   datasetLabel  (char) — dataset label (will be made safe, used first)
%   datasetTag    (char) — dataset tag  (will be made safe, used as fallback)
%
% Outputs:
%   folderPath  (char) — path of the created folder
%
% Throws:
%   MException with identifier 'ComsolAnalyzer:createFolder' if both
%   attempts fail.
%
% Validates: Requisitos 3.1, 3.3

    safeModel = make_safe_name(modelName);
    safeLabel = make_safe_name(datasetLabel);

    % First attempt: use the dataset label
    folderPath = fullfile(outputDir, safeModel, safeLabel);
    [ok, msg] = mkdir(folderPath);
    if ok
        return;
    end

    % Second attempt: fall back to the dataset tag
    safeTag = make_safe_name(datasetTag);
    folderPath = fullfile(outputDir, safeModel, safeTag);
    [ok, msg2] = mkdir(folderPath);
    if ok
        return;
    end

    % Both attempts failed — throw a descriptive exception
    throw(MException('ComsolAnalyzer:createFolder', ...
        ['Could not create output folder. Label path: %s (%s). ' ...
         'Tag path: %s (%s).'], ...
        fullfile(outputDir, safeModel, safeLabel), msg, ...
        fullfile(outputDir, safeModel, safeTag), msg2));
end
