import os

from sqlalchemy import create_engine


def get_engine():
    url = (
        f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@db:5432/{os.environ['POSTGRES_DB']}"
    )
    return create_engine(url)
