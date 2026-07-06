import tkinter as tk
from tkinter import messagebox

from cluedo.engine import ContradictionError
from cluedo.gui import theme
from cluedo.models import SuggestionResponse


def open_dialog(app, edit_suggestion=None):
    gs = app.game_state
    if gs is None:
        return

    win = tk.Toplevel(app.root)
    win.title("Edit Suggestion" if edit_suggestion else "Log Suggestion")
    win.geometry("440x520")
    win.configure(bg=theme.BG)
    win.grab_set()

    tk.Label(win, text="Suggesting player:", font=theme.body_font(10), bg=theme.BG).pack(
        anchor="w", padx=14, pady=(14, 2)
    )
    default_suggester = gs.players[edit_suggestion.suggester_seat].name if edit_suggestion else gs.players[0].name
    suggester_var = tk.StringVar(value=default_suggester)
    tk.OptionMenu(win, suggester_var, *[p.name for p in gs.players]).pack(fill="x", padx=14)

    def card_dropdown(label, names, default):
        tk.Label(win, text=label, font=theme.body_font(10), bg=theme.BG).pack(anchor="w", padx=14, pady=(10, 2))
        var = tk.StringVar(value=default)
        tk.OptionMenu(win, var, *names).pack(fill="x", padx=14)
        return var

    suspect_var = card_dropdown(
        "Suspect:", list(gs.config.suspects), edit_suggestion.suspect.name if edit_suggestion else gs.config.suspects[0]
    )
    weapon_var = card_dropdown(
        "Weapon:", list(gs.config.weapons), edit_suggestion.weapon.name if edit_suggestion else gs.config.weapons[0]
    )
    room_var = card_dropdown(
        "Room:", list(gs.config.rooms), edit_suggestion.room.name if edit_suggestion else gs.config.rooms[0]
    )

    responses_frame = tk.Frame(win, bg=theme.BG)
    responses_frame.pack(fill="both", expand=True, padx=14, pady=12)
    response_state: dict[int, tuple[tk.StringVar, tk.StringVar]] = {}

    def seat_for_name(name):
        return next(p.seat_index for p in gs.players if p.name == name)

    def rebuild_responses():
        for child in responses_frame.winfo_children():
            child.destroy()
        response_state.clear()

        suggester_seat = seat_for_name(suggester_var.get())
        order = gs.responders_in_order(suggester_seat)
        user_is_suggester = suggester_seat == gs.user_seat

        tk.Label(responses_frame, text="Responses (in turn order — stop once someone shows):",
                 font=theme.body_font(10), bg=theme.BG).pack(anchor="w", pady=(0, 6))

        prior_responses = {r.responder_seat: r for r in edit_suggestion.responses} if edit_suggestion else {}

        for seat in order:
            row = tk.Frame(responses_frame, bg=theme.BG)
            row.pack(fill="x", pady=3)
            name = gs.players[seat].name
            tk.Label(row, text=name, width=12, anchor="w", font=theme.body_font(9), bg=theme.BG).pack(side="left")

            prior = prior_responses.get(seat)
            outcome_var = tk.StringVar(value=prior.outcome if prior else "no_show")
            shown_var = tk.StringVar(value=prior.shown_card.name if prior and prior.shown_card else "")
            response_state[seat] = (outcome_var, shown_var)

            user_sees_this_response = user_is_suggester or seat == gs.user_seat

            tk.Radiobutton(row, text="Nobody", variable=outcome_var, value="no_show", bg=theme.BG,
                           font=theme.body_font(9)).pack(side="left")

            if user_sees_this_response:
                tk.Radiobutton(row, text="Shows:", variable=outcome_var, value="shown_to_me", bg=theme.BG,
                               font=theme.body_font(9)).pack(side="left")
                shown_menu = tk.OptionMenu(row, shown_var, "")
                shown_menu.pack(side="left")

                def refresh_menu(shown_var=shown_var, shown_menu=shown_menu):
                    names = [suspect_var.get(), weapon_var.get(), room_var.get()]
                    menu = shown_menu["menu"]
                    menu.delete(0, "end")
                    for n in names:
                        menu.add_command(label=n, command=lambda v=n: shown_var.set(v))
                    if shown_var.get() not in names:
                        shown_var.set(names[0])

                refresh_menu()
            else:
                tk.Radiobutton(row, text="Shows a card (unseen)", variable=outcome_var, value="shown_unseen",
                               bg=theme.BG, font=theme.body_font(9)).pack(side="left")

    suggester_var.trace_add("write", lambda *a: rebuild_responses())
    suspect_var.trace_add("write", lambda *a: rebuild_responses())
    weapon_var.trace_add("write", lambda *a: rebuild_responses())
    room_var.trace_add("write", lambda *a: rebuild_responses())
    rebuild_responses()

    def submit():
        suggester_seat = seat_for_name(suggester_var.get())
        order = gs.responders_in_order(suggester_seat)
        by_name = {c.name: c for c in gs.cards}
        suspect, weapon, room = by_name[suspect_var.get()], by_name[weapon_var.get()], by_name[room_var.get()]

        responses = []
        for seat in order:
            outcome_var, shown_var = response_state[seat]
            outcome = outcome_var.get()
            if outcome == "no_show":
                responses.append(SuggestionResponse(seat, "no_show"))
                continue
            if outcome == "shown_to_me":
                responses.append(SuggestionResponse(seat, "shown_to_me", by_name[shown_var.get()]))
            else:
                responses.append(SuggestionResponse(seat, "shown_unseen"))
            break  # real Cluedo rules: stop asking once someone shows a card

        try:
            if edit_suggestion:
                gs.edit_suggestion(edit_suggestion.suggestion_id, suggester_seat, suspect, weapon, room, responses)
            else:
                gs.record_suggestion(suggester_seat, suspect, weapon, room, responses)
        except ContradictionError as exc:
            messagebox.showerror("Impossible", exc.message)
            return

        app.after_mutation()
        win.destroy()

    btns = tk.Frame(win, bg=theme.BG)
    btns.pack(pady=12)
    tk.Button(btns, text="Save (Enter)", bg=theme.ACCENT, fg="white", font=theme.body_font(10),
              padx=16, pady=6, command=submit).pack(side="left", padx=6)
    tk.Button(btns, text="Cancel (Esc)", font=theme.body_font(10), padx=16, pady=6, command=win.destroy).pack(
        side="left"
    )
    win.bind("<Return>", lambda e: submit())
    win.bind("<Escape>", lambda e: win.destroy())
