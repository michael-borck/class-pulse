# ClassPulse AI Question Generation Demo Guide

This guide explains how to test the AI-powered question generation feature locally.

## 1. Start the Application

```bash
# Navigate to the project directory
cd /home/michael/projects/class-pulse

# Activate the virtual environment
source venv/bin/activate

# Start the application
python app.py
```

The application will start on `http://localhost:5002`

## 2. Initial Setup

**Register the first account — it becomes the admin automatically** (there is no
default admin account), then log in with the credentials you chose.

**Access the application at:** `http://localhost:5002`

## 3. Configure the AI Provider (global, in `.env`)

AI question generation uses a single provider configured for the whole
deployment in `.env` (copy `.env.example` to `.env`). Two adapter families are
supported:

- **`openai`** — any OpenAI-compatible `/chat/completions` endpoint: OpenAI,
  Groq, Together, OpenRouter, and **Ollama's `/v1`** (leave `AI_API_KEY` blank
  for a local/keyless Ollama).
- **`anthropic`** — the native Anthropic `/messages` endpoint
  (`api.anthropic.com`).

`AI_BASE_URL` is the `/v1` root for both. Examples:

```bash
# Ollama (local, no key)
AI_PROVIDER=openai
AI_BASE_URL=http://localhost:11434/v1
AI_MODEL=llama3.2
AI_API_KEY=

# OpenAI
AI_PROVIDER=openai
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini
AI_API_KEY=sk-...

# Anthropic (Claude)
AI_PROVIDER=anthropic
AI_BASE_URL=https://api.anthropic.com/v1
AI_MODEL=claude-3-5-haiku-latest
AI_API_KEY=sk-ant-...
```

Leave `AI_PROVIDER` blank to disable AI generation. Restart the app after
editing `.env`.

## 4. Install and Setup Ollama (for local testing)

If you don't have Ollama installed:

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model (this might take a few minutes)
ollama pull llama3.2

# Start Ollama server (if not already running)
ollama serve
```

## 5. Test AI Generation

Generate a question from the creation flow:

1. Create a new session: Dashboard → "Create New Session" → name it → Create.
2. Add a question: click "New Multiple Choice" (or any type). You'll see the
   purple "✨ Generate with AI" section (shown only when a provider is
   configured).
3. Enter a description, e.g.:
   - `"multiple choice question about hard disk sector size"`
   - `"rating question about user satisfaction"`
   - `"word cloud about favorite programming languages"`
4. Click "Generate Question" — the form auto-populates with AI content.
5. Edit if needed and save.

## 6. Test Different Scenarios

**Test Type Detection:**
- Enter `"word cloud about emotions"` on a multiple choice page
- Should redirect to word cloud creation page

**Test Error Handling:**
- Stop the provider (e.g. quit Ollama, or point `AI_BASE_URL` at an invalid
  host) and confirm you get a clear error message
- Enter invalid prompts and see error messages

## 7. Verify Database Integration

Check that generated questions work normally:
1. Create questions using AI generation
2. Activate the session
3. Test audience participation at: `http://localhost:5002/join`
4. Enter the session code and answer questions
5. View real-time results

## 8. Troubleshooting

**If Ollama fails:**
- Check if Ollama is running: `curl http://localhost:11434/api/tags`
- Verify model is installed: `ollama list`
- Check Ollama logs for errors

**If AI generation fails:**
- Check browser console for JavaScript errors
- Verify AI_PROVIDER/AI_BASE_URL/AI_MODEL are set in `.env` (and the app restarted)
- Check Flask console for Python errors

**Common test prompts that work well:**
- `"multiple choice question about HTTP status codes"`
- `"rating scale for customer service quality"`
- `"word cloud about machine learning concepts"`
- `"quiz question about database indexes"`

## Features to Explore

1. **Natural Language Understanding:**
   - The AI detects question types from natural descriptions
   - Try various phrasings to see how it interprets your intent

2. **Smart Redirects:**
   - If you request a different question type than the current page, it automatically redirects
   - Preserves your generated content during the redirect

3. **Provider variety:**
   - Any OpenAI-compatible endpoint works (OpenAI, Ollama `/v1`, Groq,
     OpenRouter); Anthropic uses its native `/messages` API.
   - Ollama works keyless locally; a remote Ollama just needs `AI_API_KEY` set.

4. **Secret handling:**
   - The provider key lives in `.env` (plaintext, gitignored, mode 0600) — it is
     never stored in the database.

The system is designed to be robust, so even if AI generation fails, you can always create questions manually using the traditional form fields.