"""Edit Board Data dialog: lets the player correct the movement engine's
per-room tile distances and secret passages directly in the app, since the
bundled numbers (cluedo/data/movement_<edition_key>.json) are photo-derived
best-effort estimates, not measured tile counts. Saves via
cluedo.movement.data.save_movement_override, which writes to a durable
per-user location (%APPDATA%) rather than the bundled file -- the packaged
.exe is a PyInstaller onefile build, so writing into the bundled copy would
vanish the next time the app runs (see movement/data.py's module
docstring)."""
from __future__ import annotations

import tkinter as tk

from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.gui.widgets import ChoiceGrid
from cluedo.movement.data import (
    MovementData,
    delete_override,
    has_override,
    load_movement_data,
    save_movement_override,
)


def open_movement_edit_dialog(app, on_saved=None):
    """`on_saved`, if given, is called after a successful Save or Reset --
    e.g. so the Movement Strategy screen that opened this dialog can
    re-render immediately with the corrected numbers instead of requiring
    the player to reopen it."""
    gs = app.game_state
    theme = app.theme_manager.current
    edition_key = app._edition_key
    rooms = gs.config.rooms
    current = load_movement_data(edition_key, rooms)
    if current is None:
        return  # nothing to edit -- current_movement_graph() already gates this button on graph existing

    win = tk.Toplevel(app.root)
    win.title("Edit Board Data")
    win.geometry("560x680")
    win.configure(bg=theme.bg)

    tk.Label(
        win, text="Edit Board Data", font=theme.heading_font(16), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=16, pady=(14, 2))

    # Body scrolls -- the room count (and therefore content height) varies
    # per edition/board, and this dialog must stay usable (Save reachable)
    # regardless of window size, same as movement_screen.py's own body.
    scroll_outer, body = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=0, pady=(0, 6))

    tk.Label(
        body,
        text=(
            "Bundled distances are best-effort photo estimates, not measured tile counts. "
            "Correct any number below if you've counted the real board."
        ),
        font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text, wraplength=500, justify="left",
    ).pack(anchor="w", padx=16, pady=(0, 8))

    status_label = tk.Label(
        body,
        text="Currently using your saved corrections." if has_override(edition_key) else "Currently using the bundled estimate.",
        font=theme.body_font(9, "bold"), bg=theme.bg,
        fg=theme.accent if has_override(edition_key) else theme.muted_text,
    )
    status_label.pack(anchor="w", padx=16, pady=(0, 8))

    tk.Label(
        body, text="Distance from each room to the hallway hub (tiles):", font=theme.body_font(10, "bold"),
        bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=16)

    distances_frame = tk.Frame(body, bg=theme.bg)
    distances_frame.pack(fill="x", padx=16, pady=(4, 10))

    distance_vars: dict[str, tk.StringVar] = {}
    for i, room in enumerate(rooms):
        var = tk.StringVar(value=str(current.distances_to_hub[room]))
        distance_vars[room] = var
        row, col = divmod(i, 2)
        cell = tk.Frame(distances_frame, bg=theme.bg)
        cell.grid(row=row, column=col, sticky="w", padx=(0, 16), pady=2)
        tk.Label(cell, text=room, font=theme.body_font(9), bg=theme.bg, fg=theme.text, width=16, anchor="w").pack(
            side="left"
        )
        tk.Entry(cell, textvariable=var, width=5, font=theme.body_font(9)).pack(side="left")

    tk.Label(
        body, text="Secret passages (instant, no roll needed):", font=theme.body_font(10, "bold"), bg=theme.bg,
        fg=theme.text,
    ).pack(anchor="w", padx=16, pady=(4, 2))

    passages_list_frame = tk.Frame(body, bg=theme.bg)
    passages_list_frame.pack(fill="x", padx=16)

    error_label = tk.Label(body, text="", font=theme.body_font(9), bg=theme.bg, fg=theme.impossible, wraplength=500)
    error_label.pack(anchor="w", padx=16, pady=(4, 0))

    state = {"passages": list(current.secret_passages)}

    def _render_passages():
        for child in passages_list_frame.winfo_children():
            child.destroy()
        if not state["passages"]:
            tk.Label(
                passages_list_frame, text="(none)", font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text,
            ).pack(anchor="w")
        for pair in state["passages"]:
            row = tk.Frame(passages_list_frame, bg=theme.bg)
            row.pack(anchor="w", pady=1)
            tk.Label(
                row, text=f"{pair[0]} ↔ {pair[1]}", font=theme.body_font(9), bg=theme.bg, fg=theme.text,
            ).pack(side="left", padx=(0, 8))
            tk.Button(
                row, text="Remove", font=theme.body_font(8), command=lambda p=pair: _remove_passage(p),
            ).pack(side="left")

    def _remove_passage(pair):
        state["passages"] = [p for p in state["passages"] if p != pair]
        _render_passages()

    _render_passages()

    tk.Label(
        body, text="Add a passage:", font=theme.body_font(9, "bold"), bg=theme.bg, fg=theme.text,
    ).pack(anchor="w", padx=16, pady=(8, 2))

    add_row = tk.Frame(body, bg=theme.bg)
    add_row.pack(fill="x", padx=16, pady=(0, 10))

    room_a_var = tk.StringVar(value=rooms[0])
    room_b_var = tk.StringVar(value=rooms[1] if len(rooms) > 1 else rooms[0])
    picker_a = tk.Frame(add_row, bg=theme.bg)
    picker_a.pack(side="left", padx=(0, 8))
    ChoiceGrid(picker_a, list(rooms), room_a_var, theme=theme, columns=1).pack()
    picker_b = tk.Frame(add_row, bg=theme.bg)
    picker_b.pack(side="left")
    ChoiceGrid(picker_b, list(rooms), room_b_var, theme=theme, columns=1).pack()

    def _add_passage():
        a, b = room_a_var.get(), room_b_var.get()
        if a == b:
            error_label.config(text="A room can't have a secret passage to itself.")
            return
        pair_key = frozenset((a, b))
        if any(frozenset(p) == pair_key for p in state["passages"]):
            error_label.config(text=f"{a} ↔ {b} is already in the list.")
            return
        error_label.config(text="")
        state["passages"].append((a, b))
        _render_passages()

    tk.Button(body, text="Add Passage", font=theme.body_font(9), command=_add_passage).pack(
        anchor="w", padx=16, pady=(6, 10)
    )

    def _save():
        parsed_distances: dict[str, int] = {}
        for room, var in distance_vars.items():
            text = var.get().strip()
            if not text.isdigit() or int(text) <= 0:
                error_label.config(text=f"Distance for {room!r} must be a positive whole number, got {text!r}.")
                return
            parsed_distances[room] = int(text)

        data = MovementData(
            edition_key=edition_key,
            hub=current.hub,
            distances_to_hub=parsed_distances,
            secret_passages=tuple(state["passages"]),
        )
        save_movement_override(data)
        app.invalidate_movement_graph()
        if on_saved is not None:
            on_saved()
        win.destroy()

    def _reset():
        delete_override(edition_key)
        app.invalidate_movement_graph()
        if on_saved is not None:
            on_saved()
        win.destroy()

    # Outside the scrollable body, pinned to the bottom of the window --
    # always reachable regardless of how tall the room/passage list gets.
    button_row = tk.Frame(win, bg=theme.bg)
    button_row.pack(pady=(0, 14))
    tk.Button(button_row, text="Save", font=theme.body_font(10, "bold"), command=_save).pack(side="left", padx=6)
    if has_override(edition_key):
        tk.Button(button_row, text="Reset to Bundled Defaults", font=theme.body_font(10), command=_reset).pack(
            side="left", padx=6
        )
    tk.Button(button_row, text="Cancel", font=theme.body_font(10), command=win.destroy).pack(side="left", padx=6)
