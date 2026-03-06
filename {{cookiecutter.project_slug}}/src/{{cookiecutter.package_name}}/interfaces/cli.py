{%- if cookiecutter.interface in ["cli", "both"] -%}
"""Interactive CLI chat interface."""

from __future__ import annotations

import asyncio
import sys

from {{ cookiecutter.package_name }}.orchestrator import Orchestrator
from {{ cookiecutter.package_name }}.utils.logging import setup_logging
from {{ cookiecutter.package_name }}.utils.tracing import trace_request


async def chat_loop() -> None:
    """Run an interactive chat REPL."""
    setup_logging(json_output=False)
    orchestrator = Orchestrator()
    user_id = "cli-user"
    session_id = "cli-session"

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
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
{%- endif %}
