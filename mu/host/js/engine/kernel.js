'use strict';
/**
 * RCX Engine Kernel
 *
 * stepKernel, runStructural, stepKernelStructural.
 * These are kernel orchestration, NOT bootstrap primitives.
 *
 * Depends on: core/*
 */

const { NO_MATCH, RcxError } = require('../core/constants');
const { isValidMu, muHash, muHashCached, muHashControlCached } = require('../core/types');
const muContainers = require('../core/container_factory');
const { normalize, denormalize, normalizeProjection, listToLinked } = require('../core/normalize');
const { validateNoKernelReservedFields, validateAlgorithmRuntimeFields, rejectNonlinearProjections } = require('../core/security');
const { step, match, isKernelTerminal, isKernelIntermediate, makeUndefinedMotif, stage0Match, stage0Substitute, _stepTrusted, _applyProjectionTrusted } = require('../core/bootstrap_core');
const { validateBundle, _stage0VmStepTrusted, _stage0VmRunTrusted, muDeepEqual, muCopy } = require('../core/stage0_vm'); // W6A: trusted path — bundles loaded at module level in main.js // CONTRABAND_OK: stage0_vm is our module, not Node.js vm

// S1-B: VM cutover flags (parity with Python step_mu.py)
// Founder GO 2026-03-15: VM path is now primary for match.v2/subst.v2
const _STAGE0_VM_CUTOVER = true;
let _STAGE0_SHADOW_ENABLED = false; // Shadow disabled (cutover=true makes shadow dead code)
const _VALIDATED_VM_CONFIGS = new WeakSet();
const _VM_CONFIG_BUNDLE_SLOTS = Object.freeze([
  ['kernelBundle', true],
  ['bridgeBundle', false],
  ['matchBundle', true],
  ['substBundle', true],
]);

const _vmConfigTrust = {
  validate(vmConfig) {
    if (vmConfig === null || vmConfig === undefined) {
      return null;
    }
    if (typeof vmConfig !== 'object' || Array.isArray(vmConfig)) {
      throw new Error(
        `SECURITY: vmConfig must be an object or null, got ${vmConfig === null ? 'null' : Array.isArray(vmConfig) ? 'array' : typeof vmConfig}`
      );
    }
    if (_VALIDATED_VM_CONFIGS.has(vmConfig)) {
      return vmConfig;
    }
    const trustedConfig = {};
    for (const [slotName, required] of _VM_CONFIG_BUNDLE_SLOTS) {
      if (!Object.hasOwn(vmConfig, slotName)) {
        if (required) {
          throw new Error(`SECURITY: vmConfig.${slotName} is required for trusted Stage0 VM execution`);
        }
        trustedConfig[slotName] = null;
        continue;
      }
      const bundle = vmConfig[slotName];
      if (!required && bundle === null) {
        trustedConfig[slotName] = null;
        continue;
      }
      try {
        const snapshot = muCopy(bundle, true, `vmConfig.${slotName}`);
        validateBundle(snapshot);
        const freezeStack = [snapshot];
        while (freezeStack.length > 0) {
          const node = freezeStack.pop();
          if (node !== null && typeof node === 'object' && !Object.isFrozen(node)) {
            for (const key of Object.keys(node)) {
              freezeStack.push(node[key]);
            }
            Object.freeze(node);
          }
        }
        trustedConfig[slotName] = snapshot;
      } catch (e) {
        throw new Error(
          `SECURITY: vmConfig.${slotName} failed Stage0 bundle validation before trusted VM execution: ${e.message}`
        );
      }
    }
    Object.freeze(trustedConfig);
    _VALIDATED_VM_CONFIGS.add(trustedConfig);
    return trustedConfig;
  },
};

/**
 * S1-C: Kernel step — ALL projections via Stage0 VM.
 * No coverage system in JS — pure execution only.
 * Parity with Python _step_kernel_with_vm in step_mu.py.
 */
function _assertVmMatchResult(result, bundleId) {
  // NB10 fix: fail-closed assertion on VM match result shape (parity with Python KeyError)
  // null is valid Mu (void/no-structure). Only reject undefined (missing field).
  if (result.root === undefined) {
    throw new Error(
      `SECURITY: _stage0VmStepTrusted returned status='match' for ${bundleId} but .root is undefined. ` +
      `Bundle may be malformed or VM produced invalid output.`);
  }
}

/**
 * W6A trusted path: bundles are mechanically validated once into an immutable
 * vmConfig snapshot before any trusted VM helper.
 */
function _stepKernelWithVM(kernelBundle, bridgeBundle, matchBundle, substBundle, inputValue) {
  // 1. kernel.v1 via Stage0 VM (S1-C: was host _applyProjectionTrusted)
  const kernelResult = _stage0VmStepTrusted(kernelBundle, inputValue);
  if (kernelResult.status === 'match') { _assertVmMatchResult(kernelResult, 'kernel.v1'); return kernelResult.root; }

  // 2. bridge via Stage0 VM (S1-C: was host _applyProjectionTrusted)
  if (bridgeBundle) {
    const bridgeResult = _stage0VmStepTrusted(bridgeBundle, inputValue);
    if (bridgeResult.status === 'match') { _assertVmMatchResult(bridgeResult, 'bridge'); return bridgeResult.root; }
  }

  // 3. match.v2 via Stage0 VM
  const matchResult = _stage0VmStepTrusted(matchBundle, inputValue);
  if (matchResult.status === 'match') { _assertVmMatchResult(matchResult, 'match.v2'); return matchResult.root; }

  // 4. subst.v2 via Stage0 VM
  const substResult = _stage0VmStepTrusted(substBundle, inputValue);
  if (substResult.status === 'match') { _assertVmMatchResult(substResult, 'subst.v2'); return substResult.root; }

  return inputValue; // stall
}

const KERNEL_DRIVER_CONTINUATION_KEYS = Object.freeze([
  'domain_input',
  'fuel_mode',
  'kernel_state',
  'projection_cursor',
  'remaining_fuel',
  'steps_used',
  'tag',
  'terminal',
  'version',
  'watchdog_cap',
]);
const KERNEL_PROJECTION_CURSOR_KEYS = Object.freeze([
  'exhausted',
  'position',
  'tag',
  'version',
]);
const KERNEL_TERMINAL_METADATA_KEYS = Object.freeze([
  'error',
  'reached',
  'reason',
]);
const KERNEL_TERMINAL_REASONS = Object.freeze([
  'accepted',
  'error',
  'fuel_exhausted',
  'malformed_fuel',
  'watchdog_exhausted',
]);
const KERNEL_CONTINUATION_PROOF_TOKEN = Object.freeze({
  tag: 'kernel_continuation_proof_token',
});
/**
 * Internal: single kernel-driver transition.
 * Caller must provide pre-validated, pre-normalized kernelInput or a
 * cross-substrate continuation state.
 *
 * @host_iteration — single-step host transition marker retained until ratchet baseline update.
 */
function _stepKernelCore(kernelProjections, kernelInput, domainInput, validator, maxSteps, vmConfig, kernelFuel = undefined, continuationState = null, continuationProof = null) {
  vmConfig = _vmConfigTrust.validate(vmConfig);
  if (typeof maxSteps !== 'number' || !Number.isFinite(maxSteps) || !Number.isInteger(maxSteps)) {
    throw new RcxError(
      'api.bad_request',
      `maxSteps must be a finite integer watchdog, got ${typeof maxSteps}`
    );
  }
  if (maxSteps < 0) {
    throw new RcxError('api.bad_request', `maxSteps must be >= 0, got ${maxSteps}`);
  }
  if (continuationState !== null && kernelFuel !== undefined) {
    throw new Error('SECURITY: continuationState carries remaining_fuel; do not also pass kernelFuel');
  }

  let current = kernelInput;
  let effectiveDomainInput = domainInput;
  let callerSuppliedFuel = kernelFuel !== undefined;
  let fuelCursor = kernelFuel;
  let stepsUsed = 0;
  let watchdogCap = maxSteps;
  if (continuationState !== null) {
    if (!isValidMu(continuationState)) {
      throw new Error('SECURITY: continuationState must be valid Mu data');
    }
    if (continuationState === null || typeof continuationState !== 'object' || Array.isArray(continuationState)) {
      throw new Error('SECURITY: continuationState must be valid Mu object data');
    }
    let keys = Object.keys(continuationState).sort();
    if (keys.length !== KERNEL_DRIVER_CONTINUATION_KEYS.length) {
      throw new Error('SECURITY: continuationState key set mismatch');
    }
    for (let i = 0; i < keys.length; i++) {
      if (keys[i] !== KERNEL_DRIVER_CONTINUATION_KEYS[i]) {
        throw new Error('SECURITY: continuationState key set mismatch');
      }
    }
    if (continuationState.tag !== 'kernel_driver_continuation_state') {
      throw new Error('SECURITY: continuationState tag mismatch');
    }
    if (continuationState.version !== 1) {
      throw new Error('SECURITY: continuationState version mismatch');
    }
    if (continuationState.fuel_mode !== 'explicit' && continuationState.fuel_mode !== 'omitted_compatibility') {
      throw new Error('SECURITY: continuationState fuel_mode mismatch');
    }
    if (typeof continuationState.steps_used !== 'number' ||
        !Number.isInteger(continuationState.steps_used) ||
        continuationState.steps_used < 0) {
      throw new Error('SECURITY: continuationState.steps_used must be a non-negative integer');
    }
    if (continuationState.watchdog_cap === null) {
      throw new Error('SECURITY: continuationState.watchdog_cap must match supplied maxSteps');
    }
    if (typeof continuationState.watchdog_cap !== 'number' ||
        !Number.isInteger(continuationState.watchdog_cap) ||
        continuationState.watchdog_cap < 0) {
      throw new Error('SECURITY: continuationState.watchdog_cap must be a non-negative integer');
    }
    if (continuationState.watchdog_cap !== maxSteps) {
      throw new Error('SECURITY: continuationState.watchdog_cap must match supplied maxSteps');
    }
    if (continuationState.steps_used >= continuationState.watchdog_cap) {
      throw new Error('SECURITY: continuationState steps_used is not bound to watchdog_cap');
    }
    if (continuationState.projection_cursor !== null) {
      if (continuationState.projection_cursor === null ||
          typeof continuationState.projection_cursor !== 'object' ||
          Array.isArray(continuationState.projection_cursor)) {
        throw new Error('SECURITY: projection_cursor must be a Mu object or null');
      }
      keys = Object.keys(continuationState.projection_cursor).sort();
      if (keys.length !== KERNEL_PROJECTION_CURSOR_KEYS.length) {
        throw new Error('SECURITY: projection_cursor key set mismatch');
      }
      for (let i = 0; i < keys.length; i++) {
        if (keys[i] !== KERNEL_PROJECTION_CURSOR_KEYS[i]) {
          throw new Error('SECURITY: projection_cursor key set mismatch');
        }
      }
      if (continuationState.projection_cursor.tag !== 'kernel_projection_cursor') {
        throw new Error('SECURITY: projection_cursor tag mismatch');
      }
      if (continuationState.projection_cursor.version !== 1) {
        throw new Error('SECURITY: projection_cursor version mismatch');
      }
      if (typeof continuationState.projection_cursor.position !== 'number' ||
          !Number.isInteger(continuationState.projection_cursor.position) ||
          continuationState.projection_cursor.position < 0) {
        throw new Error('SECURITY: projection_cursor.position must be a non-negative integer');
      }
      if (typeof continuationState.projection_cursor.exhausted !== 'boolean') {
        throw new Error('SECURITY: projection_cursor.exhausted must be boolean');
      }
    }
    if (continuationState.terminal === null ||
        typeof continuationState.terminal !== 'object' ||
        Array.isArray(continuationState.terminal)) {
      throw new Error('SECURITY: continuation terminal metadata must be a Mu object');
    }
    keys = Object.keys(continuationState.terminal).sort();
    if (keys.length !== KERNEL_TERMINAL_METADATA_KEYS.length) {
      throw new Error('SECURITY: terminal metadata key set mismatch');
    }
    for (let i = 0; i < keys.length; i++) {
      if (keys[i] !== KERNEL_TERMINAL_METADATA_KEYS[i]) {
        throw new Error('SECURITY: terminal metadata key set mismatch');
      }
    }
    if (typeof continuationState.terminal.reached !== 'boolean') {
      throw new Error('SECURITY: terminal.reached must be boolean');
    }
    if (continuationState.terminal.reason !== null &&
        !KERNEL_TERMINAL_REASONS.includes(continuationState.terminal.reason)) {
      throw new Error('SECURITY: terminal.reason mismatch');
    }
    if (continuationState.terminal.error !== null &&
        typeof continuationState.terminal.error !== 'string') {
      throw new Error('SECURITY: terminal.error must be string or null');
    }
    if (continuationState.terminal.reached !== false ||
        continuationState.terminal.reason !== null ||
        continuationState.terminal.error !== null) {
      throw new Error('SECURITY: continuation terminal metadata must remain nonterminal');
    }
    if (continuationState.fuel_mode === 'explicit') {
      if (!isValidMu(continuationState.remaining_fuel)) {
        throw new Error('SECURITY: kernelFuel must be valid Mu linked-list data');
      }
      let fuelProbe = continuationState.remaining_fuel;
      while (fuelProbe !== null) {
        if (typeof fuelProbe !== 'object' || Array.isArray(fuelProbe) ||
            !Object.hasOwn(fuelProbe, 'head') || !Object.hasOwn(fuelProbe, 'tail') ||
            Object.keys(fuelProbe).length !== 2) {
          throw new Error('SECURITY: kernelFuel must be a Mu head/tail linked list');
        }
        fuelProbe = fuelProbe.tail;
      }
    } else if (continuationState.remaining_fuel !== null) {
      throw new Error('SECURITY: omitted compatibility continuation must not carry remaining_fuel');
    }
    // SECURITY: continuation data owns progress, not projection authority.
    // Bind resume to the current call's supplied input/projection cursor before
    // stepping the embedded Mu kernel state.
    const proofTokenOk =
      continuationProof !== null &&
      typeof continuationProof === 'object' &&
      !Array.isArray(continuationProof) &&
      continuationProof._token === KERNEL_CONTINUATION_PROOF_TOKEN;
    const trustedSameProcessContinuation =
      proofTokenOk &&
      continuationProof.continuation === continuationState &&
      continuationProof.domainInput === domainInput &&
      continuationState.domain_input === domainInput &&
      continuationProof.normalizedInput === kernelInput._step &&
      continuationProof.projectionAuthority === kernelInput._projs &&
      continuationProof.watchdogCap === watchdogCap;
    const useDomainValidation = validator !== validateAlgorithmRuntimeFields;
    const skipContinuationBindingHashes = trustedSameProcessContinuation && !useDomainValidation;
    const normalizedInputHash = skipContinuationBindingHashes ? null : muHash(kernelInput._step);
    const domainInputHash = skipContinuationBindingHashes ? null : muHash(domainInput);
    if (
      !trustedSameProcessContinuation &&
      muHash(continuationState.domain_input) !== domainInputHash
    ) {
      throw new Error('SECURITY: continuationState domain_input is not bound to supplied input');
    }
    const projectionAuthorityHash = skipContinuationBindingHashes ? null : muHash(kernelInput._projs);
    const trustedContinuationProof =
      trustedSameProcessContinuation ||
      (
        proofTokenOk &&
        continuationProof.continuationHash === muHash(continuationState) &&
        continuationProof.domainInputHash === domainInputHash &&
        continuationProof.normalizedInputHash === normalizedInputHash &&
        continuationProof.projectionAuthorityHash === projectionAuthorityHash &&
        continuationProof.watchdogCap === watchdogCap
      );
    const kernelState = continuationState.kernel_state;
    const kernelStateIsObject = kernelState !== null && typeof kernelState === 'object' && !Array.isArray(kernelState);
    if (!useDomainValidation && !trustedContinuationProof) {
      const continuationCursors = [];
      const bodyRestPairs = [];
      const patternRestPairs = [];
      const substResultChecks = [];
      const substStateChecks = [];
      const inProgressMatchChecks = [];
      const projectionContexts = [];
      let prefixHasMatchingProjection = false;
      let projectionAuthorityCursor = kernelInput._projs;
      while (projectionAuthorityCursor !== null) {
        if (typeof projectionAuthorityCursor !== 'object' || Array.isArray(projectionAuthorityCursor) ||
            !Object.hasOwn(projectionAuthorityCursor, 'head') ||
            !Object.hasOwn(projectionAuthorityCursor, 'tail') ||
            Object.keys(projectionAuthorityCursor).length !== 2) {
          throw new Error('SECURITY: kernel projection cursor must be a Mu head/tail linked list');
        }
        const projectionAuthority = projectionAuthorityCursor.head;
        if (projectionAuthority === null || typeof projectionAuthority !== 'object' ||
            Array.isArray(projectionAuthority) ||
            !Object.hasOwn(projectionAuthority, 'pattern') ||
            !Object.hasOwn(projectionAuthority, 'body') ||
            Object.keys(projectionAuthority).length !== 2) {
          throw new Error('SECURITY: kernel projection cursor head must be a normalized projection');
        }
        let matchBindings = NO_MATCH;
        let projectionMatches = false;
        if (!prefixHasMatchingProjection) {
          matchBindings = stage0Match(projectionAuthority.pattern, kernelInput._step, null);
          projectionMatches = matchBindings !== NO_MATCH;
        }
        projectionContexts.push({
          projection: projectionAuthority,
          projectionCursor: projectionAuthorityCursor,
          projectionRest: projectionAuthorityCursor.tail,
          bodyHash: muHash(projectionAuthority.body),
          patternHash: muHash(projectionAuthority.pattern),
          restHash: muHash(projectionAuthorityCursor.tail),
          cursorHash: muHash(projectionAuthorityCursor),
          prefixCleared: !prefixHasMatchingProjection,
          matchBindings,
          projectionMatches,
        });
        if (projectionMatches) {
          prefixHasMatchingProjection = true;
        }
        projectionAuthorityCursor = projectionAuthorityCursor.tail;
      }
      if (!kernelStateIsObject) {
        // Scalar Mu states can only come from the defensive hash-stall path:
        // they carry no projection authority and must resume as cursorless,
        // already-progressed continuations.
        if (continuationState.projection_cursor !== null) {
          throw new Error('SECURITY: continuationState projection_cursor is not bound to kernel_state');
        }
        if (continuationState.steps_used === 0) {
          throw new Error('SECURITY: continuationState steps_used is not bound to kernel_state phase');
        }
        if (continuationState.steps_used >= watchdogCap) {
          throw new Error('SECURITY: continuationState steps_used is not bound to watchdog_cap');
        }
      }
      if (kernelStateIsObject && continuationState.projection_cursor !== null) {
        if (continuationState.projection_cursor.position !== continuationState.steps_used) {
          throw new Error('SECURITY: continuationState steps_used/projection_cursor mismatch');
        }
        if (!Object.hasOwn(kernelState, '_remaining')) {
          throw new Error('SECURITY: continuationState projection_cursor is not bound to kernel_state');
        }
        if (continuationState.projection_cursor.exhausted !== (kernelState._remaining === null)) {
          throw new Error('SECURITY: continuationState projection_cursor exhausted mismatch');
        }
      } else if (kernelStateIsObject && Object.hasOwn(kernelState, '_remaining')) {
        throw new Error('SECURITY: continuationState projection_cursor missing for kernel projection state');
      }
      if (kernelStateIsObject && isKernelTerminal(kernelState)) {
        throw new Error('SECURITY: continuationState kernel_state must be nonterminal');
      }
      if (kernelStateIsObject && Object.hasOwn(kernelState, '_remaining')) {
        if (kernelState._mode === 'kernel' && kernelState._phase !== 'try') {
          throw new Error('SECURITY: continuationState kernel_state phase mismatch');
        }
        if (kernelState._mode === 'kernel' && muHash(kernelState._input) !== normalizedInputHash) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        if (kernelState._remaining === null) {
          let anyProjectionMatches = false;
          for (const context of projectionContexts) {
            if (context.projectionMatches) {
              anyProjectionMatches = true;
              break;
            }
          }
          if (anyProjectionMatches) {
            throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
          }
        } else {
          continuationCursors.push({
            cursor: kernelState._remaining,
            requirePrefixCleared: true,
          });
        }
      }
      if (kernelStateIsObject && kernelState._match_ctx !== undefined) {
        const matchCtx = kernelState._match_ctx;
        if (matchCtx === null || typeof matchCtx !== 'object' || Array.isArray(matchCtx)) {
          throw new Error('SECURITY: continuationState _match_ctx must be a Mu object');
        }
        keys = Object.keys(matchCtx).sort();
        if (keys.length !== 3 || keys[0] !== '_body' || keys[1] !== '_input' || keys[2] !== '_remaining') {
          throw new Error('SECURITY: continuationState _match_ctx key set mismatch');
        }
        if (muHash(matchCtx._input) !== normalizedInputHash) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        continuationCursors.push({
          cursor: matchCtx._remaining,
          requirePrefixCleared: false,
        });
        let expectedMatchStatus = null;
        let expectedBindings = null;
        if (kernelState._mode === 'match_done') {
          if (kernelState._status === 'success') {
            expectedMatchStatus = 'success';
            expectedBindings = kernelState._bindings;
          } else if (kernelState._status === 'no_match') {
            expectedMatchStatus = 'no_match';
          } else {
            throw new Error('SECURITY: continuationState match_done status mismatch');
          }
        }
        bodyRestPairs.push([
          matchCtx._body,
          matchCtx._remaining,
          expectedMatchStatus,
          expectedBindings,
        ]);
        const finalMatchPrecursor =
          kernelState.mode === 'match' &&
          kernelState.pattern_focus === null &&
          kernelState.value_focus === null &&
          kernelState.stack === null;
        const variablePatternFocus =
          kernelState.mode === 'match' &&
          kernelState.pattern_focus !== null &&
          typeof kernelState.pattern_focus === 'object' &&
          !Array.isArray(kernelState.pattern_focus) &&
          Object.keys(kernelState.pattern_focus).length === 1 &&
          typeof kernelState.pattern_focus.var === 'string';
        if (Object.hasOwn(kernelState, 'bindings') &&
            (finalMatchPrecursor || variablePatternFocus)) {
          inProgressMatchChecks.push({
            body: matchCtx._body,
            rest: matchCtx._remaining,
            state: kernelState,
          });
        }
        if (Object.hasOwn(kernelState, 'match')) {
          const matchRequest = kernelState.match;
          if (matchRequest === null || typeof matchRequest !== 'object' || Array.isArray(matchRequest)) {
            throw new Error('SECURITY: continuationState match request must be a Mu object');
          }
          keys = Object.keys(matchRequest).sort();
          if (keys.length !== 2 || keys[0] !== 'pattern' || keys[1] !== 'value') {
            throw new Error('SECURITY: continuationState match request key set mismatch');
          }
          if (muHash(matchRequest.value) !== normalizedInputHash) {
            throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
          }
          patternRestPairs.push([matchRequest.pattern, matchCtx._remaining, true]);
        }
      }
      if (kernelStateIsObject && kernelState._subst_ctx !== undefined) {
        const substCtx = kernelState._subst_ctx;
        if (substCtx === null || typeof substCtx !== 'object' || Array.isArray(substCtx)) {
          throw new Error('SECURITY: continuationState _subst_ctx must be a Mu object');
        }
        keys = Object.keys(substCtx).sort();
        if (keys.length !== 2 || keys[0] !== '_input' || keys[1] !== '_remaining') {
          throw new Error('SECURITY: continuationState _subst_ctx key set mismatch');
        }
        if (muHash(substCtx._input) !== normalizedInputHash) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        continuationCursors.push({
          cursor: substCtx._remaining,
          requirePrefixCleared: false,
        });
        if (Object.hasOwn(kernelState, 'subst')) {
          const substRequest = kernelState.subst;
          if (substRequest === null || typeof substRequest !== 'object' || Array.isArray(substRequest)) {
            throw new Error('SECURITY: continuationState subst request must be a Mu object');
          }
          keys = Object.keys(substRequest).sort();
          if (keys.length !== 2 || keys[0] !== 'bindings' || keys[1] !== 'body') {
            throw new Error('SECURITY: continuationState subst request key set mismatch');
          }
          bodyRestPairs.push([substRequest.body, substCtx._remaining, 'success', substRequest.bindings]);
        } else if (kernelState._mode === 'subst_done') {
          substResultChecks.push([substCtx._remaining, kernelState._result, null, false]);
        } else if (kernelState.mode === 'subst' &&
            kernelState.phase === 'result' &&
            kernelState.context === null) {
          substResultChecks.push([substCtx._remaining, kernelState.focus, kernelState.bindings, true]);
        } else if (kernelState.mode === 'subst') {
          substStateChecks.push([substCtx._remaining, kernelState]);
        }
      }
      for (const cursorBinding of continuationCursors) {
        const cursorCandidate = cursorBinding.cursor;
        if (cursorCandidate === null) {
          continue;
        }
        if (typeof cursorCandidate !== 'object' || Array.isArray(cursorCandidate) ||
            !Object.hasOwn(cursorCandidate, 'head') ||
            !Object.hasOwn(cursorCandidate, 'tail') ||
            Object.keys(cursorCandidate).length !== 2) {
          throw new Error('SECURITY: continuationState kernel projection cursor must be a Mu head/tail list');
        }
        let cursorBound = false;
        let cursorHash = null;
        for (const context of projectionContexts) {
          let cursorMatches = context.projectionCursor === cursorCandidate;
          if (!cursorMatches) {
            if (cursorHash === null) {
              cursorHash = muHash(cursorCandidate);
            }
            cursorMatches = context.cursorHash === cursorHash;
          }
          if (!cursorMatches) {
            continue;
          }
          if (cursorBinding.requirePrefixCleared && !context.prefixCleared) {
            continue;
          }
          cursorBound = true;
          break;
        }
        if (!cursorBound) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
      }
      for (const [bodyValue, restCursor, expectedMatchStatus, expectedBindings] of bodyRestPairs) {
        let bodyBound = false;
        const bodyHash = muHash(bodyValue);
        const restHash = muHash(restCursor);
        for (const context of projectionContexts) {
          const bodyRestMatches =
            (context.projection.body === bodyValue && context.projectionRest === restCursor) ||
            (context.bodyHash === bodyHash && context.restHash === restHash);
          if (!bodyRestMatches) {
            continue;
          }
          if (!context.prefixCleared) {
            continue;
          }
          if (expectedMatchStatus === 'success') {
            if (!context.projectionMatches) {
              continue;
            }
            let bindingsMatch = false;
            if (context.matchBindings !== NO_MATCH &&
                context.matchBindings !== null &&
                typeof context.matchBindings === 'object' &&
                !Array.isArray(context.matchBindings)) {
              const expectedNames = new Set(Object.keys(context.matchBindings));
              if (expectedBindings === null) {
                bindingsMatch = expectedNames.size === 0;
              } else {
                if (expectedBindings === null || typeof expectedBindings !== 'object' || Array.isArray(expectedBindings)) {
                  throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                }
                const bindingKeys = Object.keys(expectedBindings).sort();
                const linkedBinding =
                  bindingKeys.length === 3 &&
                  bindingKeys[0] === 'name' &&
                  bindingKeys[1] === 'rest' &&
                  bindingKeys[2] === 'value';
                bindingsMatch = true;
                if (linkedBinding) {
                  const seenNames = new Set();
                  let bindingCursor = expectedBindings;
                  while (bindingCursor !== null) {
                    if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                      throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                    }
                    keys = Object.keys(bindingCursor).sort();
                    if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                      throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                    }
                    if (typeof bindingCursor.name !== 'string') {
                      throw new Error('SECURITY: continuationState binding name must be string');
                    }
                    if (!Object.hasOwn(context.matchBindings, bindingCursor.name)) {
                      bindingsMatch = false;
                      break;
                    }
                    if (muHash(bindingCursor.value) !== muHash(context.matchBindings[bindingCursor.name])) {
                      bindingsMatch = false;
                      break;
                    }
                    seenNames.add(bindingCursor.name);
                    bindingCursor = bindingCursor.rest;
                  }
                  for (const name of expectedNames) {
                    if (!seenNames.has(name)) {
                      bindingsMatch = false;
                      break;
                    }
                  }
                } else {
                  for (const name of bindingKeys) {
                    if (!Object.hasOwn(context.matchBindings, name)) {
                      bindingsMatch = false;
                      break;
                    }
                    if (muHash(expectedBindings[name]) !== muHash(context.matchBindings[name])) {
                      bindingsMatch = false;
                      break;
                    }
                  }
                  if (bindingsMatch) {
                    for (const name of expectedNames) {
                      if (!Object.hasOwn(expectedBindings, name)) {
                        bindingsMatch = false;
                        break;
                      }
                    }
                  }
                }
              }
            }
            if (!bindingsMatch) {
              continue;
            }
          } else if (expectedMatchStatus === 'no_match' && context.projectionMatches) {
            continue;
          }
          bodyBound = true;
          break;
        }
        if (!bodyBound) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
      }
      for (const check of inProgressMatchChecks) {
        let matchStateBound = false;
        const bodyHash = muHash(check.body);
        const restHash = muHash(check.rest);
        const state = check.state;
        const requireExactBindings =
          state.pattern_focus === null &&
          state.value_focus === null &&
          state.stack === null;
        let patternVarName = null;
        if (state.pattern_focus !== null &&
            typeof state.pattern_focus === 'object' &&
            !Array.isArray(state.pattern_focus)) {
          const patternFocusKeys = Object.keys(state.pattern_focus);
          if (patternFocusKeys.length === 1 &&
              patternFocusKeys[0] === 'var' &&
              typeof state.pattern_focus.var === 'string') {
            patternVarName = state.pattern_focus.var;
          }
        }
        for (const context of projectionContexts) {
          const bodyRestMatches =
            (context.projection.body === check.body && context.projectionRest === check.rest) ||
            (context.bodyHash === bodyHash && context.restHash === restHash);
          if (!bodyRestMatches || !context.prefixCleared) {
            continue;
          }
          if (!context.projectionMatches) {
            matchStateBound = true;
            break;
          }
          const expectedBindings = context.matchBindings;
          if (expectedBindings === NO_MATCH ||
              expectedBindings === null ||
              typeof expectedBindings !== 'object' ||
              Array.isArray(expectedBindings)) {
            continue;
          }
          const expectedNames = new Set(Object.keys(expectedBindings));
          let bindingsMatch = true;
          if (state.bindings === null) {
            bindingsMatch = !requireExactBindings || expectedNames.size === 0;
          } else {
            if (state.bindings === null || typeof state.bindings !== 'object' || Array.isArray(state.bindings)) {
              throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
            }
            const bindingKeys = Object.keys(state.bindings).sort();
            const linkedBinding =
              bindingKeys.length === 3 &&
              bindingKeys[0] === 'name' &&
              bindingKeys[1] === 'rest' &&
              bindingKeys[2] === 'value';
            if (linkedBinding) {
              const seenNames = new Set();
              let bindingCursor = state.bindings;
              while (bindingCursor !== null) {
                if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                  throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                }
                keys = Object.keys(bindingCursor).sort();
                if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                  throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                }
                if (typeof bindingCursor.name !== 'string') {
                  throw new Error('SECURITY: continuationState binding name must be string');
                }
                if (!Object.hasOwn(expectedBindings, bindingCursor.name)) {
                  bindingsMatch = false;
                  break;
                }
                if (muHash(bindingCursor.value) !== muHash(expectedBindings[bindingCursor.name])) {
                  bindingsMatch = false;
                  break;
                }
                seenNames.add(bindingCursor.name);
                bindingCursor = bindingCursor.rest;
              }
              if (bindingsMatch && requireExactBindings) {
                for (const name of expectedNames) {
                  if (!seenNames.has(name)) {
                    bindingsMatch = false;
                    break;
                  }
                }
              }
            } else {
              for (const name of bindingKeys) {
                if (!Object.hasOwn(expectedBindings, name)) {
                  bindingsMatch = false;
                  break;
                }
                if (muHash(state.bindings[name]) !== muHash(expectedBindings[name])) {
                  bindingsMatch = false;
                  break;
                }
              }
              if (bindingsMatch && requireExactBindings) {
                for (const name of expectedNames) {
                  if (!Object.hasOwn(state.bindings, name)) {
                    bindingsMatch = false;
                    break;
                  }
                }
              }
            }
          }
          if (!bindingsMatch) {
            continue;
          }
          if (patternVarName !== null) {
            if (!Object.hasOwn(expectedBindings, patternVarName)) {
              continue;
            }
            if (muHash(state.value_focus) !== muHash(expectedBindings[patternVarName])) {
              continue;
            }
          }
          matchStateBound = true;
          break;
        }
        if (!matchStateBound) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
      }
      for (const [restCursor, actualResult, actualBindings, requireBindings] of substResultChecks) {
        let resultBound = false;
        const restHash = muHash(restCursor);
        for (const context of projectionContexts) {
          if (context.restHash !== restHash || !context.prefixCleared || !context.projectionMatches) {
            continue;
          }
          if (requireBindings) {
            const expectedBindings = context.matchBindings;
            if (expectedBindings === NO_MATCH ||
                expectedBindings === null ||
                typeof expectedBindings !== 'object' ||
                Array.isArray(expectedBindings)) {
              continue;
            }
            const expectedNames = new Set(Object.keys(expectedBindings));
            let bindingsMatch = false;
            if (actualBindings === null) {
              bindingsMatch = expectedNames.size === 0;
            } else {
              if (actualBindings === null || typeof actualBindings !== 'object' || Array.isArray(actualBindings)) {
                throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
              }
              const bindingKeys = Object.keys(actualBindings).sort();
              const linkedBinding =
                bindingKeys.length === 3 &&
                bindingKeys[0] === 'name' &&
                bindingKeys[1] === 'rest' &&
                bindingKeys[2] === 'value';
              bindingsMatch = true;
              if (linkedBinding) {
                const seenNames = new Set();
                let bindingCursor = actualBindings;
                while (bindingCursor !== null) {
                  if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                    throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                  }
                  keys = Object.keys(bindingCursor).sort();
                  if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                    throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                  }
                  if (typeof bindingCursor.name !== 'string') {
                    throw new Error('SECURITY: continuationState binding name must be string');
                  }
                  if (!Object.hasOwn(expectedBindings, bindingCursor.name)) {
                    bindingsMatch = false;
                    break;
                  }
                  if (muHash(bindingCursor.value) !== muHash(expectedBindings[bindingCursor.name])) {
                    bindingsMatch = false;
                    break;
                  }
                  seenNames.add(bindingCursor.name);
                  bindingCursor = bindingCursor.rest;
                }
                for (const name of expectedNames) {
                  if (!seenNames.has(name)) {
                    bindingsMatch = false;
                    break;
                  }
                }
              } else {
                for (const name of bindingKeys) {
                  if (!Object.hasOwn(expectedBindings, name)) {
                    bindingsMatch = false;
                    break;
                  }
                  if (muHash(actualBindings[name]) !== muHash(expectedBindings[name])) {
                    bindingsMatch = false;
                    break;
                  }
                }
                if (bindingsMatch) {
                  for (const name of expectedNames) {
                    if (!Object.hasOwn(actualBindings, name)) {
                      bindingsMatch = false;
                      break;
                    }
                  }
                }
              }
            }
            if (!bindingsMatch) {
              continue;
            }
          }
          let expectedResult = null;
          try {
            expectedResult = stage0Substitute(context.projection.body, context.matchBindings);
          } catch (error) {
            const prefix = 'Unbound variable: ';
            if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
              throw error;
            }
            expectedResult = muContainers.record([
              ['_error', 'unbound_variable'],
              ['_name', error.message.slice(prefix.length)],
            ]);
          }
          if (muHash(actualResult) === muHash(expectedResult)) {
            resultBound = true;
            break;
          }
        }
        if (!resultBound) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
      }
      for (const [restCursor, substState] of substStateChecks) {
        let substStateBound = false;
        const restHash = muHash(restCursor);
        for (const context of projectionContexts) {
          if (context.restHash !== restHash || !context.prefixCleared || !context.projectionMatches) {
            continue;
          }
          const expectedBindings = context.matchBindings;
          if (expectedBindings === NO_MATCH ||
              expectedBindings === null ||
              typeof expectedBindings !== 'object' ||
              Array.isArray(expectedBindings)) {
            continue;
          }
          const actualBindings = substState.bindings;
          const expectedNames = new Set(Object.keys(expectedBindings));
          let bindingsMatch = false;
          if (actualBindings === null) {
            bindingsMatch = expectedNames.size === 0;
          } else {
            if (actualBindings === null || typeof actualBindings !== 'object' || Array.isArray(actualBindings)) {
              throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
            }
            const bindingKeys = Object.keys(actualBindings).sort();
            const linkedBinding =
              bindingKeys.length === 3 &&
              bindingKeys[0] === 'name' &&
              bindingKeys[1] === 'rest' &&
              bindingKeys[2] === 'value';
            bindingsMatch = true;
            if (linkedBinding) {
              const seenNames = new Set();
              let bindingCursor = actualBindings;
              while (bindingCursor !== null) {
                if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                  throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                }
                keys = Object.keys(bindingCursor).sort();
                if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                  throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                }
                if (typeof bindingCursor.name !== 'string') {
                  throw new Error('SECURITY: continuationState binding name must be string');
                }
                if (!Object.hasOwn(expectedBindings, bindingCursor.name)) {
                  bindingsMatch = false;
                  break;
                }
                if (muHash(bindingCursor.value) !== muHash(expectedBindings[bindingCursor.name])) {
                  bindingsMatch = false;
                  break;
                }
                seenNames.add(bindingCursor.name);
                bindingCursor = bindingCursor.rest;
              }
              for (const name of expectedNames) {
                if (!seenNames.has(name)) {
                  bindingsMatch = false;
                  break;
                }
              }
            } else {
              for (const name of bindingKeys) {
                if (!Object.hasOwn(expectedBindings, name)) {
                  bindingsMatch = false;
                  break;
                }
                if (muHash(actualBindings[name]) !== muHash(expectedBindings[name])) {
                  bindingsMatch = false;
                  break;
                }
              }
              if (bindingsMatch) {
                for (const name of expectedNames) {
                  if (!Object.hasOwn(actualBindings, name)) {
                    bindingsMatch = false;
                    break;
                  }
                }
              }
            }
          }
          if (!bindingsMatch) {
            continue;
          }
          let expectedResult = null;
          try {
            expectedResult = stage0Substitute(context.projection.body, expectedBindings);
          } catch (error) {
            const prefix = 'Unbound variable: ';
            if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
              throw error;
            }
            expectedResult = muContainers.record([
              ['_error', 'unbound_variable'],
              ['_name', error.message.slice(prefix.length)],
            ]);
          }
          let actualCompletion = null;
          if (substState.phase === 'traverse') {
            if (substState.context === null &&
                muHash(substState.focus) !== muHash(context.projection.body)) {
              continue;
            }
            try {
              actualCompletion = stage0Substitute(substState.focus, expectedBindings);
            } catch (error) {
              const prefix = 'Unbound variable: ';
              if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
                throw error;
              }
              actualCompletion = muContainers.record([
                ['_error', 'unbound_variable'],
                ['_name', error.message.slice(prefix.length)],
              ]);
            }
          } else if (substState.phase === 'lookup') {
            if (typeof substState.lookup_name !== 'string') {
              throw new Error('SECURITY: continuationState lookup_name must be string');
            }
            const lookupVar = muContainers.record([['var', substState.lookup_name]]);
            if (substState.context === null &&
                muHash(lookupVar) !== muHash(context.projection.body)) {
              continue;
            }
            let lookupSuffixBound = substState.lookup_bindings === null;
            const lookupBindingHash = substState.lookup_bindings === null ? null : muHash(substState.lookup_bindings);
            let suffixProbe = actualBindings;
            while (suffixProbe !== null) {
              if (suffixProbe === null || typeof suffixProbe !== 'object' || Array.isArray(suffixProbe)) {
                throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
              }
              keys = Object.keys(suffixProbe).sort();
              if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                throw new Error('SECURITY: continuationState binding cursor key set mismatch');
              }
              if (lookupBindingHash !== null && muHash(suffixProbe) === lookupBindingHash) {
                lookupSuffixBound = true;
                break;
              }
              suffixProbe = suffixProbe.rest;
            }
            if (!lookupSuffixBound) {
              continue;
            }
            let lookupCursor = substState.lookup_bindings;
            let lookupFound = false;
            while (lookupCursor !== null) {
              if (lookupCursor === null || typeof lookupCursor !== 'object' || Array.isArray(lookupCursor)) {
                throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
              }
              keys = Object.keys(lookupCursor).sort();
              if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                throw new Error('SECURITY: continuationState binding cursor key set mismatch');
              }
              if (typeof lookupCursor.name !== 'string') {
                throw new Error('SECURITY: continuationState binding name must be string');
              }
              if (lookupCursor.name === substState.lookup_name) {
                actualCompletion = lookupCursor.value;
                lookupFound = true;
                break;
              }
              lookupCursor = lookupCursor.rest;
            }
            if (!lookupFound) {
              actualCompletion = muContainers.record([
                ['_error', 'unbound_variable'],
                ['_name', substState.lookup_name],
              ]);
            }
          } else if (substState.phase === 'result') {
            actualCompletion = substState.focus;
          } else {
            throw new Error('SECURITY: continuationState kernel_state phase mismatch');
          }
          let substContextCursor = substState.context;
          while (substContextCursor !== null) {
            if (substContextCursor === null ||
                typeof substContextCursor !== 'object' ||
                Array.isArray(substContextCursor)) {
              throw new Error('SECURITY: continuationState subst context must be a Mu object or null');
            }
            keys = Object.keys(substContextCursor).sort();
            if (keys.length !== 2 || keys[0] !== 'head' || keys[1] !== 'tail') {
              throw new Error('SECURITY: continuationState subst context key set mismatch');
            }
            const substFrame = substContextCursor.head;
            if (substFrame === null || typeof substFrame !== 'object' || Array.isArray(substFrame)) {
              throw new Error('SECURITY: continuationState subst context frame must be a Mu object');
            }
            const frameType = substFrame.type;
            if (frameType === 'head_done') {
              keys = Object.keys(substFrame).sort();
              if (keys.length !== 2 || keys[0] !== 'tail' || keys[1] !== 'type') {
                throw new Error('SECURITY: continuationState subst context frame key set mismatch');
              }
              let tailCompletion = null;
              try {
                tailCompletion = stage0Substitute(substFrame.tail, expectedBindings);
              } catch (error) {
                const prefix = 'Unbound variable: ';
                if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
                  throw error;
                }
                tailCompletion = muContainers.record([
                  ['_error', 'unbound_variable'],
                  ['_name', error.message.slice(prefix.length)],
                ]);
              }
              actualCompletion = muContainers.record([
                ['head', actualCompletion],
                ['tail', tailCompletion],
              ]);
            } else if (frameType === 'tail_done') {
              keys = Object.keys(substFrame).sort();
              if (keys.length !== 2 || keys[0] !== 'head_result' || keys[1] !== 'type') {
                throw new Error('SECURITY: continuationState subst context frame key set mismatch');
              }
              actualCompletion = muContainers.record([
                ['head', substFrame.head_result],
                ['tail', actualCompletion],
              ]);
            } else if (frameType === 'typed_head_done') {
              keys = Object.keys(substFrame).sort();
              if (keys.length !== 3 || keys[0] !== '_type' || keys[1] !== 'tail' || keys[2] !== 'type') {
                throw new Error('SECURITY: continuationState subst context frame key set mismatch');
              }
              let tailCompletion = null;
              try {
                tailCompletion = stage0Substitute(substFrame.tail, expectedBindings);
              } catch (error) {
                const prefix = 'Unbound variable: ';
                if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
                  throw error;
                }
                tailCompletion = muContainers.record([
                  ['_error', 'unbound_variable'],
                  ['_name', error.message.slice(prefix.length)],
                ]);
              }
              actualCompletion = muContainers.record([
                ['_type', substFrame._type],
                ['head', actualCompletion],
                ['tail', tailCompletion],
              ]);
            } else if (frameType === 'typed_tail_done') {
              keys = Object.keys(substFrame).sort();
              if (keys.length !== 3 || keys[0] !== '_type' || keys[1] !== 'head_result' || keys[2] !== 'type') {
                throw new Error('SECURITY: continuationState subst context frame key set mismatch');
              }
              actualCompletion = muContainers.record([
                ['_type', substFrame._type],
                ['head', substFrame.head_result],
                ['tail', actualCompletion],
              ]);
            } else {
              throw new Error('SECURITY: continuationState subst context frame type mismatch');
            }
            substContextCursor = substContextCursor.tail;
          }
          if (muHash(actualCompletion) === muHash(expectedResult)) {
            substStateBound = true;
            break;
          }
        }
        if (!substStateBound) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
      }
      for (const [patternValue, restCursor, requirePrefixCleared] of patternRestPairs) {
        let patternBound = false;
        const patternHash = muHash(patternValue);
        const restHash = muHash(restCursor);
        for (const context of projectionContexts) {
          const patternRestMatches =
            (context.projection.pattern === patternValue && context.projectionRest === restCursor) ||
            (context.patternHash === patternHash && context.restHash === restHash);
          if (!patternRestMatches) {
            continue;
          }
          if (requirePrefixCleared && !context.prefixCleared) {
            continue;
          }
          patternBound = true;
          break;
        }
        if (!patternBound) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
      }
    } else if (useDomainValidation) {
      const projectionHashes = new Set();
      const bodyHashes = new Set();
      const projectionContexts = [];
      const useVmMatchValidation = Boolean(vmConfig && vmConfig.matchBundle);
      let prefixHasMatch = false;
      let projectionAuthorityCursor = kernelInput._projs;
      while (projectionAuthorityCursor !== null) {
        if (typeof projectionAuthorityCursor !== 'object' || Array.isArray(projectionAuthorityCursor) ||
            !Object.hasOwn(projectionAuthorityCursor, 'head') ||
            !Object.hasOwn(projectionAuthorityCursor, 'tail') ||
            Object.keys(projectionAuthorityCursor).length !== 2) {
          throw new Error('SECURITY: kernel projection cursor must be a Mu head/tail linked list');
        }
        const projectionAuthority = projectionAuthorityCursor.head;
        if (projectionAuthority === null || typeof projectionAuthority !== 'object' ||
            Array.isArray(projectionAuthority) ||
            !Object.hasOwn(projectionAuthority, 'pattern') ||
            !Object.hasOwn(projectionAuthority, 'body') ||
            Object.keys(projectionAuthority).length !== 2) {
          throw new Error('SECURITY: kernel projection cursor head must be a normalized projection');
        }
        projectionHashes.add(muHash(projectionAuthority));
        bodyHashes.add(muHash(projectionAuthority.body));
        let matchResult = null;
        let legacyMatchBindings = NO_MATCH;
        if (useVmMatchValidation) {
          const matchOutcome = _stage0VmRunTrusted(vmConfig.matchBundle, muContainers.record([
            ['match', muContainers.record([
              ['pattern', projectionAuthority.pattern],
              ['value', kernelInput._step],
            ])],
            ['_match_ctx', muContainers.record([
              ['_input', kernelInput._step],
              ['_body', projectionAuthority.body],
              ['_remaining', projectionAuthorityCursor.tail],
            ])],
          ]), 100);
          matchResult = matchOutcome.root;
        } else {
          legacyMatchBindings = stage0Match(projectionAuthority.pattern, kernelInput._step, null);
        }
        projectionContexts.push({
          projection: projectionAuthority,
          projectionRest: projectionAuthorityCursor.tail,
          bodyHash: muHash(projectionAuthority.body),
          restHash: muHash(projectionAuthorityCursor.tail),
          cursorHash: muHash(projectionAuthorityCursor),
          prefixCleared: !prefixHasMatch,
          matchResult,
          legacyMatchBindings,
        });
        const projectionMatches = useVmMatchValidation
          ? matchResult !== null && typeof matchResult === 'object' && !Array.isArray(matchResult) &&
              matchResult._mode === 'match_done' && matchResult._status === 'success'
          : legacyMatchBindings !== NO_MATCH;
        if (projectionMatches) {
          prefixHasMatch = true;
        }
        projectionAuthorityCursor = projectionAuthorityCursor.tail;
      }
      const exhaustedPrefixCleared = !prefixHasMatch;
      const enforcePrefixCleared = true;
    if (!kernelStateIsObject) {
      // Scalar Mu states can only come from the defensive hash-stall path:
      // they carry no projection authority and must resume as cursorless,
      // already-progressed continuations.
      if (continuationState.projection_cursor !== null) {
        throw new Error('SECURITY: continuationState projection_cursor is not bound to kernel_state');
      }
      if (continuationState.steps_used === 0) {
        throw new Error('SECURITY: continuationState steps_used is not bound to kernel_state phase');
      }
      if (continuationState.steps_used >= watchdogCap) {
        throw new Error('SECURITY: continuationState steps_used is not bound to watchdog_cap');
      }
    }
    if (kernelStateIsObject && continuationState.projection_cursor !== null) {
      if (continuationState.projection_cursor.position !== continuationState.steps_used) {
        throw new Error('SECURITY: continuationState steps_used/projection_cursor mismatch');
      }
      if (!Object.hasOwn(kernelState, '_remaining')) {
        throw new Error('SECURITY: continuationState projection_cursor is not bound to kernel_state');
      }
      if (continuationState.projection_cursor.exhausted !== (kernelState._remaining === null)) {
        throw new Error('SECURITY: continuationState projection_cursor exhausted mismatch');
      }
    } else if (kernelStateIsObject && Object.hasOwn(kernelState, '_remaining')) {
      throw new Error('SECURITY: continuationState projection_cursor missing for kernel projection state');
    }
    if (kernelStateIsObject && isKernelTerminal(kernelState)) {
      throw new Error('SECURITY: continuationState kernel_state must be nonterminal');
    }
    if (kernelState !== null && typeof kernelState === 'object' && !Array.isArray(kernelState) &&
        kernelState._mode === 'kernel' && kernelState._phase === 'try') {
      if (!Object.hasOwn(kernelState, '_remaining')) {
        throw new Error('SECURITY: continuationState kernel_state key set mismatch');
      }
      const remainingCursor = kernelState._remaining;
      let remainingCursorBound = false;
      if (remainingCursor === null) {
        remainingCursorBound = exhaustedPrefixCleared;
      } else {
        if (typeof remainingCursor !== 'object' || Array.isArray(remainingCursor) ||
            !Object.hasOwn(remainingCursor, 'head') ||
            !Object.hasOwn(remainingCursor, 'tail') ||
            Object.keys(remainingCursor).length !== 2) {
          throw new Error('SECURITY: continuationState kernel projection cursor must be a Mu head/tail list');
        }
        const remainingCursorHash = muHash(remainingCursor);
        for (const context of projectionContexts) {
          if (context.cursorHash === remainingCursorHash &&
              (!enforcePrefixCleared || context.prefixCleared)) {
            remainingCursorBound = true;
            break;
          }
        }
      }
      if (!remainingCursorBound) {
        throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
      }
    }
    if (kernelState !== null && typeof kernelState === 'object' && !Array.isArray(kernelState)) {
      const matchCtx = kernelState._match_ctx;
      if (matchCtx !== undefined) {
        if (matchCtx === null || typeof matchCtx !== 'object' || Array.isArray(matchCtx)) {
          throw new Error('SECURITY: continuationState _match_ctx must be a Mu object');
        }
        keys = Object.keys(matchCtx).sort();
        if (keys.length !== 3 || keys[0] !== '_body' || keys[1] !== '_input' || keys[2] !== '_remaining') {
          throw new Error('SECURITY: continuationState _match_ctx key set mismatch');
        }
        if (muHash(matchCtx._input) !== normalizedInputHash) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        const matchCandidates = [];
        const matchRestHash = muHash(matchCtx._remaining);
        const matchBodyHash = muHash(matchCtx._body);
        for (const context of projectionContexts) {
          if (context.restHash === matchRestHash &&
              context.bodyHash === matchBodyHash &&
              (!enforcePrefixCleared || context.prefixCleared)) {
            matchCandidates.push(context);
          }
        }
        if (matchCandidates.length === 0) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        if (Object.hasOwn(kernelState, 'match')) {
          const matchRequest = kernelState.match;
          if (matchRequest === null || typeof matchRequest !== 'object' || Array.isArray(matchRequest)) {
            throw new Error('SECURITY: continuationState match request must be a Mu object');
          }
          keys = Object.keys(matchRequest).sort();
          if (keys.length !== 2 || keys[0] !== 'pattern' || keys[1] !== 'value') {
            throw new Error('SECURITY: continuationState match request key set mismatch');
          }
          let requestPatternBound = false;
          for (const context of matchCandidates) {
            if (muHash(matchRequest.pattern) === muHash(context.projection.pattern)) {
              requestPatternBound = true;
              break;
            }
          }
          if (!requestPatternBound) {
            throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
          }
          if (muHash(matchRequest.value) !== normalizedInputHash) {
            throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
          }
        }
        if (useDomainValidation &&
            kernelState.mode === 'match' &&
            kernelState.pattern_focus === null &&
            kernelState.value_focus === null &&
            kernelState.stack === null) {
          let successBoundToInput = false;
          for (const context of matchCandidates) {
            const actualBindings = kernelState.bindings;
            const matchResult = useVmMatchValidation &&
                context.matchResult !== null &&
                typeof context.matchResult === 'object' &&
                !Array.isArray(context.matchResult)
              ? context.matchResult
              : null;
            if (matchResult !== null) {
              if (matchResult._mode !== 'match_done' || matchResult._status !== 'success') {
                continue;
              }
              if (muHash(actualBindings) === muHash(matchResult._bindings)) {
                successBoundToInput = true;
                break;
              }
              continue;
            }
            const expectedBindings = context.legacyMatchBindings;
            if (expectedBindings === NO_MATCH ||
                expectedBindings === null ||
                typeof expectedBindings !== 'object' ||
                Array.isArray(expectedBindings)) {
              continue;
            }
            const expectedNames = new Set(Object.keys(expectedBindings));
            let bindingsMatch = false;
            if (actualBindings === null) {
              bindingsMatch = expectedNames.size === 0;
            } else {
              bindingsMatch = true;
              const seenNames = new Set();
              let bindingCursor = actualBindings;
              while (bindingCursor !== null) {
                if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                  throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                }
                keys = Object.keys(bindingCursor).sort();
                if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                  throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                }
                if (typeof bindingCursor.name !== 'string') {
                  throw new Error('SECURITY: continuationState binding name must be string');
                }
                if (!Object.hasOwn(expectedBindings, bindingCursor.name)) {
                  bindingsMatch = false;
                  break;
                }
                if (muHash(bindingCursor.value) !== muHash(expectedBindings[bindingCursor.name])) {
                  bindingsMatch = false;
                  break;
                }
                seenNames.add(bindingCursor.name);
                bindingCursor = bindingCursor.rest;
              }
              for (const name of expectedNames) {
                if (!seenNames.has(name)) {
                  bindingsMatch = false;
                  break;
                }
              }
            }
            if (bindingsMatch) {
              successBoundToInput = true;
              break;
            }
          }
          if (!successBoundToInput) {
            throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
          }
        }
        if (kernelState._mode === 'match_done') {
          if (kernelState._status === 'success' && useDomainValidation) {
            let successBoundToInput = false;
            for (const context of matchCandidates) {
              const actualBindings = kernelState._bindings;
              const matchResult = useVmMatchValidation &&
                  context.matchResult !== null &&
                  typeof context.matchResult === 'object' &&
                  !Array.isArray(context.matchResult)
                ? context.matchResult
                : null;
              if (matchResult !== null) {
                if (matchResult._mode !== 'match_done' || matchResult._status !== 'success') {
                  continue;
                }
                if (muHash(actualBindings) === muHash(matchResult._bindings)) {
                  successBoundToInput = true;
                  break;
                }
              } else {
                const expectedBindings = context.legacyMatchBindings;
                if (expectedBindings === NO_MATCH ||
                    expectedBindings === null ||
                    typeof expectedBindings !== 'object' ||
                    Array.isArray(expectedBindings)) {
                  continue;
                }
                const expectedNames = new Set(Object.keys(expectedBindings));
                let bindingsMatch = false;
                if (actualBindings === null) {
                  bindingsMatch = expectedNames.size === 0;
                } else {
                  bindingsMatch = true;
                  const seenNames = new Set();
                  let bindingCursor = actualBindings;
                  while (bindingCursor !== null) {
                    if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                      throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                    }
                    keys = Object.keys(bindingCursor).sort();
                    if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                      throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                    }
                    if (typeof bindingCursor.name !== 'string') {
                      throw new Error('SECURITY: continuationState binding name must be string');
                    }
                    if (!Object.hasOwn(expectedBindings, bindingCursor.name)) {
                      bindingsMatch = false;
                      break;
                    }
                    if (muHash(bindingCursor.value) !== muHash(expectedBindings[bindingCursor.name])) {
                      bindingsMatch = false;
                      break;
                    }
                    seenNames.add(bindingCursor.name);
                    bindingCursor = bindingCursor.rest;
                  }
                  for (const name of expectedNames) {
                    if (!seenNames.has(name)) {
                      bindingsMatch = false;
                      break;
                    }
                  }
                }
                if (bindingsMatch) {
                  successBoundToInput = true;
                  break;
                }
              }
            }
            if (!successBoundToInput) {
              throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
            }
          } else if (kernelState._status === 'success') {
            // Algorithm-runtime continuations are trusted Mu state: shape and
            // cursor authority are checked above, while domain binding proof is
            // intentionally limited to domain validation mode.
          } else if (kernelState._status === 'no_match') {
            if (useDomainValidation) {
              for (const context of matchCandidates) {
                const matchResult = useVmMatchValidation &&
                    context.matchResult !== null &&
                    typeof context.matchResult === 'object' &&
                    !Array.isArray(context.matchResult)
                  ? context.matchResult
                  : null;
                if (matchResult !== null) {
                  if (matchResult._mode === 'match_done' && matchResult._status === 'success') {
                    throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
                  }
                } else if (context.legacyMatchBindings !== NO_MATCH) {
                  throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
                }
              }
            }
          } else {
            throw new Error('SECURITY: continuationState match_done status mismatch');
          }
        }
      }

      const substCtx = kernelState._subst_ctx;
      if (substCtx !== undefined) {
        if (substCtx === null || typeof substCtx !== 'object' || Array.isArray(substCtx)) {
          throw new Error('SECURITY: continuationState _subst_ctx must be a Mu object');
        }
        keys = Object.keys(substCtx).sort();
        if (keys.length !== 2 || keys[0] !== '_input' || keys[1] !== '_remaining') {
          throw new Error('SECURITY: continuationState _subst_ctx key set mismatch');
        }
        if (muHash(substCtx._input) !== normalizedInputHash) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        let substBody = null;
        let substBindings = null;
        if (Object.hasOwn(kernelState, 'subst')) {
          const substRequest = kernelState.subst;
          if (substRequest === null || typeof substRequest !== 'object' || Array.isArray(substRequest)) {
            throw new Error('SECURITY: continuationState subst request must be a Mu object');
          }
          keys = Object.keys(substRequest).sort();
          if (keys.length !== 2 || keys[0] !== 'bindings' || keys[1] !== 'body') {
            throw new Error('SECURITY: continuationState subst request key set mismatch');
          }
          substBody = substRequest.body;
          substBindings = substRequest.bindings;
        } else if (Object.hasOwn(kernelState, 'bindings')) {
          substBindings = kernelState.bindings;
        }
        const substCandidates = [];
        const substRestHash = muHash(substCtx._remaining);
        const substBodyHash = substBody === null ? null : muHash(substBody);
        for (const context of projectionContexts) {
          if (context.restHash !== substRestHash) {
            continue;
          }
          if (substBodyHash !== null && context.bodyHash !== substBodyHash) {
            continue;
          }
          if (enforcePrefixCleared && !context.prefixCleared) {
            continue;
          }
          substCandidates.push(context);
        }
        if (substCandidates.length === 0) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        if (useDomainValidation) {
          let substBoundToInput = false;
          for (const context of substCandidates) {
            let expectedBindings = context.legacyMatchBindings;
            let expectedSubst = null;
            if (useVmMatchValidation) {
              const matchResult = useVmMatchValidation &&
                  context.matchResult !== null &&
                  typeof context.matchResult === 'object' &&
                  !Array.isArray(context.matchResult)
                ? context.matchResult
                : null;
              if (matchResult === null ||
                  matchResult._mode !== 'match_done' ||
                  matchResult._status !== 'success') {
                continue;
              }
              expectedBindings = matchResult._bindings;
              const substOutcome = _stage0VmRunTrusted(vmConfig.substBundle, muContainers.record([
                ['subst', muContainers.record([
                  ['body', context.projection.body],
                  ['bindings', expectedBindings],
                ])],
                ['_subst_ctx', muContainers.record([
                  ['_input', kernelInput._step],
                  ['_remaining', context.projectionRest],
                ])],
              ]), 100);
              expectedSubst = substOutcome.root;
              if (expectedSubst === null ||
                  typeof expectedSubst !== 'object' ||
                  Array.isArray(expectedSubst) ||
                  expectedSubst._mode !== 'subst_done') {
                continue;
              }
              if (kernelState._mode === 'subst_done') {
                if (muHash(kernelState._result) === muHash(expectedSubst._result)) {
                  substBoundToInput = true;
                  break;
                }
                continue;
              }
              let bindingsMatch = muHash(substBindings) === muHash(expectedBindings);
              if (bindingsMatch &&
                  kernelState.mode === 'subst' &&
                  kernelState.phase === 'result' &&
                  kernelState.context === null &&
                  muHash(kernelState.focus) !== muHash(expectedSubst._result)) {
                bindingsMatch = false;
              }
              if (bindingsMatch) {
                substBoundToInput = true;
                break;
              }
              continue;
            }
            if (expectedBindings === NO_MATCH ||
                expectedBindings === null ||
                typeof expectedBindings !== 'object' ||
                Array.isArray(expectedBindings)) {
              continue;
            }
            if (kernelState._mode === 'subst_done') {
              let expectedResult = expectedSubst === null ? null : expectedSubst._result;
              if (expectedSubst === null) {
                try {
                  expectedResult = stage0Substitute(context.projection.body, expectedBindings);
                } catch (error) {
                  const prefix = 'Unbound variable: ';
                  if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
                    throw error;
                  }
                  expectedResult = muContainers.record([
                    ['_error', 'unbound_variable'],
                    ['_name', error.message.slice(prefix.length)],
                  ]);
                }
              }
              if (muHash(kernelState._result) === muHash(expectedResult)) {
                substBoundToInput = true;
                break;
              }
              continue;
            }
            const expectedNames = new Set(Object.keys(expectedBindings));
            let bindingsMatch = false;
            if (substBindings === null) {
              bindingsMatch = expectedNames.size === 0;
            } else {
              bindingsMatch = true;
              const seenNames = new Set();
              let bindingCursor = substBindings;
              while (bindingCursor !== null) {
                if (bindingCursor === null || typeof bindingCursor !== 'object' || Array.isArray(bindingCursor)) {
                  throw new Error('SECURITY: continuationState binding cursor must be a Mu object or null');
                }
                keys = Object.keys(bindingCursor).sort();
                if (keys.length !== 3 || keys[0] !== 'name' || keys[1] !== 'rest' || keys[2] !== 'value') {
                  throw new Error('SECURITY: continuationState binding cursor key set mismatch');
                }
                if (typeof bindingCursor.name !== 'string') {
                  throw new Error('SECURITY: continuationState binding name must be string');
                }
                if (!Object.hasOwn(expectedBindings, bindingCursor.name)) {
                  bindingsMatch = false;
                  break;
                }
                if (muHash(bindingCursor.value) !== muHash(expectedBindings[bindingCursor.name])) {
                  bindingsMatch = false;
                  break;
                }
                seenNames.add(bindingCursor.name);
                bindingCursor = bindingCursor.rest;
              }
              for (const name of expectedNames) {
                if (!seenNames.has(name)) {
                  bindingsMatch = false;
                  break;
                }
              }
            }
            if (bindingsMatch &&
                kernelState.mode === 'subst' &&
                kernelState.phase === 'result' &&
                kernelState.context === null) {
              let expectedFocus = expectedSubst === null ? null : expectedSubst._result;
              if (expectedSubst === null) {
                try {
                  expectedFocus = stage0Substitute(context.projection.body, expectedBindings);
                } catch (error) {
                  const prefix = 'Unbound variable: ';
                  if (!error || typeof error.message !== 'string' || !error.message.startsWith(prefix)) {
                    throw error;
                  }
                  expectedFocus = muContainers.record([
                    ['_error', 'unbound_variable'],
                    ['_name', error.message.slice(prefix.length)],
                  ]);
                }
              }
              if (muHash(kernelState.focus) !== muHash(expectedFocus)) {
                bindingsMatch = false;
              }
            }
            if (bindingsMatch) {
              substBoundToInput = true;
              break;
            }
          }
          if (!substBoundToInput) {
            throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
          }
        }
      }
    }
    if (kernelStateIsObject && projectionHashes.size === 0) {
      const expectedEmptyState = muContainers.record([
        ['_mode', 'kernel'],
        ['_phase', 'try'],
        ['_input', kernelInput._step],
        ['_remaining', null],
      ]);
      if (continuationState.steps_used !== 1 || muHash(kernelState) !== muHash(expectedEmptyState)) {
        throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
      }
    } else if (kernelStateIsObject) {
      const stateNodes = [kernelState];
      while (stateNodes.length > 0) {
        const stateNode = stateNodes.pop();
        if (stateNode === null || typeof stateNode !== 'object' || Array.isArray(stateNode)) {
          continue;
        }
        const stateNodeKeys = Object.keys(stateNode);
        if (stateNodeKeys.length === 2 &&
            Object.hasOwn(stateNode, 'pattern') &&
            Object.hasOwn(stateNode, 'body') &&
            !projectionHashes.has(muHash(stateNode))) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        for (const projectionCursorKey of ['_projs', '_remaining']) {
          if (!Object.hasOwn(stateNode, projectionCursorKey)) {
            continue;
          }
          let projectionCursor = stateNode[projectionCursorKey];
          while (projectionCursor !== null) {
            if (typeof projectionCursor !== 'object' || Array.isArray(projectionCursor) ||
                !Object.hasOwn(projectionCursor, 'head') ||
                !Object.hasOwn(projectionCursor, 'tail') ||
                Object.keys(projectionCursor).length !== 2) {
              throw new Error('SECURITY: continuationState kernel projection cursor must be a Mu head/tail list');
            }
            if (!projectionHashes.has(muHash(projectionCursor.head))) {
              throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
            }
            projectionCursor = projectionCursor.tail;
          }
        }
        if (Object.hasOwn(stateNode, '_input') && muHash(stateNode._input) !== normalizedInputHash) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        if (Object.hasOwn(stateNode, '_body') && !bodyHashes.has(muHash(stateNode._body))) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        if (Object.hasOwn(stateNode, 'body') && !Object.hasOwn(stateNode, 'pattern') &&
            !bodyHashes.has(muHash(stateNode.body))) {
          throw new Error('SECURITY: continuationState kernel_state is not bound to supplied projections/input');
        }
        for (const value of Object.values(stateNode)) {
          stateNodes.push(value);
        }
      }
    }
    }
    if (kernelStateIsObject) {
      const kernelStateKeys = Object.keys(kernelState).sort();
      let expectedKernelStateKeys = null;
      if (Object.hasOwn(kernelState, '_mode')) {
        if (kernelState._mode === 'kernel') {
          expectedKernelStateKeys = ['_input', '_mode', '_phase', '_remaining'];
          if (kernelState._phase !== 'try') {
            throw new Error('SECURITY: continuationState kernel_state phase mismatch');
          }
        } else if (kernelState._mode === 'match_done') {
          if (kernelState._status === 'success') {
            expectedKernelStateKeys = ['_bindings', '_match_ctx', '_mode', '_status'];
          } else if (kernelState._status === 'no_match') {
            expectedKernelStateKeys = ['_match_ctx', '_mode', '_status'];
          } else {
            throw new Error('SECURITY: continuationState kernel_state match_done status mismatch');
          }
        } else if (kernelState._mode === 'subst_done') {
          expectedKernelStateKeys = ['_mode', '_result', '_subst_ctx'];
        } else {
          throw new Error('SECURITY: continuationState kernel_state mode mismatch');
        }
      } else if (Object.hasOwn(kernelState, 'mode')) {
        if (kernelState.mode === 'match') {
          expectedKernelStateKeys = kernelState._phase === 'lookup_binding'
            ? ['_lookup_bindings', '_lookup_name', '_lookup_value', '_match_ctx', '_original_bindings', '_phase', 'mode', 'stack']
            : ['_match_ctx', 'bindings', 'mode', 'pattern_focus', 'stack', 'value_focus'];
        } else if (kernelState.mode === 'subst') {
          if (kernelState.phase === 'traverse' || kernelState.phase === 'result') {
            expectedKernelStateKeys = ['_subst_ctx', 'bindings', 'context', 'focus', 'mode', 'phase'];
          } else if (kernelState.phase === 'lookup') {
            expectedKernelStateKeys = ['_subst_ctx', 'bindings', 'context', 'lookup_bindings', 'lookup_name', 'mode', 'phase'];
          } else {
            throw new Error('SECURITY: continuationState kernel_state phase mismatch');
          }
        } else {
          throw new Error('SECURITY: continuationState kernel_state mode mismatch');
        }
      } else if (kernelStateKeys.length === 2 &&
          kernelStateKeys[0] === '_match_ctx' &&
          kernelStateKeys[1] === 'match') {
        expectedKernelStateKeys = ['_match_ctx', 'match'];
      } else if (kernelStateKeys.length === 2 &&
          kernelStateKeys[0] === '_subst_ctx' &&
          kernelStateKeys[1] === 'subst') {
        expectedKernelStateKeys = ['_subst_ctx', 'subst'];
      } else {
        throw new Error('SECURITY: continuationState kernel_state shape mismatch');
      }
      if (kernelStateKeys.length !== expectedKernelStateKeys.length) {
        throw new Error('SECURITY: continuationState kernel_state key set mismatch');
      }
      for (let i = 0; i < kernelStateKeys.length; i++) {
        if (kernelStateKeys[i] !== expectedKernelStateKeys[i]) {
          throw new Error('SECURITY: continuationState kernel_state key set mismatch');
        }
      }
      if (continuationState.projection_cursor === null) {
        let minimumStepsUsed = null;
        if (kernelStateKeys.length === 2 && kernelStateKeys[0] === '_match_ctx' && kernelStateKeys[1] === 'match') {
          minimumStepsUsed = 2;
        } else if (kernelStateKeys.length === 2 && kernelStateKeys[0] === '_subst_ctx' && kernelStateKeys[1] === 'subst') {
          minimumStepsUsed = 5;
        } else if (Object.hasOwn(kernelState, '_mode')) {
          if (kernelState._mode === 'match_done') {
            minimumStepsUsed = 4;
          } else if (kernelState._mode === 'subst_done') {
            minimumStepsUsed = 8;
          }
        } else if (Object.hasOwn(kernelState, 'mode')) {
          if (kernelState.mode === 'match') {
            minimumStepsUsed = 3;
          } else if (kernelState.mode === 'subst') {
            minimumStepsUsed = 6;
          }
        }
        if (minimumStepsUsed !== null && continuationState.steps_used < minimumStepsUsed) {
          throw new Error('SECURITY: continuationState steps_used is not bound to kernel_state phase');
        }
        if (continuationState.steps_used >= watchdogCap) {
          throw new Error('SECURITY: continuationState steps_used is not bound to watchdog_cap');
        }
      }
    }
    const state = continuationState;
    current = state.kernel_state;
    effectiveDomainInput = state.domain_input;
    validator(effectiveDomainInput, 'stepKernel continuation input');
    callerSuppliedFuel = state.fuel_mode === 'explicit';
    fuelCursor = state.remaining_fuel;
    stepsUsed = state.steps_used;
    watchdogCap = state.watchdog_cap === null ? maxSteps : state.watchdog_cap;
  }

  const currentHash = muHashControlCached(current, 'stepKernel');

  if (callerSuppliedFuel && fuelCursor === null) {
    validator(effectiveDomainInput, 'stepKernel output');
    return {
      kind: 'terminal',
      result: {
        output: effectiveDomainInput,
        stall: true,
        termination_reason: 'fuel_exhausted',
        steps_used: stepsUsed,
        max_steps: watchdogCap,
        fuel_supplied: true,
        fuel_remaining: fuelCursor,
        fuel_exhausted: true,
      },
      continuation: null,
    };
  }

  if (stepsUsed >= watchdogCap) {
    validator(effectiveDomainInput, 'stepKernel output');
    const canonical = {
      output: effectiveDomainInput,
      stall: true,
      termination_reason: 'max_steps_exhausted',
      steps_used: stepsUsed,
      max_steps: watchdogCap,
    };
    if (callerSuppliedFuel) {
      canonical.fuel_supplied = true;
      canonical.fuel_remaining = fuelCursor;
      canonical.fuel_exhausted = false;
    }
    return {
      kind: 'terminal',
      result: canonical,
      continuation: null,
    };
  }

  if (callerSuppliedFuel) {
    if (!isValidMu(fuelCursor)) {
      throw new Error('SECURITY: kernelFuel must be valid Mu linked-list data');
    }
    let fuelProbe = fuelCursor;
    while (fuelProbe !== null) {
      if (typeof fuelProbe !== 'object' || Array.isArray(fuelProbe) ||
          !Object.hasOwn(fuelProbe, 'head') || !Object.hasOwn(fuelProbe, 'tail') ||
          Object.keys(fuelProbe).length !== 2) {
        throw new Error('SECURITY: kernelFuel must be a Mu head/tail linked list');
      }
      fuelProbe = fuelProbe.tail;
    }
  }

  let result = undefined;
  if (vmConfig && _STAGE0_VM_CUTOVER) {
    result = _stepKernelWithVM(
      vmConfig.kernelBundle, vmConfig.bridgeBundle,
      vmConfig.matchBundle, vmConfig.substBundle, current);
  } else {
    result = _stepTrusted(kernelProjections, current);
    // P7-d shadow: run VM path too, assert equivalence
    if (vmConfig && _STAGE0_SHADOW_ENABLED) {
      const vmResult = _stepKernelWithVM(
        vmConfig.kernelBundle, vmConfig.bridgeBundle,
        vmConfig.matchBundle, vmConfig.substBundle, current);
      const hostStalled = result === current;
      const vmStalled = vmResult === current;
      if (hostStalled !== vmStalled) {
        throw new Error(
          `P7-d shadow: polarity divergence — hostStalled=${hostStalled}, vmStalled=${vmStalled}`);
      }
      if (!hostStalled && !muDeepEqual(result, vmResult)) {
        throw new Error(
          `P7-d shadow: output divergence`);
      }
    }
  }
  if (callerSuppliedFuel) {
    fuelCursor = fuelCursor.tail;
  }
  stepsUsed++;

  if (isKernelTerminal(result)) {
    const stall = result._stall === true;
    const reason = stall ? 'kernel_stall' : 'projection_applied';
    const output = stall ? effectiveDomainInput : denormalize(result._result);
    validator(output, 'stepKernel output');
    const canonical = {
      output,
      stall,
      termination_reason: reason,
      steps_used: stepsUsed,
      max_steps: watchdogCap,
    };
    if (stall) {
      canonical.undefined_motif = makeUndefinedMotif('kernel', effectiveDomainInput, null, 'no_matching_projection');
    }
    if (callerSuppliedFuel) {
      canonical.fuel_supplied = true;
      canonical.fuel_remaining = fuelCursor;
      canonical.fuel_exhausted = false;
    }
    return {
      kind: 'terminal',
      result: canonical,
      continuation: null,
    };
  }

  if (result !== null && typeof result === 'object' && !Array.isArray(result) &&
      result._mode === 'kernel' &&
      result._phase === 'try' &&
      result._remaining === null) {
    validator(effectiveDomainInput, 'stepKernel output');
    const canonical = {
      output: effectiveDomainInput,
      stall: true,
      termination_reason: 'kernel_stall',
      steps_used: stepsUsed,
      max_steps: watchdogCap,
      undefined_motif: makeUndefinedMotif('kernel', effectiveDomainInput, null, 'no_matching_projection'),
    };
    if (callerSuppliedFuel) {
      canonical.fuel_supplied = true;
      canonical.fuel_remaining = fuelCursor;
      canonical.fuel_exhausted = false;
    }
    return {
      kind: 'terminal',
      result: canonical,
      continuation: null,
    };
  }

  if (!isKernelIntermediate(result)) {
    const resultHash = muHashControlCached(result, 'stepKernel.stall');
    if (resultHash === currentHash) {
      validator(effectiveDomainInput, 'stepKernel output');
      const canonical = {
        output: effectiveDomainInput,
        stall: true,
        termination_reason: 'hash_stall',
        steps_used: stepsUsed,
        max_steps: watchdogCap,
      };
      if (callerSuppliedFuel) {
        canonical.fuel_supplied = true;
        canonical.fuel_remaining = fuelCursor;
        canonical.fuel_exhausted = false;
      }
      return {
        kind: 'terminal',
        result: canonical,
        continuation: null,
      };
    }
  }

  if (callerSuppliedFuel && fuelCursor === null) {
    validator(effectiveDomainInput, 'stepKernel output');
    return {
      kind: 'terminal',
      result: {
        output: effectiveDomainInput,
        stall: true,
        termination_reason: 'fuel_exhausted',
        steps_used: stepsUsed,
        max_steps: watchdogCap,
        fuel_supplied: true,
        fuel_remaining: fuelCursor,
        fuel_exhausted: true,
      },
      continuation: null,
    };
  }

  if (stepsUsed >= watchdogCap) {
    validator(effectiveDomainInput, 'stepKernel output');
    const canonical = {
      output: effectiveDomainInput,
      stall: true,
      termination_reason: 'max_steps_exhausted',
      steps_used: stepsUsed,
      max_steps: watchdogCap,
    };
    if (callerSuppliedFuel) {
      canonical.fuel_supplied = true;
      canonical.fuel_remaining = fuelCursor;
      canonical.fuel_exhausted = false;
    }
    return {
      kind: 'terminal',
      result: canonical,
      continuation: null,
    };
  }

  let projectionCursor = null;
  if (result !== null && typeof result === 'object' && !Array.isArray(result) && Object.hasOwn(result, '_remaining')) {
    projectionCursor = muContainers.record([
      ['tag', 'kernel_projection_cursor'],
      ['version', 1],
      ['position', stepsUsed],
      ['exhausted', result._remaining === null],
    ]);
  }
  const continuation = muContainers.record([
    ['tag', 'kernel_driver_continuation_state'],
    ['version', 1],
    ['kernel_state', result],
    ['domain_input', effectiveDomainInput],
    ['projection_cursor', projectionCursor],
    ['remaining_fuel', callerSuppliedFuel ? fuelCursor : null],
    ['fuel_mode', callerSuppliedFuel ? 'explicit' : 'omitted_compatibility'],
    ['steps_used', stepsUsed],
    ['watchdog_cap', watchdogCap],
    ['terminal', muContainers.record([
      ['reached', false],
      ['reason', null],
      ['error', null],
    ])],
  ]);
  return {
    kind: 'continuation',
    result: null,
    continuation,
    continuationProof: Object.freeze({
      _token: KERNEL_CONTINUATION_PROOF_TOKEN,
      continuation,
      domainInput: effectiveDomainInput,
      normalizedInput: kernelInput._step,
      projectionAuthority: kernelInput._projs,
      watchdogCap,
    }),
  };
}

// _stepKernelCoreNonMeta DELETED (Wave 1).
// Replaced by _stepKernelCore + public adapter shim in stepKernel().
// All internal callers now use _stepKernelCore directly.

/**
 * BOOTSTRAP PRIMITIVE: Kernel entry point with security validation.
 * Validates domain input before wrapping with kernel state.
 */
function stepKernel(projections, domainInput, domainProjections, options = {}) {
  const {
    maxSteps = 10000,
    shouldNormalize = true,
    validationMode = 'domain',
    returnMeta = false,
    returnPacket = false,
    kernelFuel = undefined,
    continuationState = null,
  } = options;
  const hasKernelFuel = Object.hasOwn(options, 'kernelFuel');
  if (typeof maxSteps !== 'number' || !Number.isFinite(maxSteps) || !Number.isInteger(maxSteps)) {
    throw new RcxError(
      'api.bad_request',
      `maxSteps must be a finite integer watchdog, got ${typeof maxSteps}`
    );
  }
  if (maxSteps < 0) {
    throw new RcxError('api.bad_request', `maxSteps must be >= 0, got ${maxSteps}`);
  }

  let validator;
  if (validationMode === 'domain') {
    validator = validateNoKernelReservedFields;
  } else if (validationMode === 'algorithm_runtime') {
    validator = validateAlgorithmRuntimeFields;
  } else {
    throw new Error(
      `SECURITY: invalid validationMode '${validationMode}'. ` +
      `Expected 'domain' or 'algorithm_runtime'.`
    );
  }

  // SECURITY: Validate input and projection payloads at selected boundary mode.
  validator(domainInput, 'domainInput');
  for (let i = 0; i < domainProjections.length; i++) {
    const proj = domainProjections[i];
    if (proj === null || typeof proj !== 'object' || Array.isArray(proj)) {
      throw new Error(
        `SECURITY: domainProjections[${i}] must be an object, got ${proj === null ? 'null' : Array.isArray(proj) ? 'array' : typeof proj}`
      );
    }
    if (!('pattern' in proj)) {
      throw new Error(`SECURITY: domainProjections[${i}] missing required 'pattern' key`);
    }
    if (!('body' in proj)) {
      throw new Error(`SECURITY: domainProjections[${i}] missing required 'body' key`);
    }
    if (!isValidMu(proj.pattern)) {
      throw new Error(`SECURITY: domainProjections[${i}].pattern is not valid Mu`);
    }
    if (!isValidMu(proj.body)) {
      throw new Error(`SECURITY: domainProjections[${i}].body is not valid Mu`);
    }
    validator(proj.pattern, `domainProjections[${i}].pattern`);
    validator(proj.body, `domainProjections[${i}].body`);

    const projId = (typeof proj.id === 'string') ? proj.id : '';
    if (projId.startsWith('kernel.')) {
      throw new Error(
        `SECURITY: stepKernel expects DOMAIN projections only, ` +
        `got kernel projection at index ${i}: ${projId}`
      );
    }
  }

  // SECURITY: Reject non-linear domain projections (fail-closed).
  // Core kernel (match.v2) silently overwrites bindings on repeated variables.
  // step_kernel_meta(kernelMode='bridge') is still treated as a direct external
  // kernel API — non-linear domain projections are rejected here regardless.
  // Bridge algorithm execution (runAlgorithmWithBridge) bypasses stepKernel entirely.
  rejectNonlinearProjections(domainProjections, 'stepKernel');

  if (hasKernelFuel) {
    if (!isValidMu(kernelFuel)) {
      throw new Error('SECURITY: kernelFuel must be valid Mu linked-list data');
    }
    let fuelProbe = kernelFuel;
    while (fuelProbe !== null) {
      if (typeof fuelProbe !== 'object' || Array.isArray(fuelProbe) ||
          !Object.hasOwn(fuelProbe, 'head') || !Object.hasOwn(fuelProbe, 'tail') ||
          Object.keys(fuelProbe).length !== 2) {
        throw new Error('SECURITY: kernelFuel must be a Mu head/tail linked list');
      }
      fuelProbe = fuelProbe.tail;
    }
  }

  const normalizedInput = shouldNormalize ? normalize(domainInput) : domainInput;
  const normalizedProjs = shouldNormalize
    ? domainProjections.map(normalizeProjection)
    : domainProjections;
  const kernelDomainProjs = normalizedProjs.map(proj => muContainers.record([
    ['pattern', proj.pattern],
    ['body', proj.body],
  ]));

  const kernelInput = muContainers.record([
    ['_step', normalizedInput],
    ['_projs', listToLinked(kernelDomainProjs)],
  ]);

  // P7-d: Accept custom vmConfig only after one-time bundle validation.
  const vmConfig = _vmConfigTrust.validate(options.vmConfig || null);

  let packet = _stepKernelCore(
    projections,
    kernelInput,
    domainInput,
    validator,
    maxSteps,
    vmConfig,
    hasKernelFuel ? kernelFuel : undefined,
    continuationState
  );
  if (returnPacket) {
    return {
      kind: packet.kind,
      result: packet.result,
      continuation: packet.continuation,
    };
  }

  // BOUNDARY: public compatibility driver over explicit Mu continuation data.
  while (packet.kind === 'continuation') {
    packet = _stepKernelCore(
      projections,
      kernelInput,
      domainInput,
      validator,
      maxSteps,
      vmConfig,
      undefined,
      packet.continuation,
      packet.continuationProof
    );
  }
  const canonical = packet.result;

  if (returnMeta) {
    return canonical;
  }

  // Non-meta mode: compatibility shim over canonical _stepKernelCore.
  // Preserves FULL legacy { result, steps, stalled, trace } observable behavior.
  // result = normalize(output) so caller's denormalize() round-trips correctly.
  // stalled preserves legacy semantics (false on max-steps — NB4 public debt deferred).
  const isFuelExhaustion = canonical.termination_reason === 'fuel_exhausted';
  const isLegacyStall = canonical.termination_reason === 'hash_stall' || canonical.termination_reason === 'kernel_stall' || isFuelExhaustion;
  return muContainers.record([
    ['result', normalize(canonical.output)],  // re-normalize so caller denormalize() works
    ['steps', isFuelExhaustion ? canonical.steps_used : isLegacyStall ? canonical.steps_used - 1 : canonical.steps_used],  // legacy uses 0-indexed steps on stall
    ['stalled', isLegacyStall],  // legacy: false on max-steps (NB4 public debt deferred)
    ['trace', muContainers.list()],
  ]);
}

/**
 * Phase 8d: Run with structural trace accumulation.
 * Parameterized: takes kernelProjections instead of module-global.
 *
 * BOUNDARY: Trace infrastructure — off kernel path. Reclassified P7W5: was host iteration marker.
 */
function runStructural(kernelProjections, domainProjections, input, maxSteps = 10000, vmConfig = null) {
  vmConfig = _vmConfigTrust.validate(vmConfig);
  if (!isValidMu(input)) {
    throw new RcxError('input.invalid_type', 'Invalid Mu input to runStructural()');
  }
  validateNoKernelReservedFields(input, 'runStructural input');

  for (let idx = 0; idx < domainProjections.length; idx++) {
    const proj = domainProjections[idx];
    if (typeof proj === 'object' && proj !== null) {
      if ('pattern' in proj) {
        validateNoKernelReservedFields(proj.pattern, `runStructural projection[${idx}].pattern`);
      }
      if ('body' in proj) {
        validateNoKernelReservedFields(proj.body, `runStructural projection[${idx}].body`);
      }
      // SECURITY: Reject kernel-prefixed projection IDs (parity with stepKernel guard).
      const projId = (typeof proj.id === 'string') ? proj.id : '';
      if (projId.startsWith('kernel.')) {
        throw new Error(
          `SECURITY: runStructural expects DOMAIN projections only, ` +
          `got kernel projection at index ${idx}: ${projId}`
        );
      }
    }
  }

  // SECURITY: Reject non-linear domain projections (fail-closed).
  // Mirrors stepKernel guard — runStructural is also a direct external entry point.
  rejectNonlinearProjections(domainProjections, 'runStructural');

  // Pre-normalize projections once (constant across all trace steps).
  const validator = validateNoKernelReservedFields;
  const normalizedProjs = domainProjections.map(normalizeProjection);
  const kernelDomainProjs = normalizedProjs.map(proj => muContainers.record([
    ['pattern', proj.pattern],
    ['body', proj.body],
  ]));
  const linkedProjs = listToLinked(kernelDomainProjs);

  const traceEntries = muContainers.list();
  let current = input;
  let currentHash = muHashControlCached(input, 'runStructural');

  for (let i = 0; i < maxSteps; i++) {
    const normalizedCurrent = normalize(current);
    const kernelInput = muContainers.record([
      ['_step', normalizedCurrent],
      ['_projs', linkedProjs],
    ]);
    // BOUNDARY: trace runner drives explicit kernel continuation values.
    let packet = _stepKernelCore(kernelProjections, kernelInput, current, validator, 10000, vmConfig);
    while (packet.kind === 'continuation') {
      packet = _stepKernelCore(
        kernelProjections,
        kernelInput,
        current,
        validator,
        10000,
        vmConfig,
        undefined,
        packet.continuation
      );
    }
    const meta = packet.result;
    const result = meta.output;
    // Resolve matched projection ID: use Stage 0 match (proven equivalent
    // to match.v2 by parity tests). First-match-wins: first projection whose
    // pattern matches current is the one the kernel applied.
    // O(N) match calls vs the previous O(N*K) kernel runs per step.
    let matchedId = null;
    if (meta.termination_reason === 'projection_applied') {
      for (const proj of domainProjections) {
        if (typeof proj === 'object' && proj !== null && 'pattern' in proj) {
          const bindings = match(proj.pattern, current);
          if (bindings !== NO_MATCH) {
            matchedId = proj.id ?? null;
            break;
          }
        }
      }
    }

    validateNoKernelReservedFields(result, 'runStructural output');
    const traceEntry = muContainers.record([
      ['step', i],
      ['state', current],
      ['projection', matchedId],
    ]);
    traceEntries.push(traceEntry);

    const resultHash = muHashControlCached(result, 'runStructural.stall');
    if (resultHash === currentHash) {
      const stallEntry = muContainers.record([
        ['step', i + 1],
        ['state', result],
        ['projection', null],
        ['stall', true],
      ]);
      traceEntries.push(stallEntry);
      return muContainers.record([
        ['result', result],
        ['trace', listToLinked(traceEntries)],
        ['stall', true],
        ['steps', i + 1],
      ]);
    }

    current = result;
    currentHash = resultHash;
  }

  const maxEntry = muContainers.record([
    ['step', maxSteps],
    ['state', current],
    ['projection', null],
    ['max_steps', true],
  ]);
  traceEntries.push(maxEntry);
  return muContainers.record([
    ['result', current],
    ['trace', listToLinked(traceEntries)],
    ['stall', false],
    ['steps', maxSteps],
  ]);
}

/**
 * Phase 8d: stepKernel with structural trace.
 * Parameterized: takes kernelProjections instead of module-global.
 */
function stepKernelStructural(kernelProjections, domainProjections, domainInput, options = {}) {
  const { maxSteps = 10000, vmConfig = null } = options;
  return runStructural(kernelProjections, domainProjections, domainInput, maxSteps, vmConfig);
}

module.exports = {
  stepKernel,
  runStructural,
  stepKernelStructural,
  // Internal: exported for pipeline.js canonical kernel step
  _stepKernelCore,
  // P7-d: exported for shadow mode control and testing
  _stepKernelWithVM,
  get _STAGE0_SHADOW_ENABLED() { return _STAGE0_SHADOW_ENABLED; },
  set _STAGE0_SHADOW_ENABLED(v) { _STAGE0_SHADOW_ENABLED = v; },
};
