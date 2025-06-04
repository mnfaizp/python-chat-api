"""
Application settings and configuration management.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Configuration
    app_name: str = Field(default="Python Chat API", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    
    # Security
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"], 
        env="ALLOWED_ORIGINS"
    )
    secret_key: str = Field(default="your-secret-key-change-in-production", env="SECRET_KEY")
    
    # Database Configuration
    redis_host: str = Field(default="localhost", env="REDIS_HOST")
    redis_port: int = Field(default=6379, env="REDIS_PORT")
    redis_db: int = Field(default=0, env="REDIS_DB")
    redis_password: Optional[str] = Field(default=None, env="REDIS_PASSWORD")
    
    postgres_server: Optional[str] = Field(default=None, env="POSTGRES_SERVER")
    postgres_user: Optional[str] = Field(default=None, env="POSTGRES_USER")
    postgres_password: Optional[str] = Field(default=None, env="POSTGRES_PASSWORD")
    postgres_db: Optional[str] = Field(default=None, env="POSTGRES_DB")
    
    # AI Service API Keys
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")
    elevenlabs_api_key: str = Field(..., env="ELEVEN_LABS_API_KEY")
    open_router_api_key: Optional[str] = Field(default=None, env="OPEN_ROUTER_API_KEY")
    
    # Audio Processing
    max_audio_chunk_size: int = Field(default=25 * 1024 * 1024, env="MAX_AUDIO_CHUNK_SIZE")  # 25MB
    temp_dir: str = Field(default="./tmp", env="TEMP_DIR")
    
    # Session Configuration
    session_timeout: int = Field(default=3600, env="SESSION_TIMEOUT")  # 1 hour
    max_sessions_per_user: int = Field(default=5, env="MAX_SESSIONS_PER_USER")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: Optional[str] = Field(default=None, env="LOG_FILE")
    
    @validator("allowed_origins", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("log_level")
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
