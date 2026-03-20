clear;
clc;
%%

import com.comsol.model.*
import com.comsol.model.util.*

disp('LiveLink is ready')
%% 

%% Options 
% NOTE: To skip any of these steps, set the corresponding option to `false`.

geometryCreate = true; % Create the geometry and generate a new .mph file. 
meshMagnets = true;    % Generate the mesh for the magnets. 
meshFOV = false;        % Generate the mesh for the field of view (FOV). 
meshUniverse = true;   % Generate the mesh for the surrounding domain (air) in the magnetic calculations (universe). 
comsolCalculus = true; % Perform calculations in COMSOL, solving the physics setup. 
resultsPlot = true;    % Generate plots and visualizations of the results. 

%% Define the position and number of magnets on the disks

% IMPORTANT: Verify and update the file path if necessary
alphaData = importdata('Z:\Projects\Kepler\Halbach\50mT_19mmCubes\Kepler_50mT_3200ppms_19mmCubes.txt');


% File: cubeCenterPosX | cubeCenterPosY | cubeCenterPosZ | Br |normalisedMagnX | normalisedMagnY | normalisedMagnZ | cubeSizeX | cubeSizeY | cubeSizeZ
cubeCenterPos(:,1) = alphaData(:,1);
cubeCenterPos(:,2) = alphaData(:,2);
cubeCenterPos(:,3) = alphaData(:,3);
magnetizationDir(:,1) = alphaData(:,5);
magnetizationDir(:,2) = alphaData(:,6);
magnetizationDir(:,3) = alphaData(:,7);
cubeSize(:,1) = alphaData(:,8);
cubeSize(:,2) = alphaData(:,9);
cubeSize(:,3) = alphaData(:,10);    

%% Para añadir shimming:
%% Options
shimmingData = importdata('C:\Users\RF_user\Desktop\Lorena Vega\Next\ComsolConstructor_codes\Import_files\Next\Shimming\shimNEXT4_2nd_round.txt');

% File: cubeCenterPosX | cubeCenterPosY | cubeCenterPosZ | Br |normalisedMagnX | normalisedMagnY | normalisedMagnZ | cubeSizeX | cubeSizeY | cubeSizeZ
shimmingcubeCenterPos(:,1) = shimmingData(:,1);
shimmingcubeCenterPos(:,2) = shimmingData(:,2);
shimmingcubeCenterPos(:,3) = shimmingData(:,3);
shimmingmagnetizationDir(:,1) = shimmingData(:,5);
shimmingmagnetizationDir(:,2) = shimmingData(:,6);
shimmingmagnetizationDir(:,3) = shimmingData(:,7);
shimmingcubeSize(:,1) = shimmingData(:,8);
shimmingcubeSize(:,2) = shimmingData(:,9);
shimmingcubeSize(:,3) = shimmingData(:,10); 
%% 

%
model = ModelUtil.create('Model');
    
model.label('Ring1.mph');

model.component.create('comp1', true);

model.component('comp1').geom.create('geom1', 3);

model.component('comp1').mesh.create('mesh1');


model.study.create('std1');
model.study('std1').create('stat', 'Stationary');



%% Geometry: fov and universe

tic;
fprintf('<strong>Running geometry...</strong>\n')
model.component('comp1').geom('geom1').selection.create('csel1', 'CumulativeSelection');
model.component('comp1').geom('geom1').selection('csel1').label('CumSelMagnets');



% Create FOV 
model.component('comp1').geom('geom1').create('sph1', 'Sphere');
model.component('comp1').geom('geom1').feature('sph1').label('FOV');
model.component('comp1').geom('geom1').feature('sph1').set('r', 0.17);
model.component('comp1').geom('geom1').feature('sph1').set('contributeto', 'csel1');
model.component('comp1').geom('geom1').feature('sph1').set('selresult', true);

%Create universe
model.component('comp1').geom('geom1').create('sph2', 'Sphere');
model.component('comp1').geom('geom1').feature('sph2').label('Universe');
model.component('comp1').geom('geom1').feature('sph2').set('r', 1.5);
model.component('comp1').geom('geom1').feature('sph2').set('contributeto', 'csel1');
model.component('comp1').geom('geom1').feature('sph2').set('selresult', true);


%Create cylinder
model.component('comp1').geom('geom1').create('cyl1', 'Cylinder');
model.component('comp1').geom('geom1').feature('cyl1').set('r', 0.3);
model.component('comp1').geom('geom1').feature('cyl1').set('h', 0.6);
model.component('comp1').geom('geom1').feature('cyl1').set('pos', [-0.3 0 0]);
model.component('comp1').geom('geom1').feature('cyl1').set('axistype', 'x');

%Create workplanes for symmetry: 
    %XY
model.component('comp1').geom('geom1').create('wp1', 'WorkPlane');
model.component('comp1').geom('geom1').feature('wp1').set('unite', true);
model.component('comp1').geom('geom1').feature('wp1').set('quickplane', 'xy');
    %YZ
model.component('comp1').geom('geom1').create('wp2', 'WorkPlane');
model.component('comp1').geom('geom1').feature('wp2').set('unite', true);
model.component('comp1').geom('geom1').feature('wp2').set('quickplane', 'yz');




%% Definition of material properties
model.component('comp1').material.create('mat1', 'Common');
model.component('comp1').material('mat1').propertyGroup('def').func.create('eta', 'Piecewise');
model.component('comp1').material('mat1').propertyGroup('def').func.create('Cp', 'Piecewise');
model.component('comp1').material('mat1').propertyGroup('def').func.create('rho', 'Analytic');
model.component('comp1').material('mat1').propertyGroup('def').func.create('k', 'Piecewise');
model.component('comp1').material('mat1').propertyGroup('def').func.create('cs', 'Analytic');
model.component('comp1').material('mat1').propertyGroup('def').func.create('an1', 'Analytic');
model.component('comp1').material('mat1').propertyGroup('def').func.create('an2', 'Analytic');
model.component('comp1').material('mat1').propertyGroup.create('RefractiveIndex', 'Refractive index');
model.component('comp1').material('mat1').propertyGroup.create('NonlinearModel', 'Nonlinear model');

%Air
model.component('comp1').material('mat1').label('Air');
model.component('comp1').material('mat1').set('family', 'air');
model.component('comp1').material('mat1').propertyGroup('def').func('eta').set('arg', 'T');
model.component('comp1').material('mat1').propertyGroup('def').func('eta').set('pieces', {'200.0' '1600.0' '-8.38278E-7+8.35717342E-8*T^1-7.69429583E-11*T^2+4.6437266E-14*T^3-1.06585607E-17*T^4'});
model.component('comp1').material('mat1').propertyGroup('def').func('eta').set('argunit', 'K');
model.component('comp1').material('mat1').propertyGroup('def').func('eta').set('fununit', 'Pa*s');
model.component('comp1').material('mat1').propertyGroup('def').func('Cp').set('arg', 'T');
model.component('comp1').material('mat1').propertyGroup('def').func('Cp').set('pieces', {'200.0' '1600.0' '1047.63657-0.372589265*T^1+9.45304214E-4*T^2-6.02409443E-7*T^3+1.2858961E-10*T^4'});
model.component('comp1').material('mat1').propertyGroup('def').func('Cp').set('argunit', 'K');
model.component('comp1').material('mat1').propertyGroup('def').func('Cp').set('fununit', 'J/(kg*K)');
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('expr', 'pA*0.02897/R_const[K*mol/J]/T');
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('args', {'pA' 'T'});
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('dermethod', 'manual');
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('argders', {'pA' 'd(pA*0.02897/R_const/T,pA)'; 'T' 'd(pA*0.02897/R_const/T,T)'});
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('argunit', 'Pa,K');
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('fununit', 'kg/m^3');
model.component('comp1').material('mat1').propertyGroup('def').func('rho').set('plotargs', {'pA' '0' '1'; 'T' '0' '1'});
model.component('comp1').material('mat1').propertyGroup('def').func('k').set('arg', 'T');
model.component('comp1').material('mat1').propertyGroup('def').func('k').set('pieces', {'200.0' '1600.0' '-0.00227583562+1.15480022E-4*T^1-7.90252856E-8*T^2+4.11702505E-11*T^3-7.43864331E-15*T^4'});
model.component('comp1').material('mat1').propertyGroup('def').func('k').set('argunit', 'K');
model.component('comp1').material('mat1').propertyGroup('def').func('k').set('fununit', 'W/(m*K)');
model.component('comp1').material('mat1').propertyGroup('def').func('cs').set('expr', 'sqrt(1.4*R_const[K*mol/J]/0.02897*T)');
model.component('comp1').material('mat1').propertyGroup('def').func('cs').set('args', {'T'});
model.component('comp1').material('mat1').propertyGroup('def').func('cs').set('dermethod', 'manual');
model.component('comp1').material('mat1').propertyGroup('def').func('cs').set('argunit', 'K');
model.component('comp1').material('mat1').propertyGroup('def').func('cs').set('fununit', 'm/s');
model.component('comp1').material('mat1').propertyGroup('def').func('cs').set('plotargs', {'T' '273.15' '373.15'});
model.component('comp1').material('mat1').propertyGroup('def').func('an1').set('funcname', 'alpha_p');
model.component('comp1').material('mat1').propertyGroup('def').func('an1').set('expr', '-1/rho(pA,T)*d(rho(pA,T),T)');
model.component('comp1').material('mat1').propertyGroup('def').func('an1').set('args', {'pA' 'T'});
model.component('comp1').material('mat1').propertyGroup('def').func('an1').set('argunit', 'Pa,K');
model.component('comp1').material('mat1').propertyGroup('def').func('an1').set('fununit', '1/K');
model.component('comp1').material('mat1').propertyGroup('def').func('an1').set('plotargs', {'pA' '101325' '101325'; 'T' '273.15' '373.15'});
model.component('comp1').material('mat1').propertyGroup('def').func('an2').set('funcname', 'muB');
model.component('comp1').material('mat1').propertyGroup('def').func('an2').set('expr', '0.6*eta(T)');
model.component('comp1').material('mat1').propertyGroup('def').func('an2').set('args', {'T'});
model.component('comp1').material('mat1').propertyGroup('def').func('an2').set('argunit', 'K');
model.component('comp1').material('mat1').propertyGroup('def').func('an2').set('fununit', 'Pa*s');
model.component('comp1').material('mat1').propertyGroup('def').func('an2').set('plotargs', {'T' '200' '1600'});
model.component('comp1').material('mat1').propertyGroup('def').set('thermalexpansioncoefficient', '');
model.component('comp1').material('mat1').propertyGroup('def').set('molarmass', '');
model.component('comp1').material('mat1').propertyGroup('def').set('bulkviscosity', '');
model.component('comp1').material('mat1').propertyGroup('def').set('thermalexpansioncoefficient', {'alpha_p(pA,T)' '0' '0' '0' 'alpha_p(pA,T)' '0' '0' '0' 'alpha_p(pA,T)'});
model.component('comp1').material('mat1').propertyGroup('def').set('molarmass', '0.02897[kg/mol]');
model.component('comp1').material('mat1').propertyGroup('def').set('bulkviscosity', 'muB(T)');
model.component('comp1').material('mat1').propertyGroup('def').descr('thermalexpansioncoefficient_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').descr('molarmass_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').descr('bulkviscosity_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('relpermeability', {'1' '0' '0' '0' '1' '0' '0' '0' '1'});
model.component('comp1').material('mat1').propertyGroup('def').descr('relpermeability_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('relpermittivity', {'1' '0' '0' '0' '1' '0' '0' '0' '1'});
model.component('comp1').material('mat1').propertyGroup('def').descr('relpermittivity_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('dynamicviscosity', 'eta(T)');
model.component('comp1').material('mat1').propertyGroup('def').descr('dynamicviscosity_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('ratioofspecificheat', '1.4');
model.component('comp1').material('mat1').propertyGroup('def').descr('ratioofspecificheat_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('electricconductivity', {'0[S/m]' '0' '0' '0' '0[S/m]' '0' '0' '0' '0[S/m]'});
model.component('comp1').material('mat1').propertyGroup('def').descr('electricconductivity_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('heatcapacity', 'Cp(T)');
model.component('comp1').material('mat1').propertyGroup('def').descr('heatcapacity_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('density', 'rho(pA,T)');
model.component('comp1').material('mat1').propertyGroup('def').descr('density_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('thermalconductivity', {'k(T)' '0' '0' '0' 'k(T)' '0' '0' '0' 'k(T)'});
model.component('comp1').material('mat1').propertyGroup('def').descr('thermalconductivity_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').set('soundspeed', 'cs(T)');
model.component('comp1').material('mat1').propertyGroup('def').descr('soundspeed_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('def').addInput('temperature');
model.component('comp1').material('mat1').propertyGroup('def').addInput('pressure');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('n', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('ki', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('n', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('ki', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('n', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('ki', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('n', {'1' '0' '0' '0' '1' '0' '0' '0' '1'});
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').set('ki', {'0' '0' '0' '0' '0' '0' '0' '0' '0'});
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').descr('n_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('RefractiveIndex').descr('ki_symmetry', '');
model.component('comp1').material('mat1').propertyGroup('NonlinearModel').set('BA', '(def.gamma+1)/2');
model.component('comp1').material('mat1').propertyGroup('NonlinearModel').descr('BA_symmetry', '');



%N48 nonlinear
model.component('comp1').material.create('mat2', 'Common');
model.component('comp1').material('mat2').selection.named('geom1_csel1_dom');
model.component('comp1').material('mat2').label('N48 (Non linear BHs)');
model.component('comp1').material('mat2').propertyGroup.create('BHsCurve', 'BHsCurve', 'B-Hs Curve');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func.create('BHs', 'Interpolation');
model.component('comp1').material('mat2').label('Nonlinear Permanent Magnet');
%model.component('comp1').material('mat1').set('family', 'iron');
model.component('comp1').material('mat2').propertyGroup('def').set('electricconductivity', {'1/1.4[uohm*m]' '0' '0' '0' '1/1.4[uohm*m]' '0' '0' '0' '1/1.4[uohm*m]'});
model.component('comp1').material('mat2').propertyGroup('def').set('relpermittivity', {'1' '0' '0' '0' '1' '0' '0' '0' '1'});
model.component('comp1').material('mat2').propertyGroup('BHsCurve').label('B-Hs Curve');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').label('Interpolation 1');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').set('table', {'-868' '0';  ...
'-833' '0.28';  ...
'0' '1.38'});
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').set('extrap', 'linear');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').set('fununit', {'T'});
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').set('argunit', {'kA/m'});
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').set('defineinv', true);
model.component('comp1').material('mat2').propertyGroup('BHsCurve').func('BHs').set('defineprimfun', true);
model.component('comp1').material('mat2').propertyGroup('BHsCurve').set('normB', 'BHs(normHsin-Hc)');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').set('normHs', 'BHs_inv(normBin)+Hc');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').set('Hc', 'abs(BHs_inv(0))');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').set('Wpm', 'BHs_prim(normHsin-Hc)');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').descr('normHsin', 'Shifted magnetic field norm');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').descr('normBin', 'Magnetic flux density norm');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').addInput('shiftedmagneticfield');
model.component('comp1').material('mat2').propertyGroup('BHsCurve').addInput('magneticfluxdensity');


%% Add physics: Magnetic fields no currents
model.component('comp1').physics.create('mfnc', 'MagnetostaticsNoCurrents', 'geom1');
model.study('std1').feature('stat').setSolveFor('/physics/mfnc', true);
model.study('std1').feature('stat').set('usestol', true);
model.study('std1').feature('stat').set('stol', 0.01);
model.study('std1').createAutoSequences('all');


%% Create study Stationary
model.study.create('std1');
model.study('std1').create('stat', 'Stationary');
model.study('std1').feature('stat').setSolveFor('/physics/mfnc', true);

%% Geometry: magnets
idxBlkstart = 10;

for idx = 1 : length(cubeCenterPos)
    % Generate shimming magnet geometry
    idxBlk = idx + idxBlkstart;
    
    model.component('comp1').geom('geom1').create(['blk' num2str(idxBlk)], 'Block');
    model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('contributeto', 'csel1');
    model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('selresult', true);
    model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('pos', {num2str(cubeCenterPos(idx,1)), num2str(cubeCenterPos(idx,2)), num2str(cubeCenterPos(idx,3))});
    model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('axis', [magnetizationDir(idx,1), magnetizationDir(idx,2), magnetizationDir(idx,3)]);
    model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('base', 'center');
    model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('size', [cubeSize(idx,1), cubeSize(idx,2), cubeSize(idx,3)]);

    % --- PHYSICS definition ---
  
    model.component('comp1').physics('mfnc').create(['mag' num2str(idxBlk)], 'Magnet', 3);
    model.component('comp1').physics('mfnc').feature(['mag' num2str(idxBlk)]).selection.named(['geom1_blk' num2str(idxBlk) '_dom']);
    model.component('comp1').physics('mfnc').feature(['mag' num2str(idxBlk)]).set('DirectionMethod', 'UserDefined');
    model.component('comp1').physics('mfnc').feature(['mag' num2str(idxBlk)]).set('directionInput', [magnetizationDir(idx,1); magnetizationDir(idx,2); magnetizationDir(idx,3)]);
    model.component('comp1').physics('mfnc').feature(['mag' num2str(idxBlk)]).set('ConstitutiveRelationBH', 'NonlinearPermanentMagnet'); 
    model.component('comp1').physics('mfnc').feature(['mag' num2str(idxBlk)]).label(['Magnet_' num2str(idxBlk) '_X' num2str(cubeCenterPos(idx,1)) '_Y' num2str(cubeCenterPos(idx,2)) '_Z' num2str(cubeCenterPos(idx,3))]);

    disp(['Magnet ' num2str(idxBlk) ': X=' num2str(cubeCenterPos(idx,1)) ', Y=' num2str(cubeCenterPos(idx,2)) ', Z=' num2str(cubeCenterPos(idx,3))]);

    % --- Force calculation ---
    model.component('comp1').physics('mfnc').create(['fcal' num2str(idxBlk)], 'ForceCalculation', 3);
    model.component('comp1').physics('mfnc').feature(['fcal' num2str(idxBlk)]).selection.named(['geom1_blk' num2str(idxBlk) '_dom']);
    model.component('comp1').physics('mfnc').feature(['fcal' num2str(idxBlk)]).label(['Force Calculation_' num2str(idxBlk)]);
    model.component('comp1').physics('mfnc').feature(['fcal' num2str(idxBlk)]).set('TorqueRotationPoint', [cubeCenterPos(idx,1), cubeCenterPos(idx,2), cubeCenterPos(idx,3)]);
    model.component('comp1').physics('mfnc').feature(['fcal' num2str(idxBlk)]).set('ForceName', num2str(idxBlk));
end



%Tolerance for magnet cubes (commented by default [1e-6])
model.component('comp1').geom('geom1').repairTolType('relative');
model.component('comp1').geom('geom1').repairTol(1.0E-4); 
model.component('comp1').geom('geom1').run('fin');
time = toc;
time = time/60;
disp(['Geometry time: ', num2str(time), ' min'])
model.component('comp1').view('view1').set('transparency', true);


%Cumulative selections corrected
%FOV
model.component('comp1').geom('geom1').selection.create('csel2', 'CumulativeSelection');
model.component('comp1').geom('geom1').selection('csel2').label('CumSelFOV');
model.component('comp1').geom('geom1').feature('sph1').set('contributeto', 'csel2');
model.component('comp1').geom('geom1').feature('sph1').set('selresult', true);

%Universe
model.component('comp1').geom('geom1').selection.create('csel3', 'CumulativeSelection');
model.component('comp1').geom('geom1').selection('csel3').label('CumSelUniverse');
model.component('comp1').geom('geom1').feature('sph2').set('contributeto', 'csel3');
model.component('comp1').geom('geom1').feature('sph2').set('selresult', true);


%% Save and launch the model (only for the mfnc module)
 

%% Para generar los cubos del shimming:

model.component('comp1').geom('geom1').selection.create('csel2', 'CumulativeSelection');
model.component('comp1').geom('geom1').selection('csel2').label('CumSelMagnetsShimming');

%% Geometry: magnets of shimming
idxBlkstartShimming = 10;

for idxShimming = 1 : length(shimmingcubeCenterPos)
    % Generate shimming magnet geometry
    idxBlkShimming = idxShimming + idxBlkstartShimming;
    
    model.component('comp1').geom('geom1').create(['blkShimming' num2str(idxBlkShimming)], 'Block');
    model.component('comp1').geom('geom1').feature(['blkShimming' num2str(idxBlkShimming)]).set('contributeto', 'csel2');
    model.component('comp1').geom('geom1').feature(['blkShimming' num2str(idxBlkShimming)]).set('selresult', true);
    model.component('comp1').geom('geom1').feature(['blkShimming' num2str(idxBlkShimming)]).set('pos', {num2str(shimmingcubeCenterPos(idxShimming,1)), num2str(shimmingcubeCenterPos(idxShimming,2)), num2str(shimmingcubeCenterPos(idxShimming,3))});
    model.component('comp1').geom('geom1').feature(['blkShimming' num2str(idxBlkShimming)]).set('axis', [shimmingmagnetizationDir(idxShimming,1), shimmingmagnetizationDir(idxShimming,2), shimmingmagnetizationDir(idxShimming,3)]);
    model.component('comp1').geom('geom1').feature(['blkShimming' num2str(idxBlkShimming)]).set('base', 'center');
    model.component('comp1').geom('geom1').feature(['blkShimming' num2str(idxBlkShimming)]).set('size', [shimmingcubeSize(idxShimming,1), shimmingcubeSize(idxShimming,2), shimmingcubeSize(idxShimming,3)]);

    % --- PHYSICS definition ---
  
    model.component('comp1').physics('mfnc').create(['magShimming' num2str(idxBlkShimming)], 'Magnet', 3);
    model.component('comp1').physics('mfnc').feature(['magShimming' num2str(idxBlkShimming)]).selection.named(['geom1_blkShimming' num2str(idxBlkShimming) '_dom']);
    model.component('comp1').physics('mfnc').feature(['magShimming' num2str(idxBlkShimming)]).set('DirectionMethod', 'UserDefined');
    model.component('comp1').physics('mfnc').feature(['magShimming' num2str(idxBlkShimming)]).set('directionInput', [shimmingmagnetizationDir(idxShimming,1); shimmingmagnetizationDir(idxShimming,2); shimmingmagnetizationDir(idxShimming,3)]);
    model.component('comp1').physics('mfnc').feature(['magShimming' num2str(idxBlkShimming)]).set('ConstitutiveRelationBH', 'NonlinearPermanentMagnet'); 
    model.component('comp1').physics('mfnc').feature(['magShimming' num2str(idxBlkShimming)]).label(['MagnetShimming_' num2str(idxBlkShimming) '_X' num2str(shimmingcubeCenterPos(idxShimming,1)) '_Y' num2str(shimmingcubeCenterPos(idxShimming,2)) '_Z' num2str(shimmingcubeCenterPos(idxShimming,3))]);

    disp(['MagnetShimming ' num2str(idxBlkShimming) ': X=' num2str(shimmingcubeCenterPos(idxShimming,1)) ', Y=' num2str(shimmingcubeCenterPos(idxShimming,2)) ', Z=' num2str(shimmingcubeCenterPos(idxShimming,3))]);

    % --- Force calculation ---
    %model.component('comp1').physics('mfnc').create(['fcalShimming' num2str(idxBlkShimming)], 'ForceCalculationShimming', 3);
    %model.component('comp1').physics('mfnc').feature(['fcalShimming' num2str(idxBlkShimming)]).selection.named(['geom1_blkShimming' num2str(idxBlkShimming) '_dom']);
    %model.component('comp1').physics('mfnc').feature(['fcalShimming' num2str(idxBlkShimming)]).label(['Force Calculation Shimming_' num2str(idxBlkShimming)]);
    %model.component('comp1').physics('mfnc').feature(['fcalShimming' num2str(idxBlkShimming)]).set('TorqueRotationPointShimming', [shimmingcubeCenterPos(idx,1), shimmingcubeCenterPos(idx,2), shimmingcubeCenterPos(idx,3)]);
    %model.component('comp1').physics('mfnc').feature(['fcalShimming' num2str(idxBlkShimming)]).set('ForceName', num2str(idxBlkShimming));
end

%Tolerance for magnet cubes (commented by default [1e-6])
model.component('comp1').geom('geom1').repairTolType('relative');
model.component('comp1').geom('geom1').repairTol(1.0E-4); 
model.component('comp1').geom('geom1').run('fin');
time = toc;
time = time/60;
disp(['Geometry time: ', num2str(time), ' min'])
model.component('comp1').view('view1').set('transparency', true);

%Partition domains
model.component('comp1').geom('geom1').create('pard1', 'PartitionDomains');
model.component('comp1').geom('geom1').feature('pard1').selection('domain').named('csel1');
model.component('comp1').geom('geom1').feature('pard1').set('workplane', 'wp1');
model.component('comp1').geom('geom1').run('pard1');

model.component('comp1').geom('geom1').create('pard2', 'PartitionDomains');
model.component('comp1').geom('geom1').feature('pard2').selection('domain').named('csel1');
model.component('comp1').geom('geom1').feature('pard2').set('workplane', 'wp2');
model.component('comp1').geom('geom1').run('pard2');

%Cumulative selections corrected
%FOV
model.component('comp1').geom('geom1').selection.create('csel3', 'CumulativeSelection');
model.component('comp1').geom('geom1').selection('csel3').label('CumSelFOV');
model.component('comp1').geom('geom1').feature('sph1').set('contributeto', 'csel3');
model.component('comp1').geom('geom1').feature('sph1').set('selresult', true);

%Universe
model.component('comp1').geom('geom1').selection.create('csel4', 'CumulativeSelection');
model.component('comp1').geom('geom1').selection('csel4').label('CumSelUniverse');
model.component('comp1').geom('geom1').feature('sph2').set('contributeto', 'csel4');
model.component('comp1').geom('geom1').feature('sph2').set('selresult', true);


%% Mesh magnets

model.component('comp1').mesh('mesh1').create('map1', 'Map');
model.component('comp1').mesh('mesh1').feature('map1').selection.named('geom1_csel1_bnd');
model.component('comp1').mesh('mesh1').feature('map1').create('dis1', 'Distribution');
model.component('comp1').mesh('mesh1').feature('map1').feature('dis1').selection.named('geom1_csel1_edg');
model.component('comp1').mesh('mesh1').feature('map1').feature('dis1').set('numelem', 8);
model.component('comp1').mesh('mesh1').run('map1');

%% Mesh magnets shimming

model.component('comp1').mesh('mesh1').create('map2', 'Map2');
model.component('comp1').mesh('mesh1').feature('map2').selection.named('geom1_csel2_bnd');
model.component('comp1').mesh('mesh1').feature('map2').create('dis2', 'Distribution');
model.component('comp1').mesh('mesh1').feature('map2').feature('dis2').selection.named('geom1_csel2_edg');
model.component('comp1').mesh('mesh1').feature('map2').feature('dis2').set('numelem', 4);
model.component('comp1').mesh('mesh1').run('map2');





% %% Save and launch the model (only for the mfnc module)
mphsave(model,'C:/Users/RF_user/Desktop/Lorena Vega/Next/Physio2_mfnc_nonlinearBH_20250714_FerPredicted_4400ppm_90mT');
mphlaunch(model)
end


%% Mechanical part component2
model.component.create('comp2', true);

model.component('comp2').geom.create('geom2', 3);

model.component('comp2').mesh.create('mesh2');

model.component('comp2').physics.create('solid', 'SolidMechanics', 'geom2');

model.study.create('std2');
model.study('std2').create('stat', 'Stationary');
model.study('std2').feature('stat').setSolveFor('/physics/solid', true);
model.study('std2').feature('stat').setEntry('activate', 'mfnc', false);

%% Materials of comp2

%Aluminio
model.component('comp2').material.create('mat3', 'Common');
model.component('comp2').material('mat3').propertyGroup.create('Enu', 'Young''s modulus and Poisson''s ratio');
model.component('comp2').material('mat3').label('Aluminum 6063-T83');
model.component('comp2').material('mat3').set('family', 'aluminum');
model.component('comp2').material('mat3').propertyGroup('def').set('relpermeability', {'1' '0' '0' '0' '1' '0' '0' '0' '1'});
model.component('comp2').material('mat3').propertyGroup('def').set('electricconductivity', {'3.030e7[S/m]' '0' '0' '0' '3.030e7[S/m]' '0' '0' '0' '3.030e7[S/m]'});
model.component('comp2').material('mat3').propertyGroup('def').set('thermalexpansioncoefficient', {'23.4e-6[1/K]' '0' '0' '0' '23.4e-6[1/K]' '0' '0' '0' '23.4e-6[1/K]'});
model.component('comp2').material('mat3').propertyGroup('def').set('heatcapacity', '900[J/(kg*K)]');
model.component('comp2').material('mat3').propertyGroup('def').set('relpermittivity', {'1' '0' '0' '0' '1' '0' '0' '0' '1'});
model.component('comp2').material('mat3').propertyGroup('def').set('density', '2700[kg/m^3]');
model.component('comp2').material('mat3').propertyGroup('def').set('thermalconductivity', {'201[W/(m*K)]' '0' '0' '0' '201[W/(m*K)]' '0' '0' '0' '201[W/(m*K)]'});
model.component('comp2').material('mat3').propertyGroup('Enu').set('E', '69[GPa]');
model.component('comp2').material('mat3').propertyGroup('Enu').set('nu', '0.33');
model.component('comp2').material('mat3').set('family', 'aluminum');

%Nylon
model.component('comp2').material.create('mat4', 'Common');
model.component('comp2').material('mat4').propertyGroup.create('Enu', 'Young''s modulus and Poisson''s ratio');
model.component('comp2').material('mat4').label('Nylon');
model.component('comp2').material('mat4').set('family', 'custom');
model.component('comp2').material('mat4').set('customspecular', [0.7843137254901961 0.7843137254901961 0.7843137254901961]);
model.component('comp2').material('mat4').set('customdiffuse', [0.39215686274509803 0.39215686274509803 0.9803921568627451]);
model.component('comp2').material('mat4').set('customambient', [0.39215686274509803 0.39215686274509803 0.7843137254901961]);
model.component('comp2').material('mat4').set('noise', true);
model.component('comp2').material('mat4').set('lighting', 'phong');
model.component('comp2').material('mat4').set('shininess', 500);
model.component('comp2').material('mat4').propertyGroup('def').set('heatcapacity', '1700[J/(kg*K)]');
model.component('comp2').material('mat4').propertyGroup('def').set('relpermittivity', {'4' '0' '0' '0' '4' '0' '0' '0' '4'});
model.component('comp2').material('mat4').propertyGroup('def').set('thermalexpansioncoefficient', {'280e-6[1/K]' '0' '0' '0' '280e-6[1/K]' '0' '0' '0' '280e-6[1/K]'});
model.component('comp2').material('mat4').propertyGroup('def').set('density', '1150[kg/m^3]');
model.component('comp2').material('mat4').propertyGroup('def').set('thermalconductivity', {'0.26[W/(m*K)]' '0' '0' '0' '0.26[W/(m*K)]' '0' '0' '0' '0.26[W/(m*K)]'});
model.component('comp2').material('mat4').propertyGroup('Enu').set('E', '2[GPa]');
model.component('comp2').material('mat4').propertyGroup('Enu').set('nu', '0.4');
model.component('comp2').material('mat4').set('family', 'custom');
model.component('comp2').material('mat4').set('lighting', 'phong');
model.component('comp2').material('mat4').set('shininess', 500);
model.component('comp2').material('mat4').set('ambient', 'custom');
model.component('comp2').material('mat4').set('customambient', [0.39215686274509803 0.39215686274509803 0.7843137254901961]);
model.component('comp2').material('mat4').set('diffuse', 'custom');
model.component('comp2').material('mat4').set('customdiffuse', [0.39215686274509803 0.39215686274509803 0.9803921568627451]);
model.component('comp2').material('mat4').set('specular', 'custom');
model.component('comp2').material('mat4').set('customspecular', [0.7843137254901961 0.7843137254901961 0.7843137254901961]);
model.component('comp2').material('mat4').set('noisecolor', 'custom');
model.component('comp2').material('mat4').set('customnoisecolor', [0 0 0]);
model.component('comp2').material('mat4').set('noisescale', 0);
model.component('comp2').material('mat4').set('noise', 'off');
model.component('comp2').material('mat4').set('noisefreq', 1);
model.component('comp2').material('mat4').set('normalnoisebrush', '0');
model.component('comp2').material('mat4').set('normalnoisetype', '0');
model.component('comp2').material('mat4').set('alpha', 1);
model.component('comp2').material('mat4').set('anisotropyaxis', [0 0 1]);

%% Geometry of the magnets 

model.component('comp2').geom('geom2').selection.create('csel1', 'CumulativeSelection');
model.component('comp2').geom('geom2').selection('csel1').label('CumSelMagnets');

idxBlkstart = 10;

for idx = 1 : length(cubeCenterPos)
    idxBlk = idx+ idxBlkstart;
    % Generate shimming magnet geometry
    model.component('comp2').geom('geom2').create(['blk' num2str(idxBlk)], 'Block');
    model.component('comp2').geom('geom2').feature(['blk' num2str(idxBlk)]).set('contributeto', 'csel1');
    model.component('comp2').geom('geom2').feature(['blk' num2str(idxBlk)]).set('selresult', true);
    model.component('comp2').geom('geom2').feature(['blk' num2str(idxBlk)]).set('pos', {num2str(cubeCenterPos(idx,1)) num2str(cubeCenterPos(idx,2)) num2str(cubeCenterPos(idx,3))});
    % model.component('comp1').geom('geom1').feature(['blk' num2str(idxBlk)]).set('rot', num2str(rad2deg(magn.angleField{idxRad, idxDisc}(idxMagnet))));
    model.component('comp2').geom('geom2').feature(['blk' num2str(idxBlk)]).set('axis', [magnetizationDir(idx, 1) magnetizationDir(idx, 2) magnetizationDir(idx, 3)]);
    model.component('comp2').geom('geom2').feature(['blk' num2str(idxBlk)]).set('base', 'center');
    model.component('comp2').geom('geom2').feature(['blk' num2str(idxBlk)]).set('size', [cubeSize(idx,1) cubeSize(idx,2) cubeSize(idx,3)]);
    
    disp(['Magnet ' num2str(idxBlk) ': X=' num2str(cubeCenterPos(idx,1)) ', Y=' num2str(cubeCenterPos(idx,2)) ', Z=' num2str(cubeCenterPos(idx,3))]);

    % Generate forces and moments applied to each magnet 
    model.component('comp2').physics('solid').create(['rd' num2str(idxBlk)], 'RigidDomain', 3);
    model.component('comp2').physics('solid').feature(['rd' num2str(idxBlk)]).selection.named(['geom2_blk' num2str(idxBlk) '_dom']);
    model.component('comp2').physics('solid').feature(['rd' num2str(idxBlk)]).create(['af' num2str(idxBlk)], 'AppliedForce', -1);
    model.component('comp2').physics('solid').feature(['rd' num2str(idxBlk)]).create(['am' num2str(idxBlk)], 'AppliedMoment', -1);
    model.component('comp2').physics('solid').feature(['rd' num2str(idxBlk)]).feature(['af' num2str(idxBlk)]').set('Ft', {['comp1.mfnc.Forcex_' num2str(idxBlk)] ['comp1.mfnc.Forcey_' num2str(idxBlk)] ['comp1.mfnc.Forcez_' num2str(idxBlk)]});
    model.component('comp2').physics('solid').feature(['rd' num2str(idxBlk)]).feature(['am' num2str(idxBlk)]').set('Mt', {['comp1.mfnc.Tx_' num2str(idxBlk)] ['comp1.mfnc.Ty_' num2str(idxBlk)] ['comp1.mfnc.Tz_' num2str(idxBlk)]});


end

%% Save and launch the model
%mphsave(model,'D:\Lucas 2\Model12AnillosSymmetries');
mphsave(model,'C:\Users\RF_user\Desktop\Lorena Vega\Kepler\90mT\Kepler_nonlinear_nosymm_90mT');
mphlaunch(model)

  



