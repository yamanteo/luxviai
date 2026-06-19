from __future__ import annotations

import threading
import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk, messagebox
from typing import Any

from luxcode_desktop.api.client import LuxCodeApiClient
from luxcode_desktop.api.schemas import TaskSubmitPayload
from luxcode_desktop.config import (
    CENTER_TABS,
    DEFAULT_BACKEND_URL,
    DEFAULT_MAIN_REPOSITORY,
    LEFT_TABS,
    RIGHT_TABS,
    LayoutConfig,
    load_layout,
    save_layout,
)
from luxcode_desktop.services.backend_process_service import BackendProcessService
from luxcode_desktop.services.backend_connection_service import backend_readiness
from luxcode_desktop.services.polling_service import PollingService
from luxcode_desktop.services.ui_dispatcher import UiDispatcher
from luxcode_desktop.state import TaskState


BG = "#0b0f14"
PANEL = "#111821"
PANEL_2 = "#17212d"
INPUT_BG = "#050505"
LINE = "#263241"
TEXT = "#f3efe6"
MUTED = "#9aa4b2"
ACCENT = "#c5812f"
OK = "#72b783"
DANGER = "#d36b5b"
BUILD_LABEL = os.getenv("LUXCODE_DESKTOP_BUILD", "Güncel UI 2026-06-18 input görünür")


CONTROL_ACTIONS = {
    "status": ("GET", "/luxcode-control/status", "right_Durum"),
    "diagnostics": ("POST", "/luxcode-control/repository/diagnostics", "right_Durum"),
    "search": ("POST", "/luxcode-control/search", "workspace_detail"),
    "context": ("POST", "/luxcode-control/context", "workspace_detail"),
    "task_plan": ("POST", "/luxcode-control/task-plan", "task_plan_detail"),
    "safe_patch": ("POST", "/luxcode-control/safe-patch/preview", "safe_patch_detail"),
    "apply_prepare": ("POST", "/luxcode-control/controlled-apply/prepare", "right_Entegrasyon"),
    "validation": ("POST", "/luxcode-control/validation/run", "validation_detail"),
    "approvals": ("GET", "/luxcode-control/approvals", "right_İzinler"),
    "deferred": ("GET", "/luxcode-control/deferred-queue", "right_Durum"),
    "deferred_resume": ("POST", "/luxcode-control/deferred-queue/resume", "right_Durum"),
    "evidence": ("GET", "/luxcode-control/evidence-board", "right_Kanıt"),
    "motors": ("GET", "/luxcode-control/motor-status", "right_Durum"),
    "settings": ("GET", "/luxcode-control/settings", "readiness"),
}


def split_lines(value: str) -> list[str]:
    return [item.strip() for item in value.replace(",", "\n").splitlines() if item.strip()]


def normalize_access_label(value: str) -> str:
    mapping = {
        "Sınırlı Erişim": "limited",
        "Kontrollü Erişim": "controlled",
        "Tam Erişim": "full",
    }
    return mapping.get(value, "controlled")


class LuxCodeDesktopApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.layout = load_layout()
        self.root.title(f"LuxCode Desktop - {BUILD_LABEL}")
        self.root.geometry(self.layout.window_geometry)
        self.root.minsize(1280, 760)
        self.root.configure(bg=BG)

        self.client = LuxCodeApiClient(DEFAULT_BACKEND_URL)
        self.backend_process = BackendProcessService(self.client)
        self.dispatcher = UiDispatcher(root)
        self.dispatcher.pump()
        self.polling = PollingService(
            self.client,
            lambda state: self.dispatcher.post(lambda: self.apply_task_state(state)),
            lambda error: self.dispatcher.post(lambda: self.log_diagnostic("ERROR", error)),
        )

        self.active_state = TaskState(main_repository_root=str(DEFAULT_MAIN_REPOSITORY))
        self.left_hidden = not self.layout.left_visible
        self.right_hidden = not self.layout.right_visible
        self.left_pane: ttk.Frame | None = None
        self.center_pane: ttk.Frame | None = None
        self.right_pane: ttk.Frame | None = None

        self.status_vars: dict[str, tk.StringVar] = {}
        self.text_widgets: dict[str, tk.Text] = {}
        self.tree_widgets: dict[str, ttk.Treeview] = {}
        self.engine_slots: list[dict[str, Any]] = []
        self.attachments: list[dict[str, str]] = []
        self.attachment_keys: set[tuple[str, str]] = set()
        self.attachment_buttons: list[tk.Button] = []
        self.pending_chat_messages: list[tuple[str, bool]] = []
        self.chat_sending = False
        self.task_running = False
        self.task_action_in_progress = False
        self._last_announced_task_marker = ""

        self.repo_root_var = tk.StringVar(value=str(DEFAULT_MAIN_REPOSITORY))
        self.working_copy_var = tk.StringVar(value="")
        self.sandbox_root_var = tk.StringVar(value="")
        self.workspace_mode_var = tk.StringVar(value="Sandbox Copy")
        self.access_level_var = tk.StringVar(value="Kontrollü Erişim")
        self.execution_mode_var = tk.StringVar(value="automatic")
        self.pilot_mode_var = tk.BooleanVar(value=True)
        self.local_worker_var = tk.BooleanVar(value=True)
        self.auto_apply_var = tk.BooleanVar(value=False)

        self._configure_style()
        self._build_ui()
        self.ensure_backend_ready()
        self._refresh_file_tree()

    def _configure_style(self) -> None:
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=PANEL, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_2, foreground=TEXT, padding=(10, 5))
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", "#101010")])
        style.configure("TFrame", background=PANEL)
        style.configure("Treeview", background="#0d131b", foreground=TEXT, fieldbackground="#0d131b", borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=TEXT)

    def _dark_scrollbar(self, parent: tk.Misc) -> tk.Scrollbar:
        return tk.Scrollbar(
            parent,
            bg=BG,
            troughcolor=BG,
            activebackground="#202832",
            highlightthickness=0,
            borderwidth=0,
            elementborderwidth=0,
            width=6,
        )

    def _create_rounded_rect(self, canvas: tk.Canvas, radius: int, **kwargs: Any) -> int:
        width = int(canvas.cget("width"))
        height = int(canvas.cget("height"))
        points = [
            radius, 0,
            width - radius, 0,
            width, 0,
            width, radius,
            width, height - radius,
            width, height,
            width - radius, height,
            radius, height,
            0, height,
            0, height - radius,
            0, radius,
            0, 0,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    def _resize_input_shell(self, _event: tk.Event[Any] | None = None) -> None:
        if not hasattr(self, "input_shell"):
            return
        width = max(1, self.input_shell.winfo_width())
        height = max(1, self.input_shell.winfo_height())
        radius = min(30, height // 2)
        points = [
            radius, 0,
            width - radius, 0,
            width, 0,
            width, radius,
            width, height - radius,
            width, height,
            width - radius, height,
            radius, height,
            0, height,
            0, height - radius,
            0, radius,
            0, 0,
        ]
        self.input_shell.coords(self.input_shell_shape, *points)
        self.input_shell.coords(self.input_shell_window, 14, 8)
        self.input_shell.itemconfigure(self.input_shell_window, width=max(1, width - 28), height=max(1, height - 32))
        if hasattr(self, "input_plus_item"):
            self.input_shell.coords(self.input_plus_item, 38, height - 22)
            self.input_shell.coords(self.input_plus_hitbox, 20, height - 40, 56, height - 4)

    def _canvas_send_action(self, _event: tk.Event[Any] | None = None) -> None:
        self._primary_task_action()

    def _canvas_add_action(self, _event: tk.Event[Any] | None = None) -> None:
        self._add_file_attachment()

    def _enter_send_action(self, event: tk.Event[Any]) -> str | None:
        if event.state & 0x0001:
            return None
        self._primary_task_action()
        return "break"

    def _build_ui(self) -> None:
        self._build_header()
        self._build_task_input()
        self._build_body()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg="#0f1720", height=58)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=f"LuxCode Desktop  |  {BUILD_LABEL}", bg="#0f1720", fg=ACCENT, font=("Segoe UI", 16, "bold")).pack(side="left", padx=18)

        actions = tk.Frame(header, bg="#0f1720")
        actions.pack(side="right", padx=12)
        for label, command in [
            ("Sol Panel", self.toggle_left_panel),
            ("Sağ Panel", self.toggle_right_panel),
            ("Düzeni Sıfırla", self.reset_layout),
        ]:
            tk.Button(actions, text=label, command=command, bg=PANEL_2, fg=TEXT, relief="flat", padx=10, pady=6).pack(side="left", padx=4)

        stats = tk.Frame(header, bg="#0f1720")
        stats.pack(side="right", padx=12)
        for key, initial in [
            ("Durum", "idle"),
            ("Aktif Motor", "-"),
            ("Aktif Model", "-"),
            ("İlerleme", "0%"),
            ("Yapıldı", "0"),
            ("Kaldı", "0"),
            ("Tasarruf", "unavailable"),
            ("Token", "unavailable"),
            ("Maliyet", "unavailable"),
            ("Alan", "Sandbox Copy"),
            ("Test", "not_started"),
        ]:
            var = tk.StringVar(value=initial)
            self.status_vars[key] = var
            tk.Label(stats, text=f"{key}:", bg="#0f1720", fg=MUTED, font=("Segoe UI", 8)).pack(side="left", padx=(7, 2))
            tk.Label(stats, textvariable=var, bg="#0f1720", fg=TEXT, font=("Segoe UI", 8, "bold")).pack(side="left")

        tk.Frame(self.root, bg=ACCENT, height=1).pack(side="top", fill="x")

    def _build_body(self) -> None:
        self.body = ttk.Panedwindow(self.root, orient="horizontal")
        self.body.pack(fill="both", expand=True, padx=10, pady=10)

        self.left_pane = ttk.Frame(self.body, width=self.layout.left_width)
        self.center_pane = ttk.Frame(self.body, width=780)
        self.right_pane = ttk.Frame(self.body, width=self.layout.right_width)

        if not self.left_hidden:
            self.body.add(self.left_pane, weight=0)
        self.body.add(self.center_pane, weight=1)
        if not self.right_hidden:
            self.body.add(self.right_pane, weight=0)

        self._build_left_panel(self.left_pane)
        self._build_center_panel(self.center_pane)
        self._build_right_panel(self.right_pane)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        self.left_notebook = notebook
        for tab in LEFT_TABS:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=tab)
            if tab == "Dosyalar":
                self._build_files_tab(frame)
            elif tab == "Modeller":
                self._build_models_tab(frame)
            elif tab == "Görevler":
                self._build_tasks_tab(frame)
            else:
                self._build_workspace_tab_left(frame)

    def _build_center_panel(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        self.center_notebook = notebook
        for tab in CENTER_TABS:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=tab)
            builder = {
                "Çalışma": self._build_center_workspace,
                "Yapılan/Kalan": self._build_done_remaining_tab,
                "Araçlar": self._build_tools_tab,
                "Plan": self._build_center_task_plan,
                "Ayarlar": self._build_repository_settings,
                "Yama": self._build_center_safe_patch,
                "Test": self._build_center_validation,
                "Geçmiş": self._build_history,
            }[tab]
            builder(frame)

    def send_chat_message(self) -> None:
        source = getattr(self, "chat_input", self.task_input)
        message = source.get("1.0", "end").strip()
        if not message:
            return
        source.delete("1.0", "end")
        self._append_chat("Sen", message)
        self._send_chat_response(message, directed=False)

    def _send_chat_response(self, message: str, directed: bool) -> None:
        if self.chat_sending:
            self.pending_chat_messages.append((message, directed))
            label = "Yönlendirilmiş mesaj sıraya alındı." if directed else "Mesaj sıraya alındı."
            self._append_chat("Sistem", label)
            return
        self.chat_sending = True
        if hasattr(self, "chat_send_button"):
            self.chat_send_button.configure(text="■", state="disabled")
        self._append_chat("Sistem", "Yönlendirilmiş mesaj iş kesilmeden iletiliyor." if directed else "Sohbet yanıtı hazırlanıyor.")
        self._append_chat("LUXVIAI", "Yanıt hazırlanıyor...")
        outgoing = f"Aktif LUXCODE görevi sürerken yönlendirilmiş kullanıcı mesajı: {message}" if directed else message

        def worker() -> None:
            try:
                response = self.client.chat(outgoing)
                answer = str(response.get("response") or "Sohbet motoru yanıt üretemedi.")
            except Exception as exc:
                answer = "Sohbet backend'i hazır değil. Arka planda başlatmayı deniyorum; birkaç saniye sonra tekrar yazabilirsin."
                self.dispatcher.post(self.ensure_backend_ready)
            self.dispatcher.post(lambda: self._finish_chat_message(answer))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_chat_message(self, answer: str) -> None:
        self._replace_last_chat_line("LUXVIAI", answer)
        self.chat_sending = False
        if hasattr(self, "chat_send_button"):
            self.chat_send_button.configure(text="↑", state="normal")
        if self.pending_chat_messages:
            message, directed = self.pending_chat_messages.pop(0)
            self._send_chat_response(message, directed)

    def _append_chat(self, speaker: str, text: str) -> None:
        if not hasattr(self, "chat_history"):
            return
        self.chat_history.configure(state="normal")
        self.chat_history.insert("end", f"{speaker}: {text}\n\n")
        self.chat_history.see("end")
        self.chat_history.configure(state="disabled")

    def _replace_last_chat_line(self, speaker: str, text: str) -> None:
        if not hasattr(self, "chat_history"):
            return
        self.chat_history.configure(state="normal")
        content = self.chat_history.get("1.0", "end")
        placeholder = f"{speaker}: Yanıt hazırlanıyor...\n\n"
        replacement = f"{speaker}: {text}\n\n"
        if content.endswith(placeholder):
            start = f"end-{len(placeholder) + 1}c"
            self.chat_history.delete(start, "end")
            self.chat_history.insert("end", replacement)
        else:
            self.chat_history.insert("end", replacement)
        self.chat_history.see("end")
        self.chat_history.configure(state="disabled")

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        self.right_notebook = notebook
        for tab in RIGHT_TABS:
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=tab)
            self._build_right_summary_tab(frame, tab)

    def _build_task_input(self) -> None:
        bottom = tk.Frame(self.root, bg="#0f1720", height=122)
        bottom.pack(side="bottom", fill="x")
        bottom.pack_propagate(False)
        tk.Frame(self.root, bg=ACCENT, height=1).pack(side="bottom", fill="x")

        input_area = tk.Frame(bottom, bg="#0f1720")
        input_area.pack(side="bottom", pady=16)

        access_panel = tk.Frame(input_area, bg="#0f1720")
        access_panel.pack(side="left", padx=(0, 14), pady=36)
        tk.Label(access_panel, text="Erişim", bg="#0f1720", fg=ACCENT, font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))
        access = ttk.Combobox(
            access_panel,
            textvariable=self.access_level_var,
            values=("Sınırlı Erişim", "Kontrollü Erişim", "Tam Erişim"),
            state="readonly",
            width=13,
        )
        access.pack(side="left")

        self.input_shell = tk.Canvas(input_area, bg="#0f1720", highlightthickness=0, width=760, height=98)
        self.input_shell.pack(side="left")
        self.input_shell_shape = self._create_rounded_rect(self.input_shell, 30, fill=INPUT_BG, outline="#2b2b2b", width=1)
        self.input_content = tk.Frame(self.input_shell, bg=INPUT_BG)
        self.input_shell_window = self.input_shell.create_window(14, 8, anchor="nw", window=self.input_content, width=732, height=66)
        self.input_shell.bind("<Configure>", self._resize_input_shell)

        input_frame = tk.Frame(self.input_content, bg=INPUT_BG)
        input_frame.pack(side="top", fill="both", expand=True, padx=10, pady=(8, 0))
        input_scroll = self._dark_scrollbar(input_frame)
        input_scroll.pack(side="right", fill="y")
        self.task_input = tk.Text(input_frame, height=3, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", yscrollcommand=input_scroll.set)
        self.task_input.pack(side="left", fill="both", expand=True)
        input_scroll.configure(command=self.task_input.yview)
        self.task_input.bind("<Return>", self._enter_send_action)
        self._attach_text_menu(self.task_input)

        self.input_plus_item = self.input_shell.create_text(38, 76, text="+", fill=MUTED, font=("Segoe UI", 20))
        self.input_plus_hitbox = self.input_shell.create_oval(20, 58, 56, 94, outline="", fill="")
        self.input_shell.tag_bind(self.input_plus_item, "<Button-1>", self._canvas_add_action)
        self.input_shell.tag_bind(self.input_plus_hitbox, "<Button-1>", self._canvas_add_action)
        self.attachment_status_var = tk.StringVar(value="Ek yok")

        self.primary_task_button = tk.Button(
            input_area,
            text="↑",
            command=self._primary_task_action,
            bg=ACCENT,
            fg="#050505",
            relief="flat",
            font=("Segoe UI", 20, "bold"),
            width=3,
            height=1,
        )
        self.primary_task_button.pack(side="left", padx=(14, 8), pady=32)
        tk.Button(
            input_area,
            text="🎙",
            command=lambda: self.log_diagnostic("INFO", "mikrofon henüz bağlanmadı"),
            bg="#0f1720",
            fg=MUTED,
            relief="flat",
            font=("Segoe UI", 14),
            width=2,
        ).pack(side="left", padx=(14, 0), pady=36)

    def _build_files_tab(self, parent: ttk.Frame) -> None:
        tree = ttk.Treeview(parent, columns=("state",), show="tree headings")
        tree.heading("#0", text="Repo Dosyaları")
        tree.heading("state", text="Durum")
        tree.column("state", width=70, stretch=False)
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree_widgets["files"] = tree
        self._text_block(parent, "İzinli Dosyalar", "Görev payloadundan güncellenir.")
        self._text_block(parent, "Şüpheli Dosyalar", "Görev payloadundan güncellenir.")

    def _build_models_tab(self, parent: ttk.Frame) -> None:
        tree = ttk.Treeview(parent, columns=("readiness", "mode", "real"), show="headings", height=10)
        for col, title in [("readiness", "Hazır"), ("mode", "Mod"), ("real", "Gerçek")]:
            tree.heading(col, text=title)
        tree.pack(fill="x", padx=6, pady=6)
        self.tree_widgets["models"] = tree
        self._refresh_models_tree()

    def _build_tasks_tab(self, parent: ttk.Frame) -> None:
        tree = ttk.Treeview(parent, columns=("status", "engine"), show="tree headings")
        tree.heading("#0", text="Görev / Session")
        tree.heading("status", text="Durum")
        tree.heading("engine", text="Motor")
        tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree_widgets["tasks"] = tree

    def _build_workspace_tab_left(self, parent: ttk.Frame) -> None:
        self._key_values(parent, [
            ("Ana Repo", self.repo_root_var),
            ("Çalışma Kopyası", self.working_copy_var),
            ("Sandbox", self.sandbox_root_var),
            ("Aktif Mod", self.workspace_mode_var),
            ("Sync", tk.StringVar(value="unknown")),
            ("Dirty", tk.StringVar(value="unknown")),
            ("Conflict", tk.StringVar(value="none")),
        ])

    def _build_center_workspace(self, parent: ttk.Frame) -> None:
        self._build_conversation_stream(parent)

    def _build_conversation_stream(self, parent: tk.Misc) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=8, pady=8)

        chat_frame = tk.Frame(frame, bg=PANEL)
        chat_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        scroll = self._dark_scrollbar(chat_frame)
        scroll.pack(side="right", fill="y")
        self.chat_history = tk.Text(
            chat_frame,
            bg="#0d131b",
            fg=TEXT,
            relief="flat",
            wrap="word",
            state="disabled",
            yscrollcommand=scroll.set,
        )
        self.chat_history.pack(fill="both", expand=True)
        scroll.configure(command=self.chat_history.yview)
        self._attach_text_menu(self.chat_history)
        self._append_chat("Sistem", "Tek giriş hazır: sohbet yazabilir veya kod görevi isteyebilirsin.")

    def _build_done_remaining_tab(self, parent: ttk.Frame) -> None:
        wrapper = tk.Frame(parent, bg=PANEL)
        wrapper.pack(fill="both", expand=True, padx=8, pady=8)
        left = tk.Frame(wrapper, bg=PANEL)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = tk.Frame(wrapper, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        self._summary_card(left, "Yapılıp Biten", "completed_summary", "Henüz tamamlanan iş yok.", height=18)
        self._summary_card(right, "Kalan İşler", "remaining_summary", "Görev bekleniyor.", height=18)

    def _summary_card(self, parent: tk.Misc, title: str, key: str, text: str, height: int) -> None:
        card = tk.Frame(parent, bg="#151f2a", highlightbackground=LINE, highlightthickness=1)
        card.pack(fill="x", pady=(0, 8))
        tk.Label(card, text=title, bg="#151f2a", fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(7, 2))
        box = tk.Text(card, height=height, bg="#151f2a", fg=TEXT, relief="flat", wrap="word")
        box.pack(fill="x", padx=8, pady=(0, 8))
        box.insert("1.0", text)
        box.configure(state="disabled")
        self.text_widgets[key] = box
        self._attach_text_menu(box)

    def _build_tools_tab(self, parent: ttk.Frame) -> None:
        self._section(parent, "Araçlar", "Durum, arama, context, onay, deferred queue ve kanıt işlemleri burada toplandı.")
        self._build_control_action_bar(parent)
        self._large_text(parent, "workspace_detail", "Araç çıktıları burada görünür.\nBackend yoksa: BACKEND CONNECTION REQUIRED")

    def _build_center_task_plan(self, parent: ttk.Frame) -> None:
        self._large_text(parent, "task_plan_detail", "Work unit listesi, dependency sırası ve handoff ayrıntıları.")

    def _build_repository_settings(self, parent: ttk.Frame) -> None:
        form = tk.Frame(parent, bg=PANEL)
        form.pack(fill="x", padx=8, pady=8)
        for label, var in [
            ("Ana Repo Kökü", self.repo_root_var),
            ("Çalışma Kopyası", self.working_copy_var),
            ("Sandbox Root", self.sandbox_root_var),
            ("Aktif Workspace Modu", self.workspace_mode_var),
            ("Erişim Seviyesi", self.access_level_var),
        ]:
            self._form_row(form, label, var)
        self.allowed_files = self._labeled_text(parent, "İzinli Dosyalar")
        self.suspected_files = self._labeled_text(parent, "Şüpheli Dosyalar")
        self.excluded_paths = self._labeled_text(parent, "Hariç Tutulan Yollar")
        tk.Label(parent, text="Çalışma Ayarları", bg=PANEL, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(10, 2))
        checks = tk.Frame(parent, bg=PANEL)
        checks.pack(fill="x", padx=8, pady=(0, 8))
        for label, var in [
            ("Pilot Mode", self.pilot_mode_var),
            ("Local", self.local_worker_var),
            ("Apply", self.auto_apply_var),
        ]:
            cb = tk.Checkbutton(checks, text=label, variable=var, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL)
            cb.pack(side="left", padx=(0, 12))
        self.engine_slot_frame = tk.Frame(parent, bg=PANEL)
        self.engine_slot_frame.pack(fill="x", padx=8, pady=(4, 8))
        tk.Button(
            parent,
            text="+ Motor",
            command=lambda: self._add_engine_slot(),
            bg=PANEL_2,
            fg=TEXT,
            relief="flat",
            padx=8,
            pady=5,
        ).pack(anchor="w", padx=8)
        self._add_engine_slot()
        self._large_text(parent, "readiness", "Backend readiness bekleniyor.")

    def _build_settings(self, parent: ttk.Frame) -> None:
        checks = tk.Frame(parent, bg=PANEL)
        checks.pack(fill="x", padx=8, pady=8)
        for label, var in [
            ("Pilot Mode", self.pilot_mode_var),
            ("Local", self.local_worker_var),
            ("Apply", self.auto_apply_var),
        ]:
            cb = tk.Checkbutton(checks, text=label, variable=var, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL)
            cb.pack(anchor="w")
        self.engine_slot_frame = tk.Frame(parent, bg=PANEL)
        self.engine_slot_frame.pack(fill="x", padx=8, pady=(4, 8))
        tk.Button(
            parent,
            text="+ Motor",
            command=lambda: self._add_engine_slot(),
            bg=PANEL_2,
            fg=TEXT,
            relief="flat",
            padx=8,
            pady=5,
        ).pack(anchor="w", padx=8)
        self._add_engine_slot()
        self._large_text(parent, "readiness", "Backend readiness bekleniyor.")

    def _add_engine_slot(self) -> None:
        if not hasattr(self, "engine_slot_frame"):
            return
        row = tk.Frame(self.engine_slot_frame, bg=PANEL)
        row.pack(fill="x", pady=3)
        enabled = tk.BooleanVar(value=False)
        manual = tk.BooleanVar(value=False)
        name = tk.StringVar(value="")
        api_ready = tk.BooleanVar(value=False)
        tk.Checkbutton(row, variable=enabled, bg=PANEL, selectcolor=BG, activebackground=PANEL, command=self._refresh_models_tree).pack(side="left")
        tk.Entry(row, textvariable=name, bg="#0d131b", fg=TEXT, insertbackground=TEXT, relief="flat", width=22).pack(side="left", padx=4)
        tk.Checkbutton(row, text="API", variable=api_ready, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL, command=self._refresh_models_tree).pack(side="left", padx=4)
        tk.Checkbutton(row, text="Manual", variable=manual, bg=PANEL, fg=TEXT, selectcolor=BG, activebackground=PANEL, command=self._refresh_models_tree).pack(side="left", padx=4)
        name.trace_add("write", lambda *_args: self._refresh_models_tree())
        self.engine_slots.append({"enabled": enabled, "manual": manual, "name": name, "api_ready": api_ready})
        self._refresh_models_tree()

    def _selected_engine_configs(self) -> list[dict[str, Any]]:
        configs = []
        for slot in self.engine_slots:
            engine_name = slot["name"].get().strip()
            if not engine_name:
                continue
            configs.append({
                "name": engine_name,
                "enabled": bool(slot["enabled"].get()),
                "manual": bool(slot["manual"].get()),
                "automatic": not bool(slot["manual"].get()),
                "api_ready": bool(slot["api_ready"].get()),
            })
        return configs

    def _refresh_models_tree(self) -> None:
        tree = self.tree_widgets.get("models")
        if not tree:
            return
        tree.delete(*tree.get_children())
        for config in self._selected_engine_configs():
            if not config["enabled"]:
                continue
            mode = "manual" if config["manual"] else "automatic"
            readiness = "api ready" if config["api_ready"] else "api missing"
            tree.insert("", "end", text=config["name"], values=(readiness, mode, "not attempted"))

    def _add_file_attachment(self) -> None:
        if not self._begin_attachment_pick("Dosya seçiliyor..."):
            return
        path = filedialog.askopenfilename(title="Dosya ekle")
        if path:
            self._register_attachment("file", path, allow_file=True)
        self._end_attachment_pick()

    def _add_folder_attachment(self) -> None:
        if not self._begin_attachment_pick("Klasör seçiliyor..."):
            return
        path = filedialog.askdirectory(title="Klasör ekle")
        if path:
            self._register_attachment("folder", path)
        self._end_attachment_pick()

    def _add_photo_attachment(self) -> None:
        if not self._begin_attachment_pick("Foto seçiliyor..."):
            return
        path = filedialog.askopenfilename(
            title="Foto ekle",
            filetypes=(("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("All files", "*.*")),
        )
        if path:
            self._register_attachment("photo", path, allow_file=True)
        self._end_attachment_pick()

    def _begin_attachment_pick(self, message: str) -> bool:
        if getattr(self, "_attachment_pick_active", False):
            return False
        self._attachment_pick_active = True
        self._set_attachment_buttons("disabled")
        self._set_attachment_status(message)
        self.root.update_idletasks()
        return True

    def _end_attachment_pick(self) -> None:
        self._attachment_pick_active = False
        self._set_attachment_buttons("normal")

    def _set_attachment_buttons(self, state: str) -> None:
        for button in self.attachment_buttons:
            button.configure(state=state)

    def _set_attachment_status(self, text: str) -> None:
        if hasattr(self, "attachment_status_var"):
            self.attachment_status_var.set(text)

    def _register_attachment(self, kind: str, path: str, allow_file: bool = False) -> None:
        normalized = str(Path(path).expanduser())
        key = (kind, normalized.lower())
        if key in self.attachment_keys:
            self._set_attachment_status(f"Zaten ekli: {Path(path).name}")
            self._show_attachment_summary()
            return
        self.attachment_keys.add(key)
        self.attachments.append({"type": kind, "path": normalized})
        if allow_file:
            self._append_allowed_file(normalized)
        self._set_attachment_status(f"{len(self.attachments)} ek hazır")
        self._show_attachment_summary()

    def _append_allowed_file(self, path: str) -> None:
        if not hasattr(self, "allowed_files"):
            return
        value = self._safe_relative_path(path)
        existing = split_lines(self.allowed_files.get("1.0", "end"))
        if value not in existing:
            self.allowed_files.insert("end", ("" if self.allowed_files.get("1.0", "end").strip() == "" else "\n") + value)

    def _safe_relative_path(self, path: str) -> str:
        try:
            repo = Path(self.repo_root_var.get().strip() or str(DEFAULT_MAIN_REPOSITORY)).resolve()
            target = Path(path).resolve()
            return target.relative_to(repo).as_posix()
        except Exception:
            return path

    def _show_attachment_summary(self) -> None:
        summary = "\n".join(f"{item['type']}: {item['path']}" for item in self.attachments)
        if not summary:
            summary = "Henüz ek yok."
        self._set_text("workspace_detail", f"Eklenenler:\n{summary}")
        self.log_diagnostic("INFO", f"attachments_ready={len(self.attachments)}")

    def _build_control_action_bar(self, parent: tk.Misc) -> None:
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill="x", padx=8, pady=(0, 8))
        actions = [
            ("Durum", "status"),
            ("Tanı", "diagnostics"),
            ("Ara", "search"),
            ("Bağlam", "context"),
            ("Plan", "task_plan"),
            ("Yama", "safe_patch"),
            ("Test", "validation"),
            ("Onaylar", "approvals"),
            ("Ertelenen", "deferred"),
            ("Sürdür", "deferred_resume"),
            ("Kanıt", "evidence"),
            ("Motorlar", "motors"),
            ("Ayarlar", "settings"),
        ]
        for label, action in actions:
            tk.Button(
                frame,
                text=label,
                command=lambda name=action: self.run_control_action(name),
                bg=PANEL_2,
                fg=TEXT,
                relief="flat",
                padx=7,
                pady=4,
            ).pack(side="left", padx=2, pady=2)

    def _build_center_safe_patch(self, parent: ttk.Frame) -> None:
        self._large_text(parent, "safe_patch_detail", "Güvenli yama diff/full content detayları backend preview ile dolar.")

    def _build_center_validation(self, parent: ttk.Frame) -> None:
        self._large_text(parent, "validation_detail", "Sandbox, Working Copy ve Main validation stdout/stderr detayları.")

    def _build_history(self, parent: ttk.Frame) -> None:
        self._large_text(parent, "history_detail", "Session geçmişi ve final evidence kayıtları.")

    def _build_right_summary_tab(self, parent: ttk.Frame, tab: str) -> None:
        content = {
            "Durum": "Aktif görev\nAktif motor\nHandoff durumu\nSistem logları\nProvider hataları",
            "İzinler": "Bekleyen model izinleri\nDosya izinleri\nÜcretli model onayları\nKapsam dışı dosya talepleri\nCommit/push izinleri",
            "Yama": "Oluşturulacak/değiştirilecek/silinecek dosyalar\nDiff/full content\nRisk seviyesi\nOnay durumu",
            "Test": "Sandbox / Working Copy / Main testleri\npy_compile, pytest, validators, smoke\nPASS / FAIL / TIMEOUT",
            "Entegrasyon": "Repository yolları\nSync / conflict\nSHA-256 precondition\nApply uygunluğu\nRollback durumu",
            "Kanıt": "Gerçek model denemeleri\nWork unit kanıtları\nTest kanıtları\nDosya hashleri\nFinal evidence",
        }[tab]
        self._large_text(parent, f"right_{tab}", content, height=16)
        if tab == "İzinler":
            self._action_row(parent, [
                ("Onayla", lambda: self._task_action("approve")),
                ("Reddet", lambda: self._task_action("reject")),
                ("Politika", lambda: self._task_action("policy")),
                ("Erişim", lambda: self._task_action("access")),
            ])
        elif tab == "Entegrasyon":
            self._action_row(parent, [
                ("Hazırla", lambda: self._task_action("prepare-integration")),
                ("Apply", lambda: self._task_action("apply")),
                ("Rollback", lambda: self._task_action("rollback")),
            ])
        elif tab == "Durum":
            self._action_row(parent, [
                ("Sürdür", lambda: self._task_action("resume")),
                ("İptal", lambda: self._task_action("cancel")),
                ("Yenile", self.refresh_backend_status),
            ])

    def _text_block(self, parent: tk.Misc, title: str, text: str) -> None:
        tk.Label(parent, text=title, bg=PANEL, fg=ACCENT, anchor="w", font=("Segoe UI", 9, "bold")).pack(fill="x", padx=6, pady=(8, 2))
        box = tk.Text(parent, height=3, bg="#0d131b", fg=TEXT, relief="flat", wrap="word")
        box.pack(fill="x", padx=6)
        box.insert("1.0", text)
        box.configure(state="disabled")
        self._attach_text_menu(box)

    def _section(self, parent: tk.Misc, title: str, text: str) -> None:
        tk.Label(parent, text=title, bg=PANEL, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        tk.Label(parent, text=text, bg=PANEL, fg=MUTED, justify="left").pack(anchor="w", padx=8, pady=(0, 8))

    def _large_text(self, parent: tk.Misc, key: str, text: str, height: int = 12) -> tk.Text:
        frame = tk.Frame(parent, bg=PANEL)
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        scroll = self._dark_scrollbar(frame)
        scroll.pack(side="right", fill="y")
        box = tk.Text(frame, height=height, bg="#0d131b", fg=TEXT, relief="flat", wrap="word", yscrollcommand=scroll.set)
        box.pack(fill="both", expand=True)
        scroll.configure(command=box.yview)
        box.insert("1.0", text)
        self.text_widgets[key] = box
        self._attach_text_menu(box)
        return box

    def _labeled_text(self, parent: tk.Misc, label: str) -> tk.Text:
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED).pack(anchor="w", padx=8, pady=(6, 1))
        return self._large_text(parent, label.lower().replace(" ", "_"), "", height=4)

    def _action_row(self, parent: tk.Misc, actions: list[tuple[str, Any]]) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", padx=8, pady=(0, 8))
        for label, command in actions:
            tk.Button(row, text=label, command=command, bg=PANEL_2, fg=TEXT, relief="flat", padx=8, pady=5).pack(side="left", padx=3)

    def _form_row(self, parent: tk.Misc, label: str, var: tk.StringVar) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=3)
        tk.Label(row, text=label, bg=PANEL, fg=MUTED, width=22, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=var, bg="#0d131b", fg=TEXT, insertbackground=TEXT, relief="flat").pack(side="left", fill="x", expand=True)

    def _key_values(self, parent: tk.Misc, rows: list[tuple[str, tk.StringVar]]) -> None:
        for label, var in rows:
            row = tk.Frame(parent, bg=PANEL)
            row.pack(fill="x", padx=8, pady=5)
            tk.Label(row, text=label, bg=PANEL, fg=MUTED, anchor="w").pack(anchor="w")
            tk.Label(row, textvariable=var, bg=PANEL, fg=TEXT, anchor="w", wraplength=210).pack(anchor="w")

    def _attach_text_menu(self, widget: tk.Text) -> None:
        menu = tk.Menu(widget, tearoff=False)
        menu.add_command(label="Kopyala", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Yapıştır", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Kes", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="Tümünü Seç", command=lambda: widget.tag_add("sel", "1.0", "end"))
        menu.add_command(label="Temizle", command=lambda: widget.delete("1.0", "end"))
        widget.bind("<Button-3>", lambda event: menu.tk_popup(event.x_root, event.y_root))

    def _looks_like_task_request(self, message: str) -> bool:
        normalized = message.casefold()
        explicit_prefixes = ("görev:", "gorev:", "task:", "işlem:", "islem:", "/task")
        if normalized.startswith(explicit_prefixes):
            return True
        task_hints = (
            "kod", "dosya", "klasör", "endpoint", "api", "test", "pytest", "validator",
            "düzelt", "duzelt", "ekle", "sil", "değiştir", "degistir", "refactor",
            "bug", "hata", "commit", "push", "safe patch", "repo", "repository",
        )
        return any(hint in normalized for hint in task_hints)

    def submit_task(self, summary: str | None = None, already_echoed: bool = False) -> None:
        if self.task_running:
            return
        summary = summary if summary is not None else self.task_input.get("1.0", "end").strip()
        if not summary:
            messagebox.showwarning("LUXCODE", "Görev açıklaması boş olamaz.")
            return
        if not already_echoed:
            self._append_chat("Sen", summary)
        self._set_task_running(True)
        self._append_chat(
            "LUXCODE",
            "Görev oluşturuluyor. Güncel durum ve gereken sonraki adım burada gösterilecek.",
        )
        payload = TaskSubmitPayload(
            task_summary=summary,
            main_repository_root=self.repo_root_var.get().strip() or str(DEFAULT_MAIN_REPOSITORY),
            working_copy_root=self.working_copy_var.get().strip(),
            sandbox_root=self.sandbox_root_var.get().strip(),
            workspace_mode=self.workspace_mode_var.get().lower().replace(" ", "_"),
            allowed_files=split_lines(self.allowed_files.get("1.0", "end")),
            suspected_files=split_lines(self.suspected_files.get("1.0", "end")),
            excluded_paths=split_lines(self.excluded_paths.get("1.0", "end")),
            pilot_mode=self.pilot_mode_var.get(),
            local_worker_enabled=self.local_worker_var.get(),
            free_gemini_enabled=any(c["enabled"] and "gemini" in c["name"].lower() for c in self._selected_engine_configs()),
            free_cloud_enabled=any(c["enabled"] for c in self._selected_engine_configs()),
            live_external_enabled=False,
            paid_escalation_allowed=False,
            auto_apply=self.auto_apply_var.get(),
            execution_mode=self.execution_mode_var.get(),
            access_level=normalize_access_label(self.access_level_var.get()),
            allowed_engines=[c["name"] for c in self._selected_engine_configs() if c["enabled"]],
            engine_configurations=self._selected_engine_configs(),
            attachments=list(self.attachments),
        )
        try:
            response = self.client.submit_task(payload)
        except Exception as exc:
            self.log_diagnostic("ERROR", str(exc))
            self._set_text("right_Durum", f"BACKEND CONNECTION REQUIRED\n{exc}")
            self._append_chat("LUXCODE", f"Görev başlatılamadı: {exc}")
            self._set_task_running(False)
            return
        self.task_input.delete("1.0", "end")
        state = TaskState.from_payload(response)
        self.apply_task_state(state)
        self._append_chat("LUXCODE", f"Görev durumu: {state.status}. Aktif motor: {state.active_engine or '-'}.")
        if state.task_id:
            self.polling.start(state.task_id)
        else:
            self._set_task_running(False)

    def _primary_task_action(self) -> None:
        message = self.task_input.get("1.0", "end").strip()
        if not message:
            return
        self.task_input.delete("1.0", "end")
        self._append_chat("Sen", message)
        if self.task_running:
            self._append_chat("Sistem", "Aktif görev kesilmedi; mesaj yönlendirilmiş konuşma olarak işleniyor.")
            self._send_chat_response(message, directed=True)
            return
        if self._looks_like_task_request(message):
            self.submit_task(message, already_echoed=True)
        else:
            self._send_chat_response(message, directed=False)

    def _set_task_running(self, running: bool) -> None:
        self.task_running = running
        if hasattr(self, "primary_task_button"):
            self.primary_task_button.configure(text="↑")

    def apply_task_state(self, state: TaskState) -> None:
        previous_status = self.active_state.status if self.active_state.task_id == state.task_id else ""
        self.active_state = state

        if state.is_terminal:
            self._set_task_running(False)

        self.status_vars["Durum"].set(state.status)
        self.status_vars["Aktif Motor"].set(state.active_engine)
        self.status_vars["Aktif Model"].set(state.active_model)
        self.status_vars["İlerleme"].set(f"{state.progress_percent}%")
        self.status_vars["Yapıldı"].set(str(len(state.completed_steps or state.completed_work_units)))
        self.status_vars["Kaldı"].set(str(len(state.pending_steps or state.remaining_work_units)))
        self.status_vars["Tasarruf"].set(str(getattr(state, "savings", "unavailable")))
        self.status_vars["Token"].set(str(state.token_usage or "unavailable"))
        self.status_vars["Maliyet"].set(str(state.provider_cost or "unavailable"))
        self.status_vars["Alan"].set(state.workspace_mode)
        self.status_vars["Test"].set(state.sandbox_validation_status)

        plan_summary = self._plan_summary(state)
        self._set_text("right_Durum", plan_summary)
        self._set_text("right_Yama", f"safe_patch_status={state.safe_patch_status}\napproval_status={state.approval_status}")
        self._set_text("right_Test", self._validation_summary(state))
        self._set_text("right_Entegrasyon", self._integration_summary(state))
        self._set_text("right_Kanıt", self._evidence_summary(state))
        self._set_text("completed_summary", self._completed_summary(state))
        self._set_text("remaining_summary", self._remaining_summary(state))
        self._set_text("task_plan_detail", plan_summary)
        self._set_text("validation_detail", self._validation_summary(state))
        self._set_text("safe_patch_detail", f"Güvenli yama durumu: {state.safe_patch_status}\nOnay: {state.approval_status}")

        if state.status == "awaiting_approval":
            self._set_text(
                "right_İzinler",
                "Görev yama onayı bekliyor.\n"
                "Devam etmek için İzinler sekmesindeki Onayla düğmesini kullanın.",
            )
        elif state.is_terminal:
            self._set_text(
                "right_İzinler",
                "Görev terminal duruma ulaştı. Yeni bir işlem için yeni görev oluşturun.",
            )

        marker = f"{state.task_id}:{state.status}:{state.next_safe_action}"
        if state.task_id and marker != self._last_announced_task_marker:
            self._last_announced_task_marker = marker
            if state.status != previous_status or state.next_safe_action:
                message = f"Durum: {state.status}."
                if state.next_safe_action:
                    message += f" Sonraki adım: {state.next_safe_action}"
                if state.changed_files:
                    message += f" Değişen dosya sayısı: {len(state.changed_files)}."
                else:
                    message += " Değişen dosya yok."
                self._append_chat("LUXCODE", message)

    def refresh_backend_status(self) -> None:
        readiness = backend_readiness(self.client, self.repo_root_var.get())
        lines = [f"{key}: {value}" for key, value in readiness.items()]
        self._set_text("readiness", "\n".join(lines))
        if readiness.get("Backend") == "disconnected":
            self._set_text("right_Durum", "BACKEND CONNECTION REQUIRED\n" + readiness.get("Reason", "backend unavailable"))

    def ensure_backend_ready(self) -> None:
        if os.getenv("LUXCODE_DESKTOP_AUTO_BACKEND", "1").strip().lower() in {"0", "false", "no", "off"}:
            self._set_text("right_Durum", "Backend otomatik başlatma test için kapalı.")
            return
        self._set_text("right_Durum", "Backend kontrol ediliyor...")

        def worker() -> None:
            result = self.backend_process.ensure_running()
            self.dispatcher.post(lambda: self._finish_backend_ready(result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_backend_ready(self, result: dict[str, str]) -> None:
        lines = [f"{key}: {value}" for key, value in result.items()]
        self._set_text("right_Durum", "\n".join(lines))
        if result.get("Backend") == "connected":
            self.refresh_backend_status()
        elif result.get("Backend") == "starting":
            self._set_text("right_Durum", "Backend başlatıldı, hazır olması birkaç saniye sürebilir.")

    def run_control_action(self, action_name: str) -> None:
        if action_name not in CONTROL_ACTIONS:
            self.log_diagnostic("ERROR", f"unknown control action: {action_name}")
            return
        method, path, target = CONTROL_ACTIONS[action_name]
        payload = self._control_payload(action_name)
        self._set_text(target, f"{action_name}: çalışıyor...")

        def worker() -> None:
            try:
                result = self.client.endpoint(method, path, payload if method == "POST" else None)
            except Exception as exc:
                self.dispatcher.post(lambda: self.log_diagnostic("ERROR", f"{action_name}: {exc}"))
                return
            self.dispatcher.post(lambda: self._finish_control_action(action_name, target, result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_control_action(self, action_name: str, target: str, result: dict[str, Any]) -> None:
        rendered = self._format_mapping(result)
        self._set_text(target, rendered)
        if action_name == "status":
            self.apply_task_state(TaskState.from_payload(result))

    def _control_payload(self, action_name: str) -> dict[str, Any]:
        repo = self.repo_root_var.get().strip() or str(DEFAULT_MAIN_REPOSITORY)
        task_summary = self.task_input.get("1.0", "end").strip() or "desktop control action"
        allowed_files = split_lines(self.allowed_files.get("1.0", "end")) if hasattr(self, "allowed_files") else []
        suspected_files = split_lines(self.suspected_files.get("1.0", "end")) if hasattr(self, "suspected_files") else []
        if action_name == "diagnostics":
            return {"repository_root": repo, "task_summary": task_summary, "selected_files": suspected_files}
        if action_name == "search":
            return {"repository_root": repo, "query": task_summary, "selected_files": suspected_files}
        if action_name == "context":
            return {"repository_root": repo, "task_summary": task_summary, "search_results": []}
        if action_name == "task_plan":
            return {"repository_root": repo, "task_summary": task_summary, "selected_files": allowed_files}
        if action_name == "safe_patch":
            return {
                "repository_root": repo,
                "approved_files": allowed_files,
                "operations": [],
                "preview_only": True,
                "auto_apply": False,
            }
        if action_name == "apply_prepare":
            return {"patch_contract": {}, "approval_confirmed": False, "auto_apply": False}
        if action_name == "validation":
            return {"repository_root": repo, "validation_plan": [], "live_external_enabled": False}
        if action_name == "deferred_resume":
            return {"repository_root": repo, "explicit_resume": True, "live_external_enabled": False}
        return {"repository_root": repo}

    def _task_action(self, action: str) -> None:
        if self.task_action_in_progress:
            self._append_chat("Sistem", "Önceki görev işlemi hâlâ sürüyor. Lütfen sonucu bekleyin.")
            return

        if not self.active_state.task_id:
            self._set_text(
                "right_Durum",
                f"{action}: blocked\nreason=no_active_task",
            )
            return

        task_id = self.active_state.task_id
        status = self.active_state.status

        if action == "approve":
            endpoint = "/luxcode-task/approve"
            payload = {"task_id": task_id}
            action_label = "Onay"

        elif action == "reject":
            endpoint = "/luxcode-task/cancel"
            payload = {
                "task_id": task_id,
                "reason": "patch_rejected_from_desktop",
            }
            action_label = "Ret"

        elif action == "cancel":
            endpoint = "/luxcode-task/cancel"
            payload = {
                "task_id": task_id,
                "reason": "cancelled_from_desktop",
            }
            action_label = "İptal"

        elif action == "resume" and self.active_state.is_terminal:
            self._set_text(
                "right_Durum",
                f"Görev zaten tamamlandı veya kapandı.\nstatus={status}\n"
                "Yeni işlem için yeni bir görev oluşturun.",
            )
            self._append_chat(
                "Sistem",
                "Görev terminal durumda. Sürdür işlemi gönderilmedi.",
            )
            return

        elif action == "resume" and status == "awaiting_approval":
            self._set_text(
                "right_İzinler",
                "Görev yama onayı bekliyor.\n"
                "Devam etmek için önce İzinler sekmesindeki Onayla düğmesine basın.",
            )
            self._append_chat(
                "Sistem",
                "Görev onay bekliyor. Sürdür işlemi gönderilmedi.",
            )
            return

        elif action == "resume" and status == "paused":
            endpoint = "/luxcode-task/resume"
            payload = {
                "task_id": task_id,
                "reason": "",
            }
            action_label = "Sürdür"

        elif action == "resume":
            endpoint = "/luxcode-task/advance"
            payload = {
                "task_id": task_id,
                "action": "next",
                "patch_steps": None,
                "verification_checks": None,
            }
            action_label = "Sürdür"

        else:
            self._set_text(
                "right_Durum",
                f"{action}: blocked\nreason=unsupported_desktop_action",
            )
            return

        self.task_action_in_progress = True
        self._set_text(
            "right_Durum",
            f"{action_label} isteği backend'e gönderiliyor...\n"
            f"task_id={task_id}\n"
            f"mevcut_durum={status}",
        )
        self._append_chat("Sistem", f"{action_label} işlemi gönderildi. Sonuç bekleniyor.")

        def worker() -> None:
            try:
                result = self.client.endpoint("POST", endpoint, payload)
            except Exception as exc:
                self.dispatcher.post(lambda: self._finish_task_action_error(action_label, str(exc)))
                return
            self.dispatcher.post(lambda: self._finish_task_action(action_label, result))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_task_action(self, action_label: str, result: dict[str, Any]) -> None:
        self.task_action_in_progress = False
        state = TaskState.from_payload(result)
        self.apply_task_state(state)
        self._append_chat("Sistem", f"{action_label} işlemi tamamlandı. Yeni durum: {state.status}.")
        if state.task_id and not state.is_terminal:
            self.polling.start(state.task_id)

    def _finish_task_action_error(self, action_label: str, error: str) -> None:
        self.task_action_in_progress = False
        self.log_diagnostic("ERROR", f"{action_label}: {error}")
        self._append_chat("Sistem", f"{action_label} işlemi başarısız: {error}")

    def _refresh_file_tree(self) -> None:
        tree = self.tree_widgets.get("files")
        if not tree:
            return
        tree.delete(*tree.get_children())
        root_path = DEFAULT_MAIN_REPOSITORY
        root_item = tree.insert("", "end", text=str(root_path), values=("main",), open=True)
        excluded = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".luxcode_runtime"}

        def add_children(parent_item: str, path, depth: int) -> None:
            if depth > 2:
                return
            try:
                entries = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
            except OSError:
                return
            for entry in entries[:80]:
                if entry.name in excluded:
                    continue
                state = "folder" if entry.is_dir() else "file"
                item = tree.insert(parent_item, "end", text=entry.name, values=(state,), open=False)
                if entry.is_dir():
                    add_children(item, entry, depth + 1)

        add_children(root_item, root_path, 0)

    def _set_text(self, key: str, value: str) -> None:
        box = self.text_widgets.get(key)
        if not box:
            return
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", value)

    def _format_mapping(self, payload: dict[str, Any]) -> str:
        lines = []
        for key in sorted(payload):
            value = payload[key]
            if isinstance(value, (dict, list)):
                lines.append(f"{key}={value}")
            else:
                lines.append(f"{key}={value}")
        return "\n".join(lines) if lines else "{}"

    def _plan_summary(self, state: TaskState) -> str:
        completed = ", ".join(state.completed_steps) if state.completed_steps else "-"
        pending = ", ".join(state.pending_steps) if state.pending_steps else "-"
        changed = ", ".join(state.changed_files) if state.changed_files else "yok"
        blocked = ", ".join(state.blocked_reasons) if state.blocked_reasons else "yok"
        return "\n".join([
            f"task_id={state.task_id or '-'}",
            f"session_id={state.session_id or '-'}",
            f"status={state.status}",
            f"active_engine={state.active_engine}",
            f"handoff_reason={state.handoff_reason}",
            f"completed_steps={completed}",
            f"pending_steps={pending}",
            f"changed_files={changed}",
            f"blocked_reasons={blocked}",
            f"next_safe_action={state.next_safe_action or '-'}",
        ])

    def _completed_summary(self, state: TaskState) -> str:
        if state.completed_steps:
            return "\n".join(f"{index}. {step}" for index, step in enumerate(state.completed_steps[:12], 1))
        if not state.completed_work_units:
            return "Henüz tamamlanan iş yok."
        lines = []
        for index, item in enumerate(state.completed_work_units[:6], 1):
            label = item.get("title") or item.get("unit_id") or item.get("id") or str(item)
            engine = item.get("completed_by_engine") or item.get("engine") or "-"
            lines.append(f"{index}. {label} ({engine})")
        return "\n".join(lines)

    def _remaining_summary(self, state: TaskState) -> str:
        if state.pending_steps:
            return "\n".join(f"{index}. {step}" for index, step in enumerate(state.pending_steps[:12], 1))
        if not state.remaining_work_units:
            return "Kalan iş yok."
        lines = []
        for index, item in enumerate(state.remaining_work_units[:12], 1):
            label = item.get("title") or item.get("unit_id") or item.get("id") or item.get("remaining_gap") or str(item)
            lines.append(f"{index}. {label}")
        return "\n".join(lines)

    def _validation_summary(self, state: TaskState) -> str:
        return "\n".join([
            f"Sandbox Testi: {state.sandbox_validation_status}",
            f"Çalışma Kopyası Testi: {state.working_copy_validation_status}",
            f"Ana Repo Testi: {state.main_validation_status}",
            "py_compile / pytest / validators / smoke: backend evidence required",
        ])

    def _integration_summary(self, state: TaskState) -> str:
        return "\n".join([
            f"main_repository_root={state.main_repository_root or self.repo_root_var.get()}",
            f"working_copy_root={state.working_copy_root}",
            f"sandbox_root={state.sandbox_root}",
            f"sync_status={state.sync_status}",
            f"conflict_status={state.conflict_status}",
            f"integration_status={state.integration_status}",
            f"rollback_status={state.rollback_status}",
        ])

    def _evidence_summary(self, state: TaskState) -> str:
        real_attempts = len(state.real_attempts)
        return "\n".join([
            f"real_model_attempts={real_attempts}",
            f"route_candidates={len(state.route_candidates)}",
            f"provider_cost={state.provider_cost}",
            f"token_usage={state.token_usage}",
            f"evidence_records={len(state.evidence)}",
        ])

    def log_diagnostic(self, level: str, message: str) -> None:
        self._set_text("right_Durum", f"[{level}] {message}")

    def toggle_left_panel(self) -> None:
        if not self.left_pane:
            return
        if self.left_hidden:
            self.body.insert(0, self.left_pane, weight=0)
            self.left_hidden = False
        else:
            self.body.forget(self.left_pane)
            self.left_hidden = True

    def toggle_right_panel(self) -> None:
        if not self.right_pane:
            return
        if self.right_hidden:
            self.body.add(self.right_pane, weight=0)
            self.right_hidden = False
        else:
            self.body.forget(self.right_pane)
            self.right_hidden = True

    def reset_layout(self) -> None:
        self.root.geometry("1440x860")
        if self.left_hidden:
            self.toggle_left_panel()
        if self.right_hidden:
            self.toggle_right_panel()

    def close(self) -> None:
        self.polling.stop()
        self.backend_process.stop_watchdog()
        self.dispatcher.close()
        save_layout(LayoutConfig(
            left_visible=not self.left_hidden,
            right_visible=not self.right_hidden,
            window_geometry=self.root.geometry(),
        ))
        self.root.destroy()
