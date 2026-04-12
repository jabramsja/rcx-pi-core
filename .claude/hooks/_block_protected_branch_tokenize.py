#!/usr/bin/env python3
"""Block-protected-branch hook tokenizer helper.

Implements a bash-aware state-machine lexer that correctly handles
POSIX word-boundary comments, single-quoted strings, double-quoted
strings, unquoted backslash escapes, and line continuations.

Reads stdin; emits NUL-terminated tokens to stdout on success
(exit 0); exits 2 on any parser error, printing one diagnostic line
to stderr. Tokens are NUL-terminated (not newline-terminated)
because a shell word may contain embedded newlines (e.g. a
single-quoted multiline string); NUL is the only byte that cannot
appear inside a POSIX shell command string.

Fail-closed contract: on error, emits NO tokens to stdout - the hook
reads stdout as the token stream, and a partial stream must never be
treated as a successful tokenization.

Contract: reports/control_plane/block_protected_branch_lexer_2026-04-11.md,
Work Item 1.
"""

import sys


# Lexer states.
UNQUOTED = "UNQUOTED"
SINGLE_QUOTED = "SINGLE_QUOTED"
DOUBLE_QUOTED = "DOUBLE_QUOTED"
ESCAPE_UNQUOTED = "ESCAPE_UNQUOTED"
ESCAPE_DOUBLE = "ESCAPE_DOUBLE"
COMMENT = "COMMENT"

# Whitespace that terminates unquoted words (emits a word boundary).
_WHITESPACE = frozenset(" \t\n\r")

# Unquoted shell operators that also act as word boundaries for our
# purposes. These match the set specified in the lexer contract:
# `;`, `&`, `|`, `(`, `)`.
_WORD_BOUNDARY_OPS = frozenset(";&|()")

# Chars after `\` inside DOUBLE_QUOTED that drop the backslash. Per the
# minimal contract: `"`, `\`, `$`, backtick, and newline. For any other
# char, BOTH the backslash and the char are kept literally.
_DOUBLE_ESCAPE_DROP = frozenset('"\\$`\n')


def tokenize(text):
    """Run the state machine over *text* and return a list of tokens.

    Raises ValueError on any parser error:
      - unclosed single quote
      - unclosed double quote
      - trailing backslash at end of input
    """
    tokens = []
    buf = []  # current token buffer (list of single-char strings)
    state = UNQUOTED
    at_word_boundary = True  # True at start-of-input per the contract

    def emit():
        # Emit the current buffer as a token, if any.
        if buf:
            tokens.append("".join(buf))
            buf.clear()

    for ch in text:
        if state == UNQUOTED:
            if ch in _WHITESPACE or ch in _WORD_BOUNDARY_OPS:
                emit()
                at_word_boundary = True
            elif ch == "'":
                state = SINGLE_QUOTED
                at_word_boundary = False
            elif ch == '"':
                state = DOUBLE_QUOTED
                at_word_boundary = False
            elif ch == "\\":
                state = ESCAPE_UNQUOTED
                at_word_boundary = False
            elif ch == "#":
                if at_word_boundary:
                    # Start of a comment - discard until newline.
                    # Do NOT append `#`.
                    state = COMMENT
                else:
                    # `#` embedded in a word is literal.
                    buf.append(ch)
                    # at_word_boundary stays False.
            else:
                buf.append(ch)
                at_word_boundary = False

        elif state == SINGLE_QUOTED:
            if ch == "'":
                # Closing quote - quotes are invisible to the token;
                # do NOT set at_word_boundary = True.
                state = UNQUOTED
            else:
                # All other chars (including `\`, `#`, newline,
                # whitespace) are literal inside single quotes.
                buf.append(ch)

        elif state == DOUBLE_QUOTED:
            if ch == '"':
                # Closing quote - do NOT set at_word_boundary = True.
                state = UNQUOTED
            elif ch == "\\":
                state = ESCAPE_DOUBLE
            else:
                buf.append(ch)

        elif state == ESCAPE_UNQUOTED:
            if ch == "\n":
                # Line continuation: drop both `\` and newline; do NOT
                # restore at_word_boundary = True (per the contract).
                state = UNQUOTED
            else:
                # Append the escaped char literally (drop the `\`).
                buf.append(ch)
                state = UNQUOTED
                # at_word_boundary stays False.

        elif state == ESCAPE_DOUBLE:
            if ch in _DOUBLE_ESCAPE_DROP:
                # Drop the backslash, keep the char literally.
                buf.append(ch)
            else:
                # Keep BOTH the backslash and the char literally.
                buf.append("\\")
                buf.append(ch)
            state = DOUBLE_QUOTED

        elif state == COMMENT:
            if ch == "\n":
                # End of comment line. No token is pending because
                # at_word_boundary was True on entry (precondition for
                # entering COMMENT). emit() here is a no-op but kept
                # for belt-and-braces.
                emit()
                at_word_boundary = True
                state = UNQUOTED
            # else: discard.

        else:
            # Unreachable - every state is handled above.
            raise ValueError(f"internal error: unknown state {state!r}")

    # End-of-input handling.
    if state == UNQUOTED or state == COMMENT:
        emit()
        return tokens
    if state == SINGLE_QUOTED:
        raise ValueError("unclosed single quote")
    if state == DOUBLE_QUOTED:
        raise ValueError("unclosed double quote")
    if state == ESCAPE_UNQUOTED or state == ESCAPE_DOUBLE:
        raise ValueError("trailing backslash at end of input")
    # Unreachable.
    raise ValueError(f"internal error: terminal state {state!r}")


def main():
    try:
        text = sys.stdin.read()
        tokens = tokenize(text)
    except ValueError as e:
        # Parser error: fail-closed. No tokens on stdout.
        print(f"tokenizer parser error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        # Any unexpected exception (e.g. UnicodeDecodeError on binary
        # stdin) also fails closed.
        print(
            f"tokenizer internal error: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Success path: emit each token NUL-terminated to stdout. NUL
    # (not newline) is used because a shell word may legitimately
    # contain embedded newlines (e.g. a single-quoted multiline
    # string); delimiting on newline would fragment such a token
    # across multiple `read -r` iterations in the consumer, which
    # could fabricate a spurious `git`/`commit` subcommand match.
    # NUL is the only byte that cannot appear inside a POSIX shell
    # command string, so it is the only safe token delimiter.
    out = sys.stdout
    for tok in tokens:
        out.write(tok)
        out.write("\0")
    sys.exit(0)


if __name__ == "__main__":
    main()
