from fastapi import FastAPI
from pydantic import BaseModel
from .database.databaseConnection import engine

class Item(BaseModel):
    name: str
    description: str = None
    price: float
    tax: float = None


try:
    connection = engine.connect()
    print("✅ PostgreSQL Connected Successfully!")
    connection.close()

except Exception as e:
    print("❌ Connection Failed")
    print(e)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/items/{item_id}")
async def read_item(item_id: int, q: str = None):
    return {"item_id": item_id, "q": q}

@app.post("/item/")
async def create_item(item: Item):
    return [item.name, item.description, item.price, item.tax]