# A 股复盘后端

FastAPI 后端，用 AKShare 获取 A 股市场数据，用 DeepSeek `deepseek-v4-pro` 生成每日复盘，并支持股票操作记录和 Excel 导出。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```

PowerShell 如果拦截 npm/脚本不影响本项目；后端运行只需要 Python。

## 关键环境变量

- `DATABASE_URL`：本地默认 SQLite；Render 上来自 Postgres。
- `APP_TOKEN`：Android 端请求 `/api/*` 时放入 `X-App-Token`。
- `DEEPSEEK_API_KEY`：DeepSeek API key。
- `DEEPSEEK_MODEL`：默认 `deepseek-v4-pro`。

## 接口

- `GET /health`
- `POST /api/operations`
- `GET /api/operations?start_date=2026-05-01&end_date=2026-05-03`
- `POST /api/reviews/daily`
- `GET /api/reviews/{review_id}`
- `GET /api/reviews/{review_id}/excel`

所有 `/api/*` 请求默认带：

```http
X-App-Token: <APP_TOKEN>
```

## 示例

```bash
curl -X POST http://localhost:8000/api/operations \
  -H "Content-Type: application/json" \
  -H "X-App-Token: change-me" \
  -d '{"stock_code":"600519","stock_name":"贵州茅台","trade_date":"2026-05-03","action":"买入","buy_reason":"回踩企稳","price":1680,"quantity":100,"profit_loss":0}'
```

```bash
curl -X POST http://localhost:8000/api/reviews/daily \
  -H "Content-Type: application/json" \
  -H "X-App-Token: change-me" \
  -d '{"trade_date":"2026-05-03","refresh":true}'
```

## 测试

默认测试 mock AKShare 和 DeepSeek，不需要真实密钥：

```bash
pytest
```

真实 AKShare/DeepSeek 冒烟测试可后续单独添加 `RUN_LIVE_TESTS=1` 后运行。AKShare 免费源来自公开网页，可能延迟或字段变动，接口会在复盘 JSON 中记录数据质量警告。

## Render

项目包含 `render.yaml`。部署前需要先把当前目录初始化为 Git 仓库并推到 GitHub/GitLab/Bitbucket，然后在 Render Dashboard 创建 Blueprint，并填写：

- `APP_TOKEN`
- `DEEPSEEK_API_KEY`

## Android App

安卓前端位于 `android/`，是原生 Android Java 工程。首次构建前，在 `android/local.properties` 写入：

```properties
sdk.dir=C:/Users/24604/AppData/Local/Android/Sdk
API_BASE_URL=https://a-share-review-api.onrender.com
APP_TOKEN=<你的 APP_TOKEN>
```

构建调试 APK：

```powershell
cd android
.\gradlew.bat :app:assembleDebug
```

产物路径：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

App 功能：

- 获取目前股市信息，并调用后端后台生成复盘。
- 展示大盘判断、涨停/跌停家数、上涨/下跌家数、热点板块。
- 下载 Excel 到系统 Downloads，并在下载完成后尝试直接打开。
