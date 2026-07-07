"""Environment-agnostic tests for player.py.

CI runners lack mpv/cvlc/afplay, so we never assert on which player is chosen.
We test the pure, deterministic pieces: media listing, path resolution (incl.
traversal rejection), and _build_cmd's shape *only when* a player happens to be
available on the current machine.
"""
import shutil
from pathlib import Path

import pytest

import player
from config import MEDIA_DIR


def test_list_media_returns_list():
    media = player.list_media()
    assert isinstance(media, list)
    # The repo ships several adhan mp3s at MEDIA_DIR (the repo root).
    assert all(isinstance(name, str) for name in media)
    assert all(Path(name).suffix.lower() in {".mp3", ".m4a", ".wav"} for name in media)


def test_list_media_sorted():
    media = player.list_media()
    assert media == sorted(media)


def test_resolve_media_accepts_known_file():
    media = player.list_media()
    if not media:
        pytest.skip("no media files present in MEDIA_DIR")
    name = media[0]
    path = player.resolve_media(name)
    assert path.name == name
    assert path.parent == MEDIA_DIR.resolve()


def test_resolve_media_rejects_traversal():
    with pytest.raises(FileNotFoundError):
        player.resolve_media("../config.py")


def test_resolve_media_rejects_unknown():
    with pytest.raises(FileNotFoundError):
        player.resolve_media("does-not-exist.mp3")


def test_resolve_media_rejects_non_audio_extension():
    # config.py lives next to the media dir but is not an allowed audio file.
    with pytest.raises(FileNotFoundError):
        player.resolve_media("config.py")


_HAS_PLAYER = any(shutil.which(p) for p in ("mpv", "cvlc", "afplay"))


@pytest.mark.skipif(not _HAS_PLAYER, reason="no audio player on this machine")
def test_build_cmd_shape_when_player_present():
    media = player.list_media()
    if not media:
        pytest.skip("no media files present in MEDIA_DIR")
    path = player.resolve_media(media[0])
    cmd, has_ipc = player._build_cmd(path, 80, None)
    assert isinstance(cmd, list) and cmd
    assert isinstance(has_ipc, bool)
    # The resolved media path is always the final argument.
    assert cmd[-1] == str(path)
    # IPC is only advertised for the mpv backend.
    assert has_ipc == (cmd[0] == "mpv")
