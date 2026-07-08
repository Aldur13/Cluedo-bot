"""World Explorer: browse every remaining candidate envelope triple with its
exact probability and real supporting facts. `cluedo.probability.
triple_probabilities` is the data source -- see that function's docstring
for why "world" means a candidate (suspect, weapon, room) triple here, not a
full per-card assignment.

Enumeration can take a moment for a game with many ambiguous cards, so it
runs on a background thread with a `.after()` poll-style callback -- the one
async pattern in this codebase (everything else runs synchronously, since
nothing else is expensive enough to need it).
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from cluedo.analysis.live_events import owner_display_name
from cluedo.gui.scrollable_frame import build_scrollable_frame
from cluedo.probability import TooManyAmbiguousCardsError, triple_probabilities


def open_world_explorer(app):
    gs = app.game_state
    theme = app.theme_manager.current
    # Captured once, up front, on the main thread -- GameState mutations
    # replace `gs.engine` with a brand-new object (the atomic-mutation
    # pattern) rather than mutating the old one in place, so this reference
    # stays a fully consistent snapshot for the whole background computation
    # even if the player keeps playing while it runs.
    engine = gs.engine

    win = tk.Toplevel(app.root)
    win.title("World Explorer")
    win.geometry("820x680")
    win.configure(bg=theme.bg)

    header = tk.Frame(win, bg=theme.bg)
    header.pack(fill="x", padx=16, pady=(14, 6))
    tk.Label(header, text="World Explorer", font=theme.heading_font(18), bg=theme.bg, fg=theme.text).pack(anchor="w")
    status_label = tk.Label(header, text="Computing…", font=theme.body_font(9), bg=theme.bg, fg=theme.muted_text)
    status_label.pack(anchor="w")

    controls = tk.Frame(win, bg=theme.bg)
    controls.pack(fill="x", padx=16, pady=(0, 6))

    search_var = tk.StringVar()
    search_row = tk.Frame(controls, bg=theme.bg)
    search_row.pack(side="left", padx=(0, 12))
    tk.Label(search_row, text="Search:", bg=theme.bg, fg=theme.text, font=theme.body_font(9)).pack(side="left")
    tk.Entry(search_row, textvariable=search_var, width=18).pack(side="left", padx=(4, 0))

    suspect_filter = tk.StringVar(value="All")
    weapon_filter = tk.StringVar(value="All")
    room_filter = tk.StringVar(value="All")

    scroll_outer, list_area = build_scrollable_frame(win, theme)
    scroll_outer.pack(fill="both", expand=True, padx=16, pady=(0, 6))

    export_row = tk.Frame(win, bg=theme.bg)
    export_row.pack(fill="x", padx=16, pady=(0, 4))

    state = {"worlds": [], "sort_desc": True}

    def _render():
        for child in list_area.winfo_children():
            child.destroy()
        worlds = state["worlds"]
        query = search_var.get().strip().lower()
        filtered = []
        for w in worlds:
            if suspect_filter.get() != "All" and w.suspect.name != suspect_filter.get():
                continue
            if weapon_filter.get() != "All" and w.weapon.name != weapon_filter.get():
                continue
            if room_filter.get() != "All" and w.room.name != room_filter.get():
                continue
            if query and query not in f"{w.suspect.name} {w.weapon.name} {w.room.name}".lower():
                continue
            filtered.append(w)
        filtered.sort(key=lambda w: w.probability, reverse=state["sort_desc"])

        if not filtered:
            tk.Label(
                list_area, text="No matching worlds.", bg=theme.bg, fg=theme.muted_text, font=theme.body_font(10),
            ).pack(anchor="w", pady=8)
            return

        for i, w in enumerate(filtered, start=1):
            card_frame = tk.Frame(
                list_area, bg=theme.panel_bg, highlightbackground=theme.unknown, highlightthickness=1,
            )
            card_frame.pack(fill="x", pady=4)
            body = tk.Frame(card_frame, bg=theme.panel_bg)
            body.pack(fill="x", padx=10, pady=8)
            tk.Label(
                body, text=f"World #{i}", font=theme.body_font(10, "bold"), bg=theme.panel_bg, fg=theme.accent_dark,
            ).pack(anchor="w")
            tk.Label(
                body, text=f"{w.suspect.name}  ·  {w.weapon.name}  ·  {w.room.name}",
                font=theme.heading_font(12), bg=theme.panel_bg, fg=theme.text,
            ).pack(anchor="w", pady=(2, 2))
            tk.Label(
                body, text=f"Probability: {w.probability * 100:.0f}%", font=theme.body_font(10),
                bg=theme.panel_bg, fg=theme.confirmed if w.probability >= 0.999 else theme.accent,
            ).pack(anchor="w")

            facts = [
                f"{owner_display_name(gs, owner_id)} may own {card.name}" for card, owner_id in w.supporting_owner_facts
            ]
            facts.append("No contradiction exists")
            tk.Label(
                body, text="Reason still valid:\n" + "\n".join(f"  • {f}" for f in facts),
                font=theme.body_font(9), bg=theme.panel_bg, fg=theme.muted_text, justify="left",
            ).pack(anchor="w", pady=(4, 0))

            tk.Button(
                body, text="Copy world", font=theme.body_font(8), command=lambda w=w: _copy_world(w),
            ).pack(anchor="w", pady=(6, 0))

    def _copy_world(w):
        text = f"{w.suspect.name} / {w.weapon.name} / {w.room.name} ({w.probability * 100:.0f}%)"
        win.clipboard_clear()
        win.clipboard_append(text)

    def _export():
        worlds = state["worlds"]
        if not worlds:
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text file", "*.txt")])
        if not path:
            return
        lines = [
            f"World #{i}: {w.suspect.name} / {w.weapon.name} / {w.room.name} — {w.probability * 100:.0f}%"
            for i, w in enumerate(sorted(worlds, key=lambda w: w.probability, reverse=True), start=1)
        ]
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            messagebox.showinfo("Exported", f"Worlds exported to {path}")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))

    def _build_filter_row(label, var, options):
        row = tk.Frame(controls, bg=theme.bg)
        row.pack(side="left", padx=(0, 8))
        tk.Label(row, text=f"{label}:", bg=theme.bg, fg=theme.text, font=theme.body_font(9)).pack(side="left")
        menu = tk.OptionMenu(row, var, *(["All"] + options), command=lambda _v: _render())
        menu.config(font=theme.body_font(9))
        menu.pack(side="left")

    def _toggle_sort():
        state["sort_desc"] = not state["sort_desc"]
        state["sort_btn"].config(text="Sort: High→Low" if state["sort_desc"] else "Sort: Low→High")
        _render()

    def _on_computed(worlds, error):
        if error is not None:
            status_label.config(text=error)
            return
        state["worlds"] = worlds
        status_label.config(text=f"{len(worlds)} candidate world(s) remaining.")

        _build_filter_row("Suspect", suspect_filter, sorted({w.suspect.name for w in worlds}))
        _build_filter_row("Weapon", weapon_filter, sorted({w.weapon.name for w in worlds}))
        _build_filter_row("Room", room_filter, sorted({w.room.name for w in worlds}))

        sort_btn = tk.Button(controls, text="Sort: High→Low", font=theme.body_font(9), command=_toggle_sort)
        sort_btn.pack(side="left", padx=(8, 0))
        state["sort_btn"] = sort_btn

        tk.Button(export_row, text="Export", font=theme.body_font(9), command=_export).pack(side="left")

        _render()

    search_var.trace_add("write", lambda *_: _render())

    # Tk methods (including `.after()`) are only ever called from the main
    # thread here -- the worker thread only computes and pushes its result
    # onto a plain queue.Queue, which is thread-safe. The main thread polls
    # the queue via a self-rescheduling `.after()` loop, which also makes
    # this testable without a running mainloop() (tests can just call
    # `root.update()` in a loop; `.after()` scheduled from the main thread
    # works either way, unlike `.after()` called from a background thread).
    result_queue: "queue.Queue" = queue.Queue()

    def _worker():
        try:
            worlds = triple_probabilities(engine)
        except TooManyAmbiguousCardsError:
            result_queue.put(([], "Not enough information yet -- too many cards are still ambiguous."))
            return
        except Exception as exc:  # pragma: no cover -- defensive; surfaced to the user rather than silently lost
            result_queue.put(([], f"World Explorer failed: {exc}"))
            return
        result_queue.put((worlds, None))

    def _poll():
        try:
            worlds, error = result_queue.get_nowait()
        except queue.Empty:
            win.after(50, _poll)
            return
        _on_computed(worlds, error)

    threading.Thread(target=_worker, daemon=True).start()
    win.after(50, _poll)

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
