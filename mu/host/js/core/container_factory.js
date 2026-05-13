'use strict';
/**
 * Internal Mu container provenance factory.
 *
 * This module is the JavaScript host-side constructor boundary for fresh Mu
 * compound containers produced by checked seed/API ingress and live Mu runtime
 * producers. The public type API exposes only the read predicate from this set.
 */

const _TRUSTED_MU_CONTAINERS = new WeakSet(); // AST_OK_JS: private provenance set for Mu-origin containers, not semantic identity or cache behavior

module.exports = Object.freeze({
  has(value) {
    return value !== null && typeof value === 'object' && _TRUSTED_MU_CONTAINERS.has(value);
  },
  list(items) {
    const out = [];
    if (items !== undefined) {
      for (const item of items) out.push(item);
    }
    _TRUSTED_MU_CONTAINERS.add(out);
    return out;
  },
  record(entries) {
    const out = Object.create(null);
    if (entries !== undefined) {
      for (const [key, value] of entries) out[key] = value;
    }
    _TRUSTED_MU_CONTAINERS.add(out);
    return out;
  },
});
