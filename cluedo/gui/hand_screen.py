import tkinter as tk
from tkinter import messagebox

from cluedo.gui.scrollable_frame import build_scrollable_frame


def build(parent, theme, config, expected_hand_size, on_confirmed):
    frame = tk.Frame(parent, bg=theme.bg)

    vars_by_name: dict[str, tk.BooleanVar] = {}

    def confirm():
        selected = [name for name, v in vars_by_name.items() if v.get()]
        if len(selected) != expected_hand_size:
            if not messagebox.askyesno(
                "Unexpected hand size",
                f"You selected {len(selected)} cards but expected {expected_hand_size}. Continue anyway?",
            ):
                return
        by_name = {c.name: c for c in config.all_cards()}
        on_confirmed([by_name[n] for n in selected])

    # Packed first, side="bottom", so the button always stays above the
    # window's bottom margin -- if the card columns below grow taller than
    # the available space, the scrollable area they're wrapped in (below)
    # scrolls internally instead of pushing this button off-screen.
    footer = tk.Frame(frame, bg=theme.bg)
    footer.pack(side="bottom", fill="x", pady=16)
    tk.Button(
        footer, text="Start tracking →", bg=theme.accent, fg="white", font=theme.body_font(12),
        padx=20, pady=8, cursor="hand2", command=confirm,
    ).pack()

    tk.Label(
        frame, text="Select your hand", font=theme.heading_font(18), bg=theme.bg, fg=theme.text
    ).pack(pady=(20, 4))
    tk.Label(
        frame, text=f"You should have {expected_hand_size} cards.",
        font=theme.body_font(11), bg=theme.bg, fg=theme.muted_text,
    ).pack(pady=(0, 16))

    scroll_outer, scroll_inner = build_scrollable_frame(frame, theme)
    scroll_outer.pack(fill="both", expand=True, padx=20)

    columns = tk.Frame(scroll_inner, bg=theme.bg)
    columns.pack(fill="both", expand=True)

    def add_column(title, names):
        col = tk.Frame(columns, bg=theme.panel_bg, bd=1, relief="solid")
        col.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        tk.Label(col, text=title, font=theme.body_font(12, "bold"), bg=theme.panel_bg, fg=theme.accent_dark).pack(
            pady=6
        )
        for name in names:
            v = tk.BooleanVar(value=False)
            vars_by_name[name] = v
            tk.Checkbutton(
                col, text=name, variable=v, bg=theme.panel_bg, anchor="w", font=theme.body_font(10)
            ).pack(fill="x", padx=10)

    add_column("Suspects", config.suspects)
    add_column("Weapons", config.weapons)
    add_column("Rooms", config.rooms)

    return frame
