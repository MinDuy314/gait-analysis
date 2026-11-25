"""Tests for Milestone 6: File upload and storage."""
import pytest
import tempfile
from pathlib import Path
from src.storage.file_storage import FileStorage, ALLOWED_EXTENSIONS


@pytest.fixture
def storage():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield FileStorage(storage_root=Path(tmpdir))


def _make_tmp_file(suffix=".mp4", size=1024):
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.write(b"0" * size)
    f.flush()
    f.close()
    return Path(f.name)


def test_allowed_extension(storage):
    for ext in ALLOWED_EXTENSIONS:
        src = _make_tmp_file(suffix=ext)
        name, path, sz = storage.save_upload(src, f"test{ext}", "S001", "SES001")
        assert path.exists()
        assert sz == 1024


def test_disallowed_extension(storage):
    src = _make_tmp_file(suffix=".exe")
    with pytest.raises(ValueError, match="Unsupported"):
        storage.save_upload(src, "malicious.exe", "S001", "SES001")
    src.unlink(missing_ok=True)


def test_file_size_limit(storage):
    storage.max_size_bytes = 100
    src = _make_tmp_file(size=200)
    with pytest.raises(ValueError, match="size"):
        storage.save_upload(src, "big.mp4", "S001", "SES001")
    src.unlink(missing_ok=True)


def test_safe_server_filename_no_path_traversal(storage):
    src = _make_tmp_file(suffix=".mp4")
    name, path, _ = storage.save_upload(src, "../../../etc/passwd.mp4", "S001", "SES001")
    assert "/" not in name and "\\" not in name
    assert ".." not in name


def test_delete_file(storage):
    src = _make_tmp_file()
    _, path, _ = storage.save_upload(src, "del.mp4", "S001", "SES001")
    assert path.exists()
    result = storage.delete_file(path)
    assert result
    assert not path.exists()


def test_sha256_computed(storage):
    src = _make_tmp_file(suffix=".mp4", size=512)
    _, path, _ = storage.save_upload(src, "hash.mp4", "S001", "SES001")
    h = storage.compute_sha256(path)
    assert len(h) == 64
