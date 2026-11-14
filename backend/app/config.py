import os
from dataclasses import dataclass

@dataclass
class Settings:
    app_name: str = "SahamYar API"
    app_env: str = "development"
    tsetmc_base_url: str = "https://cdn.tsetmc.com/api"
    tsetmc_timeout_seconds: float = 20.0
    tsetmc_min_interval_seconds: float = 1.0
    tsetmc_max_retries: int = 2

settings = Settings(
    app_name=os.getenv("APP_NAME", "SahamYar API"),
    app_env=os.getenv("APP_ENV", "development"),
    tsetmc_base_url=os.getenv("TSETMC_BASE_URL", "https://cdn.tsetmc.com/api"),
)
