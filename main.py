import os
from typing import Literal

from google import genai
from google.genai import types
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import redis
import uuid

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
app = FastAPI()
redis_client = redis.Redis(host="localhost", port=6379, db=0)

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

class Payload(BaseModel):
  session_id: str
  audio_data: bytes
  chunk_number: int
  stream_type: Literal["chunk", "final"]

async def asking_question(session_id: str):
  identifier_current_message_id = "session:" + session_id + ":current_message_id"
  message_id = redis_client.get(identifier_current_message_id)

  identifier_session = "transcription:" + session_id + ":message:" + message_id + ":chunk"

  identifier_process_chunk = "transcription:" + session_id + ":message:" + message_id + ":process"
  # await until all chunks are processed
  while redis_client.scard(identifier_process_chunk) > 0:
    await asyncio.sleep(0.01)

  # chunk to integer, sort, and loop through all chunks
  user_answer = ''
  for chunk_number in sorted(redis_client.smembers(identifier_session)):
    identifier_text_chunk = "transcription:" + session_id + ":message:" + message_id + ":" + chunk_number + ":text"
    user_answer += redis_client.get(identifier_text_chunk)

  identifier_user_answer = "transcription:" + session_id + ":message:" + message_id + ":user_answer"
  user_answer = redis_client.get(identifier_user_answer)

  final_prompt = """
        You are an excellent interviewer. You have wide experience on interviewing candidate for 15+ years.
        You will be provided with a list of questions to ask the candidate.
        You will be provided with candidate answers to the questions.

        What would you do?
          1. You need to summarize the candidate's last answer with preserve its key points and ask the next question.
          2. After summarize the candidate's last answer, you can ask the next question.

        Here is the list of all questions:
          1. Tell me about yourself.
          2. What are your strengths?
          3. What are your weaknesses?
          4. Why do you want this job?

        Important Rules:
          1. You need to ask the question in a polite and professional manner.
          2. You can't ask the same question again.
          3. You can't ask the question that is not in the list.
          4. You can only ask one question at a time.
          5. You only response with question to be asked and the summary of candidate answer.
          6. You will answer in Bahasa Indonesia
  """

  assistant_response = ''
  for chunk in client.models.generate_content_stream(
    model="gemini-2.0-flash-lite",
    config= genai.types.GenerateContentConfig(
      system_instruction=final_prompt
    ),
    contents=["Here is the candidate answer: " + user_answer]
  ):
    await asyncio.sleep(0.01)
    assistant_response += chunk.text
    yield f"data: {chunk.text} \n\n"

  redis_client.set("transcription:" + session_id + ":message:" + message_id + ":assistant_response", assistant_response)

async def transcribe(audio_data: bytes, session_id: str, chunk_number: int):
  identifier_process_chunk = "transcription:" + session_id + ":message:" + message_id + ":process"
  redis_client.sadd(identifier_process_chunk, str(chunk_number))

  identifier_current_message_id = "session:" + session_id + ":current_message_id"
  message_id = redis_client.get(identifier_current_message_id)

  identifier_session = "transcription:" + session_id + ":message:" + message_id + ":chunk"
  redis_client.sadd(identifier_session, str(chunk_number))

  audio_part = genai.types.Content(
    types.Part.from_bytes(
      data=audio_data,
      mime_type="audio/wav"
    )
  )

  response =  client.models.generate_content(
    model="gemini-2.0-flash-lite",
    contents=[
      "Transcribe the following audio data: ",
      audio_part
    ]
  )

  identifier_current_message_id = "session:" + session_id + ":current_message_id"
  message_id = redis_client.get(identifier_current_message_id)

  identifier_text_chunk = "transcription:" + session_id + ":message:" + message_id + str(chunk_number) + ":text"
  redis_client.set(identifier_text_chunk, response.text)
  redis_client.srem(identifier_process_chunk, str(chunk_number))

@app.post("/stream")
# receive payload with session_id and audio_data
async def stream(payload: Payload):
  if payload.stream_type == "chunk":
    await transcribe(payload.audio_data, payload.session_id, payload.chunk_number)
  else:
    await transcribe(payload.audio_data, payload.session_id, payload.chunk_number)
    return StreamingResponse(asking_question(payload.session_id), media_type="text/event-stream", headers={
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      'X-Accel-Buffering': 'no'
    })

@app.post("/start-session")
async def start_session():
  # Start a new session
  session_id = str(uuid.uuid4())
  message_id = str(uuid.uuid4())
  redis_client.sadd("session:" + session_id, message_id)
  redis_client.set("session:" + session_id + ":current_message_id", message_id)
  return {"session_id": session_id}

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port="8000")
