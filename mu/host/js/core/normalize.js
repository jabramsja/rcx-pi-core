'use strict';
/**
 * RCX Normalization: Convert JS values to linked-list format for kernel
 *
 * Depends on: core/constants.js, core/types.js
 */

const { MAX_DEPTH, MAX_DENORM_ITER, VALID_TYPE_TAGS, RcxError } = require('./constants');
const { isValidNumber, isVar, compareMuStringKeysByCodepoint } = require('./types');

/**
 * Check if object is EXACTLY a head/tail linked list node.
 * Strict check: must have exactly {head, tail} or {_type, head, tail}.
 */
function isLinkedListNode(obj) {
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    return false;
  }
  const keys = Object.keys(obj).sort();
  // Exactly {head, tail}
  if (keys.length === 2 && keys[0] === 'head' && keys[1] === 'tail') {
    return true;
  }
  // Exactly {_type, head, tail}
  if (keys.length === 3 && keys[0] === '_type' && keys[1] === 'head' && keys[2] === 'tail') {
    return true;
  }
  return false;
}

/**
 * Check if object is EXACTLY a typed empty sentinel.
 * Strict check: must have exactly {_type} with valid tag.
 */
function isTypedEmptySentinel(obj) {
  if (typeof obj !== 'object' || obj === null || Array.isArray(obj)) {
    return false;
  }
  const keys = Object.keys(obj);
  return keys.length === 1 && keys[0] === '_type' && VALID_TYPE_TAGS.has(obj._type);
}

/**
 * Classify a legacy (untyped) head/tail linked list as 'list' or 'dict'.
 *
 * PARITY: Matches Python classify_linked_list behavior.
 * Policy: "classify" - treat {head: X, tail: Y} as linked-list format.
 *
 * A linked list is classified as 'dict' if ALL elements are kv-pairs
 * with string keys. kv-pair format: {head: string_key, tail: {head: value, tail: null}}
 *
 * Otherwise classified as 'list' (including empty, primitives, circular).
 */
function classifyLegacyLinkedList(value) {
  // Non-object or null is list
  if (typeof value !== 'object' || value === null) {
    return 'list';
  }

  // Walk the list checking if all heads are valid kv-pairs with string keys
  const visited = new Set();
  let current = value;
  let depth = 0;

  while (current !== null && typeof current === 'object') {
    // Depth guard
    if (depth++ > MAX_DEPTH) {
      return 'list';
    }

    // Cycle detection: reject cyclic structures (parity with iterNormalizedDictPairs)
    if (visited.has(current)) {
      return 'list';
    }
    visited.add(current);

    const keys = Object.keys(current).sort();

    // Must be exactly {head, tail}
    if (keys.length !== 2 || keys[0] !== 'head' || keys[1] !== 'tail') {
      return 'list';
    }

    // Check if head is a valid kv-pair with string key and proper tail structure
    const head = current.head;
    if (typeof head === 'object' && head !== null) {
      const headKeys = Object.keys(head).sort();
      if (headKeys.length !== 2 || headKeys[0] !== 'head' || headKeys[1] !== 'tail') {
        return 'list';
      }

      const key = head.head;
      if (typeof key !== 'string') {
        return 'list';
      }

      // P2 fix: Validate tail structure is {head: value, tail: null}
      const kvTail = head.tail;
      if (typeof kvTail !== 'object' || kvTail === null) {
        return 'list';
      }
      const kvTailKeys = Object.keys(kvTail).sort();
      if (kvTailKeys.length !== 2 || kvTailKeys[0] !== 'head' || kvTailKeys[1] !== 'tail') {
        return 'list';
      }
      if (kvTail.tail !== null) {
        return 'list';
      }
    } else {
      return 'list';
    }

    current = current.tail;
  }

  return 'dict';
}

/**
 * Normalize a Mu value for structural matching.
 *
 * Converts dicts and lists to type-tagged head/tail linked lists:
 *   List: [1, 2] -> {"_type": "list", "head": 1, "tail": {"head": 2, "tail": null}}
 *   Dict: {"a": 1} -> {"_type": "dict", "head": {"head": "a", "tail": 1}, "tail": null}
 *
 * @host_recursion - recursive normalization
 * @host_iteration - for loop for array/dict conversion
 */
function normalize(value, _depth = 0) {
  // Depth guard
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
  }

  if (value === null) {
    return null;
  }

  // Reject invalid types (function, undefined, symbol)
  if (value === undefined) {
    throw new RcxError('input.malformed_normalized', 'undefined is not valid Mu');
  }
  if (typeof value === 'function') {
    throw new RcxError('input.malformed_normalized', 'Functions are not valid Mu');
  }
  if (typeof value === 'symbol') {
    throw new RcxError('input.malformed_normalized', 'Symbols are not valid Mu');
  }

  // Validate primitives
  if (typeof value === 'number') {
    if (!isValidNumber(value)) {
      throw new Error(`Invalid number: ${value} (NaN and Infinity not allowed)`);
    }
    return value;
  }

  // Other primitives (bool, string)
  if (typeof value !== 'object') {
    return value;
  }

  // Variable site - preserve as-is
  if (isVar(value)) {
    return value;
  }

  // Array
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return { _type: 'list' };
    }
    let tail = null;
    for (let i = value.length - 1; i >= 0; i--) {
      tail = { head: normalize(value[i], _depth + 1), tail: tail };
    }
    return { _type: 'list', ...tail };
  }

  // Object
  if (typeof value === 'object') {
    const keys = Object.keys(value);

    if (keys.length === 0) {
      return { _type: 'dict' };
    }

    if (isTypedEmptySentinel(value)) {
      return value;
    }

    if (isLinkedListNode(value)) {
      // F-43: Only treat as typed linked list if _type is valid
      if ('_type' in value && VALID_TYPE_TAGS.has(value._type)) {
        return {
          _type: value._type,
          head: normalize(value.head, _depth + 1),
          tail: normalize(value.tail, _depth + 1)
        };
      }
      // Untyped head/tail — normalize both parts
      if (!('_type' in value)) {
        return {
          head: normalize(value.head, _depth + 1),
          tail: normalize(value.tail, _depth + 1)
        };
      }
      // Invalid _type: fall through to regular dict normalization
    }

    // Regular dict - convert to sorted kv linked list
    const sortedKeys = keys.sort(compareMuStringKeysByCodepoint);
    let tail = null;
    for (let i = sortedKeys.length - 1; i >= 0; i--) {
      const k = sortedKeys[i];
      const kv = { head: k, tail: { head: normalize(value[k], _depth + 1), tail: null } };
      tail = { head: kv, tail: tail };
    }
    return { _type: 'dict', ...tail };
  }

  return value;
}

/**
 * Denormalize from linked-list format back to JS values.
 *
 * @host_recursion - recursive denormalization
 * @host_iteration - while loop for linked list traversal
 */
function denormalize(value, _depth = 0) {
  if (_depth > MAX_DEPTH) {
    throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
  }

  if (value === null) {
    return null;
  }

  if (typeof value !== 'object') {
    return value;
  }

  if (isVar(value)) {
    return value;
  }

  // Check for typed structure
  if (typeof value === 'object' && '_type' in value) {
    const type = value._type;

    if (typeof type === 'string') {
      if (!VALID_TYPE_TAGS.has(type)) {
        throw new Error(
          `Invalid type tag '${type}' in denormalize. ` +
          `Allowed: ${[...VALID_TYPE_TAGS].join(', ')}`
        );
      }
    }

    if (typeof type === 'string' && VALID_TYPE_TAGS.has(type)) {
      if (!('head' in value)) {
        if (type === 'list') return [];
        if (type === 'dict') return {};
      }

      if (type === 'list') {
        const result = [];
        let node = value;
        let nodeDepth = 0;
        while (node && typeof node === 'object' && 'head' in node) {
          if (nodeDepth++ > MAX_DENORM_ITER) {
            throw new Error(`Max denorm iterations exceeded in list denormalization`);
          }
          result.push(denormalize(node.head, _depth + 1));
          node = node.tail;
        }
        // Fail-closed: improper tail (non-null terminator) silently drops data
        if (node !== null && node !== undefined) {
          throw new Error(
            `Improper linked list tail in denormalize: expected null, ` +
            `got ${typeof node} (${JSON.stringify(node)}). Data would be silently lost.`
          );
        }
        return result;
      }

      if (type === 'dict') {
        const result = Object.create(null);
        let node = value;
        let nodeDepth = 0;
        while (node && typeof node === 'object' && 'head' in node) {
          if (nodeDepth++ > MAX_DENORM_ITER) {
            throw new Error(`Max denorm iterations exceeded in dict denormalization`);
          }
          const kv = node.head;
          if (kv && typeof kv === 'object' && 'head' in kv && kv.tail && 'head' in kv.tail) {
            result[kv.head] = denormalize(kv.tail.head, _depth + 1);
          }
          node = node.tail;
        }
        // Fail-closed: improper tail (non-null terminator) silently drops data
        if (node !== null && node !== undefined) {
          throw new Error(
            `Improper linked list tail in denormalize: expected null, ` +
            `got ${typeof node} (${JSON.stringify(node)}). Data would be silently lost.`
          );
        }
        return result;
      }
    }
  }

  // Non-typed head/tail (EXACTLY 2 keys) - classify and convert
  if (isLinkedListNode(value) && !('_type' in value)) {
    const isDictEncoding = classifyLegacyLinkedList(value) === 'dict';

    if (isDictEncoding) {
      const result = Object.create(null);
      let node = value;
      let nodeDepth = 0;
      while (node && typeof node === 'object' && 'head' in node) {
        if (nodeDepth++ > MAX_DENORM_ITER) {
          throw new Error(`Max denorm iterations exceeded in dict denormalization`);
        }
        const kv = node.head;
        if (kv && typeof kv === 'object' && 'head' in kv && kv.tail && 'head' in kv.tail) {
          result[kv.head] = denormalize(kv.tail.head, _depth + 1);
        }
        node = node.tail;
      }
      // Fail-closed: improper tail (non-null terminator) silently drops data
      if (node !== null && node !== undefined) {
        throw new Error(
          `Improper linked list tail in denormalize: expected null, ` +
          `got ${typeof node} (${JSON.stringify(node)}). Data would be silently lost.`
        );
      }
      return result;
    } else {
      const result = [];
      let node = value;
      let nodeDepth = 0;
      while (node && typeof node === 'object' && 'head' in node) {
        if (nodeDepth++ > MAX_DENORM_ITER) {
          throw new Error(`Max denorm iterations exceeded in list denormalization`);
        }
        result.push(denormalize(node.head, _depth + 1));
        node = node.tail;
      }
      // Fail-closed: improper tail (non-null terminator) silently drops data
      if (node !== null && node !== undefined) {
        throw new Error(
          `Improper linked list tail in denormalize: expected null, ` +
          `got ${typeof node} (${JSON.stringify(node)}). Data would be silently lost.`
        );
      }
      return result;
    }
  }

  // Regular object - denormalize values
  const result = Object.create(null);
  for (const [k, v] of Object.entries(value)) {
    result[k] = denormalize(v, _depth + 1);
  }
  return result;
}

/**
 * Normalize a projection (pattern and body).
 */
function normalizeProjection(proj) {
  return {
    pattern: normalize(proj.pattern),
    body: normalize(proj.body)
  };
}

/**
 * Convert array to linked list for kernel input.
 * @host_iteration - for loop for conversion
 */
function listToLinked(arr) {
  if (!Array.isArray(arr) || arr.length === 0) {
    return null;
  }
  let result = null;
  for (let i = arr.length - 1; i >= 0; i--) {
    result = { head: arr[i], tail: result };
  }
  return result;
}

module.exports = {
  isLinkedListNode,
  isTypedEmptySentinel,
  classifyLegacyLinkedList,
  normalize,
  denormalize,
  normalizeProjection,
  listToLinked,
};
