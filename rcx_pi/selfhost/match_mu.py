"""
Match as Mu Projections - Phase 4a Self-Hosting

This module implements pattern matching using Mu projections instead of
Python recursion. It achieves parity with eval_seed.match() but uses
the kernel loop for iteration.

See docs/core/SelfHosting.v0.md for design.
"""

from __future__ import annotations

from .mu_type import Mu, assert_mu, mu_equal
from .eval_seed import NO_MATCH, _NoMatch, step
from .kernel import get_step_budget
from .seed_integrity import get_seeds_dir  # load_verified_seed used via factory
from .classify_mu import classify_linked_list
from .projection_loader import make_projection_loader
from .projection_runner import make_projection_runner

# =============================================================================
# Type Tag Validation (Phase 6c Security)
# =============================================================================

# Whitelist of valid _type values - prevents injection of unexpected types
VALID_TYPE_TAGS = frozenset({"list", "dict"})  # AST_OK: constant whitelist


def validate_type_tag(tag: str, context: str = "") -> None:
    """
    Validate that a type tag is from the allowed whitelist.

    Args:
        tag: The _type value to validate.
        context: Context for error message.

    Raises:
        ValueError: If tag is not in whitelist.
    """
    if tag not in VALID_TYPE_TAGS:
        ctx_msg = f" in {context}" if context else ""
        raise ValueError(
            f"Invalid type tag '{tag}'{ctx_msg}. "
            f"Valid values: {sorted(VALID_TYPE_TAGS)}"
        )


# =============================================================================
# Projection Loading (consolidated via factory)
# =============================================================================

load_match_projections, clear_projection_cache = make_projection_loader("match.v1.json")


# =============================================================================
# Variable Name Validation
# =============================================================================


def _check_empty_var_names(value: Mu, context: str) -> None:
    """
    Check for empty variable names in a Mu structure (iterative).

    This ensures parity with eval_seed.py which rejects empty var names.
    Uses explicit stack instead of recursion (Phase 6d).

    Args:
        value: The Mu value to check.
        context: Context for error message (e.g., "pattern", "body").

    Raises:
        ValueError: If an empty variable name is found.
    """
    # Iterative traversal with explicit stack
    stack: list[Mu] = [value]

    while stack:
        current = stack.pop()

        if isinstance(current, dict):  # isinstance at boundary is scaffolding
            # Check if this is a variable site with empty name
            keys = set(current.keys())  # AST_OK: key comparison
            if keys == {"var"} and isinstance(current.get("var"), str):
                if current["var"] == "":
                    raise ValueError(f"Variable name cannot be empty in {context}: {{'var': ''}}")
            # Add dict values to stack for processing
            stack.extend(current.values())
        elif isinstance(current, list):  # isinstance at boundary is scaffolding
            # Add list items to stack for processing
            stack.extend(current)


# =============================================================================
# Dict Normalization
# =============================================================================


def normalize_for_match(value: Mu) -> Mu:
    """
    Normalize a Mu value for structural matching.

    Converts dicts and lists to type-tagged head/tail linked lists so they can
    be matched structurally via head/tail patterns and denormalized unambiguously.

    Dict: {"a": 1} -> {"_type": "dict", "head": {"head": "a", "tail": ...}, "tail": null}
    List: [1, 2] -> {"_type": "list", "head": 1, "tail": {"head": 2, "tail": null}}

    The _type tag on the root node distinguishes lists from dicts. This resolves
    the ambiguity where [["a", 1]] and {"a": 1} would otherwise normalize to
    identical structures.

    Note: Empty collections ({} and []) both normalize to null (no type tag needed).

    This function uses iterative traversal with an explicit stack (Phase 6c).
    The isinstance() checks at the boundary are scaffolding debt, not semantic debt.

    Args:
        value: The Mu value to normalize.

    Raises:
        ValueError: If circular reference detected.
    """
    # Simple cases - no iteration needed
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict) and set(value.keys()) == {"var"} and isinstance(value.get("var"), str):
        return value

    # Iterative normalization using explicit stack (Phase 6c)
    # Stack items: (operation, *data)
    # Operations:
    #   ("eval", val) - evaluate val and store result
    #   ("leave", val_id) - remove val_id from path (exiting this node)
    #   ("list_tail", elem_idx, elems_normalized, original_list) - building list
    #   ("dict_tail", key_idx, keys, kvs_normalized, original_dict) - building dict
    #   ("ht_head", tail_val) - head done, now process tail
    #   ("ht_combine", head_normalized) - combine head and tail results

    # Path-based cycle detection: track current ancestors, not all visited nodes.
    # This allows shared references (DAGs) while detecting true back-edges (cycles).
    path: set[int] = set()
    stack: list = [("eval", value)]
    result: Mu = None

    while stack:
        item = stack.pop()
        op = item[0]

        if op == "leave":
            # Exiting this node - remove from path
            path.discard(item[1])
            continue

        if op == "eval":
            val = item[1]

            # Simple cases
            if val is None or isinstance(val, (bool, int, float, str)):
                result = val
                continue
            if isinstance(val, dict) and set(val.keys()) == {"var"} and isinstance(val.get("var"), str):
                result = val
                continue

            # Cycle detection for compound types - check if on current path
            if isinstance(val, (list, dict)):
                val_id = id(val)
                if val_id in path:
                    raise ValueError("Circular reference detected in normalize_for_match")
                path.add(val_id)
                # Push leave marker to remove from path when done with children
                stack.append(("leave", val_id))

            if isinstance(val, list):
                if len(val) == 0:
                    result = None
                    continue
                # Start building list from the end (last element first)
                stack.append(("list_tail", len(val) - 1, [], val))
                stack.append(("eval", val[-1]))
                continue

            if isinstance(val, dict):
                keys = set(val.keys())

                # Type-tagged structure - preserve _type, normalize head/tail
                if keys == {"_type", "head", "tail"}:  # AST_OK: key comparison
                    stack.append(("ht_typed", val["_type"], val["tail"]))
                    stack.append(("eval", val["head"]))
                    continue

                if keys == {"head", "tail"}:
                    # Already head/tail structure - normalize both parts
                    # Process head first, then tail, then combine
                    stack.append(("ht_head", val["tail"]))
                    stack.append(("eval", val["head"]))
                    continue

                if len(keys) == 0:
                    result = None
                    continue

                # Regular dict - convert to sorted kv linked list
                keys = sorted(keys)
                # Start from last key (builds list in sorted order)
                stack.append(("dict_tail", len(keys) - 1, keys, [], val))
                stack.append(("eval", val[keys[-1]]))
                continue

        elif op == "ht_typed":
            # Type-tagged: head is done, now process tail (preserving _type)
            _type, tail_val = item[1], item[2]
            stack.append(("ht_typed_combine", _type, result))  # Save _type and head
            stack.append(("eval", tail_val))

        elif op == "ht_typed_combine":
            # Type-tagged: tail is done, combine with _type and head
            _type, head_normalized = item[1], item[2]
            result = {"_type": _type, "head": head_normalized, "tail": result}

        elif op == "ht_head":
            # Head is done (result contains head_normalized), now process tail
            tail_val = item[1]
            stack.append(("ht_combine", result))  # Save head result
            stack.append(("eval", tail_val))

        elif op == "ht_combine":
            # Tail is done (result contains tail_normalized), combine with head
            head_normalized = item[1]
            result = {"head": head_normalized, "tail": result}

        elif op == "list_tail":
            elem_idx, elems_normalized, original_list = item[1], item[2], item[3]
            # Add the just-computed result
            elems_normalized.append(result)

            if elem_idx == 0:
                # All elements processed - build linked list with type tag
                # Elements are in reverse order (last to first), which is correct
                # for building head/tail from end to beginning
                tail: Mu = None
                for elem in elems_normalized:
                    tail = {"head": elem, "tail": tail}
                # Add type tag to root node (fixes list/dict ambiguity)
                if tail is not None:
                    tail["_type"] = "list"
                result = tail
            else:
                # More elements to process
                stack.append(("list_tail", elem_idx - 1, elems_normalized, original_list))
                stack.append(("eval", original_list[elem_idx - 1]))

        elif op == "dict_tail":
            key_idx, keys, kvs_normalized, original_dict = item[1], item[2], item[3], item[4]
            # Build kv-pair for current key
            key = keys[key_idx]
            kv_pair: Mu = {"head": key, "tail": {"head": result, "tail": None}}
            kvs_normalized.append(kv_pair)

            if key_idx == 0:
                # All keys processed - build linked list of kv-pairs with type tag
                tail: Mu = None
                for kv in kvs_normalized:
                    tail = {"head": kv, "tail": tail}
                # Add type tag to root node (fixes list/dict ambiguity)
                if tail is not None:
                    tail["_type"] = "dict"
                result = tail
            else:
                # More keys to process
                stack.append(("dict_tail", key_idx - 1, keys, kvs_normalized, original_dict))
                stack.append(("eval", original_dict[keys[key_idx - 1]]))

    return result


def is_kv_pair_linked(value: Mu) -> bool:
    """
    Check if value is a key-value pair in linked list format.

    KV-pair format: {"head": key_string, "tail": {"head": value, "tail": null}}

    Note: This checks for the SPECIFIC kv-pair structure. A dict with
    head/tail keys but different structure is NOT classified as a kv-pair.
    """
    if not isinstance(value, dict):
        return False
    if set(value.keys()) != {"head", "tail"}:
        return False
    head = value.get("head")
    tail = value.get("tail")
    if not isinstance(head, str):
        return False
    if not isinstance(tail, dict):
        return False
    if set(tail.keys()) != {"head", "tail"}:
        return False
    if tail.get("tail") is not None:
        return False
    return True


def is_dict_linked_list(value: Mu) -> bool:
    """
    Check if value is a linked list encoding a dict (ALL elements are kv-pairs).

    Supports both type-tagged (Phase 6c) and legacy structures:
    - Type-tagged: {"_type": "dict", "head": ..., "tail": ...}
    - Legacy: {"head": ..., "tail": ...} where all heads are kv-pairs

    Includes cycle detection to prevent infinite loops on circular structures.
    """
    if not isinstance(value, dict):
        return False

    keys = set(value.keys())

    # Phase 6c: Type-tagged structures - check the type (with validation)
    if keys == {"_type", "head", "tail"}:  # AST_OK: key comparison
        _type = value.get("_type")
        # Validate if it's a string (non-string types just return False)
        if isinstance(_type, str) and _type in VALID_TYPE_TAGS:
            return _type == "dict"
        return False  # Invalid type tag - not a valid dict encoding

    # Legacy: head/tail without type tag
    if keys != {"head", "tail"}:
        return False

    # Check ALL elements are valid kv-pairs (with cycle detection)
    visited: set[int] = set()
    current = value
    while current is not None:
        node_id = id(current)
        if node_id in visited:
            return False  # Circular structure - not a valid dict encoding
        visited.add(node_id)

        if not isinstance(current, dict):
            return False
        if set(current.keys()) != {"head", "tail"}:
            return False
        if not is_kv_pair_linked(current["head"]):
            return False
        current = current["tail"]
    return True


def denormalize_from_match(value: Mu) -> Mu:
    """
    Convert normalized Mu back to regular Python structures.

    Reverses the normalization done by normalize_for_match. Uses the _type tag
    on the root node to determine if a linked list represents a list or dict.

    For legacy structures without _type tag, falls back to projection-based
    classification (classify_linked_list).

    Note: An empty linked list (null) denormalizes to None (not [] or {}).

    This function uses iterative traversal with an explicit stack (Phase 6c).
    The isinstance() checks at the boundary are scaffolding debt, not semantic debt.

    Args:
        value: The normalized Mu value to denormalize.

    Raises:
        ValueError: If circular reference detected.
    """
    # Simple cases - no iteration needed
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict) and set(value.keys()) == {"var"}:
        return value

    # Iterative denormalization using explicit stack (Phase 6c)
    # Stack items: (operation, *data)
    # Operations:
    #   ("eval", val) - evaluate val and store result
    #   ("leave", val_id) - remove val_id from path (exiting this node)
    #   ("finalize_list", result_list) - set result to the populated list
    #   ("finalize_dict", result_dict) - set result to the populated dict
    #   ("list_elem", result_list) - append result to result_list
    #   ("dict_kv", key, result_dict) - set result_dict[key] = result

    # Path-based cycle detection: track current ancestors, not all visited nodes.
    # This allows shared references (DAGs) while detecting true back-edges (cycles).
    path: set[int] = set()
    stack: list = [("eval", value)]
    result: Mu = None

    while stack:
        item = stack.pop()
        op = item[0]

        if op == "leave":
            # Exiting this node - remove from path
            path.discard(item[1])
            continue

        if op == "eval":
            val = item[1]

            # Simple cases
            if val is None or isinstance(val, (bool, int, float, str)):
                result = val
                continue
            if isinstance(val, dict) and set(val.keys()) == {"var"}:
                result = val
                continue

            # Cycle detection for compound types - check if on current path
            if isinstance(val, (list, dict)):
                val_id = id(val)
                if val_id in path:
                    raise ValueError("Circular reference detected in denormalize_from_match")
                path.add(val_id)
                # Push leave marker to remove from path when done with children
                stack.append(("leave", val_id))

            # Python list (from external sources - rare case)
            if isinstance(val, list):
                if len(val) == 0:
                    result = []
                    continue
                result_list: list = []
                # Push finalize first (will be processed last)
                stack.append(("finalize_list", result_list))
                # Push element processing in reverse order (last element pushed first)
                for elem in reversed(val):
                    stack.append(("list_elem", result_list))
                    stack.append(("eval", elem))
                continue

            # Dict
            if isinstance(val, dict):
                keys = set(val.keys())

                # Type-tagged linked list (Phase 6c: fixes list/dict ambiguity)
                if keys == {"_type", "head", "tail"}:  # AST_OK: key comparison
                    _type = val.get("_type")
                    # Validate type tag is from whitelist (security)
                    if isinstance(_type, str):
                        validate_type_tag(_type, "denormalize_from_match")
                    if _type == "dict":
                        # Dict encoding - extract all kv-pairs
                        result_dict: dict = {}
                        # Push finalize first (will be processed last)
                        stack.append(("finalize_dict", result_dict))

                        # Collect kv-pairs with cycle detection
                        kv_pairs: list = []
                        current = val
                        visited: set[int] = set()
                        while current is not None:
                            node_id = id(current)
                            if node_id in visited:
                                raise ValueError("Circular reference in linked list during denormalization")
                            visited.add(node_id)
                            if not isinstance(current, dict) or "head" not in current:
                                break
                            kv = current["head"]
                            key = kv["head"]
                            val_to_process = kv["tail"]["head"]
                            kv_pairs.append((key, val_to_process))
                            current = current.get("tail")

                        # Push processing in reverse order (last kv pushed first)
                        for key, val_to_process in reversed(kv_pairs):
                            stack.append(("dict_kv", key, result_dict))
                            stack.append(("eval", val_to_process))
                        continue

                    elif _type == "list":
                        # List encoding - extract all elements
                        result_list: list = []
                        # Push finalize first (will be processed last)
                        stack.append(("finalize_list", result_list))

                        # Collect elements with cycle detection
                        elements: list = []
                        current = val
                        visited: set[int] = set()
                        while current is not None:
                            node_id = id(current)
                            if node_id in visited:
                                raise ValueError("Circular reference in linked list during denormalization")
                            visited.add(node_id)
                            if not isinstance(current, dict) or "head" not in current:
                                break
                            elements.append(current["head"])
                            current = current.get("tail")

                        # Push processing in reverse order (last element pushed first)
                        for elem in reversed(elements):
                            stack.append(("list_elem", result_list))
                            stack.append(("eval", elem))
                        continue

                # Legacy head/tail linked list (no type tag)
                if keys == {"head", "tail"}:
                    # Phase 6b: Use Mu projection-based classification
                    if classify_linked_list(val) == "dict":
                        # Dict encoding - extract all kv-pairs
                        result_dict: dict = {}
                        # Push finalize first (will be processed last)
                        stack.append(("finalize_dict", result_dict))

                        # Collect kv-pairs with cycle detection
                        kv_pairs: list = []
                        current = val
                        visited: set[int] = set()
                        while current is not None:
                            node_id = id(current)
                            if node_id in visited:
                                raise ValueError("Circular reference in linked list during denormalization")
                            visited.add(node_id)
                            kv = current["head"]
                            key = kv["head"]
                            val_to_process = kv["tail"]["head"]
                            kv_pairs.append((key, val_to_process))
                            current = current["tail"]

                        # Push processing in reverse order (last kv pushed first)
                        for key, val_to_process in reversed(kv_pairs):
                            stack.append(("dict_kv", key, result_dict))
                            stack.append(("eval", val_to_process))
                        continue

                    else:
                        # List encoding - extract all elements
                        result_list: list = []
                        # Push finalize first (will be processed last)
                        stack.append(("finalize_list", result_list))

                        # Collect elements with cycle detection
                        elements: list = []
                        current = val
                        visited: set[int] = set()
                        while current is not None:
                            node_id = id(current)
                            if node_id in visited:
                                raise ValueError("Circular reference in linked list during denormalization")
                            visited.add(node_id)
                            elements.append(current["head"])
                            current = current["tail"]

                        # Push processing in reverse order (last element pushed first)
                        for elem in reversed(elements):
                            stack.append(("list_elem", result_list))
                            stack.append(("eval", elem))
                        continue

                # Regular dict (from external sources - rare case)
                if len(keys) == 0:
                    result = {}
                    continue
                result_dict: dict = {}
                # Push finalize first (will be processed last)
                stack.append(("finalize_dict", result_dict))
                # Push kv processing in reverse order
                for key in reversed(list(val.keys())):
                    stack.append(("dict_kv", key, result_dict))
                    stack.append(("eval", val[key]))
                continue

        elif op == "finalize_list":
            result = item[1]  # The now-populated list

        elif op == "finalize_dict":
            result = item[1]  # The now-populated dict

        elif op == "list_elem":
            result_list = item[1]
            result_list.append(result)

        elif op == "dict_kv":
            key, result_dict = item[1], item[2]
            result_dict[key] = result

    return result


# =============================================================================
# Bindings Conversion
# =============================================================================


def bindings_to_dict(linked: Mu) -> dict[str, Mu]:
    """
    Convert linked list bindings to Python dict.

    Linked format: {"name": "x", "value": 42, "rest": {...}} or null
    Dict format: {"x": 42, ...}

    Note: This is a boundary conversion function (Python API scaffolding),
    not semantic debt. The projections work on linked lists; this converts
    the result for Python callers.
    """
    result: dict[str, Mu] = {}
    current = linked
    while current is not None:
        if not isinstance(current, dict):  # isinstance at boundary is scaffolding
            raise ValueError(f"Invalid bindings structure: {current}")
        name = current.get("name")
        value = current.get("value")
        if name is None:
            raise ValueError(f"Binding missing 'name': {current}")
        result[name] = value
        current = current.get("rest")
    return result


def dict_to_bindings(d: dict[str, Mu]) -> Mu:
    """
    Convert Python dict to linked list bindings.

    Dict format: {"x": 42, ...}
    Linked format: {"name": "x", "value": 42, "rest": {...}} or null

    Note: This is a boundary conversion function (Python API scaffolding),
    not semantic debt. Python callers provide dicts; this converts to
    linked list format for projections. sorted() ensures determinism.
    """
    result: Mu = None
    # Use sorted keys for determinism (scaffolding for Python API boundary)
    for name in sorted(d.keys(), reverse=True):
        result = {"name": name, "value": d[name], "rest": result}
    return result


# =============================================================================
# Match Runner (consolidated via factory)
# =============================================================================

is_match_done, is_match_state, run_match_projections = make_projection_runner("match")


def match_mu(pattern: Mu, value: Mu) -> dict[str, Mu] | _NoMatch:
    """
    Match pattern against value using Mu projections.

    This is the parity function for eval_seed.match().

    Args:
        pattern: The pattern to match (Mu with possible var sites).
        value: The value to match against (Mu).

    Returns:
        Dict of bindings {"var_name": value} if match, NO_MATCH otherwise.
    """
    assert_mu(pattern, "match_mu.pattern")
    assert_mu(value, "match_mu.value")

    # Validate no empty variable names (parity with eval_seed.py)
    _check_empty_var_names(pattern, "pattern")

    # Normalize inputs to head/tail structures
    norm_pattern = normalize_for_match(pattern)
    norm_value = normalize_for_match(value)

    # Load projections
    projections = load_match_projections()

    # Wrap input in match request format
    initial = {"match": {"pattern": norm_pattern, "value": norm_value}}

    # Run projections
    final_state, steps, is_stall = run_match_projections(projections, initial)

    # Extract result
    if is_stall:
        # Stall means no projection matched = pattern didn't match
        return NO_MATCH

    if is_match_done(final_state):
        status = final_state.get("status")
        if status == "success":
            bindings = final_state.get("bindings")
            raw_dict = bindings_to_dict(bindings)
            # Denormalize the bound values back to regular Python structures
            return {k: denormalize_from_match(v) for k, v in raw_dict.items()}  # AST_OK: bootstrap
        else:
            # Explicit failure status
            return NO_MATCH

    # Unexpected state
    return NO_MATCH
