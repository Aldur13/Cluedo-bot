import tkinter as tk

from cluedo.gui import suggestion_dialog
from cluedo.gui.window_geometry import fit_geometry


def open_timeline(app):
    gs = app.game_state
    theme = app.theme_manager.current
    win = tk.Toplevel(app.root)
    win.title("Timeline")
    fit_geometry(win, 560, 420)
    win.configure(bg=theme.bg)

    tk.Label(win, text="Suggestion history", font=theme.heading_font(13), bg=theme.bg).pack(
        anchor="w", padx=12, pady=(12, 6)
    )

    listbox = tk.Listbox(win, font=theme.body_font(10))
    listbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    def refresh():
        if not win.winfo_exists():
            return
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

    # Timeline is non-modal -- the Suggestion dialog can be opened right
    # over it to log a new entry -- so it must react to mutations made while
    # it's still open, not just to edits/deletes it triggers itself.
    app.add_mutation_listener(refresh)
    win.bind("<Destroy>", lambda e: app.remove_mutation_listener(refresh) if e.widget is win else None, add="+")

    def edit_selected():
        sel = listbox.curselection()
        if not sel:
            return
        suggestion = gs.history[sel[0]]
        dialog = suggestion_dialog.open_dialog(app, edit_suggestion=suggestion)
        if dialog is not None:
            # Refresh once the edit dialog actually closes (committed or
            # canceled) -- a fixed after()-delay fired while the dialog was
            # still open, so the list never reflected the committed edit.
            # A <Destroy> binding on a Toplevel also fires for every
            # descendant widget, hence the e.widget check.
            dialog.bind("<Destroy>", lambda e: refresh() if e.widget is dialog else None, add="+")

    def delete_selected():
        sel = listbox.curselection()
        if not sel:
            return
        suggestion = gs.history[sel[0]]
        gs.delete_suggestion(suggestion.suggestion_id)
        app.after_mutation()  # runs refresh() via the mutation-listener registered above

    # `before=listbox` matters: listbox is packed with fill="both",
    # expand=True, so appending btns after it (a plain trailing pack()) can
    # starve it of any actual height once the history list overflows --
    # inserting it back before listbox in the packer's slave order is what
    # actually reserves its space.
    btns = tk.Frame(win, bg=theme.bg)
    btns.pack(side="bottom", pady=(0, 10), before=listbox)
    tk.Button(btns, text="Edit selected", command=edit_selected, font=theme.body_font(10)).pack(
        side="left", padx=6
    )
    tk.Button(btns, text="Delete selected", command=delete_selected, font=theme.body_font(10)).pack(
        side="left", padx=6
    )
    tk.Button(btns, text="Close", command=win.destroy, font=theme.body_font(10)).pack(side="left", padx=6)
