clear; clc;

import com.comsol.model.*
import com.comsol.model.util.*

disp('LiveLink ready')

%% ===============================
% LOAD MODEL
%% ===============================
model = mphload('C:\Users\RF_user\Desktop\Lorena Vega\Kepler\32mm_cube\Fullbody_90mT_linear_32mmcube_1329ppm.mph');

mu0 = 4*pi*1e-7;
datasetTag = 'dset1';

%% ===============================
% COUNT MAGNET DOMAINS
%% ===============================
geom = model.component('comp1').geom('geom1');
featTags = string(geom.feature().tags);
blkTags  = featTags(startsWith(featTags,'blk'));
Nmagnets = numel(blkTags);

disp(['Numero total de cubos: ' num2str(Nmagnets)])

idxBlkstart = 10;   % offset de numeración

%% ===============================
% PREALLOCATE
%% ===============================


Mag_avg = zeros(Nmagnets,1);
Mag_min = zeros(Nmagnets,1);
Mag_max = zeros(Nmagnets,1);
Mag_int = zeros(Nmagnets,1);
Mag_std = zeros(Nmagnets,1);


%% ===============================
% MAIN LOOP (SECOND OPTION)
model.result.numerical.create('avgOp','AvVolume');
model.result.numerical.create('minOp','MinVolume');
model.result.numerical.create('maxOp','MaxVolume');
model.result.numerical.create('intOp','IntVolume');
model.result.numerical.create('stdOp','StdDevVolume');
  
ops = {'avgOp','minOp','maxOp','intOp', 'stdOp'};

for k = 1:numel(ops)
    model.result.numerical(ops{k}).setIndex('expr','mfnc.normM',0);
    model.result.numerical(ops{k}).set('data',datasetTag);
end

tic;

geom = model.component('comp1').geom('geom1');

for idx = 137:137

    idxBlk = idx + idxBlkstart;
    blkTag = ['blk' num2str(idxBlk)];

    % ---- obtener selección del bloque (DESDE GEOMETRÍA) ----
    sel = mphgetselection( geom.feature(blkTag) );
    domIDs = sel.entities;   % dominios reales generados por ese bloque

    % ---- derived values ----
    model.result.numerical('avgOp').selection.set(domIDs);
    Mag_avg(idx) = model.result.numerical('avgOp').getReal;

    model.result.numerical('minOp').selection.set(domIDs);
    Mag_min(idx) = model.result.numerical('minOp').getReal;

    model.result.numerical('maxOp').selection.set(domIDs);
    Mag_max(idx) = model.result.numerical('maxOp').getReal;

    model.result.numerical('intOp').selection.set(domIDs);
    Mag_int(idx) = model.result.numerical('intOp').getReal;

    fprintf('\rProcesando cubos: %d / %d', idx, Nmagnets);

end

elapsedTime = toc;

fprintf('Tiempo total: %.2f segundos (%.2f minutos)\n', ...
        elapsedTime, elapsedTime/60);


% CLEAN UP 

model.result.numerical.remove('avgOp');
model.result.numerical.remove('minOp');
model.result.numerical.remove('maxOp');
model.result.numerical.remove('intOp');
model.result.numerical.remove('stdOp');



%% ===============================
% NORMALIZATION TO % OF Br
%% ===============================
Br_all = 1.4;
M0 = Br_all / mu0;

Mag_avg_pct = 100 * Mag_avg ./ M0;
Mag_min_pct = 100 * Mag_min ./ M0;
Mag_max_pct = 100 * Mag_max ./ M0;

%Mag_int_pct = 100 * Mag_int ./ M0;

%% ===============================
% LOAD PREVIOUSLY EXPORTED COMSOL TXT (FOR RE-PLOTTING HISTOGRAMS)
%% ===============================

% --- ruta fija al archivo ---
fullTxtFile = ...
    'Z:\Projects\Preclinico\Halbach\142mT\Demagnetization\Nonlinear_N45SH\preclinico_1layer_142mT_74ppms_filtrado_nonlinear_Comsol_demagnetization.txt';

% --- leer datos ---
data = readmatrix(fullTxtFile);

% =========================================================
% Column order MUST match your export:
%  1  X
%  2  Y
%  3  Z
%  4  Br
%  5  Mx_dir
%  6  My_dir
%  7  Mz_dir
%  8  SizeX
%  9  SizeY
% 10  SizeZ
% 11  Mag_avg
% 12  Mag_min
% 13  Mag_max
% 14  Mag_std
% 15  Mag_int
% =========================================================

% --- reconstruir variables EXACTAS usadas en los plots ---
Mag_avg = data(:,11);
Mag_min = data(:,12);
Mag_max = data(:,13);
Mag_std = data(:,14);
Mag_int = data(:,15);

% --- normalización igual que antes ---
mu0 = 4*pi*1e-7;

%Br_all = data(:,4);              % Br por cubo
Br_all=1.32;
M0     = Br_all ./ mu0;          % referencia local

Mag_avg_pct = 100 * Mag_avg ./ M0;
Mag_min_pct = 100 * Mag_min ./ M0;
Mag_max_pct = 100 * Mag_max ./ M0;

% --- asegurar formato columna (por seguridad) ---
Mag_avg_pct = Mag_avg_pct(:);
Mag_min_pct = Mag_min_pct(:);
Mag_max_pct = Mag_max_pct(:);

Nmagnets = numel(Mag_avg_pct);

disp(['Datos cargados correctamente: ' num2str(Nmagnets) ' cubos'])

%% ===============================
% COMPARATIVE HORIZONTAL HISTOGRAMS (AVG / MIN / MAX)
%% ===============================

Nbins = 5;

% --- asegurar formato numérico ---
Mag_avg_pct = double(Mag_avg_pct(:));
Mag_min_pct = double(Mag_min_pct(:));
Mag_max_pct = double(Mag_max_pct(:));

Nmagnets = numel(Mag_avg_pct);

meanAvg = mean(Mag_avg_pct);
meanMin = mean(Mag_min_pct);
meanMax = mean(Mag_max_pct);

% ---- RANGO COMÚN SOLO PARA VISUALIZACIÓN ----
yMin = min([Mag_avg_pct; Mag_min_pct; Mag_max_pct]);
yMax = max([Mag_avg_pct; Mag_min_pct; Mag_max_pct]);

margin = 0.05*(yMax - yMin);
yMin = yMin - margin;
yMax = yMax + margin;

figure('Units','normalized','Position',[0.05 0.25 0.9 0.45])


% -------- AVERAGE --------

subplot(1,3,1)
h = histogram(Mag_avg_pct, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1);

hold on
yline(meanAvg,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanAvg, ...
    sprintf('Mean = %.2f %%', meanAvg), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b','FontSize',10)

% ---- porcentajes por bin ----
counts  = h.Values;
edges   = h.BinEdges;
centers = (edges(1:end-1) + edges(2:end)) / 2;

for i = 1:numel(counts)
    if counts(i) > 0
        pct = 100 * counts(i) / Nmagnets;
        text(counts(i) + max(counts)*0.02, centers(i), ...
            sprintf('%.1f %%', pct), ...
            'VerticalAlignment','middle','FontSize',9);
    end
end

hold off
xlabel('Número de cubos')
ylabel('Magnetización (%)')
title('Average')
grid on
ylim([yMin yMax])


% -------- MINIMUM --------

subplot(1,3,2)
h = histogram(Mag_min_pct, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1);

hold on
yline(meanMin,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanMin, ...
    sprintf('Mean = %.2f %%', meanMin), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b','FontSize',10)

counts  = h.Values;
edges   = h.BinEdges;
centers = (edges(1:end-1) + edges(2:end)) / 2;

for i = 1:numel(counts)
    if counts(i) > 0
        pct = 100 * counts(i) / Nmagnets;
        text(counts(i) + max(counts)*0.02, centers(i), ...
            sprintf('%.1f %%', pct), ...
            'VerticalAlignment','middle','FontSize',9);
    end
end

hold off
xlabel('Número de cubos')
ylabel('Magnetización (%)')
title('Minimum')
grid on
ylim([yMin yMax])

% -------- MAXIMUM --------

subplot(1,3,3)
h = histogram(Mag_max_pct, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1);

hold on
yline(meanMax,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanMax, ...
    sprintf('Mean = %.2f %%', meanMax), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b','FontSize',10)

counts  = h.Values;
edges   = h.BinEdges;
centers = (edges(1:end-1) + edges(2:end)) / 2;

for i = 1:numel(counts)
    if counts(i) > 0
        pct = 100 * counts(i) / Nmagnets;
        text(counts(i) + max(counts)*0.02, centers(i), ...
            sprintf('%.1f %%', pct), ...
            'VerticalAlignment','middle','FontSize',9);
    end
end

hold off
xlabel('Número de cubos')
ylabel('Magnetización (%)')
title('Maximum')
grid on
ylim([yMin yMax])

sgtitle('Magnetization distribution per cube')


%% ===============================
% SCATTER – MAGNET HEALTH MAP (AVG vs MIN)
%% ===============================

figure('Units','normalized','Position',[0.25 0.25 0.5 0.5])

scatter(Mag_avg_pct, Mag_min_pct, ...
    80, 'filled')

grid on
box on

xlabel('Average magnetization [% of Br]')
ylabel('Minimum magnetization [% of Br]')
title('Magnet health map (average vs minimum)')

hold on

% --- diagonal reference (ideal homogeneity) ---
plot([min(Mag_avg_pct) max(Mag_avg_pct)], ...
     [min(Mag_avg_pct) max(Mag_avg_pct)], ...
     'k--','LineWidth',1)

hold off


%% ===============================
% SCATTER – MAGNET HEALTH MAPS (2-IN-1)
%% ===============================
Br=1.32;

% --- métricas auxiliares ---
Mag_std_pct_Br = 100 * Mag_std ./ (Br / mu0);   % STD [% of Br]

figure('Units','normalized','Position',[0.05 0.25 0.9 0.45])


% (1) MIN vs AVERAGE

subplot(1,2,1)

scatter(Mag_avg_pct, Mag_min_pct, 80, 'filled')

grid on
box on

xlabel('Average magnetization [% of Br]')
ylabel('Minimum magnetization [% of Br]')
title('Min vs Average')

hold on
plot([min(Mag_avg_pct) max(Mag_avg_pct)], ...
     [min(Mag_avg_pct) max(Mag_avg_pct)], ...
     'k--','LineWidth',1)
hold off


% (2) STD vs AVERAGE

subplot(1,2,2)

scatter(Mag_avg_pct, Mag_std_pct_Br, 80, 'filled')

grid on
box on

xlabel('Average magnetization [% of Br]')
ylabel('\sigma(|M|)  [% of Br]')
title('STD vs Average')

hold on
plot([min(Mag_avg_pct) max(Mag_avg_pct)], ...
     [0 0], ...
     'k--','LineWidth',1)
hold off


%% ===============================
% HISTOGRAMS – MAGNETIZATION HETEROGENEITY METRICS
%% ===============================
Nbins = 5;

% ---- METRICS ----
Mag_std_mT       = Mag_std * mu0 * 1e3;      % [mT]
Mag_std_rel_avg  = (Mag_std) ./ Mag_avg;       % [-]
M0               = Br / mu0;                 % [A/m]
Mag_std_pct_Br   = 100 * Mag_std ./ M0;      % [%]

mean_std_mT      = mean(Mag_std_mT);
mean_rel_avg     = mean(Mag_std_rel_avg);
mean_pct_Br      = mean(Mag_std_pct_Br);

% ---- FIGURE ----
figure('Units','normalized','Position',[0.03 0.25 0.94 0.45])

% -------- ABSOLUTE STD (mT) --------
subplot(1,2,1)
histogram(Mag_std_mT,'NumBins',Nbins,'Orientation','horizontal', ...
          'FaceAlpha',0.6,'EdgeColor','k','LineWidth',1)
hold on
yline(mean_std_mT,'b-','LineWidth',1.2)
text(max(xlim)*0.95, mean_std_mT, ...
    sprintf('Mean = %.2f mT', mean_std_mT), ...
    'HorizontalAlignment','right','VerticalAlignment','bottom','Color','b')
hold off
xlabel('Número de cubos')
ylabel('\sigma(|B|)  [mT]')
title('STD absolute')
grid on


% -------- STD RELATIVE TO Br --------
subplot(1,2,2)
histogram(Mag_std_pct_Br,'NumBins',Nbins,'Orientation','horizontal', ...
          'FaceAlpha',0.6,'EdgeColor','k','LineWidth',1)
hold on
yline(mean_pct_Br,'b-','LineWidth',1.2)
text(max(xlim)*0.95, mean_pct_Br, ...
    sprintf('Mean = %.2f %%', mean_pct_Br), ...
    'HorizontalAlignment','right','VerticalAlignment','bottom','Color','b')
hold off
xlabel('Número de cubos')
ylabel('\sigma(|M|) / M_0  [%]')
title('STD / Br')
grid on

sgtitle('Magnetization heterogeneity metrics')


% STD interno medio (en mT, por ejemplo)
sigma_internal = sqrt(mean(Mag_std_mT.^2))

% STD entre medias de cubos
sigma_between  = std(Mag_avg * mu0 * 1e3)

% STD global reconstruido
sigma_global = sqrt(sigma_internal^2 + sigma_between^2)

%% ===============================
% EXPORT COMBINED DATA TO TXT
% ===============================

inputFile = 'Z:\Projects\Kepler\Halbach\90mT\fullbody_90mT_55ppms(cube).txt';
alphaData = importdata(inputFile);

% File: cubeCenterPosX | cubeCenterPosY | cubeCenterPosZ | Br |normalisedMagnX | normalisedMagnY | normalisedMagnZ | cubeSizeX | cubeSizeY | cubeSizeZ
cubeCenterPos(:,1) = alphaData(:,1);
cubeCenterPos(:,2) = alphaData(:,2);
cubeCenterPos(:,3) = alphaData(:,3);

Br_all      = alphaData(:,4);
MagDir_all  = alphaData(:,5:7);
CubeSize_all = alphaData(:,8:10);

% --- asegurar formato columna ---
Mag_avg = Mag_avg(:);
Mag_min = Mag_min(:);
Mag_max = Mag_max(:);
Mag_int = Mag_int(:);
Mag_std = Mag_std(:);

% --- combinar datos ---
outputData = [ ...
    cubeCenterPos(:,1), ...   % X
    cubeCenterPos(:,2), ...   % Y
    cubeCenterPos(:,3), ...   % Z
    Br_all(:),          ...   % Br
    MagDir_all(:,1),    ...   % Mx_dir
    MagDir_all(:,2),    ...   % My_dir
    MagDir_all(:,3),    ...   % Mz_dir
    CubeSize_all(:,1),  ...   % SizeX
    CubeSize_all(:,2),  ...   % SizeY
    CubeSize_all(:,3),  ...   % SizeZ
    Mag_avg,            ...   % <|M|> volume avg
    Mag_min,            ...   % min |M|
    Mag_max,            ...   % max |M|
    Mag_std,            ...   % std |M|
    Mag_int             ...   % ∫|M| dV
];

% --- construir nombre de archivo ---
[inputPath, inputName, ~] = fileparts(inputFile);

outputFile = fullfile(inputPath, ...
    [inputName '_Comsol_demagnetization.txt']);

% --- escribir archivo ---
fileID = fopen(outputFile,'w');

fprintf(fileID, ...
    ['X\tY\tZ\tBr\tMx_dir\tMy_dir\tMz_dir\t' ...
     'SizeX\tSizeY\tSizeZ\t' ...
     'Mag_avg(A/m)\tMag_min(A/m)\tMag_max(A/m)\tMag_std(A/m)\tMag_int(A/m)\n']);

fprintf(fileID, ...
    ['%.6e\t%.6e\t%.6e\t%.6f\t' ...
     '%.6f\t%.6f\t%.6f\t' ...
     '%.6e\t%.6e\t%.6e\t' ...
     '%.6e\t%.6e\t%.6e\t%.6e\t%.6e\n'], ...
     outputData.');

fclose(fileID);

fprintf('Archivo exportado:\n%s\n', outputFile);

%% === COMPARACIÓN: 62 mm vs 32 mm ===

mu0 = 4*pi*1e-7;

% --- ARCHIVOS ---
file_nonlinear_62 = ...
'Z:\Projects\Kepler\Halbach\90mT\Nonlinear\fullbody_90mT_55ppms(cube)_nonlinear_Comsol_demagnetization.txt';

file_linear_62 = ...
'Z:\Projects\Kepler\Halbach\90mT\Linear\fullbody_90mT_55ppms(cube)_linear_Comsol_demagnetization.txt';

file_linear_32 = ...
'Z:\Projects\Kepler\Halbach\90mT_32mmCubes\fullbody_90mT_771ppms(cube)_32mmcubes_Comsol_demagnetization.txt';

% === CARGA DATOS ===
data_nl_62 = readmatrix(file_nonlinear_62);
data_l_62  = readmatrix(file_linear_62);
data_l_32  = readmatrix(file_linear_32);

% Columnas:
% 11: Mag_avg (A/m)
% 12: Mag_min (A/m)
%  4: Br (T)

% === COMPARACIÓN ===
% --- Nonlinear 62 mm ---
M0_nl_62 = data_nl_62(:,4) ./ mu0;
Mag_avg_nl_62 = 100 * data_nl_62(:,11) ./ M0_nl_62;
Mag_min_nl_62 = 100 * data_nl_62(:,12) ./ M0_nl_62;

% --- Linear 62 mm ---
M0_l_62 = data_l_62(:,4) ./ mu0;
Mag_avg_l_62 = 100 * data_l_62(:,11) ./ M0_l_62;
Mag_min_l_62 = 100 * data_l_62(:,12) ./ M0_l_62;

% --- Linear 32 mm ---
M0_l_32 = data_l_32(:,4) ./ mu0;
Mag_avg_l_32 = 100 * data_l_32(:,11) ./ M0_l_32;
Mag_min_l_32 = 100 * data_l_32(:,12) ./ M0_l_32;

% === RANGOS COMUNES ===
xmin = min([Mag_avg_nl_62; Mag_avg_l_62; Mag_avg_l_32]);
xmax = max([Mag_avg_nl_62; Mag_avg_l_62; Mag_avg_l_32]);

% === FIGURA ===
figure('Units','normalized','Position',[0.2 0.25 0.55 0.55])
hold on

% --- NONLINEAR 62 mm (verde claro) ---
scatter(Mag_avg_nl_62, Mag_min_nl_62, ...
    20, 'filled', ...
    'MarkerFaceColor',[0.60 0.85 0.60])

% --- LINEAR 62 mm (verde oscuro) ---
scatter(Mag_avg_l_62, Mag_min_l_62, ...
    20, 'filled', ...
    'MarkerFaceColor',[0.00 0.50 0.00])

% --- LINEAR 32 mm (naranja) ---
scatter(Mag_avg_l_32, Mag_min_l_32, ...
    20, 'filled', ...
    'MarkerFaceColor',[0.85 0.33 0.10], 'MarkerFaceAlpha', 0.3)

% --- DIAGONAL IDEAL ---
plot([xmin xmax],[xmin xmax],'k--','LineWidth',1)

hold off
grid on
box on


xlabel('Average magnetization [% of Br]')
ylabel('Minimum magnetization [% of Br]')
title('Magnet health map: Minimum vs Average')

legend({ ...
    '62 mm – Nonlinear', ...
    '62 mm – Linear', ...
    '32 mm – Linear', ...
    'Ideal homogeneity'}, ...
    'Location','southwest')

%% ===============================
% HISTOGRAMS – MAGNETIZATION DISTRIBUTION PER CUBE
%% ===============================
Nbins = 5;

meanAvg = mean(Mag_avg_pct);
meanMin = mean(Mag_min_pct);
meanMax = mean(Mag_max_pct);

figure('Units','normalized','Position',[0.05 0.25 0.9 0.45])

% -------- AVERAGE --------
subplot(1,3,1)
histogram(Mag_avg_pct, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1)
hold on
yline(meanAvg,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanAvg, ...
    sprintf('Mean = %.2f %%', meanAvg), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b')
hold off
xlabel('Número de cubos')
ylabel('Magnetización (%)')
title('Average')
grid on


% -------- MINIMUM --------
subplot(1,3,2)
histogram(Mag_min_pct, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1)
hold on
yline(meanMin,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanMin, ...
    sprintf('Mean = %.2f %%', meanMin), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b')
hold off
xlabel('Número de cubos')
ylabel('Magnetización (%)')
title('Minimum')
grid on


% -------- MAXIMUM --------
subplot(1,3,3)
histogram(Mag_max_pct, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1)
hold on
yline(meanMax,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanMax, ...
    sprintf('Mean = %.2f %%', meanMax), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b')
hold off
xlabel('Número de cubos')
ylabel('Magnetización (%)')
title('Maximum')
grid on

sgtitle('Magnetization distribution per cube')


%% ===============================
% HISTOGRAM – ABSOLUTE STANDARD DEVIATION (mT)
%% ===============================
Nbins = 5;

% Conversión de A/m a mT
Mag_std_mT = Mag_std * mu0 * 1e3; 

meanStd_mT = mean(Mag_std_mT);

figure('Units','normalized','Position',[0.2 0.3 0.6 0.45])

histogram(Mag_std_mT, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1)
hold on

yline(meanStd_mT,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanStd_mT, ...
    sprintf('Mean = %.2f mT', meanStd_mT), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b', ...
    'FontSize',10)

hold off

xlabel('Número de cubos')
ylabel('\sigma(|B|)  [mT]')
title('Standard deviation of magnetization (absolute)')
grid on

std(Mag_std_mT)

% STD interno medio (en mT, por ejemplo)
sigma_internal = sqrt(mean(Mag_std_mT.^2))

% STD entre medias de cubos
sigma_between  = std(Mag_avg * mu0 * 1e3)

% STD global reconstruido
sigma_global = sqrt(sigma_internal^2 + sigma_between^2)
%% ===============================
% HISTOGRAMS – MAGNETIZATION HETEROGENEITY METRICS
%% ===============================
Nbins = 5;
Br=1.4
% ---- METRICS ----
Mag_std_mT       = Mag_std * mu0 * 1e3;      % [mT]
Mag_std_rel_avg  = Mag_std ./ Mag_avg;       % [-]
M0               = Br / mu0;                 % [A/m]
Mag_std_pct_Br   = 100 * Mag_std ./ M0;      % [%]

mean_std_mT      = mean(Mag_std_mT);
mean_rel_avg     = mean(Mag_std_rel_avg);
mean_pct_Br      = mean(Mag_std_pct_Br);

% ---- FIGURE ----
figure('Units','normalized','Position',[0.03 0.25 0.94 0.45])

% -------- ABSOLUTE STD (mT) --------
subplot(1,3,1)
histogram(Mag_std_mT,'NumBins',Nbins,'Orientation','horizontal', ...
          'FaceAlpha',0.6,'EdgeColor','k','LineWidth',1)
hold on
yline(mean_std_mT,'b-','LineWidth',1.2)
text(max(xlim)*0.95, mean_std_mT, ...
    sprintf('Mean = %.2f mT', mean_std_mT), ...
    'HorizontalAlignment','right','VerticalAlignment','bottom','Color','b')
hold off
xlabel('Número de cubos')
ylabel('\sigma(|B|)  [mT]')
title('STD absolute')
grid on

% -------- STD RELATIVE TO AVG --------
subplot(1,3,2)
histogram(Mag_std_rel_avg,'NumBins',Nbins,'Orientation','horizontal', ...
          'FaceAlpha',0.6,'EdgeColor','k','LineWidth',1)
hold on
yline(mean_rel_avg,'b-','LineWidth',1.2)
text(max(xlim)*0.95, mean_rel_avg, ...
    sprintf('Mean = %.2f %%', 100*mean_rel_avg), ...
    'HorizontalAlignment','right','VerticalAlignment','bottom','Color','b')
hold off
xlabel('Número de cubos')
ylabel('\sigma(|M|)/<|M|>  [-]')
title('STD / average')
grid on

% -------- STD RELATIVE TO Br --------
subplot(1,3,3)
histogram(Mag_std_pct_Br,'NumBins',Nbins,'Orientation','horizontal', ...
          'FaceAlpha',0.6,'EdgeColor','k','LineWidth',1)
hold on
yline(mean_pct_Br,'b-','LineWidth',1.2)
text(max(xlim)*0.95, mean_pct_Br, ...
    sprintf('Mean = %.2f %%', mean_pct_Br), ...
    'HorizontalAlignment','right','VerticalAlignment','bottom','Color','b')
hold off
xlabel('Número de cubos')
ylabel('\sigma(|M|) / M_0  [%]')
title('STD / Br')
grid on

sgtitle('Magnetization heterogeneity metrics')

%% ===============================
% SCATTER – MAGNET HEALTH MAP
%% ===============================

% Métrica de heterogeneidad relativa (%)
Mag_std_rel_pct = 100 * Mag_std ./ Mag_avg;

figure('Units','normalized','Position',[0.25 0.25 0.5 0.5])

scatter(Mag_avg_pct, Mag_std_rel_pct, ...
    80, 'filled')

grid on
box on

xlabel('Average magnetization [% of Br]')
ylabel('\sigma(|M|) / <|M|>  [%]')
title('Magnet health map (average vs heterogeneity)')

% ---- GUIDELINES (OPTIONAL BUT RECOMMENDED) ----
hold on

% Vertical lines: magnetization level
xline(95,'k--','95 %','LineWidth',1)
xline(90,'k--','90 %','LineWidth',1)
xline(80,'k--','80 %','LineWidth',1)

% Horizontal lines: heterogeneity
yline(1,'r--','1 %','LineWidth',1)
yline(3,'r--','3 %','LineWidth',1)
yline(5,'r--','5 %','LineWidth',1)

hold off


%% ===============================
% HISTOGRAM – AVERAGE
% ===============================
Nbins = 5;

minAvg = min(Mag_avg_pct);
maxAvg = max(Mag_avg_pct);

edgesAvg = linspace(minAvg, maxAvg, Nbins+1);

meanAvg = mean(Mag_avg_pct);

figure
histogram(Mag_avg_pct, edgesAvg)
hold on
xline(meanAvg, 'b-', ...
    sprintf('Media = %.2f %%', meanAvg), ...
    'LineWidth', 2, ...
    'LabelOrientation', 'horizontal', ...
    'LabelVerticalAlignment', 'bottom');
hold off
xlabel('Magnetización media (%)')
ylabel('Número de cubos')
title('Histogram – Average Magnetization')
grid on

% ===============================
% HISTOGRAM – MINIMUM 
% ===============================
minMin = min(Mag_min_pct);
maxMin = max(Mag_min_pct);

edgesMin = linspace(minMin, maxMin, Nbins+1);
meanMin = mean(Mag_min_pct);

figure
histogram(Mag_min_pct, edgesMin)
xline(meanMin, 'b-', ...
    sprintf('Media = %.2f %%', meanMin), ...
    'LineWidth', 2, ...
    'LabelOrientation', 'horizontal', ...
    'LabelVerticalAlignment', 'bottom');
hold off
xlabel('Magnetización mínima (%)')
ylabel('Número de cubos')
title('Histogram – Minimum Magnetization')
grid on


% ===============================
% HISTOGRAM – MAXIMUM + MEAN VALUE
% ===============================
minMax = min(Mag_max_pct);
maxMax = max(Mag_max_pct);

edgesMax = linspace(minMax, maxMax, Nbins+1);

meanMax = mean(Mag_max_pct);

figure
histogram(Mag_max_pct, edgesMax)
hold on

xline(meanMax, 'b-', ...
    sprintf('Media = %.2f %%', meanMax), ...
    'LineWidth', 2, ...
    'LabelOrientation', 'horizontal', ...
    'LabelVerticalAlignment', 'bottom');
hold off

xlabel('Magnetización máxima (%)')
ylabel('Número de cubos')
title('Histogram – Maximum Magnetization')
grid on


% ===============================
% HISTOGRAM – STANDARD DEVIATION
% ===============================
Nbins = 5;

minStd = min(Mag_std);
maxStd = max(Mag_std);

edgesStd = linspace(minStd, maxStd, Nbins+1);

meanStd = mean(Mag_std);

figure
histogram(Mag_std, edgesStd)
hold on
xline(meanStd, 'b-', ...
    sprintf('Media = %.3e', meanStd), ...
    'LineWidth', 2, ...
    'LabelOrientation', 'horizontal', ...
    'LabelVerticalAlignment', 'bottom');
hold off

xlabel('Desviación estándar volumétrica |M|  [A/m]')
ylabel('Número de cubos')
title('Histogram – Magnetization Standard Deviation')
grid on


%% ===============================
% HISTOGRAM – VOLUME INTEGRATION (|M| dV)
%% ===============================
Nbins = 5;

meanInt = mean(Mag_int);

% Rango común solo para la integral
yMinInt = min(Mag_int);
yMaxInt = max(Mag_int);

% Margen visual
margin = 0.05*(yMaxInt - yMinInt);
yMinInt = yMinInt - margin;
yMaxInt = yMaxInt + margin;

figure('Units','normalized','Position',[0.2 0.3 0.6 0.45])

histogram(Mag_int, ...
    'NumBins',Nbins, ...
    'Orientation','horizontal', ...
    'FaceAlpha',0.6, ...
    'EdgeColor','k', ...
    'LineWidth',1)
hold on

yline(meanInt,'b-','LineWidth',1.2)
text(max(xlim)*0.95, meanInt, ...
    sprintf('Mean = %.3e', meanInt), ...
    'HorizontalAlignment','right', ...
    'VerticalAlignment','bottom', ...
    'Color','b', ...
    'FontSize',10)

hold off

xlabel('Número de cubos')
ylabel('∫ |M| dV  [A·m²]')
title('Histogram – Magnetization volume integral (5 bins)')
grid on
ylim([yMinInt yMaxInt])


%% ===============================
% 3D MAPS
%% ===============================
figure
scatter3(cubeCenterPos(:,1),cubeCenterPos(:,2),cubeCenterPos(:,3), ...
         60,Mag_min_pct,'filled')
axis equal
colorbar
title('3D map – Minimum magnetization (%)')
xlabel('X'); ylabel('Y'); zlabel('Z')
grid on

figure
scatter3(cubeCenterPos(:,1),cubeCenterPos(:,2),cubeCenterPos(:,3), ...
         60,Mag_avg_pct,'filled')
axis equal
colorbar
title('3D map – Average magnetization (%)')
xlabel('X'); ylabel('Y'); zlabel('Z')
grid on

%% ===============================
% CRITICAL CUBES
%% ===============================
criticalIdx = find(Mag_min_pct < 80);
disp(['Cubos críticos (<80%): ' num2str(numel(criticalIdx))])
criticalIdx'


%% ===============================
% MAIN LOOP (DERIVED VALUES STYLE)
idxBlkstart = 10;   % offset de numeración

tic;

for idx = 1:Nmagnets

    domID = idx + idxBlkstart;   % dominio del cubo

    % -------- VOLUME AVERAGE --------
    model.result.numerical.create('avgTmp','AvVolume');
    model.result.numerical('avgTmp').selection.set(domID);
    model.result.numerical('avgTmp').setIndex('expr','mfnc.normM',0);
    model.result.numerical('avgTmp').set('data',datasetTag);
    Mag_avg(idx) = model.result.numerical('avgTmp').getReal;
    model.result.numerical.remove('avgTmp');

    % -------- VOLUME MIN --------
    model.result.numerical.create('minTmp','MinVolume');
    model.result.numerical('minTmp').selection.set(domID);
    model.result.numerical('minTmp').setIndex('expr','mfnc.normM',0);
    model.result.numerical('minTmp').set('data',datasetTag);
    Mag_min(idx) = model.result.numerical('minTmp').getReal;
    model.result.numerical.remove('minTmp');

    % -------- VOLUME MAX --------
    model.result.numerical.create('maxTmp','MaxVolume');
    model.result.numerical('maxTmp').selection.set(domID);
    model.result.numerical('maxTmp').setIndex('expr','mfnc.normM',0);
    model.result.numerical('maxTmp').set('data',datasetTag);
    Mag_max(idx) = model.result.numerical('maxTmp').getReal;
    model.result.numerical.remove('maxTmp');

    % -------- VOLUME INTEGRATION --------
    model.result.numerical.create('intTmp','IntVolume');
    model.result.numerical('intTmp').selection.set(domID);
    model.result.numerical('intTmp').setIndex('expr','mfnc.normM',0);
    model.result.numerical('intTmp').set('data',datasetTag);
    Mag_int(idx) = model.result.numerical('intTmp').getReal;
    model.result.numerical.remove('intTmp');

    % -------- VOLUME STANDARD DEVIATION --------
    model.result.numerical.create('stdTmp','StdDevVolume');
    model.result.numerical('stdTmp').selection.set(domID);
    model.result.numerical('stdTmp').setIndex('expr','mfnc.normM',0);
    model.result.numerical('stdTmp').set('data',datasetTag);
    Mag_std(idx) = model.result.numerical('stdTmp').getReal;
    model.result.numerical.remove('stdTmp');

    % ---- PROGRESS PRINT ----
    fprintf('\rProcesando cubos: %d / %d', idx, Nmagnets);

end

elapsedTime = toc;

fprintf('Tiempo total: %.2f segundos (%.2f minutos)\n', ...
        elapsedTime, elapsedTime/60);

