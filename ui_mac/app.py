import os
import sys
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

import pyperclip

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from backend import OllamaBackend, OllamaBackendOptions, OllamaMode
from core import PipelineOptions, SplitMode, run_pipeline, render_output, OutputMode
from core.prompt import PromptOptions
from ui_mac.hotkey_mac import DoubleCmdCListener

try:
    from AppKit import NSApplication
except Exception:  # noqa: BLE001 - optional dependency
    NSApplication = None


class TranslatorApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Translator")
        self.root.geometry("720x560")

        self.source_lang_var = tk.StringVar(value="auto")
        self.target_lang_var = tk.StringVar(value="en")
        self.use_context_var = tk.BooleanVar(value=False)
        self.output_mode_var = tk.StringVar(value=OutputMode.TRANSLATIONS_ONLY.value)

        self.mode_var = tk.StringVar(value=OllamaMode.LOCAL.value)
        self.host_var = tk.StringVar(value="http://127.0.0.1:11434")
        self.model_var = tk.StringVar(value=OllamaBackendOptions().model)

        self._build_ui()
        self._setup_hotkey()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x")
        ttk.Label(header, text="Input").pack(side="left")
        ttk.Button(header, text="Translate", command=self.translate_input).pack(side="right")
        ttk.Button(header, text="Quit", command=self.root.destroy).pack(side="right", padx=(0, 8))

        options = ttk.Frame(main)
        options.pack(fill="x", pady=(8, 8))

        ttk.Label(options, text="Source").grid(row=0, column=0, sticky="w")
        source_combo = ttk.Combobox(
            options,
            textvariable=self.source_lang_var,
            values=["auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
            width=6,
            state="readonly",
        )
        source_combo.grid(row=0, column=1, sticky="w", padx=(6, 16))

        ttk.Label(options, text="Target").grid(row=0, column=2, sticky="w")
        target_combo = ttk.Combobox(
            options,
            textvariable=self.target_lang_var,
            values=["zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
            width=6,
            state="readonly",
        )
        target_combo.grid(row=0, column=3, sticky="w", padx=(6, 16))

        ttk.Checkbutton(
            options, text="Use Context", variable=self.use_context_var
        ).grid(row=0, column=4, sticky="w")

        ttk.Label(options, text="Model").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options, textvariable=self.model_var, width=28).grid(
            row=1, column=1, columnspan=2, sticky="w", padx=(6, 16), pady=(8, 0)
        )

        ttk.Label(options, text="Backend").grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Radiobutton(
            options, text="Local", variable=self.mode_var, value=OllamaMode.LOCAL.value
        ).grid(row=1, column=3, sticky="w", pady=(8, 0))
        ttk.Radiobutton(
            options, text="HTTP", variable=self.mode_var, value=OllamaMode.HTTP.value
        ).grid(row=1, column=4, sticky="w", pady=(8, 0))

        ttk.Label(options, text="Host").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(options, textvariable=self.host_var, width=32).grid(
            row=2, column=1, columnspan=3, sticky="w", padx=(6, 16), pady=(8, 0)
        )

        ttk.Label(options, text="Output").grid(row=2, column=4, sticky="w", pady=(8, 0))
        ttk.Combobox(
            options,
            textvariable=self.output_mode_var,
            values=[OutputMode.TRANSLATIONS_ONLY.value, OutputMode.INTERLEAVED.value],
            width=16,
            state="readonly",
        ).grid(row=2, column=5, sticky="w", pady=(8, 0))

        self.input_text = ScrolledText(main, height=10, wrap="word")
        self.input_text.pack(fill="both", expand=True, pady=(8, 12))

        ttk.Label(main, text="Output").pack(anchor="w")
        self.output_text = ScrolledText(main, height=10, wrap="word", state="disabled")
        self.output_text.pack(fill="both", expand=True, pady=(8, 12))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w")

    def _setup_hotkey(self):
        def on_trigger():
            self.root.after(0, self._handle_hotkey)

        listener = DoubleCmdCListener(on_trigger=on_trigger)
        t = threading.Thread(target=self._run_hotkey_listener, args=(listener,), daemon=True)
        t.start()

    def _run_hotkey_listener(self, listener: DoubleCmdCListener):
        try:
            listener.run()
        except Exception as exc:
            self.root.after(
                0,
                lambda exc=exc: self.status_var.set(
                    f"Hotkey disabled: {exc}"
                ),
            )

    def _activate_window(self):
        if NSApplication is not None:
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        self.root.attributes("-topmost", True)
        self.root.after(120, lambda: self.root.attributes("-topmost", False))

    def _handle_hotkey(self):
        self._activate_window()
        text = pyperclip.paste()
        if text:
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", text)
            self.translate_input()
        else:
            self.status_var.set("Clipboard is empty.")

    def translate_input(self):
        text = self.input_text.get("1.0", "end").strip()
        if not text:
            self.status_var.set("Nothing to translate.")
            return

        self.status_var.set("Translating...")

        def worker():
            try:
                split_mode = SplitMode.CONTEXT if self.use_context_var.get() else SplitMode.PLAIN
                prompt_opt = PromptOptions(
                    source_lang=self.source_lang_var.get(),
                    target_lang=self.target_lang_var.get(),
                )
                opt = PipelineOptions(split_mode=split_mode, prompt_opt=prompt_opt)

                backend_opt = OllamaBackendOptions(
                    mode=OllamaMode(self.mode_var.get()),
                    model=self.model_var.get().strip() or OllamaBackendOptions().model,
                    host=self.host_var.get().strip() or OllamaBackendOptions().host,
                )
                backend = OllamaBackend(backend_opt)

                pairs = run_pipeline(text, generate=backend.generate, opt=opt)
                output_mode = OutputMode(self.output_mode_var.get())
                output = render_output(pairs, mode=output_mode)
                self.root.after(0, lambda: self._set_output(output))
            except Exception as exc:
                self.root.after(0, lambda exc=exc: self._set_output(f"Error: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _set_output(self, text: str):
        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", text)
        self.output_text.configure(state="disabled")
        self.status_var.set("Done.")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    TranslatorApp().run()
