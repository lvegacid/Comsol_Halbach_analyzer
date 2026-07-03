function export_geometry_plots(model, simulationRoot, hideSelections)
% export_geometry_plots  Export Geometry_3D / Geometry_XY / Geometry_YZ PNGs.
%
% Ejecuta la secuencia COMSOL solicitada para crear view2, ocultar dominios
% seleccionados y reutilizar un unico export de imagen (img6).

    if nargin < 3 || isempty(hideSelections)
        hideSelections = struct('tag', {}, 'label', {});
    end

    if ~exist(simulationRoot, 'dir')
        [ok, msg] = mkdir(simulationRoot);
        if ~ok
            error('No se pudo crear Simulation_results: %s', msg);
        end
    end

    % Cleanup previo para evitar conflictos de tags fijos.
    try
        model.result().export().remove('img6');
    catch
    end
    try
        model.component('comp1').view().remove('view2');
    catch
    end

    % Create geometry view.
    model.component('comp1').view().create('view2', 'geom1');

    model.component('comp1').view('view2').hideObjects().clear();

    model.component('comp1').view('view2').hideEntities().clear();

    % Create hide entities one by one.
    for idx = 1:numel(hideSelections)
        hideTag = sprintf('hide%d', idx);
        model.component('comp1').view('view2').hideEntities().create(hideTag);
        model.component('comp1').view('view2').hideEntities(hideTag).named(hideSelections(idx).tag);
    end

    % Image export with exact requested settings.
    model.result().export().create('img6', 'Image');

    model.result().export('img6').set('size', 'current');
    model.result().export('img6').set('unit', 'px');
    model.result().export('img6').set('height', '600');
    model.result().export('img6').set('width', '800');
    model.result().export('img6').set('lockratio', 'off');
    model.result().export('img6').set('resolution', '96');
    model.result().export('img6').set('antialias', 'on');
    model.result().export('img6').set('zoomextents', 'off');
    model.result().export('img6').set('fontsize', '12');
    model.result().export('img6').set('colortheme', 'globaltheme');
    model.result().export('img6').set('customcolor', [1 1 1]);
    model.result().export('img6').set('background', 'color');
    model.result().export('img6').set('gltfincludelines', 'on');
    model.result().export('img6').set('title1d', 'on');
    model.result().export('img6').set('legend1d', 'on');
    model.result().export('img6').set('logo1d', 'on');
    model.result().export('img6').set('options1d', 'on');
    model.result().export('img6').set('title2d', 'on');
    model.result().export('img6').set('legend2d', 'on');
    model.result().export('img6').set('logo2d', 'on');
    model.result().export('img6').set('options2d', 'off');
    model.result().export('img6').set('title3d', 'on');
    model.result().export('img6').set('legend3d', 'on');
    model.result().export('img6').set('logo3d', 'on');
    model.result().export('img6').set('options3d', 'on');
    model.result().export('img6').set('axisorientation', 'on');
    model.result().export('img6').set('grid', 'on');
    model.result().export('img6').set('axes1d', 'on');
    model.result().export('img6').set('axes2d', 'on');
    model.result().export('img6').set('showgrid', 'on');
    model.result().export('img6').set('target', 'file');
    model.result().export('img6').set('qualitylevel', '92');
    model.result().export('img6').set('qualityactive', 'off');
    model.result().export('img6').set('imagetype', 'png');
    model.result().export('img6').set('lockview', 'off');
    model.result().export('img6').set('highprecisioncolor', 'off');

    model.result().export('img6').set('sourcetype', 'geometry');

    model.result().export('img6').set('sourceobject', 'geom1');

    model.result().export('img6').set('view', 'view2');
    model.component("comp1").view("view2").camera().set("projection", "orthographic");

    % Geometry_3D (no camera changes).

    model.component("comp1").view("view2").camera().set("orthoscale", 1.2);
    model.result().export('img6').set('pngfilename', fullfile(simulationRoot, 'Geometry_3D.png'));
    model.result().export('img6').run();

    % Geometry_XY camera.
    model.component('comp1').view('view2').camera().set('up', [0, 1, 0]);

    model.component('comp1').view('view2').camera().set('position', [0, 0, 1]);
    model.component("comp1").view("view2").camera().set("orthoscale", 1.2);

    model.result().export('img6').set('pngfilename', fullfile(simulationRoot, 'Geometry_XY.png'));
    model.result().export('img6').run();

    % Geometry_YZ camera.
    model.component('comp1').view('view2').camera().set('position', [1, 0, 0]);

    model.component('comp1').view('view2').camera().set('up', [0, 0, 1]);
    model.component("comp1").view("view2").camera().set("orthoscale", 1.2);

    model.result().export('img6').set('pngfilename', fullfile(simulationRoot, 'Geometry_YZ.png'));
    model.result().export('img6').run();
end
