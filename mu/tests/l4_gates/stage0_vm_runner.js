'use strict';
/**
 * Stage0 VM test runner — JSON API for cross-substrate parity testing.
 *
 * Test fixture, NOT a host module. Lives in tests/ to avoid triggering
 * the action-set-sync gate in test_js_parity_automated.py.
 *
 * Usage: node tests/l4_gates/stage0_vm_runner.js '<JSON request>'
 *
 * Request format:
 *   {"action": "step", "bundle_path": "...", "input": {...}}
 *   {"action": "run",  "bundle_path": "...", "input": {...}}
 *   {"action": "validate", "bundle_path": "..."}
 *
 * Response: JSON_API_RESPONSE:<json>
 */

const fs = require('fs');
const path = require('path');

// Use CWD as repo root (caller sets cwd=REPO_ROOT)
const repoRoot = process.cwd();
const { validateBundle, stage0VmStep, stage0VmRun } =
  require(path.join(repoRoot, 'mu', 'host', 'js', 'core', 'stage0_vm'));

const request = JSON.parse(process.argv[2]);

try {
  const bundlePath = path.resolve(repoRoot, request.bundle_path);
  const bundle = JSON.parse(fs.readFileSync(bundlePath, 'utf8'));

  if (request.action === 'validate') {
    validateBundle(bundle);
    console.log('JSON_API_RESPONSE:' + JSON.stringify({ ok: true }));
  }
  else if (request.action === 'step') {
    const result = stage0VmStep(bundle, request.input);
    console.log('JSON_API_RESPONSE:' + JSON.stringify(result));
  }
  else if (request.action === 'run') {
    const result = stage0VmRun(bundle, request.input);
    console.log('JSON_API_RESPONSE:' + JSON.stringify(result));
  }
  else {
    console.log('JSON_API_RESPONSE:' + JSON.stringify({
      error: `Unknown action: ${request.action}`,
    }));
    process.exit(1);
  }
} catch (e) {
  console.log('JSON_API_RESPONSE:' + JSON.stringify({
    error: e.message,
    name: e.name || 'Error',
  }));
  process.exit(1);
}
