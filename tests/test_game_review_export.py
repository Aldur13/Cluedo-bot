"""Tests for cluedo/gui/game_review_export.py."""
import json

from cluedo.analysis.game_review import compute_game_review
from cluedo.game import GameState
from cluedo.gui.game_review_export import (
    export_review_html,
    export_review_json,
    export_review_markdown,
    export_review_pdf,
    render_review_html,
    render_review_markdown,
    review_to_dict,
)
from cluedo.models import SuggestionResponse


def _solved_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    gs.record_suggestion(
        0, cards_by_name["Reverend Green"], cards_by_name["Rope"], cards_by_name["Kitchen"],
        [SuggestionResponse(1, "no_show"), SuggestionResponse(2, "no_show")],
    )
    assert gs.is_solved()
    return gs


def _unsolved_game(cfg, cards_by_name, three_players):
    gs = GameState(cfg, three_players, user_seat=0)
    hand = ["Miss Scarlett", "Colonel Mustard", "Mrs. White", "Candlestick", "Knife", "Lead Pipe"]
    gs.set_user_hand([cards_by_name[n] for n in hand])
    return gs


def test_review_to_dict_is_json_serializable(cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs, time_played_seconds=120.0)
    data = review_to_dict(review)
    # round-trips through json.dumps without a TypeError (Card objects etc.
    # must already be plain dicts/primitives)
    text = json.dumps(data)
    assert json.loads(text)["is_solved"] is True
    assert data["overall_rating"] == "A+"
    assert data["key_turning_point"]["suspect"]["name"] == "Reverend Green"


def test_export_review_json_writes_valid_file(tmp_path, cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    path = tmp_path / "review.json"
    export_review_json(review, path)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["actual_solve_turn"] == 1
    assert data["difficulty"] in ("Easy", "Medium", "Hard", "Expert")


def test_markdown_export_contains_key_sections(cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    text = render_review_markdown(review)

    for heading in (
        "# Cluedo Game Review", "## Summary", "## Key Turning Point", "## Largest Deduction",
        "## Timeline", "## Performance Metrics",
    ):
        assert heading in text
    assert review.overall_rating in text


def test_markdown_export_writes_file(tmp_path, cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    path = tmp_path / "review.md"
    export_review_markdown(review, path)
    assert path.exists()
    assert "# Cluedo Game Review" in path.read_text(encoding="utf-8")


def test_html_export_contains_stat_grid_and_embedded_chart(cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    html = render_review_html(review)

    assert "<html>" in html
    assert review.difficulty in html
    assert "data:image/png;base64," in html  # chart embedded


def test_html_export_writes_file(tmp_path, cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    path = tmp_path / "review.html"
    export_review_html(review, path)
    assert path.exists()
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_pdf_export_writes_nonempty_file(tmp_path, cfg, cards_by_name, three_players):
    gs = _solved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)
    path = tmp_path / "review.pdf"
    export_review_pdf(review, path)

    assert path.exists()
    assert path.stat().st_size > 0
    assert path.read_bytes()[:4] == b"%PDF"


def test_unsolved_game_exports_without_crashing(tmp_path, cfg, cards_by_name, three_players):
    gs = _unsolved_game(cfg, cards_by_name, three_players)
    review = compute_game_review(gs)

    export_review_json(review, tmp_path / "r.json")
    export_review_markdown(review, tmp_path / "r.md")
    export_review_html(review, tmp_path / "r.html")
    export_review_pdf(review, tmp_path / "r.pdf")

    for name in ("r.json", "r.md", "r.html", "r.pdf"):
        assert (tmp_path / name).exists()


def test_zero_turn_game_exports_without_crashing(tmp_path, cfg):
    from cluedo.models import CardType, Player

    all_cards = cfg.all_cards()
    withheld = {
        next(c for c in all_cards if c.type == CardType.SUSPECT),
        next(c for c in all_cards if c.type == CardType.WEAPON),
        next(c for c in all_cards if c.type == CardType.ROOM),
    }
    hand = [c for c in all_cards if c not in withheld]
    gs = GameState(cfg, [Player("Alice", 0, len(hand)), Player("Bob", 1, 0)], user_seat=0)
    gs.set_user_hand(hand)
    review = compute_game_review(gs)

    export_review_json(review, tmp_path / "r.json")
    export_review_markdown(review, tmp_path / "r.md")
    export_review_html(review, tmp_path / "r.html")
    export_review_pdf(review, tmp_path / "r.pdf")
