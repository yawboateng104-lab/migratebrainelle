from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg://appuser:Po$stgre$$@localhost:5432/appgrowth")

with engine.connect() as conn:
    print("connected")
