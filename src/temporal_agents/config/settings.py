from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    temporal_address: str = "localhost:7233"
    temporal_task_queue: str = "agent-task-queue"
    database_url: str = "sqlite+aiosqlite:///./temporal_agents.db"
    agent_database_url: str = "sqlite+aiosqlite:///./agent_definitions.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
