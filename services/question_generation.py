"""
Question generation service for interview scenarios.
"""
import asyncio
import json
import logging
from typing import Dict, Any, AsyncGenerator
import google.genai.types as types
from config.logging_config import get_logger

logger = get_logger(__name__)


class QuestionGeneration:
    """Service for generating interview questions based on user responses."""

    def __init__(self, redis_client, openai_client, gemini_client, elevenlabs_client):
        """
        Initialize the QuestionGeneration service.

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
    
    async def generate(self, session_id: str) -> AsyncGenerator[str, None]:
        """
        Generate interview questions based on user responses.

        Args:
            session_id: Session identifier

        Yields:
            Server-sent events with question data

        Raises:
            ValueError: If session is invalid
            Exception: If question generation fails
        """
        if not session_id:
            raise ValueError("Session ID is required")

        logger.info(f"Generating questions for session {session_id}")

        try:
            # Fetch user answer from transcription
            fetch_data = await self.fetch_answer(session_id)
            user_answer = fetch_data.get('user_answer', '')
            message_id = fetch_data.get('message_id', '')

            if not user_answer:
                raise ValueError("No user answer found for session")

            # Interview prompt
            interview_prompt = """
            You are an excellent interviewer with 15+ years of experience conducting professional interviews.

            Context:
            - You are conducting an HR interview
            - The candidate has just answered a question
            - You need to provide a brief summary of their answer and ask the next appropriate question

            Guidelines:
            1. Summarize the candidate's answer briefly, preserving key points
            2. Ask ONE follow-up question that flows naturally from their response
            3. Use standard HR interview questions appropriate for the conversation stage
            4. Be polite, friendly, and professional
            5. Avoid repeating questions unless seeking clarification
            6. Respond ONLY in Bahasa Indonesia

            Format your response as:
            Ringkasan: [Brief summary of candidate's answer]
            Pertanyaan: [Your next question]
            """

            # Generate question using Gemini and stream audio response
            async for chunk in self.understand_gemini_speech_elevenlabs(
                user_answer, interview_prompt, session_id, message_id
            ):
                yield chunk

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error generating questions for session {session_id}: {str(e)}")
            raise Exception(f"Question generation failed: {str(e)}")
    
  async def understand_speech_4o_mini_audio(self, user_answer: str, system_prompt: str, session_id: str, message_id: str):
    assistant_response = ''
    stream = self.openai_client.chat.completions.create(
      model="gpt-4o-mini-audio-preview",
      modalities=["text", "audio"],
      audio={
        "voice": "onyx",
        "format": "pcm16"
      },
      messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Here is the candidate answer: " + user_answer}
      ],
      stream=True
    )
    
    for chunk in stream:   
      await asyncio.sleep(0.01)

      # Check if delta exists and has audio attribute
      if not hasattr(chunk.choices[0].delta, 'audio') or chunk.choices[0].delta.audio is None:
        continue
      
      audio = chunk.choices[0].delta.audio
      # Check for transcript
      if 'transcript' in audio and audio['transcript'] is not None:
        assistant_response += audio['transcript']
        output = {
          "type": "text",
          "content": audio['transcript']
        }
        yield f"data: {json.dumps(output)} \n\n"

      # Check for audio data
      if 'data' in audio and audio['data'] is not None:
        output = {
          "type": "audio",
          "content": audio['data']
        }

        yield f"data: {json.dumps(output)} \n\n"

    self.redis_client.set("transcription:" + session_id + ":message:" + message_id + ":assistant_response", assistant_response)
    
    async def understand_gemini_speech_elevenlabs(
        self, user_answer: str, system_prompt: str, session_id: str, message_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Generate response using Gemini and convert to speech using ElevenLabs.

        Args:
            user_answer: User's transcribed answer
            system_prompt: System prompt for AI
            session_id: Session identifier
            message_id: Message identifier

        Yields:
            Server-sent events with audio data
        """
        try:
            logger.info(f"Generating response for session {session_id}")

            # Generate text response using Gemini
            response = self.gemini_client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[f"User answer: {user_answer}"],
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt
                )
            )

            if not response or not response.text:
                raise Exception("Empty response from Gemini")

            # Store assistant response
            response_key = f"transcription:{session_id}:message:{message_id}:assistant_response"
            self.redis_client.set(response_key, response.text)
            self.redis_client.expire(response_key, 86400)  # 24 hours

            logger.info(f"Generated text response, converting to speech")

            # Convert to speech using ElevenLabs
            stream = self.elevenlabs_client.text_to_speech.stream_with_timestamps(
                voice_id="v70fYBHUOrHA3AKIBjPq",
                model_id="eleven_flash_v2_5",
                text=response.text,
                language_code="id",
                output_format="pcm_24000"
            )

            # Stream audio chunks
            for chunk in stream:
                await asyncio.sleep(0.01)
                output = {
                    "type": "audio",
                    "content": chunk.audio_base_64
                }
                yield f"data: {json.dumps(output)}\n\n"

            logger.info(f"Completed audio streaming for session {session_id}")

        except Exception as e:
            logger.error(f"Error in speech generation: {str(e)}")
            # Send error message as text
            error_output = {
                "type": "error",
                "content": f"Speech generation failed: {str(e)}"
            }
            yield f"data: {json.dumps(error_output)}\n\n"
  
    async def fetch_answer(self, session_id: str) -> Dict[str, str]:
        """
        Fetch and combine user answer from all processed chunks.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary containing user answer, session ID, and message ID

        Raises:
            ValueError: If session is invalid
            Exception: If fetching fails
        """
        if not session_id:
            raise ValueError("Session ID is required")

        try:
            # Get current message ID
            identifier_current_message_id = f"session:{session_id}:current_message_id"
            message_id_bytes = self.redis_client.get(identifier_current_message_id)

            if not message_id_bytes:
                raise ValueError(f"Session {session_id} not found or expired")

            message_id = message_id_bytes.decode('utf-8')

            identifier_session = f"transcription:{session_id}:message:{message_id}:chunk"
            identifier_process_chunk = f"transcription:{session_id}:message:{message_id}:process"

            # Wait for all chunks to be processed (with timeout)
            max_wait_time = 30  # 30 seconds timeout
            wait_time = 0

            while self.redis_client.scard(identifier_process_chunk) > 0:
                if wait_time >= max_wait_time:
                    logger.warning(f"Timeout waiting for chunks to process for session {session_id}")
                    break

                logger.debug("Waiting for all chunks to be processed")
                await asyncio.sleep(0.1)
                wait_time += 0.1

            # Get all chunk numbers and sort them
            chunk_numbers = self.redis_client.smembers(identifier_session)
            if not chunk_numbers:
                logger.warning(f"No chunks found for session {session_id}")
                return {
                    'user_answer': '',
                    'session_id': session_id,
                    'message_id': message_id
                }

            # Sort chunks by number and combine transcriptions
            sorted_chunks = sorted([int(chunk.decode('utf-8')) for chunk in chunk_numbers])
            user_answer = ''

            for chunk_number in sorted_chunks:
                identifier_text_chunk = f"transcription:{session_id}:message:{message_id}:{chunk_number}:text"
                current_chunk = self.redis_client.get(identifier_text_chunk)

                if current_chunk:
                    chunk_text = current_chunk.decode('utf-8')
                    user_answer += f" {chunk_text}"
                else:
                    logger.warning(f"Missing transcription for chunk {chunk_number} in session {session_id}")

            # Clean up the combined answer
            user_answer = user_answer.strip()

            logger.info(f"Fetched answer for session {session_id}: {len(user_answer)} characters")

            return {
                'user_answer': user_answer,
                'session_id': session_id,
                'message_id': message_id
            }

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error fetching answer for session {session_id}: {str(e)}")
            raise Exception(f"Failed to fetch user answer: {str(e)}")