######## DB connector for AWS RDS MySQL ########

import os
import json
import pymysql


def _load_db_config():
    #pull from Secrets Manager (kpi/db secret)
    secret_id = os.environ.get("DB_SECRET_ID")
    if secret_id:
        import boto3
        sm = boto3.client(
            "secretsmanager",
            region_name=os.environ.get("AWS_REGION", "ap-south-1"),
        )
        s = json.loads(sm.get_secret_value(SecretId=secret_id)["SecretString"])
        return {
            "host": s["host"],
            "user": s["username"],
            "password": s["password"],
            "database": s["dbname"],
            "port": int(s.get("port", 3306)),
        }

    # Local-dev fallback: plain env vars
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "kpi_db"),
        "port": int(os.environ.get("DB_PORT", 3306)),
    }


_CONFIG = _load_db_config()


def get_db_connection(cp=None):
    # single RDS database. Kept for call-site compatibility.
    return pymysql.connect(
        host=_CONFIG["host"],
        user=_CONFIG["user"],
        password=_CONFIG["password"],
        database=_CONFIG["database"],
        port=_CONFIG["port"],
        cursorclass=pymysql.cursors.DictCursor,
    )
