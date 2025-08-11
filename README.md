# news-summary-agent
ニュースRSSを取得し、LLMで要約してSlackに配信する自動化エージェント

- **取得**: RSSフィード（`feedparser`）
- **解析**: HTML本文抽出（`BeautifulSoup`）
- **要約**: OpenAI API（構造化JSON出力）
- **配信**: Slack（`slack-sdk`）
- **信頼性**: ネットワークは指数バックオフ付きリトライ（`tenacity`）
- **ログ**: `agent.log` に保存（`loguru`）

## 仕組みと構成
- `agent/io_sources.py`: RSS取得（`fetch_rss`）、記事HTMLからテキスト抽出（`fetch_article_text`）。両方にリトライを適用。
- `agent/llm.py`: 入力（ニュース見出し+URL）をLLMに渡し、JSONスキーマで要約を取得。
- `agent/processors.py`: 一連の処理をまとめ、整形テキストを組み立て。
- `agent/notifiers.py`: Slack へ投稿。
- `run_once.py`: ワンショットで実行して結果を標準出力とSlackに送信。

## 必要要件
- Python 3.9 以上を推奨
- OpenAI API キー（`OPENAI_API_KEY`）
- Slack Bot Token（`SLACK_BOT_TOKEN`。Slack 投稿を使う場合）
- RSS フィードURL（`NEWS_RSS`）

## セットアップ
1) 仮想環境の作成と有効化
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
```

2) 依存関係のインストール
```bash
pip install -r requirements.txt
# openai が未インストールの場合は追加
pip install openai
```

3) 環境変数の設定（`.env` を利用）
`.env` を作成し、以下を参考に設定してください。
```bash
OPENAI_API_KEY=sk-...               # OpenAIのAPIキー
MODEL=gpt-5-nano                    # 既定モデル名（必要に応じて変更）
NEWS_RSS=https://example.com/rss    # 要約対象のRSSフィードURL
SLACK_BOT_TOKEN=xoxb-...            # Slack Bot Token（任意。未設定でも実行可）
SLACK_CHANNEL=#general              # 投稿先チャンネル（任意、既定は #general）
```
`agent/config.py` は `python-dotenv` により `.env` を自動読み込みします。

## 使い方
### ワンショット実行
```bash
python run_once.py
```
- 標準出力に要約を表示します。
- Slack の設定がある場合はチャンネルにも投稿します（失敗時はログに記録）。

## 環境変数一覧
- `OPENAI_API_KEY`: OpenAIのAPIキー（必須）
- `MODEL`: 使用モデル名。既定は `gpt-5-nano`。一部モデルは `temperature` 非対応のため自動で付与を抑制します。
- `NEWS_RSS`: 取得対象のRSSフィードURL（必須）
- `SLACK_BOT_TOKEN`: Slack ボットトークン（任意）
- `SLACK_CHANNEL`: 投稿先チャンネル。未指定時は `#general`

## ログ
- すべてのログはリポジトリ直下の `agent.log` に出力されます。

ログは`logs/`ディレクトリに保存されます。 
