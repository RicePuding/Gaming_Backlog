from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base


# Creating the connection to backlog 
import os

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///backlog.db")
engine = create_engine(DATABASE_URL)


# Creating a session
SessionLocal = sessionmaker(bind=engine)

# Starting template where the games table class will inherit from later
Base = declarative_base()