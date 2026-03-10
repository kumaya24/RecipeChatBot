from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

from llm_pre_es import run_agent          
from llm_handler import RecipeAssistant    

app = FastAPI(title="Recipe Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_methods=["*"],
    allow_headers=["*"],
)

assistants: dict[str, RecipeAssistant] = {}


class SearchRequest(BaseModel):
    query: str                  

class SearchResponse(BaseModel):
    summary: str                
    session_id: str             

class ChatRequest(BaseModel):
    session_id: str             
    message: str                
    recipe_text: Optional[str] = None  

class ChatResponse(BaseModel):
    answer: str


@app.post("/search", response_model=SearchResponse)
def search_recipes_endpoint(req: SearchRequest):
    """
    Step 1 — Search for recipes.
    Send the user's natural-language query; get back a recipe summary
    and a session_id to use for follow-up questions.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty.")

    summary = run_agent(req.query)
    session_id = str(uuid.uuid4())
    return SearchResponse(summary=summary, session_id=session_id)


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    """
    Step 2 — Ask follow-up questions about a recipe.
    On the first call, include recipe_text to initialise the assistant.
    Subsequent calls only need session_id + message.
    """
    if req.session_id not in assistants:
        if not req.recipe_text:
            raise HTTPException(
                status_code=400,
                detail="recipe_text is required for the first message in a session."
            )
        assistants[req.session_id] = RecipeAssistant(req.recipe_text)

    assistant = assistants[req.session_id]
    answer = assistant.ask(req.message, req.session_id)
    return ChatResponse(answer=answer)


@app.delete("/session/{session_id}")
def clear_session(session_id: str):
    """Optional — clear a session to free memory."""
    assistants.pop(session_id, None)
    return {"deleted": session_id}


@app.get("/health")
def health():
    return {"status": "ok"}