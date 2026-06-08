"""
Test the Supabase Storage uploader using the already-parsed Qualcomm 10-Q text file.
Uploads to the private filing-documents bucket. Does not make the bucket public.
Does not delete the local file.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from src.storage import upload_file

LOCAL_PATH = "data/parsed_filings/qcom_0000804328_26_000061.txt"
STORAGE_PATH = "parsed/qcom/0000804328-26-000061.txt"


def main():
    if not os.path.exists(LOCAL_PATH):
        print(f"ERROR: Local file not found: {LOCAL_PATH}")
        print("Please run: python test_filing_downloader.py")
        sys.exit(1)

    file_size = os.path.getsize(LOCAL_PATH)

    print(f"Uploading parsed filing to Supabase Storage...")
    result = upload_file(LOCAL_PATH, STORAGE_PATH)

    print(f"  Bucket       : {result['bucket']}")
    print(f"  Storage path : {result['storage_path']}")
    print(f"  Local path   : {result['local_path']}")
    print(f"  File size    : {file_size:,} bytes")

    assert result["bucket"] == "filing-documents", (
        f"Unexpected bucket: {result['bucket']!r}."
    )
    assert result["storage_path"] == STORAGE_PATH, (
        f"Unexpected storage path: {result['storage_path']!r}."
    )
    assert result["local_path"] == LOCAL_PATH, (
        f"Unexpected local path: {result['local_path']!r}."
    )

    print()
    print("PASS: storage upload is working correctly.")
    print("Rerunning this test will safely overwrite the same object (upsert enabled).")


if __name__ == "__main__":
    main()
