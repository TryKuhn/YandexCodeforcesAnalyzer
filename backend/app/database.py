import os
from settings import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    # add logging here to inform that env var is not set
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)



def get_db():
    db = Session()

    try:
        yield db
    finally:
        db.close()