import json
import os
import sys
import re
import threading
from typing import Optional
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from tkinter.font import Font

import pyperclip

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def _get_config_path() -> str:
    base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Translator", "ui_config.json")

from backend import OllamaBackend, OllamaBackendOptions, OllamaMode
from core import (
    PipelineOptions,
    SplitMode,
    SplitOptions,
    render_output,
    OutputMode,
    AlignedPair,
    split_plain,
    split_with_limited_context,
)
from core.prompt import PromptOptions, build_prompt
from core.postprocess import extract_translation
from ui_windows.hotkey_windows import DoubleCtrlCListener
from ui_windows.ocr import (
    get_paste_image_paths,
    get_paste_images,
    is_ocr_available,
    run_ocr_async,
    run_ocr_async_images,
)


class TranslatorApp:
    def __init__(self):
        self._set_windows_dpi()
        self.root = tk.Tk()
        self.root.title("Translator")
        self.root.geometry("720x560")

        self.source_lang_var = tk.StringVar(value="auto")
        self.target_lang_var = tk.StringVar(value="en")
        self.use_context_var = tk.BooleanVar(value=False)
        self.collapse_newlines_var = tk.BooleanVar(value=False)
        self.output_mode_var = tk.StringVar(value=OutputMode.TRANSLATIONS_ONLY.value)
        self.layout_var = tk.StringVar(value="vertical")

        self.mode_var = tk.StringVar(value=OllamaMode.LOCAL.value)
        self.host_var = tk.StringVar(value="http://127.0.0.1:11434")
        self.model_var = tk.StringVar(value=OllamaBackendOptions().model)
        self.font_size_var = tk.IntVar(value=14)
        self.hotkey_enabled_var = tk.BooleanVar(value=True)
        self.minimize_to_tray_var = tk.BooleanVar(value=True)

        self._job_lock = threading.Lock()
        self._current_job_id = 0
        self._cancel_event: Optional[threading.Event] = None
        self._tray_icon = None
        self._tray_thread = None
        self._settings_window = None
        self._config_path = _get_config_path()
        self._last_geometry: Optional[str] = None

        self._font = Font(family="Segoe UI", size=self.font_size_var.get())
        self._load_config()
        self._apply_default_font()
        self._build_ui()
        self._wire_persist()
        self._setup_hotkey()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Configure>", self._on_root_configure)

    def _set_windows_dpi(self):
        if not sys.platform.startswith("win"):
            return
        try:
            import ctypes

            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    def _apply_default_font(self):
        if not sys.platform.startswith("win"):
            return
        try:
            self.root.option_add("*Font", "{Segoe UI} 10")
        except Exception:
            pass

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x")
        ttk.Label(header, text="Translator").pack(side="left")
        ttk.Button(header, text="Settings", command=self._open_settings).pack(side="right")
        ttk.Button(header, text="Quit", command=self._exit_app).pack(side="right", padx=(0, 8))
        self.stop_button = ttk.Button(header, text="Stop", command=self.cancel_translation, state="disabled")
        self.stop_button.pack(side="right", padx=(0, 8))
        self.translate_button = ttk.Button(header, text="Translate", command=self.translate_input)
        self.translate_button.pack(side="right")

        controls = ttk.Frame(main)
        controls.pack(fill="x", pady=(8, 8))

        self.config_box = ttk.LabelFrame(controls, text="Config", padding=8)
        self.config_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        ttk.Label(self.config_box, text="Model").grid(row=0, column=0, sticky="w")
        ttk.Entry(self.config_box, textvariable=self.model_var, width=28).grid(
            row=0, column=1, sticky="w", padx=(6, 16)
        )

        ttk.Label(self.config_box, text="Backend").grid(row=0, column=2, sticky="w")
        ttk.Radiobutton(
            self.config_box, text="Local", variable=self.mode_var, value=OllamaMode.LOCAL.value
        ).grid(row=0, column=3, sticky="w")
        ttk.Radiobutton(
            self.config_box, text="HTTP", variable=self.mode_var, value=OllamaMode.HTTP.value
        ).grid(row=0, column=4, sticky="w", padx=(0, 6))

        ttk.Label(self.config_box, text="Host").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(self.config_box, textvariable=self.host_var, width=32).grid(
            row=1, column=1, columnspan=4, sticky="w", padx=(6, 16), pady=(6, 0)
        )

        self.setting_box = ttk.LabelFrame(controls, text="Setting", padding=8)
        self.setting_box.grid(row=0, column=1, sticky="nsew")

        ttk.Label(self.setting_box, text="Source").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            self.setting_box,
            textvariable=self.source_lang_var,
            values=["auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
            width=6,
            state="readonly",
        ).grid(row=0, column=1, sticky="w", padx=(6, 12))

        ttk.Button(self.setting_box, text="Swap", command=self.swap_languages).grid(
            row=0, column=2, sticky="w"
        )

        ttk.Label(self.setting_box, text="Target").grid(row=0, column=3, sticky="w", padx=(8, 0))
        ttk.Combobox(
            self.setting_box,
            textvariable=self.target_lang_var,
            values=["zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
            width=6,
            state="readonly",
        ).grid(row=0, column=4, sticky="w", padx=(6, 12))

        ttk.Checkbutton(
            self.setting_box, text="Use Context", variable=self.use_context_var
        ).grid(row=0, column=5, sticky="w")

        ttk.Checkbutton(
            self.setting_box, text="Collapse Newlines", variable=self.collapse_newlines_var
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(self.setting_box, text="Output").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            self.setting_box,
            textvariable=self.output_mode_var,
            values=[OutputMode.TRANSLATIONS_ONLY.value, OutputMode.INTERLEAVED.value],
            width=16,
            state="readonly",
        ).grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(6, 0))

        ttk.Label(self.setting_box, text="Layout").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Combobox(
            self.setting_box,
            textvariable=self.layout_var,
            values=["vertical", "horizontal"],
            width=10,
            state="readonly",
        ).grid(row=1, column=3, sticky="w", padx=(6, 12), pady=(6, 0))

        ttk.Label(self.setting_box, text="Font").grid(row=1, column=4, sticky="w", pady=(6, 0))
        ttk.Button(self.setting_box, text="-", width=3, command=self.decrease_font).grid(
            row=1, column=5, sticky="w", pady=(6, 0)
        )
        ttk.Button(self.setting_box, text="+", width=3, command=self.increase_font).grid(
            row=1, column=6, sticky="w", pady=(6, 0)
        )

        controls.columnconfigure(0, weight=1)
        controls.columnconfigure(1, weight=1)
        controls.bind("<Configure>", self._layout_controls)
        self._layout_controls()

        self.panes = None
        self._build_panes(main)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w")
        self._create_context_menus()
        self.input_text.bind("<Control-v>", self._handle_paste)
        self.input_text.bind("<<Paste>>", self._handle_paste)
        self.root.bind_all("<Control-v>", self._handle_paste, add="+")
        self.root.bind_all("<<Paste>>", self._handle_paste, add="+")
        self.input_text.bind("<Button-2>", self._show_input_menu)
        self.input_text.bind("<Button-3>", self._show_input_menu)
        self.output_text.bind("<Button-2>", self._show_output_menu)
        self.output_text.bind("<Button-3>", self._show_output_menu)

    def _setup_hotkey(self):
        def on_trigger():
            self.root.after(0, self._handle_hotkey)

        listener = DoubleCtrlCListener(on_trigger=on_trigger)
        t = threading.Thread(target=self._run_hotkey_listener, args=(listener,), daemon=True)
        t.start()

    def _run_hotkey_listener(self, listener: DoubleCtrlCListener):
        try:
            listener.run()
        except Exception as exc:
            self.root.after(0, lambda exc=exc: self.status_var.set(f"Hotkey disabled: {exc}"))

    def _activate_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(120, lambda: self.root.attributes("-topmost", False))

    def _handle_hotkey(self):
        if not self.hotkey_enabled_var.get():
            return
        self._activate_window()
        text = pyperclip.paste()
        if text:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", text)
            self.translate_input()
        else:
            self.status_var.set("Clipboard is empty.")

    def _handle_paste(self, event):
        widget = getattr(event, "widget", None)
        if widget is not None and widget is not self.input_text:
            return None
        if not is_ocr_available():
            return None
        paths = get_paste_image_paths(self.root)
        if not paths:
            images = get_paste_images()
            if not images:
                return None
            self._start_ocr_images(images)
            return "break"
        self._start_ocr(paths)
        return "break"

    def _start_ocr(self, paths):
        self.status_var.set("OCR...")
        run_ocr_async(
            paths,
            on_done=lambda text: self.root.after(0, lambda: self._apply_ocr_result(text)),
            on_error=lambda exc: self.root.after(
                0,
                lambda exc=exc: self.status_var.set(f"OCR failed: {exc}"),
            ),
        )

    def _start_ocr_images(self, images):
        self.status_var.set("OCR...")
        run_ocr_async_images(
            images,
            on_done=lambda text: self.root.after(0, lambda: self._apply_ocr_result(text)),
            on_error=lambda exc: self.root.after(
                0,
                lambda exc=exc: self.status_var.set(f"OCR failed: {exc}"),
            ),
        )

    def _apply_ocr_result(self, text: str):
        if not text:
            self.status_var.set("OCR found no text.")
            return
        self.input_text.delete("1.0", "end")
        self.input_text.insert("1.0", text)
        self.translate_input()

    def _create_context_menus(self):
        self.input_menu = tk.Menu(self.root, tearoff=0)
        self.input_menu.add_command(label="Cut", command=lambda: self._text_action(self.input_text, "<<Cut>>"))
        self.input_menu.add_command(label="Copy", command=lambda: self._text_action(self.input_text, "<<Copy>>"))
        self.input_menu.add_command(label="Paste", command=lambda: self._text_action(self.input_text, "<<Paste>>"))
        self.input_menu.add_separator()
        self.input_menu.add_command(label="Select All", command=lambda: self._text_action(self.input_text, "<<SelectAll>>"))

        self.output_menu = tk.Menu(self.root, tearoff=0)
        self.output_menu.add_command(label="Copy", command=lambda: self._text_action(self.output_text, "<<Copy>>"))
        self.output_menu.add_separator()
        self.output_menu.add_command(label="Select All", command=lambda: self._text_action(self.output_text, "<<SelectAll>>"))

    def _text_action(self, widget, sequence: str):
        widget.event_generate(sequence)

    def _show_input_menu(self, event):
        self.input_menu.tk_popup(event.x_root, event.y_root)

    def _show_output_menu(self, event):
        self.output_menu.tk_popup(event.x_root, event.y_root)

    def translate_input(self):
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            self.status_var.set("Nothing to translate.")
            return

        self.cancel_translation()
        self.status_var.set("Translating...")
        self.translate_button.configure(state="disabled")
        self.stop_button.configure(state="normal")

        def worker():
            job_id, cancel_event = self._start_job()
            try:
                split_mode = SplitMode.CONTEXT if self.use_context_var.get() else SplitMode.PLAIN
                prompt_opt = PromptOptions(
                    source_lang=self.source_lang_var.get(),
                    target_lang=self.target_lang_var.get(),
                )
                split_opt = SplitOptions(strip_each_line=True, drop_empty_lines=False)
                opt = PipelineOptions(
                    split_mode=split_mode,
                    prompt_opt=prompt_opt,
                    split_opt=split_opt,
                    skip_empty_segments=False,
                )

                backend_opt = OllamaBackendOptions(
                    mode=OllamaMode(self.mode_var.get()),
                    model=self.model_var.get().strip() or OllamaBackendOptions().model,
                    host=self.host_var.get().strip() or OllamaBackendOptions().host,
                )
                backend = OllamaBackend(backend_opt)

                output_mode = OutputMode(self.output_mode_var.get())
                pairs = []
                if split_mode == SplitMode.CONTEXT:
                    segments = split_with_limited_context(
                        text, split_opt=opt.split_opt, ctx_opt=opt.ctx_opt
                    )
                else:
                    segments = split_plain(text, opt=opt.split_opt)

                for seg in segments:
                    if not seg.text.strip():
                        pairs.append(AlignedPair(source=seg.text, target=seg.text))
                        output = render_output(pairs, mode=output_mode)
                        self.root.after(
                            0,
                            lambda output=output, job_id=job_id: self._set_output_if_current(
                                job_id, output, status="Translating..."
                            ),
                        )
                        continue
                    if cancel_event.is_set():
                        break

                    seg_opt = PromptOptions(
                        source_lang=opt.prompt_opt.source_lang,
                        target_lang=opt.prompt_opt.target_lang,
                        preset=opt.prompt_opt.preset,
                        terminology=opt.prompt_opt.terminology,
                        context=seg.context,
                        src_text_with_format=opt.prompt_opt.src_text_with_format,
                    )
                    prompt = build_prompt(seg.text, seg_opt)

                    raw = ""
                    for chunk in backend.stream_generate(prompt):
                        if cancel_event.is_set():
                            break
                        raw += chunk
                        temp_pairs = pairs + [AlignedPair(source=seg.text, target=raw)]
                        output = render_output(temp_pairs, mode=output_mode)
                        self.root.after(
                            0,
                            lambda output=output, job_id=job_id: self._set_output_if_current(
                                job_id, output, status="Translating..."
                            ),
                        )
                    if cancel_event.is_set():
                        break

                    target = extract_translation(raw, opt.post_opt)
                    pairs.append(AlignedPair(source=seg.text, target=target))
                    output = render_output(pairs, mode=output_mode)
                    self.root.after(
                        0,
                        lambda output=output, job_id=job_id: self._set_output_if_current(
                            job_id, output, status="Translating..."
                        ),
                    )
                if cancel_event.is_set():
                    self.root.after(0, lambda job_id=job_id: self._finish_job(job_id, "Canceled."))
                else:
                    self.root.after(0, lambda job_id=job_id: self._finish_job(job_id, "Done."))
            except Exception as exc:
                self.root.after(
                    0,
                    lambda exc=exc, job_id=job_id: self._set_output_if_current(
                        job_id, f"Error: {exc}", status="Error"
                    ),
                )
                self.root.after(0, lambda job_id=job_id: self._finish_job(job_id, "Error"))

        threading.Thread(target=worker, daemon=True).start()

    def _start_job(self):
        with self._job_lock:
            self._current_job_id += 1
            self._cancel_event = threading.Event()
            return self._current_job_id, self._cancel_event

    def _finish_job(self, job_id: int, status: str):
        with self._job_lock:
            if job_id != self._current_job_id:
                return
            self.status_var.set(status)
            self.translate_button.configure(state="normal")
            self.stop_button.configure(state="disabled")

    def _normalize_output_text(self, text: str) -> str:
        if self.collapse_newlines_var.get():
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            return re.sub(r"\n{3,}", "\n\n", normalized)
        return text

    def _set_output(self, text: str, status: Optional[str] = "Done."):
        text = self._normalize_output_text(text)
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.see("end")
        self.output_text.configure(state="disabled")
        if status is not None:
            self.status_var.set(status)

    def _set_output_if_current(self, job_id: int, text: str, status: Optional[str] = "Done."):
        with self._job_lock:
            if job_id != self._current_job_id:
                return
        self._set_output(text, status=status)

    def cancel_translation(self):
        with self._job_lock:
            if self._cancel_event is not None:
                self._cancel_event.set()

    def swap_languages(self):
        src = self.source_lang_var.get()
        tgt = self.target_lang_var.get()
        if src == "auto":
            detected = self._detect_source_lang()
            if detected:
                src = detected
        self.source_lang_var.set(tgt)
        self.target_lang_var.set(src)

    def _detect_source_lang(self) -> Optional[str]:
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            return None
        for ch in text:
            code = ord(ch)
            if 0x3040 <= code <= 0x30FF:
                return "ja"
            if 0xAC00 <= code <= 0xD7AF:
                return "ko"
            if 0x4E00 <= code <= 0x9FFF:
                return "zh"
        return "en"

    def increase_font(self):
        size = min(30, self.font_size_var.get() + 1)
        self.font_size_var.set(size)
        self._font.configure(size=size)
        self._save_config()

    def decrease_font(self):
        size = max(10, self.font_size_var.get() - 1)
        self.font_size_var.set(size)
        self._font.configure(size=size)
        self._save_config()

    def _wire_persist(self):
        for var in [
            self.source_lang_var,
            self.target_lang_var,
            self.output_mode_var,
            self.use_context_var,
            self.collapse_newlines_var,
            self.layout_var,
            self.mode_var,
            self.host_var,
            self.model_var,
            self.font_size_var,
            self.hotkey_enabled_var,
            self.minimize_to_tray_var,
        ]:
            var.trace_add("write", lambda *_: self._save_config())
        self.layout_var.trace_add("write", lambda *_: self._rebuild_panes())

    def _load_config(self):
        if not os.path.exists(self._config_path):
            return
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        self.source_lang_var.set(data.get("source_lang", self.source_lang_var.get()))
        self.target_lang_var.set(data.get("target_lang", self.target_lang_var.get()))
        self.output_mode_var.set(data.get("output_mode", self.output_mode_var.get()))
        self.layout_var.set(data.get("layout", self.layout_var.get()))
        self.use_context_var.set(bool(data.get("use_context", self.use_context_var.get())))
        self.collapse_newlines_var.set(bool(data.get("collapse_newlines", self.collapse_newlines_var.get())))
        self.mode_var.set(data.get("mode", self.mode_var.get()))
        self.host_var.set(data.get("host", self.host_var.get()))
        self.model_var.set(data.get("model", self.model_var.get()))
        self.hotkey_enabled_var.set(bool(data.get("hotkey_enabled", self.hotkey_enabled_var.get())))
        self.minimize_to_tray_var.set(bool(data.get("minimize_to_tray", self.minimize_to_tray_var.get())))
        font_size = data.get("font_size", self.font_size_var.get())
        if isinstance(font_size, int):
            self.font_size_var.set(font_size)
            self._font.configure(size=font_size)
        geometry = data.get("window_geometry")
        if isinstance(geometry, str) and geometry:
            try:
                self.root.geometry(geometry)
            except Exception:
                pass

    def _save_config(self):
        data = {
            "source_lang": self.source_lang_var.get(),
            "target_lang": self.target_lang_var.get(),
            "output_mode": self.output_mode_var.get(),
            "layout": self.layout_var.get(),
            "use_context": self.use_context_var.get(),
            "collapse_newlines": self.collapse_newlines_var.get(),
            "mode": self.mode_var.get(),
            "host": self.host_var.get(),
            "model": self.model_var.get(),
            "font_size": self.font_size_var.get(),
            "hotkey_enabled": self.hotkey_enabled_var.get(),
            "minimize_to_tray": self.minimize_to_tray_var.get(),
            "window_geometry": self._last_geometry or self.root.geometry(),
        }
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=True, indent=2)
        except Exception:
            pass

    def _build_panes(self, parent):
        orient = "vertical" if self.layout_var.get() == "vertical" else "horizontal"
        self.panes = ttk.Panedwindow(parent, orient=orient)
        self.panes.pack(fill="both", expand=True)

        input_box = ttk.LabelFrame(self.panes, text="Input", padding=8)
        self.input_text = ScrolledText(input_box, height=10, wrap="word", font=self._font)
        self.input_text.pack(fill="both", expand=True)

        output_box = ttk.LabelFrame(self.panes, text="Output", padding=8)
        self.output_text = ScrolledText(output_box, height=10, wrap="word", state="disabled", font=self._font)
        self.output_text.pack(fill="both", expand=True)

        self.panes.add(input_box, weight=1)
        self.panes.add(output_box, weight=1)

    def _rebuild_panes(self):
        if self.panes is None:
            return
        input_text = self.input_text.get("1.0", "end")
        self.output_text.configure(state="normal")
        output_text = self.output_text.get("1.0", "end")
        self.output_text.configure(state="disabled")

        parent = self.panes.master
        self.panes.destroy()
        self._build_panes(parent)

        self.input_text.insert("1.0", input_text)
        self.output_text.configure(state="normal")
        self.output_text.insert("1.0", output_text)
        self.output_text.configure(state="disabled")

    def _layout_controls(self, event=None):
        width = event.width if event is not None else self.root.winfo_width()
        if width < 980:
            self.config_box.grid_configure(row=0, column=0, columnspan=2, padx=0, pady=(0, 8))
            self.setting_box.grid_configure(row=1, column=0, columnspan=2, padx=0, pady=(0, 0))
        else:
            self.config_box.grid_configure(row=0, column=0, columnspan=1, padx=(0, 8), pady=0)
            self.setting_box.grid_configure(row=0, column=1, columnspan=1, padx=0, pady=0)

    def _on_root_configure(self, event):
        if event.widget is self.root:
            self._last_geometry = self.root.geometry()

    def _open_settings(self):
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.resizable(False, False)
        win.transient(self.root)
        self._settings_window = win

        box = ttk.Frame(win, padding=12)
        box.pack(fill="both", expand=True)

        ttk.Checkbutton(
            box,
            text="Enable Ctrl+C Ctrl+C hotkey",
            variable=self.hotkey_enabled_var,
        ).pack(anchor="w", pady=(0, 6))

        ttk.Checkbutton(
            box,
            text="Minimize to tray on close",
            variable=self.minimize_to_tray_var,
        ).pack(anchor="w")

        ttk.Button(box, text="Close", command=win.destroy).pack(anchor="e", pady=(12, 0))

        def on_close():
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _on_close(self):
        self._save_config()
        if self.minimize_to_tray_var.get() and self._ensure_tray_icon():
            self._hide_to_tray()
            return
        self._exit_app()

    def _exit_app(self):
        self._save_config()
        self._stop_tray_icon()
        self.root.destroy()

    def _hide_to_tray(self):
        self.root.withdraw()
        try:
            if self._tray_icon is not None:
                self._tray_icon.visible = True
        except Exception:
            pass

    def _show_from_tray(self):
        self._activate_window()
        try:
            if self._tray_icon is not None:
                self._tray_icon.visible = False
        except Exception:
            pass

    def _ensure_tray_icon(self) -> bool:
        if self._tray_icon is not None:
            return True
        try:
            import pystray
            from PIL import Image, ImageDraw
        except Exception:
            self.status_var.set("Tray icon requires pystray and pillow.")
            return False

        image = Image.new("RGB", (64, 64), color=(40, 40, 40))
        draw = ImageDraw.Draw(image)
        draw.rectangle([8, 8, 56, 56], outline=(255, 255, 255), width=3)
        draw.text((22, 18), "T", fill=(255, 255, 255))

        def on_open(icon, item):
            self.root.after(0, self._show_from_tray)

        def on_quit(icon, item):
            self.root.after(0, self._exit_app)

        menu = pystray.Menu(
            pystray.MenuItem("Open", on_open, default=True),
            pystray.MenuItem("Quit", on_quit),
        )

        self._tray_icon = pystray.Icon("Translator", image, "Translator", menu)
        self._tray_thread = threading.Thread(target=self._tray_icon.run, daemon=True)
        self._tray_thread.start()
        return True

    def _stop_tray_icon(self):
        if self._tray_icon is None:
            return
        try:
            self._tray_icon.stop()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TranslatorApp().run()
