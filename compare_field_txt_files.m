% compare_field_txt_files.m
% Standalone utility to compare two field TXT files and export:
% 1) B_diff histogram TXT (BFOV style)
% 2) BFOV PNG from [x,y,z,B_diff]
% 3) BFOV histogram PNG (using the same Python postprocess as GUI)
% 3) Pointwise table [x y z B_diff]

clear;
clc;

%% ===================== USER INPUTS =====================
file2_path = "Z:\Projects\PhysioII - NextMRI\Magnet\Comsol\Shimming_arbitrary_rotations\20260520_Odin3_Cube_arbRot2D_3e4Iter_factor1e8_ineq3e-3_81mT_2515ppmsFlat_2529ppmsLinear\campoFOV_mT.txt";
file1_path = "Z:\Projects\PhysioII - NextMRI\Magnet\Comsol\Shimming_arbitrary_rotations\20260520_Odin3_Cube_arbRot2D_3e4Iter_factor1e8_ineq3e-3_81mT_2515ppmsFlat_2529ppmsLinear\Linear\B_coordinates_FromFile_campoFOV_mT_cols_1_2_3.txt";

col_coordinates_file1 = [1 2 3];
col_coordinates_file2 = [1 2 3];

col_By_file1 = 5;
col_By_file2 = 4;

% Optional settings
output_dir = "Z:\Projects\PhysioII - NextMRI\Magnet\Comsol\Shimming_arbitrary_rotations\20260520_Odin3_Cube_arbRot2D_3e4Iter_factor1e8_ineq3e-3_81mT_2515ppmsFlat_2529ppmsLinear\Linear";                 % empty -> same folder as file1
output_prefix = "comparison";    % base name for generated files
hist_bins = 100;
coord_tolerance = 1e-9;

magnet_info = "Comparison";
fov_info = "N/A";
analysis_info = "B_file1 + B_file2";
require_python_style = true;  % true => exact same format as GUI Python postprocess
%% =======================================================

if strlength(strtrim(file1_path)) == 0 || strlength(strtrim(file2_path)) == 0
    error('Please set file1_path and file2_path before running the script.');
end

file1_path = char(file1_path);
file2_path = char(file2_path);

if ~isfile(file1_path)
    error('file1_path does not exist: %s', file1_path);
end
if ~isfile(file2_path)
    error('file2_path does not exist: %s', file2_path);
end

if isempty(output_dir)
    output_dir = fileparts(file1_path);
end
output_dir = char(output_dir);
if ~isfolder(output_dir)
    mkdir(output_dir);
end

output_prefix = char(output_prefix);
if isempty(output_prefix)
    output_prefix = 'comparison';
end

hist_txt_path = fullfile(output_dir, sprintf('BFOV_histogram_%s.txt', output_prefix));
bfov_png_path = fullfile(output_dir, sprintf('BFOV_%s.png', output_prefix));
hist_png_path = fullfile(output_dir, sprintf('BFOV_histogram_%s.png', output_prefix));
data_table_path = fullfile(output_dir, sprintf('Bdiff_table_%s.txt', output_prefix));
hist_metrics_path = fullfile(output_dir, sprintf('BFOV_histogram_metrics_%s.txt', output_prefix));

fprintf('Reading file 1: %s\n', file1_path);
data1 = readmatrix(file1_path, 'FileType', 'text', 'CommentStyle', '%');

fprintf('Reading file 2: %s\n', file2_path);
data2 = readmatrix(file2_path, 'FileType', 'text', 'CommentStyle', '%');

if isempty(data1) || isempty(data2)
    error('One of the input files is empty or could not be parsed.');
end

if size(data1, 1) ~= size(data2, 1)
    error(['Incompatible dimensions: different number of rows. ' ...
           'file1 rows=%d, file2 rows=%d'], size(data1, 1), size(data2, 1));
end

required_col1 = max([col_coordinates_file1(:); col_By_file1]);
required_col2 = max([col_coordinates_file2(:); col_By_file2]);

if size(data1, 2) < required_col1
    error('file1 has %d columns, but column %d is required.', size(data1, 2), required_col1);
end
if size(data2, 2) < required_col2
    error('file2 has %d columns, but column %d is required.', size(data2, 2), required_col2);
end

coords1 = data1(:, col_coordinates_file1);
coords2 = data2(:, col_coordinates_file2);

B_file1 = data1(:, col_By_file1);
B_file2 = data2(:, col_By_file2);

if any(~isfinite(B_file1)) || any(~isfinite(B_file2))
    error('Non-finite values detected in selected B-field columns.');
end

% Row-by-row coordinate validation with tolerance.
coord_diff = abs(coords1 - coords2);
mismatch_rows = find(any(coord_diff > coord_tolerance, 2));

if isempty(mismatch_rows)
    fprintf('Coordinate check: all rows match within tolerance %.3e\n', coord_tolerance);
else
    fprintf('WARNING: %d coordinate row(s) differ (tolerance %.3e):\n', numel(mismatch_rows), coord_tolerance);
    for k = 1:numel(mismatch_rows)
        r = mismatch_rows(k);
        fprintf(['  row %d | file1=[%.12g %.12g %.12g] | ' ...
                 'file2=[%.12g %.12g %.12g]\n'], ...
            r, coords1(r,1), coords1(r,2), coords1(r,3), coords2(r,1), coords2(r,2), coords2(r,3));
    end
end

% Field subtraction.
B_diff = B_file1 + B_file2;

% BFOV metrics on the new points.
B_max = max(B_diff);
B_min = min(B_diff);
B_avg = mean(B_diff);
if abs(B_avg) < eps
    ppm_p2p = NaN;
else
    ppm_p2p = (B_max - B_min) / B_avg * 1e6;
end

fprintf('B_diff metrics -> min: %.9g mT | max: %.9g mT | avg: %.9g mT | p2p ppm: %.9g\n', ...
    B_min, B_max, B_avg, ppm_p2p);

% Save pointwise output table [x y z B_diff].
out_table = [coords1(:,1), coords1(:,2), coords1(:,3), B_diff];
writematrix(out_table, data_table_path, 'Delimiter', 'tab');
fprintf('Saved data table: %s\n', data_table_path);

% Generate BFOV PNG from spatial coordinates (project-style scatter plot).
create_bfov_png_from_xyz(coords1, B_diff, bfov_png_path, B_min, B_max, B_avg, ppm_p2p);
fprintf('Saved BFOV PNG: %s\n', bfov_png_path);

% Build BFOV-style histogram text [bin_center, bin_value].
if hist_bins < 1 || ~isfinite(hist_bins)
    hist_bins = 100;
end
hist_bins = floor(hist_bins);

bmin = min(B_diff);
bmax = max(B_diff);
if bmax <= bmin
    delta = max(1e-12, abs(bmin) * 1e-6 + 1e-12);
    bmin = bmin - delta;
    bmax = bmax + delta;
end

edges = linspace(bmin, bmax, hist_bins + 1);
[counts, edges] = histcounts(B_diff, edges);
bin_centers = 0.5 * (edges(1:end-1) + edges(2:end));

hist_out = [bin_centers(:), counts(:)];
writematrix(hist_out, hist_txt_path, 'Delimiter', 'tab');
fprintf('Saved BFOV histogram: %s\n', hist_txt_path);

% Compute histogram metrics equivalent to GUI Python postprocess.
histMetrics = compute_bfov_histogram_metrics(bin_centers(:), counts(:));
write_bfov_histogram_metrics(hist_metrics_path, histMetrics);
print_bfov_histogram_metrics(histMetrics);
fprintf('Saved BFOV histogram metrics: %s\n', hist_metrics_path);

% Generate PNG using the same Python postprocess used by GUI.
python_ok = run_bfov_python_postprocess(hist_txt_path, magnet_info, fov_info, analysis_info, hist_png_path);

if python_ok
    fprintf('Saved BFOV histogram PNG (GUI style): %s\n', hist_png_path);
else
    if require_python_style
        error(['Python BFOV postprocess failed. Exact GUI format is required, so fallback was disabled. ' ...
            'Install/configure Python + numpy + matplotlib and retry.']);
    else
        warning('Python BFOV postprocess failed. Generating fallback MATLAB PNG.');
        create_bfov_histogram_fallback_png(bin_centers(:), counts(:), histMetrics, ...
            hist_png_path, magnet_info, fov_info, analysis_info);
        fprintf('Saved BFOV histogram PNG (fallback): %s\n', hist_png_path);
    end
end

fprintf('Done.\n');


function ok = run_bfov_python_postprocess(txtPath, magnetInfo, fovInfo, analysisName, outputPng)
    ok = false;

    scriptPath = locate_bfov_python_script();
    if ~isfile(scriptPath)
        warning('Python script not found: %s', scriptPath);
        return;
    end

    [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(txtPath, outputPng);
    cleanupObj = onCleanup(@() cleanup_temp_folder(cleanupFolder)); %#ok<NASGU>

    args = [ ...
        ' --file-path '   q(txtPathForPython), ...
        ' --magnet-info ' q(magnetInfo), ...
        ' --fov-info '    q(fovInfo), ...
        ' --analysis '    q(analysisName), ...
        ' --output-png '  q(outputPngForPython), ...
        ' --bfov-only --no-show'];

    pyCandidates = get_python_command_candidates();
    for i = 1:numel(pyCandidates)
        cmd = [pyCandidates{i} ' ' q(scriptPath) args];
        [status, out] = system(cmd);
        if status == 0
            if ~strcmp(outputPngForPython, outputPng)
                [okCopy, copyMsg] = copyfile(outputPngForPython, outputPng, 'f');
                if ~okCopy
                    error('Python generated PNG but copy to final path failed: %s', copyMsg);
                end
            end
            ok = true;
            return;
        end
        fprintf('Python attempt failed (%s): %s\n', pyCandidates{i}, strtrim(out));
    end
end


function [txtPathForPython, outputPngForPython, cleanupFolder] = prepare_python_temp_io(txtPath, outputPng)
    txtPathForPython = txtPath;
    outputPngForPython = outputPng;
    cleanupFolder = '';

    % Always use short temp paths for Python on Windows to avoid MAX_PATH issues.
    if ispc
        cleanupFolder = fullfile(tempdir, ['comsol_bfov_' char(java.util.UUID.randomUUID)]);
        mkdir(cleanupFolder);

        txtPathForPython = fullfile(cleanupFolder, 'BFOV_histogram_input.txt');
        outputPngForPython = fullfile(cleanupFolder, 'BFOV_histogram_output.png');

        [okCopy, copyMsg] = copyfile(txtPath, txtPathForPython, 'f');
        if ~okCopy
            error('Failed to copy histogram TXT to temporary short path: %s', copyMsg);
        end
    end
end


function cleanup_temp_folder(folderPath)
    if isempty(folderPath)
        return;
    end
    if isfolder(folderPath)
        try
            rmdir(folderPath, 's');
        catch
        end
    end
end


function pyCandidates = get_python_command_candidates()
    pyCandidates = {};

    % 1) Prefer Python explicitly configured in MATLAB.
    try
        pe = pyenv;
        if isprop(pe, 'Executable')
            exePath = char(pe.Executable);
            if endsWith(lower(exePath), 'pythonw.exe')
                altExe = [exePath(1:end-11) 'python.exe'];
                if isfile(altExe)
                    exePath = altExe;
                end
            end
            if ~isempty(strtrim(exePath)) && isfile(exePath)
                pyCandidates{end+1} = q(exePath); %#ok<AGROW>
            end
        end
    catch
    end

    % 2) Common shell commands on Windows/Linux.
    defaults = {'python', 'python3', 'py -3', 'py'};
    for i = 1:numel(defaults)
        if ~any(strcmp(pyCandidates, defaults{i}))
            pyCandidates{end+1} = defaults{i}; %#ok<AGROW>
        end
    end
end


function create_bfov_histogram_fallback_png(B_mT, counts, m, outputPng, magnetInfo, fovInfo, analysisInfo)
    if isempty(B_mT) || isempty(counts)
        error('Histogram vectors are empty.');
    end
    if numel(B_mT) ~= numel(counts)
        error('Histogram vectors must have the same length.');
    end

    counts = counts(:);
    B_mT = B_mT(:);
    countsNorm = counts ./ max(counts);

    fig = figure('Visible', 'off', 'Color', [0.92 0.92 0.92], 'Position', [100 100 1000 620]);
    ax = axes(fig, 'Color', [0.92 0.92 0.92]);
    hold(ax, 'on');

    plot(ax, B_mT, countsNorm, 'Color', [0.5 0.5 0.5], 'LineWidth', 1.4);
    xlabel(ax, 'By (mT)');
    ylabel(ax, 'Normalized histogram');

    caseTitle = sprintf('Magnet: %s, FOV: %s, Analysis: %s', magnetInfo, fovInfo, analysisInfo);
    title(ax, sprintf('%s\nBFOV Histogram (Normalized)', caseTitle), ...
        'FontAngle', 'italic', 'Interpreter', 'none', 'FontSize', 16, 'FontWeight', 'normal');

    % Min/Avg/Max vertical lines and labels.
    minAvgMaxVals = [m.B_min_mT, m.B_avg_mT, m.B_max_mT];
    minAvgMaxLabs = {'Min', 'Avg', 'Max'};
    boxEdge = [0.95 0.50 0.50];
    for k = 1:3
        xv = minAvgMaxVals(k);
        xline(ax, xv, ':', 'Color', 'red', 'LineWidth', 1.5);
        txt = sprintf('%s\n%.4f mT\n%+.3f kHz', minAvgMaxLabs{k}, xv, b_to_khz(xv, m.B_peak_mT));
        yPos = 0.78;
        if k == 2
            yPos = 0.74;
        end
        text(ax, xv + 0.0005, yPos, txt, 'Color', 'red', 'FontSize', 11, ...
            'BackgroundColor', 'white', 'EdgeColor', boxEdge, 'Margin', 4);
    end

    % Peak marker and annotation.
    peakIdx = find(B_mT == m.B_peak_mT, 1, 'first');
    if isempty(peakIdx)
        [~, peakIdx] = min(abs(B_mT - m.B_peak_mT));
    end
    peakY = countsNorm(peakIdx);
    plot(ax, m.B_peak_mT, peakY, '.', 'Color', [0.85 0.35 0.85], 'MarkerSize', 18);
    text(ax, m.B_peak_mT + 0.002, min(1.08, peakY + 0.02), ...
        sprintf('Peak %.4f mT (%+.1f kHz)', m.B_peak_mT, b_to_khz(m.B_peak_mT, m.B_peak_mT)), ...
        'Color', [0.85 0.35 0.85], 'FontSize', 11);

    % Percentile vertical lines and labels.
    pVals = [m.P1_mT, m.P5_mT, m.P95_mT, m.P99_mT];
    pLabs = {'P1', 'P5', 'P95', 'P99'};
    pCols = {[0.25 0.40 0.85], [0.00 0.50 0.00], [0.00 0.50 0.00], [0.25 0.40 0.85]};
    for k = 1:numel(pVals)
        xline(ax, pVals(k), '--', 'Color', pCols{k}, 'LineWidth', 1.5);
        pTxt = sprintf('%s) %.3f mT (%+.2f kHz)', pLabs{k}, pVals(k), b_to_khz(pVals(k), m.B_peak_mT));
        text(ax, pVals(k), 0.05, pTxt, 'Rotation', 90, 'HorizontalAlignment', 'center', ...
            'VerticalAlignment', 'bottom', 'FontSize', 10, 'Color', pCols{k}, ...
            'BackgroundColor', 'white', 'Margin', 1);
    end

    % FWHM line and left/right boundaries.
    halfMax = 0.5;
    yline(ax, halfMax, '-.', 'Color', [0.85 0.55 0.90], 'LineWidth', 1.2);
    fwhmMask = countsNorm >= halfMax;
    if any(fwhmMask)
        leftIdx = find(fwhmMask, 1, 'first');
        rightIdx = find(fwhmMask, 1, 'last');
    else
        leftIdx = peakIdx;
        rightIdx = peakIdx;
    end
    bLeft = B_mT(leftIdx);
    bRight = B_mT(rightIdx);
    fwhmCols = [1 0 1];
    xline(ax, bLeft, '-.', 'Color', fwhmCols, 'LineWidth', 1.4);
    xline(ax, bRight, '-.', 'Color', fwhmCols, 'LineWidth', 1.4);
    text(ax, bLeft, 0.05, sprintf('FWHM L) %.3f mT (%+.2f kHz)', bLeft, b_to_khz(bLeft, m.B_peak_mT)), ...
        'Rotation', 90, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontSize', 10, 'Color', fwhmCols, 'BackgroundColor', 'white', 'Margin', 1);
    text(ax, bRight, 0.05, sprintf('FWHM R) %.3f mT (%+.2f kHz)', bRight, b_to_khz(bRight, m.B_peak_mT)), ...
        'Rotation', 90, 'HorizontalAlignment', 'center', 'VerticalAlignment', 'bottom', ...
        'FontSize', 10, 'Color', fwhmCols, 'BackgroundColor', 'white', 'Margin', 1);

    add_top_khz_axis(ax, m.B_peak_mT);
    ylim(ax, [-0.05, 1.11]);
    grid(ax, 'off');

    % Top metrics panel.
    fwhm_mT = bRight - bLeft;
    fwhm_Hz = (b_to_khz(bRight, m.B_peak_mT) - b_to_khz(bLeft, m.B_peak_mT)) * 1e3;
    panelItems = {
        0.08, sprintf('P2P %.1f ppm\n%.1f Hz', (m.B_max_mT - m.B_min_mT) / m.B_avg_mT * 1e6, m.BW_p2p_Hz), [1 0 0]
        0.34, sprintf('1-99%% %.1f ppm\n%.1f Hz', m.ppm_1_99, m.BW_1_99_Hz), [0.25 0.40 0.85]
        0.60, sprintf('5-95%% %.1f ppm\n%.1f Hz', m.ppm_5_95, m.BW_5_95_Hz), [0.00 0.50 0.00]
        0.86, sprintf('FWHM %.1f uT\n%.1f Hz', fwhm_mT * 1e3, fwhm_Hz), [1 0 1]
    };

    rectangle(ax, 'Position', [0.0, 1.13, 1.0, 0.10], 'Units', 'normalized', ...
        'FaceColor', [0.92 0.92 0.92], 'EdgeColor', [0.5 0.5 0.5], 'LineWidth', 1.5, ...
        'Clipping', 'off');
    for k = 1:size(panelItems, 1)
        text(ax, panelItems{k,1}, 1.18, panelItems{k,2}, 'Units', 'normalized', ...
            'HorizontalAlignment', 'center', 'VerticalAlignment', 'center', ...
            'FontSize', 18, 'Color', panelItems{k,3}, 'Clipping', 'off');
    end

    % Date stamp in figure lower-right corner.
    annotation(fig, 'textbox', [0.905, 0.01, 0.09, 0.04], ...
        'String', datestr(now, 'yyyy-mm-dd'), ...
        'EdgeColor', 'none', 'HorizontalAlignment', 'right', ...
        'VerticalAlignment', 'bottom', 'Color', [0.45 0.45 0.45], 'FontSize', 12);

    exportgraphics(fig, outputPng, 'Resolution', 300);
    close(fig);
end


function scriptPath = locate_bfov_python_script()
    scriptName = 'Comsol_extracted_histograms_BFOV_Magnets.py';

    % 1) If the script is on MATLAB path, use that.
    pathCandidate = which(scriptName);
    if ~isempty(pathCandidate) && isfile(pathCandidate)
        scriptPath = pathCandidate;
        return;
    end

    % 2) Try the directory of this m-file as resolved by which().
    thisMFile = which('compare_field_txt_files');
    if ~isempty(thisMFile)
        candidate = fullfile(fileparts(thisMFile), scriptName);
        if isfile(candidate)
            scriptPath = candidate;
            return;
        end
    end

    % 3) Try current working directory.
    candidate = fullfile(pwd, scriptName);
    if isfile(candidate)
        scriptPath = candidate;
        return;
    end

    % 4) If running from MATLAB Editor temp folder, resolve against active file.
    editorFile = get_active_editor_filename_safe();
    if ~isempty(editorFile)
        candidate = fullfile(fileparts(editorFile), scriptName);
        if isfile(candidate)
            scriptPath = candidate;
            return;
        end
    end

    % 5) Try searching in this file directory and up to 3 parent folders.
    roots = {};
    thisDir = fileparts(mfilename('fullpath'));
    if ~isempty(thisDir)
        roots{end+1} = thisDir; %#ok<AGROW>
        p = thisDir;
        for i = 1:3
            p2 = fileparts(p);
            if isempty(p2) || strcmp(p2, p)
                break;
            end
            roots{end+1} = p2; %#ok<AGROW>
            p = p2;
        end
    end
    if ~isempty(editorFile)
        edDir = fileparts(editorFile);
        if ~any(strcmp(roots, edDir))
            roots{end+1} = edDir; %#ok<AGROW>
        end
    end

    for r = 1:numel(roots)
        d = dir(fullfile(roots{r}, '**', scriptName));
        if ~isempty(d)
            scriptPath = fullfile(d(1).folder, d(1).name);
            return;
        end
    end

    % 6) Fallback (for warning message consistency).
    scriptPath = fullfile(fileparts(mfilename('fullpath')), scriptName);
end


function editorFile = get_active_editor_filename_safe()
    editorFile = '';
    try
        editorFile = matlab.desktop.editor.getActiveFilename;
        editorFile = char(editorFile);
        if isempty(editorFile) || ~isfile(editorFile)
            editorFile = '';
            return;
        end
    catch
        editorFile = '';
    end
end


function create_bfov_png_from_xyz(coords, byValues, outputPng, bMin, bMax, bAvg, ppmP2P)
    if size(coords, 2) < 3
        error('coords must have 3 columns [x y z].');
    end
    if numel(byValues) ~= size(coords, 1)
        error('coords and byValues must have the same number of rows.');
    end

    fig = figure('Visible', 'off', 'Color', 'w', 'Position', [100 100 900 700]);
    ax = axes(fig);
    scatter3(ax, coords(:,1), coords(:,2), coords(:,3), 48, byValues, 'filled');
    grid(ax, 'on');
    axis(ax, 'equal');
    view(ax, 3);
    xlabel(ax, 'X [m]');
    ylabel(ax, 'Y [m]');
    zlabel(ax, 'Z [m]');
    title(ax, 'B_FOV (B_{diff})', 'Interpreter', 'none');
    colormap(ax, safe_inferno_colormap(256));
    cb = colorbar(ax);
    cb.Label.String = 'B_{diff} [mT]';

    metricsText = sprintf(['Min: %.6g mT\n' ...
        'Max: %.6g mT\n' ...
        'Avg: %.6g mT\n' ...
        'P2P ppm: %.6g'], bMin, bMax, bAvg, ppmP2P);
    text(ax, 0.02, 0.98, metricsText, ...
        'Units', 'normalized', ...
        'VerticalAlignment', 'top', ...
        'HorizontalAlignment', 'left', ...
        'BackgroundColor', 'white', ...
        'Margin', 6, ...
        'EdgeColor', [0.7 0.7 0.7], ...
        'Interpreter', 'none');

    exportgraphics(fig, outputPng, 'Resolution', 140);
    close(fig);
end


function cmap = safe_inferno_colormap(n)
    if nargin < 1 || isempty(n)
        n = 256;
    end
    n = max(2, floor(double(n)));

    % Use project helper when available.
    try
        cmap = inferno_colormap(n);
        if isnumeric(cmap) && size(cmap, 2) == 3
            return;
        end
    catch
    end

    % Fallback: same anchor-based inferno approximation.
    anchor = [
        0.0015 0.0005 0.0139
        0.1060 0.0470 0.2530
        0.2510 0.0380 0.4040
        0.4160 0.0900 0.4320
        0.5780 0.1660 0.3810
        0.7350 0.2790 0.2730
        0.8650 0.4470 0.1660
        0.9550 0.6550 0.1290
        0.9870 0.8440 0.1890
        0.9880 0.9980 0.6450];

    xAnchor = linspace(0, 1, size(anchor, 1));
    xQuery = linspace(0, 1, n);
    cmap = interp1(xAnchor, anchor, xQuery, 'pchip');
    cmap = max(0, min(1, cmap));
end


function out = q(str)
    if isempty(str)
        out = '""';
        return;
    end
    str = strrep(char(str), '"', '\\"');
    out = ['"' str '"'];
end


function metrics = compute_bfov_histogram_metrics(B_mT, histVals)
    gamma = 42.58e6; % Hz/T

    if isempty(B_mT) || isempty(histVals)
        error('Histogram vectors are empty.');
    end
    if numel(B_mT) ~= numel(histVals)
        error('Histogram vectors must have the same length.');
    end

    B_mT = B_mT(:);
    histVals = histVals(:);

    if all(histVals <= 0)
        error('Histogram values are all zero or negative.');
    end

    idxPeak = find(histVals == max(histVals), 1, 'first');
    B_peak = B_mT(idxPeak);

    validMask = histVals > 0;
    B_real = B_mT(validMask);
    H_real = histVals(validMask);

    B_min = min(B_real);
    B_max = max(B_real);
    B_avg = sum(B_real .* H_real) / sum(H_real);

    P1  = weighted_percentile(B_mT, histVals, 1);
    P5  = weighted_percentile(B_mT, histVals, 5);
    P95 = weighted_percentile(B_mT, histVals, 95);
    P99 = weighted_percentile(B_mT, histVals, 99);

    ppm_1_99 = (P99 - P1) / B_avg * 1e6;
    ppm_5_95 = (P95 - P5) / B_avg * 1e6;

    BW_1_99_Hz = (b_to_khz(P99, B_peak) - b_to_khz(P1, B_peak)) * 1e3;
    BW_5_95_Hz = (b_to_khz(P95, B_peak) - b_to_khz(P5, B_peak)) * 1e3;

    BW_1_99_kHz = BW_1_99_Hz / 1e3;
    BW_5_95_kHz = BW_5_95_Hz / 1e3;

    BW_p2p_Hz = (b_to_khz(B_max, B_peak) - b_to_khz(B_min, B_peak)) * 1e3;
    BW_p2p_kHz = BW_p2p_Hz / 1e3;

    metrics = struct();
    metrics.gamma_Hz_per_T = gamma;
    metrics.B_peak_mT = B_peak;
    metrics.B_min_mT = B_min;
    metrics.B_max_mT = B_max;
    metrics.B_avg_mT = B_avg;
    metrics.P1_mT = P1;
    metrics.P5_mT = P5;
    metrics.P95_mT = P95;
    metrics.P99_mT = P99;
    metrics.ppm_1_99 = ppm_1_99;
    metrics.ppm_5_95 = ppm_5_95;
    metrics.BW_1_99_Hz = BW_1_99_Hz;
    metrics.BW_5_95_Hz = BW_5_95_Hz;
    metrics.BW_1_99_kHz = BW_1_99_kHz;
    metrics.BW_5_95_kHz = BW_5_95_kHz;
    metrics.BW_p2p_Hz = BW_p2p_Hz;
    metrics.BW_p2p_kHz = BW_p2p_kHz;
end


function write_bfov_histogram_metrics(pathOut, m)
    lines = {
        sprintf('B_peak_mT\t%.12g', m.B_peak_mT)
        sprintf('B_min_mT\t%.12g', m.B_min_mT)
        sprintf('B_max_mT\t%.12g', m.B_max_mT)
        sprintf('B_avg_mT\t%.12g', m.B_avg_mT)
        sprintf('P1_mT\t%.12g', m.P1_mT)
        sprintf('P5_mT\t%.12g', m.P5_mT)
        sprintf('P95_mT\t%.12g', m.P95_mT)
        sprintf('P99_mT\t%.12g', m.P99_mT)
        sprintf('ppm_1_99\t%.12g', m.ppm_1_99)
        sprintf('ppm_5_95\t%.12g', m.ppm_5_95)
        sprintf('BW_1_99_Hz\t%.12g', m.BW_1_99_Hz)
        sprintf('BW_5_95_Hz\t%.12g', m.BW_5_95_Hz)
        sprintf('BW_1_99_kHz\t%.12g', m.BW_1_99_kHz)
        sprintf('BW_5_95_kHz\t%.12g', m.BW_5_95_kHz)
        sprintf('BW_p2p_Hz\t%.12g', m.BW_p2p_Hz)
        sprintf('BW_p2p_kHz\t%.12g', m.BW_p2p_kHz)
    };

    fid = fopen(pathOut, 'w');
    if fid < 0
        error('Could not open metrics file for writing: %s', pathOut);
    end
    cleanupObj = onCleanup(@() fclose(fid)); %#ok<NASGU>
    for i = 1:numel(lines)
        fprintf(fid, '%s\n', lines{i});
    end
end


function print_bfov_histogram_metrics(m)
    fprintf('Histogram metrics -> Peak: %.9g mT\n', m.B_peak_mT);
    fprintf('  P1=%.9g | P99=%.9g | ppm(1-99)=%.9g | BW(1-99)=%.9g Hz (%.9g kHz)\n', ...
        m.P1_mT, m.P99_mT, m.ppm_1_99, m.BW_1_99_Hz, m.BW_1_99_kHz);
    fprintf('  P5=%.9g | P95=%.9g | ppm(5-95)=%.9g | BW(5-95)=%.9g Hz (%.9g kHz)\n', ...
        m.P5_mT, m.P95_mT, m.ppm_5_95, m.BW_5_95_Hz, m.BW_5_95_kHz);
end


function p = weighted_percentile(values, weights, percentile)
    values = values(:);
    weights = weights(:);
    if numel(values) ~= numel(weights)
        error('values and weights must have same length');
    end

    [v, idx] = sort(values, 'ascend');
    w = weights(idx);

    w = max(w, 0);
    if all(w == 0)
        error('All weights are zero.');
    end

    % Remove zero-weight samples so cumulative probabilities are strictly increasing.
    keep = w > 0;
    v = v(keep);
    w = w(keep);

    if isempty(v)
        error('All weights are zero after filtering.');
    end

    c = cumsum(w) ./ sum(w);

    % Collapse any residual duplicate cumulative values for interp1 safety.
    [cUnique, uniqueIdx] = unique(c, 'stable');
    vUnique = v(uniqueIdx);

    q = max(0, min(1, percentile / 100));
    if q <= cUnique(1)
        p = vUnique(1);
        return;
    end
    if q >= cUnique(end)
        p = vUnique(end);
        return;
    end

    p = interp1(cUnique, vUnique, q, 'linear');
end


function kHz = b_to_khz(B_mT, B_peak_mT)
    gamma = 42.58e6; % Hz/T
    kHz = ((B_mT - B_peak_mT) * 1e-3 * gamma) / 1e3;
end


function B_mT = khz_to_b(kHz, B_peak_mT)
    gamma = 42.58e6; % Hz/T
    B_mT = ((kHz * 1e3 / gamma) + (B_peak_mT * 1e-3)) * 1e3;
end


function add_top_khz_axis(ax, B_peak_mT)
    % Prefer modern API when available.
    try
        secax = ax.secondary_xaxis('top', ...
            'functions', {@(B) b_to_khz(B, B_peak_mT), ...
                          @(k) khz_to_b(k, B_peak_mT)});
        secax.Label.String = 'Bandwidth (kHz)';
        return;
    catch
    end

    % Compatibility fallback for older MATLAB: create an overlaid top axis.
    fig = ancestor(ax, 'figure');
    axTop = axes(fig, 'Position', ax.Position, ...
        'Color', 'none', ...
        'XAxisLocation', 'top', ...
        'YAxisLocation', 'right', ...
        'YTick', [], ...
        'YColor', 'none', ...
        'Box', 'off', ...
        'HitTest', 'off', ...
        'HandleVisibility', 'off');

    % Map bottom ticks (mT) to top ticks (kHz).
    bottomTicks = ax.XTick;
    axTop.XLim = b_to_khz(ax.XLim, B_peak_mT);
    axTop.XTick = b_to_khz(bottomTicks, B_peak_mT);
    axTop.XLabel.String = 'Bandwidth (kHz)';

    % Keep plotting focus on main axis.
    axes(ax); %#ok<LAXES>
end
