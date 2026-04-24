{%- if cookiecutter.interface in ["cli", "both"] -%}
"""Interactive CLI chat interface."""

from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

# Load .env into os.environ early so downstream SDKs (openai, pydantic-ai)
# see OPENAI_API_KEY / OPENAI_BASE_URL when libraries instantiate their own
# provider clients. pydantic-settings reads .env into the Settings model
# only — the OS environment stays untouched without this call.
load_dotenv()

from {{ cookiecutter.package_name }}.orchestrator import Orchestrator
from {{ cookiecutter.package_name }}.utils.logging import setup_logging
from {{ cookiecutter.package_name }}.utils.tracing import trace_request


async def chat_loop(user_id: str = "cli-user", session_id: str = "cli-session") -> None:
    """Run an interactive chat REPL."""
    setup_logging(json_output=False)
    orchestrator = Orchestrator()

    print(f"{{ cookiecutter.project_name }} - Interactive Chat")
    print("Type 'quit' or 'exit' to end the conversation.")
    print("-" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye!")
            break

        print("\nAssistant: ", end="", flush=True)
        with trace_request():
            async for token in orchestrator.chat_stream(
                user_input, user_id=user_id, session_id=session_id,
            ):
                print(token, end="", flush=True)
        print()


def main() -> None:
    """Entry point for the CLI."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="{{ cookiecutter.project_name }} CLI")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Override log level")
    parser.add_argument("--user-id", default="cli-user", help="User ID (default: cli-user)")
    parser.add_argument("--session-id", default="cli-session", help="Session ID (default: cli-session)")
    args = parser.parse_args()

    if args.debug:
        os.environ["DEBUG"] = "true"
        os.environ.setdefault("LOG_LEVEL", "DEBUG")
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level

    try:
        asyncio.run(chat_loop(user_id=args.user_id, session_id=args.session_id))
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
{%- endif %}
