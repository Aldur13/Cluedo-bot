import tkinter as tk
from tkinter import filedialog, messagebox

from cluedo.config import ConfigError, list_bundled_editions, load_bundled_edition, load_card_config


def build(parent, theme, on_selected):
    frame = tk.Frame(parent, bg=theme.bg)

    tk.Label(
        frame, text="Cluedo Deduction Assistant", font=theme.heading_font(22), bg=theme.bg, fg=theme.text
    ).pack(pady=(48, 4))
    tk.Label(
        frame, text="Choose an edition to begin", font=theme.body_font(12), bg=theme.bg, fg=theme.muted_text
    ).pack(pady=(0, 28))

    card_frame = tk.Frame(frame, bg=theme.bg)
    card_frame.pack()

    for key, display_name in list_bundled_editions():
        tk.Button(
            card_frame,
            text=display_name,
            font=theme.body_font(12),
            width=34,
            height=2,
            bg=theme.panel_bg,
            fg=theme.text,
            relief="raised",
            bd=1,
            cursor="hand2",
            command=lambda k=key: on_selected(load_bundled_edition(k)),
        ).pack(pady=6)

    def choose_custom():
        path = filedialog.askopenfilename(
            title="Choose a card-set JSON file", filetypes=[("JSON files", "*.json")]
        )
        if not path:
            return
        try:
            cfg = load_card_config(path)
        except ConfigError as exc:
            messagebox.showerror("Invalid card set", str(exc))
            return
        on_selected(cfg)

    tk.Button(
        card_frame,
        text="Load custom JSON…",
        font=theme.body_font(12),
        width=34,
        height=2,
        bg=theme.panel_bg,
        fg=theme.accent,
        relief="raised",
        bd=1,
        cursor="hand2",
        command=choose_custom,
    ).pack(pady=6)

    return frame
