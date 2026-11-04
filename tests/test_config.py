from app.core.config import Settings


def test_builds_database_url_from_postgres_variables() -> None:
    settings = Settings(
        postgres_user="user",
        postgres_password="p@ss",
        postgres_host="db",
        postgres_port=5432,
        postgres_db="app_db",
    )

    url = settings.sqlalchemy_database_url

    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "user"
    assert url.password == "p@ss"
    assert url.host == "db"
    assert url.port == 5432
    assert url.database == "app_db"
    assert (
        url.render_as_string(hide_password=False)
        == "postgresql+asyncpg://user:p%40ss@db:5432/app_db"
    )


def test_empty_provider_keys_become_none() -> None:
    settings = Settings(jina_api_key="", deepseek_api_key="")

    assert settings.jina_api_key is None
    assert settings.deepseek_api_key is None


def test_builds_rabbitmq_url_and_honors_override() -> None:
    settings = Settings(
        rabbitmq_user="user",
        rabbitmq_password="p@ss",
        rabbitmq_host="rabbit",
        rabbitmq_port=5673,
    )
    override = Settings(celery_broker_url="amqp://managed:5672//")

    assert settings.rabbitmq_url == "amqp://user:p%40ss@rabbit:5673//"
    assert override.rabbitmq_url == "amqp://managed:5672//"


def test_explicit_database_url_overrides_components() -> None:
    settings = Settings(
        postgres_user="ignored",
        postgres_host="localhost",
        database_url="postgresql+asyncpg://user:secret@managed:5432/app_db",
    )

    url = settings.sqlalchemy_database_url

    assert url.host == "managed"
    assert url.username == "user"
    assert url.database == "app_db"
