import tkinter as tk
from tkinter import messagebox

from cluedo.gui import theme
from cluedo.models import Player


def build(parent, config, on_confirmed):
    frame = tk.Frame(parent, bg=theme.BG)
    tk.Label(
        frame, text=f"Setup — {config.edition}", font=theme.heading_font(18), bg=theme.BG, fg=theme.TEXT
    ).pack(pady=(24, 12))

    total_non_envelope = len(config.suspects) + len(config.weapons) + len(config.rooms) - 3

    count_frame = tk.Frame(frame, bg=theme.BG)
    count_frame.pack(pady=6)
    tk.Label(count_frame, text="Number of players:", font=theme.body_font(11), bg=theme.BG).pack(
        side="left", padx=6
    )
    count_var = tk.IntVar(value=3)

    rows_frame = tk.Frame(frame, bg=theme.BG)
    rows_frame.pack(pady=12)

    name_vars: list[tk.StringVar] = []
    hand_vars: list[tk.IntVar] = []
    you_var = tk.IntVar(value=0)

    def default_hand_sizes(n):
        base, extra = divmod(total_non_envelope, n)
        return [base + (1 if i < extra else 0) for i in range(n)]

    def rebuild_rows():
        for child in rows_frame.winfo_children():
            child.destroy()
        name_vars.clear()
        hand_vars.clear()
        n = count_var.get()
        sizes = default_hand_sizes(n)
        for i in range(n):
            row = tk.Frame(rows_frame, bg=theme.BG)
            row.pack(fill="x", pady=3)
            tk.Radiobutton(row, text="You", variable=you_var, value=i, bg=theme.BG).pack(side="left", padx=(0, 8))
            nv = tk.StringVar(value=f"Player {i + 1}")
            name_vars.append(nv)
            tk.Entry(row, textvariable=nv, width=18, font=theme.body_font(11)).pack(side="left", padx=4)
            tk.Label(row, text="Hand size:", bg=theme.BG, font=theme.body_font(10)).pack(side="left", padx=(12, 4))
            hv = tk.IntVar(value=sizes[i])
            hand_vars.append(hv)
            tk.Spinbox(row, from_=0, to=total_non_envelope, textvariable=hv, width=4).pack(side="left")

    tk.Spinbox(
        count_frame, from_=3, to=6, textvariable=count_var, width=4, command=rebuild_rows
    ).pack(side="left")
    rebuild_rows()

    hint = (
        f"Hand sizes must total {total_non_envelope} "
        f"({len(config.suspects) + len(config.weapons) + len(config.rooms)} cards minus the 3 in the envelope)."
    )
    tk.Label(frame, text=hint, font=theme.body_font(9), bg=theme.BG, fg=theme.MUTED_TEXT).pack(pady=(0, 4))

    def confirm():
        n = count_var.get()
        names = [v.get().strip() for v in name_vars]
        if any(not name for name in names):
            messagebox.showerror("Missing name", "Every player needs a name.")
            return
        if len(set(names)) != len(names):
            messagebox.showerror("Duplicate name", "Player names must be unique.")
            return
        sizes = [v.get() for v in hand_vars]
        if sum(sizes) != total_non_envelope:
            messagebox.showerror("Hand sizes don't add up", hint)
            return
        players = [Player(names[i], i, sizes[i]) for i in range(n)]
        on_confirmed(players, you_var.get())

    tk.Button(
        frame, text="Continue →", font=theme.body_font(12), bg=theme.ACCENT, fg="white",
        activebackground=theme.ACCENT_DARK, padx=20, pady=8, cursor="hand2", command=confirm,
    ).pack(pady=20)

    return frame
