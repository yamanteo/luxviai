(function () {
    "use strict";

    const DEFAULT_TIMEOUT_MS = 15000;

    function backendBaseUrl() {
        const configured = window.LUXCODE_BACKEND_BASE_URL || "";
        return String(configured).replace(/\/+$/, "");
    }

    function normalizeApiError(error) {
        if (!error) return { message: "Bilinmeyen backend hatası", code: "unknown_error" };
        if (error.name === "AbortError") {
            return { message: "Backend isteği zaman aşımına uğradı", code: "request_timeout" };
        }
        if (error.normalized) return error;
        return {
            message: error.message || "Backend bağlantısı kurulamadı",
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
                message: "Backend geçersiz JSON yanıtı döndürdü",
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

    function runLuxCodeAgent(payload, options = {}) {
        if (options.stream) {
            return requestLuxCodeAgentStream(payload, options);
        }
        return requestJson("/luxcode-agent/run", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 60000,
            controller: options.controller,
        });
    }

    function looksLikeCoderPrompt(prompt) {
        return /\b(create|read|write|update|edit|delete|patch|test|run|fix|dosya|klas[oö]r|oku|yaz|olu[sş]tur|d[üu]zelt|test|kod|commit|deploy)\b/i.test(prompt || "");
    }

    async function sendConversationMessage(payload = {}, options = {}) {
        const prompt = String(payload.message || payload.prompt || "").trim();
        const workspaceRoot = payload.repository_root
            || payload.workspace_root
            || payload.project_path
            || "C:\\Users\\Teoman\\OneDrive\\Desktop\\LUXDEEP";
        const sessionId = payload.session_id || "default";
        const result = await runLuxCodeAgent({
            prompt,
            workspace_root: workspaceRoot,
            session_id: sessionId,
        }, {
            timeoutMs: options.timeoutMs || 90000,
            controller: options.controller,
        });
        const assistantText = result.response
            || result.message
            || result.output
            || result.content
            || (result.ok === false ? "Agent yanıt üretemedi." : "İşlem tamamlandı.");
        return {
            ok: result.ok !== false,
            route: "agent",
            response: assistantText,
            agent: result,
            session: {
                session_id: sessionId,
                active_task_id: result.task_id || "",
                active_task_state: result.task || null,
                message_history: [
                    {
                        id: payload.client_message_id || `client-${Date.now()}`,
                        role: "user",
                        content: prompt,
                        meta: { status: "sent" },
                    },
                    {
                        id: payload.assistant_message_id || `asst-${Date.now()}`,
                        role: "assistant",
                        content: assistantText,
                        meta: { route: "agent", ok: result.ok !== false },
                    },
                ],
            },
        };
    }

    function inspectWorkspace(payload, options = {}) {
        return requestJson("/luxcode-workspace/inspect", {
            method: "POST",
            body: JSON.stringify(payload || {}),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 20000,
            controller: options.controller,
        });
    }

    function selectWorkspaceFolder(payload = {}, options = {}) {
        return requestJson("/luxcode-workspace/select-folder", {
            method: "POST",
            body: JSON.stringify(payload || {}),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 120000,
            controller: options.controller,
        });
    }

    function runWorkspaceCommand(payload, options = {}) {
        return requestJson("/luxcode-workspace/run-command", {
            method: "POST",
            body: JSON.stringify(payload || {}),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 120000,
            controller: options.controller,
        });
    }

    function commitWorkspace(payload, options = {}) {
        return requestJson("/luxcode-workspace/commit", {
            method: "POST",
            body: JSON.stringify(payload || {}),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 120000,
            controller: options.controller,
        });
    }

    async function requestLuxCodeAgentStream(payload, options = {}) {
        const controller = options.controller || new AbortController();
        const timeoutMs = Number(options.timeoutMs || 90000);
        const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);

        let response;
        try {
            const finalPayload = { ...payload, stream: true };
            response = await fetch(`${backendBaseUrl()}/luxcode-agent/run`, {
                method: "POST",
                body: JSON.stringify(finalPayload),
                headers: {
                    Accept: "text/event-stream",
                    "Content-Type": "application/json",
                },
                signal: controller.signal,
            });
            if (!response.ok) {
                throw { normalized: true, message: `HTTP ${response.status}`, status: response.status };
            }
            if (!response.body) {
                throw { normalized: true, message: "Sunucu response body bulunamadi", code: "missing_response_body" };
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let result = null;
            const onEvent = typeof options.onEvent === "function" ? options.onEvent : null;
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop();
                for (const line of lines) {
                    const trimmed = String(line || "").trim();
                    if (!trimmed.startsWith("data:")) {
                        continue;
                    }
                    const raw = trimmed.replace(/^data:\s*/, "");
                    if (!raw) {
                        continue;
                    }
                    let event;
                    try {
                        event = JSON.parse(raw);
                    } catch (error) {
                        continue;
                    }
                    if (onEvent) onEvent(event);
                    if (event.type === "done" && event.result) {
                        result = event.result;
                    }
                }
            }
            if (!result) {
                throw { normalized: true, message: "Akış tamamlanamadı", code: "agent_stream_incomplete" };
            }
            return result;
        } catch (error) {
            throw normalizeApiError(error);
        } finally {
            window.clearTimeout(timeoutId);
        }
    }

    window.LuxCodeApi = {
        createLuxCodeTask,
        getLuxCodeTask,
        advanceLuxCodeTask,
        inspectWorkspace,
        selectWorkspaceFolder,
        runWorkspaceCommand,
        commitWorkspace,
        runLuxCodeAgent,
        sendConversationMessage,
        normalizeApiError,
    };
})();
