% Crea un PlotGroup3D con expresion mfnc.By en mT para el dataset dado
% y exporta la imagen como PNG en outputPath.
%
% Entradas:
%   model        (com.comsol.model.Model)
%   datasetTag   (char) — tag del dataset (se usa tal cual)
%   outputPath   (char) — ruta completa del archivo PNG de salida
%   outputTxtPath(char, opcional) — ruta completa del TXT de salida
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:export3DPlot'
function export_3d_plot(model, datasetTag, outputPath, outputTxtPath)
    if nargin < 4
        outputTxtPath = '';
    end

    pgTag     = ['pg3d_' datasetTag];
    exportTag = ['img_' datasetTag];
    txtTag    = ['plot3d_' datasetTag];

    try
        % Limpiar nodos previos si existen
        try; model.result.export.remove(exportTag); catch; end
        try; model.result.export.remove(txtTag);    catch; end
        try; model.result.remove(pgTag);            catch; end

        % Crear PlotGroup3D
        model.result.create(pgTag, 'PlotGroup3D');
        model.result(pgTag).set('data', datasetTag);
        model.result(pgTag).create('vol1', 'Volume');
        model.result(pgTag).feature('vol1').set('expr',       'mfnc.By');
        model.result(pgTag).feature('vol1').set('unit',       'mT');
        model.result(pgTag).feature('vol1').set('colortable', 'Inferno');
        model.result(pgTag).run;

        % Crear exportacion de imagen
        model.result.export.create(exportTag, pgTag, 'Image');
        model.result.export(exportTag).set('imagetype',  'png');
        model.result.export(exportTag).set('pngfilename', outputPath);
        model.result.export(exportTag).set('width',      '800');
        model.result.export(exportTag).set('height',     '600');
        model.result.export(exportTag).set('resolution', '96');
        model.result.export(exportTag).run;

        % Exportar TXT del mismo plot 3D (opcional)
        if ~isempty(outputTxtPath)
            model.result.export.create(txtTag, pgTag, 'vol1', 'Plot');
            model.result.export(txtTag).set('filename', outputTxtPath);
            model.result.export(txtTag).run;
        end

    catch cause
        try; model.result.export.remove(exportTag); catch; end
        try; model.result.export.remove(txtTag);    catch; end
        try; model.result.remove(pgTag);            catch; end
        throw(MException('ComsolAnalyzer:export3DPlot', ...
            'Error al exportar plot 3D para dataset "%s": %s', ...
            datasetTag, cause.message));
    end

    % Limpiar nodos temporales
    try; model.result.export.remove(exportTag); catch; end
    try; model.result.export.remove(txtTag);    catch; end
    try; model.result.remove(pgTag);            catch; end
end

