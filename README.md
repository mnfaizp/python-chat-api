# Python Chat API

A FastAPI-based AI-powered interview system with audio transcription and question generation capabilities.

## Features

- **Audio Transcription**: Real-time audio chunk processing using Gemini AI
- **Question Generation**: AI-powered interview question generation based on user responses
- **Session Management**: Redis-based session handling with automatic expiration
- **Multi-language Support**: Supports Bahasa Indonesia and English
- **Audio Streaming**: Real-time audio response generation using ElevenLabs
- **Health Monitoring**: Built-in health check endpoints

## Tech Stack

- **Backend**: FastAPI, Python 3.12+
- **AI Services**: OpenAI GPT, Google Gemini, ElevenLabs
- **Database**: Redis for session management, PostgreSQL (optional)
- **Audio Processing**: PyDub for audio processing
- **Deployment**: Docker, Docker Compose

## Quick Start

### Prerequisites

- Python 3.12+
- Redis server
- Docker (optional)
- API keys for: OpenAI, Google Gemini, ElevenLabs

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd python-chat-api
   ```

2. **Set up environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and configuration
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start Redis** (if not using Docker)
   ```bash
   redis-server
   ```

5. **Run the application**
   ```bash
   python main.py
   ```

### Using Docker

1. **Create secrets directory**
   ```bash
   mkdir secrets
   echo "your-gemini-key" > secrets/gemini_api_key.txt
   echo "your-openai-key" > secrets/openai_api_key.txt
   echo "your-elevenlabs-key" > secrets/elevenlabs_api_key.txt
   echo "your-postgres-password" > secrets/postgress_password.txt
   ```

2. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

## API Endpoints

### Core Endpoints

- `POST /start-session` - Create a new session
- `POST /stream` - Process audio chunks or generate questions
- `GET /health` - Health check

### API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Configuration

### Environment Variables

See `.env.example` for all available configuration options.

### Key Settings

- `GEMINI_API_KEY`: Required for transcription and question generation
- `OPENAI_API_KEY`: Required for AI processing
- `ELEVEN_LABS_API_KEY`: Required for audio generation
- `REDIS_HOST`: Redis server host (default: localhost)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Usage Examples

### Start a Session

```bash
curl -X POST "http://localhost:8000/start-session"
```

### Process Audio Chunk

```bash
curl -X POST "http://localhost:8000/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "audio_data": "base64-encoded-audio",
    "chunk_number": 1,
    "stream_type": "chunk"
  }'
```

### Generate Questions

```bash
curl -X POST "http://localhost:8000/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "audio_data": "",
    "chunk_number": 0,
    "stream_type": "question"
  }'
```

## Development

### Project Structure

```
python-chat-api/
├── config/                 # Configuration management
│   ├── settings.py         # Application settings
│   └── logging_config.py   # Logging configuration
├── services/               # Business logic services
│   ├── transcribe.py       # Audio transcription
│   └── question_generation.py  # Question generation
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Docker configuration
├── compose.yml            # Docker Compose setup
└── README.md              # This file
```

### Code Quality

The codebase follows Python best practices:
- Type hints throughout
- Comprehensive error handling
- Structured logging
- Input validation with Pydantic
- Dependency injection
- Proper async/await usage

### Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest
```

## Deployment

### Production Considerations

1. **Security**
   - Change default secret keys
   - Configure proper CORS origins
   - Use environment-specific configurations
   - Enable HTTPS

2. **Monitoring**
   - Set up proper logging
   - Monitor Redis and database connections
   - Track API response times
   - Monitor AI service usage

3. **Scaling**
   - Use Redis cluster for high availability
   - Consider load balancing for multiple instances
   - Monitor memory usage for audio processing

### Docker Production

```bash
# Build production image
docker build -t python-chat-api:latest .

# Run with production settings
docker run -d \
  --name chat-api \
  -p 8000:8000 \
  -e DEBUG=false \
  -e LOG_LEVEL=INFO \
  python-chat-api:latest
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed**
   - Check Redis server is running
   - Verify REDIS_HOST and REDIS_PORT settings

2. **AI Service Errors**
   - Verify API keys are correct
   - Check API quotas and limits
   - Monitor service status

3. **Audio Processing Issues**
   - Ensure audio data is properly base64 encoded
   - Check audio format compatibility
   - Verify chunk size limits

### Logs

Check application logs for detailed error information:
```bash
# Docker logs
docker logs python-chat-api

# Local development
tail -f app.log
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license information here]