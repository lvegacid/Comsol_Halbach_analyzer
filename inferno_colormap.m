function cmap = inferno_colormap(n)
% inferno_colormap  Approximate inferno colormap for MATLAB versions
% without built-in inferno support.

    if nargin < 1 || isempty(n)
        n = 256;
    end

    n = max(2, floor(double(n)));

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