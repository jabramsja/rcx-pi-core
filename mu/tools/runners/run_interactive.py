#!/usr/bin/env python3
"""
RCX Interactive Review - Conversational agent sessions with follow-up support.

This tool allows you to have a conversation with any agent, asking follow-up
questions about their findings. Agents maintain full context across turns.

Features:
- Interactive REPL for agent conversations
- Resume previous sessions
- Multi-agent handoff ("ask the adversary about this")
- Session persistence for later review

Usage:
    # Start interactive session with verifier
    python tools/runners/run_interactive.py verifier rcx_pi/selfhost/step_mu.py

    # Start with multiple files
    python tools/runners/run_interactive.py adversary rcx_pi/selfhost/

    # Resume a previous session
    python tools/runners/run_interactive.py --resume <session_id>

    # List recent sessions
    python tools/runners/run_interactive.py --list

Commands during session:
    /switch <agent>  - Switch to different agent (keeps context)
    /files           - Show current files being reviewed
    /add <file>      - Add file to review scope
    /save            - Save session for later
    /exit            - End session
"""

import sys
import os
import json
import asyncio
import argparse
import subprocess
import readline  # For input history
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict

# Ensure repo root is on sys.path for direct script invocation
_tools_dir = Path(__file__).resolve().parent
if str(_tools_dir.parent.parent) not in sys.path:
    sys.path.insert(0, str(_tools_dir.parent.parent))

from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

from tools.runners.agent_runner_common import sanitize_files
from tools.runners.shared_agent_utils import (
    SUPPORTED_AGENT_MODELS,
    build_sdk_options,
    extract_text_from_message,
    load_agent_prompt_with_contract,
    resolve_agent_model,
    validate_compliance,
)


# =============================================================================
# Session Management
# =============================================================================

SESSIONS_DIR = Path(".claude/sessions")


@dataclass
class Session:
    """Represents an interactive review session."""
    id: str
    agent: str
    files: list[str]
    started: str
    messages: list[dict]
    sdk_session_id: str | None = None


def _validate_session_id(session_id: str) -> bool:
    """Validate session ID to prevent path traversal.

    Security: Only allow alphanumeric and underscore characters.
    """
    import re
    return bool(re.match(r'^[a-zA-Z0-9_]+$', session_id)) and len(session_id) <= 50


def load_session(session_id: str) -> Session | None:
    """Load a session from disk."""
    # Security: Validate session ID to prevent path traversal
    if not _validate_session_id(session_id):
        return None
    path = SESSIONS_DIR / f"{session_id}.json"
    # Security: Verify resolved path is within SESSIONS_DIR
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(SESSIONS_DIR.resolve()):
            return None
    except (OSError, ValueError):
        return None
    if path.exists():
        data = json.loads(path.read_text())
        return Session(**data)
    return None


def save_session(session: Session):
    """Save a session to disk."""
    # Security: Validate session ID to prevent path traversal
    if not _validate_session_id(session.id):
        raise ValueError(f"Invalid session ID: {session.id}")
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session.id}.json"
    # Security: Verify resolved path is within SESSIONS_DIR
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(SESSIONS_DIR.resolve()):
            raise ValueError(f"Path traversal attempt detected: {session.id}")
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid session path: {e}")
    path.write_text(json.dumps(asdict(session), indent=2))


def list_sessions() -> list[Session]:
    """List all saved sessions."""
    sessions = []
    if SESSIONS_DIR.exists():
        for path in SESSIONS_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                sessions.append(Session(**data))
            except Exception:
                pass
    return sorted(sessions, key=lambda s: s.started, reverse=True)


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# =============================================================================
# Agent Definitions
# =============================================================================

AVAILABLE_AGENTS = [
    "verifier", "adversary", "expert", "structural-proof",
    "grounding", "fuzzer", "translator", "visualizer", "advisor"
]


def create_agent_definition(agent_name: str, model_override: str | None = None) -> AgentDefinition:
    """Create an agent definition for interactive use."""
    model = resolve_agent_model(agent_name, model_override)

    return AgentDefinition(
        description=f"RCX {agent_name} agent for interactive review",
        prompt=load_agent_prompt_with_contract(agent_name),
        tools=["Read", "Grep", "Glob"],
        model=model
    )


# =============================================================================
# Interactive Session
# =============================================================================

class InteractiveSession:
    """Manages an interactive conversation with an agent."""

    def __init__(
        self,
        agent_name: str,
        files: list[str],
        session: Session | None = None,
        model_override: str | None = None,
    ):
        self.agent_name = agent_name
        self.files = files
        self.model_override = model_override
        self.session = session or Session(
            id=generate_session_id(),
            agent=agent_name,
            files=files,
            started=datetime.now().isoformat(),
            messages=[],
        )
        self.sdk_session_id = session.sdk_session_id if session else None

    def _build_initial_prompt(self) -> str:
        """Build the initial prompt for the agent."""
        file_list = ", ".join(sanitize_files(self.files))
        return f"""You are the RCX {self.agent_name.replace('-', ' ').title()} Agent in INTERACTIVE mode.

{load_agent_prompt_with_contract(self.agent_name)}

---

You are reviewing these files: {file_list}

This is an INTERACTIVE session. The user will ask follow-up questions.
Be conversational but precise. Cite FILE:LINE for all claims.

Start by giving a brief overview of what you see in these files.
"""

    async def send_message(self, user_message: str) -> str:
        """Send a message to the agent and get a response."""

        # Build prompt
        if not self.session.messages:
            # First message - include initial prompt
            prompt = self._build_initial_prompt() + f"\n\nUser: {user_message}"
        else:
            prompt = user_message

        # Prepare options
        options = build_sdk_options(
            ClaudeAgentOptions,
            allowed_tools=["Read", "Grep", "Glob"],
            max_turns=15,
            model=resolve_agent_model(self.agent_name, self.model_override),
            require_model_kwarg=True,
        )

        # Add resume if we have a session ID
        if self.sdk_session_id:
            options.resume = self.sdk_session_id

        result_text = ""
        fragments: list[str] = []
        new_session_id = None

        async for message in query(prompt=prompt, options=options):
            # Capture session ID for resumption
            if hasattr(message, 'session_id'):
                new_session_id = message.session_id

            extracted = extract_text_from_message(message)
            if extracted:
                fragments.append(extracted)

            if hasattr(message, 'result') and message.result:
                result_text = message.result

        if not result_text and fragments:
            result_text = "\n".join(dict.fromkeys(fragments))

        # Update session
        if new_session_id:
            self.sdk_session_id = new_session_id
            self.session.sdk_session_id = new_session_id

        self.session.messages.append({"role": "user", "content": user_message})
        self.session.messages.append({"role": "assistant", "content": result_text})

        # Compliance validation (shared_agent_utils returns 3-tuple, warn but don't block in interactive mode)
        is_compliant, error, _ = validate_compliance(result_text)
        if not is_compliant:
            result_text += f"\n\n⚠️ COMPLIANCE WARNING: {error}"

        return result_text

    def switch_agent(self, new_agent: str):
        """Switch to a different agent while keeping context."""
        if new_agent not in AVAILABLE_AGENTS:
            raise ValueError(f"Unknown agent: {new_agent}. Available: {', '.join(AVAILABLE_AGENTS)}")

        self.agent_name = new_agent
        self.session.agent = new_agent
        # Note: SDK session continues, but we'll re-prompt with new agent identity

    def add_file(self, file_path: str):
        """Add a file to the review scope."""
        if file_path not in self.files:
            self.files.append(file_path)
            self.session.files = self.files

    def save(self):
        """Save the session for later resumption."""
        save_session(self.session)
        return self.session.id


# =============================================================================
# REPL
# =============================================================================

def print_header(session: InteractiveSession):
    """Print session header."""
    print("\n" + "=" * 60)
    print(f"RCX INTERACTIVE REVIEW")
    print(f"=" * 60)
    print(f"Agent:   {session.agent_name}")
    print(f"Files:   {', '.join(session.files[:3])}")
    if len(session.files) > 3:
        print(f"         ... and {len(session.files) - 3} more")
    print(f"Session: {session.session.id}")
    print(f"=" * 60)
    print("\nCommands: /switch <agent>, /files, /add <file>, /save, /exit")
    print("Type your question or command:\n")


async def run_repl(session: InteractiveSession):
    """Run the interactive REPL."""
    print_header(session)

    # Initial analysis
    print(f"🤖 {session.agent_name}: Analyzing files...\n")
    response = await session.send_message("Begin your analysis.")
    print(f"\n{response}\n")

    while True:
        try:
            user_input = input(f"You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            parts = user_input[1:].split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "exit" or cmd == "quit":
                print("\nSession ended.")
                break

            elif cmd == "save":
                session_id = session.save()
                print(f"\n✅ Session saved: {session_id}")
                print(f"   Resume with: python tools/runners/run_interactive.py --resume {session_id}\n")

            elif cmd == "files":
                print(f"\nFiles in scope:")
                for f in session.files:
                    print(f"  - {f}")
                print()

            elif cmd == "add" and arg:
                session.add_file(arg)
                print(f"\n✅ Added: {arg}\n")

            elif cmd == "switch" and arg:
                try:
                    old_agent = session.agent_name
                    session.switch_agent(arg)
                    print(f"\n🔄 Switched from {old_agent} to {arg}")
                    print(f"🤖 {arg}: I'm now reviewing as the {arg} agent. What would you like me to look at?\n")
                except ValueError as e:
                    print(f"\n❌ {e}\n")

            else:
                print("\nUnknown command. Available: /switch, /files, /add, /save, /exit\n")

            continue

        # Regular message
        print(f"\n🤖 {session.agent_name}: ", end="", flush=True)
        response = await session.send_message(user_input)
        print(f"\n{response}\n")


# =============================================================================
# Main
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="RCX Interactive Review - Conversational agent sessions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/runners/run_interactive.py verifier rcx_pi/selfhost/step_mu.py
  python tools/runners/run_interactive.py adversary rcx_pi/selfhost/
  python tools/runners/run_interactive.py --resume 20240201_143052
  python tools/runners/run_interactive.py --list

Available agents:
  verifier, adversary, expert, structural-proof, grounding,
  fuzzer, translator, visualizer, advisor
"""
    )

    parser.add_argument("agent", nargs="?", help="Agent to use")
    parser.add_argument("files", nargs="*", help="Files to review")
    parser.add_argument("--resume", metavar="SESSION_ID", help="Resume a previous session")
    parser.add_argument("--list", action="store_true", help="List saved sessions")
    parser.add_argument(
        "--model",
        choices=sorted(SUPPORTED_AGENT_MODELS),
        help="Override model for interactive agent sessions",
    )

    args = parser.parse_args()

    # List sessions
    if args.list:
        sessions = list_sessions()
        if not sessions:
            print("No saved sessions.")
        else:
            print("\nSaved Sessions:")
            print("-" * 60)
            for s in sessions[:10]:
                msg_count = len(s.messages)
                print(f"  {s.id}  {s.agent:15}  {msg_count} messages  {s.started[:16]}")
            print("-" * 60)
            print(f"Resume with: python tools/runners/run_interactive.py --resume <SESSION_ID>")
        return

    # Resume session
    if args.resume:
        session_data = load_session(args.resume)
        if not session_data:
            print(f"Session not found: {args.resume}")
            sys.exit(1)
        session = InteractiveSession(
            agent_name=session_data.agent,
            files=session_data.files,
            session=session_data,
            model_override=args.model,
        )
        print(f"\n📂 Resuming session {args.resume}")
        await run_repl(session)
        return

    # New session
    if not args.agent or not args.files:
        parser.print_help()
        print("\nError: specify agent and files, or use --resume/--list")
        sys.exit(1)

    if args.agent not in AVAILABLE_AGENTS:
        print(f"Unknown agent: {args.agent}")
        print(f"Available: {', '.join(AVAILABLE_AGENTS)}")
        sys.exit(1)

    session = InteractiveSession(
        agent_name=args.agent,
        files=args.files,
        model_override=args.model,
    )
    await run_repl(session)

    # Auto-save on exit
    session_id = session.save()
    print(f"\n💾 Session auto-saved: {session_id}")


if __name__ == "__main__":
    asyncio.run(main())
