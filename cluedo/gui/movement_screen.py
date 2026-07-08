"""Movement Strategy screen: the full "chess engine for Cluedo" view --
room rankings (distance + reach probability + advisor info gain + overall
score), reachability buckets, a route-preview breadcrumb, a "what if I roll
N" simulator, a headline best-move-recommendation, and a schematic (not
pixel-accurate -- no measured board coordinates exist) board overlay with
the previewed route highlighted.

Synchronous and cheap: the board graph tops out at 9 rooms + 1 hub node, so
unlike World Explorer there's no need for the background-thread pattern."""
from __future__ import annotations

import tkinter as tk

from cluedo.gui import movement_edit_dialog
from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.gui.widgets import ChoiceGrid
from cluedo.movement.scoring import rank_rooms

# Schematic layout (fractions of the canvas, NOT measured board coordinates)
# for the swedish_2012 edition's 9 rooms -- corner rooms are placed at the
# four canvas corners in their confirmed secret-passage diagonal pairing
# (Köket <-> Garaget, Vardagsrummet <-> Sovrummet). A future edition with
# movement data but no hand-authored layout here simply skips the canvas
# (see _render_board) rather than guessing at one from distances alone,
# which are under-constrained for 2D placement.
_ROOM_LAYOUT = {
    "Köket": (0.12, 0.12),
    "Vardagsrummet": (0.88, 0.12),
    "Garaget": (0.88, 0.88),
    "Sovrummet": (0.12, 0.88),
    "Badrummet": (0.5, 0.06),
    "Matsalen": (0.94, 0.5),
    "Spelrummet": (0.5, 0.94),
    "Arbetsrummet": (0.06, 0.5),
    "Gården": (0.7, 0.72),
}


def _display_path(path: tuple[str, ...], hub: str) -> str:
    return " → ".join("Hallway" if node == hub else node for node in path)


def _best_triple_for_room(game_state, room_name):
    """The advisor's own best (suspect, weapon) pairing for a given room --
    purely a display cross-reference; movement/scoring.py stays room-level
    only, this is the one place the GUI asks "which exact triple" for the
    headline recommendation."""
    from cluedo.advisor import rank_candidates

    candidates = [
        c for c in rank_candidates(game_state, top_k=24)
        if c.room.name == room_name and c.expected_info_gain is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda c: c.expected_info_gain)


def open_movement_screen(app):
    gs = app.game_state
    theme = app.theme_manager.current
    graph = app.current_movement_graph()

    win = tk.Toplevel(app.root)
    win.title("Movement Strategy")
    win.geometry("900x760")
    win.configure(bg=theme.bg)

    header = tk.Frame(win, bg=theme.bg)
    header.pack(fill="x", padx=16, pady=(14, 4))
    tk.Label(
        header, text="Movement Strategy", font=theme.heading_font(18), bg=theme.bg, fg=theme.text,
    ).pack(side="left")

    def _reopen():
        # Simplest correct way to reflect a saved/reset board-data edit:
        # close this snapshot and rebuild a fresh one from the (now
        # invalidated) graph, rather than threading a live-refresh path
        # through both of this screen's early-return branches.
        win.destroy()
        app.open_movement_screen()

    if graph is not None:
        tk.Button(
            header, text="Edit Board Data", font=theme.body_font(9),
            command=lambda: movement_edit_dialog.open_movement_edit_dialog(app, on_saved=_reopen),
        ).pack(side="right")

    if graph is None:
        tk.Label(
            win, text="No movement data for this edition yet.", font=theme.body_font(11),
            bg=theme.bg, fg=theme.muted_text,
        ).pack(anchor="w", padx=16, pady=(0, 10))
        tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=10)
        return

    if gs.current_room is None:
        tk.Label(
            win, text="Set your current position in the Dice Analysis panel to see movement recommendations.",
            font=theme.body_font(11), bg=theme.bg, fg=theme.muted_text, wraplength=800, justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=10)
        return

    scroll_outer, body = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=16, pady=(0, 6))

    # --------------------------------------------------------- best move
    best_move_frame = tk.Frame(body, bg=theme.solved_bg, highlightbackground=theme.unknown, highlightthickness=1)
    best_move_frame.pack(fill="x", pady=(0, 10))
    best_move_label = tk.Label(
        best_move_frame, text="", font=theme.heading_font(13), bg=theme.solved_bg, fg=theme.solved_text,
        justify="left", anchor="w", padx=10, pady=8, wraplength=820,
    )
    best_move_label.pack(fill="x")

    # ------------------------------------------------------ room rankings
    tk.Label(
        body, text="Room Rankings", font=theme.body_font(12, "bold"), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", pady=(4, 2))
    rankings_table = tk.Frame(body, bg=theme.bg)
    rankings_table.pack(fill="x", pady=(0, 10))

    # --------------------------------------------------- reachability buckets
    tk.Label(
        body, text="Reachability", font=theme.body_font(12, "bold"), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", pady=(4, 2))
    reachability_frame = tk.Frame(body, bg=theme.bg)
    reachability_frame.pack(fill="x", pady=(0, 10))

    # ------------------------------------------------------- route preview
    tk.Label(
        body, text="Route Preview", font=theme.body_font(12, "bold"), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", pady=(4, 2))
    destination_var = tk.StringVar(value="")
    route_picker_frame = tk.Frame(body, bg=theme.bg)
    route_picker_frame.pack(fill="x")
    route_label = tk.Label(
        body, text="", font=theme.body_font(10), bg=theme.bg, fg=theme.text, justify="left", anchor="w",
        wraplength=820,
    )
    route_label.pack(anchor="w", pady=(4, 10))

    # ---------------------------------------------------- movement simulator
    tk.Label(
        body, text="Movement Simulator — “What if I roll…”", font=theme.body_font(12, "bold"),
        bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", pady=(4, 2))
    roll_var = tk.StringVar(value="")
    roll_picker_frame = tk.Frame(body, bg=theme.bg)
    roll_picker_frame.pack(fill="x")
    simulator_label = tk.Label(
        body, text="", font=theme.body_font(10), bg=theme.bg, fg=theme.text, justify="left", anchor="w",
        wraplength=820,
    )
    simulator_label.pack(anchor="w", pady=(4, 10))

    # -------------------------------------------------------- board overlay
    tk.Label(
        body, text="Board Overlay (schematic — not to scale)", font=theme.body_font(12, "bold"),
        bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", pady=(4, 2))
    canvas_size = 360
    board_canvas = tk.Canvas(body, width=canvas_size, height=canvas_size, bg=theme.panel_bg, highlightthickness=1,
                              highlightbackground=theme.unknown)
    board_canvas.pack(pady=(0, 14))

    state = {"sort_key": "overall_score", "sort_desc": True, "recommendation": None}

    def _render_rankings():
        for child in rankings_table.winfo_children():
            child.destroy()
        rankings = list(state["recommendation"].rankings)

        columns = [
            ("room", "Room"),
            ("distance", "Distance"),
            ("reach_probability", "Reach %"),
            ("expected_info_gain", "Info Gain"),
            ("overall_score", "Score"),
        ]

        def _sort_value(ranking, key):
            value = getattr(ranking, key)
            if value is None:
                return -1.0
            return value

        def _make_sorter(key):
            def _sort():
                if state["sort_key"] == key:
                    state["sort_desc"] = not state["sort_desc"]
                else:
                    state["sort_key"] = key
                    state["sort_desc"] = True
                _render_rankings()
            return _sort

        for col_index, (key, header) in enumerate(columns):
            arrow = ""
            if state["sort_key"] == key:
                arrow = " ▾" if state["sort_desc"] else " ▴"
            tk.Button(
                rankings_table, text=header + arrow, font=theme.body_font(9, "bold"), relief="flat",
                bg=theme.bg, fg=theme.text, command=_make_sorter(key),
            ).grid(row=0, column=col_index, sticky="w", padx=6)

        rankings.sort(key=lambda r: _sort_value(r, state["sort_key"]), reverse=state["sort_desc"])
        best_room = state["recommendation"].best.room if state["recommendation"].best else None

        for row_index, ranking in enumerate(rankings, start=1):
            is_best = ranking.room == best_room
            row_bg = theme.solved_bg if is_best else theme.bg
            row_fg = theme.solved_text if is_best else theme.text
            values = [
                ranking.room,
                str(ranking.distance),
                f"{round(ranking.reach_probability * 100)}%",
                "—" if ranking.expected_info_gain is None else f"{round(ranking.expected_info_gain * 100)}%",
                f"{ranking.overall_score:.3f}",
            ]
            for col_index, value in enumerate(values):
                tk.Label(
                    rankings_table, text=value, font=theme.body_font(9), bg=row_bg, fg=row_fg, anchor="w",
                ).grid(row=row_index, column=col_index, sticky="w", padx=6, pady=1)

    def _render_reachability():
        for child in reachability_frame.winfo_children():
            child.destroy()
        rankings = state["recommendation"].rankings
        this_turn = sorted((r for r in rankings if r.reachable_this_turn), key=lambda r: r.distance)
        not_reachable = sorted((r for r in rankings if not r.reachable_this_turn), key=lambda r: r.distance)

        def _bucket(title, rooms, color):
            col = tk.Frame(reachability_frame, bg=theme.bg)
            col.pack(side="left", anchor="n", padx=(0, 24))
            tk.Label(col, text=title, font=theme.body_font(10, "bold"), bg=theme.bg, fg=color).pack(anchor="w")
            if not rooms:
                tk.Label(col, text="(none)", font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text).pack(
                    anchor="w"
                )
            for r in rooms:
                tk.Label(
                    col, text=f"{r.room} (d={r.distance})", font=theme.body_font(9), bg=theme.bg, fg=theme.text,
                ).pack(anchor="w")

        _bucket("Reach This Turn", this_turn, theme.confirmed)
        _bucket("Not Reachable This Turn", not_reachable, theme.impossible)

    def _render_route_preview():
        dest = destination_var.get()
        if not dest:
            route_label.config(text="")
            return
        route = graph.route(gs.current_room, dest)
        path_text = _display_path(route.path, graph.hub)
        if route.via_secret_passage:
            desc = f"{path_text}  —  instant via secret passage (saves {route.moves_saved} tile(s))"
        else:
            desc = f"{path_text}  —  distance {route.distance}, needs a roll of {route.distance}+ this turn"
        route_label.config(text=desc)
        _render_board(highlight_path=route.path)

    def _render_simulator():
        roll_text = roll_var.get()
        if not roll_text:
            simulator_label.config(text="")
            return
        roll = int(roll_text)
        reachable = graph.reachable_rooms(gs.current_room, max_distance=roll)
        if not reachable:
            simulator_label.config(text=f"Rolling {roll}: no new room is reachable this turn.")
            return
        room_list = ", ".join(f"{r.destination} (d={r.distance})" for r in reachable)
        simulator_label.config(text=f"Rolling {roll}, you could reach: {room_list}")

    def _render_board(highlight_path=()):
        board_canvas.delete("all")
        rooms = graph.all_rooms()
        if not all(room in _ROOM_LAYOUT for room in rooms):
            board_canvas.create_text(
                canvas_size / 2, canvas_size / 2, text="No board layout available for this edition.",
                fill=theme.muted_text, font=theme.body_font(9), width=canvas_size - 20,
            )
            return

        hub_xy = (canvas_size / 2, canvas_size / 2)
        room_xy = {room: (fx * canvas_size, fy * canvas_size) for room, (fx, fy) in _ROOM_LAYOUT.items()}

        for room, xy in room_xy.items():
            board_canvas.create_line(*hub_xy, *xy, fill=theme.unknown, width=1)
        for a, b in graph.secret_passages:
            board_canvas.create_line(*room_xy[a], *room_xy[b], fill=theme.accent_dark, width=1, dash=(4, 2))

        if len(highlight_path) >= 2:
            highlight_xy = [hub_xy if node == graph.hub else room_xy[node] for node in highlight_path]
            for (x1, y1), (x2, y2) in zip(highlight_xy, highlight_xy[1:]):
                board_canvas.create_line(x1, y1, x2, y2, fill=theme.accent, width=3)

        board_canvas.create_oval(
            hub_xy[0] - 8, hub_xy[1] - 8, hub_xy[0] + 8, hub_xy[1] + 8, fill=theme.possible, outline=""
        )
        for room, (x, y) in room_xy.items():
            is_current = room == gs.current_room
            fill = theme.accent if is_current else theme.panel_bg
            text_fg = "white" if is_current else theme.text
            board_canvas.create_rectangle(x - 34, y - 12, x + 34, y + 12, fill=fill, outline=theme.unknown)
            board_canvas.create_text(x, y, text=room, fill=text_fg, font=theme.body_font(7))

    def _refresh_all():
        state["recommendation"] = rank_rooms(gs, graph)
        best = state["recommendation"].best
        if best is not None:
            triple = _best_triple_for_room(gs, best.room)
            route = graph.route(gs.current_room, best.room)
            move_text = _display_path(route.path, graph.hub)
            if triple is not None:
                suggestion_text = f"Suggestion: {triple.suspect.name} / {triple.weapon.name} / {best.room}"
            else:
                suggestion_text = f"Suggest in: {best.room}"
            best_move_label.config(
                text=(
                    f"Move: {move_text}\n{suggestion_text}\n"
                    f"Expected overall score: {best.overall_score:.3f}  ·  {best.rationale}"
                )
            )
        else:
            best_move_label.config(text="No recommendation available yet.")

        _render_rankings()
        _render_reachability()
        if not destination_var.get():
            # .set() always fires the trace-bound _render_route_preview,
            # even if the value happens to be unchanged -- covers the board
            # canvas's first draw too, so no separate initial render call
            # is needed here.
            destination_var.set(best.room if best else graph.all_rooms()[0])
        else:
            _render_route_preview()

    ChoiceGrid(route_picker_frame, list(graph.all_rooms()), destination_var, theme=theme, columns=4).pack(fill="x")
    destination_var.trace_add("write", lambda *_: _render_route_preview())

    ChoiceGrid(roll_picker_frame, [str(n) for n in range(2, 13)], roll_var, theme=theme, columns=6).pack(fill="x")
    roll_var.trace_add("write", lambda *_: _render_simulator())

    _refresh_all()

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
