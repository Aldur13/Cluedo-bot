import tkinter as tk

from cluedo.history import build_replay_snapshots


def open_replay(app, initial_index=None):
    gs = app.game_state
    theme = app.theme_manager.current
    snapshots = build_replay_snapshots(gs)
    start_index = len(snapshots) - 1 if initial_index is None else max(0, min(initial_index, len(snapshots) - 1))

    win = tk.Toplevel(app.root)
    win.title("Replay")
    win.geometry("520x520")
    win.configure(bg=theme.bg)

    tk.Label(win, text="Scrub through the game turn by turn", font=theme.heading_font(13), bg=theme.bg).pack(
        anchor="w", padx=12, pady=(12, 4)
    )

    label = tk.Label(win, text="", font=theme.body_font(10), justify="left", anchor="nw", bg=theme.panel_bg)
    label.pack(fill="both", expand=True, padx=12, pady=8)

    def render(index):
        snap = snapshots[index].game_state
        sheet = snap.detective_sheet()
        lines = [f"After turn {index} of {len(snapshots) - 1}:", ""]
        for card, info in sheet.items():
            if info["status"] == "confirmed":
                lines.append(f"  {card.name} → {info['owner']}")
        if snap.is_solved():
            s, w, r = snap.solution()
            lines.append("")
            lines.append(f"SOLVED: {s.name} / {w.name} / {r.name}")
        label.config(text="\n".join(lines))

    slider = tk.Scale(
        win, from_=0, to=max(0, len(snapshots) - 1), orient="horizontal", label="Turn",
        command=lambda v: render(int(v)), bg=theme.bg,
    )
    slider.pack(fill="x", padx=12, pady=(0, 12))
    slider.set(start_index)
    render(start_index)

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
