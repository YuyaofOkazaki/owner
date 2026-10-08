# 音色先行モーダル・スケッチ × Logic Pro MCP

**音色を先に決め → その音色に合うモードを導き → 単旋律の候補を作り → MIDI にして Logic Pro に置き → 残りのパートを AI（Claude Code）で補完する**ためのリポジトリです。

Logic Pro の操作には [MongLong0214/logic-pro-mcp](https://github.com/MongLong0214/logic-pro-mcp)（Logic Pro MCP Server, MIT）を使います。

```
音色プロファイル ──▶ モード順位 ──▶ 単旋律候補 (.mid + manifest.json)
 (brightness,          (Lydian…        │
  warmth, attack,       Locrian)       ▼
  sustain, breath)              logic_tracks.record_sequence ──▶ Logic Pro
                                        │
                     Claude Code が旋律を読んで ベース/和声/対旋律/リズム を補完
```

## 構成

| パス | 内容 |
|------|------|
| `.mcp.json` | Claude Code 用のプロジェクトスコープ MCP 登録（`logic-pro` → `LogicProMCP`、デスクトップ版 Logic Pro に固定） |
| `scripts/setup-macos.sh` | Homebrew で Logic Pro MCP を導入し、権限チェックと doctor を実行 |
| `modal_sketch/` | 音色 → モード → 単旋律 → MIDI / `record_sequence` 引数を出す Python ツール（標準ライブラリのみ） |
| `.claude/skills/modal-sketch/SKILL.md` | Claude Code に一連のワークフロー（配置・アレンジ規則を含む）を教えるスキル |
| `tests/` | `python3 -m unittest discover -s tests -t .` |

## 1. Logic Pro MCP の導入（Mac で）

必要なもの: macOS 14+（Logic Pro 12.3 は macOS 15.6+）、Logic Pro 12.0.1 以上（12.3 が検証対象）、Homebrew、Claude Code。

```bash
git clone <このリポジトリ> && cd owner
./scripts/setup-macos.sh
```

スクリプトがやること:

```bash
brew tap MongLong0214/logic-pro-mcp https://github.com/MongLong0214/logic-pro-mcp
brew trust monglong0214/logic-pro-mcp   # Homebrew 6.0+ のみ
brew install logic-pro-mcp
LogicProMCP --check-permissions
LogicProMCP doctor --profile core --client claude-code
```

その後の手動ステップ:

1. **システム設定 > プライバシーとセキュリティ**
   - アクセシビリティ: Claude Code を起動するアプリ（ターミナル / iTerm / VS Code など）
   - オートメーション: そのアプリに **Logic Pro** と **System Events** の両方
2. Logic Pro で **`LogicProMCP-MCU-Internal`** を MCU コントロールサーフェスとして登録（[公式 SETUP.md](https://github.com/MongLong0214/logic-pro-mcp/blob/main/docs/SETUP.md)）
3. このディレクトリで `claude` を起動すると `.mcp.json` の `logic-pro` サーバーの承認を求められるので許可
4. 「Logic Pro MCP の health を確認して ready なチャンネルを全部見せて」と聞く → 7（Key Commands と Scripter を省いたなら 5）チャンネル ready ならOK

> リリースバイナリは ad-hoc 署名なので、**アップグレードのたびに権限の再付与が必要**です。
> 他のディレクトリでも使う場合は `claude mcp add --scope user logic-pro -- LogicProMCP`。

## 2. 単旋律の生成（どこでも動く）

```bash
python3 -m modal_sketch timbres                       # 音色プリセット一覧
python3 -m modal_sketch modes --timbre shakuhachi     # 音色に合うモードの順位
python3 -m modal_sketch generate --timbre shakuhachi --tonic E --bars 8 --tempo 66 --count 3 --out out/shaku
```

- 音色プリセット: `flute`, `shakuhachi`, `cello`, `analog_pad`, `glass_pluck`, `bell`, `dark_lead`, `nylon_guitar`
- 独自音色は JSON で: `--timbre-file my_timbre.json`
  ```json
  {"name": "fog_reed", "brightness": 0.3, "warmth": 0.6, "attack": 0.2,
   "sustain": 0.8, "breath": 0.9, "low": 55, "high": 84,
   "patch_hints": ["World/Asia/Shakuhachi"]}
  ```
- モードを明示するなら `--mode dorian phrygian`

### 音色 → モード / 旋律の規則

| 音色パラメータ | 影響 |
|---|---|
| brightness | 明るいほど Lydian / Ionian、暗いほど Aeolian / Phrygian（Locrian は暗く硬い音色以外で減点） |
| warmth | 高いほど中庸な Dorian / Mixolydian 付近を好む |
| attack | 高いほど短い音価・同音反復・跳躍が増える |
| sustain | 高いほど長い音価・順次進行が増える |
| breath | 2小節ごとの息継ぎ（休符）の頻度 |
| low / high | 旋律の音域 |

旋律は常に: モード内の音のみ／特性音（Lydian #4, Mixolydian ♭7, Dorian ♮6, Aeolian ♭6, Phrygian ♭2, Locrian ♭5…）を最低1回／三全音跳躍なし／大跳躍の後は反行順次／主音へ順次進行で終止（2拍以上）。同じ seed なら同じ結果。

出力 `out/<name>/manifest.json` の各候補には、Logic Pro MCP の `logic_tracks` → `record_sequence` にそのまま渡せる `{"bar", "tempo", "notes": "pitch,offsetMs,durMs,vel,ch;..."}` が入っています。

## 3. Logic に置いて、残りを補完する

Claude Code でこのリポジトリを開き、例えば:

> 霧の中で鳴る尺八みたいな音色で、Eを主音に8小節のモーダルな旋律候補を作って。良いのを Logic に置いたら、ベースのドローンとパッド、静かなパーカッションを足して。

`modal-sketch` スキルが、音色決定 → モード提示 → 候補生成 → （確認の上で）`record_sequence` → トラック名・音源設定 → 他パートの作曲と配置、の順に進めます。アレンジでは V→I を避けてモード固有の終止（Dorian ♭VII–i、Phrygian ♭II–i、Lydian II–I など）を使います。

注意点（Logic Pro MCP 側の仕様）:
- `logic_midi import_file` はサーバー管理の一時 .mid しか受け付けないため、生成した `.mid` は MCP 経由ではなく `record_sequence` で書き込みます（`.mid` は手動ドラッグでの試聴・保存用）。
- `record_sequence` は呼び出しごとに新しいトラックを作り、1回 1024 ノートまで。
- MIDI の読み戻し（ノート検証）は未実装なので、配置後は Logic 上で耳と目で確認してください。
- このリポジトリのクラウド環境（Linux）では Logic Pro MCP は動きません。生成ツールとテストは動きます。
