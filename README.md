# Quiz Agent

An AI study buddy that quizzes you on any topic, grades your answers, and remembers what you need to practise, built step by step with **LangGraph** and **LangChain**.

This repository is a **starter project for developers who are new to LangGraph and LangChain**. It is small enough to read in an afternoon and cheap to run (it uses Claude Haiku), but it is built the way real agents are built: a typed state graph, tools, structured output, short- and long-term memory, configuration, tests that need no API key, and a separate frontend that talks to the agent through an API.

It is also a **first use case for the LangSmith platform**: every run is traced, so you can see exactly what each node and model call did, and the grader is a natural target for your first evaluation experiment.

> **Project status:** this is a learning project that runs locally. Production hardening (authentication, rate limits, a production database) and deployment are planned for later; see the [roadmap](#roadmap).

---

## Table of contents

- [What it does](#what-it-does)
- [What you will learn](#what-you-will-learn)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Tracing and evaluation with LangSmith](#tracing-and-evaluation-with-langsmith)
- [Tests and linting](#tests-and-linting)
- [Costs and safety](#costs-and-safety)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Ideas to extend it](#ideas-to-extend-it)
- [License](#license)

---

## What it does

- **Quizzes you on any topic**, one question at a time, at the difficulty you choose (easy, medium or hard).
- **Quizzes you on your own notes**: drop `.md` or `.txt` files in `notes/` and the agent reads them with tools.
- **Grades every answer as structured data** (correct or not, topic, feedback) and keeps a score for the quiz.
- **Remembers you across quizzes**: it tracks your results per topic and suggests your weakest topics next time.
- **Comes with a web UI** (Streamlit) with a scoreboard, topic buttons, grade badges and per-topic progress, plus LangGraph Studio for debugging.

---

## What you will learn

Each bullet points to the file where the concept lives, so you can read the code right after.

### LangGraph fundamentals
- **State**: a typed dict shared by all nodes. `QuizState` extends `MessagesState`, so the conversation is a `messages` list ([state.py](src/quiz_agent/state.py)).
- **Nodes return partial updates**: a node only returns the keys it changes ([agent.py](src/quiz_agent/agent.py)).
- **Reducers**: `messages` uses a reducer that *appends* new messages; other keys like `answered` are simply overwritten.
- **Building and compiling a graph**: `StateGraph(...)`, `add_node`, `add_edge(START, ...)`, then `.compile()`.
- **Dynamic routing with `Command`**: a node can update the state *and* choose the next node at runtime with `Command(goto=..., update=...)`. The `Command[Literal[...]]` return type tells LangGraph the possible destinations.
- **The ReAct loop**: model, then tools, then model again, until the model answers without calling a tool. A limit (`max_react_tool_calls`) stops endless loops.

### LangChain models and tools
- **Provider-agnostic models**: `init_chat_model(configurable_fields=...)` creates one model object whose model name and settings are chosen per call.
- **Tools from plain Python functions**: `@tool` turns a function's name, docstring and type hints into a schema the model reads. The docstring *is* the model's instruction manual ([utils.py](src/quiz_agent/utils.py)).
- **`bind_tools`, `tool_calls` and `ToolMessage`**: the model only *requests* a tool call, your code runs it, and the result goes back linked by `tool_call_id`.
- **Content blocks**: model replies can contain text, thinking and tool-use blocks. `message.text` extracts just the text.

### Structured output
- **Getting typed objects instead of text**: `with_structured_output(Grade)` returns a Pydantic object your code can use (`grade.is_correct`), not a sentence to parse.
- **Retries**: `.with_retry(stop_after_attempt=...)` makes LLM calls robust to occasional failures.
- **One owner per responsibility**: the `grade_answer` node grades and the `quiz_master` node talks. When two LLM components can do the same job, they end up disagreeing.

### Memory
- **Working memory**: the state while a run is executing, passed from node to node.
- **Short-term memory (checkpointer)**: the state saved per `thread_id` after each run and reloaded on the next message. That is why the agent remembers the conversation.
- **Long-term memory (Store)**: facts saved per user across all threads, in a namespace like `(user_id, "quiz_results")` ([utils.py](src/quiz_agent/utils.py)).
- **The model itself remembers nothing**: the full conversation is sent on every call.

### Configuration
- **One Pydantic `Configuration` class** for all settings, with defaults, readable from environment variables or per run ([configuration.py](src/quiz_agent/configuration.py)).
- **UI metadata**: LangGraph Studio turns each field into a control (dropdown, slider, text field).
- **Validate input at the boundary**: a validator turns a blank `user_id` from the UI into the default user.

### Prompting for agents
- **Structured system prompts** with tagged sections (`<Task>`, `<Instructions>`, `<Tools>`) ([prompts.py](src/quiz_agent/prompts.py)).
- **Keep the conversation append-only**: Claude's thinking blocks are tied to the exact conversation that produced them, so settings that shape the system prompt (difficulty, learner history) are locked in state on the first turn of each thread.

### Serving, API and frontend
- **`langgraph.json` plus `langgraph dev`** serve the graph as an HTTP API and open LangGraph Studio.
- **A frontend is just an API client**: the Streamlit app uses `langgraph_sdk` to create threads, stream runs and read state and memory ([frontend/app.py](frontend/app.py)). It never calls the model or holds API keys.
- **Streaming with metadata**: tokens arrive tagged with the node that produced them, so the UI shows only the quiz master's words.

### Observability and evaluation with LangSmith
- **Tracing with zero code**: three environment variables turn on tracing for every run.
- **Reading a trace**: each run is a tree of nodes, model calls and tool calls, with inputs, outputs, tokens, latency and cost.
- **Debugging with traces**: when the agent misbehaves, the trace shows which component made the wrong decision (for example, the grader marking a real answer as "not an answer").
- **Datasets and experiments**: save example inputs with reference outputs, run the agent on them, and compare runs side by side.
- **LLM-as-a-judge evaluators**: let a model score each output (for example, "is this grade correct?") and track the score across prompt or model changes.

### Testing and code quality
- **Tests without API calls**: a fake chat model returns scripted replies, so the tests are fast, free and deterministic ([tests/conftest.py](tests/conftest.py)).
- **Testing memory**: `InMemorySaver` and `InMemoryStore` give each test a clean checkpointer and store.
- **Linting** with Ruff (style, imports, docstrings, no stray `print`).

### Security basics for agents
- **Tool arguments come from the model, so treat them as untrusted**: `load_notes` resolves the path and refuses anything outside `notes/`, which blocks path traversal like `../.env`.
- **Return errors as strings** from tools, so the model can read them and correct itself instead of crashing the run.
- **Secrets stay in `.env`**, which is gitignored. Only `.env.example` (without values) is committed.
- **Memory is namespaced per user**, so one user never reads another user's results.

---

## How it works

### Architecture

```
┌───────────────────┐   HTTP API    ┌─────────────────────────────────┐        ┌──────────────┐
│ Streamlit UI      │ ────────────▶ │ LangGraph server (langgraph dev)│ ─────▶ │ Claude Haiku │
│ or LangGraph      │ ◀──────────── │  • quiz graph                   │ ◀───── │ (Anthropic)  │
│ Studio            │  streaming    │  • checkpointer (threads)       │        └──────────────┘
└───────────────────┘               │  • store (long-term memory)     │
                                    └─────────────────────────────────┘
```

### The graph

```
START ──▶ grade_answer ──▶ quiz_master ──▶ END
                               │   ▲
                   tool calls  ▼   │  tool results
                         quiz_master_tools
```

| Node | Job |
|---|---|
| `grade_answer` | If you just answered a question, grade it with structured output, update the score, save the result to long-term memory, and add a `<grade>` message for the quiz master. On the first turn, or when your message is not an answer, it does nothing. |
| `quiz_master` | Talks to you: picks up the grade, explains, and asks the next question. It can call tools to read your notes. |
| `quiz_master_tools` | Runs the tools the quiz master asked for (`list_notes`, `load_notes`) and sends the results back. |

### One turn, step by step

1. You send a message. The server loads the thread's saved state (the checkpointer) and appends your message.
2. `grade_answer` finds the last question, asks Claude for a `Grade` object, updates `answered` and `correct`, and saves the topic result to the Store under your user id.
3. `quiz_master` builds the system prompt (difficulty and learner history, locked for the thread) and calls Claude with the whole conversation.
4. If Claude requests a tool, `quiz_master_tools` runs it and the loop goes back to `quiz_master`.
5. The final reply streams back to the UI, and the state is saved again for the next turn.

---

## Project structure

```
quiz_agent/
├── src/quiz_agent/
│   ├── agent.py          # the graph: nodes, routing, compile
│   ├── state.py          # QuizState and the Grade schema
│   ├── configuration.py  # all settings (Pydantic), with Studio UI metadata
│   ├── prompts.py        # system prompt, grading prompt, grade message template
│   └── utils.py          # notes tools, tool helpers, memory helpers
├── frontend/
│   └── app.py            # Streamlit UI that talks to the LangGraph API
├── tests/                # pytest suite with a fake chat model (no API calls)
├── notes/                # your study notes (.md / .txt) for the notes tools
├── .streamlit/config.toml  # UI theme
├── langgraph.json        # tells `langgraph dev` where the graph is
├── pyproject.toml        # dependencies and tool settings
└── .env.example          # template for your API keys
```

---

## Getting started

### Prerequisites

- **Python 3.11 or 3.12**
- **[uv](https://docs.astral.sh/uv/)**, a fast Python package and project manager
- An **Anthropic API key** ([console.anthropic.com](https://console.anthropic.com))
- Optional: a **LangSmith API key** for tracing ([smith.langchain.com](https://smith.langchain.com), the free tier is enough)

### 1. Install

```bash
git clone https://github.com/houssem71/quiz_agent.git
cd quiz_agent
uv sync --extra dev --extra ui
```

`uv sync` creates a `.venv` and installs the exact versions from `uv.lock`. The `dev` extra adds the LangGraph CLI, pytest and Ruff; the `ui` extra adds Streamlit.

### 2. Add your keys

Copy the template and fill in your keys in `.env` (never in `.env.example`):

```bash
cp .env.example .env          # Windows PowerShell: Copy-Item .env.example .env
```

### 3. Start the agent server

```bash
uv run langgraph dev
```

This serves the API at `http://127.0.0.1:2024` and opens **LangGraph Studio** in your browser, where you can chat with the graph, watch each node run, and change the configuration.

### 4. Start the web UI

In a second terminal, with the server still running:

```bash
uv run streamlit run frontend/app.py
```

Open `http://localhost:8501`, pick a topic and start answering.

---

## Configuration

All settings live in [configuration.py](src/quiz_agent/configuration.py). You can change them in LangGraph Studio, pass them per run (`config={"configurable": {...}}`), or set an environment variable with the uppercase name (for example `DIFFICULTY=hard`). Environment variables take priority.

| Setting | Default | What it does |
|---|---|---|
| `difficulty` | `medium` | Question difficulty: `easy`, `medium` or `hard`. Fixed for the whole quiz (thread). |
| `user_id` | `default_user` | Whose long-term memory to read and update. |
| `max_react_tool_calls` | `3` | Maximum tool-calling rounds before the quiz master must answer. |
| `max_structured_output_retries` | `3` | Attempts for the structured grading call. |
| `quiz_model` | `anthropic:claude-haiku-5-5` | Model in `provider:model` format. |
| `quiz_model_max_tokens` | `512` | Maximum output tokens per model reply. |

---

## Tracing and evaluation with LangSmith

[LangSmith](https://smith.langchain.com) is LangChain's platform for observing and evaluating LLM applications. This project is a simple first use case for it.

### Tracing

1. Create a free account and an API key.
2. In your `.env`, set:
   ```
   LANGSMITH_API_KEY=<your key>
   LANGSMITH_PROJECT=quiz-agent
   LANGSMITH_TRACING=true
   ```
3. Restart `langgraph dev` and chat with the agent.
4. Open the **quiz-agent** project in LangSmith (it is created automatically on the first trace).

Each message you send becomes one trace. Open one and you will see:
- `grade_answer` with the structured `Grade` the model returned
- `quiz_master` with the exact system prompt and messages sent to Claude
- `quiz_master_tools` with the tool arguments and results
- tokens, latency and cost for every model call

### Evaluation

The grader is a good first thing to evaluate, because its output is a clear right-or-wrong decision.

1. **Build a dataset**: from a few traces, use *Add to dataset* to save the input (question and answer) with the expected output (correct or not).
2. **Add an evaluator**: create an LLM-as-a-judge evaluator, for example "Is the grade correct given the reference?". Give the judge model enough max tokens (around 1024) so it can return valid feedback.
3. **Run an experiment** on the dataset and read the scores.
4. **Iterate**: change a prompt in [prompts.py](src/quiz_agent/prompts.py), run the experiment again, and compare the two experiments side by side.

> Evaluators that run in the LangSmith UI call a model on LangSmith's side, so they need a model provider key saved as a workspace secret in LangSmith, with a name that exactly matches the one the evaluator uses (for example `ANTHROPIC_API_KEY`).

---

## Tests and linting

The tests replace Claude with a fake model, so they make **no API calls and cost nothing**.

```bash
uv run pytest -v
uv run ruff check
```

| Command | What it does |
|---|---|
| `uv run pytest` | Run all tests in `tests/` |
| `uv run pytest -v` | List each test with PASSED or FAILED |
| `uv run ruff check` | Lint: bugs, import order, docstrings, outdated syntax |
| `uv run ruff check --fix` | Fix the findings Ruff can fix automatically |

---

## Costs and safety

- **Costs**: every message makes one or two calls to Claude Haiku, so a quiz session costs very little, but it is not free. Set a monthly spending limit in the Anthropic console.
- **Keys**: keep them in `.env` only. It is gitignored; check `git status` before every commit.
- **Local use only**: `langgraph dev` and the Streamlit app have **no authentication**, and `user_id` is just a name anyone can type. Do not expose them on the internet as they are. A public deployment needs real login, so the server sets the user's identity, plus rate limits.
- **Data**: in development, threads and memory are stored on your machine in `.langgraph_api/` (gitignored). Delete that folder (with the server stopped) to reset everything.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `401 invalid x-api-key` | Your `ANTHROPIC_API_KEY` in `.env` is wrong or empty. Restart the server after fixing it. |
| No traces in LangSmith | Set `LANGSMITH_API_KEY` and `LANGSMITH_TRACING=true` in `.env`, then restart the server. |
| Port 2024 already in use | An old server is still running. Stop it (Ctrl+C in its terminal), or find and stop the process using port 2024. |
| Error about a thinking block "bound to a different conversation" | A thread was started with an older prompt. Start a **new thread**. |
| Windows: `os error 4551` / "Application Control policy has blocked this file" | Windows Smart App Control blocks the `.exe` launchers in `.venv\Scripts`. Run the tools through Python instead: `uv run python -m langgraph_cli dev`, `uv run python -m pytest`, `uv run python -m streamlit run frontend/app.py`. Use a Python installer from python.org, which is signed. |
| The UI says it can't reach the server | Start `uv run langgraph dev` first, in another terminal. |

---

## Roadmap

- [x] Graph with a quiz master node and a ReAct tool loop over your notes
- [x] Structured grading with retries and a score per quiz
- [x] Long-term memory per user with the LangGraph Store
- [x] Streamlit frontend over the LangGraph API
- [x] LangSmith tracing and a first evaluation experiment
- [ ] Human-in-the-loop with `interrupt()`
- [ ] Evaluation in code (datasets and evaluators as Python scripts)
- [ ] Production hardening: authentication, rate limits, Postgres for threads and memory
- [ ] Deployment: Docker image for the agent server and a hosted frontend

---

## Ideas to extend it

Good next exercises, roughly from easiest to hardest:

1. **Consistent topic names**: give the grader the list of existing topics so that "Python tuples" and "Python tuples and lists" don't become two topics.
2. **Human-in-the-loop**: use `interrupt()` to pause after five answers and ask "Switch difficulty? (yes/no)", then resume with the answer.
3. **Async nodes**: convert the nodes to `async def` and see how the server runs them.
4. **Evaluation in code**: turn your LangSmith dataset and evaluator into a Python script, so you can run it before every change.
5. **Authentication and deployment**: add a LangGraph auth handler so the server sets `user_id` from a login token, then deploy with Docker.

---

## License

[MIT](LICENSE)
