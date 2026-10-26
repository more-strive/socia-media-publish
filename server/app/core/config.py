"""全局配置：从环境变量 / .env 加载"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 应用
    app_name: str = "social-media-publish"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = ""

    # 安全
    secret_key: str = "change-me-to-a-random-long-secret"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 14

    # MySQL
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "root123456"
    mysql_database: str = "social_publish"
    mysql_pool_size: int = 10
    mysql_max_overflow: int = 20

    # Redis
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # 业务开关
    mock_publish: bool = True
    dev_return_sms_code: bool = True

    # 上传（RPA 截图等），经 /api/v1/files 静态暴露
    upload_dir: str = "uploads"

    # AI
    ark_api_key: str = ""
    ark_model: str = "doubao-seed-1-6-250615"
    seedance_api_key: str = ""
    ai_mock_delay_seconds: int = 10

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
