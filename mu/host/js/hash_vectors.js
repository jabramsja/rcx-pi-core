#!/usr/bin/env node
/**
 * Cross-substrate hash parity verifier.
 *
 * Computes muHash for test vectors and outputs JSON mapping {id: hash}.
 * Called by tests/test_hash_parity.py to compare against Python mu_hash().
 *
 * The canonicalize function here MUST match eval_step.js muHash exactly.
 * If you change muHash in eval_step.js, update this file too.
 *
 * Usage: node hash_vectors.js <path-to-hashing_vectors.json>
 */
const crypto = require('crypto');
const fs = require('fs');

// Canonical JSON serialization — must match Python json.dumps(value, sort_keys=True, ensure_ascii=False)
// This is copied from eval_step.js muHash to ensure we test the SAME algorithm.
function canonicalize(v) {
  if (v === null) return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return JSON.stringify(v);
  if (typeof v === 'string') return JSON.stringify(v);
  if (Array.isArray(v)) {
    return '[' + v.map(canonicalize).join(', ') + ']';
  }
  // Object: sort keys, use Python separators
  const keys = Object.keys(v).sort();
  const pairs = keys.map(k => JSON.stringify(k) + ': ' + canonicalize(v[k]));
  return '{' + pairs.join(', ') + '}';
}

function muHash(value) {
  return crypto.createHash('sha256').update(canonicalize(value), 'utf8').digest('hex');
}

const vectorsPath = process.argv[2];
if (!vectorsPath) {
  process.stderr.write('Usage: node hash_vectors.js <vectors.json>\n');
  process.exit(1);
}

const data = JSON.parse(fs.readFileSync(vectorsPath, 'utf8'));
const result = {};
for (const v of data.vectors) {
  result[v.id] = muHash(v.value);
}

process.stdout.write(JSON.stringify(result));
