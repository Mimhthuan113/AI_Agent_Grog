from src.config import Settings


def _settings(**overrides) -> Settings:
    base = {
        "GROQ_API_KEY": "gsk_primary",
        "ADMIN_PASSWORD": "admin-password",
    }
    base.update(overrides)
    return Settings(**base)


def test_groq_numbered_keys_are_split_between_chat_and_vision():
    settings = _settings(
        GROQ_API_KEY_2="gsk_second",
        GROQ_API_KEY_3="gsk_third",
        GROQ_API_KEY_4="gsk_fourth",
    )

    assert settings.groq_all_api_key_list == [
        "gsk_primary",
        "gsk_second",
        "gsk_third",
        "gsk_fourth",
    ]
    assert settings.groq_chat_api_key_list == [
        "gsk_primary",
        "gsk_second",
        "gsk_third",
    ]
    assert settings.groq_vision_api_key_list == ["gsk_fourth"]


def test_explicit_groq_key_pools_override_default_split():
    settings = _settings(
        GROQ_API_KEY_2="gsk_second",
        GROQ_CHAT_API_KEYS="gsk_chat_1,gsk_chat_2",
        GROQ_VISION_API_KEYS="gsk_vision",
    )

    assert settings.groq_chat_api_key_list == ["gsk_chat_1", "gsk_chat_2"]
    assert settings.groq_vision_api_key_list == ["gsk_vision"]


def test_groq_key_parser_deduplicates_csv_values():
    settings = _settings(GROQ_API_KEYS="gsk_primary, gsk_extra, gsk_extra")

    assert settings.groq_all_api_key_list == ["gsk_primary", "gsk_extra"]
