from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str
    rule_version: str = 'v1-first-feasible'
    simulation_mode: bool = False
    scheduling_deviation_minutes: int = 0
settings = Settings()
