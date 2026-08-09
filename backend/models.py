from sqlalchemy import Column, Integer, String
from database import Base



# Creating the table using the base from the database
class Game(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True)
    title = Column(String)
    status = Column(String)
    
    priority = Column(Integer)
    estimated_hours = Column(Integer)
    