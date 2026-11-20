import pytest

from app.config import Settings, load_settings


def test_settings_read_tsetmc_environment_variables():
    settings = load_settings({
        "TSETMC_TIMEOUT_SECONDS": "15.5",
        "TSETMC_MIN_INTERVAL_SECONDS": "0.5",
        "TSETMC_MAX_RETRIES": "4",
    })

    assert settings.tsetmc_timeout_seconds == 15.5
    assert settings.tsetmc_min_interval_seconds == 0.5
    assert settings.tsetmc_max_retries == 4


def test_settings_use_default_tsetmc_values():
    settings = load_settings({})

    assert settings.tsetmc_timeout_seconds == 20.0
    assert settings.tsetmc_min_interval_seconds == 1.0
    assert settings.tsetmc_max_retries == 2


@pytest.mark.parametrize(
    "variable,value",
    [
        ("TSETMC_TIMEOUT_SECONDS", "0"),
        ("TSETMC_TIMEOUT_SECONDS", "-1"),
        ("TSETMC_TIMEOUT_SECONDS", "nan"),
        ("TSETMC_TIMEOUT_SECONDS", "inf"),
        ("TSETMC_TIMEOUT_SECONDS", "invalid"),
        ("TSETMC_MIN_INTERVAL_SECONDS", "-0.1"),
        ("TSETMC_MIN_INTERVAL_SECONDS", "nan"),
        ("TSETMC_MIN_INTERVAL_SECONDS", "inf"),
        ("TSETMC_MIN_INTERVAL_SECONDS", "invalid"),
        ("TSETMC_MAX_RETRIES", "-1"),
        ("TSETMC_MAX_RETRIES", "1.5"),
        ("TSETMC_MAX_RETRIES", "invalid"),
    ],
)
def test_settings_reject_invalid_environment_values(variable, value):
    with pytest.raises((ValueError, OverflowError)):
        load_settings({variable: value})


def test_settings_reject_boolean_timeout():
    with pytest.raises(ValueError):
        Settings(tsetmc_timeout_seconds=True)


def test_settings_reject_boolean_retries():
    with pytest.raises(ValueError):
        Settings(tsetmc_max_retries=True)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "ftp://cdn.tsetmc.com/api",
        "http://cdn.tsetmc.com/api",
        "https:///api",
        "https://",
        "https://user:pass@cdn.tsetmc.com/api",
        "https://cdn.tsetmc.com:invalid/api",
    ],
)
def test_settings_reject_invalid_tsetmc_base_url(url):
    with pytest.raises(ValueError):
        Settings(tsetmc_base_url=url)


def test_settings_accept_default_tsetmc_base_url():
    settings = Settings()
    assert settings.tsetmc_base_url == "https://cdn.tsetmc.com/api"


@pytest.mark.parametrize(
    "url",
    [
        "https://cdn.tsetmc.com:0/api",
        "https://cdn.tsetmc.com:65536/api",
        "https://cdn.tsetmc.com:abc/api",
        "https://bad host/api",
    ],
)
def test_settings_reject_invalid_ports_and_hosts(url):
    with pytest.raises(ValueError):
        Settings(tsetmc_base_url=url)


@pytest.mark.parametrize("environment", ["", "prod", "testing", "unknown"])
def test_settings_reject_invalid_app_environment(environment):
    with pytest.raises(ValueError):
        Settings(app_env=environment)


@pytest.mark.parametrize("environment", ["development", "production"])
def test_settings_accept_supported_app_environments(environment):
    assert Settings(app_env=environment).app_env == environment


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/api",
        "https://10.0.0.1/api",
        "https://192.168.1.1/api",
        "https://172.16.0.1/api",
        "https://[::1]/api",
        "https://localhost/api",
        "https://service.local/api",
    ],
)
def test_production_rejects_local_and_private_urls(url):
    with pytest.raises(ValueError):
        Settings(app_env="production", tsetmc_base_url=url)


def test_production_accepts_public_tsetmc_url():
    settings = Settings(app_env="production")
    assert settings.tsetmc_base_url == "https://cdn.tsetmc.com/api"


def test_development_allows_local_https_url():
    settings = Settings(
        app_env="development",
        tsetmc_base_url="https://localhost/api",
    )
    assert settings.tsetmc_base_url == "https://localhost/api"
