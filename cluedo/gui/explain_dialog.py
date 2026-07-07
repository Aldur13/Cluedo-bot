import tkinter as tk


def open_explain(app, card):
    gs = app.game_state
    theme = app.theme_manager.current
    win = tk.Toplevel(app.root)
    win.title(f"Why: {card.name}")
    win.geometry("440x340")
    win.configure(bg=theme.bg)

    explanation = gs.explain_card(card)
    if explanation is None:
        info = gs.detective_sheet()[card]
        text = f"{card.name} is not yet confirmed.\n\nStill possible: {', '.join(sorted(info['possible']))}"
    else:
        lines = [f"{card.name} is confirmed because:"]
        for line in explanation.narrative[:-1]:
            lines.append(f"  • {line}")
        lines.append("")
        lines.append(explanation.narrative[-1])
        text = "\n".join(lines)

    tk.Label(
        win, text=text, justify="left", wraplength=400, font=theme.body_font(10), bg=theme.bg, anchor="nw"
    ).pack(padx=16, pady=16, anchor="w", fill="both", expand=True)
    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=(0, 12))
