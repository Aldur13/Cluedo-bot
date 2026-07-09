import pytest

from cluedo.config import ConfigError, load_bundled_edition, validate_card_config


def test_validate_card_config_rejects_duplicate_names_across_categories():
    data = {
        "edition": "Test Edition",
        "suspects": ["Miss Scarlett", "Colonel Mustard"],
        "weapons": ["Miss Scarlett", "Rope"],  # duplicate against a suspect
        "rooms": ["Kitchen"],
    }
    with pytest.raises(ConfigError):
        validate_card_config(data)


def test_validate_card_config_rejects_missing_keys():
    with pytest.raises(ConfigError):
        validate_card_config({"edition": "Test Edition", "suspects": ["A"], "weapons": ["B"]})


def test_validate_card_config_rejects_empty_category():
    data = {"edition": "Test Edition", "suspects": [], "weapons": ["Rope"], "rooms": ["Kitchen"]}
    with pytest.raises(ConfigError):
        validate_card_config(data)


def test_validate_card_config_accepts_well_formed_data():
    data = {
        "edition": "Test Edition",
        "suspects": ["Miss Scarlett", "Colonel Mustard"],
        "weapons": ["Rope"],
        "rooms": ["Kitchen"],
    }
    cfg = validate_card_config(data)
    assert cfg.edition == "Test Edition"
    assert cfg.suspects == ("Miss Scarlett", "Colonel Mustard")


def test_load_bundled_edition_unknown_key_raises_config_error():
    with pytest.raises(ConfigError):
        load_bundled_edition("totally_unknown_edition")


def test_load_bundled_edition_invalid_json_raises_config_error(monkeypatch):
    # Regression: load_bundled_edition used to call json.loads(raw) directly
    # with no try/except, unlike load_card_config -- a malformed bundled file
    # raised a raw json.JSONDecodeError instead of the module's own
    # ConfigError, breaking callers (e.g. list_bundled_editions) that only
    # catch ConfigError.
    import cluedo.config as config_module

    class _BrokenResource:
        def read_text(self, encoding="utf-8"):
            return "{not valid json"

    class _BrokenFiles:
        def joinpath(self, _name):
            return _BrokenResource()

    monkeypatch.setattr(config_module.resources, "files", lambda _pkg: _BrokenFiles())

    with pytest.raises(ConfigError):
        load_bundled_edition("swedish_2012")
