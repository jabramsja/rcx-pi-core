# RCX Golden Snapshots

Canonical semantic trace snapshots.

Normal runs compare against committed JSON.
Updates require explicit acknowledgement.

To update intentionally:
RCX_UPDATE_GOLDENS=1 RCX_ACK_GOLDEN_UPDATE=YES pytest -q tests/test_semantic_goldens.py
