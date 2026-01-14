#!/usr/bin/env python3
"""
FastAPI Backend for Music Production Tutorial RAG System
Handles vector search, chat queries, and document management
"""

import os
import json
import mmh3
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pymilvus import MilvusClient
import openai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MILVUS_URI = os.getenv("MILVUS_URI")
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN")
COLLECTION_NAME = "music_production_tutorials"

# Initialize OpenAI client
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Global state
_milvus_client: Optional[MilvusClient] = None


# Pydantic Models
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=1000)
    conversation_history: List[ChatMessage] = Field(default_factory=list, max_items=20)


class SearchResult(BaseModel):
    text: str
    channel_name: str
    metadata: Dict[str, Any]
    score: float


class ChatResponse(BaseModel):
    response: str
    sources: List[SearchResult]


class AddDocumentRequest(BaseModel):
    text: str
    metadata: str  # JSON string


class AddDocumentResponse(BaseModel):
    message: str
    status: str


class HealthResponse(BaseModel):
    status: str
    milvus_connected: bool


class StatsResponse(BaseModel):
    collection_name: str
    stats: Dict[str, Any]


# Database utilities
def get_milvus_client() -> Optional[MilvusClient]:
    """Get the global Milvus client instance."""
    return _milvus_client


def create_milvus_collection(client: MilvusClient, collection_name: str) -> None:
    """Create Milvus collection using simplified API."""
    # MilvusClient simplified API for serverless
    client.create_collection(
        collection_name=collection_name,
        dimension=3072,  # text-embedding-3-large dimension
        metric_type="COSINE",
        id_type="int",
        max_length=65535
    )

    print(f"Collection '{collection_name}' created successfully")


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding using OpenAI API."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-large",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error generating embedding: {str(e)}"
        )


async def search_similar_segments(
    client: MilvusClient,
    collection_name: str,
    embedding: List[float],
    limit: int = 5,
    channel_name: Optional[str] = None
) -> List[SearchResult]:
    """Search Milvus for similar documents."""
    filter_expr = f'channel_name == "{channel_name}"' if channel_name else None

    try:
        results = client.search(
            collection_name=collection_name,
            data=[embedding],
            limit=limit,
            filter=filter_expr,
            output_fields=["text", "channel_name", "metadata"]
        )

        search_results = []
        for hit in results[0]:
            entity = hit.get("entity", {})
            search_results.append(
                SearchResult(
                    text=entity.get("text", ""),
                    channel_name=entity.get("channel_name", ""),
                    metadata=json.loads(entity.get("metadata", "{}")),
                    score=hit.get("distance", 0)
                )
            )

        return search_results

    except Exception as e:
        print(f"Error searching Milvus: {e}")
        return []


def format_context_from_results(results: List[SearchResult]) -> str:
    """Format search results as context for the LLM."""
    if not results:
        return "No relevant information found."

    context_parts = []
    for idx, result in enumerate(results, 1):
        context_parts.append(f"{idx}. [{result.channel_name}] {result.text}")

    return "\n\n".join(context_parts)


async def generate_chat_completion(
    user_message: str,
    context: str,
    conversation_history: List[ChatMessage]
) -> str:
    """Generate response using GPT-3.5-turbo."""
    try:
        messages = [
            {
                "role": "system",
                "content": f"""You are an AI assistant specialized in music production tutorials.
Use the following context from music production YouTube videos to answer the user's question.
Include specific techniques, DAW names, and plugin references when mentioned.

Format your response with proper markdown for readability:
- Use **bold** for important terms, DAW names, and plugin names
- Use bullet points or numbered lists when listing multiple items
- Use `code blocks` for technical settings or parameters
- Break up long paragraphs into shorter, digestible sections
- Use headers (##) for distinct sections if needed

Context:
{context}"""
            }
        ]

        # Add conversation history (last 10 messages)
        for msg in conversation_history[-10:]:
            messages.append({"role": msg.role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": user_message})

        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )

        return response.choices[0].message.content

    except Exception as e:
        print(f"Error generating chat response: {e}")
        return "I apologize, but I encountered an error generating a response. Please try again."


def calculate_text_hash(text: str) -> int:
    """Calculate Murmur3 hash for text deduplication."""
    return mmh3.hash(text, signed=False)


async def insert_document(
    client: MilvusClient,
    collection_name: str,
    text: str,
    metadata_str: str
) -> AddDocumentResponse:
    """Add a document to the RAG system."""
    # Hash text for deduplication
    text_hash = calculate_text_hash(text)

    # Check if exists
    existing = client.query(
        collection_name=collection_name,
        filter=f"id == {text_hash}",
        output_fields=["id"]
    )

    if existing:
        return AddDocumentResponse(
            message="Document already exists",
            status="duplicate"
        )

    # Generate embedding
    embedding = await generate_embedding(text)

    # Parse metadata
    metadata_dict = json.loads(metadata_str)
    channel_name = metadata_dict.get("channel_name", "Unknown")

    # Insert into Milvus
    data = [{
        "id": text_hash,
        "text": text,
        "vector": embedding,
        "channel_name": channel_name,
        "metadata": metadata_str
    }]

    client.insert(collection_name=collection_name, data=data)

    return AddDocumentResponse(
        message="Document added successfully",
        status="success"
    )


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown events."""
    global _milvus_client

    # Startup
    print("Starting up...")

    try:
        _milvus_client = MilvusClient(uri=MILVUS_URI, token=MILVUS_TOKEN)
        print(f"Connected to Milvus at {MILVUS_URI}")

        # Create collection if it doesn't exist
        collections = _milvus_client.list_collections()
        if COLLECTION_NAME not in collections:
            print(f"Creating collection: {COLLECTION_NAME}")
            create_milvus_collection(_milvus_client, COLLECTION_NAME)
        else:
            print(f"Collection '{COLLECTION_NAME}' already exists")

    except Exception as e:
        print(f"Error connecting to Milvus: {e}")
        print("You need to set up Milvus. Sign up at https://cloud.zilliz.com")
        _milvus_client = None

    yield

    # Shutdown
    if _milvus_client:
        _milvus_client.close()
        print("Milvus connection closed")


# Initialize FastAPI app
app = FastAPI(
    title="Music Production Tutorial RAG API",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
from pathlib import Path
Path("static/css").mkdir(parents=True, exist_ok=True)
Path("static/js").mkdir(parents=True, exist_ok=True)
Path("templates").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# Routes
@app.get("/", response_class=HTMLResponse)
async def get_root(request: Request) -> HTMLResponse:
    """Serve the main web interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def post_chat(request: ChatRequest) -> ChatResponse:
    """Main chat endpoint for querying the RAG system."""
    client = get_milvus_client()

    if not client:
        raise HTTPException(
            status_code=503,
            detail="Milvus not connected. Please configure MILVUS_URI and MILVUS_TOKEN in .env"
        )

    try:
        # Generate embedding for user message
        embedding = await generate_embedding(request.message)

        # Search for similar segments
        results = await search_similar_segments(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding=embedding,
            limit=5
        )

        # Format context
        context = format_context_from_results(results)

        # Generate response
        response_text = await generate_chat_completion(
            user_message=request.message,
            context=context,
            conversation_history=request.conversation_history
        )

        return ChatResponse(
            response=response_text,
            sources=results
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/add-document", response_model=AddDocumentResponse)
async def post_add_document(request: AddDocumentRequest) -> AddDocumentResponse:
    """Add a document to the RAG system."""
    client = get_milvus_client()

    if not client:
        raise HTTPException(
            status_code=503,
            detail="Milvus not connected"
        )

    try:
        return await insert_document(
            client=client,
            collection_name=COLLECTION_NAME,
            text=request.text,
            metadata_str=request.metadata
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    """Health check endpoint."""
    client = get_milvus_client()
    is_connected = client is not None

    return HealthResponse(
        status="healthy" if is_connected else "degraded",
        milvus_connected=is_connected
    )


@app.get("/api/stats", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get collection statistics."""
    client = get_milvus_client()

    if not client:
        raise HTTPException(
            status_code=503,
            detail="Milvus not connected"
        )

    try:
        stats = client.get_collection_stats(COLLECTION_NAME)
        return StatsResponse(
            collection_name=COLLECTION_NAME,
            stats=stats
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
