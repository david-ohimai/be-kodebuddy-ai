import os

from dotenv import load_dotenv
from sqlmodel import SQLModel, create_engine

load_dotenv() 

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL is None:
    raise ValueError("DATABASE_URL is not set.")

# def create_db_and_tables():
#     SQLModel.metadata.create_all(engine)
    
engine = create_engine(
    DATABASE_URL,
    echo=True,
)