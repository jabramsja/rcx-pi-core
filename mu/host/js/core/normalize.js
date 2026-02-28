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
 * @host_iteration - iterative normalization with explicit stack (Phase 6c parity)
 */
function normalize(value, _depth = 0) {
  // Iterative normalization using explicit stack (Phase 6c parity with Python).
  // Stack items: [operation, ...data]
  // Operations:
  //   ["eval", val] - evaluate val and store result
  //   ["leave", ref] - remove ref from path (exiting this node)
  //   ["list_tail", elemIdx, elemsNormalized, originalList] - building list
  //   ["dict_tail", keyIdx, keys, kvsNormalized, originalDict] - building dict
  //   ["ht_head", tailVal] - head done, now process tail
  //   ["ht_combine", headNormalized] - combine head and tail results
  //   ["ht_typed", type, tailVal] - typed head done, process tail
  //   ["ht_typed_combine", type, headNormalized] - combine typed head/tail

  // Path-based cycle detection: track current ancestors via object references.
  // Allows shared references (DAGs) while detecting true back-edges (cycles).
  const path = new Set();
  const stack = [['eval', value]];
  let result = null;

  while (stack.length > 0) {
    const item = stack.pop();
    const op = item[0];

    if (op === 'leave') {
      path.delete(item[1]);
      continue;
    }

    if (op === 'eval') {
      const val = item[1];

      if (val === null) {
        result = null;
        continue;
      }

      // Reject invalid types (function, undefined, symbol)
      if (val === undefined) {
        throw new RcxError('input.malformed_normalized', 'undefined is not valid Mu');
      }
      if (typeof val === 'function') {
        throw new RcxError('input.malformed_normalized', 'Functions are not valid Mu');
      }
      if (typeof val === 'symbol') {
        throw new RcxError('input.malformed_normalized', 'Symbols are not valid Mu');
      }

      // Validate primitives
      if (typeof val === 'number') {
        if (!isValidNumber(val)) {
          throw new Error(`Invalid number: ${val} (NaN and Infinity not allowed)`);
        }
        result = val;
        continue;
      }

      // Other primitives (bool, string)
      if (typeof val !== 'object') {
        result = val;
        continue;
      }

      // Variable site - preserve as-is
      if (isVar(val)) {
        result = val;
        continue;
      }

      // Compound types - depth + cycle detection
      if (path.size > MAX_DEPTH) {
        throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
      }
      if (path.has(val)) {
        throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
      }
      path.add(val);
      stack.push(['leave', val]);

      // Array
      if (Array.isArray(val)) {
        if (val.length === 0) {
          result = { _type: 'list' };
          continue;
        }
        // Start from last element (LIFO builds correct order)
        stack.push(['list_tail', val.length - 1, [], val]);
        stack.push(['eval', val[val.length - 1]]);
        continue;
      }

      // Object
      const keys = Object.keys(val);

      if (keys.length === 0) {
        result = { _type: 'dict' };
        continue;
      }

      if (isTypedEmptySentinel(val)) {
        result = val;
        continue;
      }

      if (isLinkedListNode(val)) {
        if ('_type' in val) {
          stack.push(['ht_typed', val._type, val.tail]);
          stack.push(['eval', val.head]);
        } else {
          stack.push(['ht_head', val.tail]);
          stack.push(['eval', val.head]);
        }
        continue;
      }

      // Regular dict - convert to sorted kv linked list
      const sortedKeys = keys.sort(compareMuStringKeysByCodepoint);
      stack.push(['dict_tail', sortedKeys.length - 1, sortedKeys, [], val]);
      stack.push(['eval', val[sortedKeys[sortedKeys.length - 1]]]);
      continue;

    } else if (op === 'ht_typed') {
      // Type-tagged: head is done, now process tail (preserving _type)
      const _type = item[1];
      const tailVal = item[2];
      stack.push(['ht_typed_combine', _type, result]);
      stack.push(['eval', tailVal]);

    } else if (op === 'ht_typed_combine') {
      // Type-tagged: tail is done, combine with _type and head
      const _type = item[1];
      const headNormalized = item[2];
      result = { _type: _type, head: headNormalized, tail: result };

    } else if (op === 'ht_head') {
      // Head is done, now process tail
      const tailVal = item[1];
      stack.push(['ht_combine', result]);
      stack.push(['eval', tailVal]);

    } else if (op === 'ht_combine') {
      // Tail is done, combine with head
      const headNormalized = item[1];
      result = { head: headNormalized, tail: result };

    } else if (op === 'list_tail') {
      const elemIdx = item[1];
      const elemsNormalized = item[2];
      const originalList = item[3];
      elemsNormalized.push(result);

      if (elemIdx === 0) {
        // All elements processed - build linked list with type tag
        // Elements are in reverse order (last to first), correct for building
        let tail = null;
        for (const elem of elemsNormalized) {
          tail = { head: elem, tail: tail };
        }
        if (tail !== null) {
          tail._type = 'list';
        }
        result = tail;
      } else {
        stack.push(['list_tail', elemIdx - 1, elemsNormalized, originalList]);
        stack.push(['eval', originalList[elemIdx - 1]]);
      }

    } else if (op === 'dict_tail') {
      const keyIdx = item[1];
      const sortedKeys = item[2];
      const kvsNormalized = item[3];
      const originalDict = item[4];
      const key = sortedKeys[keyIdx];
      const kvPair = { head: key, tail: { head: result, tail: null } };
      kvsNormalized.push(kvPair);

      if (keyIdx === 0) {
        // All keys processed - build linked list of kv-pairs with type tag
        let tail = null;
        for (const kv of kvsNormalized) {
          tail = { head: kv, tail: tail };
        }
        if (tail !== null) {
          tail._type = 'dict';
        }
        result = tail;
      } else {
        stack.push(['dict_tail', keyIdx - 1, sortedKeys, kvsNormalized, originalDict]);
        stack.push(['eval', originalDict[sortedKeys[keyIdx - 1]]]);
      }
    }
  }

  return result;
}

/**
 * Denormalize from linked-list format back to JS values.
 *
 * @host_iteration - iterative denormalization with explicit stack (Phase 6c parity)
 */
function denormalize(value, _depth = 0) {
  // Simple cases - no iteration needed
  if (value === null) return null;
  if (typeof value !== 'object') return value;
  if (isVar(value)) return value;

  // Iterative denormalization using explicit stack (Phase 6c parity with Python).
  // Stack items: [operation, ...data]
  // Operations:
  //   ["eval", val] - evaluate val and store result
  //   ["leave", ref] - remove ref from path (exiting this node)
  //   ["finalize_list", resultList] - set result to the populated list
  //   ["finalize_dict", resultDict] - set result to the populated dict
  //   ["list_elem", resultList] - append result to resultList
  //   ["dict_kv", key, resultDict] - set resultDict[key] = result

  const path = new Set();
  const stack = [['eval', value]];
  let result = null;

  while (stack.length > 0) {
    const item = stack.pop();
    const op = item[0];

    if (op === 'leave') {
      path.delete(item[1]);
      continue;
    }

    if (op === 'eval') {
      const val = item[1];

      // Simple cases
      if (val === null) { result = null; continue; }
      if (typeof val !== 'object') { result = val; continue; }
      if (isVar(val)) { result = val; continue; }

      // Depth + cycle detection
      if (path.size > MAX_DEPTH) {
        throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
      }
      if (path.has(val)) {
        throw new Error(`Max depth exceeded (${MAX_DEPTH}): possible circular reference or deeply nested structure`);
      }
      path.add(val);
      stack.push(['leave', val]);

      // Typed structure
      if ('_type' in val) {
        const type = val._type;

        if (typeof type === 'string') {
          if (!VALID_TYPE_TAGS.has(type)) {
            throw new Error(
              `Invalid type tag '${type}' in denormalize. ` +
              `Allowed: ${[...VALID_TYPE_TAGS].join(', ')}`
            );
          }
        }

        if (typeof type === 'string' && VALID_TYPE_TAGS.has(type)) {
          // Empty sentinel
          if (!('head' in val)) {
            if (type === 'list') { result = []; continue; }
            if (type === 'dict') { result = {}; continue; }
          }

          if (type === 'list') {
            // Collect elements iteratively from linked list
            const resultList = [];
            stack.push(['finalize_list', resultList]);
            const elements = [];
            let node = val;
            let nodeDepth = 0;
            while (node && typeof node === 'object' && 'head' in node) {
              if (nodeDepth++ > MAX_DENORM_ITER) {
                throw new Error('Max denorm iterations exceeded in list denormalization');
              }
              elements.push(node.head);
              node = node.tail;
            }
            // Push in reverse order (LIFO)
            for (let i = elements.length - 1; i >= 0; i--) {
              stack.push(['list_elem', resultList]);
              stack.push(['eval', elements[i]]);
            }
            continue;
          }

          if (type === 'dict') {
            // Collect kv-pairs iteratively from linked list
            const resultDict = Object.create(null);
            stack.push(['finalize_dict', resultDict]);
            const kvPairs = [];
            let node = val;
            let nodeDepth = 0;
            while (node && typeof node === 'object' && 'head' in node) {
              if (nodeDepth++ > MAX_DENORM_ITER) {
                throw new Error('Max denorm iterations exceeded in dict denormalization');
              }
              const kv = node.head;
              if (kv && typeof kv === 'object' && 'head' in kv && kv.tail && 'head' in kv.tail) {
                kvPairs.push([kv.head, kv.tail.head]);
              }
              node = node.tail;
            }
            // Push in reverse order (LIFO)
            for (let i = kvPairs.length - 1; i >= 0; i--) {
              stack.push(['dict_kv', kvPairs[i][0], resultDict]);
              stack.push(['eval', kvPairs[i][1]]);
            }
            continue;
          }
        }
      }

      // Non-typed head/tail (EXACTLY 2 keys) - classify and convert
      if (isLinkedListNode(val) && !('_type' in val)) {
        const isDictEncoding = classifyLegacyLinkedList(val) === 'dict';

        if (isDictEncoding) {
          const resultDict = Object.create(null);
          stack.push(['finalize_dict', resultDict]);
          const kvPairs = [];
          let node = val;
          let nodeDepth = 0;
          while (node && typeof node === 'object' && 'head' in node) {
            if (nodeDepth++ > MAX_DENORM_ITER) {
              throw new Error('Max denorm iterations exceeded in dict denormalization');
            }
            const kv = node.head;
            if (kv && typeof kv === 'object' && 'head' in kv && kv.tail && 'head' in kv.tail) {
              kvPairs.push([kv.head, kv.tail.head]);
            }
            node = node.tail;
          }
          for (let i = kvPairs.length - 1; i >= 0; i--) {
            stack.push(['dict_kv', kvPairs[i][0], resultDict]);
            stack.push(['eval', kvPairs[i][1]]);
          }
          continue;
        } else {
          const resultList = [];
          stack.push(['finalize_list', resultList]);
          const elements = [];
          let node = val;
          let nodeDepth = 0;
          while (node && typeof node === 'object' && 'head' in node) {
            if (nodeDepth++ > MAX_DENORM_ITER) {
              throw new Error('Max denorm iterations exceeded in list denormalization');
            }
            elements.push(node.head);
            node = node.tail;
          }
          for (let i = elements.length - 1; i >= 0; i--) {
            stack.push(['list_elem', resultList]);
            stack.push(['eval', elements[i]]);
          }
          continue;
        }
      }

      // Regular object - denormalize values
      const resultDict = Object.create(null);
      stack.push(['finalize_dict', resultDict]);
      const entries = Object.entries(val);
      for (let i = entries.length - 1; i >= 0; i--) {
        stack.push(['dict_kv', entries[i][0], resultDict]);
        stack.push(['eval', entries[i][1]]);
      }
      continue;

    } else if (op === 'finalize_list') {
      result = item[1];

    } else if (op === 'finalize_dict') {
      result = item[1];

    } else if (op === 'list_elem') {
      item[1].push(result);

    } else if (op === 'dict_kv') {
      item[2][item[1]] = result;
    }
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
