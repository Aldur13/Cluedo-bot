import tkinter as tk
from tkinter import messagebox


def build(parent, theme, config, expected_hand_size, on_confirmed):
    frame = tk.Frame(parent, bg=theme.bg)
    tk.Label(
        frame, text="Select your hand", font=theme.heading_font(18), bg=theme.bg, fg=theme.text
    ).pack(pady=(20, 4))
    tk.Label(
        frame, text=f"You should have {expected_hand_size} cards.",
        font=theme.body_font(11), bg=theme.bg, fg=theme.muted_text,
    ).pack(pady=(0, 16))

    columns = tk.Frame(frame, bg=theme.bg)
    columns.pack(fill="both", expand=True, padx=20)

    vars_by_name: dict[str, tk.BooleanVar] = {}

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

    tk.Button(
        frame, text="Start tracking →", bg=theme.accent, fg="white", font=theme.body_font(12),
        padx=20, pady=8, cursor="hand2", command=confirm,
    ).pack(pady=16)

    return frame
