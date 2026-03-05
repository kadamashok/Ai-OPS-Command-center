import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str = os.getenv("SERVICE_NAME", "carop-service")
    environment: str = os.getenv("ENVIRONMENT", "dev")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-prod")
    jwt_alg: str = os.getenv("JWT_ALG", "HS256")
    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        "postgresql://carop:carop@localhost:5432/carop",
    )


settings = Settings()
