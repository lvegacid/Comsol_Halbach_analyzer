function results = test_preservation()
% test_preservation  Preservation property tests for COMSOL LiveLink Linux stability bugfix
%
% ALL tests MUST PASS on unfixed code (document behavioral baseline).
% ALL tests MUST STILL PASS on fixed code (confirm no regressions).
%
% Strategy: observation-first — run the UNFIXED code with non-buggy inputs
% and record actual outputs. Tests assert the ACTUAL current behavior.
%
% Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
%
% Usage:
%   results = test_preservation()

    fprintf('=== Preservation Property Tests ===\n');
    fprintf('Spec: comsol-livelink-linux-stability\n');
    fprintf('ALL tests MUST PASS on unfixed AND fixed code.\n\n');

    results = struct();
    results.P6 = test_property6_windows_preservation();
    results.P7 = test_property7_struct_schema();
    results.R31 = test_req31_already_connected_linux();
    results.R34 = test_req34_no_livelink_path();
    results.probe_disconnect = test_probe_disconnect_behavior();
    results.probe_success = test_probe_success_behavior();

    print_summary(results);
end

% =========================================================================
% Property 6: Windows Behavior Preservation
% =========================================================================
function result = test_property6_windows_preservation()
% On the current Windows test environment, verify comsol_livelink_connection
% behaves correctly for the Windows platform:
%   - canAutoConnect = false  (Windows cannot auto-launch the server)
%   - connect_on_linux is never invoked  (source-code analysis)
%
% This test uses BOTH source-code analysis (for the platform-guard logic)
% AND stub-based execution (connected + disconnected states on Windows).
%
% Validates: Requirements 3.2, 3.3  (Property 6)

    result = struct('name', 'P6', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Property 6: Windows behavior preservation ---\n');

    % ---- Part 1: Source-code analysis ----
    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'comsol_livelink_connection.m');
    if ~isfile(sourceFile)
        result.message = 'SKIP: comsol_livelink_connection.m not found';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    src = fileread(sourceFile);

    % Verify connect_on_linux is guarded by a Linux platform check
    connectOnLinuxCallPattern = 'connect_on_linux';
    linuxGuardPattern = 'strcmp(status.platform, ''linux'')';

    callIdx = strfind(src, connectOnLinuxCallPattern);
    guardIdx = strfind(src, linuxGuardPattern);

    if isempty(callIdx)
        result.counterexample = 'connect_on_linux not found in source — unexpected';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if isempty(guardIdx)
        result.counterexample = ['No strcmp(status.platform, ''linux'') guard found. ' ...
            'connect_on_linux might be called on Windows.'];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    % Verify: the connect_on_linux CALL comes AFTER the linux guard (i.e., inside the if block)
    % Find call sites of connect_on_linux that are not the function definition itself
    callSitePattern = '\[connected.*\]\s*=\s*connect_on_linux\(\)';
    [callSiteMatches] = regexp(src, callSitePattern, 'match');

    if isempty(callSiteMatches)
        % Try simpler pattern for the call site
        callSiteSimple = '= connect_on_linux()';
        callSiteIdx = strfind(src, callSiteSimple);
        if isempty(callSiteIdx)
            result.counterexample = 'Could not locate connect_on_linux() call site';
            result.message = ['SKIP: ' result.counterexample];
            fprintf('  SKIP: %s\n\n', result.message);
            return;
        end
        callSitePos = callSiteIdx(1);
    else
        callSitePos = strfind(src, callSiteMatches{1});
        callSitePos = callSitePos(1);
    end

    % The guard must appear before the call site
    guardsBeforeCall = guardIdx(guardIdx < callSitePos);
    if isempty(guardsBeforeCall)
        result.counterexample = ['The linux platform guard appears AFTER the connect_on_linux() ' ...
            'call site — Windows path may reach connect_on_linux.'];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end
    fprintf('  Source analysis: connect_on_linux() is guarded by strcmp(status.platform, ''linux'') — OK.\n');

    % ---- Part 2: Stub-based execution (connected state on Windows) ----
    % We are on Windows; stubs are added to path so has_livelink_functions() = true
    stubDir = fullfile(fileparts(mfilename('fullpath')), 'test_stubs');
    addpath(stubDir);
    cleanupObj = onCleanup(@() rmpath(stubDir));

    % Reset globals
    global STUB_MPHVERSION_MODE STUB_MPHVERSION_CALL_COUNT;
    STUB_MPHVERSION_MODE = 'success';
    STUB_MPHVERSION_CALL_COUNT = 0;

    try
        statusConnected = comsol_livelink_connection('status');
    catch ex
        result.counterexample = ['comsol_livelink_connection(''status'') threw: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    % On Windows: canAutoConnect must be false
    if statusConnected.canAutoConnect ~= false
        result.counterexample = sprintf('canAutoConnect = %d on Windows (expected false)', ...
            statusConnected.canAutoConnect);
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    % Platform must be 'windows'
    if ~strcmp(statusConnected.platform, 'windows')
        result.counterexample = sprintf('platform = ''%s'' (expected ''windows'')', ...
            statusConnected.platform);
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    % connected must be true (stub returns '6.2-stub')
    if ~statusConnected.connected
        result.counterexample = 'connected = false when mphversion stub returns success';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Stub exec (connected): platform=windows, canAutoConnect=false, connected=true — OK.\n');

    % -- Disconnected state on Windows --
    STUB_MPHVERSION_MODE = 'disconnect';
    STUB_MPHVERSION_CALL_COUNT = 0;

    try
        statusDisc = comsol_livelink_connection('status');
    catch ex
        result.counterexample = ['comsol_livelink_connection(''status'') threw on disconnect: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if statusDisc.canAutoConnect ~= false
        result.counterexample = sprintf('canAutoConnect = %d on Windows disconnected (expected false)', ...
            statusDisc.canAutoConnect);
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if statusDisc.connected ~= false
        result.counterexample = 'connected = true when mphversion stub throws disconnect';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Stub exec (disconnected): platform=windows, canAutoConnect=false, connected=false — OK.\n');

    % -- connect action on Windows: must NOT call connect_on_linux --
    % Since platform=windows, the 'connect' action should NOT trigger connect_on_linux.
    % We verify no server start was attempted.
    STUB_MPHVERSION_MODE = 'disconnect';
    STUB_MPHVERSION_CALL_COUNT = 0;
    global STUB_MPHSTART_CALL_COUNT;
    STUB_MPHSTART_CALL_COUNT = 0;
    global STUB_MPHSTART_MODE;
    STUB_MPHSTART_MODE = 'success';

    try
        statusConnect = comsol_livelink_connection('connect');
    catch ex
        result.counterexample = ['comsol_livelink_connection(''connect'') threw on Windows: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if statusConnect.serverStartAttempted ~= false
        result.counterexample = 'serverStartAttempted = true on Windows connect (expected false)';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Stub exec (connect on Windows): serverStartAttempted=false — connect_on_linux NOT called.\n');

    result.passed = true;
    result.message = ['PASS: Windows platform guard confirmed by source analysis and stub execution. ' ...
        'canAutoConnect=false, connect_on_linux never reached.'];
    fprintf('  PASS: Windows behavior preserved.\n\n');
end

% =========================================================================
% Property 7: Status Struct Schema
% =========================================================================
function result = test_property7_struct_schema()
% Verify that comsol_livelink_connection returns a struct containing AT MINIMUM
% the 8 required fields from the spec.
%
% NOTE: The actual source code initializes 10 fields (the 8 required ones plus
% 'serverPort' and 'serverLog'). This test asserts the 8 REQUIRED fields are
% present and does NOT fail if extra fields exist — so it passes on BOTH the
% current (10-field) code and any future version that keeps the required schema.
%
% Actual field schema documented from current code:
%   Required 8: connected, platform, hasLiveLink, canAutoConnect,
%               message, detail, version, serverStartAttempted
%   Extra (current code): serverPort, serverLog
%
% Validates: Requirement 3.3  (Property 7)

    result = struct('name', 'P7', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Property 7: Status struct schema ---\n');

    REQUIRED_FIELDS = {'connected', 'platform', 'hasLiveLink', 'canAutoConnect', ...
                       'message', 'detail', 'version', 'serverStartAttempted'};

    stubDir = fullfile(fileparts(mfilename('fullpath')), 'test_stubs');
    addpath(stubDir);
    cleanupObj = onCleanup(@() rmpath(stubDir));

    % Test cases: action x mode combinations
    testCases = {
        'status',  'success',    'status+connected';
        'status',  'disconnect', 'status+disconnected';
        'connect', 'success',    'connect+connected';
        'connect', 'disconnect', 'connect+disconnected';
        '',        'success',    'empty-action+connected';
    };

    global STUB_MPHVERSION_MODE STUB_MPHVERSION_CALL_COUNT;

    for tc = 1:size(testCases, 1)
        action = testCases{tc, 1};
        mode   = testCases{tc, 2};
        label  = testCases{tc, 3};

        STUB_MPHVERSION_MODE = mode;
        STUB_MPHVERSION_CALL_COUNT = 0;

        try
            if isempty(action)
                s = comsol_livelink_connection();
            else
                s = comsol_livelink_connection(action);
            end
        catch ex
            result.counterexample = sprintf('Case "%s": threw exception: %s', label, ex.message);
            result.message = ['FAIL: ' result.counterexample];
            fprintf('  FAIL case "%s": %s\n\n', label, ex.message);
            return;
        end

        % Check all required fields are present
        actualFields = fieldnames(s);
        missingFields = {};
        for k = 1:numel(REQUIRED_FIELDS)
            if ~ismember(REQUIRED_FIELDS{k}, actualFields)
                missingFields{end+1} = REQUIRED_FIELDS{k}; %#ok<AGROW>
            end
        end

        if ~isempty(missingFields)
            result.counterexample = sprintf('Case "%s": missing required fields: %s. Actual fields: %s', ...
                label, strjoin(missingFields, ', '), strjoin(actualFields, ', '));
            result.message = ['FAIL: ' result.counterexample];
            fprintf('  FAIL case "%s": missing fields: %s\n\n', label, strjoin(missingFields, ', '));
            return;
        end

        fprintf('  Case "%-30s": fields OK (%d total, %d required). Fields: %s\n', ...
            label, numel(actualFields), numel(REQUIRED_FIELDS), strjoin(actualFields, ', '));
    end

    % Document the actual field count from current code
    STUB_MPHVERSION_MODE = 'success';
    STUB_MPHVERSION_CALL_COUNT = 0;
    s = comsol_livelink_connection('status');
    actualFields = fieldnames(s);
    fprintf('\n  Actual struct schema (current code): %d fields: %s\n', ...
        numel(actualFields), strjoin(actualFields, ', '));
    fprintf('  Required by spec: 8 fields (%s)\n', strjoin(REQUIRED_FIELDS, ', '));

    if numel(actualFields) > numel(REQUIRED_FIELDS)
        extraFields = setdiff(actualFields, REQUIRED_FIELDS);
        fprintf('  Extra fields in current code (not in spec): %s\n', strjoin(extraFields, ', '));
        fprintf('  NOTE: Test asserts minimum required fields only — extra fields are acceptable.\n');
    end

    result.passed = true;
    result.message = sprintf(['PASS: All %d required struct fields present in all test cases. ' ...
        'Actual code has %d fields (extra: serverPort, serverLog).'], ...
        numel(REQUIRED_FIELDS), numel(actualFields));
    fprintf('\n  PASS: Struct schema preserved (>= 8 required fields).\n\n');
end

% =========================================================================
% Requirement 3.1: Already-connected Linux path
% =========================================================================
function result = test_req31_already_connected_linux()
% Verify that when mphversion succeeds (connection already established),
% comsol_livelink_connection('connect') returns connected=true and
% serverStartAttempted=false — no server launch is attempted.
%
% Since we are running on Windows, the actual 'connect' action won't call
% connect_on_linux(). We verify the behavior via:
%   1. Stub-based execution on Windows (mphversion succeeds → no start attempted)
%   2. Source-code analysis: connect_on_linux() checks connection first via
%      try_mphstart_retries(1, 0.0) and returns early if already connected.
%
% Validates: Requirement 3.1

    result = struct('name', 'R31', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Requirement 3.1: Already-connected path (no server launch) ---\n');

    % ---- Part 1: Stub-based execution ----
    stubDir = fullfile(fileparts(mfilename('fullpath')), 'test_stubs');
    addpath(stubDir);
    cleanupObj = onCleanup(@() rmpath(stubDir));

    global STUB_MPHVERSION_MODE STUB_MPHVERSION_CALL_COUNT;
    global STUB_MPHSTART_MODE STUB_MPHSTART_CALL_COUNT;

    STUB_MPHVERSION_MODE = 'success';
    STUB_MPHVERSION_CALL_COUNT = 0;
    STUB_MPHSTART_MODE = 'success';
    STUB_MPHSTART_CALL_COUNT = 0;

    try
        s = comsol_livelink_connection('connect');
    catch ex
        result.counterexample = ['comsol_livelink_connection(''connect'') threw: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    % Assert connected = true
    if ~s.connected
        result.counterexample = 'connected = false when mphversion stub succeeds';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    % Assert serverStartAttempted = false
    if s.serverStartAttempted ~= false
        result.counterexample = sprintf('serverStartAttempted = %d (expected false when already connected)', ...
            s.serverStartAttempted);
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Stub exec: connected=true, serverStartAttempted=false — OK.\n');

    % ---- Part 2: Source-code analysis of connect_on_linux ----
    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'comsol_livelink_connection.m');
    src = fileread(sourceFile);

    % Locate connect_on_linux function
    connectFnToken = 'function [connected, detail, versionText, startAttempted] = connect_on_linux';
    connectIdx = strfind(src, connectFnToken);

    if isempty(connectIdx)
        result.message = 'SKIP: Could not locate connect_on_linux in source';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    connectBody = src(connectIdx(1) : min(connectIdx(1)+2000, length(src)));

    % Verify: try_mphstart_retries(1, 0.0) is called first (fast pre-check)
    fastProbePattern = 'try_mphstart_retries\(1,\s*0\.0';
    hasFastProbe = ~isempty(regexp(connectBody, fastProbePattern, 'once'));

    % Verify: early return if connected (before startAttempted = true)
    % Pattern: [connected, ...] = try_mphstart_retries(1, 0.0 ...) followed by "if connected" then "return"
    earlyReturnPattern = 'if connected\s*\n\s*return';
    hasEarlyReturn = ~isempty(regexp(connectBody, earlyReturnPattern, 'once'));

    if ~hasFastProbe
        result.counterexample = 'connect_on_linux does NOT have try_mphstart_retries(1, 0.0) fast pre-probe';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Source analysis: try_mphstart_retries(1, 0.0) fast pre-probe found.\n');

    if hasEarlyReturn
        fprintf('  Source analysis: early return-if-connected found — already-connected returns immediately.\n');
    else
        % Try simpler pattern
        simpleEarlyReturn = 'if connected';
        hasSimple = contains(connectBody, simpleEarlyReturn);
        if hasSimple
            fprintf('  Source analysis: "if connected" guard found in connect_on_linux body — OK.\n');
        else
            result.counterexample = 'No early return for already-connected in connect_on_linux';
            result.message = ['FAIL: ' result.counterexample];
            fprintf('  FAIL: %s\n\n', result.counterexample);
            return;
        end
    end

    result.passed = true;
    result.message = ['PASS: Already-connected path returns connected=true, serverStartAttempted=false. ' ...
        'Source analysis confirms fast pre-probe and early return in connect_on_linux.'];
    fprintf('  PASS: Already-connected path preserved.\n\n');
end

% =========================================================================
% Requirement 3.4: No-LiveLink path
% =========================================================================
function result = test_req34_no_livelink_path()
% Verify that when LiveLink functions are absent from the MATLAB path,
% comsol_livelink_connection returns hasLiveLink=false without exception.
%
% Strategy: source-code analysis of has_livelink_functions() to confirm it
% uses exist() checks, plus verification that the main function returns early
% when hasLiveLink is false.
%
% Additionally: call comsol_livelink_connection WITHOUT adding stubs to path,
% so mphload/mphstart/mphversion are absent. Verify hasLiveLink=false.
%
% Validates: Requirement 3.4

    result = struct('name', 'R34', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Requirement 3.4: No-LiveLink path (hasLiveLink=false) ---\n');

    % ---- Part 1: Source-code analysis of has_livelink_functions ----
    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'comsol_livelink_connection.m');
    src = fileread(sourceFile);

    hasLiveLinkFnToken = 'function tf = has_livelink_functions';
    fnIdx = strfind(src, hasLiveLinkFnToken);

    if isempty(fnIdx)
        result.message = 'SKIP: has_livelink_functions not found in source';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    fnBody = src(fnIdx(1) : min(fnIdx(1)+400, length(src)));

    % Verify uses exist() check
    if ~contains(fnBody, "exist('mphload'") && ~contains(fnBody, 'exist(''mphload''')
        result.counterexample = 'has_livelink_functions does not use exist(''mphload'', ...) check';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Source analysis: has_livelink_functions uses exist() checks — OK.\n');

    % Verify main function returns early when hasLiveLink = false
    % Look for: if ~status.hasLiveLink ... return
    noLiveLinkGuardPattern = 'if ~status\.hasLiveLink';
    hasEarlyReturn = ~isempty(regexp(src, noLiveLinkGuardPattern, 'once'));

    if ~hasEarlyReturn
        % Try alternate pattern
        altPattern = '~status.hasLiveLink';
        hasEarlyReturn = contains(src, altPattern);
    end

    if ~hasEarlyReturn
        result.counterexample = 'No ~status.hasLiveLink early-return guard in main function';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  Source analysis: ~status.hasLiveLink early-return guard found — OK.\n');

    % ---- Part 2: Functional test — stubs NOT on path ----
    % Make sure stubs are NOT currently on the MATLAB path for this test
    stubDir = fullfile(fileparts(mfilename('fullpath')), 'test_stubs');

    % Check if stubs are already on path (from a previous test via onCleanup)
    % We explicitly remove them for this test
    wasOnPath = ~isempty(strfind(path, stubDir)); %#ok<STREMP>
    if wasOnPath
        rmpath(stubDir);
    end

    noStubCleanup = onCleanup(@() conditionally_addpath(stubDir, wasOnPath));

    % Now stubs are NOT on path — has_livelink_functions() should return false
    % (assuming no real COMSOL is installed)
    try
        s = comsol_livelink_connection('status');
    catch ex
        result.counterexample = ['comsol_livelink_connection threw when stubs absent: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: Exception thrown (should not throw): %s\n\n', ex.message);
        return;
    end

    % When stubs are absent and no real COMSOL, hasLiveLink must be false
    if s.hasLiveLink
        % Real COMSOL might be installed — this is acceptable; skip functional check
        fprintf('  NOTE: hasLiveLink=true without stubs (real COMSOL may be installed). Skipping functional check.\n');
        fprintf('  Source analysis confirms correct no-LiveLink handling.\n');
    else
        fprintf('  Functional test (stubs absent): hasLiveLink=false — no exception thrown.\n');

        % Verify connected = false as well
        if s.connected
            result.counterexample = 'connected=true when hasLiveLink=false';
            result.message = ['FAIL: ' result.counterexample];
            fprintf('  FAIL: %s\n\n', result.counterexample);
            return;
        end
        fprintf('  Functional test: connected=false — correct.\n');
    end

    result.passed = true;
    result.message = ['PASS: No-LiveLink path returns hasLiveLink=false without exception. ' ...
        'Source analysis confirms exist() checks and early return.'];
    fprintf('  PASS: No-LiveLink path preserved.\n\n');
end

% Helper: conditionally re-add path
function conditionally_addpath(p, wasOnPath)
    if wasOnPath
        addpath(p);
    end
end

% =========================================================================
% Non-disconnect error paths: probe_connection with 'disconnect' stub
% =========================================================================
function result = test_probe_disconnect_behavior()
% Verify: when mphversion stub throws a confirmed disconnect error,
% comsol_livelink_connection('status') returns connected=false.
%
% This documents the EXPECTED behavior for disconnect detection.
% PASSES on unfixed code.
%
% Validates: Requirements 3.1, 3.5

    result = struct('name', 'probe_disconnect', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- probe_connection: disconnect error → connected=false ---\n');

    stubDir = fullfile(fileparts(mfilename('fullpath')), 'test_stubs');
    addpath(stubDir);
    cleanupObj = onCleanup(@() rmpath(stubDir));

    global STUB_MPHVERSION_MODE STUB_MPHVERSION_CALL_COUNT;
    STUB_MPHVERSION_MODE = 'disconnect';
    STUB_MPHVERSION_CALL_COUNT = 0;

    try
        s = comsol_livelink_connection('status');
    catch ex
        result.counterexample = ['comsol_livelink_connection threw on disconnect mode: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if s.connected ~= false
        result.counterexample = sprintf(['connected = %d when mphversion throws "not connected to a server". ' ...
            'Expected false.'], s.connected);
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  mphversion(disconnect) → connected=false, detail="%s" — OK.\n', s.detail);

    result.passed = true;
    result.message = 'PASS: Confirmed disconnect error → connected=false (correct disconnect detection).';
    fprintf('  PASS: Disconnect detection preserved.\n\n');
end


% =========================================================================
% Non-disconnect error paths: probe_connection with 'success' stub
% =========================================================================
function result = test_probe_success_behavior()
% Verify: when mphversion stub returns a version string,
% comsol_livelink_connection('status') returns connected=true with version set.
%
% This documents the baseline successful-connection behavior.
% PASSES on unfixed code.
%
% Validates: Requirements 3.1, 3.5

    result = struct('name', 'probe_success', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- probe_connection: success → connected=true ---\n');

    stubDir = fullfile(fileparts(mfilename('fullpath')), 'test_stubs');
    addpath(stubDir);
    cleanupObj = onCleanup(@() rmpath(stubDir));

    global STUB_MPHVERSION_MODE STUB_MPHVERSION_CALL_COUNT;
    STUB_MPHVERSION_MODE = 'success';
    STUB_MPHVERSION_CALL_COUNT = 0;

    try
        s = comsol_livelink_connection('status');
    catch ex
        result.counterexample = ['comsol_livelink_connection threw on success mode: ' ex.message];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if ~s.connected
        result.counterexample = sprintf('connected=false when mphversion stub succeeds. detail="%s"', s.detail);
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    if isempty(s.version)
        result.counterexample = 'version field is empty when mphversion stub returns ''6.2-stub''';
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
        return;
    end

    fprintf('  mphversion(success) → connected=true, version="%s" — OK.\n', s.version);

    result.passed = true;
    result.message = sprintf('PASS: Successful connection → connected=true, version="%s".', s.version);
    fprintf('  PASS: Success path behavior preserved.\n\n');
end

% =========================================================================
% Summary printer
% =========================================================================
function print_summary(results)
    fprintf('\n=== Preservation Test Summary ===\n');
    fprintf('%-18s %-8s %s\n', 'Test', 'Result', 'Notes');
    fprintf('%s\n', repmat('-', 1, 90));

    fields = fieldnames(results);
    allPassed = true;
    nPass = 0;
    nFail = 0;

    for k = 1:numel(fields)
        r = results.(fields{k});
        if r.passed
            status = 'PASS';
            nPass = nPass + 1;
        else
            status = 'FAIL';
            allPassed = false;
            nFail = nFail + 1;
        end
        % Truncate message for display
        msg = r.message;
        if numel(msg) > 80
            msg = [msg(1:77) '...'];
        end
        fprintf('  %-16s %-8s %s\n', r.name, status, msg);
    end

    fprintf('%s\n', repmat('-', 1, 90));
    fprintf('\nResults: %d PASS, %d FAIL\n', nPass, nFail);

    fprintf('\nExpected results on UNFIXED code: ALL PASS (baseline documentation)\n');
    fprintf('Expected results on FIXED code:   ALL PASS (regression prevention)\n');

    fprintf('\nProperty summary:\n');
    fprintf('  P6  (Property 6)  Windows behavior preservation — canAutoConnect=false, no auto-launch\n');
    fprintf('  P7  (Property 7)  Status struct schema — 8 required fields always present\n');
    fprintf('  R31 (Req 3.1)     Already-connected path — no server restart, connected=true\n');
    fprintf('  R34 (Req 3.4)     No-LiveLink path — hasLiveLink=false, no exception\n');
    fprintf('  probe_disconnect  Confirmed disconnect → connected=false\n');
    fprintf('  probe_success     mphversion success → connected=true with version\n');

    fprintf('\nFinal status: ');
    if allPassed
        fprintf('ALL PASS — behavioral baseline documented.\n\n');
    else
        fprintf('SOME FAIL — investigate failures before implementing fix.\n\n');
    end
end
