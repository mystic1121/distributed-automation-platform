"""
KPI Automation Worker — SQS consumer.

Replaces the old HTTP-poll + Flask-trigger design. The worker long-polls an SQS
queue for job_ids enqueued by the backend.

Per-instance concurrency is capped by a semaphore (MAX_CONCURRENT_JOBS),
replacing the old in-process active_jobs_count / starting_jobs bookkeeping.
"""
import json
import os
import threading
import time

import boto3

from prepost_runner import run_prepost_job

# ── Config 
SQS_QUEUE_URL      = os.environ["SQS_QUEUE_URL"]
AWS_REGION         = os.environ.get("AWS_REGION", "ap-south-1")
MAX_CONCURRENT     = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))

# Visibility timeout (seconds) must exceed the worst-case job runtime, otherwise
# SQS will re-deliver a job that is still running.
VISIBILITY_TIMEOUT = int(os.environ.get("SQS_VISIBILITY_TIMEOUT", "2000"))

# ── Shared state ──────────────────────────────────────────────────────────────
# The semaphore is this instance's concurrency limit (was active_jobs_count).

_semaphore = threading.Semaphore(MAX_CONCURRENT)
_sqs = boto3.client("sqs", region_name=AWS_REGION)


def _process_message(message: dict):
    """
    Run one job in a daemon thread. The poll loop has already acquired one
    semaphore slot for this message; we release it here when done.
    """
    receipt = message["ReceiptHandle"]
    job_id = "<unknown>"
    try:
        body = json.loads(message["Body"])
        job_id = body["job_id"]
        print(f"[Worker] Starting job {job_id}")
        # run_prepost_job handles its own status reporting (Running/Finished/Failed)
        # and never raises for application-level failures — it returns (ok, msg).
        run_prepost_job(job_id)
        print(f"[Worker] Finished job {job_id}")
    except Exception as e:
        
        print(f"[Worker] Unhandled error processing job {job_id}: {e}")
    finally:
        # Delete on completion
        
        try:
            _sqs.delete_message(QueueUrl=SQS_QUEUE_URL, ReceiptHandle=receipt)
        except Exception as del_err:
            print(f"[Worker] Failed to delete SQS message for job {job_id}: {del_err}")
        _semaphore.release()


def poll_forever():
    print(f"[SQS Worker] Polling {SQS_QUEUE_URL} | max_concurrent={MAX_CONCURRENT}")
    while True:
        # Block until a processing slot is free. While all slots are busy we do
        # NOT fetch from SQS, so messages stay in the queue for other workers.
        if not _semaphore.acquire(blocking=True, timeout=5):
            continue

        try:
            resp = _sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,            # long-poll: efficient, no busy-wait
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
            )
            messages = resp.get("Messages", [])
            if not messages:
                _semaphore.release()          # give the slot back
                continue

            # Hand off to a worker thread; it releases the slot when finished.
            thread = threading.Thread(
                target=_process_message, args=(messages[0],), daemon=True
            )
            thread.start()
        except Exception as e:
            print(f"[SQS Worker] Poll error: {e}")
            _semaphore.release()
            time.sleep(5)                     # back off before retrying


if __name__ == "__main__":
    poll_forever()
