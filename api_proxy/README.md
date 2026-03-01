# ComfyUI Secure API Proxy

ComfyUI を安全な公開APIとして提供するための FastAPI ベースのリバースプロキシ。
Cloudflare Tunnel 経由で HTTPS アクセスを実現し、認証・レート制限・入力検証を行う。

## アーキテクチャ

```
Internet → Cloudflare Tunnel (HTTPS) → cloudflared
    → 127.0.0.1:8189 (FastAPI Proxy: 認証・レート制限・バリデーション)
    → 127.0.0.1:8188 (ComfyUI: localhost限定)
```

## セットアップ

### 1. 依存関係のインストール

```bat
install-proxy.bat
```

または手動で:

```bash
pip install fastapi "uvicorn[standard]" httpx websockets pydantic-settings
winget install --id Cloudflare.cloudflared
```

### 2. 起動

```bat
start-api.bat
```

ComfyUI が `127.0.0.1:8188` で起動済みであることを確認してから実行する。
初回起動時に `api_proxy/.env` が自動生成され、ランダムな API キーが設定される。

## API エンドポイント

| Method | Path | Auth | Description |
|--------|------|:----:|-------------|
| `GET` | `/health` | - | ヘルスチェック |
| `POST` | `/generate` | Bearer | 画像生成 |
| `GET` | `/status` | Bearer | キュー状況・システム情報 |
| `GET` | `/result/{prompt_id}` | Bearer | 生成結果取得 |
| `GET` | `/image/{filename}` | Bearer | 画像ダウンロード |
| `POST` | `/cancel/{prompt_id}` | Bearer | 生成キャンセル |
| `WS` | `/ws?token=KEY` | Query | リアルタイム進捗 |

## 使い方

### ヘルスチェック

```bash
curl http://127.0.0.1:8189/health
```

### テキストプロンプトで画像生成（シンプルモード）

Flux Dev GGUF ワークフローが自動的に構築される。

```bash
curl -X POST http://127.0.0.1:8189/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "a cat sitting on a windowsill, golden hour lighting",
    "width": 1024,
    "height": 1024,
    "steps": 20,
    "cfg": 1.0
  }'
```

レスポンス:

```json
{"prompt_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"}
```

### 結果の取得

```bash
# ステータス確認（running → completed になるまでポーリング）
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://127.0.0.1:8189/result/{prompt_id}

# 画像ダウンロード（outputs 内の filename を指定）
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://127.0.0.1:8189/image/api_output_00001_.png -o output.png
```

### フルワークフローモード

`prompt` に ComfyUI ワークフロー JSON を直接渡すことも可能。

```bash
curl -X POST http://127.0.0.1:8189/generate \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": {
      "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux1-dev-Q4_K_S.gguf"}},
      "...": "..."
    }
  }'
```

### WebSocket で進捗監視

```python
import websockets, asyncio, json

async def monitor(api_key, prompt_id):
    async with websockets.connect(f"ws://127.0.0.1:8189/ws?token={api_key}") as ws:
        async for msg in ws:
            data = json.loads(msg)
            if data["type"] == "executing" and data["data"]["prompt_id"] == prompt_id:
                if data["data"]["node"] is None:
                    print("Complete!")
                    break
                print(f"Executing node: {data['data']['node']}")

asyncio.run(monitor("YOUR_API_KEY", "prompt-id-here"))
```

### キュー状況

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" http://127.0.0.1:8189/status
```

### 生成キャンセル

```bash
curl -X POST -H "Authorization: Bearer YOUR_API_KEY" \
  http://127.0.0.1:8189/cancel/{prompt_id}
```

## 設定

`api_proxy/.env` で変更可能（`.env.example` 参照）:

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `API_KEY` | 自動生成 | Bearer トークン（64文字） |
| `COMFYUI_HOST` | `127.0.0.1` | ComfyUI ホスト |
| `COMFYUI_PORT` | `8188` | ComfyUI ポート |
| `PROXY_HOST` | `127.0.0.1` | プロキシ リッスンアドレス |
| `PROXY_PORT` | `8189` | プロキシ ポート |
| `RATE_LIMIT_PER_MINUTE` | `10` | 1分あたりのリクエスト上限 |
| `RATE_LIMIT_BURST` | `3` | バースト許容数 |
| `MAX_WORKFLOW_SIZE` | `524288` | ワークフロー最大サイズ (bytes) |
| `MAX_NODE_COUNT` | `200` | ワークフロー最大ノード数 |

## セキュリティ

- **ネットワーク分離**: ComfyUI・Proxy 共に localhost のみリッスン
- **認証**: `hmac.compare_digest` によるタイミング攻撃耐性のある Bearer トークン検証
- **レート制限**: IP ごとの Token Bucket アルゴリズム（`CF-Connecting-IP` 対応）
- **入力検証**: ワークフローサイズ制限、危険ノードブロック、パストラバーサル防止
- **API 最小化**: ComfyUI の内部エンドポイント (`/upload`, `/models`, `/internal` 等) は一切公開しない
- **Swagger/OpenAPI 無効化**: 本番環境でのエンドポイント探索を防止
- **TLS**: Cloudflare Tunnel による自動 HTTPS 終端

### ブロックされるノード

`LoadImage`, `LoadImageMask`, `UploadImage`, `LoadImageFromUrl`, `PythonModule`, `ExecuteScript`, `RunCommand`, `Shell`

## ファイル構成

```
api_proxy/
├── __init__.py
├── main.py             # FastAPI アプリ・エンドポイント定義
├── config.py           # 設定管理・.env 読み込み・API key 自動生成
├── auth.py             # Bearer トークン認証
├── rate_limiter.py     # Token Bucket レート制限
├── proxy.py            # httpx による ComfyUI へのリクエスト転送
├── models.py           # Pydantic リクエスト/レスポンスモデル
├── validators.py       # ワークフロー検証・危険ノードブロック
├── ws_proxy.py         # WebSocket 双方向プロキシ
├── workflows/
│   ├── __init__.py
│   └── flux_dev.py     # Flux Dev GGUF ワークフローテンプレート
├── .env                # API_KEY (自動生成・gitignore推奨)
└── .env.example        # 設定テンプレート
```
