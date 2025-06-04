"""
Audio transcription service using AI models.
"""
import logging
import base64
from typing import Optional
import google.genai.types as types
from config.logging_config import get_logger

logger = get_logger(__name__)


class Transcribe:
    """Service for transcribing audio chunks using AI models."""

    def __init__(self, redis_client, openai_client, gemini_client, elevenlabs_client):
        """
        Initialize the Transcribe service.

        Args:
            redis_client: Redis client for session management
            openai_client: OpenAI client for AI processing
            gemini_client: Gemini client for AI processing
            elevenlabs_client: ElevenLabs client for audio processing
        """
        self.redis_client = redis_client
        self.openai_client = openai_client
        self.gemini_client = gemini_client
        self.elevenlabs_client = elevenlabs_client
  
    async def process_chunk(self, audio_data: str, session_id: str, chunk_number: int) -> None:
        """
        Process an audio chunk for transcription.

        Args:
            audio_data: Base64 encoded audio data
            session_id: Session identifier
            chunk_number: Sequence number of the chunk

        Raises:
            ValueError: If input parameters are invalid
            Exception: If transcription fails
        """
        if not audio_data or not session_id:
            raise ValueError("Audio data and session ID are required")

        if chunk_number < 0:
            raise ValueError("Chunk number must be non-negative")

        logger.info(f"Processing audio chunk {chunk_number} for session {session_id}")

        try:
            # Get current message ID
            identifier_current_message_id = f"session:{session_id}:current_message_id"
            message_id_bytes = self.redis_client.get(identifier_current_message_id)

            if not message_id_bytes:
                raise ValueError(f"Session {session_id} not found or expired")

            message_id = message_id_bytes.decode('utf-8')

            # Track processing chunks
            identifier_process_chunk = f"transcription:{session_id}:message:{message_id}:process"
            self.redis_client.sadd(identifier_process_chunk, str(chunk_number))

            identifier_session = f"transcription:{session_id}:message:{message_id}:chunk"
            self.redis_client.sadd(identifier_session, str(chunk_number))

            # Decode and prepare audio data
            try:
                audio_bytes = base64.b64decode(audio_data)
            except Exception as e:
                raise ValueError(f"Invalid base64 audio data: {str(e)}")

            # Create audio part for Gemini
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type="audio/wav"
            )

            # Transcribe using Gemini
            transcription_prompt = (
                "Transcribe the following audio data. The speaker will use Bahasa Indonesia "
                "or English, so you need to transcribe it accurately in the original language. "
                "Return only the transcribed text without any additional formatting or comments."
            )

            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=[transcription_prompt, audio_part]
            )

            if not response or not response.text:
                raise Exception("Empty transcription response from Gemini")

            # Store transcription result
            identifier_text_chunk = f"transcription:{session_id}:message:{message_id}:{chunk_number}:text"
            self.redis_client.set(identifier_text_chunk, response.text)

            # Set expiration for the transcription (24 hours)
            self.redis_client.expire(identifier_text_chunk, 86400)

            # Remove from processing set
            self.redis_client.srem(identifier_process_chunk, str(chunk_number))

            logger.info(f"Successfully transcribed chunk {chunk_number} for session {session_id}")

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_number} for session {session_id}: {str(e)}")

            # Clean up processing state on error
            try:
                identifier_process_chunk = f"transcription:{session_id}:message:{message_id}:process"
                self.redis_client.srem(identifier_process_chunk, str(chunk_number))
            except:
                pass

            raise Exception(f"Transcription failed: {str(e)}")
    
    