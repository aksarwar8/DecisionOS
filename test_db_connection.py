
from sqlalchemy import text
from backend.database import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT current_user, current_database()"))
        print(result.fetchone())
        print("Successfully connected to PostgreSQL!")

except Exception as e:
    print("Connection failed!")
    print(e)
