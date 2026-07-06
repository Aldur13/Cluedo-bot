import tkinter as tk
from tkinter import filedialog, messagebox

from cluedo.config import ConfigError, list_bundled_editions, load_bundled_edition, load_card_config
from cluedo.gui import theme


def build(parent, on_selected):
    frame = tk.Frame(parent, bg=theme.BG)

    tk.Label(
        frame, text="Cluedo Deduction Assistant", font=theme.heading_font(22), bg=theme.BG, fg=theme.TEXT
    ).pack(pady=(48, 4))
    tk.Label(
        frame, text="Choose an edition to begin", font=theme.body_font(12), bg=theme.BG, fg=theme.MUTED_TEXT
    ).pack(pady=(0, 28))

    card_frame = tk.Frame(frame, bg=theme.BG)
    card_frame.pack()

    for key, display_name in list_bundled_editions():
        tk.Button(
            card_frame,
            text=display_name,
            font=theme.body_font(12),
            width=34,
            height=2,
            bg=theme.PANEL_BG,
            fg=theme.TEXT,
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
        bg=theme.PANEL_BG,
        fg=theme.ACCENT,
        relief="raised",
        bd=1,
        cursor="hand2",
        command=choose_custom,
    ).pack(pady=6)

    return frame
