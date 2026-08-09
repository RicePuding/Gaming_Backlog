from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base


# Creating the connection to backlog 
engine = create_engine("sqlite:///backlog.db")

# Creating a session
SessionLocal = sessionmaker(bind=engine)

# Starting template where the games table class will inherit from later
Base = declarative_base()