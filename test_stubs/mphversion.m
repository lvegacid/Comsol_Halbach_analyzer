function v = mphversion()
% mphversion  Stub for COMSOL LiveLink mphversion function.
% Behavior is controlled by global STUB_MPHVERSION_MODE:
%   'success'        -> returns '6.2' (default)
%   'disconnect'     -> throws "not connected to a server"
%   'transient'      -> throws "java.net.SocketException: Software caused connection abort"
%   'counter'        -> uses STUB_MPHVERSION_CALL_COUNT and STUB_MPHVERSION_FAIL_ON_CALL
%                       to fail on a specific call number

global STUB_MPHVERSION_MODE STUB_MPHVERSION_CALL_COUNT STUB_MPHVERSION_FAIL_ON_CALL;

if isempty(STUB_MPHVERSION_CALL_COUNT)
    STUB_MPHVERSION_CALL_COUNT = 0;
end
STUB_MPHVERSION_CALL_COUNT = STUB_MPHVERSION_CALL_COUNT + 1;

if isempty(STUB_MPHVERSION_MODE)
    STUB_MPHVERSION_MODE = 'success';
end

mode = STUB_MPHVERSION_MODE;

% Counter mode: fail on specific call number
if strcmp(mode, 'counter')
    if ~isempty(STUB_MPHVERSION_FAIL_ON_CALL) && STUB_MPHVERSION_CALL_COUNT >= STUB_MPHVERSION_FAIL_ON_CALL
        error('ComsolStub:NotConnected', 'not connected to a server');
    end
    v = '6.2-stub';
    return;
end

switch mode
    case 'success'
        v = '6.2-stub';
    case 'disconnect'
        error('ComsolStub:NotConnected', 'not connected to a server');
    case 'always_disconnect'
        error('ComsolStub:NotConnected', 'not connected to a server');
    case 'transient'
        error('ComsolStub:Transient', 'java.net.SocketException: Software caused connection abort');
    otherwise
        v = '6.2-stub';
end
end
