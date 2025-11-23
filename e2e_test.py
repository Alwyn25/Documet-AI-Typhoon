
import subprocess
import time
import requests
import os
import signal
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
# This ensures the test uses the same config as a regular run
load_dotenv('InvoiceCoreProcessor/.env')

def print_process_logs(name, process):
    """Helper function to print stdout and stderr from a subprocess."""
    print(f"--- Logs for {name} (PID: {process.pid}) ---")
    try:
        stdout, stderr = process.communicate(timeout=1)
        if stdout:
            print("--- STDOUT ---")
            print(stdout)
        if stderr:
            print("--- STDERR ---")
            print(stderr)
    except Exception as e:
        print(f"  - Error reading logs: {e}")

def run_test():
    processes = {}
    pids = []
    success = True

    try:
        # --- 1. Start all microservices as modules ---
        print("--- Starting Microservices ---")
        services = ["mapper", "agent", "datastore"]
        for service in services:
            process = subprocess.Popen(
                ["python", "-m", f"InvoiceCoreProcessor.microservices.{service}.main"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid, text=True
            )
            processes[service.capitalize()] = process
            pids.append(process.pid)

        # --- 2. Start the main FastAPI app as a module ---
        print("\n--- Starting FastAPI Application ---")
        main_app_process = subprocess.Popen(
            ["python", "-m", "InvoiceCoreProcessor.main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid, text=True
        )
        processes["FastAPI"] = main_app_process
        pids.append(main_app_process.pid)

        print(f"  - PIDs: {pids}")
        print("\n--- Waiting for services to initialize... ---")
        time.sleep(10)

        # --- 3. Run Test Cases ---
        app_host = os.getenv("APP_HOST", "0.0.0.0")
        # In Docker/localhost scenarios, 0.0.0.0 needs to be translated to localhost for the client
        if app_host == "0.0.0.0":
            app_host = "127.0.0.1"
        app_port = os.getenv("APP_PORT", "8080")
        api_url = f"http://{app_host}:{app_port}/invoice/upload"

        print(f"--- Running tests against {api_url} ---")

        # Test Case 1: Successful Workflow
        print("\n--- Test Case 1: Successful Workflow ---")
        success_payload = {"raw_file_ref": "/path/to/normal_invoice.pdf", "user_id": "test_user_1"}
        response = None
        try:
            response = requests.post(api_url, json=success_payload)
            response.raise_for_status()
            response_json = response.json()
            assert "SUCCESS" in response_json.get("final_state", "")
            print("  - ✅ PASSED")
        except Exception as e:
            print(f"  - ❌ FAILED: {e}")
            if response is not None: print(f"    Response body: {response.text}")
            success = False

        # Test Case 2: Anomaly Workflow
        print("\n--- Test Case 2: Anomaly Workflow ---")
        anomaly_payload = {"raw_file_ref": "/path/to/high_value_invoice.pdf", "user_id": "test_user_2"}
        response = None
        try:
            response = requests.post(api_url, json=anomaly_payload)
            response.raise_for_status()
            response_json = response.json()
            assert "ANOMALY" in response_json.get("final_state", "")
            print("  - ✅ PASSED")
        except Exception as e:
            print(f"  - ❌ FAILED: {e}")
            if response is not None: print(f"    Response body: {response.text}")
            success = False

    finally:
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
                pass
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
