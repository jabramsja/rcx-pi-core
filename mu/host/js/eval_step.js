'use strict';
/**
 * RCX eval_step.js — Compatibility facade / stable CLI entrypoint
 *
 * All runtime logic extracted to mu/host/js/core/ and mu/host/js/engine/.
 * This file remains the stable entrypoint for:
 *   node mu/host/js/eval_step.js          # self-tests
 *   node mu/host/js/eval_step.js --json-api '...'  # JSON API
 *
 * BOOTSTRAP_PRIMITIVE: eval_step
 * (this shim delegates to cli/main.js which loads seeds and runs tests)
 */
if (require.main === module) {
  require('./cli/main');
}
