"""教会旋法と、音色からモード候補を導く規則。"""

from __future__ import annotations

from dataclasses import dataclass

from .timbres import Timbre

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLAT_ALIASES = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}


@dataclass(frozen=True)
class Mode:
    name: str
    intervals: tuple[int, ...]   # 主音からの半音数（7音）
    characteristic: int          # そのモードらしさを決める音の音階度数（0 始まり）
    brightness: float            # 0 = 最も暗い (Locrian) 〜 1 = 最も明るい (Lydian)


# 明るさ順（Lydian が最も明るく Locrian が最も暗い）
MODES: dict[str, Mode] = {
    m.name: m
    for m in (
        Mode("lydian", (0, 2, 4, 6, 7, 9, 11), 3, 1.0),        # #4
        Mode("ionian", (0, 2, 4, 5, 7, 9, 11), 6, 5 / 6),      # ♮7 と 4 の対比
        Mode("mixolydian", (0, 2, 4, 5, 7, 9, 10), 6, 4 / 6),  # ♭7
        Mode("dorian", (0, 2, 3, 5, 7, 9, 10), 5, 3 / 6),      # ♮6
        Mode("aeolian", (0, 2, 3, 5, 7, 8, 10), 5, 2 / 6),     # ♭6
        Mode("phrygian", (0, 1, 3, 5, 7, 8, 10), 1, 1 / 6),    # ♭2
        Mode("locrian", (0, 1, 3, 5, 6, 8, 10), 4, 0.0),       # ♭5
    )
}


def parse_tonic(name: str) -> int:
    """'D', 'F#', 'Bb' などをピッチクラス (0..11) に変換する。"""
    key = name.strip()
    key = key[:1].upper() + key[1:]
    key = _FLAT_ALIASES.get(key, key)
    if key not in NOTE_NAMES:
        raise ValueError(f"unknown tonic '{name}'")
    return NOTE_NAMES.index(key)


def rank_modes(timbre: Timbre) -> list[tuple[Mode, float]]:
    """音色に対する各モードの適合度を高い順に返す。

    - 明るさ: 音色の brightness とモードの brightness の近さ
    - 温かさ: warmth が高い音色は中庸なモード (Dorian/Mixolydian 付近) を好む
    - Locrian は不安定なので、極端に暗く硬い音色以外では減点する
    """
    ranked = []
    for mode in MODES.values():
        score = 1.0 - abs(timbre.brightness - mode.brightness)
        score += 0.35 * timbre.warmth * (1.0 - 2 * abs(mode.brightness - 0.58))
        if mode.name == "locrian":
            score -= 0.4 * (1.0 - (1.0 - timbre.brightness) * timbre.attack)
        ranked.append((mode, round(score, 4)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


def scale_pitches(tonic_pc: int, mode: Mode, low: int, high: int) -> list[int]:
    """音域内でモードに属する MIDI ノートを昇順に返す。"""
    pcs = {(tonic_pc + i) % 12 for i in mode.intervals}
    return [p for p in range(low, high + 1) if p % 12 in pcs]


def degree_of(pitch: int, tonic_pc: int, mode: Mode) -> int | None:
    rel = (pitch - tonic_pc) % 12
    return mode.intervals.index(rel) if rel in mode.intervals else None
