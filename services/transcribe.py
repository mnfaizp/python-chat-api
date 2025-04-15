import google.genai.types as types


class Transcribe:
  def __init__(self, redis_client, openai_client, gemini_client, elevenlabs_client):
    self.redis_client = redis_client
    self.openai_client = openai_client
    self.gemini_client = gemini_client
    self.redis_client = redis_client
    self.elevenlabs_client = elevenlabs_client
  
  async def process_chunk(self, audio_data: str, session_id: str, chunk_number: int):
    identifier_current_message_id = "session:" + session_id + ":current_message_id"
    message_id = self.redis_client.get(identifier_current_message_id).decode('utf-8')

    identifier_process_chunk = "transcription:" + session_id + ":message:" + message_id + ":process"
    self.redis_client.sadd(identifier_process_chunk, str(chunk_number))

    identifier_session = "transcription:" + session_id + ":message:" + message_id + ":chunk"
    self.redis_client.sadd(identifier_session, str(chunk_number))

    audio_part = types.Part.from_bytes(
      data=audio_data,
      mime_type="audio/wav"
    )

    response =  self.gemini_client.models.generate_content(
      model="gemini-2.0-flash-lite",
      contents=[
        "Transcribe the following audio data, The Speaker will use Bahasa Indonesia or English, so you need to transcribe it in Bahasa Indonesia or English: ",
        audio_part
      ]
    )

    identifier_current_message_id = "session:" + session_id + ":current_message_id"
    message_id = self.redis_client.get(identifier_current_message_id).decode('utf-8')

    identifier_text_chunk = "transcription:" + session_id + ":message:" + message_id + ":" + str(chunk_number) + ":text"
    self.redis_client.set(identifier_text_chunk, response.text)
    self.redis_client.srem(identifier_process_chunk, str(chunk_number))
    
    