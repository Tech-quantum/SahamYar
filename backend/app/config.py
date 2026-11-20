import ipaddress
import math
import os
from dataclasses import dataclass
from collections.abc import Mapping
from urllib.parse import urlsplit


@dataclass
class Settings:
    app_name: str = "SahamYar API"
    app_env: str = "development"
    tsetmc_base_url: str = "https://cdn.tsetmc.com/api"
    tsetmc_timeout_seconds: float = 20.0
    tsetmc_min_interval_seconds: float = 1.0
    tsetmc_max_retries: int = 2

    def __post_init__(self):
        if self.app_env not in ("development", "production"):
            raise ValueError(
                "app_env must be 'development' or 'production'."
            )

        if not isinstance(self.tsetmc_base_url, str):
            raise ValueError("tsetmc_base_url must be a valid HTTPS URL.")

        try:
            parsed_url = urlsplit(self.tsetmc_base_url)
            valid_url = (
                parsed_url.scheme == "https"
                and bool(parsed_url.hostname)
                and parsed_url.username is None
                and parsed_url.password is None
                and parsed_url.port != 0
                and not any(char.isspace() for char in self.tsetmc_base_url)
            )
        except ValueError:
            valid_url = False

        if not valid_url:
            raise ValueError("tsetmc_base_url must be a valid HTTPS URL.")

        if self.app_env == "production":
            hostname = parsed_url.hostname.lower().rstrip(".")
            try:
                address = ipaddress.ip_address(hostname)
                is_unsafe_host = not address.is_global
            except ValueError:
                is_unsafe_host = (
                    hostname == "localhost"
                    or hostname.endswith(
                        (".localhost", ".local", ".internal", ".lan")
                    )
                    or "." not in hostname
                )

            if is_unsafe_host:
                raise ValueError(
                    "tsetmc_base_url must not point to a local or non-public host in production."
                )

        for name in ("tsetmc_timeout_seconds", "tsetmc_min_interval_seconds"):
            value = getattr(self, name)
            valid = (
                not isinstance(value, bool)
                and isinstance(value, (int, float))
                and math.isfinite(value)
                and value >= 0
            )
            if not valid or (name == "tsetmc_timeout_seconds" and value == 0):
                raise ValueError(f"Invalid value for {name}: {value!r}")

        if (
            isinstance(self.tsetmc_max_retries, bool)
            or not isinstance(self.tsetmc_max_retries, int)
            or self.tsetmc_max_retries < 0
        ):
            raise ValueError("tsetmc_max_retries must be a non-negative integer.")


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ

    return Settings(
        app_name=env.get("APP_NAME", "SahamYar API"),
        app_env=env.get("APP_ENV", "development"),
        tsetmc_base_url=env.get("TSETMC_BASE_URL", "https://cdn.tsetmc.com/api"),
        tsetmc_timeout_seconds=float(env.get("TSETMC_TIMEOUT_SECONDS", "20.0")),
        tsetmc_min_interval_seconds=float(env.get("TSETMC_MIN_INTERVAL_SECONDS", "1.0")),
        tsetmc_max_retries=int(env.get("TSETMC_MAX_RETRIES", "2")),
    )


settings = load_settings()
