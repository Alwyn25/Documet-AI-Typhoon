
import subprocess
import time
import requests
import os
import signal
import sys

def print_process_logs(name, process):
    """Helper function to print stdout and stderr from a subprocess."""
    print(f"\n--- Logs for {name} (PID: {process.pid}) ---")

    # Non-blocking read of stdout and stderr
    try:
        stdout, stderr = process.communicate(timeout=1)
        if stdout:
            print("--- STDOUT ---")
            print(stdout)
        if stderr:
            print("--- STDERR ---")
            print(stderr)
    except subprocess.TimeoutExpired:
        print("  - Timed out reading logs.")
    except Exception as e:
        print(f"  - Error reading logs: {e}")

def run_test():
    """
    An end-to-end test for the invoice processing system.
    """
    processes = {}
    pids = []
    success = True

    try:
        # --- 1. Start all microservices in the background ---
        print("--- Starting Microservices ---")
        mapper_process = subprocess.Popen(
            ["python", "-m", "InvoiceCoreProcessor.microservices.mapper.main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid, text=True
        )
        processes["Mapper"] = mapper_process
        pids.append(mapper_process.pid)

        agent_process = subprocess.Popen(
            ["python", "-m", "InvoiceCoreProcessor.microservices.agent.main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid, text=True
        )
        processes["Agent"] = agent_process
        pids.append(agent_process.pid)

        datastore_process = subprocess.Popen(
            ["python", "-m", "InvoiceCoreProcessor.microservices.datastore.main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid, text=True
        )
        processes["DataStore"] = datastore_process
        pids.append(datastore_process.pid)

        # --- 2. Start the main FastAPI app ---
        print("\n--- Starting FastAPI Application ---")
        main_app_process = subprocess.Popen(
            ["uvicorn", "InvoiceCoreProcessor.main:app", "--host", "0.0.0.0", "--port", "8080"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid, text=True
        )
        processes["FastAPI"] = main_app_process
        pids.append(main_app_process.pid)

        print(f"  - PIDs: {pids}")
        print("\n--- Waiting for services to initialize... ---")
        time.sleep(10)

        # --- 4. Run Test Case 1: Successful Workflow ---
        print("\n--- Test Case 1: Successful Workflow ---")
        success_payload = {"raw_file_ref": "/path/to/normal_invoice.pdf", "user_id": "test_user_1"}
        response = None
        try:
            response = requests.post("http://localhost:8080/invoice/upload", json=success_payload)
            response.raise_for_status()
            response_json = response.json()
            assert "SUCCESS" in response_json.get("final_state", "")
            print("  - ✅ PASSED")
        except Exception as e:
            print(f"  - ❌ FAILED: {e}")
            if response: print(f"    Response body: {response.text}")
            success = False

        # --- 5. Run Test Case 2: Anomaly Workflow ---
        print("\n--- Test Case 2: Anomaly Workflow ---")
        anomaly_payload = {"raw_file_ref": "/path/to/high_value_invoice.pdf", "user_id": "test_user_2"}
        response = None
        try:
            response = requests.post("http://localhost:8080/invoice/upload", json=anomaly_payload)
            response.raise_for_status()
            response_json = response.json()
            assert "ANOMALY" in response_json.get("final_state", "")
            print("  - ✅ PASSED")
        except Exception as e:
            print(f"  - ❌ FAILED: {e}")
            if response: print(f"    Response body: {response.text}")
            success = False

    finally:
        # --- 6. Cleanup ---
        if not success:
            print("\n" + "="*20 + " CAPTURING LOGS " + "="*20)
            for name, proc in processes.items():
                print_process_logs(name, proc)
            print("="*58)

        print("\n--- Cleaning up all running processes ---")
        for pid in pids:
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
                print(f"  - Terminated process group for PID: {pid}")
            except ProcessLookupError:
                print(f"  - Process {pid} already terminated.")
            except Exception as e:
                print(f"  - Error terminating process {pid}: {e}")
        time.sleep(2)

    if not success:
        print("\n--- E2E TEST FAILED ---")
        sys.exit(1)
    else:
        print("\n--- E2E TEST PASSED ---")

if __name__ == "__main__":
    run_test()
