# InvoiceCoreProcessor

## Project Overview

**InvoiceCoreProcessor** is an intelligent, AI-powered application designed to revolutionize Accounts Payable (AP) workflows. It provides a secure and intuitive interface for uploading scanned or PDF invoices, leveraging the power of Google's Gemini API to instantly extract critical structured data. By automating manual data entry, the application accelerates invoice processing, minimizes human error, and provides a real-time, auditable history of all transactions.

This tool is built for Accounting Departments, Finance Managers, and Procurement Teams who need to reconcile and pay invoices with speed and accuracy.

## Features

-   **Secure Invoice Upload**: A clean, single-page interface for securely uploading invoice files (PDFs, JPGs, PNGs).
-   **Structured Data Extraction**: Utilizes the Gemini `gemini-2.5-flash-preview-09-2025` model to intelligently parse documents and extract key fields, including Vendor Name, Total Amount, Due Date, Invoice Date, and detailed Line Items.
-   **Real-time Validation & Status Tracking**: The system provides immediate feedback on the extraction process, with statuses like `PROCESSING`, `COMPLETE`, or `FAILED`.
-   **Persistent History Tracking**: All processed invoice metadata and extracted data are securely stored in a persistent history, allowing for easy auditing and review.

## Setup and Execution in Canvas

InvoiceCoreProcessor is designed to run as a single, self-contained React application within an internal Canvas/Immersive Environment.

1.  **Load the Application**: The application is provided as a single file. Load it into your Canvas environment.
2.  **Authentication**: The application uses Firebase Auth with a custom/anonymous token to automatically secure your session and associate all processed invoices with your unique user ID.
3.  **Run the Preview**: Click the **Preview** button in the Canvas environment to launch the application.
4.  **Upload Invoices**: Use the upload interface to select and process your invoice files. The extracted data and status will appear in the history view in real-time.

## Contribution Workflow

We follow a standard Git-based workflow for contributions. All changes are managed through feature branches, pull requests, and code reviews to ensure quality and stability.

For a detailed, live visualization of our branching and merging strategy, please refer to our Git Diagram:

[**Live Git Workflow Diagram**](https://gitdiagram.com/alwyn25/invoice-core-processor)

## Tech Stack

-   **Frontend**: React (Single Page Application), Tailwind CSS
-   **AI & Data Extraction**: Google Gemini API (`gemini-2.5-flash-preview-09-2025`) with structured JSON output
-   **Data Persistence**: Google Firebase Firestore
-   **Authentication**: Firebase Auth (Custom/Anonymous Token)
-   **Deployment**: Internal Canvas/Immersive Environment

## Data Persistence

All extracted invoice data is securely stored in a **Firebase Firestore** database. To ensure data privacy and isolation, records are saved under a collection path that includes the current user's unique `userId`. This means only you can access the invoice data you have processed.

**Collection Path**: `/artifacts/{__app_id}/users/{userId}/invoice_records`
