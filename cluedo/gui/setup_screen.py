import tkinter as tk
from tkinter import messagebox

from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.models import Player


def build(parent, theme, config, on_confirmed):
    frame = tk.Frame(parent, bg=theme.bg)

    total_non_envelope = len(config.suspects) + len(config.weapons) + len(config.rooms) - 3

    # Packed first, side="bottom", so "Continue ->" always stays above the
    # window's bottom margin regardless of how many player rows are shown
    # below (up to 6) -- the scrollable wrapper around rows_frame (below)
    # scrolls internally instead of pushing this button off-screen.
    footer = tk.Frame(frame, bg=theme.bg)
    footer.pack(side="bottom", fill="x")

    tk.Label(
        frame, text=f"Setup — {config.edition}", font=theme.heading_font(18), bg=theme.bg, fg=theme.text
    ).pack(pady=(24, 12))

    count_frame = tk.Frame(frame, bg=theme.bg)
    count_frame.pack(pady=6)
    tk.Label(count_frame, text="Number of players:", font=theme.body_font(11), bg=theme.bg).pack(
        side="left", padx=6
    )
    count_var = tk.IntVar(value=3)

    scroll_outer, scroll_inner = build_scrollable_frame(frame, theme)
    scroll_outer.pack(fill="both", expand=True, padx=20)
    rows_frame = tk.Frame(scroll_inner, bg=theme.bg)
    rows_frame.pack(fill="x", pady=12)

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
            row = tk.Frame(rows_frame, bg=theme.bg)
            row.pack(fill="x", pady=3)
            tk.Radiobutton(row, text="You", variable=you_var, value=i, bg=theme.bg).pack(side="left", padx=(0, 8))
            nv = tk.StringVar(value=f"Player {i + 1}")
            name_vars.append(nv)
            tk.Entry(row, textvariable=nv, width=18, font=theme.body_font(11)).pack(side="left", padx=4)
            tk.Label(row, text="Hand size:", bg=theme.bg, font=theme.body_font(10)).pack(side="left", padx=(12, 4))
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
    tk.Label(frame, text=hint, font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text).pack(
        before=scroll_outer, pady=(0, 4)
    )

    def confirm():
        # The player-count/hand-size Spinboxes are freely editable text
        # fields, not just up/down-click steppers -- typing e.g. "3x" leaves
        # the IntVar holding a non-numeric string, and .get() raises TclError
        # rather than returning a value. Report it like every other
        # validation failure here instead of letting it crash the app.
        try:
            n = count_var.get()
            sizes = [v.get() for v in hand_vars]
        except tk.TclError:
            messagebox.showerror("Invalid number", "Player count and hand sizes must be whole numbers.")
            return
        names = [v.get().strip() for v in name_vars]
        if any(not name for name in names):
            messagebox.showerror("Missing name", "Every player needs a name.")
            return
        if len(set(names)) != len(names):
            messagebox.showerror("Duplicate name", "Player names must be unique.")
            return
        if sum(sizes) != total_non_envelope:
            messagebox.showerror("Hand sizes don't add up", hint)
            return
        players = [Player(names[i], i, sizes[i]) for i in range(n)]
        on_confirmed(players, you_var.get())

    tk.Button(
        footer, text="Continue →", font=theme.body_font(12), bg=theme.accent, fg="white",
        activebackground=theme.accent_dark, padx=20, pady=8, cursor="hand2", command=confirm,
    ).pack(pady=20)

    return frame
