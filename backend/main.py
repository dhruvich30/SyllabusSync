import os
import re
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load secrets from the .env file (GEMINI_API_KEY)
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
# Leave GEMINI_MODEL out of .env to auto-pick the newest Flash model your key can use.
# To force a specific model, add e.g. GEMINI_MODEL=gemini-2.5-flash to .env
MODEL = os.getenv("GEMINI_MODEL")

app = FastAPI(title="SyllabusSync API")

# Allow the Next.js website (Day 4) to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Data shapes ----------

class SyllabusRequest(BaseModel):
    text: str = Field(min_length=20, max_length=50_000, description="The syllabus text")
    year: int | None = Field(default=None, description="Year to use when the syllabus leaves it out")


class Deadline(BaseModel):
    title: str = Field(description="Short name, e.g. 'Midterm Exam' or 'Homework 3'")
    date: str = Field(description="Due date in YYYY-MM-DD format")
    time: str | None = Field(default=None, description="Due time in 24-hour HH:MM, only if the syllabus gives one")
    type: str = Field(description="One of: exam, quiz, assignment, project, other")


class ExtractResponse(BaseModel):
    course: str | None = Field(default=None, description="Course code or name, if stated")
    deadlines: list[Deadline]


# ---------- The prompt sent to the AI ----------

def build_prompt(text: str, year: int) -> str:
    return f"""You extract deadlines from a college course syllabus.

Rules:
- Find every exam, quiz, assignment, homework, project, paper, lab, and presentation that has a specific date.
- Only include items that are actually in the text. Never invent deadlines.
- Write dates as YYYY-MM-DD. If a date has no year, use {year}.
- Include a time (24-hour HH:MM) only if the syllabus states one.
- type must be one of: exam, quiz, assignment, project, other.
- Skip recurring items that have no specific date (e.g. "weekly readings").

Syllabus:
\"\"\"
{text}
\"\"\""""


# ---------- Choosing a model ----------

def available_models(client) -> list[str]:
    """Ask Google which models this API key can use for text generation."""
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.removeprefix("models/"))
    return names


def version_of(name: str) -> float:
    match = re.search(r"gemini-(\d+(?:\.\d+)?)", name)
    return float(match.group(1)) if match else 0.0


def pick_model(client) -> str:
    """Pick the newest stable Gemini Flash model (fast, cheap, free-tier friendly)."""
    global MODEL
    if MODEL:
        return MODEL
    names = [n for n in available_models(client) if n.startswith("gemini")]
    skip = ("lite", "image", "tts", "audio", "live", "embedding", "thinking")
    flash = [n for n in names if "flash" in n and not any(s in n for s in skip)]
    stable = [n for n in flash if "preview" not in n and "exp" not in n]
    for group in (stable, flash, names):
        if group:
            # newest version first; among equals, the shortest (base) name
            MODEL = sorted(group, key=lambda n: (-version_of(n), len(n)))[0]
            return MODEL
    raise HTTPException(status_code=502, detail="No Gemini models are available for this API key.")


# ---------- Endpoints ----------

@app.get("/")
def home():
    return {"message": "SyllabusSync API is running", "model": MODEL or "auto (picked on first request)", "api_key_loaded": bool(API_KEY)}


@app.get("/models")
def list_models():
    """Shows which Gemini models your key can use. Handy for debugging."""
    client = genai.Client(api_key=API_KEY)
    try:
        return {"in_use": pick_model(client), "available": available_models(client)}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Could not list models: {error}")


@app.post("/extract", response_model=ExtractResponse)
def extract_deadlines(request: SyllabusRequest):
    if not API_KEY or API_KEY == "paste-your-key-here":
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is missing. Add it to backend/.env and restart the server.")

    client = genai.Client(api_key=API_KEY)
    year = request.year or date.today().year

    try:
        response = client.models.generate_content(
            model=pick_model(client),
            contents=build_prompt(request.text, year),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",  # ask for JSON, not chatty text
                response_schema=ExtractResponse,          # ...in exactly this shape
                temperature=0,                             # same input -> same answer
            ),
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"AI request failed: {error}")

    result = response.parsed
    if result is None:
        try:
            result = ExtractResponse.model_validate_json(response.text or "")
        except Exception:
            raise HTTPException(status_code=502, detail="The AI returned something we couldn't read. Try again.")

    # Earliest deadline first
    result.deadlines.sort(key=lambda d: (d.date, d.time or ""))
    return result
