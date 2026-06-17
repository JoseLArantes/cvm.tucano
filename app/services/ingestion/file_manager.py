from __future__ import annotations

import csv
import hashlib
import zipfile
from pathlib import Path

import httpx

DEFAULT_CSV_DELIMITER = ";"


def download_file_to_disk(url: str, dest_path: str, timeout: float = 300) -> str:
    """Downloads a file from the URL directly to the destination path on disk using streaming.
    
    Computes the SHA256 checksum on the fly.
    Returns the SHA256 hex digest of the downloaded file.
    """
    dest_path_obj = Path(dest_path)
    dest_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    sha256 = hashlib.sha256()
    with httpx.stream("GET", url, timeout=timeout) as response:
        response.raise_for_status()
        with open(dest_path_obj, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                f.write(chunk)
                sha256.update(chunk)
                
    return sha256.hexdigest()


def compute_file_sha256(file_path: str) -> str:
    """Computes the SHA256 checksum of a file on disk in a memory-safe streamed way."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_zip_member(zip_path: str, member_name: str, dest_dir: str) -> str:
    """Safely extracts a single member CSV file from the ZIP archive to dest_dir.
    
    Returns the absolute path to the extracted file.
    """
    dest_dir_obj = Path(dest_dir)
    dest_dir_obj.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path) as archive:
        archive.extract(member_name, path=dest_dir_obj)
        
    return str(dest_dir_obj / member_name)


def extract_all_zip_members(zip_path: str, dest_dir: str) -> list[str]:
    """Extracts all CSV files inside a ZIP archive to dest_dir.
    
    Returns a list of absolute paths of the extracted members.
    """
    dest_dir_obj = Path(dest_dir)
    dest_dir_obj.mkdir(parents=True, exist_ok=True)
    
    extracted_paths = []
    with zipfile.ZipFile(zip_path) as archive:
        for member_name in archive.namelist():
            if not member_name.endswith(".csv"):
                continue
            archive.extract(member_name, path=dest_dir_obj)
            extracted_paths.append(str(dest_dir_obj / member_name))
            
    return extracted_paths


def detect_encoding_and_delimiter(file_path: str) -> tuple[str, str]:
    """Reads a small prefix of the file to detect the encoding and delimiter.
    
    Tries utf-8-sig first, then latin-1.
    Checks if ';' is present to determine the delimiter, defaulting to ';'.
    """
    with open(file_path, "rb") as f:
        prefix_bytes = f.read(65536)  # 64 KB prefix
        
    encoding = "utf-8-sig"
    try:
        prefix_text = prefix_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        prefix_text = prefix_bytes.decode("latin1", errors="replace")
        encoding = "latin1"
        
    # Simple delimiter heuristic
    first_line = prefix_text.splitlines()[0] if prefix_text else ""
    delimiter = DEFAULT_CSV_DELIMITER
    if ";" in first_line:
        delimiter = ";"
    elif "," in first_line:
        delimiter = ","
        
    return encoding, delimiter


def get_csv_header(file_path: str, encoding: str, delimiter: str) -> list[str]:
    """Reads only the first line of the CSV to retrieve headers."""
    with open(file_path, encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            return next(reader)
        except StopIteration:
            return []


def count_csv_rows(file_path: str, encoding: str, delimiter: str) -> int:
    """Counts the number of rows in the CSV file by streaming through it.
    
    Does not load the entire file into memory.
    """
    with open(file_path, encoding=encoding, errors="replace") as f:
        reader = csv.reader(f, delimiter=delimiter)
        try:
            next(reader)  # Skip header
        except StopIteration:
            return 0
        return sum(1 for _ in reader)
