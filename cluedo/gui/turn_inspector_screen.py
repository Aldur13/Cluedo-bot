"""Turn Inspector: every logged suggestion, clickable into a full per-turn
breakdown -- the suggestion and its real responses, which cards became newly
confirmed that turn, how the envelope probabilities and remaining-world
count changed, the real derivation chain for each new deduction, and the
replay state immediately before/after. Everything here is read from
`cluedo.history.build_replay_snapshots` and existing solver-core queries --
no new solver math, just composing what already exists per-turn.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.analysis.live_events import confirmed_card_events, owner_display_name
from cluedo.explain import render_narrative
from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.history import build_replay_snapshots
from cluedo.models import ENVELOPE
from cluedo.probability import TooManyAmbiguousCardsError
from cluedo.timeseries import worlds_over_time


def open_turn_inspector(app, turn_index: "int | None" = None):
    gs = app.game_state
    theme = app.theme_manager.current
    snapshots = build_replay_snapshots(gs)
    total_turns = len(gs.history)

    if total_turns == 0:
        from tkinter import messagebox

        messagebox.showinfo("Turn Inspector", "No suggestions have been logged yet.")
        return

    if turn_index is None or not (1 <= turn_index <= total_turns):
        turn_index = total_turns

    win = tk.Toplevel(app.root)
    win.title("Turn Inspector")
    win.geometry("760x680")
    win.configure(bg=theme.bg)

    header = tk.Frame(win, bg=theme.bg)
    header.pack(fill="x", padx=16, pady=(14, 4))
    tk.Label(header, text="Turn Inspector", font=theme.heading_font(18), bg=theme.bg, fg=theme.text).pack(anchor="w")

    scroll_outer, content = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    def _section(text):
        tk.Label(content, text=text, font=theme.heading_font(12), bg=theme.bg, fg=theme.accent_dark).pack(
            anchor="w", padx=16, pady=(12, 4)
        )

    def _line(text, *, fg=None, bold=False):
        tk.Label(
            content, text=text, font=theme.body_font(9, "bold" if bold else "normal"), bg=theme.bg,
            fg=fg or theme.text, justify="left", wraplength=680, anchor="w",
        ).pack(anchor="w", padx=16, pady=1)

    def _render(index: int):
        for child in content.winfo_children():
            child.destroy()

        suggestion = gs.history[index - 1]
        before = snapshots[index - 1].game_state
        after = snapshots[index].game_state

        _section(f"Turn {index} of {total_turns}")
        suggester_name = next(
            (p.name for p in gs.players if p.seat_index == suggestion.suggester_seat), f"Seat {suggestion.suggester_seat}"
        )
        _line(f"{suggester_name} suggested: {suggestion.suspect.name} · {suggestion.weapon.name} · {suggestion.room.name}", bold=True)
        for response in suggestion.responses:
            responder_name = next(
                (p.name for p in gs.players if p.seat_index == response.responder_seat), f"Seat {response.responder_seat}"
            )
            if response.outcome == "no_show":
                _line(f"  {responder_name}: no show")
            elif response.outcome == "shown_to_me":
                _line(f"  {responder_name}: showed {response.shown_card.name if response.shown_card else 'a card'}")
            else:
                _line(f"  {responder_name}: showed someone a card (not seen)")

        _section("New Deductions")
        events = [e for e in confirmed_card_events(gs) if e.turn == index]
        if not events:
            _line("No new cards were confirmed this turn.", fg=theme.muted_text)
        for event in events:
            owner = owner_display_name(gs, event.owner_id)
            _line(f"• {event.card.name} → {owner}", fg=theme.confirmed)
            explanation = after.explain_card(event.card)
            if explanation is not None:
                for line in render_narrative(explanation):
                    _line(f"    {line}", fg=theme.muted_text)

        _section("World Reduction")
        worlds = worlds_over_time(snapshots)
        before_worlds, after_worlds = worlds[index - 1], worlds[index]
        if before_worlds is not None and after_worlds is not None:
            pct = 0.0 if before_worlds <= 0 else (1.0 - after_worlds / before_worlds) * 100
            _line(f"{before_worlds:,} → {after_worlds:,} valid worlds ({pct:.0f}% eliminated)")
        else:
            _line("Not enough information yet to count exact worlds for this turn.", fg=theme.muted_text)

        _section("Envelope Probability Changes")
        try:
            before_probs = before.card_probabilities()
            after_probs = after.card_probabilities()
            trio = (suggestion.suspect, suggestion.weapon, suggestion.room)
            for card in trio:
                b = before_probs.get(card, {}).get(ENVELOPE, 0.0)
                a = after_probs.get(card, {}).get(ENVELOPE, 0.0)
                _line(f"{card.name}: {b * 100:.0f}% → {a * 100:.0f}%")
        except TooManyAmbiguousCardsError:
            _line("Not enough information yet for exact probabilities at this turn.", fg=theme.muted_text)

        _section("Replay State")
        for label, snap in (("Before", before), ("After", after)):
            _line(f"{label}:", bold=True)
            sheet = snap.detective_sheet()
            confirmed_lines = [
                f"  {card.name} → {info['owner']}" for card, info in sheet.items() if info["status"] == "confirmed"
            ]
            if confirmed_lines:
                for line in confirmed_lines:
                    _line(line, fg=theme.muted_text)
            else:
                _line("  (nothing confirmed yet)", fg=theme.muted_text)

    nav = tk.Frame(win, bg=theme.bg)
    nav.pack(fill="x", padx=16, pady=(0, 10))

    state = {"index": turn_index}

    def _go(delta):
        state["index"] = max(1, min(total_turns, state["index"] + delta))
        slider.set(state["index"])
        _render(state["index"])

    tk.Button(nav, text="◀ Prev", font=theme.body_font(9), command=lambda: _go(-1)).pack(side="left")
    slider = tk.Scale(
        nav, from_=1, to=total_turns, orient="horizontal", showvalue=True,
        command=lambda v: _render(int(v)), bg=theme.bg,
    )
    slider.pack(side="left", fill="x", expand=True, padx=8)
    slider.set(turn_index)
    tk.Button(nav, text="Next ▶", font=theme.body_font(9), command=lambda: _go(1)).pack(side="left")

    _render(turn_index)

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
