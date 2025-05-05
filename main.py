import asyncio
import json
import os
import subprocess
import textwrap

import streamlit as st
from agents import Agent, Runner, function_tool, ItemHelpers
from agents.items import ToolCallItem, ToolCallOutputItem, MessageOutputItem, ReasoningItem

openai_key = os.getenv("OPENAI_API_KEY")
if not openai_key:
    st.error("❌  OPENAI_API_KEY environment variable not found inside the container.")
    st.stop()

WORKDIR = "/workdir"  # this is the volume the user mounts on `docker run`


def _safe_path(path: str) -> str:
    """Resolve path inside WORKDIR and reject escapes."""
    abs_path = os.path.abspath(os.path.join(WORKDIR, path))
    if not abs_path.startswith(WORKDIR):
        raise ValueError("Path escapes /workdir – forbidden")
    return abs_path


@function_tool
def execute_command(command: str) -> str:
    """Run a shell command inside /workdir and return the combined output."""
    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=WORKDIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    out, _ = proc.communicate()
    return out


@function_tool
def write_file(path: str, content: str) -> str:
    """Create or overwrite *path* inside /workdir with the supplied *content*."""
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


def main():
    assistant = Agent(
        name="Simple DinD CLI Assistant",
        model="o4-mini",
        instructions=textwrap.dedent(
            """
            You are running inside an isolated Docker container (but you can and should use docker -- you have support enabled via DinD).
            • Only files under /workdir are accessible.
            • Use the provided tools to search the web, inspect or modify files,
            and run shell commands for the user.
            """
        ),
        tools=[
            # TODO: some search tool
            # WebSearchTool(),
            execute_command,
            write_file,
            read_file,
        ],
    )

    st.set_page_config(page_title="Simple DinD CLI Agent", page_icon="🐳")
    st.title("🐳 Simple DinD CLI Agent")

    if "history" not in st.session_state:
        st.session_state.history = []

    # Render prior messages
    for msg in st.session_state.history:
        st.chat_message(msg["role"]).markdown(msg["content"])

    # New user prompt
    prompt = st.chat_input("Type a request…")
    if prompt:
        # Show the user message immediately
        st.session_state.history.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        with st.spinner("Running agent…"):
            result = asyncio.run(Runner.run(assistant, prompt, max_turns=40))

        trace_md = []
        for item in result.new_items:
            if isinstance(item, ToolCallItem):
                content = f"🔧 **Tool call** `{item.raw_item.name}`\n```json\n{json.dumps(item.raw_item.arguments, indent=2)}\n```"
                st.session_state.history.append({"role": "tool", "content": content})
            elif isinstance(item, ToolCallOutputItem):
                content = f"📤 **Tool result** \n```\n{item.output}\n```"
                st.session_state.history.append({"role": "tool_result", "content": content})
            elif isinstance(item, MessageOutputItem):
                content = ItemHelpers.text_message_output(item)
                content = f"🤖 **LLM message**\n```\n{content}\n```"
                st.session_state.history.append({"role": "assistant", "content": content})
            elif isinstance(item, ReasoningItem):
                # content = ItemHelpers.text_message_output(item)
                # content = f"🤖 **LLM message**\n```\n{content}\n```"
                content = item.raw_item
                st.session_state.history.append({"role": "reasoning", "content": content})
            else:
                st.session_state.history.append({"role": "unknown", "content": str(item)})

            # msg = st.session_state.history[-1]
            # st.chat_message(msg['role']).markdown(msg['content'])

        if trace_md:
            st.divider()
            st.subheader("Full execution trace")
            st.markdown("\n\n".join(trace_md))

        st.rerun()


if __name__ == '__main__':
    main()
