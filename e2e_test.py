
import subprocess
import time
import requests
import os
import signal
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
import pymongo.errors

# Load environment variables
load_dotenv('InvoiceCoreProcessor/.env')

def run_test():
    processes = []
    success = True
    mongo_client = None
    document_id = None

    try:
        # --- 1. Set up MongoDB connection for verification ---
        mongo_uri = os.getenv("MONGODB_URI")
        db_name = os.getenv("MONGODB_DATABASE")
        collection_name = os.getenv("MONGODB_COLLECTION")

        try:
            # Check for MongoDB connection with a short timeout
            mongo_client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
            mongo_client.server_info() # This will raise an exception if connection fails
            collection = mongo_client[db_name][collection_name]
            collection.delete_many({})
            print("--- MongoDB connection established and collection cleared ---")
        except pymongo.errors.ServerSelectionTimeoutError:
            print("\n--- ⚠️  WARNING: Could not connect to MongoDB. ---")
            print("--- The e2e test requires a running MongoDB instance at the URI specified in .env. ---")
            print("--- Skipping test. ---")
            return # Exit the test function gracefully

        # --- 2. Start the Ingestion Agent ---
        print("\n--- Starting Ingestion Agent ---")
        ingestion_process = subprocess.Popen(
            ["python", "-m", "InvoiceCoreProcessor.microservices.ingestion.main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid
        )
        processes.append(ingestion_process)
        print(f"  - Ingestion Agent started with PID: {ingestion_process.pid}")

        # --- 3. Start the main FastAPI app ---
        print("\n--- Starting FastAPI Application ---")
        main_app_process = subprocess.Popen(
            ["python", "-m", "InvoiceCoreProcessor.main"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=os.setsid
        )
        processes.append(main_app_process)
        print(f"  - FastAPI app started with PID: {main_app_process.pid}")

        print("\n--- Waiting for services to initialize... ---")
        time.sleep(5)

        # --- 4. Run the Test Case ---
        print("\n--- Test Case: Successful Ingestion ---")
        payload = {"invoice_path": "/invoices/test_invoice.pdf", "user_id": "e2e_test_user"}
        api_url = f"http://{os.getenv('APP_HOST', '127.0.0.1').replace('0.0.0.0', '127.0.0.1')}:{os.getenv('APP_PORT', '8080')}/invoice/upload"

        document_id = None
        try:
            response = requests.post(api_url, json=payload)
            response.raise_for_status()
            response_json = response.json()

            print(f"  - API Response: {response_json}")
            assert "SUCCESS" in response_json.get("final_state", {}).get("final_status", "")
            document_id = response_json.get("final_state", {}).get("document_id")
            assert document_id is not None
            print("  - ✅ PASSED: API call was successful.")
        except Exception as e:
            print(f"  - ❌ FAILED: API call failed. Error: {e}")
            success = False

        # --- 5. Verify the results ---
        if success:
            print("\n--- Verifying Results ---")
            # 5.1 Verify file was created in uploads/
            # Note: we don't know the exact filename, so we check if any file exists.
            if any(os.scandir("uploads")):
                print("  - ✅ PASSED: File was created in the 'uploads' directory.")
            else:
                print("  - ❌ FAILED: No file was found in the 'uploads' directory.")
                success = False

            # 5.2 Verify metadata was saved to MongoDB
            record = collection.find_one({"document_id": document_id})
            if record:
                print("  - ✅ PASSED: Metadata record found in MongoDB.")
                assert record["user_id"] == "e2e_test_user"
                assert record["original_filename"] == "test_invoice.pdf"
                print("  - ✅ PASSED: Metadata content is correct.")
            else:
                print(f"  - ❌ FAILED: No record found in MongoDB for document_id '{document_id}'.")
                success = False

    finally:
        # --- 6. Cleanup ---
        print("\n--- Cleaning up all running processes ---")
        for p in processes:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass # Process already terminated

        if mongo_client:
            # Clean up the test entry
            if document_id:
                collection.delete_one({"document_id": document_id})
            # Clean up the dummy file
            for f in os.scandir("uploads"):
                os.remove(f.path)
            mongo_client.close()
            print("--- MongoDB connection closed and test data cleaned up ---")

    if not success:
        print("\n--- E2E TEST FAILED ---")
        sys.exit(1)
    else:
        print("\n--- E2E TEST PASSED ---")

if __name__ == "__main__":
    run_test()
