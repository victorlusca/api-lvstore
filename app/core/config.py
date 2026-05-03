import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    APP_NAME: str = "LV Store API"
    VERSION: str = "3.1.0"
    DEBUG: bool = Field(False, validation_alias="API_DEBUG")
    
    # Square Cloud
    SQUARE_CLOUD_API_TOKEN: str = Field("", validation_alias="SQUARECLOUD_API_TOKEN")
    SQUARE_CLOUD_APP_ID: str = Field("", validation_alias="SQUARECLOUD_APP_ID")
    
    # Security
    API_KEY: str = Field("lvstore_default_hash_16_char", validation_alias="API_KEY")
    
    # Server
    PORT: int = Field(8000, validation_alias="API_PORT")
    HOST: str = Field("0.0.0.0", validation_alias="API_HOST")

settings = Settings()
