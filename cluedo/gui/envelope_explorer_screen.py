"""Envelope Explorer: a standalone-window version of the sidebar's Envelope
Analysis card (same Suspects/Weapons/Rooms tabs, top-3-by-default + Show
All -- see `cluedo/gui/panels/envelope_probabilities_panel.py`), plus a
per-card trend sparkline and a "recent change" delta computed from
`cluedo.timeseries.envelope_probability_over_time` over the replay history.
Row rendering is shared with the sidebar panel via
`cluedo/gui/envelope_rendering.py` to avoid duplicating the bar-drawing code.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.gui import sidebar_state
from cluedo.gui.envelope_rendering import render_probability_row, render_sparkline
from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.gui.window_geometry import fit_geometry
from cluedo.history import build_replay_snapshots
from cluedo.models import ENVELOPE, CardType
from cluedo.probability import TooManyAmbiguousCardsError
from cluedo.timeseries import envelope_probability_over_time

_TOP_N_DEFAULT = 3
_RECENT_WINDOW = 3
_SCREEN_KEY = "envelope_explorer"

_TABS = (
    (CardType.SUSPECT, "Suspects"),
    (CardType.WEAPON, "Weapons"),
    (CardType.ROOM, "Rooms"),
)


def open_envelope_explorer(app):
    gs = app.game_state
    theme = app.theme_manager.current
    snapshots = build_replay_snapshots(gs)

    win = tk.Toplevel(app.root)
    win.title("Envelope Explorer")
    fit_geometry(win, 560, 600)
    win.configure(bg=theme.bg)

    # Packed first, side="bottom", so Close stays reachable regardless of
    # how tall the probability list gets -- the scrollable body (below)
    # scrolls internally instead of pushing it off-screen.
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="bottom", pady=(0, 10))

    header = tk.Frame(win, bg=theme.bg)
    header.pack(fill="x", padx=16, pady=(14, 6))
    tk.Label(header, text="Envelope Explorer", font=theme.heading_font(16), bg=theme.bg, fg=theme.text).pack(anchor="w")

    active_tab = tk.StringVar(value=_TABS[0][1])
    tabs_row = tk.Frame(win, bg=theme.bg)
    tabs_row.pack(fill="x", padx=16, pady=(0, 6))
    tab_buttons: dict[str, tk.Button] = {}

    def _style_tabs():
        for name, btn in tab_buttons.items():
            if name == active_tab.get():
                btn.config(bg=theme.accent, fg="white", relief="sunken")
            else:
                btn.config(bg=theme.panel_bg, fg=theme.text, relief="raised")

    scroll_outer, list_area = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=16, pady=(0, 6))

    def _show_all_key(tab_name: str) -> str:
        return f"{_SCREEN_KEY}.show_all.{tab_name}"

    def _render_active_tab():
        for child in list_area.winfo_children():
            child.destroy()

        try:
            probs = gs.card_probabilities()
        except TooManyAmbiguousCardsError:
            tk.Label(
                list_area, text="Not enough information yet for probabilities.", bg=theme.bg, fg=theme.muted_text,
                font=theme.body_font(10), wraplength=480, justify="left",
            ).pack(anchor="w")
            return

        tab_name = active_tab.get()
        card_type = next(ct for ct, name in _TABS if name == tab_name)
        cards = [c for c in gs.cards if c.type == card_type]
        cards.sort(key=lambda c: probs.get(c, {}).get(ENVELOPE, 0.0), reverse=True)

        show_all = sidebar_state.get_flag(_show_all_key(tab_name), False)
        visible = cards if show_all else cards[:_TOP_N_DEFAULT]

        for candidate_card in visible:
            p = probs.get(candidate_card, {}).get(ENVELOPE, 0.0)
            row = render_probability_row(list_area, theme, candidate_card.name, p, bar_width=160)

            trend = envelope_probability_over_time(snapshots, candidate_card)
            render_sparkline(row, theme, trend).pack(side="left", padx=(6, 6))

            known = [v for v in trend if v is not None]
            recent = known[-_RECENT_WINDOW:]
            if len(recent) >= 2:
                delta = (recent[-1] - recent[0]) * 100
                sign = "+" if delta >= 0 else ""
                tk.Label(
                    row, text=f"{sign}{delta:.0f}% recently", bg=theme.panel_bg, fg=theme.muted_text,
                    font=theme.body_font(8),
                ).pack(side="left")

        if len(cards) > _TOP_N_DEFAULT:
            tk.Button(
                list_area, text="Show Less" if show_all else f"Show All ({len(cards)})", font=theme.body_font(8),
                command=lambda: _toggle_show_all(tab_name),
            ).pack(anchor="w", pady=(6, 0))

    def _toggle_show_all(tab_name: str):
        sidebar_state.toggle_flag(_show_all_key(tab_name), False)
        _render_active_tab()

    def _select_tab(name: str):
        active_tab.set(name)
        _style_tabs()
        _render_active_tab()

    for _card_type, name in _TABS:
        btn = tk.Button(tabs_row, text=name, font=theme.body_font(9), command=lambda n=name: _select_tab(n))
        btn.pack(side="left", padx=(0, 4))
        tab_buttons[name] = btn
    _style_tabs()
    _render_active_tab()
