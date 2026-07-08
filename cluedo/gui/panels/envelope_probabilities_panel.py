"""Envelope Analysis panel: per-card horizontal bars showing each card's
probability of being the envelope card, split into Suspects/Weapons/Rooms
tabs instead of one long stacked list.

Each tab shows only the top 3 highest-probability cards by default -- most
cards sit at 0% for most of a game, and stacking all of them wastes sidebar
space -- with a "Show All" toggle (remembered per tab via
cluedo.gui.sidebar_state) to see the rest.

Mirrors main_screen.py's existing try/except around `TooManyAmbiguousCardsError`
-- when too many cards are still ambiguous for an exact count, this shows a
plain "not enough information yet" message instead of guessing.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.gui import sidebar_state
from cluedo.gui.envelope_rendering import render_probability_row
from cluedo.gui.widgets import CollapsibleCard
from cluedo.models import ENVELOPE, CardType
from cluedo.probability import TooManyAmbiguousCardsError

_TOP_N_DEFAULT = 3
_CARD_KEY = "envelope_analysis"

_TABS = (
    (CardType.SUSPECT, "Suspects"),
    (CardType.WEAPON, "Weapons"),
    (CardType.ROOM, "Rooms"),
)


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Envelope Analysis", key=_CARD_KEY)
    card.pack(fill="x")
    body = card.body

    active_tab = tk.StringVar(value=_TABS[0][1])

    tabs_row = tk.Frame(body, bg=theme.panel_bg)
    tabs_row.pack(fill="x", pady=(0, 6))

    tab_buttons: dict[str, tk.Button] = {}

    def _style_tabs():
        for name, btn in tab_buttons.items():
            if name == active_tab.get():
                btn.config(bg=theme.accent, fg="white", relief="sunken")
            else:
                btn.config(bg=theme.panel_bg, fg=theme.text, relief="raised")

    list_area = tk.Frame(body, bg=theme.panel_bg)
    list_area.pack(fill="x")

    show_all_button = tk.Button(body, text="Show All", font=theme.body_font(8))

    def _show_all_key(tab_name: str) -> str:
        return f"{_CARD_KEY}.show_all.{tab_name}"

    state = {"game_state": None}

    def _render_active_tab():
        for child in list_area.winfo_children():
            child.destroy()
        show_all_button.pack_forget()

        game_state = state["game_state"]
        if game_state is None:
            tk.Label(
                list_area, text="No game in progress.", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9),
            ).pack(anchor="w")
            return

        try:
            probs = game_state.card_probabilities()
        except TooManyAmbiguousCardsError:
            tk.Label(
                list_area, text="Not enough information yet for probabilities.",
                bg=theme.panel_bg, fg=theme.muted_text, font=theme.body_font(9),
                wraplength=280, justify="left",
            ).pack(anchor="w")
            return

        tab_name = active_tab.get()
        card_type = next(ct for ct, name in _TABS if name == tab_name)
        cards = [c for c in game_state.cards if c.type == card_type]
        cards.sort(key=lambda c: probs.get(c, {}).get(ENVELOPE, 0.0), reverse=True)

        show_all = sidebar_state.get_flag(_show_all_key(tab_name), False)
        visible = cards if show_all else cards[:_TOP_N_DEFAULT]
        for candidate_card in visible:
            p = probs.get(candidate_card, {}).get(ENVELOPE, 0.0)
            row = render_probability_row(list_area, theme, candidate_card.name, p)
            # Click any row to see the real derivation chain behind that
            # card's probability (Probability Breakdown, spec item 9) --
            # only meaningful once something is actually known about it.
            if hasattr(app, "open_explain"):
                row.bind("<Button-1>", lambda _e, c=candidate_card: app.open_explain(c))
                for child in row.winfo_children():
                    child.bind("<Button-1>", lambda _e, c=candidate_card: app.open_explain(c))

        if len(cards) > _TOP_N_DEFAULT:
            show_all_button.config(
                text="Show Less" if show_all else f"Show All ({len(cards)})",
                command=lambda: _toggle_show_all(tab_name),
            )
            show_all_button.pack(anchor="w", pady=(4, 0))

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

    def refresh(game_state):
        state["game_state"] = game_state
        _render_active_tab()

    frame.refresh = refresh
    refresh(None)
    return frame
