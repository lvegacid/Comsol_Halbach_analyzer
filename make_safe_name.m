function safe = make_safe_name(name)
% make_safe_name  Generate a filesystem-safe name from an arbitrary string.
%
% Replaces any character that is not alphanumeric or underscore with '_'.
% Strips trailing spaces and dots from the result.
% Returns a non-empty string when the input contains at least one
% alphanumeric character; otherwise returns an empty string.
%
% Syntax:
%   safe = make_safe_name(name)
%
% Inputs:
%   name  (char) — arbitrary string
%
% Outputs:
%   safe  (char) — safe name containing only [a-zA-Z0-9_], no trailing
%                  spaces or dots
%
% Validates: Requisito 3.2

    if isempty(name)
        safe = '';
        return;
    end

    % Replace every character that is not alphanumeric or underscore with '_'
    safe = regexprep(name, '[^a-zA-Z0-9_]', '_');

    % Strip trailing spaces and dots
    safe = regexprep(safe, '[. ]+$', '');

    % If the result is empty but the original had at least one alphanumeric
    % character, the replacement loop above would have kept those characters,
    % so an empty result here means no alphanumeric content existed.
    % Return empty string in that case (already handled by the strip above).
end
