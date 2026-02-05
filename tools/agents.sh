#!/usr/bin/env bash
# RCX Agent System - Quick Reference
#
# Usage: ./tools/agents.sh [command]

set -euo pipefail

show_help() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════════════════════╗
║                          RCX AGENT SYSTEM                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ORCHESTRATORS (run multiple agents)                                         ║
║  ───────────────────────────────────                                         ║
║  python tools/run_review.py <files>           Full parallel review           ║
║  python tools/run_review.py <files> --quick   4 core agents only             ║
║  python tools/run_review.py --pr              Review current PR diff         ║
║  python tools/run_review.py <files> --founder Include translator/visualizer ║
║                                                                              ║
║  python tools/run_ci_review.py --pr-number 123   CI/CD review                ║
║  python tools/run_interactive.py verifier <files> Interactive session        ║
║                                                                              ║
║  INDIVIDUAL AGENTS (with compliance validation)                              ║
║  ──────────────────────────────────────────────                              ║
║  python tools/run_verifier.py <files>         North Star compliance          ║
║  python tools/run_adversary.py <files>        Security/attack vectors        ║
║  python tools/run_expert.py <files>           Complexity review              ║
║  python tools/run_structural_proof.py "claim" Verify structural claims       ║
║  python tools/run_grounding.py <files>        Test coverage verification     ║
║  python tools/run_fuzzer.py <files>           Property-based testing         ║
║  python tools/run_translator.py <files>       Plain English explanation      ║
║  python tools/run_visualizer.py <files>       Mermaid diagrams               ║
║  python tools/run_advisor.py "problem"        Strategic advice               ║
║                                                                              ║
║  INTERACTIVE MODE                                                            ║
║  ────────────────                                                            ║
║  python tools/run_interactive.py verifier <files>   Start session            ║
║  python tools/run_interactive.py --list             List saved sessions      ║
║  python tools/run_interactive.py --resume <id>      Resume session           ║
║                                                                              ║
║  Commands in interactive mode:                                               ║
║    /switch <agent>  - Switch to different agent                              ║
║    /files           - Show files in scope                                    ║
║    /add <file>      - Add file to scope                                      ║
║    /save            - Save session                                           ║
║    /exit            - End session                                            ║
║                                                                              ║
║  EXIT CODES                                                                  ║
║  ──────────                                                                  ║
║  0 = Pass           1 = Fail (hard gate)                                     ║
║  2 = Warnings       3 = Compliance failure                                   ║
║                                                                              ║
║  DEPTH LEVELS (for run_review.py)                                            ║
║  ────────────────────────────────                                            ║
║  quick   = verifier, adversary, expert, structural-proof (4 agents)          ║
║  full    = + grounding, fuzzer (6 agents)                                    ║
║  founder = + translator, visualizer (8 agents)                               ║
║  all     = + advisor (9 agents)                                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
EOF
}

case "${1:-help}" in
    help|-h|--help)
        show_help
        ;;
    list)
        echo "Available agent runners:"
        ls -1 tools/run_*.py | xargs -I{} basename {} .py | sed 's/run_/  /'
        ;;
    *)
        show_help
        ;;
esac
