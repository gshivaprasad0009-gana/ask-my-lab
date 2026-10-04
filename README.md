# 🔬 LabMind

**Ask your lab a question in plain English.**

LabMind is an AI agent that answers questions about sensor data — temperature,
humidity and light readings from an environment monitor. You ask; it works out
which data it needs, queries the database, and answers with the real numbers.

```
You:  Were there any spikes overnight?
It:   I found 12 readings above the threshold. The most recent was 52.4 °C at 03:15:00.
```

The point is the pattern: **the model never invents the numbers.** It chooses a
tool, the tool reads the database, and the model phrases the result. That is how
every reliable AI assistant is built, and it is the thing most "chatbot" projects
get wrong.

## ✨ Why this is interesting

- 🤖 **Agentic AI, done properly** — the model calls tools instead of guessing
- 🔌 **Grounded in real data** — every answer comes from a database query
- 🆓 **Runs with zero setup** — no API key needed; a rules engine answers instead
- 🔑 **Real LLM when you want it** — any OpenAI-compatible model (OpenAI, Groq, a local Ollama)
- 🧪 **Tested** — the agent's tool selection is covered by tests
- 🐍 **Two dependencies** — Streamlit and pytest. Nothing else.

## 🏗️ How it works

```
                       ┌──────────────────────────────┐
   "Were there        │  agent.py                    │
    any spikes?"  ──► │  1. pick a tool              │
                       │  2. run it against the DB    │
                       │  3. phrase the answer        │
                       └───────────┬──────────────────┘
                                   │ calls
                       ┌───────────▼──────────────────┐
                       │  tools.py                    │
                       │  latest_reading()            │
                       │  summary_stats()             │
                       │  recent_anomalies()          │
                       │  readings_since()            │
                       │  count_readings()            │
                       │  device_list()               │
                       └───────────┬──────────────────┘
                                   │ reads
                       ┌───────────▼──────────────────┐
                       │  data/sensors.db (SQLite)    │
                       └──────────────────────────────┘
```

The agent has **two modes** and picks automatically:

| Mode | When | What it does |
|---|---|---|
| **Rules** | default — no configuration | keyword matching picks the tool; a template writes the answer |
| **LLM** | when `LLM_BASE_URL` + `LLM_API_KEY` are set | the model chooses tools and writes the answer |

Rules mode exists for two reasons: it makes the project runnable by anyone in
one command, and it makes the agent **testable** — you cannot write a reliable
test against a model that answers differently every time.

## 🚀 Quick start

```bash
pip install -r requirements.txt
python seed_data.py          # creates a day of sample readings
streamlit run app.py
```

Open `http://localhost:8501` and ask it something.

**Or from the command line, with no UI:**

```bash
python agent.py "What is the average temperature?"
python agent.py "Were there any spikes?"
```

## 💬 What it can answer

| Question | Tool used |
|---|---|
| "What is the latest reading?" | `latest_reading` |
| "What is the average temperature?" | `summary_stats` |
| "Were there any spikes?" | `recent_anomalies` |
| "How many readings are there?" | `count_readings` |
| "Which devices reported?" | `device_list` |
| "What happened in the last 6 hours?" | `readings_since` |

Ask something outside that list and it tells you what it *can* answer, rather
than making something up.

## 🔑 Using a real language model (optional)

LabMind speaks to any OpenAI-compatible API, so you are not locked to one
provider. Set three environment variables:

```bash
export LLM_BASE_URL="https://api.openai.com/v1"   # or Groq, Together, local Ollama
export LLM_API_KEY="your-key-here"
export LLM_MODEL="gpt-4o-mini"
streamlit run app.py
```

The sidebar shows which mode is active. If the API is unreachable, it falls
back to rules mode rather than failing.

**Never commit your key.** It belongs in your environment — that is why `.env`
is in `.gitignore`.

## 🔗 Using your own data

LabMind uses the same database schema as the
[ESP32 Environment Monitor](https://github.com/gshivaprasad0009-gana/esp32-environment-monitor),
so you can point it at that project's real data:

```bash
SENSOR_DB=../esp32-environment-monitor/data/sensors.db streamlit run app.py
```

## 🧪 Tests

```bash
pytest -q
```

They cover the data tools, the tool registry (every tool the model is told about
must actually exist), and the rules-mode agent's tool selection — all offline.

## 📁 Project structure

```
ask-my-lab/
├── tools.py             # the data tools — one function per question type
├── agent.py             # the agent: LLM tool-calling + rules fallback
├── seed_data.py         # generates sample readings
├── app.py               # Streamlit chat interface
├── tests/test_agent.py
├── .github/workflows/tests.yml
└── requirements.txt
```

## 🎓 How to understand this code

If you are learning Python, read the files in this order:

1. **`tools.py`** — start at `count_readings()`. It is five lines. Every tool
   follows the same shape: open the database, run one query, return the result.
2. **`agent.py`**, the `_pick_tool()` function — plain `if` statements on the
   words in your question. You could write this yourself.
3. **`agent.py`**, `_format()` — turning a query result into a sentence.
4. **`agent.py`**, `ask_with_llm()` — the real agent loop: send the question,
   run whatever tool the model asks for, send the result back.

Steps 1–3 are beginner Python. Step 4 is where it gets interesting, and you will
be able to read it once you are through the 30-day challenge.

## 🗺️ Roadmap

- [ ] Add more tools (trends, comparisons between days, per-device breakdowns)
- [ ] Chart the data when the answer is visual
- [ ] Remember the conversation (multi-turn questions)
- [ ] Deploy to AWS — Bedrock for the model, Lambda for the tools
- [ ] Expose the tools as an MCP server, so other AI apps can use your sensors

## 📄 License

Released under the [MIT License](LICENSE).

## ✍️ Author

**Ganamolla Shiva Prasad** — B.Tech ECE student, building in Python, AI/ML, IoT
and cloud computing.
