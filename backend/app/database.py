from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from settings import POSTGRES_URL

engine = create_engine(POSTGRES_URL)
Session = sessionmaker(bind=engine)


def get_db():
    db = Session()

    try:
        yield db
    finally:
        db.close()
