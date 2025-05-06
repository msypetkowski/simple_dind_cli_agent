import asyncio
import json
import os
import subprocess
import textwrap
from typing import List

import streamlit as st
from agents import Agent, Runner, function_tool, ItemHelpers
from agents.items import (
    ToolCallItem,
    ToolCallOutputItem,
    MessageOutputItem,
    ReasoningItem,
)

openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    st.error("❌  OPENAI_API_KEY environment variable not found inside the container.")
    st.stop()

WORKDIR = "/workdir"  # this is the volume the user mounts on `docker run`


def _safe_path(path: str) -> str:
    """Resolve *path* inside WORKDIR and reject escapes."""
    abs_path = os.path.abspath(os.path.join(WORKDIR, path))
    if not abs_path.startswith(WORKDIR):
        raise ValueError("Path escapes /workdir – forbidden")
    return abs_path


@function_tool
def execute_command(command: str) -> str:
    """
    Run *command* inside /workdir and return the combined output.

    If the command produces more than 100 lines of output, only the first 50 and
    last 50 lines are returned. A single informational line is inserted between
    them indicating how many lines were omitted, e.g.:

        ... [truncated 245 lines] ...
    """
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=WORKDIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out, _ = proc.communicate()

    lines: List[str] = out.splitlines()
    if len(lines) <= 100:
        return out

    keep_head = 50
    keep_tail = 50
    omitted = len(lines) - keep_head - keep_tail
    truncated_output = (
            lines[:keep_head]
            + [f"... [truncated {omitted} lines] ..."]
            + lines[-keep_tail:]
    )
    return "\n".join(truncated_output)


@function_tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite *path* inside /workdir with *content*."""
    abs_path = _safe_path(path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"


@function_tool
def read_file(path: str) -> str:
    """Return the full contents of *path* inside /workdir."""
    abs_path = _safe_path(path)
    with open(abs_path, "r", encoding="utf-8") as f:
        return f.read()


assistant = Agent(
    name="Simple DinD CLI Assistant",
    model="o4-mini",
    instructions=textwrap.dedent(
        """
        You are running inside an isolated Docker container (but you can and should use docker -- you have DinD support).
        • Only files under /workdir are accessible.
        • Use the provided tools to search the web, inspect or modify files, and run shell commands for the user.
        """
    ),
    tools=[
        execute_command,
        write_file,
        read_file,
    ],
)


def _append_and_render(role: str, content: str):
    """Utility: store a message in session_state and render it immediately."""
    st.session_state.history.append({"role": role, "content": content})
    st.chat_message(role).markdown(content)


def _render_stream_event(event):
    """Handle one streaming event coming from Runner.run_streamed."""
    if event.type == "run_item_stream_event":
        item = event.item
        if isinstance(item, ToolCallItem):
            content = (
                f"🔧 **Tool call** `{item.raw_item.name}`\n```json\n{json.dumps(item.raw_item.arguments, indent=2)}\n```"
            )
            _append_and_render("tool", content)
        elif isinstance(item, ToolCallOutputItem):
            content = f"📤 **Tool result**\n```\n{item.output}\n```"
            _append_and_render("tool_result", content)
        elif isinstance(item, MessageOutputItem):
            content = f"🤖 **LLM message**\n```\n{ItemHelpers.text_message_output(item)}\n```"
            _append_and_render("assistant", content)
        elif isinstance(item, ReasoningItem):
            _append_and_render("reasoning", item.raw_item)
    elif event.type == "agent_updated_stream_event":
        pass


async def _run_agent_and_stream(input_data, max_turns: int = 40):
    """Run the agent and push UI updates *while* it is running."""
    result_streaming = Runner.run_streamed(
        assistant, input_data, max_turns=max_turns
    )
    async for ev in result_streaming.stream_events():
        _render_stream_event(ev)
        await asyncio.sleep(0)  # let Streamlit refresh
    return result_streaming


st.set_page_config(page_title="Simple DinD CLI Agent", page_icon="🐳")
st.title("🐳 Simple DinD CLI Agent")

# Chat-render history (for UI only)
if "history" not in st.session_state:
    st.session_state.history = []

# Persistent conversation the model receives each turn
if "conversation" not in st.session_state:
    st.session_state.conversation = []  # list[dict] in Agents-SDK format

# Render prior chat history (UI)
for msg in st.session_state.history:
    st.chat_message(msg["role"]).markdown(msg["content"])

# New user prompt
prompt = st.chat_input("Type a request…")
if prompt:
    # Show the user message immediately (UI only)
    _append_and_render("user", prompt)

    # ----- Build input list the agent should see -----
    input_list = st.session_state.conversation + [
        {"role": "user", "content": prompt}
    ]

    # ----- Run the agent, streaming events in real-time -----
    with st.spinner("Running agent…"):
        result = asyncio.run(_run_agent_and_stream(input_list, max_turns=40))

    # ----- Save updated conversation for the next turn -----
    st.session_state.conversation = result.to_input_list()

    # Optional: show trace
    if hasattr(result, "trace_spans") and result.trace_spans:
        if st.toggle("Show full execution trace"):
            trace_md = [span.to_markdown() for span in result.trace_spans]
            st.markdown(" ".join(trace_md))

    # Rerun so that history (now fully updated) is rendered from scratch
    st.rerun()

if __name__ == "__main__":
    # Running inside `streamlit run` automatically executes the script
    pass
