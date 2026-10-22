import json
import boto3        # AWS SDK for Python — lets us talk to AWS services
import uuid         # For generating unique filenames
import os           # For reading environment variables

# Initialize the S3 client.
# boto3 automatically uses the Lambda's IAM role for credentials.
# (You don't need to hardcode AWS keys — Lambda gets permissions from its role.)
s3_client = boto3.client("s3", region_name="us-east-1")

# The S3 bucket name comes from an environment variable set in serverless.yml.
# In serverless-offline, CloudFormation !Ref resolves to '[object Object]', so we fallback
# to the actual bucket name.
BUCKET_NAME = os.environ.get("UPLOAD_BUCKET")
if not BUCKET_NAME or BUCKET_NAME == "[object Object]":
    BUCKET_NAME = "clickpe-csv-uploads-dev"


def handler(event, context):
    """
    AWS Lambda handler function.

    PARAMETERS (set by AWS, you don't call this directly):
      - event:   Contains the HTTP request data (headers, body, query params)
                  when called through API Gateway.
      - context: Contains runtime info (function name, remaining time, etc.)
                  We don't use it here but it's always passed by AWS.

    RETURNS:
      A JSON response with the presigned URL and the S3 key (filename).
      The frontend uses the URL to upload, and sends the key to track the file.
    """
    try:
        # Generate a unique batch_id for this upload.
        # All users from this CSV will share this batch_id, so Workflow B
        # can process just the new batch instead of re-processing everyone.
        batch_id = str(uuid.uuid4())

        # S3 key = the "path" inside the bucket where the file will be stored.
        # Format: uploads/<batch_id>.csv
        # Using batch_id as filename ensures no collisions if two people
        # upload simultaneously.
        s3_key = f"uploads/{batch_id}.csv"

        # S3 bucket name
        bucket = os.environ.get("UPLOAD_BUCKET", "clickpe-csv-uploads-dev")
        if not bucket or "object" in str(bucket).lower():
            bucket = "clickpe-csv-uploads-dev"

        # generate_presigned_url creates a temporary URL (valid for 300 seconds)
        # that allows uploading a file to the specified S3 key.
        # "put_object" means this URL can only be used for uploading, not downloading.
        presigned_url = s3_client.generate_presigned_url(
            ClientMethod="put_object",     # Only allows PUT (upload), not GET (download)
            Params={
                "Bucket": bucket,
                "Key": s3_key,
                "ContentType": "text/csv",  # Only accept CSV files
            },
            ExpiresIn=300,                  # URL expires in 5 minutes
        )

        # Return the URL and metadata to the frontend.
        return {
            "statusCode": 200,
            "headers": {
                # CORS headers: Allow the frontend (running on a different origin)
                # to call this API. Without these, the browser blocks the request.
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
            },
            "body": json.dumps({
                "upload_url": presigned_url,  # The frontend uses this to upload
                "s3_key": s3_key,             # Reference to the uploaded file
                "batch_id": batch_id,         # Used to track this batch of users
            }),
        }

    except Exception as e:
        print(f"Error generating presigned URL: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps({
                "error": "Failed to generate upload URL",
                "detail": str(e),
            }),
        }
