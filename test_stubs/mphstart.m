function mphstart(varargin)
% mphstart  Stub for COMSOL LiveLink mphstart function.
% Behavior is controlled by global STUB_MPHSTART_MODE:
%   'success'  -> silently succeeds (default)
%   'fail'     -> throws an error

global STUB_MPHSTART_MODE STUB_MPHSTART_CALL_COUNT;

if isempty(STUB_MPHSTART_CALL_COUNT)
    STUB_MPHSTART_CALL_COUNT = 0;
end
STUB_MPHSTART_CALL_COUNT = STUB_MPHSTART_CALL_COUNT + 1;

if isempty(STUB_MPHSTART_MODE)
    STUB_MPHSTART_MODE = 'success';
end

switch STUB_MPHSTART_MODE
    case 'success'
        % Silently succeed - do nothing
    case 'fail'
        error('ComsolStub:MphstartFail', 'mphstart: connection refused');
    otherwise
        % default: succeed
end
end
