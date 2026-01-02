from rcx_pi import VOID


def motif_to_int(m):
    """Interpret a Motif Peano number as an int, or None if not a pure number."""
    # Zero
    if not isinstance(m, type(VOID)):
        return None
    if m.is_zero_pure():
        return 0
    # succ-chain
    count = 0
    cur = m
    while cur.is_successor_pure():
        count += 1
        cur = cur.head()
        if not isinstance(cur, type(VOID)):
            return None
    if cur.is_zero_pure():
        return count
    return None
