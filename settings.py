from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DJANGO_SECRET_KEY:str
    DJANGO_DEBUG:int
    DJANGO_ALLOWED_HOSTS:str
    CSRF_ALLOWED_HOSTS:str
    DB_NAME:str
    DB_HOST:str
    DB_USER:str
    DB_PASSWORD:str
    DB_PORT:int

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "allow"
    }
        
settings = Settings()