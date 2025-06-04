import os
import logging
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import redis
import uuid

from google import genai
from openai import OpenAI
from elevenlabs import ElevenLabs

# Load environment variables
load_dotenv()

from services.transcribe import Transcribe
from services.question_generation import QuestionGeneration
from config.settings import Settings
from config.logging_config import setup_logging

# Initialize settings and logging
settings = Settings()
setup_logging(settings.log_level, settings.log_file)
logger = logging.getLogger(__name__)

# Initialize clients
def create_clients():
    """Create and return AI service clients."""
    try:
        gemini_client = genai.Client(api_key=settings.gemini_api_key)
        openai_client = OpenAI(api_key=settings.openai_api_key)
        elevenlabs_client = ElevenLabs(api_key=settings.elevenlabs_api_key)

        # Redis client with proper configuration
        redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=False,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False
        )

        return gemini_client, openai_client, elevenlabs_client, redis_client

    except Exception as e:
        logger.error(f"Failed to initialize clients: {str(e)}")
        raise

# Initialize clients with error handling
try:
    gemini_client, openai_client, elevenlabs_client, redis_client = create_clients()
    logger.info("Clients initialized successfully")
except Exception as e:
    logger.warning(f"Client initialization failed: {e}")
    # Create mock clients for development
    gemini_client = None
    openai_client = None
    elevenlabs_client = None
    redis_client = None

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None
)

# Add CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Pydantic models with validation
class AudioPayload(BaseModel):
    """Payload for audio processing requests."""
    session_id: str = Field(..., min_length=1, max_length=100, description="Session identifier")
    audio_data: str = Field(..., min_length=1, description="Base64 encoded audio data")
    chunk_number: int = Field(..., ge=0, le=10000, description="Chunk sequence number")
    stream_type: str = Field(..., description="Type of stream processing")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000",
                "audio_data": "UklGRnoGAABXQVZFZm10IBAAAAABAAEA...",
                "chunk_number": 1,
                "stream_type": "chunk"
            }
        }





class SessionResponse(BaseModel):
    """Response model for session creation."""
    session_id: str = Field(..., description="Unique session identifier")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


# Dependency injection for services
def get_transcribe_service() -> Transcribe:
    """Get transcribe service instance."""
    if not all([redis_client, openai_client, gemini_client, elevenlabs_client]):
        raise HTTPException(status_code=503, detail="Service dependencies not available")
    return Transcribe(redis_client, openai_client, gemini_client, elevenlabs_client)


def get_question_generation_service() -> QuestionGeneration:
    """Get question generation service instance."""
    if not all([redis_client, openai_client, gemini_client, elevenlabs_client]):
        raise HTTPException(status_code=503, detail="Service dependencies not available")
    return QuestionGeneration(redis_client, openai_client, gemini_client, elevenlabs_client)


# API Endpoints
@app.post("/stream", summary="Process audio stream", description="Process audio chunks or generate questions")
async def stream(
    payload: AudioPayload,
    transcribe_service: Transcribe = Depends(get_transcribe_service),
    question_service: QuestionGeneration = Depends(get_question_generation_service)
):
    """Process audio stream for transcription or question generation."""
    try:
        logger.info(f"Processing stream request for session {payload.session_id}")

        if payload.stream_type == "chunk":
            await transcribe_service.process_chunk(
                payload.audio_data,
                payload.session_id,
                payload.chunk_number
            )
            return {"status": "chunk_processed", "chunk_number": payload.chunk_number}
        else:
            return StreamingResponse(
                question_service.generate(payload.session_id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
    except Exception as e:
        logger.error(f"Error processing stream: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Stream processing failed: {str(e)}")

@app.post("/start-session", response_model=SessionResponse, summary="Start new session")
async def start_session() -> SessionResponse:
    """Start a new session for audio processing."""
    try:
        session_id = str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        # Initialize session in Redis
        redis_client.sadd(f"session:{session_id}", message_id)
        redis_client.set(f"session:{session_id}:current_message_id", message_id)

        # Set session timeout
        redis_client.expire(f"session:{session_id}", settings.session_timeout)
        redis_client.expire(f"session:{session_id}:current_message_id", settings.session_timeout)

        logger.info(f"Created new session: {session_id}")
        return SessionResponse(session_id=session_id)

    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create session")


@app.get("/health", summary="Health check")
async def health_check():
    """Health check endpoint."""
    try:
        # Test Redis connection if available
        redis_status = "unavailable"
        if redis_client:
            try:
                redis_client.ping()
                redis_status = "connected"
            except Exception:
                redis_status = "disconnected"

        return {
            "status": "healthy",
            "version": settings.app_version,
            "timestamp": asyncio.get_event_loop().time(),
            "redis": redis_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service unavailable")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        access_log=True
    )
