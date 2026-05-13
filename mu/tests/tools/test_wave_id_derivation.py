from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from tests.repo_root import REPO_ROOT


SCRIPT = REPO_ROOT / "tools" / "checks" / "derive_wave_id.sh"


@pytest.mark.skipif(os.name == "nt", reason="bash script test")
class TestWaveIdDerivation:
    def _init_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "checkout", "-b", "dev"], cwd=repo, check=True, capture_output=True)
        (repo / "TASKS.md").write_text("## NOW\n\n## NEXT\n\n", encoding="utf-8")
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "base"], cwd=repo, check=True, capture_output=True)
        return repo

    def _derive_flag(self, repo: Path, branch: str, mode: str, value: str) -> str:
        cmd = (
            f"source '{SCRIPT}' '{branch}' {mode} '{value}' >/dev/null 2>&1; "
            "printf '%s' \"$WAVE_ID_FLAG\""
        )
        result = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=20,
            check=True,
        )
        return result.stdout.strip()

    def _derive_flag_legacy_range(self, repo: Path, branch: str, value: str) -> str:
        cmd = (
            f"source '{SCRIPT}' '{branch}' '{value}' >/dev/null 2>&1; "
            "printf '%s' \"$WAVE_ID_FLAG\""
        )
        result = subprocess.run(
            ["bash", "-lc", cmd],
            cwd=repo,
            text=True,
            capture_output=True,
            timeout=20,
            check=True,
        )
        return result.stdout.strip()

    def test_range_mode_normalizes_restart_branch_suffix_to_canonical_wave_id(
        self, tmp_path: Path
    ) -> None:
        repo = self._init_repo(tmp_path)
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- Tracker sync note (2026-04-21, test-wave): **TEST.** "
            "Class: L4_ENABLER. target_gate_id: G8. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave.json. "
            "indicator_collection_command: python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id test-wave. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "tracker"], cwd=repo, check=True, capture_output=True)

        flag = self._derive_flag(
            repo,
            "jabramsja/test-wave-restart-2026-04-21",
            "--range",
            "HEAD~1...HEAD",
        )
        assert flag == "--wave-id=test-wave"

    def test_staged_mode_prefers_exact_restart_wave_id_when_tracker_note_matches(
        self, tmp_path: Path
    ) -> None:
        repo = self._init_repo(tmp_path)
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- Tracker sync note (2026-04-21, test-wave): **TEST.** "
            "Class: L4_STRUCTURAL. target_gate_id: G8. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave.json. "
            "indicator_collection_command: python3 tools/checks/enforce_l4_execution_contract.py --range origin/dev...HEAD --wave-id test-wave. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n"
            "- Tracker sync note (2026-04-21, test-wave-restart-2026-04-21): **TEST.** "
            "Class: L4_ENABLER. target_gate_id: G8. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave-restart-2026-04-21.json. "
            "indicator_collection_command: python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id test-wave-restart-2026-04-21. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, check=True)

        flag = self._derive_flag(
            repo,
            "jabramsja/test-wave-restart-2026-04-21",
            "--staged",
            "",
        )
        assert flag == "--wave-id=test-wave-restart-2026-04-21"

    def test_range_mode_uses_exact_branch_suffix_when_tracker_note_matches(
        self, tmp_path: Path
    ) -> None:
        repo = self._init_repo(tmp_path)
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- Tracker sync note (2026-04-21, test-wave): **TEST.** "
            "Class: L4_ENABLER. target_gate_id: G8. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave.json. "
            "indicator_collection_command: python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id test-wave. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "tracker"], cwd=repo, check=True, capture_output=True)

        flag = self._derive_flag(
            repo,
            "jabramsja/test-wave",
            "--range",
            "HEAD~1...HEAD",
        )
        assert flag == "--wave-id=test-wave"

    def test_legacy_two_arg_range_call_uses_exact_branch_suffix_when_tracker_note_matches(
        self, tmp_path: Path
    ) -> None:
        repo = self._init_repo(tmp_path)
        (repo / "TASKS.md").write_text(
            "## NOW\n\n## NEXT\n\n"
            "- Tracker sync note (2026-04-21, test-wave): **TEST.** "
            "Class: L4_STRUCTURAL. target_gate_id: G8. "
            "indicator_artifact_ref: reports/l4_wave_indicators/test-wave.json. "
            "indicator_collection_command: python3 tools/checks/enforce_l4_execution_contract.py --staged --wave-id test-wave. "
            "bootstrap_endgame_policy: SUBSTRATE_INDEPENDENT_MINIMAL_BOOTSTRAP. "
            "boot0_track_id: V1. boot0_progress_state: HOLD.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "TASKS.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "tracker"], cwd=repo, check=True, capture_output=True)

        flag = self._derive_flag_legacy_range(
            repo,
            "jabramsja/test-wave",
            "HEAD~1...HEAD",
        )
        assert flag == "--wave-id=test-wave"
