# news-summary-agent
ニュースRSSを取得し、LLMで要約してSlackに配信する自動化エージェント

- **取得**: RSSフィード（`feedparser`）
- **解析**: HTML本文抽出（`BeautifulSoup`）
- **要約**: OpenAI API（構造化JSON出力）
- **配信**: Slack（`slack-sdk`）
- **信頼性**: ネットワークは指数バックオフ付きリトライ（`tenacity`）
- **ログ**: リポジトリ直下の `agent.log` に保存（`loguru`、ローテーション/保持あり）

## 仕組みと構成
- `agent/io_sources.py`: RSS取得（`fetch_rss_feed`/`fetch_all_rss`）、記事HTMLからテキスト抽出（`fetch_article_text`）。いずれもリトライ適用。
- `agent/llm.py`: ニュース見出し+URLをLLMに渡し、JSONスキーマで要約を取得（集約/記事単位）。一部モデルでは `temperature` を自動オフ。`gpt-5-nano` 失敗時は `gpt-4o-mini` にフォールバック。
- `agent/processors.py`: 集約要約（ハイライト/リスク/機会）のテキスト整形（`run_summary`）。
- `agent/curator.py`: 記事単位の3点要約（タイトル/URL/箇条書き）と整形（`run_curated`）。
- `agent/notifiers.py`: Slack へ投稿（`post_to_slack`）。
- `agent/config.py`: `.env` の読み込みと環境変数の集約。
- `run_once.py`: ワンショット実行（標準出力＋Slack投稿の呼び出し）。

## 必要要件
- Python 3.9 以上を推奨
- OpenAI API キー（`OPENAI_API_KEY`）
- Slack Bot Token（`SLACK_BOT_TOKEN`。Slack 投稿を使う場合）
- RSS フィードURL（`NEWS_RSS` または `NEWS_FEEDS`）

## セットアップ
1) 仮想環境の作成と有効化
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
```

2) 依存関係のインストール
```bash
pip install -r requirements.txt
```

3) 環境変数の設定（`.env` を利用）
`.env` を作成し、以下を参考に設定してください。
```bash
OPENAI_API_KEY=sk-...                               # OpenAIのAPIキー（必須）
MODEL=gpt-5-nano                                    # 既定モデル名（必要に応じて変更）

# RSSは単一 or 複数どちらでも設定可（複数指定時はNEWS_FEEDSが優先）
NEWS_RSS=https://example.com/rss                    # 単一RSS
NEWS_FEEDS=https://a.example.com/rss,https://b.example.com/feed  # 複数RSS（カンマ区切り）
NEWS_MAX_AGE_DAYS=7                                 # 直近N日でフィルタ（既定: 7）

# Slack（使う場合のみ）
SLACK_BOT_TOKEN=xoxb-...                            # Slack Bot Token（任意）
SLACK_CHANNEL=#general                              # 投稿先チャンネル（任意、既定は #general）

# スコアリング用の優先キーワード（任意、カンマ区切り、小文字化して部分一致）
PREF_PRIMARY=llm,ai,生成,OpenAI
PREF_SECONDARY=cloud,db,agent
```
`agent/config.py` が `python-dotenv` により `.env` を自動読み込みします。

## 使い方
### A) ワンショット実行（`run_once.py`）
```bash
python run_once.py
```
- 標準出力に要約を表示します。
- Slack を使う場合は `SLACK_BOT_TOKEN` を設定してください。未設定のまま `post_to_slack` を呼ぶとエラーになる場合があります。Slack不要の場合は `run_once.py` の `post_to_slack(text)` をコメントアウトしてください。

### B) 集約要約（ハイライト/リスク/機会）
```bash
python -c "from agent.processors import run_summary; print(run_summary(top_n=6))"
```
- RSSから上位N件を要約し、日付＋ハイライト等のブロックで表示します。

### C) 記事単位の箇条書き要約（カスタム整形）
```bash
python -c "from agent.curator import run_curated; print(run_curated(top_k=5, per_feed=10, use_snippet=False))"
```
- 複数RSSからスコアリング→重複排除→上位K件を選び、各記事の3点要約を整形して表示します。
- `use_snippet=True` にすると本文スニペットもLLMへ渡します（コスト増）。

## 環境変数一覧
- `OPENAI_API_KEY`（必須）: OpenAIのAPIキー
- `MODEL`（任意、既定: `gpt-5-nano`）: 使用モデル名。`gpt-5*`/`o1*`/`o3*` など一部は `temperature` を自動で付与しません。
- `NEWS_RSS`（任意）: 単一のRSSフィードURL
- `NEWS_FEEDS`（任意）: 複数RSSのカンマ区切り。設定されていればこちらを優先
- `NEWS_MAX_AGE_DAYS`（任意、既定: 7）: この日数以内の記事にフィルタ
- `SLACK_BOT_TOKEN`（任意）: Slack ボットトークン（投稿に必要）
- `SLACK_CHANNEL`（任意、既定: `#general`）: 投稿先チャンネル
- `PREF_PRIMARY`（任意）: 強キーワード（スコア+3）
- `PREF_SECONDARY`（任意）: 弱キーワード（スコア+1.5）

## RSS取得と本文抽出
- RSS/本文取得は指数バックオフ（最大3回）でリトライします。
- 本文抽出は `BeautifulSoup` + `lxml` を使用し、JS/CSS/`noscript` を除去してテキスト化します（最大8,000文字）。

## OpenAIモデルについて
- 出力は `response_format={"type": "json_object"}` でJSONを強制し、予期せぬラップ（`articles` 配列など）があれば自動で正規化します。
- `gpt-5-nano` で失敗した場合は `gpt-4o-mini` にフォールバックします。

## ログ
- すべてのログはリポジトリ直下の `agent.log` に出力されます。
- ローテーション: 1週間ごと、保持: 4週間（`agent/utils.py` 参照）。 
