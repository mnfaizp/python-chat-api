import os

from google import genai
from google.genai import types
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import asyncio
import redis
import uuid
import json

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

async def asking_question(session_id: str):
  identifier_current_message_id = "session:" + session_id + ":current_message_id"
  message_id = redis_client.get(identifier_current_message_id).decode('utf-8')

  identifier_session = "transcription:" + session_id + ":message:" + message_id + ":chunk"

  identifier_process_chunk = "transcription:" + session_id + ":message:" + message_id + ":process"
  # block until all chunks are processed
  while redis_client.scard(identifier_process_chunk) > 0:
    print("waiting for all chunks to be processed")
    await asyncio.sleep(0.1)

  # chunk to integer, sort, and loop through all chunks
  user_answer = ''
  for chunk_number in sorted(redis_client.smembers(identifier_session)):
    identifier_text_chunk = "transcription:" + session_id + ":message:" + message_id + ":" + chunk_number.decode('utf-8') + ":text"
    current_chunk = redis_client.get(identifier_text_chunk)
    if current_chunk:
      user_answer += current_chunk.decode('utf-8')

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
  stream = openai_client.chat.completions.create(
    model="gpt-4o-mini-audio-preview",
    modalities=["text", "audio"],
    audio={
      "voice": "alloy",
      "format": "pcm16"
    },
    messages=[
      {"role": "system", "content": final_prompt},
      {"role": "user", "content": "Here is the candidate answer: " + user_answer}
    ],
    stream=True
  )
  
  for chunk in stream:   
    await asyncio.sleep(0.05)

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

  redis_client.set("transcription:" + session_id + ":message:" + message_id + ":assistant_response", assistant_response)

async def transcribe(audio_data: str, session_id: str, chunk_number: int):
  identifier_current_message_id = "session:" + session_id + ":current_message_id"
  message_id = redis_client.get(identifier_current_message_id).decode('utf-8')

  identifier_process_chunk = "transcription:" + session_id + ":message:" + message_id + ":process"
  redis_client.sadd(identifier_process_chunk, str(chunk_number))

  identifier_session = "transcription:" + session_id + ":message:" + message_id + ":chunk"
  redis_client.sadd(identifier_session, str(chunk_number))

  audio_part = types.Part.from_bytes(
    data=audio_data,
    mime_type="audio/wav"
  )

  response =  client.models.generate_content(
    model="gemini-2.0-flash-lite",
    contents=[
      "Transcribe the following audio data, The Speaker will use Bahasa Indonesia or English, so you need to transcribe it in Bahasa Indonesia or English: ",
      audio_part
    ]
  )

  identifier_current_message_id = "session:" + session_id + ":current_message_id"
  message_id = redis_client.get(identifier_current_message_id).decode('utf-8')

  identifier_text_chunk = "transcription:" + session_id + ":message:" + message_id + ":" + str(chunk_number) + ":text"
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
