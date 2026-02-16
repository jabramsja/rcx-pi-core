import os


def test_goldens_update_requires_explicit_ack():
    update = os.getenv("RCX_UPDATE_GOLDENS", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if not update:
        return

    ack = os.getenv("RCX_ACK_GOLDEN_UPDATE", "").strip()
    assert ack == "YES", (
        "RCX_UPDATE_GOLDENS enabled without explicit acknowledgement.\n"
        "To intentionally update goldens:\n"
        "  RCX_UPDATE_GOLDENS=1 RCX_ACK_GOLDEN_UPDATE=YES pytest -q tests/test_semantic_goldens.py"
    )
