from eventflow.config import Settings


def test_blank_secrets_mean_not_set() -> None:
    settings = Settings(_env_file=None, api_key="", groq_api_key="  ", langfuse_public_key="")
    assert settings.api_key is None
    assert settings.groq_api_key is None
    assert settings.langfuse_public_key is None


def test_real_values_are_kept() -> None:
    settings = Settings(_env_file=None, api_key="secret")
    assert settings.api_key.get_secret_value() == "secret"


def test_database_url_override_wins() -> None:
    settings = Settings(_env_file=None, database_url_override="sqlite:///x.db")
    assert settings.database_url == "sqlite:///x.db"
