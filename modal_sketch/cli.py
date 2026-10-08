"""音色 → モード候補 → 単旋律 → MIDI / record_sequence 用 JSON を出力する CLI。

例:
  python3 -m modal_sketch timbres
  python3 -m modal_sketch modes --timbre cello
  python3 -m modal_sketch generate --timbre cello --tonic D --bars 8 --tempo 72 --count 4 --out out/cello_d
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .export import to_record_sequence_notes, write_smf
from .melody import BAR_TICKS, generate_line
from .modes import MODES, NOTE_NAMES, degree_of, parse_tonic, rank_modes
from .timbres import PRESETS, Timbre, get_timbre, timbre_from_dict


def _load_timbre(args: argparse.Namespace) -> Timbre:
    if args.timbre_file:
        return timbre_from_dict(json.loads(Path(args.timbre_file).read_text(encoding="utf-8")))
    return get_timbre(args.timbre)


def cmd_timbres(_: argparse.Namespace) -> int:
    for t in PRESETS.values():
        print(f"{t.name:14s} {t.description}  (bright={t.brightness} warm={t.warmth} "
              f"attack={t.attack} sustain={t.sustain} breath={t.breath}, "
              f"range={t.low}-{t.high})")
    return 0


def cmd_modes(args: argparse.Namespace) -> int:
    timbre = _load_timbre(args)
    for mode, score in rank_modes(timbre):
        print(f"{mode.name:11s} {score:.3f}")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    timbre = _load_timbre(args)
    tonic_pc = parse_tonic(args.tonic)
    if args.mode:
        modes = [MODES[m] for m in args.mode]
    else:
        modes = [m for m, _ in rank_modes(timbre)[: args.top_modes]]

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    candidates = []
    for mi, mode in enumerate(modes):
        for k in range(args.count):
            seed = args.seed + mi * 1000 + k
            notes = generate_line(timbre, mode, tonic_pc, args.bars, seed)
            cid = f"{timbre.name}_{NOTE_NAMES[tonic_pc].replace('#', 's')}_{mode.name}_{k + 1:02d}"
            write_smf(out / f"{cid}.mid", notes, args.tempo, track_name=cid)
            degrees = [degree_of(n.pitch, tonic_pc, mode) for n in notes]
            candidates.append({
                "id": cid,
                "mode": mode.name,
                "tonic": NOTE_NAMES[tonic_pc],
                "seed": seed,
                "bars": args.bars,
                "note_count": len(notes),
                "range": [min(n.pitch for n in notes), max(n.pitch for n in notes)],
                "characteristic_degree": mode.characteristic + 1,
                "characteristic_hits": degrees.count(mode.characteristic),
                "midi_file": f"{cid}.mid",
                "notes": [[n.pitch, n.start, n.duration, n.velocity] for n in notes],
                # Logic Pro MCP: logic_tracks.record_sequence にそのまま渡せる引数
                "record_sequence": {
                    "bar": args.bar,
                    "tempo": args.tempo,
                    "notes": to_record_sequence_notes(notes, args.tempo),
                },
            })

    manifest = {
        "timbre": timbre.__dict__ | {"patch_hints": list(timbre.patch_hints)},
        "tonic": NOTE_NAMES[tonic_pc],
        "tempo": args.tempo,
        "bars": args.bars,
        "ppq": 480,
        "bar_ticks": BAR_TICKS,
        "mode_ranking": [{"mode": m.name, "score": s} for m, s in rank_modes(timbre)],
        "candidates": candidates,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for c in candidates:
        print(f"{c['id']:40s} notes={c['note_count']:3d} char_hits={c['characteristic_hits']}")
    print(f"-> {out / 'manifest.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="modal_sketch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("timbres", help="音色プリセット一覧").set_defaults(func=cmd_timbres)

    def add_timbre_args(sp: argparse.ArgumentParser) -> None:
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--timbre", help="プリセット名")
        g.add_argument("--timbre-file", help="独自音色の JSON ファイル")

    sp = sub.add_parser("modes", help="音色に合うモードの順位")
    add_timbre_args(sp)
    sp.set_defaults(func=cmd_modes)

    sp = sub.add_parser("generate", help="単旋律を生成して .mid と manifest.json を書き出す")
    add_timbre_args(sp)
    sp.add_argument("--tonic", default="D", help="主音 (例: D, F#, Bb)")
    sp.add_argument("--mode", nargs="+", choices=sorted(MODES), help="モードを明示（省略時は音色から導出）")
    sp.add_argument("--top-modes", type=int, default=3, help="導出時に使う上位モード数")
    sp.add_argument("--count", type=int, default=3, help="モードごとの候補数")
    sp.add_argument("--bars", type=int, default=4)
    sp.add_argument("--tempo", type=float, default=90.0)
    sp.add_argument("--bar", type=int, default=1, help="Logic 上で配置する小節")
    sp.add_argument("--seed", type=int, default=1)
    sp.add_argument("--out", default="out")
    sp.set_defaults(func=cmd_generate)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
