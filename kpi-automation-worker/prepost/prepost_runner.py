import os
import json
import traceback
import threading
import requests
import subprocess
import sys
import shutil
import tempfile
from datetime import datetime, timedelta
from s3_helpers import (read_json_s3, write_json_s3, s3_key_exists,
                        download_file_s3, upload_file_s3)

IMS_API_BASE_URL = os.environ.get("BACKEND_URL")


def _notify_ims_status(job_id: str, status: str, started_at: str = None, finished_at: str = None, error_message: str = None, company: str = 'jio', created_by: str = None):
    url = f"{IMS_API_BASE_URL.rstrip('/')}/api/kpi-automation/status"
    payload = {"job_id": job_id, "status": status}
    if started_at:
        payload["started_at"] = started_at
    if finished_at:
        payload["finished_at"] = finished_at
    if error_message is not None:
        payload["error_message"] = error_message
    
    headers = {"X-KPI-Company": company}
    try:
        requests.post(url, json=payload, headers=headers, timeout=5)
        
    except Exception:
        pass

def _get_db_post_process_flag(job_id: str, company: str = 'jio'):
    """Helper to fetch the post_processed flag from the IMS database via API."""
    url = f"{IMS_API_BASE_URL.rstrip('/')}/api/kpi-automation/job-params/{job_id}"
    headers = {"X-KPI-Company": company}
    try:
        resp = requests.get(url, headers=headers, timeout=10, proxies={"http": None, "https": None})
        if resp.ok:
            return resp.json().get("post_process", False)
    except Exception as e:
        print(f"--- [ERROR] Failed to fetch post_process param from DB: {e} ---")
    return False


# S3 prefixes (inputs/outputs/templates) + a LOCAL scratch dir for processing
INPUT_PREFIX         = "inputs"
OUTPUT_PREFIX        = "outputs"
TEMPLATE_PREFIX      = "templates/prepost"
TEMPLATES_CONFIG_KEY = "templates_config.json"
WORK_DIR = os.environ.get("WORK_DIR", os.path.join(tempfile.gettempdir(), "kpi_work"))

def get_template_map():
    config_data = read_json_s3(TEMPLATES_CONFIG_KEY)
    if not config_data:
        print("--- [WARNING] templates_config.json not found in S3 ---")
        return {}
    # template_id -> S3 key of the template file
    return {k: f"{TEMPLATE_PREFIX}/{v}" for k, v in config_data.items()}
       

def run_prepost_job(job_id: str) -> tuple[bool, str]:
    """
    Called by your JCP Flask API with job_id.
    - Reads meta.json from inputs/jobs/<job_id>/
    - Uses template_id to select correct template
    - Runs the notebook logic and writes outputs to outputs/jobs/<job_id>/
    """
    # Local scratch folders for this job (subprocess works on local files)
    job_input_dir   = os.path.join(WORK_DIR, job_id, "input")
    job_template_dir = os.path.join(WORK_DIR, job_id, "template")
    job_output_dir  = os.path.join(WORK_DIR, job_id, "output")
    for d in (job_input_dir, job_template_dir, job_output_dir):
        os.makedirs(d, exist_ok=True)

    # 1) meta.json from S3
    meta_key = f"{INPUT_PREFIX}/{job_id}/meta.json"
    meta = read_json_s3(meta_key)
    if meta is None:
        _notify_ims_status(job_id, "Failed", error_message="meta.json not found")
        return False, f"meta.json not found for job_id={job_id}"

    template_id = meta.get("template_id")
    if not template_id:
        _notify_ims_status(job_id, "Failed", error_message="template_id missing in meta.json")
        return False, "template_id missing in meta.json"

    # 2) template file from S3 -> local
    template_map = get_template_map()
    template_key = template_map.get(template_id)
    if not template_key or not s3_key_exists(template_key):
        _notify_ims_status(job_id, "Failed", error_message=f"Unknown or missing template for template_id={template_id}")
        return False, f"Unknown or missing template for template_id={template_id}"

    job_template_path = os.path.join(job_template_dir, os.path.basename(template_key))
    download_file_s3(template_key, job_template_path)
    # keep a copy under inputs/<job_id>/template/ in S3 (for reference/job audit)
    upload_file_s3(job_template_path, f"{INPUT_PREFIX}/{job_id}/template/{os.path.basename(template_key)}")

    meta_yaml_key = f"{TEMPLATE_PREFIX}/meta.yaml"
    if s3_key_exists(meta_yaml_key):
        download_file_s3(meta_yaml_key, os.path.join(job_template_dir, "meta.yaml"))
    else:
        _notify_ims_status(job_id, "Failed", error_message=f"meta.yaml not found in S3 at {meta_yaml_key}")
        return False, f"meta.yaml not found in S3 at {meta_yaml_key}"

    # 3) CSV from S3 -> local
    csv_path = os.path.join(job_input_dir, "kpi_input.csv")
    csv_key  = f"{INPUT_PREFIX}/{job_id}/kpi_input.csv"
    if not s3_key_exists(csv_key):
        _notify_ims_status(job_id, "Failed", error_message="kpi_input.csv not found")
        return False, f"kpi_input.csv not found for job_id={job_id}"
    download_file_s3(csv_key, csv_path)

    report_date = meta.get("report_date") or (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%d-%m-%Y")
    report_type = meta.get("report_type") or "daily"
    company = meta.get("company", "jio")
    jcp_format = meta.get("jcp_format", False)

     # READ FROM META.JSON (previously database)
    post_process = meta.get("post_process", False)
    # post_process = _get_db_post_process_flag(job_id, company) 
    created_by = meta.get("created_by", None)

    try:
        # -------------------------------------------------
        # 1️⃣ Update status → RUNNING
        # -------------------------------------------------

        meta["status"] = "running"
        meta["started_at"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

        write_json_s3(meta_key, meta)

        _notify_ims_status(job_id, "Running", started_at=meta["started_at"], company=company)

        # -------------------------------------------------
        # 2️⃣ Execute main report logic via Subprocess (True Parallelism)
        # -------------------------------------------------

        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Final_run.py")
        
        cmd = [
            sys.executable, "-u", script_path,
            "--input_csv", csv_path,
            "--template_id", template_id,
            "--report_type", report_type,
            "--jcp_format", str(jcp_format),
            "--post_process", str(post_process),
            "--output_dir", job_output_dir,
            "--template_path", job_template_path
        ]
        
        if report_date:
            cmd.extend(["--report_date", report_date])

        print(f"Executing Process: {' '.join(cmd)}")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Merge stderr into stdout for easier monitoring
            text=True,
            bufsize=1 # Line buffered
        )
        
        print(f"--- [DEBUG] Subprocess started with PID: {process.pid} ---")
        
        # Stream output in real-time
        output_lines = []
        for line in process.stdout:
            print(f"[PID {process.pid}] {line.strip()}")
            output_lines.append(line)
        
        process.wait()
        stdout = "".join(output_lines)
        
        ok = (process.returncode == 0)
        
        # A zero exit code is not enough: if the report logic silently produced no
        # files, treat the job as failed rather than shipping an empty zip.
        produced_files = os.listdir(job_output_dir) if os.path.isdir(job_output_dir) else []
        if ok and not produced_files:
            ok = False
            message = "Job exited 0 but produced no output files (empty output dir). Check logs for errors."
            print(f"--- [DEBUG] PROCESS {process.pid} reported success but output dir is empty ---")
        elif ok:
            message = "Success"
        else:
            # If the process crashed, we dynamically rip off the final stack trace logs for perfect clarity
            clean_lines = [l.strip() for l in output_lines if l.strip()]
            error_segment = clean_lines[-25:] if len(clean_lines) > 25 else clean_lines
            formatted_error_trace = "\n".join(error_segment)
            message = f"Job crashed with Exit Code {process.returncode}. Reason:\n{formatted_error_trace}"
            
        if not ok:
            print(f"--- [DEBUG] PROCESS {process.pid} FAILED with code {process.returncode} ---")
        else:
            print(f"--- [DEBUG] PROCESS {process.pid} SUCCESS ---")

        # -------------------------------------------------
        # 3️⃣ Update meta → SUCCESS / FAILED
        # -------------------------------------------------

        meta["finished_at"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

        if ok:
            meta["status"] = "success"
            meta["output_files"] = os.listdir(job_output_dir)
            meta["error_message"] = None

            try:
                local_zip_base = os.path.join(WORK_DIR, job_id, job_id)
                generated_zip = local_zip_base + ".zip"
                print(f"Zipping local output: {job_output_dir} -> {generated_zip}")
                shutil.make_archive(local_zip_base, 'zip', job_output_dir)

                # Upload zip to S3: outputs/<job_id>/<job_id>.zip
                upload_file_s3(generated_zip, f"{OUTPUT_PREFIX}/{job_id}/{job_id}.zip")
                print("--- [DEBUG] Zip uploaded to S3 ---")
            except Exception as zip_err:
                print(f"--- [ERROR] Zipping/Upload failed: {zip_err} ---")

            _notify_ims_status(job_id, "Finished", finished_at=meta["finished_at"], company=company, created_by=created_by)
        else:
            meta["status"] = "failed"
            meta["error_message"] = message
            _notify_ims_status(job_id, "Failed", finished_at=meta["finished_at"], error_message=message, company=company, created_by=created_by)

        write_json_s3(meta_key, meta)

        return ok, message

    except Exception:
        meta["status"] = "failed"
        meta["finished_at"] = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        meta["error_message"] = traceback.format_exc()
        _notify_ims_status(job_id, "Failed", finished_at=meta["finished_at"], error_message=meta["error_message"], company=company)

        write_json_s3(meta_key, meta)

        return False, traceback.format_exc()

    finally:
        job_root = os.path.join(WORK_DIR, job_id)
        if os.path.exists(job_root):
            try:
                shutil.rmtree(job_root)
            except Exception as e:
                print(f"--- [WARNING] Failed to clean up {job_root}: {e} ---")

if __name__ == "__main__":
    
    # Optional: Test with a job_id if provided via args
    if len(sys.argv) > 1:
        job_id = sys.argv[1]
        ok, res = run_prepost_job(job_id)
        print(f"Job {job_id} Result: {ok}, {res}")
    else:
        print("No job_id provided for testing. Runner is ready.")