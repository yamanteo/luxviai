(function () {
    "use strict";

    const DEFAULT_TIMEOUT_MS = 15000;

    function backendBaseUrl() {
        const configured = window.LUXCODE_BACKEND_BASE_URL || "";
        return String(configured).replace(/\/+$/, "");
    }

    function normalizeApiError(error) {
        if (!error) return { message: "Bilinmeyen backend hatasi", code: "unknown_error" };
        if (error.name === "AbortError") {
            return { message: "Backend istegi zaman asimina ugradi", code: "request_timeout" };
        }
        if (error.normalized) return error;
        return {
            message: error.message || "Backend baglantisi kurulamadı",
            code: error.code || "network_error",
            status: error.status || 0,
            detail: error.detail || null,
        };
    }

    async function requestJson(path, options = {}) {
        const controller = options.controller || new AbortController();
        const timeoutMs = Number(options.timeoutMs || DEFAULT_TIMEOUT_MS);
        const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
        const headers = { Accept: "application/json", ...(options.headers || {}) };

        let response;
        let text = "";
        try {
            response = await fetch(`${backendBaseUrl()}${path}`, {
                method: options.method || "GET",
                body: options.body,
                headers,
                signal: controller.signal,
            });
            text = await response.text();
        } catch (error) {
            throw normalizeApiError(error);
        } finally {
            window.clearTimeout(timeoutId);
        }

        let payload;
        try {
            payload = text ? JSON.parse(text) : {};
        } catch (error) {
            throw {
                normalized: true,
                message: "Backend gecersiz JSON yaniti dondurdu",
                code: "invalid_json",
                status: response.status,
                detail: text.slice(0, 300),
            };
        }

        if (!response.ok) {
            const message = payload.detail || payload.reason || payload.error || `HTTP ${response.status}`;
            throw {
                normalized: true,
                message,
                code: response.status >= 500 ? "server_error" : "client_error",
                status: response.status,
                detail: payload,
            };
        }

        return payload;
    }

    function createLuxCodeTask(payload, options = {}) {
        return requestJson("/luxcode-task/create", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs,
            controller: options.controller,
        });
    }

    function getLuxCodeTask(taskId, options = {}) {
        if (!taskId) {
            return Promise.reject({
                normalized: true,
                message: "Gorev kimligi eksik",
                code: "missing_task_id",
            });
        }
        return requestJson(`/luxcode-task/${encodeURIComponent(taskId)}`, {
            timeoutMs: options.timeoutMs,
            controller: options.controller,
        });
    }

    function advanceLuxCodeTask(taskId, payload = {}, options = {}) {
        if (!taskId) {
            return Promise.reject({
                normalized: true,
                message: "Gorev kimligi eksik",
                code: "missing_task_id",
            });
        }
        return requestJson("/luxcode-task/advance", {
            method: "POST",
            body: JSON.stringify({
                task_id: taskId,
                action: payload.action || "next",
                ...(payload.patch_steps ? { patch_steps: payload.patch_steps } : {}),
                ...(payload.verification_checks ? { verification_checks: payload.verification_checks } : {}),
            }),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs,
            controller: options.controller,
        });
    }

    window.LuxCodeApi = {
        createLuxCodeTask,
        getLuxCodeTask,
        advanceLuxCodeTask,
        normalizeApiError,
    };
})();
