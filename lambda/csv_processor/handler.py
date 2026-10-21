

import json
import csv
import io           # For reading the CSV bytes as a text stream
import os
import uuid
import urllib.parse  # For decoding S3 key (spaces become %20 in URLs)
import boto3
import psycopg2     # PostgreSQL adapter for Python — lets us run SQL queries

# --- AWS S3 client ---
s3_client = boto3.client("s3")

# --- Database connection settings ---
# These come from environment variables set in serverless.yml.
# In production (AWS), they point to RDS. For local testing, they point
# to our Docker Postgres.
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "clickpe_db")
DB_USER = os.environ.get("DB_USER", "clickpe_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "clickpe_pass")

# --- n8n webhook URL ---
# After inserting users, we call this URL to trigger Workflow B.
# This is set in serverless.yml and points to your n8n instance.
N8N_WEBHOOK_URL = os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/matching-trigger")


def get_db_connection():
    """
    Creates and returns a connection to the PostgreSQL database.

    WHY A FUNCTION:
      We might need to reconnect if the connection drops. Having this
      as a function makes it easy to retry.

    WHAT psycopg2.connect DOES:
      Opens a TCP connection to the Postgres server and authenticates.
      Returns a connection object we can use to run SQL queries.
    """
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def handler(event, context):
    """
    Lambda handler — triggered automatically when a CSV file is uploaded to S3.

    PARAMETERS:
      - event:   The S3 event notification (contains bucket name and file key)
      - context: Lambda runtime info (we use it to check remaining time)
    """
    try:
        # =====================================================================
        # STEP 1: Extract the S3 bucket and file key from the event
        # =====================================================================
        # S3 events come in a "Records" array (could be multiple files,
        # but in practice it's usually just one).
        record = event["Records"][0]
        bucket = record["s3"]["bucket"]["name"]

        # URL-decode the key: S3 encodes special characters (spaces → +, etc.)
        raw_key = record["s3"]["object"]["key"]
        s3_key = urllib.parse.unquote_plus(raw_key)

        print(f"Processing file: s3://{bucket}/{s3_key}")

        # Extract batch_id from the filename.
        # Our presigned URL Lambda names files as "uploads/<batch_id>.csv"
        # So we split by "/" and strip ".csv" to get the batch_id.
        batch_id = s3_key.split("/")[-1].replace(".csv", "")

        # =====================================================================
        # STEP 2: Download the CSV file from S3
        # =====================================================================
        # get_object returns a streaming response; we read the body into memory.
        # For a 1MB CSV with 10K rows, this is fine. For 100MB+ files, you'd
        # stream it in chunks, but that's overkill for this task.
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        csv_content = response["Body"].read().decode("utf-8")

        # =====================================================================
        # STEP 3: Parse the CSV and insert rows into PostgreSQL
        # =====================================================================
        # io.StringIO wraps the string so csv.DictReader can iterate over it.
        # DictReader uses the first row as column headers, so each row
        # becomes a dict like {"user_id": "abc", "name": "John", ...}
        reader = csv.DictReader(io.StringIO(csv_content))

        conn = get_db_connection()
        cursor = conn.cursor()

        inserted_count = 0
        skipped_count = 0

        for row in reader:
            try:
                # INSERT each user row into the database.
                # ON CONFLICT (user_id) DO UPDATE: If a user with the same UUID
                # already exists, we update their data instead of crashing.
                # This makes the upload idempotent (safe to re-upload same CSV).
                cursor.execute(
                    """
                    INSERT INTO users (user_id, name, email, monthly_income,
                                       credit_score, employment_status, age, batch_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        email = EXCLUDED.email,
                        monthly_income = EXCLUDED.monthly_income,
                        credit_score = EXCLUDED.credit_score,
                        employment_status = EXCLUDED.employment_status,
                        age = EXCLUDED.age,
                        batch_id = EXCLUDED.batch_id
                    """,
                    (
                        row["user_id"],
                        row["name"],
                        row["email"],
                        int(row["monthly_income"]),
                        int(row["credit_score"]),
                        row["employment_status"],
                        int(row["age"]),
                        batch_id,
                    ),
                )
                inserted_count += 1

            except Exception as row_error:
                # If one row fails (bad data), skip it and continue.
                # We don't want one malformed row to kill the entire upload.
                print(f"Skipping row {row.get('user_id', 'unknown')}: {str(row_error)}")
                skipped_count += 1
                continue

        # COMMIT: Actually saves all the INSERTs to the database.
        # Without commit(), the transaction is rolled back and nothing is saved.
        conn.commit()
        cursor.close()
        conn.close()

        print(f"Inserted {inserted_count} users, skipped {skipped_count}")

        # =====================================================================
        # STEP 4: Trigger n8n Workflow B via webhook
        # =====================================================================
        # Now that users are in the database, we tell n8n to start matching
        # them with loan products. We send the batch_id so Workflow B knows
        # which users to process (just the new ones, not all 10K).
        #
        # WHY URLLIB AND NOT REQUESTS:
        #   Lambda has a limited set of pre-installed libraries. `requests`
        #   is NOT included by default, but `urllib3` is available via botocore.
        #   Using urllib.request avoids needing to package extra dependencies.
        import urllib.request

        webhook_data = json.dumps({
            "batch_id": batch_id,
            "user_count": inserted_count,
            "s3_key": s3_key,
        }).encode("utf-8")

        req = urllib.request.Request(
            N8N_WEBHOOK_URL,
            data=webhook_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            urllib.request.urlopen(req, timeout=10)
            print(f"Successfully triggered n8n webhook for batch {batch_id}")
        except Exception as webhook_error:
            # Don't fail the whole Lambda if n8n is unreachable.
            # The data is already saved in Postgres; you can trigger
            # Workflow B manually from the n8n UI.
            print(f"Warning: Could not trigger n8n webhook: {str(webhook_error)}")
            print("Data was saved. Trigger Workflow B manually if needed.")

        # =====================================================================
        # STEP 5: Return success response
        # =====================================================================
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "CSV processed successfully",
                "batch_id": batch_id,
                "inserted": inserted_count,
                "skipped": skipped_count,
            }),
        }

    except Exception as e:
        print(f"Fatal error processing CSV: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": "Failed to process CSV",
                "detail": str(e),
            }),
        }
