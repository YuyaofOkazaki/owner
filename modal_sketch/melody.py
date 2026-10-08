"""音色とモードから単旋律（モノフォニック）を生成する。"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .modes import Mode, degree_of, scale_pitches
from .timbres import Timbre

PPQ = 480
BAR_TICKS = PPQ * 4  # 4/4 固定

# (音価 tick, 何に向いているか) — 速い立ち上がりは短く、長い持続は長く
_SHORT = (PPQ // 4, PPQ // 2)
_MID = (PPQ, PPQ * 3 // 2)
_LONG = (PPQ * 2, PPQ * 3, PPQ * 4)


@dataclass(frozen=True)
class Note:
    pitch: int
    start: int     # tick
    duration: int  # tick
    velocity: int


def _rhythm(timbre: Timbre, bars: int, rng: random.Random) -> list[tuple[int, int]]:
    """(開始 tick, 音価 tick) の列。breath に応じて2小節ごとに休符を入れる。"""
    weights = {}
    for d in _SHORT:
        weights[d] = 0.2 + 1.6 * timbre.attack * (1 - timbre.sustain * 0.5)
    for d in _MID:
        weights[d] = 1.0
    for d in _LONG:
        weights[d] = 0.15 + 1.4 * timbre.sustain * (1 - timbre.attack * 0.6)

    events: list[tuple[int, int]] = []
    total = bars * BAR_TICKS
    t = 0
    while t < total:
        bar_end = (t // BAR_TICKS + 1) * BAR_TICKS
        phrase_end = (t // (BAR_TICKS * 2) + 1) * BAR_TICKS * 2
        choices = [d for d in weights if t + d <= bar_end] or [bar_end - t]
        dur = rng.choices(choices, weights=[weights.get(d, 1.0) for d in choices])[0]
        # フレーズ末の息継ぎ（最終フレーズは除く）
        if phrase_end < total and t + dur >= phrase_end - PPQ // 2 and rng.random() < timbre.breath * 0.8:
            sounding = max(PPQ // 4, phrase_end - t - PPQ // 2)
            events.append((t, min(dur, sounding)))
            t = phrase_end
            continue
        events.append((t, dur))
        t += dur

    # 終止音（主音）のために最後の2拍を確保する
    final_start = total - PPQ * 2
    events = [(s, d) for s, d in events if s < final_start]
    if events and events[-1][0] + events[-1][1] > final_start:
        s, _ = events[-1]
        events[-1] = (s, final_start - s)
    events.append((final_start, PPQ * 2))
    return events


def _interval_weights(timbre: Timbre) -> dict[int, float]:
    """音階度数での移動量ごとの重み。"""
    step = 1.0 + 2.0 * timbre.sustain
    leap = 0.2 + 1.2 * timbre.attack
    return {0: 0.25 + 0.6 * timbre.attack, 1: step, 2: 0.6 + leap * 0.6, 3: leap * 0.5, 4: leap * 0.4, 7: leap * 0.15}


def generate_line(
    timbre: Timbre,
    mode: Mode,
    tonic_pc: int,
    bars: int,
    seed: int,
    max_tries: int = 50,
) -> list[Note]:
    """1本の単旋律を生成する。

    規則:
      - 主音（finalis）付近から始め、最後は主音へ順次進行で終止する
      - モード特性音を最低1回、できれば強拍に置く
      - 増4度（三全音）の跳躍は避け、4度以上の跳躍の後は反対方向へ順次進行
      - 長い音・強拍は安定音（主音・5度・特性音）を好む
    """
    rng = random.Random(seed)
    pitches = scale_pitches(tonic_pc, mode, timbre.low, timbre.high)
    if len(pitches) < 8:
        raise ValueError("range too narrow for this mode")
    center = (timbre.low + timbre.high) // 2
    finals = [i for i, p in enumerate(pitches) if p % 12 == tonic_pc]
    home = min(finals, key=lambda i: abs(pitches[i] - center))
    stable = {0, 4, mode.characteristic}
    iw = _interval_weights(timbre)

    best: list[Note] = []
    for _ in range(max_tries):
        rhythm = _rhythm(timbre, bars, rng)
        idx = home if rng.random() < 0.6 else min(home + 4, len(pitches) - 1)
        last_leap = 0
        line: list[int] = []
        for n, (start, dur) in enumerate(rhythm):
            if n == 0:
                line.append(idx)
                continue
            remaining = len(rhythm) - n
            if remaining == 1:
                idx = min(finals, key=lambda i: abs(i - idx))
                line.append(idx)
                break
            if remaining == 2:
                # 主音の上下どちらかの隣接音で終止を準備
                target = min(finals, key=lambda i: abs(i - idx))
                idx = target + (1 if idx > target else -1)
                idx = max(0, min(len(pitches) - 1, idx))
                line.append(idx)
                continue
            candidates, weights = [], []
            for size, w in iw.items():
                for sign in ((1, -1) if size else (1,)):
                    cand = idx + sign * size
                    if not 0 <= cand < len(pitches):
                        continue
                    if abs(pitches[cand] - pitches[idx]) == 6:
                        continue  # 三全音跳躍を避ける
                    if abs(last_leap) >= 3 and (sign == (1 if last_leap > 0 else -1) or size != 1):
                        w = w * 0.1  # 大跳躍の後は反対方向へ順次
                    deg = degree_of(pitches[cand], tonic_pc, mode)
                    strong = start % (PPQ * 2) == 0
                    if deg in stable and (strong or dur >= PPQ * 2):
                        w *= 1.8
                    if deg == mode.characteristic:
                        w *= 1.4
                    # 中央に引き戻す
                    w *= 1.0 / (1.0 + abs(pitches[cand] - center) / 12)
                    candidates.append(cand)
                    weights.append(w)
            nxt = rng.choices(candidates, weights=weights)[0]
            last_leap = nxt - idx
            idx = nxt
            line.append(idx)

        notes = []
        for (start, dur), i in zip(rhythm, line):
            strong = start % BAR_TICKS == 0
            vel = int(60 + 30 * timbre.attack + (10 if strong else 0) + rng.randint(-6, 6))
            notes.append(Note(pitches[i], start, dur, max(1, min(127, vel))))
        degs = [degree_of(n.pitch, tonic_pc, mode) for n in notes]
        if mode.characteristic in degs:
            return notes
        best = best or notes
    return best
