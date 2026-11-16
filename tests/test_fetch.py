import hashlib

import pytest

from tools import fetch_sources


def test_verify_accepts_matching_digest(tmp_path):
    data = b"state tb score"
    p = tmp_path / "f.bin"
    p.write_bytes(data)
    fetch_sources.verify(p, hashlib.sha256(data).hexdigest())


def test_verify_rejects_tampered_file(tmp_path):
    data = bytearray(b"state tb score")
    digest = hashlib.sha256(bytes(data)).hexdigest()
    data[0] ^= 0x01
    p = tmp_path / "f.bin"
    p.write_bytes(bytes(data))
    with pytest.raises(ValueError):
        fetch_sources.verify(p, digest)
