# 📖 Project Guide — LabMind (ask-my-lab)

Everything about this project, explained from the ground up.

**Repository:** `ask-my-lab`
**What it is in one line:** an AI agent that answers questions about sensor
data in plain English — and it looks the answer up in a database instead of
guessing.

---

## 1. What problem does it solve?

You have a lab full of sensors and a database full of readings. To get anything
out of it, you have to know SQL, or click through a dashboard, or scroll a
table looking for the interesting row.

LabMind lets you just *ask*:

```
You:  Were there any spikes?
It:   I found 10 readings above the threshold. The most recent was 45.0 °C at 03:19:28.
```

The interesting part is not the chat box. It is that **the answer is real**.
The language model never invents a temperature — it asks a tool, the tool reads
the database, and the model only puts the result into a sentence.

That distinction is the whole project. Most "AI chatbot" projects let the model
make things up; this one does not.

---

## 2. The big picture

```
   "Were there any spikes?"
              │
              ▼
   ┌──────────────────────────┐
   │        agent.py          │
   │  1. decide which tool    │
   │  2. run it               │
   │  3. phrase the answer    │
   └───────────┬──────────────┘
               │ calls
   ┌───────────▼──────────────┐
   │        tools.py          │
   │  latest_reading()        │
   │  summary_stats()         │
   │  recent_anomalies()      │
   │  readings_since()        │
   │  count_readings()        │
   │  device_list()           │
   └───────────┬──────────────┘
               │ reads
   ┌───────────▼──────────────┐
   │   data/sensors.db        │
   └──────────────────────────┘
```

---

## 3. The two modes — and why there are two

The agent has two ways of deciding which tool to use:

| Mode | When it runs | How it decides |
|---|---|---|
| **Rules** | by default, with no configuration | keyword matching in `_pick_tool()` |
| **LLM** | when `LLM_BASE_URL` and `LLM_API_KEY` are set | the language model chooses the tool |

Rules mode exists for two very practical reasons:

1. **Anyone can run the project.** No API key, no account, no cost, no internet.
2. **The agent becomes testable.** You cannot write a reliable test against a
   model that answers slightly differently every time. Rules mode is
   deterministic, so the test suite can assert exact behaviour.

That is a real engineering trade-off, not a shortcut: LLM mode is smarter,
rules mode is verifiable. Having both is the honest answer.

---

## 4. Every technology used, and what it is

| Technology | What it actually is | Where it appears |
|---|---|---|
| **Python** | The language everything is written in. | all files |
| **SQLite** | A database in a single file. No server. | `tools.py` |
| **Streamlit** | Turns a Python script into a web page — no HTML or JavaScript needed. | `app.py` |
| **JSON** | A text format for structured data. Used for the database rows, the tool definitions, and talking to the model. | `agent.py`, `tools.py` |
| **LLM (Large Language Model)** | A model trained on huge amounts of text that can hold a conversation and follow instructions. Here it is used for one narrow job: choosing a tool. | `agent.py` |
| **Tool calling** | The mechanism where you describe functions to a model, the model replies "call `recent_anomalies` with `threshold=40`", you run it and hand back the result. This is how reliable AI assistants are built. | `agent.py` |
| **OpenAI-compatible API** | A widely copied HTTP interface. Because many providers implement it (OpenAI, Groq, local Ollama), this project is not locked to one vendor. | `agent.py` |
| **urllib** | Python's built-in way to make web requests — used so the project needs no HTTP library installed. | `agent.py` |
| **Environment variables** | Settings from outside the program. This is where the API key goes, so it never ends up in the code. | `agent.py` |
| **pytest** | The Python testing tool. | `tests/` |
| **GitHub Actions** | Runs the tests automatically on every push. | `.github/workflows/tests.yml` |
| **Regular expressions** | Pattern matching on text. Used to find the number in "the last 6 hours". | `agent.py` |

---

## 5. File-by-file: what each one does

### `tools.py` — the agent's hands
Six functions, each answering one factual question. They are kept separate from
the agent for a reason: they can be tested on their own, and reused anywhere
(a script, a dashboard, a different agent).

- `latest_reading()` — the newest row
- `summary_stats()` — counts, averages, min and max
- `recent_anomalies(threshold, limit)` — readings above a temperature
- `readings_since(hours)` — the last N hours
- `count_readings()` — how many rows exist
- `device_list()` — which devices reported

At the bottom is `TOOLS`: a list of descriptions of each function. **These
descriptions are the only thing the language model sees** when deciding what to
call, which is why they are written so carefully.

### `agent.py` — the brain
Three parts:

1. `_pick_tool()` — rules mode. Reads the question's words and picks a tool.
   Note it matches on **whole words**, not substrings — otherwise "meaning"
   would match "mean" and a nonsense question would get a data answer.
2. `ask_with_llm()` — the real agent loop: send the question and the tool
   descriptions to the model; if the model asks for a tool, run it; send the
   result back; the model writes the final answer. This repeats until the model
   answers without asking for another tool.
3. `ask()` — picks the mode, and falls back to rules if the API is unreachable.

### `seed_data.py` — the data
Creates `data/sensors.db` with a day of believable readings, so the project runs
with no hardware. Same schema as the ESP32 project, so you can point it at real
data instead.

### `app.py` — the chat page
A Streamlit interface: a message history, a text box, and a sidebar showing
which mode is active and some live stats. Each answer is labelled with the tool
that produced it — so you can see it really did look the answer up.

### `tests/test_agent.py`
21 tests. They cover the tools against a known database, the tool registry
(every tool advertised to the model must actually exist — otherwise the model
would call a function that is not there), and the rules agent's choice of tool
for each kind of question.

### The other files
- `README.md` — features, quick start, examples, how to configure an LLM
- `LICENSE` — MIT
- `requirements.txt` — just Streamlit and pytest

---

## 6. How to run it

```bash
pip install -r requirements.txt
python seed_data.py          # create sample data
streamlit run app.py         # the chat page
```

Or from the terminal, no UI:

```bash
python agent.py "What is the average temperature?"
python agent.py "Were there any spikes?"
```

To use a real language model:

```bash
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_API_KEY="your-key-here"
export LLM_MODEL="gpt-4o-mini"
streamlit run app.py
```

---

## 7. Concepts worth understanding (in this order)

1. **A function that takes arguments and returns a value** — `count_readings()`
   is five lines; start there
2. **`if` / `elif` statements** — that is all `_pick_tool()` is
3. **A list of dictionaries** — that is what `TOOLS` is
4. **An HTTP request** — sending data to a server and getting a reply
5. **Tool calling** — the loop in `ask_with_llm()`

Items 1–3 are beginner Python and cover most of the file. Item 5 is the idea
worth understanding properly, because it is how modern AI applications are built.

---

## 8. Common problems and what they mean

| Symptom | What is happening | Fix |
|---|---|---|
| `No sensor database at …` | The sample data has not been created | Run `python seed_data.py` |
| Answers always come from rules mode | No API key configured | Set `LLM_BASE_URL` and `LLM_API_KEY`, or accept rules mode |
| `(LLM unavailable: …)` appended to an answer | The API call failed | Check the key and your internet — the agent deliberately falls back rather than crashing |
| `ModuleNotFoundError: streamlit` | Dependencies not installed | `pip install -r requirements.txt` |
| A question gets the "I can answer questions about…" reply | The wording did not match any tool | Rephrase using words like *latest*, *average*, *spikes*, *how many*, *hours* |

---

## 9. What you would say about this project in an interview

> "It's an AI agent over a sensor database. The model doesn't generate numbers —
> it chooses which tool to call, the tool runs a real SQL query, and the model
> phrases the result. I kept a rules-based fallback so the project runs with no
> API key and so the tool selection is actually testable. There are 21 tests."

The phrase **"the model doesn't generate numbers"** is the one that lands,
because it shows you understand the difference between a demo and something
you would trust.

---

## 10. Where this project goes next

See the roadmap in the README. The interesting next step is exposing these tools
as an **MCP server**, so other AI applications can use your sensors — or moving
the whole thing onto AWS Bedrock for the model and Lambda for the tools.
