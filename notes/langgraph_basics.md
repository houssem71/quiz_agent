# LangGraph basics

- A graph is built from **nodes** (Python functions) connected by **edges**, and a shared **state** flows through it.
- A node receives the state and returns a **partial update**: only the keys it changes.
- A **reducer** decides how an update is merged. `MessagesState` appends new messages instead of replacing the list.
- `StateGraph(...)` is the builder; `.compile()` checks it and returns a runnable graph.
- `Command(goto=..., update=...)` lets a node update the state and choose the next node at the same time.
- `bind_tools` sends tool schemas to the model. The model only *requests* a tool call; your code runs the tool.
- Each tool result is a `ToolMessage` linked to its request by `tool_call_id`.
- The **ReAct loop** alternates model and tools until the model replies without calling a tool.
- A limit such as `max_react_tool_calls` stops a model that keeps calling tools forever.
- `langgraph.json` points to the compiled graph with `file.py:variable`; `langgraph dev` serves it on port 2024.
