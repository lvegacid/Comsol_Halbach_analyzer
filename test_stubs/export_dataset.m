function export_dataset(model, datasetTag, histTxtPath, plot3dPngPath, varargin)
% export_dataset  Stub for export_dataset function.
% Behavior is controlled by globals:
%   STUB_EXPORT_DATASET_CALL_COUNT   - incremented each call
%   STUB_EXPORT_DATASET_FAIL_ON_CALL - call number on which to throw disconnect error

global STUB_EXPORT_DATASET_CALL_COUNT STUB_EXPORT_DATASET_FAIL_ON_CALL;

if isempty(STUB_EXPORT_DATASET_CALL_COUNT)
    STUB_EXPORT_DATASET_CALL_COUNT = 0;
end
STUB_EXPORT_DATASET_CALL_COUNT = STUB_EXPORT_DATASET_CALL_COUNT + 1;

if ~isempty(STUB_EXPORT_DATASET_FAIL_ON_CALL) && ...
        STUB_EXPORT_DATASET_CALL_COUNT == STUB_EXPORT_DATASET_FAIL_ON_CALL
    error('ComsolStub:NotConnected', 'not connected to a server');
end

% Otherwise succeed silently
end
