"""
LabMind — a chat interface for your lab data.

Ask questions in plain English; the agent queries the sensor database and
answers. Runs with no configuration (rules mode), or with a real LLM if you
set LLM_BASE_URL and LLM_API_KEY.

Usage:
    python seed_data.py      # first time only — creates sample data
    streamlit run app.py
"""

import streamlit as st

import agent
import tools

st.set_page_config(page_title="LabMind", page_icon="🔬", layout="wide")

st.title("🔬 LabMind")
st.caption("Ask your lab a question in plain English.")

# --- sidebar ----------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Mode")
    if agent.llm_available():
        st.success(f"LLM mode — {agent.LLM_MODEL}")
    else:
        st.info(
            "**Rules mode** — no configuration needed.\n\n"
            "To use a real language model, set:\n"
            "`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`"
        )

    st.header("📊 Your data")
    try:
        st.metric("Readings stored", tools.count_readings())
        latest = tools.latest_reading()
        if latest:
            st.write(
                f"Latest: **{latest['temperature']} °C**, "
                f"{latest['humidity']} % humidity, {latest['light']} % light"
            )
            st.caption(f"at {latest['ts']}")
    except FileNotFoundError:
        st.warning("No data yet — run `python seed_data.py`.")

    st.header("💡 Try asking")
    for example in [
        "What is the latest reading?",
        "What is the average temperature?",
        "Were there any spikes?",
        "How many readings are there?",
        "What happened in the last 6 hours?",
    ]:
        st.caption(f"• {example}")

# --- chat -------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Hi! Ask me anything about the readings from your lab sensors.",
    }]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tool"):
            st.caption(f"answered using the `{message['tool']}` tool")

if question := st.chat_input("Ask about your lab data…"):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            result = agent.ask(question)
            st.markdown(result["answer"])
            if result.get("tool"):
                st.caption(f"answered using the `{result['tool']}` tool")
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "tool": result.get("tool"),
            })
        except FileNotFoundError as e:
            st.error(str(e))
