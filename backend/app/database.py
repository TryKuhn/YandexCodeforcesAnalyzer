import os
from settings import POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    logging.warning("DATABASE_URL environment variable is not set. Falling back to default PostgreSQL connection string.")
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)



def get_db():
    db = Session()

    try:
        yield db
    finally:
        db.close()