"""Standard MIDI File の書き出しと、Logic Pro MCP の record_sequence 用ノート文字列への変換。"""

from __future__ import annotations

import struct
from pathlib import Path

from .melody import PPQ, Note

# Logic Pro MCP の record_sequence は 1 回あたり 1024 ノートまで、音価は 1..30000ms
MAX_RECORD_SEQUENCE_NOTES = 1024
MAX_DURATION_MS = 30_000


def _vlq(value: int) -> bytes:
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


def to_smf(notes: list[Note], tempo_bpm: float, track_name: str = "", channel: int = 1) -> bytes:
    """フォーマット 0 の SMF バイト列を返す。channel は 1..16。"""
    if not 1 <= channel <= 16:
        raise ValueError("channel must be 1..16")
    ch = channel - 1
    events: list[tuple[int, int, bytes]] = []  # (tick, 順序, データ) note-off を先に
    for n in notes:
        events.append((n.start, 1, bytes([0x90 | ch, n.pitch, n.velocity])))
        events.append((n.start + n.duration, 0, bytes([0x80 | ch, n.pitch, 0])))
    events.sort(key=lambda e: (e[0], e[1]))

    mpqn = round(60_000_000 / tempo_bpm)
    body = bytearray()
    body += _vlq(0) + b"\xff\x51\x03" + mpqn.to_bytes(3, "big")
    body += _vlq(0) + b"\xff\x58\x04\x04\x02\x18\x08"  # 4/4
    if track_name:
        name = track_name.encode("utf-8")
        body += _vlq(0) + b"\xff\x03" + _vlq(len(name)) + name
    last = 0
    for tick, _, data in events:
        body += _vlq(tick - last) + data
        last = tick
    body += _vlq(0) + b"\xff\x2f\x00"

    header = b"MThd" + struct.pack(">IHHH", 6, 0, 1, PPQ)
    return header + b"MTrk" + struct.pack(">I", len(body)) + bytes(body)


def write_smf(path: Path, notes: list[Note], tempo_bpm: float, track_name: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(to_smf(notes, tempo_bpm, track_name))


def ticks_to_ms(ticks: int, tempo_bpm: float) -> int:
    return round(ticks * 60_000 / (tempo_bpm * PPQ))


def to_record_sequence_notes(notes: list[Note], tempo_bpm: float, channel: int = 1) -> str:
    """'pitch,offsetMs,durMs,vel,ch;...' 形式（offset は対象小節の頭から）。"""
    if len(notes) > MAX_RECORD_SEQUENCE_NOTES:
        raise ValueError(f"record_sequence accepts at most {MAX_RECORD_SEQUENCE_NOTES} notes")
    parts = []
    for n in notes:
        dur = min(MAX_DURATION_MS, max(1, ticks_to_ms(n.duration, tempo_bpm)))
        parts.append(f"{n.pitch},{ticks_to_ms(n.start, tempo_bpm)},{dur},{n.velocity},{channel}")
    return ";".join(parts)
