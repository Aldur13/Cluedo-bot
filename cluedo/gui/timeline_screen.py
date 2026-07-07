import tkinter as tk

from cluedo.gui import suggestion_dialog


def open_timeline(app):
    gs = app.game_state
    theme = app.theme_manager.current
    win = tk.Toplevel(app.root)
    win.title("Timeline")
    win.geometry("560x420")
    win.configure(bg=theme.bg)

    tk.Label(win, text="Suggestion history", font=theme.heading_font(13), bg=theme.bg).pack(
        anchor="w", padx=12, pady=(12, 6)
    )

    listbox = tk.Listbox(win, font=theme.body_font(10))
    listbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def refresh():
        listbox.delete(0, "end")
        for i, s in enumerate(gs.history, start=1):
            suggester = gs.players[s.suggester_seat].name
            outcome = "no one showed"
            for r in s.responses:
                if r.outcome != "no_show":
                    who = gs.players[r.responder_seat].name
                    outcome = f"{who} showed {'a card' if r.outcome == 'shown_unseen' else r.shown_card.name}"
                    break
            listbox.insert(
                "end",
                f"Turn {i}: {suggester} suggested {s.suspect.name} / {s.weapon.name} / {s.room.name} — {outcome}",
            )

    refresh()

    def edit_selected():
        sel = listbox.curselection()
        if not sel:
            return
        suggestion = gs.history[sel[0]]
        suggestion_dialog.open_dialog(app, edit_suggestion=suggestion)
        win.after(150, refresh)

    def delete_selected():
        sel = listbox.curselection()
        if not sel:
            return
        suggestion = gs.history[sel[0]]
        gs.delete_suggestion(suggestion.suggestion_id)
        app.after_mutation()
        refresh()

    btns = tk.Frame(win, bg=theme.bg)
    btns.pack(pady=(0, 10))
    tk.Button(btns, text="Edit selected", command=edit_selected, font=theme.body_font(10)).pack(
        side="left", padx=6
    )
    tk.Button(btns, text="Delete selected", command=delete_selected, font=theme.body_font(10)).pack(
        side="left", padx=6
    )
    tk.Button(btns, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="left", padx=6)
