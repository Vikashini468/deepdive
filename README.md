# AI Technical Interviewer

A Flask-based web application that conducts AI-powered technical interviews with voice interaction and real-time evaluation.

## Features

- **User Authentication**: Register/Login system
- **Resume Upload**: PDF resume parsing and analysis
- **Voice Interaction**: Speech-to-text using Whisper for all responses
- **AI Evaluation**: Uses Ollama (Llama3) for:
  - Introduction evaluation against resume
  - Technical question generation (2 easy, 2 medium, 1 hard)
  - Answer evaluation with scoring (0-10 points each)
- **Real-time Chat**: Interactive interview interface
- **Dashboard**: Performance analytics with strengths/weaknesses

## Prerequisites

1. **Ollama**: Install and run Ollama with Llama3 model
   ```bash
   # Install Ollama from https://ollama.ai
   ollama pull llama3
   ollama serve
   ```

2. **Python 3.8+**: Required for the application

## Installation

1. Clone/download the project
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Open browser to `http://localhost:5000`

## Usage

1. **Register** a new account or **Login**
2. **Upload Resume** (PDF) and select your technical field
3. **Start Interview**:
   - First question: "Tell me about yourself" (voice response)
   - AI evaluates against your resume
   - 5 technical questions follow (voice responses)
   - Each question worth 10 points (50 total)
4. **View Results** on dashboard with detailed analytics

## Technical Stack

- **Backend**: Flask, SQLite
- **AI**: Ollama (Llama3), Whisper
- **Frontend**: Bootstrap, JavaScript
- **Audio**: Web Audio API, MediaRecorder

## File Structure

```
├── app.py              # Main Flask application
├── requirements.txt    # Dependencies
├── templates/          # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── upload_resume.html
│   ├── chat.html
│   └── dashboard.html
└── uploads/           # Temporary file storage
```

## Configuration

- Ollama URL: `http://localhost:11434/api/generate`
- Model: `llama3`
- Timeout: 60 seconds
- Whisper Model: `base`

## Notes

- Ensure microphone permissions are granted
- Ollama must be running before starting interviews
- PDF resumes only supported for upload
- Voice responses required for all questions