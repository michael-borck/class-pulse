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

**Login with default admin credentials:**
- Username: `admin`
- Password: `admin123`

**Access the application at:** `http://localhost:5002`

## 3. Configure AI Settings

1. **Navigate to AI Settings:**
   - Click "AI Settings" in the top navigation menu
   - Or go directly to: `http://localhost:5002/settings/ai`

2. **Configure Ollama (Recommended for local testing):**
   - Keep "Enable AI Question Generation" checked
   - Set "Preferred Provider" to "Ollama (Local) - Try first"
   - Ollama URL: `http://localhost:11434` (default)
   - Ollama Model: `llama3.2` (or any model you have installed)

3. **Optional - Configure Cloud API:**
   - Set API URL (e.g., `https://api.openai.com/v1`)
   - Add your API key
   - Set model name (e.g., `gpt-3.5-turbo`)

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

### Option A: Test from AI Settings Page
1. Go to AI Settings page
2. Scroll down to "Test AI Generation" section
3. Enter a test prompt like:
   - `"multiple choice question about hard disk sector size"`
   - `"rating question about user satisfaction"`
   - `"word cloud about favorite programming languages"`
4. Click "Test Generation"
5. Review the generated question structure

### Option B: Test in Question Creation Flow
1. Create a new session:
   - Dashboard → "Create New Session"
   - Enter session name → Create
2. Add a question:
   - Click "New Multiple Choice" (or any type)
   - You'll see the purple "✨ Generate with AI" section
3. Enter a description:
   - `"Create a question about database normalization"`
   - `"Make a multiple choice about Python data types"`
4. Click "Generate Question"
5. The form will auto-populate with AI-generated content
6. Edit if needed and save

## 6. Test Different Scenarios

**Test Type Detection:**
- Enter `"word cloud about emotions"` on a multiple choice page
- Should redirect to word cloud creation page

**Test Error Handling:**
- Disable Ollama server and test fallback behavior
- Enter invalid prompts and see error messages

**Test Cloud Fallback:**
- Set preference to "Cloud API" without valid API key
- Should fallback to Ollama

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
- Verify AI is enabled in settings
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

3. **Provider Fallback:**
   - Configure both Cloud and Ollama to test automatic fallback
   - Disable one provider to see seamless switching

4. **Security Features:**
   - API keys are encrypted in the database
   - Check the settings page to see masked API key display

The system is designed to be robust, so even if AI generation fails, you can always create questions manually using the traditional form fields.