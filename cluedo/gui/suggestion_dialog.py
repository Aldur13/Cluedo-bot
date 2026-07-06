import tkinter as tk
from tkinter import messagebox

from cluedo.engine import ContradictionError
from cluedo.gui import theme
from cluedo.gui.widgets import ChoiceGrid
from cluedo.models import SuggestionResponse

# Remembers the last-picked suspect/weapon/room across dialog opens (within
# this process) so logging several suggestions in a row doesn't require
# re-picking from scratch every time. Suggester is *not* remembered here --
# it's defaulted from turn order instead, which is a stronger signal.
_last_choice = {"suspect": None, "weapon": None, "room": None}


def _default_suggester_seat(gs):
    """Whoever's turn it is next, based on the last logged suggestion --
    Cluedo turns rotate around the table, so this is right far more often
    than defaulting to seat 0 or to the user."""
    if gs.history:
        return (gs.history[-1].suggester_seat + 1) % len(gs.players)
    return 0


def open_dialog(app, edit_suggestion=None):
    gs = app.game_state
    if gs is None:
        return

    win = tk.Toplevel(app.root)
    win.title("Edit Suggestion" if edit_suggestion else "Log Suggestion")
    win.geometry("520x680")
    win.configure(bg=theme.BG)
    win.grab_set()

    # Fixed action bar at the bottom, packed first so it never scrolls away.
    btns = tk.Frame(win, bg=theme.BG)
    btns.pack(side="bottom", pady=12)

    scroll_area = tk.Frame(win, bg=theme.BG)
    scroll_area.pack(side="top", fill="both", expand=True)
    canvas = tk.Canvas(scroll_area, bg=theme.BG, highlightthickness=0)
    vscroll = tk.Scrollbar(scroll_area, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    content = tk.Frame(canvas, bg=theme.BG)
    canvas.create_window((0, 0), window=content, anchor="nw")
    content.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    def seat_for_name(name):
        return next(p.seat_index for p in gs.players if p.name == name)

    default_suggester_seat = (
        edit_suggestion.suggester_seat if edit_suggestion else _default_suggester_seat(gs)
    )
    suggester_var = tk.StringVar(value=gs.players[default_suggester_seat].name)

    tk.Label(content, text="Suggesting player:", font=theme.body_font(10), bg=theme.BG).pack(
        anchor="w", padx=14, pady=(14, 2)
    )
    ChoiceGrid(content, [p.name for p in gs.players], suggester_var, columns=3).pack(
        fill="x", padx=14
    )

    def choice_section(label, names, default):
        tk.Label(content, text=label, font=theme.body_font(10), bg=theme.BG).pack(
            anchor="w", padx=14, pady=(12, 2)
        )
        var = tk.StringVar(value=default)
        ChoiceGrid(content, names, var, columns=3).pack(fill="x", padx=14)
        return var

    suspect_var = choice_section(
        "Suspect:", list(gs.config.suspects),
        edit_suggestion.suspect.name if edit_suggestion else (_last_choice["suspect"] or gs.config.suspects[0]),
    )
    weapon_var = choice_section(
        "Weapon:", list(gs.config.weapons),
        edit_suggestion.weapon.name if edit_suggestion else (_last_choice["weapon"] or gs.config.weapons[0]),
    )
    room_var = choice_section(
        "Room:", list(gs.config.rooms),
        edit_suggestion.room.name if edit_suggestion else (_last_choice["room"] or gs.config.rooms[0]),
    )

    responses_frame = tk.Frame(content, bg=theme.BG)
    responses_frame.pack(fill="both", expand=True, padx=14, pady=(12, 4))
    response_state: dict[int, tuple[tk.StringVar, tk.StringVar]] = {}

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

        _last_choice["suspect"] = suspect.name
        _last_choice["weapon"] = weapon.name
        _last_choice["room"] = room.name

        app.after_mutation()
        win.destroy()

    tk.Button(btns, text="Save (Enter)", bg=theme.ACCENT, fg="white", font=theme.body_font(10),
              padx=16, pady=6, command=submit).pack(side="left", padx=6)
    tk.Button(btns, text="Cancel (Esc)", font=theme.body_font(10), padx=16, pady=6, command=win.destroy).pack(
        side="left"
    )
    win.bind("<Return>", lambda e: submit())
    win.bind("<Escape>", lambda e: win.destroy())
