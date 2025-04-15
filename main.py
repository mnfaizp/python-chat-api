import os

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import redis
import uuid

from google import genai
from openai import OpenAI
from elevenlabs import ElevenLabs
load_dotenv()

from services.transcribe import Transcribe
from services.question_generation import QuestionGeneration

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
eleven_labs_client = ElevenLabs(api_key=os.getenv("ELEVEN_LABS_API_KEY"))

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
  audio_data: str
  chunk_number: int
  stream_type: str
  

@app.post("/stream")
# receive payload with session_id and audio_data
async def stream(payload: Payload):
  if payload.stream_type == "chunk":
    transribe = Transcribe(redis_client, openai_client, client, eleven_labs_client)
    await transribe.process_chunk(payload.audio_data, payload.session_id, payload.chunk_number)
  else:
    generate_question = QuestionGeneration(redis_client, openai_client, client, eleven_labs_client)
    return StreamingResponse(generate_question.generate(payload.session_id), media_type="text/event-stream", headers={
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
