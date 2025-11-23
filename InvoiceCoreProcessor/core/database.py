import os
from contextlib import contextmanager
from datetime import date, timedelta
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# --- PostgreSQL Connection Pool ---
db_pool = None

def init_pool():
    """Initializes the PostgreSQL connection pool."""
    global db_pool
    db_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,  # Max number of connections
        dbname=os.getenv("POSTGRES_DB"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT")
    )

def close_pool():
    """Closes all connections in the pool."""
    global db_pool
    if db_pool:
        db_pool.closeall()

@contextmanager
def get_db_connection():
    """Gets a connection from the pool."""
    if db_pool is None:
        raise RuntimeError("Database pool has not been initialized.")

    conn = db_pool.getconn()
    try:
        yield conn
    finally:
        db_pool.putconn(conn)

def check_duplicate_invoice(vendor_gstin: str, invoice_no: str, invoice_date: date) -> bool:
    """
    Checks for a duplicate invoice in the PostgreSQL database using a pooled connection.
    """
    date_start = invoice_date - timedelta(days=3)
    date_end = invoice_date + timedelta(days=3)

    query = """
    SELECT EXISTS (
        SELECT 1 FROM invoices
        WHERE vendor_gstin = %s
          AND invoice_no = %s
          AND invoice_date BETWEEN %s AND %s
    );
    """

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (vendor_gstin, invoice_no, date_start, date_end))
                exists = cursor.fetchone()[0]
                return exists
    except psycopg2.Error as e:
        # In a real app, you would log this error
        print(f"Database error: {e}")
        # To be safe, assume a duplicate might exist if the DB check fails
        return True


# --- MongoDB Connection (can also be managed more robustly) ---
# For this exercise, we will leave the MongoDB connection as is,
# but in a production system, it should be managed at app startup/shutdown as well.
def get_mongo_client():
    """Establishes and returns a connection to the MongoDB server."""
    client = MongoClient(os.getenv("MONGO_URI"))
    return client

def get_mongo_db():
    """Returns the specific MongoDB database instance."""
    client = get_mongo_client()
    db = client[os.getenv("MONGO_DB")]
    return db
