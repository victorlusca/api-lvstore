import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    APP_NAME: str = "API Oficial da ™LV Store"
    VERSION: str = "3.1.1"
    DEBUG: bool = Field(False, validation_alias="API_DEBUG")
    
    # Square Cloud
    SQUARE_CLOUD_API_TOKEN: str = Field("", validation_alias="SQUARECLOUD_API_TOKEN")
    SQUARE_CLOUD_APP_ID: str = Field("", validation_alias="SQUARECLOUD_APP_ID")
    
    # Security
    # Sem valor padrao por design: uma chave-mestra versionada no repositorio da
    # acesso "admin:*" a quem ler o codigo. Vazia significa "master key desligada"
    # (ver app/auth.py::validate_token), nunca "aceita qualquer coisa".
    API_KEY: str = Field("", validation_alias="API_KEY")
    
    # Server
    PORT: int = Field(8000, validation_alias="API_PORT")
    HOST: str = Field("0.0.0.0", validation_alias="API_HOST")

settings = Settings()
