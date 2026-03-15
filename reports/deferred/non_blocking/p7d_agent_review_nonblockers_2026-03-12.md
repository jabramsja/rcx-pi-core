# P7-d Agent Review (Active Non-Blocking Residue)

Archived source snapshot:

- `reports/archive/deferred/p7d_agent_review_nonblockers.md`

Resolved or merely documented items were archived with the source snapshot.

## Open Items

### 1. `step_mu.py` still has substantial unannotated `isinstance` residue

- Status: pre-existing marker-truth debt, not specific to P7-d

### 2. `kernel.js` shadow-mode logic still duplicates the same check block twice

- Status: temporary duplication until cutover removes or shrinks the shadow path

### 3. `stepKernelStructural` is still a trivial pass-through wrapper

- Status: low-priority simplification only

### 4. `_STAGE0_SHADOW_ENABLED` remains externally mutable

- Status: low-risk test seam that should disappear or freeze at cutover

### 5. `_STAGE0_VM_CUTOVER=True` path still has no direct test coverage

- Status: expected until the cutover wave lands

### 6. Shadow mode still has no dedicated fuzz coverage

- Status: acceptable while the lane remains temporary, but worth revisiting if it
  persists

