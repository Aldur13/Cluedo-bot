"""Deduction Graph: the full derivation tree behind one confirmed card,
rendered as nested, indented, expandable/collapsible rows -- an indented
tree rather than a drawn node-and-arrow canvas (see the v4.5 plan's scoping
notes for why: same information, far less new UI risk). Selecting a node
whose fact originated from a real suggestion jumps into Replay at that turn.

Data source: `cluedo.explain.build_explanation_tree`, a real nested
restructuring of the same premise chain `full_derivation_chain` already
walks -- nothing here invents a link that isn't already recorded by the
engine's own `ExplanationRegistry`.
"""
from __future__ import annotations

import tkinter as tk

from cluedo.explain import build_explanation_tree
from cluedo.gui import replay_screen
from cluedo.gui.scrollable_frame import build_scrollable_frame

_INDENT_PX = 22


def open_deduction_graph(app, card):
    gs = app.game_state
    theme = app.theme_manager.current

    win = tk.Toplevel(app.root)
    win.title(f"Deduction Graph — {card.name}")
    win.geometry("640x600")
    win.configure(bg=theme.bg)

    header = tk.Frame(win, bg=theme.bg)
    header.pack(fill="x", padx=16, pady=(14, 6))
    tk.Label(
        header, text=f"Why is {card.name} solved?", font=theme.heading_font(15), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w")

    scroll_outer, content = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=4, pady=(0, 6))

    explanation = gs.explain_card(card)
    if explanation is None:
        tk.Label(
            content, text="No derivation is recorded for this card yet.", bg=theme.bg, fg=theme.muted_text,
            font=theme.body_font(10),
        ).pack(anchor="w", padx=16, pady=12)
        tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
        return

    tree = build_explanation_tree(explanation, gs.engine.explanations)

    def _turn_for_source(source) -> "int | None":
        if source.origin != "suggestion" or source.suggestion_id is None:
            return None
        for i, suggestion in enumerate(gs.history):
            if suggestion.suggestion_id == source.suggestion_id:
                return i + 1
        return None

    def _render_node(parent, node, depth):
        row = tk.Frame(parent, bg=theme.bg)
        row.pack(fill="x", anchor="w", padx=(depth * _INDENT_PX, 0), pady=1)

        children_container = tk.Frame(parent, bg=theme.bg)

        has_children = bool(node.children)
        toggle = tk.Label(
            row, text=("▾" if has_children else "•"), bg=theme.bg, fg=theme.accent, font=theme.body_font(10, "bold"),
            width=2, cursor="hand2" if has_children else "arrow",
        )
        toggle.pack(side="left")

        tk.Label(
            row, text=node.explanation.conclusion.label, bg=theme.bg, fg=theme.text, font=theme.body_font(9),
            anchor="w", justify="left", wraplength=520 - depth * _INDENT_PX,
        ).pack(side="left", padx=(4, 6))

        turn = _turn_for_source(node.explanation.conclusion.source)
        if turn is not None:
            tk.Button(
                row, text=f"Jump to Turn {turn}", font=theme.body_font(8),
                command=lambda t=turn: replay_screen.open_replay(app, initial_index=t),
            ).pack(side="left")

        state = {"expanded": True}

        def _toggle(_e=None):
            if not has_children:
                return
            state["expanded"] = not state["expanded"]
            toggle.config(text="▾" if state["expanded"] else "▸")
            if state["expanded"]:
                children_container.pack(fill="x", anchor="w")
            else:
                children_container.pack_forget()

        toggle.bind("<Button-1>", _toggle)

        children_container.pack(fill="x", anchor="w")
        for child in node.children:
            _render_node(children_container, child, depth + 1)

    _render_node(content, tree, 0)

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
