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


def create_signed_url(storage_path: str, expires_in: int = 3600) -> str:
    """Create a short-lived signed URL for a private Storage object.

    Lets the browser download a private object (e.g. a report PDF) without ever
    exposing the bucket publicly or leaking credentials. The URL expires after
    ``expires_in`` seconds.

    Raises:
        RuntimeError: If the object is missing or the signed URL cannot be made.
    """
    supabase = get_supabase_client()
    bucket = supabase.storage.from_(BUCKET_NAME)
    try:
        result = bucket.create_signed_url(storage_path, expires_in)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to sign '{storage_path}' in bucket '{BUCKET_NAME}': {exc}"
        ) from exc
    # The client returns the URL under one of these keys depending on version.
    url = result.get("signedURL") or result.get("signedUrl") or result.get("signed_url")
    if not url:
        raise RuntimeError(f"No signed URL returned for '{storage_path}'.")
    return url


def download_file(storage_path: str, local_path: str) -> str:
    """Download a file from the private Supabase Storage bucket.

    Args:
        storage_path: Path of the object inside the bucket.
        local_path: Local path where the file will be saved.

    Returns:
        The local_path where the file was saved.

    Raises:
        RuntimeError: If the download fails.
    """
    supabase = get_supabase_client()
    bucket = supabase.storage.from_(BUCKET_NAME)

    try:
        content = bucket.download(storage_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to download '{storage_path}' from bucket '{BUCKET_NAME}': {exc}"
        ) from exc

    parent_dir = os.path.dirname(local_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(local_path, "wb") as f:
        f.write(content)

    return local_path
