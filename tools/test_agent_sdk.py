#!/usr/bin/env python3
"""
Test that the Claude Agent SDK actually works.
This is NOT pretend - it runs a real agent query.
"""

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions


async def test_basic_query():
    """Test that we can run a basic agent query."""
    print("Testing basic agent query...")

    async for message in query(
        prompt="What is 2 + 2? Answer with just the number.",
        options=ClaudeAgentOptions(
            max_turns=1,
        )
    ):
        print(f"Message type: {type(message).__name__}")
        if hasattr(message, 'content'):
            print(f"Content: {message.content}")
        if hasattr(message, 'result'):
            print(f"Result: {message.result}")

    print("Basic query test complete.")


async def test_with_tools():
    """Test that we can run an agent with read-only tools."""
    print("\nTesting agent with tools...")

    async for message in query(
        prompt="Read the file .claude/agents/verifier.md and tell me its name field from the YAML frontmatter.",
        options=ClaudeAgentOptions(
            allowed_tools=["Read"],
            max_turns=3,
        )
    ):
        print(f"Message type: {type(message).__name__}")
        if hasattr(message, 'content'):
            print(f"Content: {message.content[:200] if message.content else 'None'}...")
        if hasattr(message, 'result'):
            print(f"Result: {message.result[:200] if message.result else 'None'}...")

    print("Tools test complete.")


async def main():
    print("=" * 60)
    print("AGENT SDK TEST - This is real, not pretend")
    print("=" * 60)

    try:
        await test_basic_query()
        await test_with_tools()
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED - Agent SDK is working")
        print("=" * 60)
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        print("\nThis means the Agent SDK is NOT properly configured.")
        raise


if __name__ == "__main__":
    anyio.run(main)
