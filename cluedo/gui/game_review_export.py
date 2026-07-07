"""Export a computed GameReview (cluedo.analysis.game_review) to PDF, HTML,
Markdown, or JSON.

Chart generation reuses matplotlib's non-interactive "Agg" backend (not
"TkAgg", unlike cluedo/gui/graph_screen.py) so these functions work headless
-- no Tk root required, safe to call from a script or a test with no display.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Optional

from cluedo.analysis.game_review import GameReview


def _card_dict(card) -> Optional[dict]:
    if card is None:
        return None
    return {"name": card.name, "type": card.type.value}


def review_to_dict(review: GameReview) -> dict:
    """Plain-dict, JSON-serializable projection of a GameReview."""
    return {
        "is_solved": review.is_solved,
        "difficulty": review.difficulty,
        "difficulty_explanation": review.difficulty_explanation,
        "overall_rating": review.overall_rating,
        "efficiency_pct": review.efficiency_pct,
        "turns_played": review.turns_played,
        "estimated_optimal_solve_turn": review.estimated_optimal_solve_turn,
        "actual_solve_turn": review.actual_solve_turn,
        "turns_lost": review.turns_lost,
        "time_played_seconds": review.time_played_seconds,
        "average_time_per_turn_seconds": review.average_time_per_turn_seconds,
        "final_accuracy_pct": review.final_accuracy_pct,
        "key_turning_point": _highlight_dict(review.key_turning_point),
        "best_suggestion": _highlight_dict(review.best_suggestion),
        "largest_deduction": (
            None if review.largest_deduction is None else {
                "turn": review.largest_deduction.turn,
                "card": _card_dict(review.largest_deduction.card),
                "narrative": list(review.largest_deduction.narrative),
                "newly_confirmed_count": review.largest_deduction.newly_confirmed_count,
            }
        ),
        "missed_opportunities": [
            {"kind": m.kind, "turn": m.turn, "message": m.message} for m in review.missed_opportunities
        ],
        "timeline": [
            {"turn": e.turn, "label": e.label, "description": e.description} for e in review.timeline
        ],
        "performance": {
            "info_gain_per_turn": review.performance.info_gain_per_turn,
            "average_info_gain": review.performance.average_info_gain,
            "highest_info_gain": review.performance.highest_info_gain,
            "lowest_info_gain": review.performance.lowest_info_gain,
            "redundant_suggestion_count": review.performance.redundant_suggestion_count,
            "unique_suggestion_count": review.performance.unique_suggestion_count,
            "total_suggestion_count": review.performance.total_suggestion_count,
            "valid_worlds_per_turn": review.performance.valid_worlds_per_turn,
        },
        "feedback": list(review.feedback),
    }


def _highlight_dict(highlight) -> Optional[dict]:
    if highlight is None:
        return None
    return {
        "turn": highlight.turn,
        "player": highlight.player,
        "suspect": _card_dict(highlight.suspect),
        "weapon": _card_dict(highlight.weapon),
        "room": _card_dict(highlight.room),
        "info_gain": highlight.info_gain,
        "explanation": highlight.explanation,
    }


# --------------------------------------------------------------------- JSON


def export_review_json(review: GameReview, path: "Path | str") -> None:
    Path(path).write_text(json.dumps(review_to_dict(review), indent=2, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------- Markdown


def render_review_markdown(review: GameReview) -> str:
    lines: list[str] = ["# Cluedo Game Review", ""]

    lines.append("## Summary")
    lines.append(f"- **Difficulty:** {review.difficulty} ({review.difficulty_explanation})")
    lines.append(f"- **Overall Rating:** {review.overall_rating or 'N/A'}")
    lines.append(f"- **Efficiency:** {_pct(review.efficiency_pct)}")
    lines.append(f"- **Turns Played:** {review.turns_played}")
    lines.append(f"- **Estimated Optimal Solve Turn:** {_int_or_na(review.estimated_optimal_solve_turn)}")
    lines.append(f"- **Actual Solve Turn:** {_int_or_na(review.actual_solve_turn)}")
    lines.append(f"- **Turns Lost:** {_int_or_na(review.turns_lost)}")
    lines.append(f"- **Time Played:** {_seconds_or_na(review.time_played_seconds)}")
    lines.append(f"- **Average Time Per Turn:** {_seconds_or_na(review.average_time_per_turn_seconds)}")
    lines.append(f"- **Final Accuracy:** {_pct(review.final_accuracy_pct)}")
    lines.append("")

    if review.key_turning_point:
        h = review.key_turning_point
        lines.append("## Key Turning Point")
        lines.append(f"Turn {h.turn}: {h.explanation}")
        lines.append("")

    if review.best_suggestion:
        h = review.best_suggestion
        lines.append("## Best Suggestion")
        lines.append(f"Turn {h.turn} -- {h.player}: {h.suspect.name} - {h.weapon.name} - {h.room.name}")
        lines.append(f"Information gained / probability reduction: {_pct(h.info_gain * 100)}")
        lines.append("")

    if review.largest_deduction:
        d = review.largest_deduction
        lines.append("## Largest Deduction")
        lines.append(f"Turn {d.turn}" + (f" -- {d.card.name}" if d.card else ""))
        for line in d.narrative:
            lines.append(f"- {line}")
        lines.append("")

    if review.missed_opportunities:
        lines.append("## Missed Opportunities")
        for m in review.missed_opportunities:
            lines.append(f"- {m.message}")
        lines.append("")

    if review.timeline:
        lines.append("## Timeline")
        for e in review.timeline:
            lines.append(f"- **Turn {e.turn}** -- {e.label}: {e.description}")
        lines.append("")

    lines.append("## Performance Metrics")
    p = review.performance
    lines.append(f"- Average info gain: {_pct(p.average_info_gain * 100)}")
    lines.append(f"- Highest info gain: {_pct(p.highest_info_gain * 100)}")
    lines.append(f"- Lowest info gain: {_pct(p.lowest_info_gain * 100)}")
    lines.append(f"- Redundant suggestions: {p.redundant_suggestion_count}")
    lines.append(f"- Unique suggestions: {p.unique_suggestion_count} / {p.total_suggestion_count}")
    lines.append("")

    if review.feedback:
        lines.append("## Feedback")
        for f in review.feedback:
            lines.append(f"- {f}")
        lines.append("")

    return "\n".join(lines)


def export_review_markdown(review: GameReview, path: "Path | str") -> None:
    Path(path).write_text(render_review_markdown(review), encoding="utf-8")


# --------------------------------------------------------------------- HTML


def _chart_png_base64(review: GameReview) -> Optional[str]:
    """Renders a small "valid worlds remaining" / "cards confirmed" chart to
    a base64 PNG for embedding, using the Agg backend so no Tk display is
    required. Returns None if there's no history to chart."""
    if not review.performance.valid_worlds_per_turn:
        return None
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure

    fig = Figure(figsize=(6, 3), dpi=100)
    ax = fig.add_subplot(1, 1, 1)
    worlds = review.performance.valid_worlds_per_turn
    turns = list(range(len(worlds)))
    known_points = [(t, w) for t, w in zip(turns, worlds) if w is not None]
    if known_points:
        ax.plot([t for t, _ in known_points], [w for _, w in known_points], marker="o", markersize=3)
    ax.set_title("Valid worlds remaining")
    ax.set_xlabel("Turn")
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def render_review_html(review: GameReview) -> str:
    chart_b64 = _chart_png_base64(review)
    chart_html = (
        f'<img src="data:image/png;base64,{chart_b64}" alt="Valid worlds remaining" />' if chart_b64 else ""
    )

    def _rows(items: list[str]) -> str:
        return "".join(f"<li>{item}</li>" for item in items)

    timeline_html = _rows(
        [f"<strong>Turn {e.turn}</strong> -- {e.label}: {e.description}" for e in review.timeline]
    )
    missed_html = _rows([m.message for m in review.missed_opportunities])
    feedback_html = _rows(list(review.feedback))

    key_turning_point_html = ""
    if review.key_turning_point:
        h = review.key_turning_point
        key_turning_point_html = f"<p>Turn {h.turn}: {h.explanation}</p>"

    best_suggestion_html = ""
    if review.best_suggestion:
        h = review.best_suggestion
        best_suggestion_html = (
            f"<p>Turn {h.turn} -- {h.player}: {h.suspect.name} &bull; {h.weapon.name} &bull; {h.room.name}"
            f"<br/>Information gained / probability reduction: {_pct(h.info_gain * 100)}</p>"
        )

    largest_deduction_html = ""
    if review.largest_deduction:
        d = review.largest_deduction
        narrative_html = "".join(f"<li>{line}</li>" for line in d.narrative)
        largest_deduction_html = f"<p>Turn {d.turn}{f' -- {d.card.name}' if d.card else ''}</p><ul>{narrative_html}</ul>"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>Cluedo Game Review</title>
<style>
  body {{ font-family: -apple-system, "Segoe UI", sans-serif; margin: 2rem; color: #2b2d42; }}
  h1 {{ color: #3a0ca3; }}
  h2 {{ color: #4361ee; border-bottom: 1px solid #dee2e6; padding-bottom: 4px; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 1rem 0; }}
  .stat {{ background: #f5f6fa; border-radius: 8px; padding: 10px 14px; }}
  .stat .label {{ font-size: 0.8rem; color: #6c757d; }}
  .stat .value {{ font-size: 1.3rem; font-weight: bold; }}
  img {{ max-width: 100%; }}
</style>
</head>
<body>
<h1>Cluedo Game Review</h1>
<div class="stat-grid">
  <div class="stat"><div class="label">Difficulty</div><div class="value">{review.difficulty}</div></div>
  <div class="stat"><div class="label">Overall Rating</div><div class="value">{review.overall_rating or 'N/A'}</div></div>
  <div class="stat"><div class="label">Efficiency</div><div class="value">{_pct(review.efficiency_pct)}</div></div>
  <div class="stat"><div class="label">Turns Played</div><div class="value">{review.turns_played}</div></div>
  <div class="stat"><div class="label">Estimated Optimal Turn</div><div class="value">{_int_or_na(review.estimated_optimal_solve_turn)}</div></div>
  <div class="stat"><div class="label">Actual Solve Turn</div><div class="value">{_int_or_na(review.actual_solve_turn)}</div></div>
  <div class="stat"><div class="label">Turns Lost</div><div class="value">{_int_or_na(review.turns_lost)}</div></div>
  <div class="stat"><div class="label">Final Accuracy</div><div class="value">{_pct(review.final_accuracy_pct)}</div></div>
  <div class="stat"><div class="label">Time Played</div><div class="value">{_seconds_or_na(review.time_played_seconds)}</div></div>
</div>
<p>{review.difficulty_explanation}</p>

{chart_html}

<h2>Key Turning Point</h2>
{key_turning_point_html or '<p>N/A</p>'}

<h2>Best Suggestion</h2>
{best_suggestion_html or '<p>N/A</p>'}

<h2>Largest Deduction</h2>
{largest_deduction_html or '<p>N/A</p>'}

<h2>Missed Opportunities</h2>
<ul>{missed_html or '<li>None found.</li>'}</ul>

<h2>Timeline</h2>
<ul>{timeline_html or '<li>No events.</li>'}</ul>

<h2>Feedback</h2>
<ul>{feedback_html or '<li>No feedback generated.</li>'}</ul>
</body>
</html>
"""


def export_review_html(review: GameReview, path: "Path | str") -> None:
    Path(path).write_text(render_review_html(review), encoding="utf-8")


# ---------------------------------------------------------------------- PDF


def _multi_cell_line(pdf, line_height: float, text: str) -> None:
    """multi_cell(0, ...) (auto-width) leaves the cursor at the page's right
    edge afterward in this fpdf2 version rather than resetting to the left
    margin, which starves the *next* multi_cell(0, ...) call of horizontal
    space and raises FPDFException("Not enough horizontal space to render a
    single character") -- reproduced and confirmed while building this
    export. Explicitly resetting x before every call sidesteps it."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, line_height, text)


def export_review_pdf(review: GameReview, path: "Path | str") -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Cluedo Game Review", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Difficulty: {review.difficulty} -- {review.difficulty_explanation}", ln=True)
    pdf.cell(0, 8, f"Overall Rating: {review.overall_rating or 'N/A'}    Efficiency: {_pct(review.efficiency_pct)}", ln=True)
    pdf.cell(
        0, 8,
        f"Turns Played: {review.turns_played}    Estimated Optimal: {_int_or_na(review.estimated_optimal_solve_turn)}"
        f"    Actual Solve Turn: {_int_or_na(review.actual_solve_turn)}    Turns Lost: {_int_or_na(review.turns_lost)}",
        ln=True,
    )
    pdf.cell(
        0, 8,
        f"Time Played: {_seconds_or_na(review.time_played_seconds)}    "
        f"Avg/Turn: {_seconds_or_na(review.average_time_per_turn_seconds)}    "
        f"Final Accuracy: {_pct(review.final_accuracy_pct)}",
        ln=True,
    )
    pdf.ln(4)

    chart_b64 = _chart_png_base64(review)
    if chart_b64:
        buf = io.BytesIO(base64.b64decode(chart_b64))
        chart_width = 170
        # figsize=(6, 3) in _chart_png_base64 is a fixed 2:1 aspect ratio.
        chart_height = chart_width / 2
        pdf.image(buf, x=pdf.l_margin, w=chart_width)
        # fpdf2's image() doesn't reliably advance the cursor past the image
        # (x can be left wherever it was), which then starves the next
        # multi_cell(0, ...) call of horizontal space -- pin both x and y
        # back to a known-good position explicitly rather than relying on
        # ln() alone.
        pdf.set_xy(pdf.l_margin, pdf.get_y() + chart_height + 4)

    if review.key_turning_point:
        h = review.key_turning_point
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Key Turning Point", ln=True)
        pdf.set_font("Helvetica", "", 10)
        _multi_cell_line(pdf, 6, f"Turn {h.turn}: {h.explanation}")
        pdf.ln(2)

    if review.largest_deduction:
        d = review.largest_deduction
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Largest Deduction", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for line in d.narrative:
            _multi_cell_line(pdf, 6, f"- {line}")
        pdf.ln(2)

    if review.missed_opportunities:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Missed Opportunities", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for m in review.missed_opportunities:
            _multi_cell_line(pdf, 6, f"- {m.message}")
        pdf.ln(2)

    if review.timeline:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Timeline", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for e in review.timeline:
            _multi_cell_line(pdf, 6, f"Turn {e.turn} -- {e.label}: {e.description}")
        pdf.ln(2)

    if review.feedback:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, "Feedback", ln=True)
        pdf.set_font("Helvetica", "", 10)
        for f in review.feedback:
            _multi_cell_line(pdf, 6, f"- {f}")

    pdf.output(str(path))


# --------------------------------------------------------------------- misc


def _pct(value: Optional[float]) -> str:
    return "N/A" if value is None else f"{value:.0f}%"


def _int_or_na(value: Optional[int]) -> str:
    return "N/A" if value is None else str(value)


def _seconds_or_na(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}m {seconds}s"
