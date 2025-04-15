import asyncio
import json
import google.genai.types as types

class QuestionGeneration:
  def __init__(self, redis_client, openai_client, gemini_client, elevenlabs_client):
    self.redis_client = redis_client
    self.openai_client = openai_client
    self.gemini_client = gemini_client
    self.elevenlabs_client = elevenlabs_client
    
  async def generate(self, session_id: str):
    fetch_date = await self.fetch_answer(session_id)
    user_answer = fetch_date['user_answer']
    message_id = fetch_date['message_id']
    
    final_prompt = """
        You are an excellent interviewer. You have wide experience on interviewing candidate for 15+ years.
        You will be provided with a list of questions to ask the candidate.
        You will be provided with candidate answers to the questions.

        First candidate answer is answering the question "Tell me about yourself".

        You need to ask 5 questions to the candidate using standard interview questions in HR Interview Steps.

        What would you do?
          1. You need to summarize the candidate's last answer with preserve its key points and ask the next question.
          2. After summarize the candidate's last answer, you can ask the next question.  

        Important Rules:
          1. You need to ask the question in a polite, friendly, and professional manner.
          2. You can't ask the same question again but can ask elaboration if interviewee didn't explain their answer well.
          3. You can only ask one question at a time.
          4. You only response with question to be asked and the summary of candidate answer.
          5. You will answer only in Bahasa Indonesia
    """
    
    await self.understand_gemini_speech_elevenlabs(user_answer, final_prompt, session_id, message_id)
    
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
    
  async def understand_gemini_speech_elevenlabs(self, user_answer: str, system_prompt: str, session_id: str, message_id: str):
    response = self.client.models.generate_content(
      model="gemini-2.0-flash",
      contents=[
        user_answer
      ],
      config=types.GenerateContentConfig(
        system_instruction=system_prompt
      )
    )

    self.redis_client.set("transcription:" + session_id + ":message:" + message_id + ":assistant_response", response.text)

    stream = self.eleven_labs_client.text_to_speech.stream_with_timestamps(
      voice_id="v70fYBHUOrHA3AKIBjPq",
      model_id="eleven_flash_v2_5",
      text=response.text,
      language_code="id",
      output_format="pcm_24000"
    )

    for chunk in stream:
      await asyncio.sleep(0.01)
      output = {
        "type": "audio",
        "content": chunk.audio_base_64
      }
      yield f"data: {json.dumps(output)} \n\n"
  
  async def fetch_answer(self, session_id: str):
    identifier_current_message_id = "session:" + session_id + ":current_message_id"
    message_id = self.redis_client.get(identifier_current_message_id).decode('utf-8')

    identifier_session = "transcription:" + session_id + ":message:" + message_id + ":chunk"

    identifier_process_chunk = "transcription:" + session_id + ":message:" + message_id + ":process"
    # block until all chunks are processed
    while self.redis_client.scard(identifier_process_chunk) > 0:
      print("waiting for all chunks to be processed")
      await asyncio.sleep(0.1)

    # chunk to integer, sort, and loop through all chunks
    user_answer = ''
    for chunk_number in sorted(self.redis_client.smembers(identifier_session)):
      identifier_text_chunk = "transcription:" + session_id + ":message:" + message_id + ":" + chunk_number.decode('utf-8') + ":text"
      current_chunk = self.redis_client.get(identifier_text_chunk)
      if current_chunk:
        user_answer += current_chunk.decode('utf-8')
    
    return {
      user_answer: user_answer,
      session_id: session_id,
      message_id: message_id
    }