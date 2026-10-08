"""音色プロファイル。

各音色は「どのモードが似合うか」と「どんな旋律の動きが自然か」を導くための
いくつかの数値で記述する。値はすべて 0.0〜1.0。

- brightness : 倍音の明るさ。高いほど #4 / ♮7 を含む明るいモードに寄る
- warmth     : 中低域の厚み。高いほど Dorian / Mixolydian のような中庸なモードに寄る
- attack     : 立ち上がりの速さ。高いほど短い音価・反復・跳躍が増える
- sustain    : 持続の長さ。高いほど長い音価・順次進行が増える
- breath     : 息づかい。高いほどフレーズ間の休符が増える

low / high は MIDI ノート番号での推奨音域、patch_hints は Logic の
ライブラリパスの候補（環境により異なるので必ず resolve_path で確認する）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Timbre:
    name: str
    description: str
    brightness: float
    warmth: float
    attack: float
    sustain: float
    breath: float
    low: int
    high: int
    patch_hints: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for attr in ("brightness", "warmth", "attack", "sustain", "breath"):
            value = getattr(self, attr)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{self.name}: {attr} must be within 0..1, got {value}")
        if not 0 <= self.low < self.high <= 127:
            raise ValueError(f"{self.name}: invalid range {self.low}..{self.high}")
        if self.high - self.low < 7:
            raise ValueError(f"{self.name}: range must span at least a fifth")


PRESETS: dict[str, Timbre] = {
    t.name: t
    for t in (
        Timbre("flute", "息の混じった明るい木管", 0.75, 0.35, 0.35, 0.6, 0.8, 60, 93,
               ("Orchestral/Woodwinds/Flute Solo",)),
        Timbre("shakuhachi", "かすれた息と揺れのある尺八系", 0.35, 0.45, 0.25, 0.65, 0.95, 62, 86,
               ("World/Asia/Shakuhachi",)),
        Timbre("cello", "温かく深い擦弦", 0.3, 0.9, 0.2, 0.85, 0.4, 36, 72,
               ("Orchestral/Strings/Cello Solo",)),
        Timbre("analog_pad", "ゆっくり立ち上がる太いアナログパッド", 0.45, 0.8, 0.05, 1.0, 0.2, 48, 79,
               ("Synthesizer/Pad",)),
        Timbre("glass_pluck", "硬質で短いプラック", 0.9, 0.2, 0.95, 0.15, 0.3, 60, 96,
               ("Synthesizer/Pluck",)),
        Timbre("bell", "金属的で長い余韻のベル", 0.95, 0.15, 0.9, 0.7, 0.5, 67, 100,
               ("Mallet/Bells",)),
        Timbre("dark_lead", "歪みのある暗いモノシンセ", 0.2, 0.5, 0.7, 0.5, 0.25, 43, 74,
               ("Synthesizer/Lead",)),
        Timbre("nylon_guitar", "柔らかいナイロン弦", 0.5, 0.65, 0.8, 0.35, 0.35, 40, 81,
               ("Guitar/Acoustic Guitar",)),
    )
}


def get_timbre(name: str) -> Timbre:
    try:
        return PRESETS[name]
    except KeyError:
        known = ", ".join(sorted(PRESETS))
        raise KeyError(f"unknown timbre '{name}'. known: {known}") from None


def timbre_from_dict(data: dict) -> Timbre:
    """JSON などから独自の音色を作る。patch_hints は省略可。"""
    data = dict(data)
    data["patch_hints"] = tuple(data.get("patch_hints", ()))
    data.setdefault("description", data.get("name", "custom"))
    return Timbre(**data)
