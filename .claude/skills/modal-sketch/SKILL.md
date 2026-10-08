---
name: modal-sketch
description: 音色を先に決め、その音色から導いたモードで単旋律の候補を作り、MIDI 化して Logic Pro MCP 経由で Logic Pro に配置し、残りのパート（ベース・和声・対旋律・リズム）を補完する。「音色から旋律を作って」「モーダルなメロディを Logic に」「残りのパートをアレンジして」などで使う。
---

# 音色先行モーダル・スケッチ（Logic Pro MCP）

前提: Mac 上で `logic-pro` MCP サーバー（MongLong0214/logic-pro-mcp）が接続済みで、Logic Pro でプロジェクトが開いていること。
未接続なら `scripts/setup-macos.sh` と README の手順を案内して止まる。

## 0. 準備確認
- `logic://system/health` リソースで ready なチャンネルを確認する。
- `logic://project/info` と `logic://tracks` を読む。プロジェクトが無ければユーザーに確認してから `logic_project` の `new`。

## 1. 音色を定める（最初に必ず）
- ユーザーの言葉（例:「霧の中の尺八」「硬いガラスのプラック」）を、`modal_sketch/timbres.py` のプリセットに当てはめるか、
  独自 JSON（brightness / warmth / attack / sustain / breath / low / high、各 0..1 と MIDI 音域）を `out/<name>/timbre.json` に書く。
- Logic 側の音源も同時に決める: `logic_tracks` の `resolve_path`（`patch_hints` を起点に）で `exists: true, kind: "leaf", loadable: true` を確認。
  見つからなければ `scan_library` → `logic://library/inventory` から近いものを提案する。

## 2. 音色からモードを導く
```bash
python3 -m modal_sketch modes --timbre <preset>        # または --timbre-file out/<name>/timbre.json
```
上位 2〜3 モードの理由（明るさ・特性音: Lydian #4, Ionian ♮7, Mixolydian ♭7, Dorian ♮6, Aeolian ♭6, Phrygian ♭2, Locrian ♭5）を一言添えてユーザーに示す。
ユーザーがモードを指定したらそれに従う（`--mode dorian phrygian`）。

## 3. 単旋律の候補を生成
```bash
python3 -m modal_sketch generate --timbre <preset> --tonic D --bars 8 --tempo 72 --count 3 --out out/<name>
```
- `out/<name>/*.mid`（Finder から Logic にドラッグしても試聴できる）と `out/<name>/manifest.json` ができる。
- 候補ごとの `note_count` / `range` / `characteristic_hits` を表にして示し、試聴する候補を選んでもらう。

## 4. Logic Pro に配置（1 回の書き込みごとに確認）
`record_sequence` は MIDI を書き込む L1 操作。**どの候補をどこに置くかをユーザーに確認してから**実行する。
1. テンポ: `logic_transport` `set_tempo` `{ "bpm": <tempo> }`
2. 旋律: `logic_tracks` `record_sequence` に manifest の `candidates[i].record_sequence`（`bar`, `tempo`, `notes`）をそのまま渡す。
   新しいトラックが作られる。応答が `verified: true`（State A）になるまで次の書き込みをしない。State B/C は理由を報告して止まる。
3. `logic://tracks` で新トラックの index と名前を読み、`rename`（例: `Melody - <timbre>`）。
4. 音源: `set_instrument` に `index` + `expected_name`（直前に読んだ名前）+ `path` を渡す（bare index は拒否される）。

注意: `logic_midi` `import_file` はサーバー管理の一時 .mid しか受け付けないので、生成した .mid を直接渡さない。必ず `record_sequence` を使う。

## 5. 残りのパートを補完（アレンジ）
manifest の `notes`（`[pitch, start_tick, duration_tick, velocity]`、PPQ 480・4/4）を読み、旋律に合わせて各パートを作曲し、
同じ `"pitch,offsetMs,durMs,vel,ch;..."` 形式で `record_sequence` する（ms = tick × 60000 / (tempo × 480)）。

モーダルらしさを保つ規則:
- 使う音はすべて同じモード内。特性音を和声側でも強調し、主音ペダル/ドローンで中心を示す。
- 機能和声の V→I（導音の解決）を避け、モード固有の終止を使う:
  Dorian i–IV / ♭VII–i、Aeolian ♭VI–♭VII–i、Phrygian ♭II–i、Lydian II–I、Mixolydian ♭VII–I、Ionian は IV–I や vi–I。
- ベース: 主音と5度中心のドローン、またはフレーズ頭で旋律と反行。旋律と同じ音域に入れない。
- 和声パッド: 長い音価で 3〜4 声。旋律の長い音とは協和、特性音を含む和音を1つは置く。
- 対旋律: 旋律が長く伸ばす箇所でだけ動く（リズム的補完）。
- リズム: `create_drummer` か、打楽器を Ch10 で `record_sequence`。
- 1 パートずつ「パート名・音源・小節範囲・概要」を提示して確認 → 書き込み → `verified` を確認 → `rename` / `set_instrument`。

## 6. 仕上げ
- `logic://project/audit` で問題（External MIDI トラック等）を確認。
- 保存はユーザー確認の上で `logic_project` `save`。
- 使った timbre / mode / seed を `out/<name>/manifest.json` と一緒に残すと再生成できる。
