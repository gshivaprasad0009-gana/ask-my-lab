"""
The agent — turns a question in plain English into an answer about your data.

Two modes, and it picks automatically:

* **LLM mode** — if `LLM_BASE_URL` and `LLM_API_KEY` are set, the question and
  the tool descriptions are sent to an OpenAI-compatible model. The model
  chooses which tool to call; we run it and feed the result back; the model
  writes the final answer.
* **Rules mode** — with no configuration at all, a small keyword matcher picks
  the tool and a template writes the answer. Less flexible, but it runs free,
  offline, and deterministically — which is what makes the project testable.

The important idea is the same in both modes: **the model never invents the
numbers.** It asks a tool, and the tool reads the database.

Configuration (all optional):
    LLM_BASE_URL   e.g. https://api.openai.com/v1   (or a local Ollama, Groq, …)
    LLM_API_KEY    your key
    LLM_MODEL      model name, e.g. gpt-4o-mini
"""

import json
import os
import re
import urllib.error
import urllib.request

import tools

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are LabMind, an assistant that answers questions about readings from a "
    "lab environment monitor (temperature, humidity and light sensors). "
    "Always call a tool to get the real numbers — never guess or invent data. "
    "Answer in one or two short sentences, quoting the actual values, with units. "
    "If the data does not contain the answer, say so plainly."
)


# ----------------------------------------------------------------------
# Rules mode — no configuration needed
# ----------------------------------------------------------------------

# Words that select each tool. Matched on whole words, not substrings —
# otherwise "meaning" would match "mean" and nonsense questions would get
# a data answer instead of the help message.
_ANOMALY_WORDS = {"anomaly", "anomalies", "anomalous", "spike", "spikes",
                  "alert", "alerts", "abnormal", "unusual"}
_COUNT_PHRASES = ("how many", "number of readings")
_DEVICE_WORDS = {"device", "devices"}
_LATEST_WORDS = {"latest", "current", "now"}
_LATEST_PHRASES = ("right now", "last reading", "most recent")
_STATS_WORDS = {"average", "avg", "mean", "summary", "overall", "statistics", "stats"}
_SINCE_WORDS = {"today", "overnight", "recent", "recently", "since", "hours", "last"}


def _pick_tool(question: str):
    """Choose a tool (and arguments) from the words in the question."""
    q = question.lower()
    words = set(re.findall(r"[a-z]+", q))

    # Most specific first, so "last reading" beats the generic "last".
    if words & _ANOMALY_WORDS or "too hot" in q:
        return "recent_anomalies", {}
    if any(phrase in q for phrase in _COUNT_PHRASES) or "count" in words:
        return "count_readings", {}
    if words & _DEVICE_WORDS:
        return "device_list", {}
    if words & _LATEST_WORDS or any(phrase in q for phrase in _LATEST_PHRASES):
        return "latest_reading", {}
    if words & _STATS_WORDS:
        return "summary_stats", {}
    if words & _SINCE_WORDS:
        hours = 24
        match = re.search(r"\d+", q)
        if match:
            hours = int(match.group())
        return "readings_since", {"hours": hours}
    return None, {}


def _format(tool_name: str, result) -> str:
    """Turn a tool's raw result into a readable sentence."""
    if tool_name == "latest_reading":
        if not result:
            return "There are no readings stored yet."
        return (
            f"The most recent reading was {result['temperature']} °C, "
            f"{result['humidity']} % humidity and {result['light']} % light "
            f"(device {result['device']}, at {result['ts']})."
        )

    if tool_name == "summary_stats":
        if not result:
            return "There are no readings stored yet."
        t = result["temperature"]
        return (
            f"Across {result['readings']} readings, temperature averaged "
            f"{t['average']} °C (lowest {t['min']} °C, highest {t['max']} °C). "
            f"Humidity averaged {result['humidity_average']} % and light "
            f"{result['light_average']} %."
        )

    if tool_name == "recent_anomalies":
        if not result:
            return "No temperature spikes were found above the threshold."
        newest = result[0]
        return (
            f"I found {len(result)} readings above the threshold. The most recent "
            f"was {newest['temperature']} °C at {newest['ts']}."
        )

    if tool_name == "count_readings":
        return f"There are {result} readings stored."

    if tool_name == "device_list":
        if not result:
            return "No devices have reported any readings."
        return "Devices reporting: " + ", ".join(result) + "."

    if tool_name == "readings_since":
        if not result:
            return "No readings were recorded in that period."
        temps = [r["temperature"] for r in result]
        return (
            f"In that period there were {len(result)} readings. Temperature ranged "
            f"from {min(temps)} °C to {max(temps)} °C "
            f"(average {round(sum(temps) / len(temps), 1)} °C)."
        )

    return "I could not work out how to answer that."


HELP = (
    "I can answer questions about the stored sensor readings, for example: "
    "\"What is the latest reading?\", \"What is the average temperature?\", "
    "\"Were there any spikes?\", \"How many readings are there?\", "
    "\"What happened in the last 6 hours?\""
)


def ask_with_rules(question: str) -> dict:
    """Answer using keyword matching only — no model, no network, no cost."""
    tool_name, arguments = _pick_tool(question)
    if tool_name is None:
        return {"answer": HELP, "tool": None, "mode": "rules"}

    result = tools.call_tool(tool_name, arguments)
    return {"answer": _format(tool_name, result), "tool": tool_name, "mode": "rules"}


# ----------------------------------------------------------------------
# LLM mode — used only when configured
# ----------------------------------------------------------------------

def llm_available() -> bool:
    return bool(LLM_BASE_URL and LLM_API_KEY)


def _post(payload: dict) -> dict:
    request = urllib.request.Request(
        f"{LLM_BASE_URL}/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LLM_API_KEY}",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


def ask_with_llm(question: str, max_steps: int = 4) -> dict:
    """Let the model choose tools, run them, and write the answer."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    openai_tools = [
        {"type": "function", "function": t} for t in tools.TOOLS
    ]
    used_tool = None

    for _ in range(max_steps):
        payload = {
            "model": LLM_MODEL,
            "messages": messages,
            "tools": openai_tools,
            "temperature": 0,
        }
        reply = _post(payload)["choices"][0]["message"]
        messages.append(reply)

        tool_calls = reply.get("tool_calls")
        if not tool_calls:
            return {"answer": reply.get("content", ""), "tool": used_tool, "mode": "llm"}

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = json.loads(call["function"].get("arguments") or "{}")
            used_tool = name
            try:
                result = tools.call_tool(name, arguments)
            except Exception as e:                      # tell the model, don't crash
                result = {"error": str(e)}
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": json.dumps(result, default=str),
            })

    return {"answer": "I could not work that out.", "tool": used_tool, "mode": "llm"}


# ----------------------------------------------------------------------

def ask(question: str) -> dict:
    """Answer a question, using the LLM when configured and rules otherwise."""
    if llm_available():
        try:
            return ask_with_llm(question)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            fallback = ask_with_rules(question)
            fallback["answer"] += f"  (LLM unavailable: {e})"
            return fallback
    return ask_with_rules(question)


if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) or "What is the latest reading?"
    answer = ask(question)
    print(f"[{answer['mode']}] {answer['answer']}")
