from fastapi import FastAPI
from pydantic import BaseModel

# Create the app
app = FastAPI(title="SyllabusSync API")


# Describe what data the /extract endpoint expects to receive
class SyllabusRequest(BaseModel):
    text: str


# Endpoint 1: a simple check that the server is running
@app.get("/")
def home():
    return {"message": "SyllabusSync API is running"}


# Endpoint 2: receives syllabus text, returns deadlines
@app.post("/extract")
def extract_deadlines(request: SyllabusRequest):
    # Fake data for now. On Day 3, AI will create this list.
    fake_deadlines = [
        {"title": "Homework 1", "date": "2026-09-10", "type": "assignment"},
        {"title": "Midterm Exam", "date": "2026-10-15", "type": "exam"},
        {"title": "Final Project", "date": "2026-12-05", "type": "project"},
    ]

    return {
        "characters_received": len(request.text),
        "deadlines": fake_deadlines,
    }
