from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_url: str = "mysql+aiomysql://nestgrow:nestgrow@db/nestgrow_db"
    mqtt_host: str = "mosquitto"
    mqtt_port: int = 1883
    license_server_url: str = "https://license.lake8.dev"
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 8
    admin_password: str = "admin"
    admin_username: str = "admin"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
