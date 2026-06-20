(function () {
    "use strict";

    const TERMINAL_TASK_STATES = new Set(["cancelled", "blocked", "failed", "completed"]);
    const DEFAULT_POLL_INTERVAL_MS = 2500;
    const APPROVAL_POLL_INTERVAL_MS = 8000;
    const MAX_CONSECUTIVE_ERRORS = 3;
    const MAX_ADVANCE_ATTEMPTS = 8;
    const MAX_ADVANCE_ERRORS = 2;
    const ADVANCE_DELAY_MS = 700;
    const USER_ACTION_STATES = new Set([
        "awaiting_approval",
        "apply_prepared",
        "verification_prepared",
        "paused",
        "awaiting_scope_permission",
        "awaiting_irreversible_confirmation",
        "autonomy_paused",
        "budget_exhausted",
    ]);

    const state = {
        currentTaskId: "",
        currentTask: null,
        pollingTimer: null,
        pollingActive: false,
        lastError: null,
        submittedText: "",
        consecutiveErrors: 0,
        abortController: null,
        advanceInFlight: false,
        autoAdvanceActive: false,
        autoAdvanceTimer: null,
        lastAdvancedState: "",
        lastAdvanceResult: null,
        lastAdvanceDigest: "",
        advanceErrorCount: 0,
        advanceAttemptCount: 0,
        advanceAbortController: null,
    };

    function taskStatus(task) {
        return String(task?.current_state || task?.status || task?.outcome || "").toLowerCase();
    }

    function isTerminalTaskState(status) {
        return TERMINAL_TASK_STATES.has(String(status || "").toLowerCase());
    }

    function shouldStopAdvancing(task) {
        const status = taskStatus(task);
        return (
            !task
            || isTerminalTaskState(status)
            || USER_ACTION_STATES.has(status)
            || task.requires_user_approval === true
            || task.can_advance === false
            || (Array.isArray(task.blocked_reasons) && task.blocked_reasons.length > 0)
        );
    }

    function canAdvanceTask(task) {
        return Boolean(task?.task_id) && !state.advanceInFlight && !shouldStopAdvancing(task);
    }

    function advanceDigest(task) {
        return [
            task?.task_id || "",
            taskStatus(task),
            (task?.completed_steps || []).join("|"),
            (task?.pending_steps || []).join("|"),
            task?.updated_at || "",
        ].join("::");
    }

    function emit(name, detail) {
        window.dispatchEvent(new CustomEvent(name, { detail }));
    }

    function setCurrentTask(task) {
        state.currentTask = task || null;
        state.currentTaskId = String(task?.task_id || task?.id || state.currentTaskId || "");
        state.lastError = null;
        state.consecutiveErrors = 0;
        emit("luxcode:task-update", { task: state.currentTask });
        if (state.autoAdvanceActive && state.currentTaskId && shouldStopAdvancing(state.currentTask)) {
            stopAutoAdvance();
        }
    }

    function stopTaskPolling() {
        if (state.pollingTimer) {
            window.clearTimeout(state.pollingTimer);
            state.pollingTimer = null;
        }
        if (state.abortController) {
            state.abortController.abort();
            state.abortController = null;
        }
        state.pollingActive = false;
    }

    function stopAutoAdvance() {
        if (state.autoAdvanceTimer) {
            window.clearTimeout(state.autoAdvanceTimer);
            state.autoAdvanceTimer = null;
        }
        if (state.advanceAbortController) {
            state.advanceAbortController.abort();
            state.advanceAbortController = null;
        }
        state.advanceInFlight = false;
        state.autoAdvanceActive = false;
    }

    function resetTaskState() {
        stopTaskPolling();
        stopAutoAdvance();
        state.currentTaskId = "";
        state.currentTask = null;
        state.lastError = null;
        state.submittedText = "";
        state.consecutiveErrors = 0;
        state.lastAdvancedState = "";
        state.lastAdvanceResult = null;
        state.lastAdvanceDigest = "";
        state.advanceErrorCount = 0;
        state.advanceAttemptCount = 0;
    }

    function scheduleNextPoll(taskId) {
        const status = taskStatus(state.currentTask);
        const interval = status === "awaiting_approval" ? APPROVAL_POLL_INTERVAL_MS : DEFAULT_POLL_INTERVAL_MS;
        state.pollingTimer = window.setTimeout(() => pollTask(taskId), interval);
    }

    async function pollTask(taskId) {
        if (!state.pollingActive || taskId !== state.currentTaskId) return;
        state.abortController = new AbortController();
        try {
            const task = await window.LuxCodeApi.getLuxCodeTask(taskId, {
                timeoutMs: 12000,
                controller: state.abortController,
            });
            state.abortController = null;
            if (task?.found === false) {
                throw { normalized: true, message: "Gorev bulunamadi", code: "task_not_found", detail: task };
            }
            setCurrentTask(task);
            if (isTerminalTaskState(taskStatus(task))) {
                stopTaskPolling();
                stopAutoAdvance();
                emit("luxcode:task-terminal", { task });
                return;
            }
            scheduleNextPoll(taskId);
        } catch (error) {
            state.abortController = null;
            state.lastError = window.LuxCodeApi.normalizeApiError(error);
            state.consecutiveErrors += 1;
            emit("luxcode:task-error", { error: state.lastError, taskId });
            if (state.consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                stopTaskPolling();
                return;
            }
            scheduleNextPoll(taskId);
        }
    }

    function startTaskPolling(taskId) {
        const safeTaskId = String(taskId || "");
        if (!safeTaskId) {
            state.lastError = { message: "Gorev kimligi eksik", code: "missing_task_id" };
            emit("luxcode:task-error", { error: state.lastError, taskId: safeTaskId });
            return;
        }
        if (state.pollingActive && state.currentTaskId === safeTaskId) return;
        stopTaskPolling();
        state.currentTaskId = safeTaskId;
        state.pollingActive = true;
        state.consecutiveErrors = 0;
        pollTask(safeTaskId);
    }

    function scheduleAutoAdvance(taskId) {
        if (!state.autoAdvanceActive || state.advanceInFlight) return;
        if (state.autoAdvanceTimer) window.clearTimeout(state.autoAdvanceTimer);
        state.autoAdvanceTimer = window.setTimeout(() => requestTaskAdvance(state.currentTask), ADVANCE_DELAY_MS);
    }

    async function requestTaskAdvance(task) {
        const taskId = String(task?.task_id || state.currentTaskId || "");
        if (!taskId || !state.autoAdvanceActive) return;
        if (!canAdvanceTask(task)) {
            stopAutoAdvance();
            return;
        }
        const digest = advanceDigest(task);
        if (state.lastAdvanceDigest === digest || state.lastAdvancedState === taskStatus(task)) {
            state.lastError = {
                message: "Gorev ilerletilemedi: backend ayni state yanitini tekrarliyor",
                code: "advance_repeated_state",
            };
            emit("luxcode:task-error", { error: state.lastError, taskId });
            stopAutoAdvance();
            return;
        }
        if (state.advanceAttemptCount >= MAX_ADVANCE_ATTEMPTS) {
            state.lastError = {
                message: "Gorev ilerletilemedi: maksimum otomatik ilerleme sinirina ulasildi",
                code: "advance_attempt_limit",
            };
            emit("luxcode:task-error", { error: state.lastError, taskId });
            stopAutoAdvance();
            return;
        }

        state.advanceInFlight = true;
        state.advanceAbortController = new AbortController();
        state.lastAdvancedState = taskStatus(task);
        state.lastAdvanceDigest = digest;
        state.advanceAttemptCount += 1;
        emit("luxcode:task-advance-start", { task, attempt: state.advanceAttemptCount });

        try {
            const advanced = await window.LuxCodeApi.advanceLuxCodeTask(taskId, { action: "next" }, {
                timeoutMs: 30000,
                controller: state.advanceAbortController,
            });
            state.advanceAbortController = null;
            state.advanceInFlight = false;
            state.lastAdvanceResult = advanced;
            state.advanceErrorCount = 0;
            setCurrentTask(advanced);

            const fresh = await window.LuxCodeApi.getLuxCodeTask(taskId, { timeoutMs: 12000 });
            setCurrentTask(fresh);
            if (shouldStopAdvancing(fresh)) {
                stopAutoAdvance();
                if (isTerminalTaskState(taskStatus(fresh))) {
                    stopTaskPolling();
                    emit("luxcode:task-terminal", { task: fresh });
                }
                return;
            }
            scheduleAutoAdvance(taskId);
        } catch (error) {
            state.advanceAbortController = null;
            state.advanceInFlight = false;
            state.advanceErrorCount += 1;
            state.lastError = window.LuxCodeApi.normalizeApiError(error);
            emit("luxcode:task-error", { error: state.lastError, taskId });
            if (state.advanceErrorCount >= MAX_ADVANCE_ERRORS) {
                stopAutoAdvance();
                return;
            }
            scheduleAutoAdvance(taskId);
        }
    }

    function startAutoAdvance(taskId) {
        const safeTaskId = String(taskId || "");
        if (!safeTaskId) return;
        state.autoAdvanceActive = true;
        state.advanceErrorCount = 0;
        state.advanceAttemptCount = 0;
        state.lastAdvancedState = "";
        state.lastAdvanceDigest = "";
        scheduleAutoAdvance(safeTaskId);
    }

    window.LuxCodeTaskState = {
        state,
        setCurrentTask,
        startTaskPolling,
        stopTaskPolling,
        resetTaskState,
        isTerminalTaskState,
        canAdvanceTask,
        requestTaskAdvance,
        startAutoAdvance,
        stopAutoAdvance,
        shouldStopAdvancing,
    };
})();
