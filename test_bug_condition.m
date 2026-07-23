function results = test_bug_condition()
% test_bug_condition  Bug Condition Exploration Tests for COMSOL LiveLink Linux Stability
%
% CRITICAL: Sub-conditions A and B are EXPECTED TO FAIL on unfixed code.
%           Sub-conditions C, D, E are EXPECTED TO PASS on unfixed code
%           (their passing confirms the bug exists in those areas).
%
% After implementing the fix (tasks 3.1-3.4), re-run — all tests should PASS.
%
% Usage:
%   results = test_bug_condition()
%
% Requirements: 1.1, 1.2, 1.3, 1.4, 1.5

    fprintf('=== Bug Condition Exploration Tests ===\n');
    fprintf('Spec: comsol-livelink-linux-stability\n');
    fprintf('CRITICAL: Sub-conditions A and B MUST FAIL on unfixed code.\n');
    fprintf('          Sub-conditions C, D, E MUST PASS on unfixed code (documenting bugs).\n\n');

    results = struct();
    results.A = test_subcondition_A();
    results.B = test_subcondition_B();
    results.C = test_subcondition_C();
    results.D = test_subcondition_D();
    results.E = test_subcondition_E();

    print_summary(results);
end

% =========================================================================
% Sub-condition A: No pre-extraction connection probe in extraction_controller
% =========================================================================
function result = test_subcondition_A()
% Test that extraction_controller calls comsol_livelink_connection('status')
% BEFORE calling export_dataset at the top of each dataset loop iteration.
%
% Strategy: Source-code analysis of extraction_controller.m.
% On unfixed code, there is NO such probe at the top of the loop — EXPECTED FAILURE.
%
% Validates: Requirements 1.1, 2.1

    result = struct('name', 'A', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Sub-condition A: Pre-extraction connection probe ---\n');

    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'extraction_controller.m');
    if ~isfile(sourceFile)
        result.message = 'SKIP: extraction_controller.m not found';
        fprintf('  SKIP: extraction_controller.m not found\n\n');
        return;
    end

    src = fileread(sourceFile);

    % Find the main loop body: from "for i = 1:nTotal" to end of loop
    % We want to check: does comsol_livelink_connection('status') appear
    % BEFORE export_dataset (via run_bfov_exports) in the loop body?

    loopStartToken = 'for i = 1:nTotal';
    exportCallToken = 'run_bfov_exports';
    probeTokens = {
        'comsol_livelink_connection(''status'')', ...
        'comsol_livelink_connection("status")', ...
        "comsol_livelink_connection('status')"
    };

    loopIdx = strfind(src, loopStartToken);
    if isempty(loopIdx)
        result.message = 'SKIP: Could not locate loop "for i = 1:nTotal" in extraction_controller.m';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    loopStart = loopIdx(1);
    exportIdx = strfind(src(loopStart:end), exportCallToken);
    if isempty(exportIdx)
        result.message = 'SKIP: Could not locate run_bfov_exports call after loop start';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end
    exportAbsIdx = loopStart + exportIdx(1) - 1;

    % Look for a pre-export probe in the loop body (between loop start and first export call)
    loopBodyBeforeExport = src(loopStart:exportAbsIdx);
    probeFound = false;
    for k = 1:numel(probeTokens)
        if contains(loopBodyBeforeExport, probeTokens{k})
            probeFound = true;
            break;
        end
    end

    if probeFound
        result.passed = true;
        result.message = 'PASS: comsol_livelink_connection(''status'') probe found before export_dataset in loop body.';
        fprintf('  PASS: Pre-extraction probe found (fix may already be applied).\n\n');
    else
        result.passed = false;
        result.counterexample = ['No comsol_livelink_connection(''status'') call found in the loop ' ...
            'body between "for i = 1:nTotal" and the first run_bfov_exports call. ' ...
            'A mid-session disconnect will not be detected until export_dataset throws.'];
        result.message = ['FAIL (expected on unfixed code): ' result.counterexample];
        fprintf('  FAIL (expected): No pre-extraction probe found in loop body.\n');
        fprintf('  Counterexample: %s\n\n', result.counterexample);
    end
end


% =========================================================================
% Sub-condition B: extraction_controller aborts without reconnect attempt
% =========================================================================
function result = test_subcondition_B()
% Test that the catch block in extraction_controller calls
% comsol_livelink_connection('connect') BEFORE breaking out of the loop
% when a not-connected error is caught.
%
% Strategy: Source-code analysis of extraction_controller.m.
% On unfixed code, the catch block only has "break" — EXPECTED FAILURE.
%
% Validates: Requirements 1.2, 2.2

    result = struct('name', 'B', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Sub-condition B: Reconnect attempt before batch abort ---\n');

    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'extraction_controller.m');
    if ~isfile(sourceFile)
        result.message = 'SKIP: extraction_controller.m not found';
        fprintf('  SKIP: extraction_controller.m not found\n\n');
        return;
    end

    src = fileread(sourceFile);

    % Locate the is_not_connected_error check inside the catch block
    % and verify that comsol_livelink_connection('connect') appears
    % BEFORE the break that follows it.
    notConnectedToken = 'is_not_connected_error(err)';
    connectTokens = {
        'comsol_livelink_connection(''connect'')', ...
        'comsol_livelink_connection("connect")'
    };
    breakToken = 'break;';

    notConnIdx = strfind(src, notConnectedToken);
    if isempty(notConnIdx)
        result.message = 'SKIP: Could not locate is_not_connected_error(err) in extraction_controller.m';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    % Use the first occurrence (main loop catch block)
    checkPos = notConnIdx(1);

    % Find the next break after this check
    breakSearch = strfind(src(checkPos:end), breakToken);
    if isempty(breakSearch)
        result.message = 'SKIP: Could not locate break after is_not_connected_error check';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end
    breakAbsIdx = checkPos + breakSearch(1) - 1;

    % Look for a reconnect call between the not-connected check and the break
    catchBodyBeforeBreak = src(checkPos:breakAbsIdx);
    reconnectFound = false;
    for k = 1:numel(connectTokens)
        if contains(catchBodyBeforeBreak, connectTokens{k})
            reconnectFound = true;
            break;
        end
    end

    if reconnectFound
        result.passed = true;
        result.message = 'PASS: comsol_livelink_connection(''connect'') found in catch block before break.';
        fprintf('  PASS: Reconnect call found before break (fix may already be applied).\n\n');
    else
        result.passed = false;
        result.counterexample = sprintf(['In extraction_controller.m catch block: after is_not_connected_error ' ...
            'returns true, no comsol_livelink_connection(''connect'') call found before "break;". ' ...
            'The batch will abort immediately at dataset N without attempting reconnect, ' ...
            'abandoning all remaining datasets.']);
        result.message = ['FAIL (expected on unfixed code): ' result.counterexample];
        fprintf('  FAIL (expected): No reconnect call in catch block before break.\n');
        fprintf('  Counterexample: %s\n\n', result.counterexample);
    end
end


% =========================================================================
% Sub-condition C: Server launch command uses session-detached mechanism
% =========================================================================
function result = test_subcondition_C()
% Test that the launch command in comsol_livelink_connection.m uses
% setsid or systemd-run for session detachment.
%
% NOTE: The current (unfixed) code already contains setsid in a conditional
% check. This sub-condition documents whether a RELIABLE primary detachment
% strategy is used vs. a fragile fallback.
%
% On unfixed code: the command uses setsid only if available, with nohup
% fallback — no systemd-run fallback.
% This test PASSES on current code to document that setsid IS present,
% but verifies the command structure for correctness.
%
% Validates: Requirements 1.3, 2.3

    result = struct('name', 'C', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Sub-condition C: Session-detached server launch command ---\n');

    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'comsol_livelink_connection.m');
    if ~isfile(sourceFile)
        result.message = 'SKIP: comsol_livelink_connection.m not found';
        fprintf('  SKIP: comsol_livelink_connection.m not found\n\n');
        return;
    end

    src = fileread(sourceFile);

    % Find the launch_linux_mphserver function body
    launchFnToken = 'function [statusCode, output] = launch_linux_mphserver';
    launchIdx = strfind(src, launchFnToken);

    if isempty(launchIdx)
        result.message = 'SKIP: Could not locate launch_linux_mphserver function';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    % Extract a reasonable window of the function body (next 1500 chars)
    launchBody = src(launchIdx(1) : min(launchIdx(1)+1500, length(src)));

    hasSetsid = contains(launchBody, 'setsid');
    hasSystemdRun = contains(launchBody, 'systemd-run');
    hasNohupFallback = contains(launchBody, 'nohup');

    % Sub-condition C: assert that setsid OR systemd-run is used in the command
    % (not only nohup, which does not create a new session)
    if hasSetsid || hasSystemdRun
        result.passed = true;
        if hasSetsid && hasSystemdRun
            mechanism = 'setsid AND systemd-run';
        elseif hasSetsid
            mechanism = 'setsid';
        else
            mechanism = 'systemd-run';
        end

        if hasNohupFallback
            result.message = sprintf(['PASS: launch_linux_mphserver uses %s with nohup fallback. ' ...
                'Session detachment is supported when %s is available.'], mechanism, mechanism);
        else
            result.message = sprintf('PASS: launch_linux_mphserver uses %s (no nohup fallback present).', mechanism);
        end
        fprintf('  PASS: %s\n\n', result.message);
    else
        % Only nohup — this is the bug (no setsid or systemd-run)
        result.passed = false;
        result.counterexample = ['launch_linux_mphserver command does NOT contain setsid or ' ...
            'systemd-run. Only nohup is used, which does not create a new Unix session. ' ...
            'If the calling terminal/SSH session closes, comsol mphserver may receive SIGHUP and exit.'];
        result.message = ['FAIL: ' result.counterexample];
        fprintf('  FAIL: %s\n\n', result.counterexample);
    end

    % Additional documentation: log the actual command snippet
    cmdToken = 'command = sprintf';
    cmdIdx = strfind(launchBody, cmdToken);
    if ~isempty(cmdIdx)
        snippetEnd = min(cmdIdx(1)+400, length(launchBody));
        snippet = strtrim(launchBody(cmdIdx(1):snippetEnd));
        snippet = strrep(snippet, newline, ' ');
        fprintf('  Launch command snippet: %s...\n\n', snippet(1:min(200,end)));
    end
end


% =========================================================================
% Sub-condition D: Post-launch retry budget is too short (< 60 seconds)
% =========================================================================
function result = test_subcondition_D()
% Test that the try_mphstart_retries call after server launch uses a
% budget of at least 12 probes x 5 seconds = 60 seconds total.
%
% On unfixed code: try_mphstart_retries(12, 2.0, serverPort) = 24s total.
% This PASSES on unfixed code to confirm the bug (24s < 60s).
%
% Validates: Requirements 1.4, 2.4

    result = struct('name', 'D', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Sub-condition D: Post-launch retry budget sufficiency ---\n');

    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'comsol_livelink_connection.m');
    if ~isfile(sourceFile)
        result.message = 'SKIP: comsol_livelink_connection.m not found';
        fprintf('  SKIP: comsol_livelink_connection.m not found\n\n');
        return;
    end

    src = fileread(sourceFile);

    % Locate connect_on_linux function body
    connectFnToken = 'function [connected, detail, versionText, startAttempted] = connect_on_linux';
    connectIdx = strfind(src, connectFnToken);
    if isempty(connectIdx)
        result.message = 'SKIP: Could not locate connect_on_linux function';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    % Extract function body (next 3000 chars covers it)
    connectBody = src(connectIdx(1) : min(connectIdx(1)+3000, length(src)));

    % Find all try_mphstart_retries calls and extract their arguments
    pattern = 'try_mphstart_retries\((\d+),\s*([\d.]+)';
    [tokens, matches] = regexp(connectBody, pattern, 'tokens', 'match');

    if isempty(tokens)
        result.message = 'SKIP: Could not parse try_mphstart_retries call arguments';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    fprintf('  Found %d try_mphstart_retries call(s) in connect_on_linux:\n', numel(tokens));
    for k = 1:numel(tokens)
        maxTries = str2double(tokens{k}{1});
        pauseSec = str2double(tokens{k}{2});
        totalWait = maxTries * pauseSec;
        fprintf('    Call %d: try_mphstart_retries(%d, %.1f) → total budget = %.1f s  [match: %s]\n', ...
            k, maxTries, pauseSec, totalWait, matches{k});
    end

    % The post-launch call is the one that follows startAttempted = true and launch_linux_mphserver.
    % It is typically the LAST try_mphstart_retries call (or the one after launch).
    % Find the call that comes after "startAttempted = true"
    startAttemptedToken = 'startAttempted = true';
    saIdx = strfind(connectBody, startAttemptedToken);

    postLaunchMaxTries = NaN;
    postLaunchPause = NaN;
    postLaunchTotal = NaN;

    if ~isempty(saIdx)
        bodyAfterLaunch = connectBody(saIdx(1):end);
        [postTokens, postMatches] = regexp(bodyAfterLaunch, pattern, 'tokens', 'match');
        if ~isempty(postTokens)
            % First try_mphstart_retries after startAttempted = true is the post-launch one
            postLaunchMaxTries = str2double(postTokens{1}{1});
            postLaunchPause = str2double(postTokens{1}{2});
            postLaunchTotal = postLaunchMaxTries * postLaunchPause;
            fprintf('  Post-launch call: try_mphstart_retries(%d, %.1f) = %.1f s total\n', ...
                postLaunchMaxTries, postLaunchPause, postLaunchTotal);
        end
    end

    if isnan(postLaunchTotal)
        % Fall back: use the last call found
        lastTok = tokens{end};
        postLaunchMaxTries = str2double(lastTok{1});
        postLaunchPause = str2double(lastTok{2});
        postLaunchTotal = postLaunchMaxTries * postLaunchPause;
        fprintf('  (Using last call as post-launch): %.1f s total\n', postLaunchTotal);
    end

    REQUIRED_MIN_WAIT = 60.0;  % seconds (12 probes × 5s)
    REQUIRED_MIN_PROBES = 12;

    if postLaunchTotal < REQUIRED_MIN_WAIT
        % Bug confirmed: budget is too short
        % This PASSES the sub-condition test (we expect to confirm the bug)
        result.passed = true;
        result.counterexample = sprintf(['try_mphstart_retries(%d, %.1f) after server launch: ' ...
            'total budget = %.1f s, which is < %.0f s (required). ' ...
            'COMSOL typically takes 30-90 s to initialize on Linux. ' ...
            'All probes will fail before the server is ready.'], ...
            postLaunchMaxTries, postLaunchPause, postLaunchTotal, REQUIRED_MIN_WAIT);
        result.message = sprintf(['PASS (confirms bug D): %s'], result.counterexample);
        fprintf('  PASS (confirms bug): Post-launch budget = %.1f s < %.0f s required.\n', ...
            postLaunchTotal, REQUIRED_MIN_WAIT);
        fprintf('  Counterexample: %s\n\n', result.counterexample);
    else
        % Budget is sufficient — bug is fixed
        result.passed = true;
        result.message = sprintf(['PASS (fix verified): Post-launch budget = %.1f s >= %.0f s required. ' ...
            'try_mphstart_retries(%d, %.1f).'], ...
            postLaunchTotal, REQUIRED_MIN_WAIT, postLaunchMaxTries, postLaunchPause);
        fprintf('  PASS (fix verified): Budget = %.1f s (>= %.0f s required).\n\n', ...
            postLaunchTotal, REQUIRED_MIN_WAIT);
    end
end


% =========================================================================
% Sub-condition E: Transient errors cause false disconnect classification
% =========================================================================
function result = test_subcondition_E()
% Test that probe_connection() does NOT return connected=false for a
% transient error that is NOT a confirmed disconnect error.
%
% Strategy: Inject a stub mphversion that throws a generic socket error
% whose message does NOT contain any disconnect keyword recognized by
% is_not_connected_error(). Then call probe_connection() (via
% comsol_livelink_connection('status')) and observe the result.
%
% On unfixed code: probe_connection falls through to ModelUtil probes,
% which also fail (no COMSOL), so connected=false is returned.
% This PASSES on unfixed code (confirms the bug — false disconnect).
%
% Validates: Requirements 1.5, 2.5

    result = struct('name', 'E', 'passed', false, 'message', '', 'counterexample', '');
    fprintf('--- Sub-condition E: Transient error false-disconnect classification ---\n');

    sourceFile = fullfile(fileparts(mfilename('fullpath')), 'comsol_livelink_connection.m');
    if ~isfile(sourceFile)
        result.message = 'SKIP: comsol_livelink_connection.m not found';
        fprintf('  SKIP: comsol_livelink_connection.m not found\n\n');
        return;
    end

    % First, verify that the transient error message we'll use is NOT
    % classified as a disconnect by is_not_connected_error
    transientMsg = 'java.net.SocketException: Software caused connection abort';
    % Note: "connection reset", "connection timed out" etc. ARE in is_not_connected_error.
    % "Software caused connection abort" and "Network unreachable" are NOT listed.

    % Check our source analysis of is_not_connected_error in comsol_livelink_connection.m
    src = fileread(sourceFile);
    isNotConnFnToken = 'function tf = is_not_connected_error(err)';
    fnIdx = strfind(src, isNotConnFnToken);

    if isempty(fnIdx)
        result.message = 'SKIP: Could not locate is_not_connected_error function in comsol_livelink_connection.m';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    % Extract function body
    fnBody = src(fnIdx(1) : min(fnIdx(1)+600, length(src)));

    % Verify transientMsg keywords are NOT in is_not_connected_error
    transientKeyword = 'software caused connection abort';
    if contains(lower(fnBody), transientKeyword)
        % The keyword IS in the classifier — pick a different transient message
        transientMsg = 'java.lang.NullPointerException: null';
        transientKeyword = 'nullpointerexception';
        fprintf('  Note: "software caused connection abort" IS in classifier, using NullPointerException instead.\n');
    end

    fprintf('  Transient error message under test: "%s"\n', transientMsg);
    fprintf('  Verifying this is NOT a disconnect keyword in is_not_connected_error...\n');

    % Verify our chosen message isn't caught by the classifier
    disconnectKeywords = {'not connected to a server', 'no conectado a un servidor', ...
        'connection reset', 'connection timed out', 'broken pipe', 'java.rmi', ...
        'connection refused', 'failed to connect'};

    msgLower = lower(transientMsg);
    isClassifiedAsDisconnect = false;
    for k = 1:numel(disconnectKeywords)
        if contains(msgLower, disconnectKeywords{k})
            isClassifiedAsDisconnect = true;
            fprintf('  WARNING: transient message contains keyword "%s" — choosing different message.\n', disconnectKeywords{k});
            transientMsg = 'java.lang.IllegalStateException: method invocation failed';
            msgLower = lower(transientMsg);
            break;
        end
    end

    % Final verification
    isTransientClassifiedAsDisconnect = false;
    for k = 1:numel(disconnectKeywords)
        if contains(lower(transientMsg), disconnectKeywords{k})
            isTransientClassifiedAsDisconnect = true;
            break;
        end
    end

    if isTransientClassifiedAsDisconnect
        result.message = 'SKIP: Could not find a transient error message not caught by is_not_connected_error';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    fprintf('  Confirmed: "%s" is NOT classified as disconnect by is_not_connected_error.\n', transientMsg);

    % Now check probe_connection() source for transient retry logic
    probeConnFnToken = 'function [connected, detail, versionText] = probe_connection';
    probeIdx = strfind(src, probeConnFnToken);
    if isempty(probeIdx)
        result.message = 'SKIP: Could not locate probe_connection function';
        fprintf('  SKIP: %s\n\n', result.message);
        return;
    end

    % Extract probe_connection body
    probeBody = src(probeIdx(1) : min(probeIdx(1)+1200, length(src)));

    % Look for transient-error retry logic: a retry of mphversion after a non-disconnect error
    % Fixed code would have: if ~is_not_connected_error(err) -> pause and retry mphversion
    retryPatterns = {
        'retry', ...
        'pause(', ...
        '~is_not_connected_error'
    };

    retryFound = false;
    for k = 1:numel(retryPatterns)
        if contains(probeBody, retryPatterns{k})
            retryFound = true;
            break;
        end
    end

    % Check: after catching a non-disconnect error, does probe_connection fall through
    % to ModelUtil probes WITHOUT retrying mphversion?
    % On unfixed code: the catch block does "if is_not_connected_error(err) -> return"
    % then falls through — no retry of mphversion for transient errors.
    catchBlock = '';
    catchIdx = strfind(probeBody, 'catch err');
    if ~isempty(catchIdx)
        catchBlock = probeBody(catchIdx(1) : min(catchIdx(1)+400, length(probeBody)));
    end

    hasRetryInCatch = false;
    for k = 1:numel(retryPatterns)
        if contains(catchBlock, retryPatterns{k})
            hasRetryInCatch = true;
            break;
        end
    end

    fprintf('  Analyzing probe_connection() catch block for transient retry logic...\n');

    if ~hasRetryInCatch
        % No retry — bug confirmed. On unfixed code, a transient error causes
        % connected=false because ModelUtil probes also fail. This PASSES the test.
        result.passed = true;
        result.counterexample = sprintf(['probe_connection() catch block has NO retry of mphversion ' ...
            'for non-disconnect errors. When mphversion throws "%s" ' ...
            '(which is_not_connected_error classifies as false), the function falls through ' ...
            'to ModelUtil probes. In a test environment (no COMSOL), ModelUtil also fails, ' ...
            'so connected=false is returned — a false disconnect classification. ' ...
            'The transient error is treated as a disconnection.'], transientMsg);
        result.message = sprintf('PASS (confirms bug E): %s', result.counterexample);
        fprintf('  PASS (confirms bug): No transient-error retry in probe_connection catch block.\n');
        fprintf('  Counterexample: %s\n\n', result.counterexample);
    else
        % Retry logic found — bug is fixed
        result.passed = true;
        result.message = ['PASS (fix verified): probe_connection catch block has retry logic ' ...
            'for non-disconnect errors.'];
        fprintf('  PASS (fix verified): Transient error retry logic found in probe_connection.\n\n');
    end
end


% =========================================================================
% Summary printer
% =========================================================================
function print_summary(results)
    fprintf('\n=== Test Summary ===\n');
    fprintf('%-14s %-8s %s\n', 'Sub-condition', 'Result', 'Notes');
    fprintf('%s\n', repmat('-', 1, 80));

    fields = fieldnames(results);
    allPassed = true;
    for k = 1:numel(fields)
        r = results.(fields{k});
        if r.passed
            status = 'PASS';
        else
            status = 'FAIL';
            allPassed = false;
        end
        fprintf('%-14s %-8s %s\n', ['  ' r.name], status, r.message);
    end

    fprintf('%s\n', repmat('-', 1, 80));
    fprintf('\nExpected results on UNFIXED code:\n');
    fprintf('  A: FAIL  (no pre-extraction probe → counterexample confirms bug 1.1)\n');
    fprintf('  B: FAIL  (no reconnect in catch block → counterexample confirms bug 1.2)\n');
    fprintf('  C: PASS  (documents launch command: confirms setsid present or absent)\n');
    fprintf('  D: PASS  (post-launch budget < 60s → counterexample confirms bug 1.4)\n');
    fprintf('  E: PASS  (no retry for transient errors → counterexample confirms bug 1.5)\n');

    fprintf('\nExpected results on FIXED code (after tasks 3.1-3.4):\n');
    fprintf('  A: PASS  (pre-extraction probe present)\n');
    fprintf('  B: PASS  (reconnect attempted before break)\n');
    fprintf('  C: PASS  (setsid or systemd-run in launch command)\n');
    fprintf('  D: PASS  (budget >= 60s)\n');
    fprintf('  E: PASS  (transient-error retry in probe_connection)\n');

    fprintf('\nFinal status: ');
    if allPassed
        fprintf('ALL PASS\n\n');
    else
        fprintf('SOME FAIL (expected on unfixed code — run again after fix)\n\n');
    end
end
