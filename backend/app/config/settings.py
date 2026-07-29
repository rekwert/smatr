from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Smart Money AI Scanner"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    database_url: str = "postgresql+asyncpg://smas:smas@localhost:5433/smas"
    redis_url: str = "redis://localhost:6380/0"

    bybit_base_url: str = "https://api.bybit.com"
    bybit_ws_url: str = "wss://stream.bybit.com/v5/public/linear"
    bybit_category: str = "linear"

    scan_interval_seconds: int = 120
    scan_symbol_limit: int = 50
    # Universe Engine v2
    universe_cheap_limit: int = 200
    universe_heavy_limit: int = 80
    universe_trade_ideas: int = 15
    history_per_exchange: int = 12
    default_timeframes: str = "15,60,240,D"
    min_signal_score: int = 50

    llm_enabled: bool = False
    llm_api_key: str = ""
    llm_api_base: str = ""
    llm_model: str = "deepseek-chat"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    notify_cooldown_minutes: int = 30
    notify_min_score: int = 90

    enabled_exchanges: str = "bybit,okx,bitget,mexc,bingx,kucoin"

    cors_origins: str = "http://localhost:3001,http://localhost:3000"

    @property
    def timeframe_list(self) -> list[str]:
        return [t.strip() for t in self.default_timeframes.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def exchange_list(self) -> list[str]:
        return [e.strip().lower() for e in self.enabled_exchanges.split(",") if e.strip()]


settings = Settings()
