"""Dice Analysis panel: given the app user's own current board position (set
here via a room picker), shows the best destination this turn, its route,
distance, minimum roll needed, and the full 2d6 roll-probability breakdown.
Combines cluedo.movement's graph/dice/scoring with the existing advisor's
information-gain scoring -- gracefully reports "no movement data" for
editions with no bundled board (e.g. classic_uk/classic_us) instead of
showing a broken or empty panel, matching ai_insights_panel.py's "not
enough data yet" convention for advisory content."""
from __future__ import annotations

import tkinter as tk

from cluedo.gui.widgets import ChoiceGrid, CollapsibleCard
from cluedo.movement.scoring import rank_rooms


def _format_route(route_path: tuple[str, ...], hub: str) -> str:
    return " → ".join("Hallway" if node == hub else node for node in route_path)


def build(parent, theme, app) -> tk.Frame:
    frame = tk.Frame(parent, bg=theme.bg)
    card = CollapsibleCard(frame, theme, title="Dice Analysis", key="dice_analysis")
    card.pack(fill="x")
    body = card.body

    message_label = tk.Label(
        body, text="", justify="left", wraplength=280, bg=theme.panel_bg, fg=theme.muted_text,
        font=theme.body_font(9),
    )
    message_label.pack(anchor="w")

    picker_holder = tk.Frame(body, bg=theme.panel_bg)
    result_holder = tk.Frame(body, bg=theme.panel_bg)

    room_var = tk.StringVar(value="")

    def _on_room_selected(*_args):
        if app.game_state is None:
            return
        selected = room_var.get()
        if not selected or selected == app.game_state.current_room:
            return
        app.game_state.set_current_room(selected)
        app.after_mutation()

    room_var.trace_add("write", _on_room_selected)

    def refresh(game_state):
        for holder in (picker_holder, result_holder):
            for child in holder.winfo_children():
                child.destroy()
        picker_holder.pack_forget()
        result_holder.pack_forget()

        if game_state is None:
            message_label.config(text="No game in progress.")
            return

        graph = app.current_movement_graph()
        if graph is None:
            message_label.config(text="No movement data for this edition yet.")
            return

        message_label.config(text="")

        rooms = game_state.config.rooms
        if room_var.get() != (game_state.current_room or ""):
            room_var.set(game_state.current_room or "")

        tk.Label(
            picker_holder, text="Your current room:", bg=theme.panel_bg, fg=theme.text,
            font=theme.body_font(9, "bold"), anchor="w",
        ).pack(anchor="w", pady=(0, 2))
        ChoiceGrid(picker_holder, rooms, room_var, theme=theme, columns=2, bg=theme.panel_bg).pack(fill="x")
        picker_holder.pack(fill="x", pady=(0, 6))

        recommendation = rank_rooms(game_state, graph)
        if recommendation.unsupported_reason is not None:
            tk.Label(
                result_holder, text=recommendation.unsupported_reason, bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(9), wraplength=280, justify="left",
            ).pack(anchor="w")
            result_holder.pack(fill="x")
            return

        best = recommendation.best
        route = graph.route(recommendation.current_room, best.room)
        tk.Label(
            result_holder, text=f"Best destination: {best.room}", bg=theme.panel_bg, fg=theme.accent,
            font=theme.body_font(10, "bold"), anchor="w",
        ).pack(anchor="w")
        tk.Label(
            result_holder, text=_format_route(route.path, graph.hub), bg=theme.panel_bg, fg=theme.text,
            font=theme.body_font(9), anchor="w", wraplength=280, justify="left",
        ).pack(anchor="w", pady=(2, 4))

        instant = route.via_secret_passage or route.distance == 0
        if route.via_secret_passage:
            distance_text = f"Distance: instant (secret passage, saves {route.moves_saved} tile(s))"
        elif route.distance == 0:
            distance_text = "Distance: 0 (you're already here)"
        else:
            distance_text = f"Distance: {route.distance}  ·  Min roll needed: {route.distance}"
        tk.Label(
            result_holder, text=distance_text, bg=theme.panel_bg, fg=theme.text, font=theme.body_font(9),
            anchor="w",
        ).pack(anchor="w")

        if not instant:
            table_frame = tk.Frame(result_holder, bg=theme.panel_bg)
            table_frame.pack(anchor="w", pady=(4, 0))
            tk.Label(
                table_frame, text="Chance to reach this turn:", bg=theme.panel_bg, fg=theme.muted_text,
                font=theme.body_font(8, "bold"), anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w")
            dice_table = _dice_table(route.distance)
            for i, (roll, pct) in enumerate(dice_table, start=1):
                tk.Label(
                    table_frame, text=f"Roll {roll}+:", bg=theme.panel_bg, fg=theme.text,
                    font=theme.body_font(8), anchor="w",
                ).grid(row=i, column=0, sticky="w", padx=(0, 6))
                tk.Label(
                    table_frame, text=f"{pct}%", bg=theme.panel_bg, fg=theme.text,
                    font=theme.body_font(8), anchor="w",
                ).grid(row=i, column=1, sticky="w")

        result_holder.pack(fill="x")

    frame.refresh = refresh
    refresh(None)
    return frame


def _dice_table(distance: int) -> list[tuple[int, int]]:
    """[(roll_threshold, percent)] for thresholds from `distance` up to 12,
    e.g. distance=7 -> [(7,58),(8,42),(9,28),(10,17),(11,8),(12,3)]."""
    from cluedo.movement.dice import full_distribution

    dp = full_distribution(distance)
    thresholds = [n for n in range(max(distance, 2), 13)]
    return [(n, round(dp.probabilities[n] * 100)) for n in thresholds]
