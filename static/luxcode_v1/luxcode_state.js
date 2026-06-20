(function () {
    "use strict";

    const TERMINAL_TASK_STATES = new Set(["cancelled", "blocked", "failed", "completed"]);
    const DEFAULT_POLL_INTERVAL_MS = 2500;
    const APPROVAL_POLL_INTERVAL_MS = 8000;
    const MAX_CONSECUTIVE_ERRORS = 3;

    const state = {
        currentTaskId: "",
        currentTask: null,
        pollingTimer: null,
        pollingActive: false,
        lastError: null,
        submittedText: "",
        consecutiveErrors: 0,
        abortController: null,
    };

    function taskStatus(task) {
        return String(task?.current_state || task?.status || task?.outcome || "").toLowerCase();
    }

    function isTerminalTaskState(status) {
        return TERMINAL_TASK_STATES.has(String(status || "").toLowerCase());
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

    function resetTaskState() {
        stopTaskPolling();
        state.currentTaskId = "";
        state.currentTask = null;
        state.lastError = null;
        state.submittedText = "";
        state.consecutiveErrors = 0;
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

    window.LuxCodeTaskState = {
        state,
        setCurrentTask,
        startTaskPolling,
        stopTaskPolling,
        resetTaskState,
        isTerminalTaskState,
    };
})();
