function [txtPath, pngPath] = build_output_paths(folderPath, datasetSafeName, modelName)
% build_output_paths  Build the TXT and PNG output file paths for a dataset.
%
% Constructs:
%   TXT: <folderPath>/BFOV_histogram_<datasetSafeName>_<modelName>.txt
%   PNG: <folderPath>/BFOV_<datasetSafeName>_<modelName>.png
%
% Syntax:
%   [txtPath, pngPath] = build_output_paths(folderPath, datasetSafeName, modelName)
%
% Inputs:
%   folderPath       (char) — directory where the files will be written
%   datasetSafeName  (char) — safe name of the dataset
%   modelName        (char) — model name (used as-is, already safe)
%
% Outputs:
%   txtPath  (char) — full path for the histogram TXT file
%   pngPath  (char) — full path for the 3-D plot PNG file
%
% Validates: Requisito 3.4

    txtFile = sprintf('BFOV_histogram_%s_%s.txt', datasetSafeName, modelName);
    pngFile = sprintf('BFOV_%s_%s.png',           datasetSafeName, modelName);

    txtPath = fullfile(folderPath, txtFile);
    pngPath = fullfile(folderPath, pngFile);
end
