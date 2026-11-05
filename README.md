# Quiz Agent

A study buddy agent that quizzes you on a topic, grades your answers and adapts.
It is built with the same stack and architecture as Open Deep Research (LangGraph, LangChain, uv), at a size that is cheap to run.

## Setup (once)

1. Install Python 3.11.9 from python.org (signed, so Windows Smart App Control allows it).
2. Create the environment and install dependencies:

```powershell
uv venv --python "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" --clear
uv sync --extra dev
```

3. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `LANGSMITH_API_KEY`.

## Run (every new terminal)

```powershell
cd "C:\Users\Administrator\Desktop\personal projects\quiz_agent"
uv run langgraph dev
```

Studio opens in the browser (API at http://127.0.0.1:2024). Stop the server with Ctrl+C.
No activation is needed: `uv run` uses `.venv` automatically.

If port 2024 is already in use, an old server is still running:

```powershell
netstat -ano | findstr :2024
Stop-Process -Id <PID>
```
