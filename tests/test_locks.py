from __future__ import annotations

import json

import pytest

from prosperity.orchestration.locks import file_lock


def test_file_lock_reclaims_existing_plain_file(tmp_path):
    path = tmp_path / "conversation.loop.lock"
    path.write_text("locked", encoding="utf-8")

    with file_lock(path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "pid" in payload
        assert "acquired_at" in payload

    assert not path.exists()


def test_file_lock_blocks_second_acquire(tmp_path):
    path = tmp_path / "conversation.loop.lock"

    with file_lock(path):
        with pytest.raises(RuntimeError, match="Lock already held"):
            with file_lock(path):
                pass
