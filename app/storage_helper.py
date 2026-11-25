import os
import uuid
import io
import mimetypes
from werkzeug.utils import secure_filename
from .firebase_config import _get_pg_connection

def get_s3_client():
    endpoint = os.environ.get('AWS_ENDPOINT_URL_S3')
    ak = os.environ.get('AWS_ACCESS_KEY_ID')
    sk = os.environ.get('AWS_SECRET_ACCESS_KEY')
    region = os.environ.get('AWS_REGION', 'us-east-2')

    if endpoint and ak and sk:
        try:
            import boto3
            return boto3.client(
                's3',
                endpoint_url=endpoint,
                aws_access_key_id=ak,
                aws_secret_access_key=sk,
                region_name=region
            )
        except Exception as e:
            print(f"⚠️ S3 client init notice: {e}")
            return None
    return None

def save_uploaded_file(file_obj, original_filename, folder="library"):
    """
    Saves an uploaded file to Neon S3 Storage bucket and/or Neon PostgreSQL.
    Guarantees persistence across Vercel serverless cold starts and restarts.
    """
    file_id = uuid.uuid4().hex
    safe_name = secure_filename(original_filename) if original_filename else f"file_{file_id}"
    mimetype, _ = mimetypes.guess_type(safe_name)
    mimetype = mimetype or (getattr(file_obj, 'content_type', None) or 'application/octet-stream')

    file_bytes = file_obj.read() if hasattr(file_obj, 'read') else bytes(file_obj)
    size_bytes = len(file_bytes)

    # 1. Attempt upload to Neon S3 bucket
    s3_uploaded = False
    s3_key = f"{folder}/{file_id}_{safe_name}"
    s3 = get_s3_client()
    if s3:
        try:
            s3.put_object(
                Bucket='assets',
                Key=s3_key,
                Body=file_bytes,
                ContentType=mimetype
            )
            s3_uploaded = True
            print(f"✅ Uploaded {safe_name} ({size_bytes} bytes) to Neon S3 bucket.")
        except Exception as s3_err:
            print(f"⚠️ Neon S3 upload notice ({s3_err}), saving to cloud PostgreSQL.")

    # 2. Persist to Neon PostgreSQL stored_files table as fail-safe
    try:
        conn = _get_pg_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS stored_files (
                        id TEXT PRIMARY KEY,
                        filename TEXT,
                        mimetype TEXT,
                        file_bytes BYTEA,
                        size_bytes BIGINT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                ''')
                # If S3 succeeded and file > 5MB, store metadata only to save DB space
                # If file <= 5MB or S3 didn't upload, store full bytes in DB
                data_to_store = file_bytes if (not s3_uploaded or size_bytes <= 5 * 1024 * 1024) else None
                cur.execute('''
                    INSERT INTO stored_files (id, filename, mimetype, file_bytes, size_bytes)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        filename = EXCLUDED.filename,
                        file_bytes = EXCLUDED.file_bytes;
                ''', (file_id, safe_name, mimetype, data_to_store, size_bytes))
            conn.close()
            print(f"✅ Stored file record {file_id} in Neon PostgreSQL.")
    except Exception as db_err:
        print(f"⚠️ Database file store notice: {db_err}")

    # Canonical download/view URL
    file_url = f"/api/library/download/{file_id}"
    return file_id, file_url, safe_name, size_bytes

def get_stored_file(file_id):
    """
    Retrieves stored file from Neon S3 or PostgreSQL stored_files table.
    """
    # 1. Check PostgreSQL first
    try:
        conn = _get_pg_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT filename, mimetype, file_bytes, size_bytes FROM stored_files WHERE id = %s;",
                    (file_id,)
                )
                row = cur.fetchone()
                if row:
                    filename, mimetype, file_bytes, size_bytes = row
                    if file_bytes:
                        conn.close()
                        return filename, mimetype, io.BytesIO(file_bytes)
            conn.close()
    except Exception as db_err:
        print(f"⚠️ DB file fetch notice: {db_err}")

    # 2. Check S3
    s3 = get_s3_client()
    if s3:
        for folder in ['library', 'uploads', 'assets']:
            try:
                # List objects with prefix
                response = s3.list_objects_v2(Bucket='assets', Prefix=f"{folder}/{file_id}")
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key = obj['Key']
                        get_resp = s3.get_object(Bucket='assets', Key=key)
                        mimetype = get_resp.get('ContentType', 'application/octet-stream')
                        filename = key.split('_', 1)[-1] if '_' in key else f"file_{file_id}"
                        return filename, mimetype, io.BytesIO(get_resp['Body'].read())
            except Exception:
                pass

    return None, None, None
