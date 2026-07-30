"""Interactive CLI agent that lets an OpenRouter-hosted LLM drive the calendar-mcp
server's tools (list/create/update/delete events, free/busy, etc.) via MCP over stdio.

The reusable machinery (system prompt, OpenRouter call, tool-calling loop) lives in
src/scheduling_agent.py, shared with interview_api.py's HTTP endpoints.
"""
import asyncio
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.scheduling_agent import build_system_prompt, handle_message, mcp_tool_to_openai_tool

# Avoid crashing when the model's reply contains characters (e.g. emoji) that
# the terminal's codepage can't encode (common on Windows consoles).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_EXE = os.path.join(PROJECT_DIR, "calendar_mcp", "Scripts", "python.exe")
RUN_SERVER = os.path.join(PROJECT_DIR, "run_server.py")

# One-off bootstrap task run automatically before the interactive prompt starts.
# Leave as "" to skip straight to the interactive loop.
BOOTSTRAP_TASK = ""


async def run_agent():
    from src.scheduling_agent import OPENROUTER_API_KEY

    if not OPENROUTER_API_KEY or "YOUR_OPENROUTER_API_KEY" in OPENROUTER_API_KEY:
        print("Set OPENROUTER_API_KEY in .env first (get one at https://openrouter.ai/keys).")
        return

    server_env = os.environ.copy()
    server_env["RELOAD"] = "false"  # avoid uvicorn's reload supervisor when embedded via stdio

    server_params = StdioServerParameters(
        command=PYTHON_EXE,
        args=[RUN_SERVER],
        env=server_env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            openai_tools = [mcp_tool_to_openai_tool(t) for t in tools_result.tools]
            print(f"Connected to calendar-mcp server. {len(openai_tools)} tools available.")

            messages = [{"role": "system", "content": build_system_prompt()}]

            async def say(user_input: str) -> None:
                reply = await handle_message(session, messages, openai_tools, user_input)
                print(f"Agent: {reply or '(stopped after too many tool-call iterations)'}\n")

            if BOOTSTRAP_TASK.strip():
                print(f"You: {BOOTSTRAP_TASK}")
                await say(BOOTSTRAP_TASK)

            print("Calendar agent ready. Type 'exit' to quit.\n")
            while True:
                user_input = input("You: ").strip()
                if user_input.lower() in ("exit", "quit"):
                    break
                if not user_input:
                    continue
                await say(user_input)


if __name__ == "__main__":
    import logging

    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="  -> %(message)s")
    asyncio.run(run_agent())
