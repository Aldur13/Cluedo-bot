import tkinter as tk
from tkinter import messagebox

from cluedo.gui.scrollable_frame import build_scrollable_frame


def build(parent, theme, config, expected_hand_size, on_confirmed):
    frame = tk.Frame(parent, bg=theme.bg)

    vars_by_name: dict[str, tk.BooleanVar] = {}
    mode_var = tk.StringVar(value="checkbox")
    manual_input_widget = None

    def confirm():
        if mode_var.get() == "manual":
            text = manual_input_widget.get("1.0", "end").strip()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            by_name = {c.name: c for c in config.all_cards()}
            valid_names = set(by_name.keys())
            invalid = [n for n in lines if n not in valid_names]
            if invalid:
                messagebox.showerror("Invalid cards", f"Card names not found: {', '.join(invalid)}")
                return
            selected = lines
        else:
            selected = [name for name, v in vars_by_name.items() if v.get()]

        if len(selected) != expected_hand_size:
            if not messagebox.askyesno(
                "Unexpected hand size",
                f"You selected {len(selected)} cards but expected {expected_hand_size}. Continue anyway?",
            ):
                return
        by_name = {c.name: c for c in config.all_cards()}
        on_confirmed([by_name[n] for n in selected])

    footer = tk.Frame(frame, bg=theme.bg)
    footer.pack(side="bottom", fill="x", pady=16)
    tk.Button(
        footer, text="Start tracking →", bg=theme.accent, fg="white", font=theme.body_font(12),
        padx=20, pady=8, cursor="hand2", command=confirm,
    ).pack()

    tk.Label(
        frame, text="Select your hand", font=theme.heading_font(18), bg=theme.bg, fg=theme.text
    ).pack(pady=(20, 4))

    mode_frame = tk.Frame(frame, bg=theme.bg)
    mode_frame.pack(pady=(0, 12))
    tk.Radiobutton(
        mode_frame, text="Click cards", variable=mode_var, value="checkbox", bg=theme.bg,
        command=lambda: toggle_input_mode()
    ).pack(side="left", padx=6)
    tk.Radiobutton(
        mode_frame, text="Type names", variable=mode_var, value="manual", bg=theme.bg,
        command=lambda: toggle_input_mode()
    ).pack(side="left", padx=6)

    tk.Label(
        frame, text=f"You should have {expected_hand_size} cards.",
        font=theme.body_font(11), bg=theme.bg, fg=theme.muted_text,
    ).pack(pady=(0, 8))

    content_frame = tk.Frame(frame, bg=theme.bg)
    content_frame.pack(fill="both", expand=True, padx=20)

    scroll_outer, scroll_inner = build_scrollable_frame(content_frame, theme)
    scroll_outer.pack(fill="both", expand=True)

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

    manual_frame = tk.Frame(content_frame, bg=theme.bg)

    manual_label = tk.Label(
        manual_frame,
        text="Enter one card name per line:",
        font=theme.body_font(10),
        bg=theme.bg,
        fg=theme.muted_text,
    )
    manual_label.pack(pady=(0, 6))

    manual_input_widget = tk.Text(manual_frame, height=10, width=40, font=theme.body_font(10))
    manual_input_widget.pack(fill="both", expand=True)

    hint_text = ", ".join([c.name for c in config.all_cards()[:6]])
    tk.Label(
        manual_frame,
        text=f"e.g. {hint_text}, ...",
        font=theme.body_font(9),
        bg=theme.bg,
        fg=theme.muted_text,
    ).pack(pady=(4, 0))

    def toggle_input_mode():
        if mode_var.get() == "manual":
            scroll_outer.pack_forget()
            manual_frame.pack(fill="both", expand=True)
        else:
            manual_frame.pack_forget()
            scroll_outer.pack(fill="both", expand=True)

    return frame
