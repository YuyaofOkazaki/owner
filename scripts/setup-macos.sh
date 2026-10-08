#!/usr/bin/env bash
# Logic Pro MCP Server (MongLong0214/logic-pro-mcp) を macOS に導入する。
# Logic Pro がインストールされた Mac で実行すること（Linux/クラウド環境では動かない）。
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "このスクリプトは macOS 専用です。" >&2
  exit 1
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew が見つかりません: https://brew.sh" >&2
  exit 1
fi

brew tap MongLong0214/logic-pro-mcp https://github.com/MongLong0214/logic-pro-mcp
# Homebrew 6.0+ はサードパーティ tap の trust が必要（それより古い場合このコマンドは存在しない）
brew trust monglong0214/logic-pro-mcp 2>/dev/null || true
if brew list logic-pro-mcp >/dev/null 2>&1; then
  brew upgrade logic-pro-mcp || true
else
  brew install logic-pro-mcp
fi

# このリポジトリの .mcp.json でプロジェクトスコープ登録済み。
# 他のディレクトリからも使いたい場合のみユーザースコープに登録する:
#   claude mcp add --scope user logic-pro -- LogicProMCP

echo
echo "== 権限チェック =="
LogicProMCP --check-permissions || true
echo
echo "== doctor (core プロファイル, Claude Code) =="
LogicProMCP doctor --profile core --client claude-code || true

cat <<'MSG'

残りの手動ステップ:
  1. システム設定 > プライバシーとセキュリティ
     - アクセシビリティ: Claude Code を起動するアプリ（ターミナル等）を許可
     - オートメーション: そのアプリに「Logic Pro」と「System Events」の両方を許可
  2. Logic Pro で LogicProMCP-MCU-Internal を MCU コントロールサーフェスとして登録
     (詳細: https://github.com/MongLong0214/logic-pro-mcp/blob/main/docs/SETUP.md)
  3. Claude Code で「Logic Pro MCP の health を確認して ready なチャンネルを全部見せて」と聞く
※ アップグレード後は署名が変わるため権限の再付与が必要です。
MSG
