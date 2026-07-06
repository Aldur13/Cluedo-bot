import tkinter as tk

from cluedo.engine import ContradictionError
from cluedo.gui import theme
from cluedo.history import whatif_game_state
from cluedo.models import Suggestion, SuggestionResponse


def open_whatif(app):
    gs = app.game_state
    win = tk.Toplevel(app.root)
    win.title("What-If")
    win.geometry("480x460")
    win.configure(bg=theme.BG)

    tk.Label(
        win, text="Simulate a hypothetical outcome\n(never affects your real game)",
        font=theme.body_font(10), justify="left", bg=theme.BG,
    ).pack(padx=14, pady=10, anchor="w")

    suggester_var = tk.StringVar(value=gs.players[0].name)
    tk.OptionMenu(win, suggester_var, *[p.name for p in gs.players]).pack(fill="x", padx=14)

    def dropdown(label, names):
        tk.Label(win, text=label, font=theme.body_font(10), bg=theme.BG).pack(anchor="w", padx=14, pady=(8, 2))
        var = tk.StringVar(value=names[0])
        tk.OptionMenu(win, var, *names).pack(fill="x", padx=14)
        return var

    suspect_var = dropdown("Suspect:", list(gs.config.suspects))
    weapon_var = dropdown("Weapon:", list(gs.config.weapons))
    room_var = dropdown("Room:", list(gs.config.rooms))

    tk.Label(win, text="Hypothetical outcome:", font=theme.body_font(10), bg=theme.BG).pack(
        anchor="w", padx=14, pady=(8, 2)
    )
    outcome_var = tk.StringVar(value="no_show")
    outcome_frame = tk.Frame(win, bg=theme.BG)
    outcome_frame.pack(anchor="w", padx=14)
    tk.Radiobutton(outcome_frame, text="Nobody shows", variable=outcome_var, value="no_show", bg=theme.BG).pack(
        side="left"
    )

    def rebuild_who_shows():
        for w in outcome_frame.winfo_children()[1:]:
            w.destroy()
        suggester_seat = next(p.seat_index for p in gs.players if p.name == suggester_var.get())
        for seat in gs.responders_in_order(suggester_seat):
            tk.Radiobutton(
                outcome_frame, text=f"{gs.players[seat].name} shows", variable=outcome_var, value=str(seat),
                bg=theme.BG,
            ).pack(side="left")

    suggester_var.trace_add("write", lambda *a: rebuild_who_shows())
    rebuild_who_shows()

    result_label = tk.Label(
        win, text="", justify="left", font=theme.body_font(9), wraplength=440, bg=theme.PANEL_BG, anchor="nw"
    )
    result_label.pack(fill="both", expand=True, padx=14, pady=12)

    def run_whatif():
        by_name = {c.name: c for c in gs.cards}
        suspect, weapon, room = by_name[suspect_var.get()], by_name[weapon_var.get()], by_name[room_var.get()]
        suggester_seat = next(p.seat_index for p in gs.players if p.name == suggester_var.get())
        order = gs.responders_in_order(suggester_seat)
        outcome = outcome_var.get()

        if outcome == "no_show":
            responses = [SuggestionResponse(s, "no_show") for s in order]
        else:
            target_seat = int(outcome)
            responses = []
            for seat in order:
                if seat == target_seat:
                    responses.append(SuggestionResponse(seat, "shown_unseen"))
                    break
                responses.append(SuggestionResponse(seat, "no_show"))

        hypothetical = Suggestion("__whatif__", suggester_seat, suspect, weapon, room, tuple(responses))
        try:
            scratch = whatif_game_state(gs, hypothetical)
        except ContradictionError as exc:
            result_label.config(text=f"This outcome is impossible given what's known:\n{exc.message}")
            return

        lines = []
        if scratch.is_solved():
            s, w, r = scratch.solution()
            lines.append(f"This would SOLVE the game: {s.name} / {w.name} / {r.name}")
        else:
            lines.append(f"Ambiguous cards remaining: {scratch.last_solver_stats.ambiguous_card_count_last}")
            newly_confirmed = [
                card.name
                for card in gs.cards
                if gs.engine.owner_of(card) is None and scratch.engine.owner_of(card) is not None
            ]
            if newly_confirmed:
                lines.append("Would newly confirm: " + ", ".join(newly_confirmed))
            else:
                lines.append("Would not confirm anything new yet.")
        result_label.config(text="\n".join(lines))

    tk.Button(
        win, text="Simulate", bg=theme.ACCENT, fg="white", font=theme.body_font(10), padx=14, pady=6,
        command=run_whatif,
    ).pack(pady=8)
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 10))
