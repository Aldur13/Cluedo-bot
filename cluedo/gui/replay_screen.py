"""Replay: scrub through the game turn by turn. Enhanced (v4.5) to also show,
per snapshot: the exact remaining-world count, top envelope candidate per
category, and the largest-deduction/missed-opportunities-so-far (from a
`GameReview` computed once per open -- reused from `app._game_review_cache`
when available post-solve, matching `game_review_card_panel.py`'s
never-recompute-twice rule -- not recomputed on every slider tick). "Jump to
next/previous deduction" uses `cluedo.analysis.live_events.
confirmed_card_events`, the same real per-turn confirmation data Timeline
and Recent Deductions already use.
"""
import tkinter as tk

from cluedo.analysis.game_review import compute_game_review
from cluedo.analysis.live_events import confirmed_card_events
from cluedo.gui.window_geometry import fit_geometry
from cluedo.history import build_replay_snapshots
from cluedo.models import ENVELOPE, CardType
from cluedo.probability import TooManyAmbiguousCardsError
from cluedo.timeseries import worlds_over_time


def open_replay(app, initial_index=None):
    gs = app.game_state
    theme = app.theme_manager.current
    snapshots = build_replay_snapshots(gs)
    start_index = len(snapshots) - 1 if initial_index is None else max(0, min(initial_index, len(snapshots) - 1))

    review = getattr(app, "_game_review_cache", None)
    if review is None:
        review = compute_game_review(gs)
    worlds = worlds_over_time(snapshots)
    deduction_turns = sorted({e.turn for e in confirmed_card_events(gs)})

    win = tk.Toplevel(app.root)
    win.title("Replay")
    fit_geometry(win, 560, 600)
    win.configure(bg=theme.bg)

    tk.Label(win, text="Scrub through the game turn by turn", font=theme.heading_font(13), bg=theme.bg).pack(
        anchor="w", padx=12, pady=(12, 4)
    )

    # Created here (so `render` below can close over it) but *packed* only
    # at the very end of this function, after the slider/jump/close group --
    # this widget is the one that fills leftover space with
    # fill="both", expand=True, and packing an expand=True widget before
    # its bottom-anchored siblings can starve them of any actual height
    # once the window's content genuinely overflows the available space.
    label = tk.Label(win, text="", font=theme.body_font(10), justify="left", anchor="nw", bg=theme.panel_bg)

    def render(index):
        snap = snapshots[index].game_state
        sheet = snap.detective_sheet()
        lines = [f"After turn {index} of {len(snapshots) - 1}:", ""]
        for card, info in sheet.items():
            if info["status"] == "confirmed":
                lines.append(f"  {card.name} → {info['owner']}")

        world_count = worlds[index]
        lines.append("")
        lines.append(f"Valid worlds remaining: {'unknown' if world_count is None else f'{world_count:,}'}")

        lines.append("")
        lines.append("Top envelope candidate per category:")
        try:
            probs = snap.card_probabilities()
            for card_type in CardType:
                cards = [c for c in snap.cards if c.type == card_type]
                best = max(cards, key=lambda c: probs.get(c, {}).get(ENVELOPE, 0.0), default=None)
                if best is not None:
                    p = probs.get(best, {}).get(ENVELOPE, 0.0)
                    lines.append(f"  {card_type.value}: {best.name} ({p * 100:.0f}%)")
        except TooManyAmbiguousCardsError:
            lines.append("  Not enough information yet.")

        if review.largest_deduction is not None and review.largest_deduction.turn <= index:
            lines.append("")
            lines.append(f"Largest deduction so far: turn {review.largest_deduction.turn}")

        opportunities_so_far = [m for m in review.missed_opportunities if m.turn <= index]
        if opportunities_so_far:
            lines.append("")
            lines.append(f"Missed opportunities so far: {len(opportunities_so_far)}")

        if snap.is_solved():
            s, w, r = snap.solution()
            lines.append("")
            lines.append(f"SOLVED: {s.name} / {w.name} / {r.name}")
        label.config(text="\n".join(lines))

    slider = tk.Scale(
        win, from_=0, to=max(0, len(snapshots) - 1), orient="horizontal", label="Turn",
        command=lambda v: render(int(v)), bg=theme.bg,
    )

    jump_row = tk.Frame(win, bg=theme.bg)

    def _jump(delta):
        current = slider.get()
        candidates = [t for t in deduction_turns if (t > current if delta > 0 else t < current)]
        if not candidates:
            return
        target = min(candidates) if delta > 0 else max(candidates)
        slider.set(target)

    tk.Button(jump_row, text="◀ Prev deduction", font=theme.body_font(9), command=lambda: _jump(-1)).pack(side="left")
    tk.Button(jump_row, text="Next deduction ▶", font=theme.body_font(9), command=lambda: _jump(1)).pack(
        side="left", padx=(6, 0)
    )

    # Packed bottom-up (Close first, so it ends up truly at the bottom),
    # then the expand=True label last -- see the comment on `label` above.
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="bottom", pady=(0, 10))
    jump_row.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
    slider.pack(side="bottom", fill="x", padx=12, pady=(0, 6))
    label.pack(fill="both", expand=True, padx=12, pady=8)

    slider.set(start_index)
    render(start_index)
