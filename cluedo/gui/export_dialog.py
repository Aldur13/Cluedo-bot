import csv
import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from cluedo.models import CardType, ENVELOPE


def open_export(app):
    gs = app.game_state
    theme = app.theme_manager.current
    win = tk.Toplevel(app.root)
    win.title("Export")
    win.geometry("320x280")
    win.configure(bg=theme.bg)

    def export_png():
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG image", "*.png")])
        if not path:
            return
        try:
            _export_sheet_png(gs, path)
            messagebox.showinfo("Exported", f"Detective sheet exported to {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def export_pdf():
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF document", "*.pdf")])
        if not path:
            return
        try:
            _export_timeline_pdf(gs, path)
            messagebox.showinfo("Exported", f"Timeline exported to {path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def export_json():
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        Path(path).write_text(json.dumps(gs.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        messagebox.showinfo("Exported", f"Game exported to {path}")

    def export_csv():
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        stats = gs.last_solver_stats
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            writer.writerow(["suggestions_logged", len(gs.history)])
            writer.writerow(["ambiguous_cards", stats.ambiguous_card_count_last])
            writer.writerow(["valid_worlds_last_counted", stats.valid_worlds_last_counted])
            writer.writerow(["propagation_iterations", stats.propagation_iterations])
            writer.writerow(["wall_clock_seconds", stats.wall_clock_seconds])
        messagebox.showinfo("Exported", f"Statistics exported to {path}")

    for label, cmd in [
        ("Detective sheet → PNG", export_png),
        ("Timeline → PDF", export_pdf),
        ("Full game → JSON", export_json),
        ("Statistics → CSV", export_csv),
    ]:
        tk.Button(win, text=label, command=cmd, font=theme.body_font(10), width=28).pack(pady=8)

    tk.Button(win, text="Close", command=win.destroy, font=theme.body_font(10)).pack(pady=10)


def _export_sheet_png(gs, path):
    from PIL import Image, ImageDraw, ImageFont

    sheet = gs.detective_sheet()
    owners = [p.owner_id for p in gs.players] + [ENVELOPE]
    owner_labels = [p.name for p in gs.players] + ["Envelope"]

    row_h, col_w, name_col_w = 22, 90, 170
    rows = len(gs.cards) + 4
    width = name_col_w + col_w * len(owners) + 40
    height = row_h * rows + 90

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
        bold = ImageFont.truetype("arialbd.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
        bold = font

    draw.text((20, 15), f"Cluedo Detective Sheet — {gs.config.edition}", fill="black", font=bold)
    y = 50
    x = name_col_w
    for label in owner_labels:
        draw.text((x + 4, y), label, fill="black", font=font)
        x += col_w
    y += row_h

    colors = {"confirmed": (46, 204, 113), "impossible": (231, 111, 81), "possible": (244, 197, 66)}
    for card_type in (CardType.SUSPECT, CardType.WEAPON, CardType.ROOM):
        draw.text((20, y), card_type.value.title(), fill=(58, 12, 163), font=bold)
        y += row_h
        for card in gs.cards:
            if card.type != card_type:
                continue
            info = sheet[card]
            draw.text((20, y), card.name, fill="black", font=font)
            x = name_col_w
            for owner in owners:
                if info["status"] == "confirmed" and info["owner"] == owner:
                    color, text = colors["confirmed"], "OK"
                elif owner in info["possible"]:
                    color, text = colors["possible"], "?"
                else:
                    color, text = colors["impossible"], "X"
                draw.rectangle([x, y, x + col_w - 6, y + row_h - 4], fill=color)
                draw.text((x + col_w // 2 - 6, y + 2), text, fill="black", font=font)
                x += col_w
            y += row_h

    img.save(path)


def _export_timeline_pdf(gs, path):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Cluedo Game Timeline -- {gs.config.edition}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Players: {', '.join(p.name for p in gs.players)}", ln=True)
    pdf.ln(4)

    for i, s in enumerate(gs.history, start=1):
        suggester = gs.players[s.suggester_seat].name
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, f"Turn {i}: {suggester} suggested", ln=True)
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"  {s.suspect.name} / {s.weapon.name} / {s.room.name}", ln=True)
        for r in s.responses:
            responder = gs.players[r.responder_seat].name
            if r.outcome == "no_show":
                pdf.cell(0, 6, f"    {responder}: showed nothing", ln=True)
            elif r.outcome == "shown_to_me":
                pdf.cell(0, 6, f"    {responder}: showed {r.shown_card.name}", ln=True)
            else:
                pdf.cell(0, 6, f"    {responder}: showed a card (unseen)", ln=True)
        pdf.ln(2)

    if gs.is_solved():
        s, w, r = gs.solution()
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, f"Solution: {s.name} / {w.name} / {r.name}", ln=True)

    pdf.output(path)
