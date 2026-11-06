import pytest

from abreveilverdetto.settings import ConfigError, Settings, derive_webhook_secret


def test_token_obbligatorio():
    with pytest.raises(ConfigError):
        Settings.from_env({})


def test_default_polling_e_segreto_stabile():
    s = Settings.from_env({"TELEGRAM_TOKEN": "1:abc"})
    assert not s.use_webhook
    assert s.webhook_secret == derive_webhook_secret("1:abc")
    assert s.webhook_secret == Settings.from_env({"TELEGRAM_TOKEN": "1:abc"}).webhook_secret
    assert s.webhook_secret != derive_webhook_secret("1:abd")
    assert "1:abc" not in s.webhook_secret


def test_webhook():
    s = Settings.from_env({"TELEGRAM_TOKEN": "1:abc", "WEBHOOK_BASE_URL": "https://bot.example.app/", "PORT": "9000"})
    assert s.use_webhook
    assert s.webhook_url == "https://bot.example.app/telegram"
    assert s.port == 9000


@pytest.mark.parametrize("secret", ["con spazi", "x" * 257, "àccento"])
def test_webhook_secret_non_valido(secret):
    with pytest.raises(ConfigError):
        Settings.from_env({"TELEGRAM_TOKEN": "1:abc", "WEBHOOK_SECRET": secret})
