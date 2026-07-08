import sys
sys.path.insert(0, ".")
from cluedo.config import load_bundled_edition
from cluedo.game import GameState
from cluedo.models import Player, SuggestionResponse
from cluedo.analysis.patterns import analyze_player_patterns

cfg = load_bundled_edition("classic_uk")
cards_by_name = {c.name: c for c in cfg.all_cards()}
players = [Player("Alice", 0, 6), Player("Bob", 1, 6), Player("Carol", 2, 6)]

gs = GameState(cfg, players, user_seat=2)
carols_hand = ["Kitchen", "Ballroom", "Conservatory", "Lounge", "Hall", "Study"]
gs.set_user_hand([cards_by_name[n] for n in carols_hand])

suggestions = [
    ("Miss Scarlett", "Candlestick", "Kitchen"),
    ("Colonel Mustard", "Knife", "Ballroom"),
    ("Mrs. White", "Lead Pipe", "Conservatory"),
    ("Reverend Green", "Revolver", "Dining Room"),
    ("Mrs. Peacock", "Rope", "Billiard Room"),
    ("Professor Plum", "Wrench", "Library"),
    ("Reverend Green", "Revolver", "Dining Room"),
    ("Reverend Green", "Revolver", "Dining Room"),
    ("Reverend Green", "Revolver", "Dining Room"),
    ("Reverend Green", "Revolver", "Dining Room"),
]
for i, (suspect, weapon, room) in enumerate(suggestions):
    gs.record_suggestion(1, cards_by_name[suspect], cards_by_name[weapon], cards_by_name[room], [SuggestionResponse(0, "no_show")])
    print(i, "DiningRoom=", gs.engine.confirmed.get(cards_by_name["Dining Room"]),
          "BilliardRoom=", gs.engine.confirmed.get(cards_by_name["Billiard Room"]),
          "Library=", gs.engine.confirmed.get(cards_by_name["Library"]))

stats = analyze_player_patterns(gs, seat=1)
print("redundant", stats.redundant_suggestion_count)
print("coverage cards", len(stats.card_frequency), len(stats.never_suggested))
