import tkinter as tk

from cluedo.gui import theme
from cluedo.gui.widgets import Tooltip
from cluedo.models import CardType, ENVELOPE
from cluedo.probability import TooManyAmbiguousCardsError


def build(parent, app):
    """`app` is the App controller; this screen reads/writes app.game_state and
    calls back into `app` for cross-screen actions (dialogs, save, etc.)."""
    frame = tk.Frame(parent, bg=theme.BG)

    header = tk.Frame(frame, bg=theme.BG)
    header.pack(fill="x", padx=12, pady=(10, 4))
    tk.Label(header, text="Detective Sheet", font=theme.heading_font(16), bg=theme.BG, fg=theme.TEXT).pack(
        side="left"
    )
    banner = tk.Label(
        header, text="", font=theme.heading_font(13), bg=theme.SOLVED_BG, fg=theme.SOLVED_TEXT, padx=10, pady=4
    )

    toolbar = tk.Frame(frame, bg=theme.BG)
    toolbar.pack(fill="x", padx=12, pady=(0, 8))

    def make_button(text, command):
        tk.Button(toolbar, text=text, command=command, font=theme.body_font(10), padx=8, pady=4).pack(
            side="left", padx=3
        )

    make_button("Log Suggestion (Ctrl+N)", app.open_suggestion_dialog)
    make_button("Undo (Ctrl+Z)", app.undo)
    make_button("Timeline (Ctrl+E)", app.open_timeline)
    make_button("Replay (Ctrl+R)", app.open_replay)
    make_button("What-If", app.open_whatif)
    make_button("Save (Ctrl+S)", app.save)
    make_button("Load (Ctrl+O)", app.load)
    make_button("Export", app.open_export)

    body = tk.Frame(frame, bg=theme.BG)
    body.pack(fill="both", expand=True, padx=12, pady=4)

    sheet_container = tk.Frame(body, bg=theme.PANEL_BG, bd=1, relief="solid")
    sheet_container.pack(side="left", fill="both", expand=True, padx=(0, 8))

    canvas = tk.Canvas(sheet_container, bg=theme.PANEL_BG, highlightthickness=0)
    vscroll = tk.Scrollbar(sheet_container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vscroll.set)
    vscroll.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    sheet_frame = tk.Frame(canvas, bg=theme.PANEL_BG)
    canvas.create_window((0, 0), window=sheet_frame, anchor="nw")
    sheet_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    side_panel = tk.Frame(body, bg=theme.BG, width=320)
    side_panel.pack(side="left", fill="y")
    side_panel.pack_propagate(False)

    advisor_box = tk.LabelFrame(side_panel, text="Advisor", font=theme.body_font(11), bg=theme.PANEL_BG)
    advisor_box.pack(fill="x", pady=(0, 8))
    advisor_label = tk.Label(
        advisor_box, text="", justify="left", wraplength=290, bg=theme.PANEL_BG, font=theme.body_font(10)
    )
    advisor_label.pack(padx=8, pady=8, anchor="w")

    prob_box = tk.LabelFrame(side_panel, text="Envelope probabilities", font=theme.body_font(11), bg=theme.PANEL_BG)
    prob_box.pack(fill="x", pady=(0, 8))
    prob_inner = tk.Frame(prob_box, bg=theme.PANEL_BG)
    prob_inner.pack(fill="x", padx=8, pady=8)

    stats_box = tk.LabelFrame(side_panel, text="Statistics", font=theme.body_font(11), bg=theme.PANEL_BG)
    stats_box.pack(fill="x")
    stats_label = tk.Label(stats_box, text="", justify="left", bg=theme.PANEL_BG, font=theme.body_font(9))
    stats_label.pack(padx=8, pady=8, anchor="w")

    def refresh():
        gs = app.game_state
        if gs is None:
            return
        for child in sheet_frame.winfo_children():
            child.destroy()

        sheet = gs.detective_sheet()
        owners = [p.owner_id for p in gs.players] + [ENVELOPE]
        owner_labels = [p.name for p in gs.players] + ["Envelope"]

        tk.Label(sheet_frame, text="", bg=theme.PANEL_BG, width=18).grid(row=0, column=0)
        for c, label in enumerate(owner_labels, start=1):
            tk.Label(sheet_frame, text=label, font=theme.body_font(9, "bold"), bg=theme.PANEL_BG).grid(
                row=0, column=c, padx=2, pady=2
            )

        row = 1
        for card_type in (CardType.SUSPECT, CardType.WEAPON, CardType.ROOM):
            tk.Label(
                sheet_frame, text=card_type.value.title(), font=theme.body_font(10, "bold"),
                bg=theme.PANEL_BG, fg=theme.ACCENT_DARK,
            ).grid(row=row, column=0, columnspan=len(owners) + 1, sticky="w", pady=(10, 2), padx=4)
            row += 1
            for card in gs.cards:
                if card.type != card_type:
                    continue
                info = sheet[card]
                tk.Label(
                    sheet_frame, text=card.name, font=theme.body_font(9), bg=theme.PANEL_BG, anchor="w", width=18
                ).grid(row=row, column=0, sticky="w", padx=4)
                for c, owner in enumerate(owners, start=1):
                    if info["status"] == "confirmed" and info["owner"] == owner:
                        bg, text = theme.CONFIRMED, "✔"
                    elif owner in info["possible"]:
                        bg, text = theme.POSSIBLE, "?"
                    else:
                        bg, text = theme.IMPOSSIBLE, "✘"
                    cell = tk.Label(sheet_frame, text=text, bg=bg, width=4, font=theme.body_font(9))
                    cell.grid(row=row, column=c, padx=1, pady=1, sticky="nsew")
                    cell.bind("<Button-1>", lambda e, card=card: app.open_explain(card))

                    def tooltip_text(card=card):
                        info = app.game_state.detective_sheet()[card]
                        if info["status"] == "confirmed":
                            exp = app.game_state.explain_card(card)
                            if exp is not None:
                                return "\n".join(exp.narrative)
                            return f"Confirmed: {info['owner']}"
                        return "Still possible: " + ", ".join(sorted(info["possible"]))

                    Tooltip(cell, tooltip_text)
                row += 1

        if gs.is_solved():
            suspect, weapon, room = gs.solution()
            banner.config(text=f"SOLVED — {suspect.name} · {weapon.name} · {room.name}")
            banner.pack(side="right")
            advisor_label.config(text="The game is solved. Make your accusation!")
        else:
            banner.pack_forget()
            candidates = gs.best_suggestions(top_k=5)
            if candidates:
                best = candidates[0]
                advisor_label.config(
                    text=f"Suggest: {best.suspect.name}, {best.weapon.name}, {best.room.name}\n\n{best.rationale}"
                )
            else:
                advisor_label.config(text="Not enough information yet to suggest anything.")

        for child in prob_inner.winfo_children():
            child.destroy()
        try:
            probs = gs.card_probabilities()
            for card_type, title in (
                (CardType.SUSPECT, "Suspect"), (CardType.WEAPON, "Weapon"), (CardType.ROOM, "Room")
            ):
                best_card, best_p = None, -1.0
                for card in gs.cards:
                    if card.type != card_type:
                        continue
                    p = probs.get(card, {}).get(ENVELOPE, 0.0)
                    if p > best_p:
                        best_card, best_p = card, p
                row_frame = tk.Frame(prob_inner, bg=theme.PANEL_BG)
                row_frame.pack(fill="x", pady=2)
                tk.Label(
                    row_frame, text=f"{title}:", bg=theme.PANEL_BG, font=theme.body_font(9), width=9, anchor="w"
                ).pack(side="left")
                color = theme.CONFIRMED if best_p >= 0.999 else theme.TEXT
                tk.Label(
                    row_frame, text=f"{best_card.name} ({best_p * 100:.0f}%)",
                    bg=theme.PANEL_BG, font=theme.body_font(9), fg=color, anchor="w",
                ).pack(side="left")
        except TooManyAmbiguousCardsError:
            tk.Label(
                prob_inner, text="Not enough information yet for probabilities.",
                bg=theme.PANEL_BG, font=theme.body_font(9), wraplength=280, justify="left",
            ).pack()

        stats = gs.last_solver_stats
        confirmed_count = sum(1 for v in sheet.values() if v["status"] == "confirmed")
        stats_label.config(
            text=(
                f"Suggestions logged: {len(gs.history)}\n"
                f"Confirmed cards: {confirmed_count}/{len(gs.cards)}\n"
                f"Ambiguous cards: {stats.ambiguous_card_count_last}\n"
                f"Valid worlds (last count): {stats.valid_worlds_last_counted}\n"
                f"Propagation iterations: {stats.propagation_iterations}\n"
                f"Last solve time: {stats.wall_clock_seconds * 1000:.1f} ms"
            )
        )

    app.refresh_main_screen = refresh
    refresh()
    return frame
