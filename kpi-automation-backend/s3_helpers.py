import os
import io
import json
import boto3

_S3 = None

def s3():
    global _S3
    if _S3 is None:
        _S3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "ap-south-1"))
    return _S3

def bucket():
    return os.environ["S3_BUCKET"]            # set in /etc/kpi/*.env on the server

# ---- existence ----
def s3_key_exists(key):
    try:
        s3().head_object(Bucket=bucket(), Key=key)
        return True
    except Exception:
        return False

# ---- small JSON files ----
def read_json_s3(key, default=None):
    if not s3_key_exists(key):
        return default
    body = s3().get_object(Bucket=bucket(), Key=key)["Body"].read()
    return json.loads(body.decode("utf-8"))

def write_json_s3(key, data):
    s3().put_object(Bucket=bucket(), Key=key,
                    Body=json.dumps(data, indent=4).encode("utf-8"),
                    ContentType="application/json")

# ---- raw bytes (for send_file downloads + browser uploads) ----
def get_bytes_s3(key):
    """Return a BytesIO of an S3 object — pass straight to Flask send_file()."""
    data = s3().get_object(Bucket=bucket(), Key=key)["Body"].read()
    return io.BytesIO(data)

def put_bytes_s3(key, data_bytes):
    s3().put_object(Bucket=bucket(), Key=key, Body=data_bytes)

def delete_key_s3(key):
    s3().delete_object(Bucket=bucket(), Key=key)

# ---- whole-file up/download (for Excel/CSV/zip processed locally) ----
def download_file_s3(key, local_path):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    s3().download_file(bucket(), key, local_path)
    return local_path

def upload_file_s3(local_path, key):
    s3().upload_file(local_path, bucket(), key)

# ---- folder ("prefix") sync — for the trend files + job output folders ----
def list_keys_s3(prefix):
    keys, paginator = [], s3().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket(), Prefix=prefix):
        keys += [o["Key"] for o in page.get("Contents", [])]
    return keys

def download_prefix_s3(prefix, local_dir):
    """Download everything under an S3 prefix into local_dir (keeps subpaths)."""
    os.makedirs(local_dir, exist_ok=True)
    for key in list_keys_s3(prefix):
        rel = key[len(prefix):].lstrip("/")
        if not rel:
            continue
        dest = os.path.join(local_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        s3().download_file(bucket(), key, dest)

def upload_prefix_s3(local_dir, prefix):
    """Upload every file under local_dir to S3 under prefix."""
    for root, _, files in os.walk(local_dir):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, local_dir).replace("\\", "/")
            s3().upload_file(full, bucket(), f"{prefix.rstrip('/')}/{rel}")
