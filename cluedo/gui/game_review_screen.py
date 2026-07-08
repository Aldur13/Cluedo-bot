"""Game Review screen: a polished, scrollable analytics dashboard summarizing
`cluedo.analysis.game_review.GameReview` -- stat cards, progress bars, a
trend chart, a clickable timeline (jumps into Replay), and export buttons.

Follows the `open_X(app) -> Toplevel` convention every other screen in this
package uses (timeline_screen.py, replay_screen.py, whatif_screen.py,
graph_screen.py, settings_screen.py), and `cluedo.gui.scrollable_frame`'s
shared Canvas+Scrollbar idiom for the long, variable-height content.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from cluedo.analysis.game_review import GameReview, compute_game_review
from cluedo.gui import replay_screen
from cluedo.gui.game_review_export import (
    export_review_html,
    export_review_json,
    export_review_markdown,
    export_review_pdf,
)
from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.gui.window_geometry import fit_geometry

_BAR_WIDTH = 320
_BAR_HEIGHT = 16


def open_game_review(app, *, review: "GameReview | None" = None):
    """`review` lets a caller (e.g. the one-shot auto-open on solve) pass in
    an already-computed GameReview instead of recomputing it; manual
    toolbar/menu access omits it and this recomputes fresh from the live
    game_state, always reflecting current history."""
    gs = app.game_state
    theme = app.theme_manager.current
    if review is None:
        time_played = getattr(app, "_game_review_time_played_seconds", lambda: None)()
        review = compute_game_review(gs, time_played_seconds=time_played)

    win = tk.Toplevel(app.root)
    win.title("Game Review")
    fit_geometry(win, 820, 760)
    win.configure(bg=theme.bg)

    # Packed first, side="bottom", so Close stays reachable regardless of
    # how tall the dashboard gets -- the scrollable body (below) scrolls
    # internally instead of pushing it off-screen.
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="bottom", pady=(4, 12))

    header = tk.Frame(win, bg=theme.bg)
    header.pack(fill="x", padx=16, pady=(14, 6))
    tk.Label(
        header, text="★★★★★ Game Review", font=theme.heading_font(18), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w")

    scroll_outer, content = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True)

    _build_stat_cards(content, theme, review)
    _build_progress_bars(content, theme, review)
    _build_highlight_card(content, theme, "Key Turning Point", _turning_point_text(review))
    _build_highlight_card(content, theme, "Best Suggestion", _best_suggestion_text(review))
    _build_highlight_card(content, theme, "Largest Deduction", _largest_deduction_text(review))
    _build_missed_opportunities(content, theme, review)
    _build_chart(content, theme, review)
    _build_timeline(content, theme, review, app)
    _build_feedback(content, theme, review)
    _build_export_row(content, theme, review)


# ------------------------------------------------------------------- pieces


def _section_label(parent, theme, text):
    tk.Label(parent, text=text, font=theme.heading_font(13), bg=theme.bg, fg=theme.accent_dark).pack(
        anchor="w", padx=16, pady=(14, 4)
    )


def _build_stat_cards(parent, theme, review: GameReview):
    grid = tk.Frame(parent, bg=theme.bg)
    grid.pack(fill="x", padx=16, pady=(0, 4))

    stats = [
        ("Difficulty", review.difficulty, theme.accent),
        ("Overall Rating", review.overall_rating or "N/A", theme.confirmed if review.overall_rating else theme.muted_text),
        ("Efficiency", _pct(review.efficiency_pct), theme.text),
        ("Turns Played", str(review.turns_played), theme.text),
        ("Estimated Optimal Turn", _int_or_na(review.estimated_optimal_solve_turn), theme.text),
        ("Actual Solve Turn", _int_or_na(review.actual_solve_turn), theme.text),
        ("Turns Lost", _int_or_na(review.turns_lost), theme.impossible if review.turns_lost else theme.text),
        ("Time Played", _seconds_or_na(review.time_played_seconds), theme.text),
        ("Avg Time / Turn", _seconds_or_na(review.average_time_per_turn_seconds), theme.text),
        ("Final Accuracy", _pct(review.final_accuracy_pct), theme.text),
    ]
    columns = 3
    for i, (label, value, color) in enumerate(stats):
        card = tk.Frame(grid, bg=theme.panel_bg, padx=10, pady=8, highlightbackground=theme.unknown, highlightthickness=1)
        card.grid(row=i // columns, column=i % columns, padx=4, pady=4, sticky="nsew")
        tk.Label(card, text=label, font=theme.body_font(9), bg=theme.panel_bg, fg=theme.muted_text).pack(anchor="w")
        tk.Label(card, text=value, font=theme.heading_font(15), bg=theme.panel_bg, fg=color).pack(anchor="w")
    for c in range(columns):
        grid.grid_columnconfigure(c, weight=1)

    tk.Label(
        parent, text=review.difficulty_explanation, font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text,
        wraplength=760, justify="left",
    ).pack(anchor="w", padx=16, pady=(2, 6))


def _build_progress_bars(parent, theme, review: GameReview):
    _section_label(parent, theme, "Progress")
    body = tk.Frame(parent, bg=theme.bg)
    body.pack(fill="x", padx=16)

    for label, pct in (("Efficiency", review.efficiency_pct), ("Final Accuracy", review.final_accuracy_pct)):
        row = tk.Frame(body, bg=theme.bg)
        row.pack(fill="x", pady=4)
        tk.Label(row, text=label, font=theme.body_font(9), bg=theme.bg, fg=theme.text, width=14, anchor="w").pack(
            side="left"
        )
        bar_canvas = tk.Canvas(row, width=_BAR_WIDTH, height=_BAR_HEIGHT, bg=theme.unknown, highlightthickness=0)
        bar_canvas.pack(side="left", padx=(4, 8))
        fraction = 0.0 if pct is None else max(0.0, min(1.0, pct / 100.0))
        color = theme.confirmed if fraction >= 0.999 else theme.accent
        bar_canvas.create_rectangle(0, 0, _BAR_WIDTH * fraction, _BAR_HEIGHT, fill=color, width=0)
        tk.Label(row, text=_pct(pct), font=theme.body_font(9), bg=theme.bg, fg=theme.text).pack(side="left")


def _build_highlight_card(parent, theme, title, text):
    if text is None:
        return
    _section_label(parent, theme, title)
    tk.Label(
        parent, text=text, font=theme.body_font(10), bg=theme.panel_bg, fg=theme.text, justify="left",
        wraplength=760, padx=10, pady=8,
    ).pack(fill="x", padx=16)


def _build_missed_opportunities(parent, theme, review: GameReview):
    _section_label(parent, theme, "Missed Opportunities")
    body = tk.Frame(parent, bg=theme.bg)
    body.pack(fill="x", padx=16)
    if not review.missed_opportunities:
        tk.Label(
            body, text="None found -- no missed opportunities detected.", font=theme.body_font(9),
            bg=theme.bg, fg=theme.muted_text,
        ).pack(anchor="w")
        return
    for m in review.missed_opportunities:
        row = tk.Frame(body, bg=theme.bg)
        row.pack(fill="x", pady=1, anchor="w")
        tk.Label(row, text="⚠", font=theme.body_font(10), bg=theme.bg, fg=theme.possible).pack(side="left", padx=(0, 6))
        tk.Label(
            row, text=m.message, font=theme.body_font(9), bg=theme.bg, fg=theme.text, wraplength=720, justify="left",
        ).pack(side="left", anchor="w")


def _build_chart(parent, theme, review: GameReview):
    worlds = review.performance.valid_worlds_per_turn
    known_points = [(t, w) for t, w in enumerate(worlds) if w is not None]
    if len(known_points) < 2:
        return
    _section_label(parent, theme, "Valid Worlds Remaining")
    fig = Figure(figsize=(7, 2.4), dpi=100, facecolor=theme.bg)
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([t for t, _ in known_points], [w for _, w in known_points], color=theme.accent, marker="o", markersize=3)
    ax.set_xlabel("Turn", fontsize=9, color=theme.text)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="x", padx=16, pady=(0, 4))


def _build_timeline(parent, theme, review: GameReview, app):
    _section_label(parent, theme, "Timeline (click an event to jump to that turn in Replay)")
    body = tk.Frame(parent, bg=theme.bg)
    body.pack(fill="x", padx=16)
    if not review.timeline:
        tk.Label(body, text="No events.", font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text).pack(anchor="w")
        return
    for event in review.timeline:
        row = tk.Button(
            body, text=f"Turn {event.turn} — {event.label}: {event.description}",
            font=theme.body_font(9), bg=theme.panel_bg, fg=theme.text, anchor="w", justify="left",
            relief="flat", padx=8, pady=4,
            command=lambda t=event.turn: replay_screen.open_replay(app, initial_index=t),
        )
        row.pack(fill="x", pady=1)


def _build_feedback(parent, theme, review: GameReview):
    if not review.feedback:
        return
    _section_label(parent, theme, "Feedback")
    body = tk.Frame(parent, bg=theme.bg)
    body.pack(fill="x", padx=16)
    for line in review.feedback:
        tk.Label(
            body, text=f"• {line}", font=theme.body_font(9), bg=theme.bg, fg=theme.text, wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=1)


def _build_export_row(parent, theme, review: GameReview):
    _section_label(parent, theme, "Export")
    row = tk.Frame(parent, bg=theme.bg)
    row.pack(fill="x", padx=16, pady=(0, 8))

    def _do_export(label, extension, filetypes, export_fn):
        path = filedialog.asksaveasfilename(defaultextension=extension, filetypes=filetypes)
        if not path:
            return
        try:
            export_fn(review, path)
            messagebox.showinfo("Exported", f"Game review exported to {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    exports = [
        ("PDF", ".pdf", [("PDF document", "*.pdf")], export_review_pdf),
        ("HTML", ".html", [("HTML page", "*.html")], export_review_html),
        ("Markdown", ".md", [("Markdown", "*.md")], export_review_markdown),
        ("JSON", ".json", [("JSON", "*.json")], export_review_json),
    ]
    for label, ext, filetypes, fn in exports:
        tk.Button(
            row, text=label, font=theme.body_font(9), padx=10, pady=4,
            command=lambda label=label, ext=ext, filetypes=filetypes, fn=fn: _do_export(label, ext, filetypes, fn),
        ).pack(side="left", padx=(0, 6))


# --------------------------------------------------------------------- text


def _turning_point_text(review: GameReview) -> "str | None":
    h = review.key_turning_point
    if h is None:
        return None
    return f"Turn {h.turn}\n{h.explanation}"


def _best_suggestion_text(review: GameReview) -> "str | None":
    h = review.best_suggestion
    if h is None:
        return None
    return (
        f"{h.suspect.name} • {h.weapon.name} • {h.room.name}\n"
        f"Information gained / probability reduction: {_pct(h.info_gain * 100)}\n{h.explanation}"
    )


def _largest_deduction_text(review: GameReview) -> "str | None":
    d = review.largest_deduction
    if d is None:
        return None
    header = f"Turn {d.turn}" + (f" — {d.card.name}" if d.card else "")
    body = "\n".join(d.narrative)
    return f"{header}\n{body}"


# -------------------------------------------------------------------- misc


def _pct(value) -> str:
    return "N/A" if value is None else f"{value:.0f}%"


def _int_or_na(value) -> str:
    return "N/A" if value is None else str(value)


def _seconds_or_na(value) -> str:
    if value is None:
        return "N/A"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}m {seconds}s"
