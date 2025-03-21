import asyncio

from google import genai
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

client = genai.Client(api_key="")
app = FastAPI()

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

async def genereateStreamContent():
  # Generate content stream
  yield f"data: Generating \n\n"

  for chunk in client.models.generate_content_stream(
    model="gemini-2.0-flash-lite",
    contents=["Explain to me about relativity theory! in details!"]
  ):
    await asyncio.sleep(0.01)
    yield f"data: {chunk.text} \n\n"

@app.post("/stream")
async def stream():
  return StreamingResponse(genereateStreamContent(), media_type="text/event-stream", headers={
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    'X-Accel-Buffering': 'no'
  })

if __name__ == "__main__":
  import uvicorn
  uvicorn.run(app, host="0.0.0.0", port="8000")
