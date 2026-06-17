from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.services.ingestion.file_manager import (
    compute_file_sha256,
    count_csv_rows,
    detect_encoding_and_delimiter,
    download_file_to_disk,
    extract_all_zip_members,
    extract_zip_member,
    get_csv_header,
)


def test_download_file_to_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"hello world from streaming download"
    expected_sha = hashlib.sha256(content).hexdigest()
    
    class FakeResponse:
        def __init__(self) -> None:
            self.status_code = 200
        def raise_for_status(self) -> None:
            pass
        def iter_bytes(self, chunk_size: int = 8192) -> list[bytes]:
            return [b"hello ", b"world ", b"from ", b"streaming ", b"download"]
        def __enter__(self) -> FakeResponse:
            return self
        def __exit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: Any | None) -> None:
            pass

    monkeypatch.setattr(
        httpx, 
        "stream", 
        lambda method, url, timeout: FakeResponse()
    )
    
    dest_file = tmp_path / "downloaded.txt"
    sha = download_file_to_disk("http://fakeurl", str(dest_file))
    
    assert sha == expected_sha
    assert dest_file.exists()
    assert dest_file.read_bytes() == content


def test_compute_file_sha256(tmp_path: Path) -> None:
    content = b"test compute sha256 content"
    expected_sha = hashlib.sha256(content).hexdigest()
    
    test_file = tmp_path / "hash_test.txt"
    test_file.write_bytes(content)
    
    sha = compute_file_sha256(str(test_file))
    assert sha == expected_sha


def test_extract_zip_member(tmp_path: Path) -> None:
    zip_file = tmp_path / "test.zip"
    dest_dir = tmp_path / "extracted"
    
    with zipfile.ZipFile(zip_file, "w") as z:
        z.writestr("member1.csv", "a;b\n1;2")
        z.writestr("member2.txt", "ignore")
        
    extracted_path = extract_zip_member(str(zip_file), "member1.csv", str(dest_dir))
    
    assert Path(extracted_path).exists()
    assert Path(extracted_path).name == "member1.csv"
    assert Path(extracted_path).read_text() == "a;b\n1;2"


def test_extract_all_zip_members(tmp_path: Path) -> None:
    zip_file = tmp_path / "test.zip"
    dest_dir = tmp_path / "extracted"
    
    with zipfile.ZipFile(zip_file, "w") as z:
        z.writestr("a.csv", "1;2")
        z.writestr("b.csv", "3;4")
        z.writestr("c.txt", "ignored")
        
    extracted_paths = extract_all_zip_members(str(zip_file), str(dest_dir))
    
    assert len(extracted_paths) == 2
    assert any(Path(p).name == "a.csv" for p in extracted_paths)
    assert any(Path(p).name == "b.csv" for p in extracted_paths)
    assert not any(Path(p).name == "c.txt" for p in extracted_paths)


def test_detect_encoding_and_delimiter_utf8_semicolon(tmp_path: Path) -> None:
    csv_file = tmp_path / "utf8_semi.csv"
    # UTF-8 with BOM
    csv_file.write_bytes(b"\xef\xbb\xbfcol1;col2\nval1;val2")
    
    encoding, delimiter = detect_encoding_and_delimiter(str(csv_file))
    assert encoding == "utf-8-sig"
    assert delimiter == ";"


def test_detect_encoding_and_delimiter_latin1_comma(tmp_path: Path) -> None:
    csv_file = tmp_path / "latin1_comma.csv"
    # Latin-1 with special character, comma delimiter
    csv_file.write_bytes("cabeção,col2\nval1,val2".encode("latin1"))
    
    encoding, delimiter = detect_encoding_and_delimiter(str(csv_file))
    assert encoding == "latin1"
    assert delimiter == ","


def test_get_csv_header(tmp_path: Path) -> None:
    csv_file = tmp_path / "header.csv"
    csv_file.write_text("header1;header2;header3\n1;2;3")
    
    header = get_csv_header(str(csv_file), "utf-8", ";")
    assert header == ["header1", "header2", "header3"]


def test_count_csv_rows(tmp_path: Path) -> None:
    csv_file = tmp_path / "rows.csv"
    csv_file.write_text("col1;col2\n1;2\n3;4\n5;6")
    
    row_count = count_csv_rows(str(csv_file), "utf-8", ";")
    assert row_count == 3
