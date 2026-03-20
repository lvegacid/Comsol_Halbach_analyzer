% Descubre todos los datasets disponibles en el modelo.
%
% Salidas:
%   datasets (struct array) con campos:
%     .tag        (char) — tag interno COMSOL, e.g. 'dset1'
%     .label      (char) — label completo, e.g. 'Linear/Solution 1 (1)'
%     .shortLabel (char) — parte antes del '/', e.g. 'Linear'
%
% Lanza:
%   MException con identifier 'ComsolAnalyzer:getDatasets' si falla
function datasets = get_datasets(model)
    try
        tags = model.result().dataset().tags();
        nTags = numel(tags);
        datasets = struct('tag', {}, 'label', {}, 'shortLabel', {});

        for i = 1:nTags
            tag       = char(tags(i));
            fullLabel = char(model.result().dataset(tag).label());

            % shortLabel: only the part before the first '/'
            slashIdx = strfind(fullLabel, '/');
            if ~isempty(slashIdx)
                shortLabel = strtrim(fullLabel(1:slashIdx(1)-1));
            else
                shortLabel = strtrim(fullLabel);
            end

            datasets(end+1).tag        = tag;        %#ok<AGROW>
            datasets(end).label        = fullLabel;
            datasets(end).shortLabel   = shortLabel;
        end
    catch err
        throw(MException('ComsolAnalyzer:getDatasets', ...
            'Failed to retrieve datasets: %s', err.message));
    end
end
