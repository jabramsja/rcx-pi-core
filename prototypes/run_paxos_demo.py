
import sys
import os
import json

# Ensure we can import from the current directory
sys.path.insert(0, os.getcwd())

from rcx_pi.selfhost.step_mu import run_mu_structural, run_algorithm_meta_circular
from rcx_pi.selfhost.seed_integrity import load_verified_seed, get_seed_path

def dump(label, data):
    print(f"--- {label} ---")
    try:
        # Filter out the massive trace for readability
        if isinstance(data, dict) and "trace" in data:
            summary = {k: v for k, v in data.items() if k != "trace"}
            summary["trace"] = "<Linked List Trace omitted for brevity>"
            print(json.dumps(summary, indent=2, default=str))
        else:
            print(json.dumps(data, indent=2, default=str))
    except Exception:
        print(data)
    print()

def main():
    print("=== PAXOS DEADLOCK EATER: PRODUCTION-GRADE RUN ===\n")

    # 1. Load All Seeds Securely
    paxos_seed = load_verified_seed(get_seed_path("paxos_demo.v1.json"))
    paxos_projs = paxos_seed["projections"]
    
    recurrence_seed = load_verified_seed(get_seed_path("recurrence.v1.json"))
    recurrence_projs = recurrence_seed["projections"]
    
    print("Step 1: Starting Paxos Livelock Simulation")
    initial_input = {"paxos_trigger": "start_paxos"}
    
    # Run the livelock to generate a trace
    trace_result = run_mu_structural(paxos_projs, initial_input, max_steps=15)
    dump("Trace Result (Final State of Livelock)", trace_result["result"])

    print("\nStep 2: Activating Recurrence Detector (Immune System)")
    recurrence_input = {
        "_detect_closure": {
            "trace": trace_result["trace"],
            "result": trace_result["result"]
        }
    }
    
    # Use the production-grade, meta-circular runner for algorithms.
    # This runs the recurrence state machine until it stalls in a 'recurrence_done' state.
    closure_internal_state = run_algorithm_meta_circular(
        recurrence_projs,
        recurrence_input
    )
    
    # The final step is to "unwrap" the internal state into the clean output format.
    # The 'recurrence.unwrap' projection handles this.
    closure_output = run_algorithm_meta_circular(recurrence_projs, closure_internal_state)
    dump("Closure Detection Output (Final)", closure_output)

    print("\nStep 3: Applying Healer Projection (Metabolization)")
    if isinstance(closure_output, dict) and closure_output.get("closure_detected") is True:
        # Feed the output of the recurrence detector back into the system.
        final_state = run_mu_structural(paxos_projs, closure_output, max_steps=5)["result"]
        dump("FINAL RECONCILED STATE", final_state)
        
        if isinstance(final_state, dict) and final_state.get("status") == "consensus_reached":
            print("\nSUCCESS: System healed. Consensus reached on Node_A.")
        else:
            print("\nFAILURE: Healer did not activate.")
    else:
        print("\nFAILURE: Deadlock not detected.")

if __name__ == "__main__":
    main()
