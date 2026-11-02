import os

from sqlalchemy import create_engine


def get_engine():
    # Credenciais vêm do .env, nunca do código. "db" é o nome do serviço no compose.
    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@db:5432/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url)
