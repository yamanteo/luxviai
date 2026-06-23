(function () {
    "use strict";

    const SESSION_KEY = "luxcode_live_session_id";
    const TERMINAL_STATES = new Set(["completed", "failed", "blocked", "cancelled"]);
    const renderedMessages = new Set();
    const processedEventIds = new Set();
    const urlSessionId = new URLSearchParams(window.location.search).get("session_id") || "";
    const createSessionId = () => `lux-live-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const state = {
        sessionId: urlSessionId || createSessionId(),
        explicitSession: Boolean(urlSessionId),
        eventSource: null,
        lastSession: null,
        submitting: false,
        pendingMessages: [],
        eventsBound: false,
        isTerminalOpen: false,
        terminalHeight: 220,
        scrollDrag: null,
        taskCardCollapsed: false,
        attachments: [],
        streamingMessages: new Map(),
    };
    if (state.explicitSession) localStorage.setItem(SESSION_KEY, state.sessionId);
    else localStorage.removeItem(SESSION_KEY);

    const byId = id => document.getElementById(id);
    function normalizeDisplayContent(value) {
        if (typeof value === "string") return value;
        if (value == null) return "";
        if (typeof value.content === "string") return value.content;
        if (typeof value.message === "string") return value.message;
        if (typeof value.text === "string") return value.text;
        try {
            return JSON.stringify(value, null, 2);
        } catch (_) {
            return "";
        }
    }
    const text = value => normalizeDisplayContent(value);
    const terminalStatus = value => TERMINAL_STATES.has(text(value).toLowerCase());

    function backendBaseUrl() {
        const configured = window.LUXCODE_BACKEND_BASE_URL || "";
        return String(configured).replace(/\/+$/, "");
    }

    function normalizeApiError(error) {
        if (!error) return { message: "Bilinmeyen backend hatasi", code: "unknown_error" };
        if (error.name === "AbortError") return { message: "Backend istegi zaman asimina ugradi", code: "request_timeout" };
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
        const timeoutMs = Number(options.timeoutMs || 15000);
        const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs);
        const headers = { Accept: "application/json", ...(options.headers || {}) };
        let response;
        let bodyText = "";
        try {
            response = await fetch(`${backendBaseUrl()}${path}`, {
                method: options.method || "GET",
                body: options.body,
                headers,
                signal: controller.signal,
            });
            bodyText = await response.text();
        } catch (error) {
            throw normalizeApiError(error);
        } finally {
            window.clearTimeout(timeoutId);
        }
        let payload = {};
        try {
            payload = bodyText ? JSON.parse(bodyText) : {};
        } catch (error) {
            throw { normalized: true, message: "Backend gecersiz JSON yaniti dondurdu", code: "invalid_json", status: response.status, detail: bodyText.slice(0, 300) };
        }
        if (!response.ok) {
            throw { normalized: true, message: payload.detail || payload.reason || payload.error || `HTTP ${response.status}`, code: response.status >= 500 ? "server_error" : "client_error", status: response.status, detail: payload };
        }
        return payload;
    }

    const fallbackApi = {
        getConversationState: (sessionId, options = {}) => requestJson(`/luxcode-conversation/${encodeURIComponent(sessionId || "default")}`, options),
        sendConversationMessage: (payload, options = {}) => requestJson("/luxcode-conversation/message", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 90000,
            controller: options.controller,
        }),
        sendConversationAction: (payload, options = {}) => requestJson("/luxcode-conversation/action", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 30000,
            controller: options.controller,
        }),
        createArtifact: (payload, options = {}) => requestJson("/luxcode-artifacts", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 30000,
            controller: options.controller,
        }),
        listConversationArtifacts: (sessionId, options = {}) => requestJson(`/luxcode-conversation/${encodeURIComponent(sessionId || "default")}/artifacts`, options),
        createAttachment: (payload, options = {}) => requestJson("/luxcode-attachments", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 60000,
            controller: options.controller,
        }),
        inspectWorkspace: (payload, options = {}) => requestJson("/luxcode-workspace/inspect", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 20000,
            controller: options.controller,
        }),
        selectWorkspaceFolder: (payload = {}, options = {}) => requestJson("/luxcode-workspace/select-folder", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 120000,
            controller: options.controller,
        }),
        runWorkspaceCommand: (payload, options = {}) => requestJson("/luxcode-workspace/run-command", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 120000,
            controller: options.controller,
        }),
        commitWorkspace: (payload, options = {}) => requestJson("/luxcode-workspace/commit", {
            method: "POST",
            body: JSON.stringify(payload),
            headers: { "Content-Type": "application/json" },
            timeoutMs: options.timeoutMs || 120000,
            controller: options.controller,
        }),
        conversationEventUrl: sessionId => `${backendBaseUrl()}/luxcode-conversation/${encodeURIComponent(sessionId || "default")}/events`,
        normalizeApiError,
    };
    const api = { ...fallbackApi, ...(window.LuxCodeApi || {}) };
    window.LuxCodeApi = api;

    function escapeHtml(value) {
        return text(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function highlightCode(code, language) {
        let safe = escapeHtml(code);
        const lang = text(language).toLowerCase();
        const stash = [];
        const keep = (value, cls) => {
            const key = `\uE000${String.fromCharCode(0xE100 + stash.length)}\uE001`;
            stash.push(`<span class="${cls}">${value}</span>`);
            return key;
        };
        safe = safe.replace(/(&lt;!--[\s\S]*?--&gt;|\/\*[\s\S]*?\*\/|(^|\s)(\/\/|#).*?$)/gm, match => keep(match, "tok-comment"));
        safe = safe.replace(/(&quot;.*?&quot;|&#39;.*?&#39;|`[\s\S]*?`)/g, match => keep(match, "tok-string"));
        if (/(html|xml)/.test(lang)) {
            safe = safe.replace(/(&lt;\/?)([A-Za-z][\w:-]*)([\s\S]*?)(\/?&gt;)/g, (_, open, tag, attrs, close) => {
                const markedAttrs = attrs.replace(/\s([A-Za-z_:][\w:.-]*)(=)/g, ' <span class="tok-attribute">$1</span><span class="tok-operator">$2</span>');
                return `<span class="tok-punctuation">${open}</span><span class="tok-tag">${tag}</span>${markedAttrs}<span class="tok-punctuation">${close}</span>`;
            });
        } else if (/(css|scss|sass)/.test(lang)) {
            safe = safe.replace(/(^|[{};])([^{}\n;]+)(?=\s*\{)/g, (_, lead, selector) => `${lead}<span class="tok-selector">${selector}</span>`);
            safe = safe.replace(/([A-Za-z-]+)(\s*:)([^;{}\n]+)(;?)/g, (_, prop, sep, value, end) => `<span class="tok-property">${prop}</span><span class="tok-operator">${sep}</span><span class="tok-value">${value}</span><span class="tok-punctuation">${end}</span>`);
        } else if (/(bash|powershell|shell|ps1)/.test(lang)) {
            safe = safe.replace(/(\$[A-Za-z_][\w:]*|--?[\w-]+|\b(?:Get-[A-Za-z]+|Set-[A-Za-z]+|New-[A-Za-z]+|Remove-[A-Za-z]+|Write-[A-Za-z]+|Start-[A-Za-z]+|Stop-[A-Za-z]+|git|python|npm|node|cd|dir|ls|curl|echo)\b|\b\d+(?:\.\d+)?\b)/g, token => {
                if (/^\$/.test(token)) return `<span class="tok-env">${token}</span>`;
                if (/^--?/.test(token)) return `<span class="tok-flag">${token}</span>`;
                if (/^\d/.test(token)) return `<span class="tok-number">${token}</span>`;
                return `<span class="tok-command">${token}</span>`;
            });
        } else if (/(json|yaml|yml)/.test(lang)) {
            safe = safe.replace(/(&quot;[^&]*?&quot;)(\s*:)/g, '<span class="tok-property">$1</span><span class="tok-operator">$2</span>');
            safe = safe.replace(/\b(true|false|null)\b/g, '<span class="tok-boolean">$1</span>');
            safe = safe.replace(/\b-?\d+(?:\.\d+)?\b/g, '<span class="tok-number">$&</span>');
        } else if (/sql/.test(lang)) {
            safe = safe.replace(/\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TABLE|ORDER|GROUP|BY|HAVING|LIMIT|OFFSET|VALUES|SET|AND|OR|NOT|NULL|TRUE|FALSE)\b/gi, '<span class="tok-keyword">$1</span>');
            safe = safe.replace(/\b\d+(?:\.\d+)?\b/g, '<span class="tok-number">$&</span>');
        } else {
            safe = safe.replace(/\b(function|const|let|var|return|if|else|elif|for|while|class|def|import|from|async|await|try|except|catch|finally|with|as|yield|new|switch|case|break|continue|interface|type|enum|public|private|protected|static|extends|implements|this|self|in|is|lambda|true|false|True|False|null|None|undefined|\d+(?:\.\d+)?|[A-Z][A-Za-z_][\w$]*|[A-Za-z_][\w$]*(?=\s*\())\b/g, token => {
                if (/^(true|false|True|False)$/.test(token)) return `<span class="tok-boolean">${token}</span>`;
                if (/^(null|None|undefined)$/.test(token)) return `<span class="tok-null">${token}</span>`;
                if (/^\d/.test(token)) return `<span class="tok-number">${token}</span>`;
                if (/^[A-Z]/.test(token)) return `<span class="tok-class">${token}</span>`;
                if (/^[A-Za-z_][\w$]*$/.test(token) && !/^(function|const|let|var|return|if|else|elif|for|while|class|def|import|from|async|await|try|except|catch|finally|with|as|yield|new|switch|case|break|continue|interface|type|enum|public|private|protected|static|extends|implements|this|self|in|is|lambda)$/.test(token)) return `<span class="tok-function">${token}</span>`;
                return `<span class="tok-keyword">${token}</span>`;
            });
            safe = safe.replace(/(\.)([A-Za-z_][\w$]*)/g, '<span class="tok-punctuation">$1</span><span class="tok-property">$2</span>');
        }
        return safe.replace(/\uE000([\uE100-\uEFFF])\uE001/g, (_, key) => stash[key.charCodeAt(0) - 0xE100] || "");
    }

    function inlineMarkdown(value) {
        return escapeHtml(value)
            .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
            .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
    }

    function extensionForLanguage(language) {
        const lang = text(language).toLowerCase();
        return ({
            html: "html",
            css: "css",
            javascript: "js",
            js: "js",
            typescript: "ts",
            ts: "ts",
            python: "py",
            py: "py",
            powershell: "ps1",
            ps1: "ps1",
            bash: "sh",
            shell: "sh",
            json: "json",
            yaml: "yaml",
            yml: "yml",
            sql: "sql",
            markdown: "md",
            md: "md",
            xml: "xml",
        })[lang] || "txt";
    }

    function normalizeCodeLanguage(info) {
        const first = text(info).trim().split(/\s+/)[0] || "text";
        return ({
            js: "javascript",
            ts: "typescript",
            py: "python",
            ps1: "powershell",
            sh: "bash",
            yml: "yaml",
            md: "markdown",
        })[first.toLowerCase()] || first.toLowerCase();
    }

    function filenameFromCodeInfo(info, index, language) {
        const parts = text(info).trim().split(/\s+/).filter(Boolean);
        const named = parts.find(part => /[\\/.\w-]+\.[A-Za-z0-9]+$/.test(part));
        return named || `luxcode-snippet-${index + 1}.${extensionForLanguage(language)}`;
    }

    function splitCodeForCards(code) {
        const clean = text(code);
        const lines = clean.split(/\n/);
        if (clean.length <= 180000 && lines.length <= 3000) return [clean];
        const chunkSize = 1200;
        const chunks = [];
        for (let index = 0; index < lines.length; index += chunkSize) {
            chunks.push(lines.slice(index, index + chunkSize).join("\n"));
        }
        return chunks;
    }

    function codeCardHtml(code, info, blockIndex) {
        const language = normalizeCodeLanguage(info);
        const filename = filenameFromCodeInfo(info, blockIndex, language);
        const chunks = splitCodeForCards(code);
        const group = `code-group-${blockIndex}`;
        return chunks.map((chunk, partIndex) => {
            const total = chunks.length;
            const label = total > 1 ? `LUXCODE ${partIndex + 1}/${total}` : "LUXCODE";
            return (
                `<div class="code-card code-block" data-code-index="${blockIndex}-${partIndex}" data-code-group="${escapeHtml(group)}" data-code-part="${partIndex + 1}" data-filename="${escapeHtml(filename)}">`
                + `<div class="code-card-header code-block-header">`
                + `<span class="code-title"><strong>${label}</strong><span> — ${escapeHtml(filename)} ? ${escapeHtml(language.toUpperCase())}</span></span>`
                + `<div class="code-actions"><button class="copy-code-button" type="button" data-copy-code>Kopyala</button><button class="copy-code-button" type="button" data-copy-all-code="${escapeHtml(group)}">Tümünü Kopyala</button><button class="save-code-button" type="button" data-save-code>Dosya olarak kaydet</button><button class="copy-code-button" type="button" data-toggle-code>Daralt</button></div>`
                + `</div>`
                + `<pre><code>${highlightCode(chunk, language)}</code></pre>`
                + `</div>`
            );
        }).join("");
    }

    function renderMarkdown(markdown) {
        const blocks = [];
        const source = text(markdown).replace(/\r\n?/g, "\n");
        const outputLines = [];
        const lines = source.split("\n");
        for (let index = 0; index < lines.length; index += 1) {
            const fence = lines[index].match(/^\s*```(.*)$/);
            if (!fence) {
                outputLines.push(lines[index]);
                continue;
            }
            const info = fence[1] || "";
            const codeLines = [];
            index += 1;
            while (index < lines.length && !/^\s*```\s*$/.test(lines[index])) {
                codeLines.push(lines[index]);
                index += 1;
            }
            const blockIndex = blocks.length;
            blocks.push(codeCardHtml(codeLines.join("\n"), info, blockIndex));
            outputLines.push(`@@CODE_BLOCK_${blockIndex}@@`);
        }
        const protectedSource = outputLines.join("\n");
        const html = [];
        let listType = "";
        const closeList = () => {
            if (listType) html.push(`</${listType}>`);
            listType = "";
        };
        for (const line of protectedSource.split(/\n/)) {
            const trimmed = line.trim();
            const block = trimmed.match(/^@@CODE_BLOCK_(\d+)@@$/);
            if (block) {
                closeList();
                html.push(blocks[Number(block[1])] || "");
            } else if (/^#{1,3}\s+/.test(trimmed)) {
                closeList();
                const level = Math.min(3, trimmed.match(/^#+/)[0].length);
                html.push(`<h${level}>${inlineMarkdown(trimmed.replace(/^#{1,3}\s+/, ""))}</h${level}>`);
            } else if (/^[-*]\s+/.test(trimmed)) {
                if (listType !== "ul") {
                    closeList();
                    listType = "ul";
                    html.push("<ul>");
                }
                html.push(`<li>${inlineMarkdown(trimmed.replace(/^[-*]\s+/, ""))}</li>`);
            } else if (/^\d+\.\s+/.test(trimmed)) {
                if (listType !== "ol") {
                    closeList();
                    listType = "ol";
                    html.push("<ol>");
                }
                html.push(`<li>${inlineMarkdown(trimmed.replace(/^\d+\.\s+/, ""))}</li>`);
            } else if (trimmed) {
                closeList();
                html.push(`<p>${inlineMarkdown(trimmed)}</p>`);
            } else {
                closeList();
            }
        }
        closeList();
        return html.join("");
    }

    function ensureStream() {
        let stream = byId("conversationStream");
        if (stream) return stream;
        stream = document.createElement("div");
        stream.id = "conversationStream";
        stream.className = "conversation-stream";
        byId("activeTaskView")?.insertBefore(stream, byId("activeTaskView").firstChild);
        return stream;
    }

    function enterConversation() {
        byId("landingView") && (byId("landingView").style.display = "none");
        byId("activeTaskView") && (byId("activeTaskView").style.display = "flex");
        byId("dockedInputContainer") && (byId("dockedInputContainer").style.display = "flex");
    }

    function focusComposer() {
        const docked = byId("txtDockedInput");
        const dockedVisible = docked && docked.offsetParent !== null;
        const input = dockedVisible ? docked : byId("txtLandingInput");
        if (!input) return;
        input.disabled = false;
        input.readOnly = false;
        window.setTimeout(() => input.focus({ preventScroll: true }), 0);
    }

    function isNearBottom() {
        const area = byId("contentArea");
        if (!area) return true;
        return area.scrollHeight - area.scrollTop - area.clientHeight < 100;
    }

    function scrollToBottom() {
        const area = byId("contentArea");
        if (!area) return;
        window.requestAnimationFrame(() => {
            area.scrollTo({ top: area.scrollHeight });
            updateScrollIndicator();
        });
    }

    function setMessageStatus(messageId, status, label) {
        const bubble = document.querySelector(`[data-message-id="${CSS.escape(String(messageId))}"]`);
        const node = bubble?.querySelector(".message-status");
        if (!node) return;
        node.textContent = label || "";
        node.classList.toggle("error", status === "error");
        bubble.dataset.status = status || "";
    }

    function appendBubble(role, content, messageId, meta = {}) {
        const clean = text(content).trim();
        if (!clean || !messageId) return;
        const id = String(messageId);
        if (renderedMessages.has(id)) {
            if (meta.status) setMessageStatus(id, meta.status, meta.status === "sending" ? "Gönderiliyor..." : "");
            return;
        }
        const shouldStick = role === "user" || isNearBottom();
        renderedMessages.add(id);
        enterConversation();
        const rendered = role === "user" ? "" : renderMarkdown(clean);
        const bubble = document.createElement("div");
        bubble.className = role === "user" ? "chat-bubble chat-user live-message" : "chat-bubble chat-lux live-message";
        if (rendered.includes("code-card")) bubble.classList.add("has-code");
        bubble.dataset.messageId = id;
        bubble.dataset.status = meta.status || "";
        if (role === "user") bubble.textContent = clean;
        else bubble.innerHTML = rendered;
        if (role === "user") {
            const status = document.createElement("div");
            status.className = "message-status";
            status.textContent = meta.status === "sending" ? "Gönderiliyor..." : "";
            bubble.appendChild(status);
        }
        ensureStream().appendChild(bubble);
        if (shouldStick) scrollToBottom();
        else updateScrollIndicator();
    }

    function renderMessages(session) {
        const messages = Array.isArray(session?.message_history) ? session.message_history : [];
        messages.forEach(message => appendBubble(message.role, message.content, message.id, message.meta || {}));
    }

    function clearMessageStream() {
        const stream = ensureStream();
        stream.innerHTML = "";
        renderedMessages.clear();
        processedEventIds.clear();
        state.streamingMessages.clear();
    }

    function ensureAssistantStream(messageId, placeholder = "Luxcode...") {
        const id = String(messageId || "assistant-stream");
        let bubble = document.querySelector(`[data-message-id="${CSS.escape(id)}"]`);
        if (!bubble) {
            renderedMessages.add(id);
            enterConversation();
            bubble = document.createElement("div");
            bubble.className = "chat-bubble chat-lux live-message";
            bubble.dataset.messageId = id;
            bubble.dataset.status = "streaming";
            bubble.dataset.rawContent = "";
            bubble.innerHTML = `<span class="assistant-thinking">${escapeHtml(placeholder)}</span>`;
            ensureStream().appendChild(bubble);
            scrollToBottom();
        }
        state.streamingMessages.set(id, bubble);
        return bubble;
    }

    function appendAssistantDelta(messageId, delta) {
        const bubble = ensureAssistantStream(messageId);
        const raw = (bubble.dataset.rawContent || "") + text(delta);
        bubble.dataset.rawContent = raw;
        bubble.innerHTML = renderMarkdown(raw);
        bubble.classList.toggle("has-code", bubble.innerHTML.includes("code-card"));
        if (isNearBottom()) scrollToBottom();
        else updateScrollIndicator();
    }

    function completeAssistantStream(messageId, content) {
        const bubble = ensureAssistantStream(messageId, "");
        const finalText = text(content || bubble.dataset.rawContent || "");
        bubble.dataset.rawContent = finalText;
        bubble.dataset.status = "complete";
        bubble.innerHTML = renderMarkdown(finalText);
        bubble.classList.toggle("has-code", bubble.innerHTML.includes("code-card"));
        state.streamingMessages.delete(String(messageId));
        if (isNearBottom()) scrollToBottom();
    }

    function isRightPanelOpen() {
        const panel = byId("rightPanel");
        return Boolean(panel && getComputedStyle(panel).display === "flex");
    }

    function renderActiveTaskCard(task) {
        const card = byId("activeTaskPanelCard");
        if (!card) return;
        const hasTask = Boolean(task?.task_id);
        const completed = Array.isArray(task?.completed_steps) ? task.completed_steps : [];
        const pending = Array.isArray(task?.pending_steps) ? task.pending_steps : [];
        const progress = typeof progressFromTask === "function" ? progressFromTask(task) : 0;
        card.classList.toggle("open", hasTask && !state.taskCardCollapsed);
        const indicator = byId("taskCompactIndicator");
        if (indicator) {
            indicator.style.display = "none";
            indicator.textContent = "";
        }
        if (!hasTask) return;
        byId("activeTaskCommand") && (byId("activeTaskCommand").textContent = task.original_request || "—");
        byId("activeTaskStatus") && (byId("activeTaskStatus").textContent = `${task.current_state || task.status || "—"} ? %${progress}`);
        const steps = [
            ...completed.map(item => `âœ“ ${item}`),
            ...pending.slice(0, 6).map(item => `â€¢ ${item}`),
        ];
        byId("activeTaskProgress") && (byId("activeTaskProgress").textContent = steps.length ? steps.join("\n") : "Henüz aşama bilgisi yok.");
    }

    async function refreshArtifactPanel() {
        const host = byId("fileTreeEmptyState");
        if (!host) return;
        try {
            const result = await api.listConversationArtifacts(state.sessionId);
            const artifacts = Array.isArray(result.artifacts) ? result.artifacts : [];
            if (!artifacts.length) return;
            host.innerHTML = artifacts.map(item => {
                const status = item.complete ? "Doğruland?" : item.validation_status === "failed" ? "Hatalı" : "Eksik";
                return `<div class="panel-card artifact-card" data-artifact-id="${escapeHtml(item.artifact_id)}"><strong>${escapeHtml(item.filename)}</strong><span>${escapeHtml(item.language)} ? ${item.line_count || 0} satır ? ${formatBytes(item.size_bytes)} ? ${escapeHtml(status)}</span><div class="code-actions"><button type="button" data-copy-artifact="${escapeHtml(item.artifact_id)}">Kopyala</button><button type="button" data-preview-artifact="${escapeHtml(item.artifact_id)}">Ã–nizle</button><a href="/luxcode-artifacts/${encodeURIComponent(item.artifact_id)}/download" target="_blank">İndir</a></div></div>`;
            }).join("");
        } catch (_) {}
    }

    function updateTaskPanels(task) {
        if (!task) return;
        const changed = Array.isArray(task.changed_files) ? task.changed_files : [];
        const selected = Array.isArray(task.selected_files) ? task.selected_files : [];
        const evidence = Array.isArray(task.evidence) ? task.evidence : [];
        const completed = Array.isArray(task.completed_steps) ? task.completed_steps : [];
        const pending = Array.isArray(task.pending_steps) ? task.pending_steps : [];
        const progress = typeof progressFromTask === "function" ? progressFromTask(task) : 0;

        byId("reviewFileCount") && (byId("reviewFileCount").textContent = String(changed.length || selected.length || "—"));
        byId("reviewAdditions") && (byId("reviewAdditions").textContent = text(task.patch_summary?.additions || "—"));
        byId("reviewDeletions") && (byId("reviewDeletions").textContent = text(task.patch_summary?.deletions || "—"));
        byId("metricProgress") && (byId("metricProgress").textContent = `%${progress}`);
        byId("metricDone") && (byId("metricDone").textContent = String(completed.length || "—"));
        byId("metricRemaining") && (byId("metricRemaining").textContent = String(pending.length || "—"));
        byId("metricTokens") && (byId("metricTokens").textContent = task.token_usage || "—");
        byId("metricCost") && (byId("metricCost").textContent = task.provider_cost || "—");
        renderActiveTaskCard(task);

        const fileEmpty = byId("fileTreeEmptyState");
        if (fileEmpty) {
            fileEmpty.innerHTML = selected.length || changed.length
                ? `<strong>Görev dosyaları</strong><span>${[...new Set([...selected, ...changed])].map(escapeHtml).join("<br>")}</span>`
                : "<strong>Bu görev için henüz veri yok.</strong>";
        }
        const testEmpty = byId("testEmptyState");
        if (testEmpty) {
            const verification = task.verification_summary || {};
            testEmpty.innerHTML = Object.keys(verification).length
                ? `<strong>Doğrulama</strong><span>${escapeHtml(JSON.stringify(verification).slice(0, 500))}</span>`
                : "<strong>Bu görev için henüz veri yok.</strong>";
        }
        const evidenceHost = document.querySelector(".evidence-timeline");
        if (evidenceHost) {
            evidenceHost.innerHTML = evidence.length
                ? evidence.slice(-8).map(item => `<div class="evidence-item"><strong>${escapeHtml(item.kind || item.evidence_id || "Kanıt")}</strong><span>${escapeHtml(item.summary || item.failure_fingerprint || JSON.stringify(item)).slice(0, 220)}</span></div>`).join("")
                : '<div class="panel-empty-state"><strong>Bu görev için henüz veri yok.</strong></div>';
        }
        const log = byId("dockedTerminalLog");
        if (log) {
            const follow = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
            const status = task.current_state || task.status || "unknown";
            log.innerHTML += `<br>$ luxcode task ${escapeHtml(task.task_id || "")}<br>Durum: ${escapeHtml(status)}<br>`;
            if (follow) log.scrollTo({ top: log.scrollHeight });
        }
    }

    function ensureScrollIndicator() {
        let indicator = byId("luxConversationScrollIndicator");
        if (indicator) return indicator;
        indicator = document.createElement("div");
        indicator.id = "luxConversationScrollIndicator";
        indicator.className = "lux-scroll-indicator";
        byId("contentArea")?.appendChild(indicator);
        return indicator;
    }

    function scrollIndicatorLeft() {
        const panel = byId("rightPanel");
        const area = byId("contentArea");
        const panelRect = panel?.getBoundingClientRect();
        const areaRect = area?.getBoundingClientRect();
        if (isRightPanelOpen() && panelRect) return panelRect.left - 12;
        return (areaRect?.right || window.innerWidth) - 10;
    }

    function scrollMetrics() {
        const area = byId("contentArea");
        const trackTop = 72;
        const trackHeight = Math.max(40, (area?.clientHeight || window.innerHeight) - 150);
        return { area, trackTop, trackHeight, thumbHeight: 19 };
    }

    function updateScrollIndicator() {
        const { area, trackTop, trackHeight, thumbHeight } = scrollMetrics();
        const indicator = ensureScrollIndicator();
        if (!area || !indicator) return;
        const maxScroll = Math.max(0, area.scrollHeight - area.clientHeight);
        if (!maxScroll) {
            indicator.style.opacity = "0";
            return;
        }
        const ratio = Math.min(1, Math.max(0, area.scrollTop / maxScroll));
        indicator.style.opacity = "1";
        indicator.style.left = `${Math.round(scrollIndicatorLeft())}px`;
        indicator.style.transform = `translateY(${Math.round(trackTop + ratio * (trackHeight - thumbHeight))}px)`;
    }

    function renderSession(session) {
        state.lastSession = session;
        clearMessageStream();
        renderMessages(session);
        const task = session?.active_task_state;
        if (task && task.task_id) {
            window.LuxCodeTaskState?.setCurrentTask(task);
            if (!terminalStatus(task.current_state || task.status)) {
                window.LuxCodeTaskState?.startTaskPolling(task.task_id);
            }
            updateTaskPanels(task);
        }
        focusComposer();
    }

    function acceptsTaskUpdate(task) {
        const taskId = text(task?.task_id || task?.id);
        if (!taskId) return false;
        return taskId === text(state.lastSession?.active_task_id)
            || taskId === text(state.lastSession?.active_task_state?.task_id || state.lastSession?.active_task_state?.id);
    }

    async function restore() {
        if (!state.explicitSession) return;
        try {
            const restored = await api.getConversationState(state.sessionId, { timeoutMs: 8000 });
            if (restored?.session) renderSession(restored.session);
        } catch (error) {
            console.warn("LuxCode conversation restore failed", error);
        }
    }

    function startEvents() {
        if (!window.LUXCODE_ENABLE_LEGACY_SSE) return;
        if (!window.EventSource || state.eventSource) return;
        state.eventSource = new EventSource(api.conversationEventUrl(state.sessionId));
        state.eventSource.addEventListener("luxcode", event => {
            try {
                const payload = JSON.parse(event.data);
                if (payload.id && processedEventIds.has(payload.id)) return;
                if (payload.id) processedEventIds.add(payload.id);
                const log = byId("dockedTerminalLog");
                if (log) {
                    const follow = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
                    log.innerHTML += `<br>event: ${escapeHtml(payload.type)}`;
                    if (follow) log.scrollTo({ top: log.scrollHeight });
                }
                if (payload.type === "user_message_accepted" && payload.payload?.client_message_id) {
                    setMessageStatus(payload.payload.client_message_id, "sent", "");
                }
                if (payload.type === "assistant_started") {
                    ensureAssistantStream(payload.payload?.message_id, payload.payload?.text);
                }
                if (payload.type === "assistant_delta") {
                    appendAssistantDelta(payload.payload?.message_id, payload.payload?.delta);
                }
                if (payload.type === "assistant_completed") {
                    completeAssistantStream(payload.payload?.message_id, payload.payload?.content);
                    if (Array.isArray(payload.payload?.artifacts) && payload.payload.artifacts.length) refreshArtifactPanel();
                }
                if (payload.type === "error" && payload.payload?.message_id) {
                    completeAssistantStream(payload.payload.message_id, payload.payload.message || "İşlem tamamlanamadı.");
                }
                if (payload.payload?.task) updateTaskPanels(payload.payload.task);
                focusComposer();
            } catch (_) {}
        });
        state.eventSource.onerror = () => {
            state.eventSource?.close();
            state.eventSource = null;
            setTimeout(startEvents, 2500);
        };
    }

    function closeEvents() {
        if (!state.eventSource) return;
        state.eventSource.close();
        state.eventSource = null;
    }

    function resetConversationSurface() {
        clearMessageStream();
        state.lastSession = null;
        state.pendingMessages = [];
        state.submitting = false;
        clearAttachments();
        window.LuxCodeTaskState?.resetTaskState?.();
        byId("txtLandingInput") && (byId("txtLandingInput").value = "");
        byId("txtDockedInput") && (byId("txtDockedInput").value = "");
        byId("userTaskText") && (byId("userTaskText").textContent = "");
        byId("taskStatusDetails") && (byId("taskStatusDetails").textContent = "");
        byId("taskStatusMeta") && (byId("taskStatusMeta").textContent = "");
        byId("taskErrorText") && (byId("taskErrorText").textContent = "");
        byId("taskCompactIndicator") && (byId("taskCompactIndicator").textContent = "");
        byId("activeTaskCommand") && (byId("activeTaskCommand").textContent = "Henüz görev yok.");
        byId("activeTaskState") && (byId("activeTaskState").textContent = "-");
        byId("activeTaskProgress") && (byId("activeTaskProgress").textContent = "");
        byId("activeTaskPanelCard")?.classList.remove("open");
        byId("landingView") && (byId("landingView").style.display = "");
        byId("activeTaskView") && (byId("activeTaskView").style.display = "none");
        byId("dockedInputContainer") && (byId("dockedInputContainer").style.display = "none");
        if (typeof window.setTaskState === "function") window.setTaskState("home");
        byId("landingView") && (byId("landingView").style.display = "flex");
        byId("activeTaskView") && (byId("activeTaskView").style.display = "none");
        byId("dockedInputContainer") && (byId("dockedInputContainer").style.display = "none");
        focusComposer();
    }

    function startNewConversation() {
        closeEvents();
        state.sessionId = createSessionId();
        state.explicitSession = false;
        localStorage.removeItem(SESSION_KEY);
        sessionStorage.removeItem(SESSION_KEY);
        resetConversationSurface();
        startEvents();
        refreshArtifactPanel();
    }

    function formatBytes(size) {
        const value = Number(size || 0);
        if (value > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
        if (value > 1024) return `${(value / 1024).toFixed(1)} KB`;
        return `${value} B`;
    }

    async function sha256Hex(dataUrl) {
        if (!window.crypto?.subtle) return "";
        const data = new TextEncoder().encode(dataUrl);
        const hash = await crypto.subtle.digest("SHA-256", data);
        return Array.from(new Uint8Array(hash)).map(byte => byte.toString(16).padStart(2, "0")).join("");
    }

    function fileToDataUrl(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(String(reader.result || ""));
            reader.onerror = () => reject(reader.error || new Error("file_read_failed"));
            reader.readAsDataURL(file);
        });
    }

    function ensureAttachmentUi() {
        let input = byId("luxAttachmentInput");
        if (!input) {
            input = document.createElement("input");
            input.id = "luxAttachmentInput";
            input.type = "file";
            input.multiple = true;
            input.accept = ".png,.jpg,.jpeg,.webp,.gif,.pdf,.txt,.md,.json,.html,.css,.js,.ts,.py,.zip,image/png,image/jpeg,image/webp,image/gif,application/pdf,text/*,application/json";
            input.style.display = "none";
            document.body.appendChild(input);
        }
        document.querySelectorAll(".omnibox").forEach(box => {
            if (!box.querySelector(".attachment-tray")) {
                const tray = document.createElement("div");
                tray.className = "attachment-tray";
                box.insertBefore(tray, box.firstChild);
            }
        });
        return input;
    }

    function renderAttachments() {
        document.querySelectorAll(".attachment-tray").forEach(tray => {
            tray.innerHTML = state.attachments.map(item => {
                const preview = item.mime_type.startsWith("image/") ? `<img src="${escapeHtml(item.data_url)}" alt="">` : "";
                return `<div class="attachment-chip" data-attachment-id="${escapeHtml(item.attachment_id)}">${preview}<span>${escapeHtml(item.filename)} ? ${formatBytes(item.size_bytes)} ? ${escapeHtml(item.status || "hazır")}</span><button type="button" data-remove-attachment="${escapeHtml(item.attachment_id)}">Ã—</button></div>`;
            }).join("");
        });
    }

    function clearAttachments() {
        state.attachments = [];
        renderAttachments();
    }

    async function addFiles(files) {
        const accepted = Array.from(files || []);
        for (const file of accepted) {
            if (file.size > 15 * 1024 * 1024) {
                showToast?.(`${file.name} dosyası çok büyük`);
                continue;
            }
            const dataUrl = await fileToDataUrl(file);
            const pending = {
                attachment_id: `att-${Date.now()}-${Math.random().toString(16).slice(2)}`,
                filename: file.name || "pasted-image.png",
                mime_type: file.type || "application/octet-stream",
                size_bytes: file.size || 0,
                data_url: dataUrl,
                sha256: await sha256Hex(dataUrl),
                status: "yükleniyor",
            };
            state.attachments.push(pending);
            renderAttachments();
            try {
                const saved = await api.createAttachment({
                    session_id: state.sessionId,
                    filename: pending.filename,
                    mime_type: pending.mime_type,
                    data_url: pending.data_url,
                    attachment_id: pending.attachment_id,
                });
                Object.assign(pending, saved.attachment, { data_url: pending.data_url, status: "hazır" });
            } catch (error) {
                pending.status = "hatalı";
                pending.error = api.normalizeApiError(error).message;
                showToast?.(pending.error);
            }
        }
        renderAttachments();
    }

    async function submitFromInput(inputId) {
        const input = byId(inputId);
        const value = input?.value.trim() || "";
        if (state.submitting) {
            if (value) {
                state.pendingMessages.push(value);
                input.value = "";
                focusComposer();
            }
            return;
        }
        if (!value) {
            showToast?.("Önce bir mesaj yazın");
            input?.focus();
            return;
        }
        state.submitting = true;
        setSubmitBusy?.(true);
        const clientMessageId = `client-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const assistantMessageId = `asst-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const attachments = state.attachments.map(item => ({
            attachment_id: item.attachment_id,
            filename: item.filename,
            mime_type: item.mime_type,
            size_bytes: item.size_bytes,
            sha256: item.sha256 || "",
            status: item.status || "hazır",
        }));
        const attachmentIds = attachments.filter(item => item.status !== "hatalı").map(item => item.attachment_id);
        appendBubble("user", value, clientMessageId, { status: "sending" });
        clearAttachments();
        input.value = "";
        focusComposer();
        ensureAssistantStream(assistantMessageId, "Luxcode...");
        scrollToBottom();
        try {
            const selectedProject = window.LuxCodeSidebar?.getSelectedProject?.() || null;
            const result = await api.sendConversationMessage({
                session_id: state.sessionId,
                message: value,
                mode: "auto",
                client_message_id: clientMessageId,
                assistant_message_id: assistantMessageId,
                attachments,
                attachment_ids: attachmentIds,
                project_name: selectedProject?.name || "",
                project_path: selectedProject?.path || "",
                repository_root: selectedProject?.path || "",
            });
            setMessageStatus(clientMessageId, "sent", "");
            if (result.session) renderSession(result.session);
            if (result.task?.task_id) {
                window.LuxCodeTaskState?.setCurrentTask(result.task);
                updateTaskPanels(result.task);
                window.LuxCodeTaskState?.startTaskPolling(result.task.task_id);
                window.LuxCodeTaskState?.startAutoAdvance(result.task.task_id);
            }
            if (result.error) showToast?.(result.error.message || "İşlem başarısız");
        } catch (error) {
            const normalized = api.normalizeApiError(error);
            setMessageStatus(clientMessageId, "error", "Gönderilemedi — Tekrar dene");
            completeAssistantStream(assistantMessageId, normalized.message);
            showToast?.(normalized.message);
            scrollToBottom();
        } finally {
            state.submitting = false;
            setSubmitBusy?.(false);
            focusComposer();
            const nextMessage = state.pendingMessages.shift();
            if (nextMessage) {
                const nextInput = byId("txtDockedInput") || byId("txtLandingInput");
                nextInput.value = nextMessage;
                submitFromInput(nextInput.id);
            }
        }
    }

    async function sendAction(action) {
        const taskId = window.LuxCodeTaskState?.state?.currentTaskId || state.lastSession?.active_task_id || "";
        try {
            const result = await api.sendConversationAction({
                session_id: state.sessionId,
                task_id: taskId,
                action,
            });
            if (result.session) renderSession(result.session);
            if (result.task) updateTaskPanels(result.task);
        } catch (error) {
            showToast?.(api.normalizeApiError(error).message);
        }
    }

    function ensureTerminalInWorkspace() {
        const tray = byId("dockedTerminalTray");
        const workspace = document.querySelector(".workspace-container");
        if (tray && workspace && tray.parentElement !== workspace) workspace.appendChild(tray);
    }

    function setTerminalHeight(height) {
        const next = Math.max(180, Math.min(460, Number(height) || state.terminalHeight));
        state.terminalHeight = next;
        byId("dockedTerminalTray") && (byId("dockedTerminalTray").style.height = `${next}px`);
        document.documentElement.style.setProperty("--terminal-height", state.isTerminalOpen ? `${next}px` : "0px");
        updateScrollIndicator();
    }

    function setTerminalOpen(open) {
        ensureTerminalInWorkspace();
        state.isTerminalOpen = Boolean(open);
        setTerminalHeight(state.terminalHeight);
        byId("dockedTerminalTray") && (byId("dockedTerminalTray").style.display = state.isTerminalOpen ? "block" : "none");
        document.documentElement.style.setProperty("--terminal-height", state.isTerminalOpen ? `${state.terminalHeight}px` : "0px");
        byId("btnTerminalToggle")?.classList.toggle("active", state.isTerminalOpen);
        scrollToBottom();
        focusComposer();
    }

    function toggleTerminal() {
        setTerminalOpen(!state.isTerminalOpen);
    }

    function switchPanelTab(tabName) {
        const target = String(tabName || "integrations");
        document.querySelectorAll(".panel-tab").forEach(button => button.classList.toggle("active", button.dataset.panelTab === target));
        document.querySelectorAll(".panel-view").forEach(view => view.classList.toggle("active", view.dataset.panelView === target));
        const titles = window.LuxCodePanelTitles || {};
        byId("panelTitle") && (byId("panelTitle").textContent = titles[target] || "Modeller");
        if (["review", "files", "tests", "evidence", "environment", "integrations"].includes(target)) {
            window.LuxCodeWorkspace?.refresh?.(`panel_${target}`);
        }
    }

    function openRightPanel(tabName = "integrations") {
        byId("rightPanel") && (byId("rightPanel").style.display = "flex");
        byId("btnRightPanelToggle")?.classList.add("active");
        switchPanelTab(tabName);
        if (state.lastSession?.active_task_state) renderActiveTaskCard(state.lastSession.active_task_state);
        updateScrollIndicator();
    }

    function closeRightPanel() {
        byId("rightPanel") && (byId("rightPanel").style.display = "none");
        byId("btnRightPanelToggle")?.classList.remove("active");
        if (state.lastSession?.active_task_state) renderActiveTaskCard(state.lastSession.active_task_state);
        updateScrollIndicator();
    }

    function toggleRightPanel() {
        if (isRightPanelOpen()) closeRightPanel();
        else openRightPanel("integrations");
    }

    function bindUiEvents() {
        if (state.eventsBound) return;
        state.eventsBound = true;

        byId("btnSubmitTask")?.removeAttribute("onclick");
        byId("btnTerminalToggle")?.removeAttribute("onclick");
        byId("btnRightPanelToggle")?.removeAttribute("onclick");
        document.querySelector(".btn-new-chat")?.removeAttribute("onclick");

        byId("btnSubmitTask")?.addEventListener("click", event => { event.preventDefault(); submitFromInput("txtLandingInput"); });
        document.querySelector(".btn-new-chat")?.addEventListener("click", event => { event.preventDefault(); startNewConversation(); });
        document.querySelector("#dockedInputContainer .btn-submit")?.addEventListener("click", event => { event.preventDefault(); submitFromInput("txtDockedInput"); });
        byId("btnTerminalToggle")?.addEventListener("click", event => { event.preventDefault(); toggleTerminal(); });
        document.querySelector(".terminal-close-btn")?.addEventListener("click", event => { event.preventDefault(); setTerminalOpen(false); });
        byId("btnRightPanelToggle")?.addEventListener("click", event => { event.preventDefault(); toggleRightPanel(); });
        document.querySelector(".panel-tabs")?.addEventListener("click", event => {
            const button = event.target.closest(".panel-tab");
            if (!button) return;
            event.preventDefault();
            openRightPanel(button.dataset.panelTab);
        });
        byId("contentArea")?.addEventListener("scroll", updateScrollIndicator, { passive: true });
        byId("txtLandingInput")?.addEventListener("keydown", event => {
            if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitFromInput("txtLandingInput"); }
        });
        byId("txtDockedInput")?.addEventListener("keydown", event => {
            if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submitFromInput("txtDockedInput"); }
        });
        const attachmentInput = ensureAttachmentUi();
        attachmentInput.addEventListener("change", event => {
            document.documentElement.dataset.luxcodeAttachmentChange = String(event.target.files?.length || 0);
            addFiles(event.target.files);
            event.target.value = "";
        });
        document.addEventListener("click", event => {
            if (event.target.closest?.(".attachment-button")) {
                event.preventDefault();
                document.documentElement.dataset.luxcodeAttachmentClick = String(Date.now());
                attachmentInput.click();
            }
            const menuTrigger = event.target.closest?.("[data-omnibox-menu-trigger]");
            if (menuTrigger) {
                event.preventDefault();
                const group = menuTrigger.closest(".control-group-left");
                const menuName = menuTrigger.dataset.omniboxMenuTrigger;
                const targetMenu = group?.querySelector(`[data-omnibox-menu="${CSS.escape(menuName)}"]`);
                document.querySelectorAll(".omnibox-menu.open").forEach(menu => {
                    if (menu !== targetMenu) menu.classList.remove("open");
                });
                targetMenu?.classList.toggle("open");
            }
            const choice = event.target.closest?.("[data-omnibox-choice]");
            if (choice) {
                event.preventDefault();
                const group = choice.closest(".control-group-left");
                const kind = choice.dataset.omniboxChoice;
                const value = choice.dataset.value || choice.textContent.trim();
                document.querySelectorAll(`[data-control-label="${CSS.escape(kind)}"]`).forEach(label => {
                    label.textContent = value;
                });
                group?.querySelectorAll(".omnibox-menu.open").forEach(menu => menu.classList.remove("open"));
                focusComposer();
            }
            const removeId = event.target.closest?.("[data-remove-attachment]")?.dataset.removeAttachment;
            if (removeId) {
                state.attachments = state.attachments.filter(item => item.attachment_id !== removeId);
                renderAttachments();
            }
        });
        document.addEventListener("click", event => {
            if (event.target.closest?.(".control-group-left")) return;
            document.querySelectorAll(".omnibox-menu.open").forEach(menu => menu.classList.remove("open"));
        });
        document.addEventListener("paste", event => {
            const files = Array.from(event.clipboardData?.files || []);
            if (files.length) addFiles(files);
        });
        document.addEventListener("dragover", event => {
            if (Array.from(event.dataTransfer?.items || []).some(item => item.kind === "file")) event.preventDefault();
        });
        document.addEventListener("drop", event => {
            const files = Array.from(event.dataTransfer?.files || []);
            if (!files.length) return;
            event.preventDefault();
            addFiles(files);
        });

        const thumb = ensureScrollIndicator();
        thumb.addEventListener("pointerdown", event => {
            const { area, trackTop, trackHeight, thumbHeight } = scrollMetrics();
            if (!area) return;
            event.preventDefault();
            thumb.setPointerCapture?.(event.pointerId);
            thumb.classList.add("dragging");
            state.scrollDrag = {
                startY: event.clientY,
                startTop: trackTop + (area.scrollTop / Math.max(1, area.scrollHeight - area.clientHeight)) * (trackHeight - thumbHeight),
            };
        });
        document.addEventListener("pointermove", event => {
            if (!state.scrollDrag) return;
            const { area, trackTop, trackHeight, thumbHeight } = scrollMetrics();
            if (!area) return;
            const travel = Math.max(1, trackHeight - thumbHeight);
            const top = Math.max(trackTop, Math.min(trackTop + travel, state.scrollDrag.startTop + event.clientY - state.scrollDrag.startY));
            area.scrollTo({ top: ((top - trackTop) / travel) * Math.max(0, area.scrollHeight - area.clientHeight) });
            updateScrollIndicator();
        });
        document.addEventListener("pointerup", () => {
            if (!state.scrollDrag) return;
            thumb.classList.remove("dragging");
            state.scrollDrag = null;
        });
        byId("terminalResizer")?.addEventListener("pointerdown", event => {
            event.preventDefault();
            event.currentTarget.setPointerCapture?.(event.pointerId);
            const startY = event.clientY;
            const startHeight = state.terminalHeight;
            const move = moveEvent => {
                const maxHeight = Math.floor(window.innerHeight * 0.65);
                const next = Math.max(180, Math.min(maxHeight, startHeight - (moveEvent.clientY - startY)));
                setTerminalHeight(next);
                localStorage.setItem("luxcode_terminal_height", String(next));
            };
            const up = () => {
                document.removeEventListener("pointermove", move);
                document.removeEventListener("pointerup", up);
            };
            document.addEventListener("pointermove", move);
            document.addEventListener("pointerup", up);
        });

        byId("taskCompactIndicator")?.addEventListener("click", event => { event.preventDefault(); openRightPanel("review"); });
        byId("btnCollapseTaskCard")?.addEventListener("click", event => {
            event.preventDefault();
            state.taskCardCollapsed = !state.taskCardCollapsed;
            byId("activeTaskPanelCard")?.classList.toggle("open", !state.taskCardCollapsed);
            event.currentTarget.textContent = state.taskCardCollapsed ? "Göster" : "Daralt";
        });
        document.addEventListener("click", event => {
            const button = event.target.closest("[data-copy-code]");
            if (!button) return;
            const code = button.closest(".code-block")?.querySelector("code")?.textContent || "";
            document.documentElement.dataset.luxcodeLastCopiedCode = code;
            navigator.clipboard?.writeText(code).catch(() => {});
            button.textContent = "Kopyaland?";
            window.setTimeout(() => { button.textContent = "Kopyala"; }, 1200);
        });
        document.addEventListener("click", async event => {
            const button = event.target.closest("[data-copy-all-code]");
            if (!button) return;
            const group = button.dataset.copyAllCode || "";
            const cards = Array.from(document.querySelectorAll(`.code-block[data-code-group="${CSS.escape(group)}"]`))
                .sort((a, b) => Number(a.dataset.codePart || 0) - Number(b.dataset.codePart || 0));
            const code = cards.map(card => card.querySelector("code")?.textContent || "").join("\n");
            document.documentElement.dataset.luxcodeLastCopiedAllCode = code;
            await navigator.clipboard?.writeText(code).catch(() => {});
            button.textContent = "Tümü kopyalandı";
            window.setTimeout(() => { button.textContent = "Tümünü Kopyala"; }, 1400);
        });
        document.addEventListener("click", event => {
            const button = event.target.closest("[data-toggle-code]");
            if (!button) return;
            const card = button.closest(".code-block");
            card?.classList.toggle("collapsed");
            button.textContent = card?.classList.contains("collapsed") ? "A?" : "Daralt";
        });
        document.addEventListener("click", async event => {
            const button = event.target.closest("[data-save-code]");
            if (!button) return;
            const card = button.closest(".code-block");
            const code = card?.querySelector("code")?.textContent || "";
            const filename = card?.dataset.filename || "luxcode-snippet.txt";
            button.textContent = "Doğrulan?yor";
            try {
                const created = await api.createArtifact({
                    filename,
                    language: card?.querySelector(".code-language")?.textContent || "",
                    content: code,
                    session_id: state.sessionId,
                    message_id: card?.closest("[data-message-id]")?.dataset.messageId || "",
                    complete: true,
                });
                const artifact = created.artifact;
                card.dataset.artifactId = artifact.artifact_id;
                button.textContent = artifact.complete ? "Kaydedildi" : "Hatalı";
                if (artifact.complete) {
                    refreshArtifactPanel();
                    window.open(`/luxcode-artifacts/${encodeURIComponent(artifact.artifact_id)}/download`, "_blank");
                } else {
                    showToast?.("Artifact doğrulamas? ge?medi");
                }
            } catch (error) {
                button.textContent = "Hatalı";
                showToast?.(api.normalizeApiError(error).message);
            }
            window.setTimeout(() => { button.textContent = "Dosya olarak kaydet"; }, 1400);
        });
        document.addEventListener("click", async event => {
            const copyId = event.target.closest?.("[data-copy-artifact]")?.dataset.copyArtifact;
            const previewId = event.target.closest?.("[data-preview-artifact]")?.dataset.previewArtifact;
            const artifactId = copyId || previewId;
            if (!artifactId) return;
            try {
                const response = await fetch(`/luxcode-artifacts/${encodeURIComponent(artifactId)}/content`);
                const content = await response.text();
                if (copyId) {
                    await navigator.clipboard?.writeText(content);
                    event.target.textContent = "Kopyaland?";
                } else {
                    const win = window.open("", "_blank");
                    if (win) {
                        win.document.write(`<pre style="white-space:pre-wrap;background:#050505;color:#e0e0e0;padding:16px">${escapeHtml(content)}</pre>`);
                        win.document.close();
                    }
                }
            } catch (error) {
                showToast?.(api.normalizeApiError(error).message);
            }
        });
        document.addEventListener("mousemove", updateScrollIndicator);
        window.addEventListener("resize", updateScrollIndicator);
    }

    const controllerActions = {
        submitLanding: () => submitFromInput("txtLandingInput"),
        submitDocked: () => submitFromInput("txtDockedInput"),
        newConversation: () => startNewConversation(),
        approve: () => sendAction("approve"),
        reject: () => sendAction("reject"),
        cancel: () => sendAction("cancel"),
        updateScrollIndicator,
    };
    window.LuxCodeConversationController = controllerActions;
    window.resetToHome = startNewConversation;

    window.addEventListener("luxcode:task-update", event => {
        if (acceptsTaskUpdate(event.detail?.task)) updateTaskPanels(event.detail?.task);
    });
    window.addEventListener("luxcode:task-terminal", event => {
        if (acceptsTaskUpdate(event.detail?.task)) updateTaskPanels(event.detail?.task);
    });
    function boot() {
        bindUiEvents();
        ensureTerminalInWorkspace();
        state.terminalHeight = Math.max(180, Number(localStorage.getItem("luxcode_terminal_height")) || state.terminalHeight);
        setTerminalOpen(false);
        restore();
        refreshArtifactPanel();
        startEvents();
        updateScrollIndicator();
        document.documentElement.dataset.luxcodeControllerReady = "1";
    }
    if (document.readyState === "complete") boot();
    else window.addEventListener("load", boot);
})();
