"""Trends screen: matplotlib line/bar charts over the replayed game history,
built once when opened (not redrawn on every dashboard refresh tick, since a
matplotlib redraw is comparatively expensive and this data is replay-derived
rather than live-per-cell like the detective sheet).

Follows the same `open_X(app) -> Toplevel` convention as timeline_screen.py/
replay_screen.py rather than main_screen.py's `build(parent, app)` -- this is
a popup, not a screen swap.
"""
import tkinter as tk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from cluedo.history import build_replay_snapshots
from cluedo.timeseries import info_gained_per_turn, solver_progress_over_time, worlds_over_time


def open_graphs(app):
    gs = app.game_state
    theme = app.theme_manager.current
    snapshots = build_replay_snapshots(gs)

    win = tk.Toplevel(app.root)
    win.title("Trends")
    win.geometry("640x680")
    win.configure(bg=theme.bg)

    tk.Label(
        win, text="Trends over the game so far", font=theme.heading_font(13), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=12, pady=(12, 4))

    if len(snapshots) < 2:
        tk.Label(
            win, text="Log at least one suggestion to see trends.", font=theme.body_font(10), bg=theme.bg,
            fg=theme.muted_text,
        ).pack(padx=12, pady=12)
        tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
        return

    turns = list(range(len(snapshots)))
    worlds = worlds_over_time(snapshots)
    confirmed = solver_progress_over_time(snapshots)
    gains = info_gained_per_turn(snapshots)  # one shorter than turns/worlds/confirmed

    fig = Figure(figsize=(6, 6), dpi=100, facecolor=theme.bg)

    ax_worlds = fig.add_subplot(3, 1, 1)
    ax_worlds.plot(
        [t for t, w in zip(turns, worlds) if w is not None],
        [w for w in worlds if w is not None],
        color=theme.accent, marker="o", markersize=3,
    )
    ax_worlds.set_title("Valid worlds remaining", fontsize=10, color=theme.text)
    ax_worlds.tick_params(labelsize=8)

    ax_confirmed = fig.add_subplot(3, 1, 2)
    ax_confirmed.plot(turns, confirmed, color=theme.confirmed, marker="o", markersize=3)
    ax_confirmed.set_title("Cards confirmed", fontsize=10, color=theme.text)
    ax_confirmed.tick_params(labelsize=8)

    ax_gain = fig.add_subplot(3, 1, 3)
    ax_gain.bar(turns[1:], [g * 100 for g in gains], color=theme.accent_dark)
    ax_gain.set_title("Info gained per turn (%)", fontsize=10, color=theme.text)
    ax_gain.set_xlabel("Turn", fontsize=9, color=theme.text)
    ax_gain.tick_params(labelsize=8)

    fig.tight_layout()

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=4)

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
