import os

from src.database import get_supabase_client

BUCKET_NAME = "filing-documents"


def upload_file(local_path: str, storage_path: str) -> dict:
    """Upload a local file to the private Supabase Storage bucket.

    Args:
        local_path: Path to the local file to upload.
        storage_path: Destination path inside the bucket (e.g. "parsed/qcom/filing.txt").

    Returns:
        A dict with bucket, storage_path, and local_path.

    Raises:
        FileNotFoundError: If the local file does not exist.
    """
    if not os.path.exists(local_path):
        raise FileNotFoundError(
            f"Local file not found: {local_path!r}. "
            "Make sure the file has been downloaded or parsed before uploading."
        )

    supabase = get_supabase_client()
    bucket = supabase.storage.from_(BUCKET_NAME)

    with open(local_path, "rb") as f:
        bucket.upload(
            path=storage_path,
            file=f,
            file_options={"upsert": "true"},
        )

    return {
        "bucket": BUCKET_NAME,
        "storage_path": storage_path,
        "local_path": local_path,
    }
