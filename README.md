# ai-cook

做菜智能体 — React Admin + Python FastAPI，用于管理中国菜品、生成即梦视频提示词、调用火山方舟生成美食短视频。

## 功能

- 千问生成 50 道全国火爆菜品入库
- 每道菜可生成多版本提示词（含反向提示词）
- 千问同时生成「发布的文案」（标题+步骤合一）
- 基于提示词调用火山即梦 API 生成视频
- 视频上传阿里云 OSS，提示词、视频均可删除

## 启动

### 一键启动（推荐）

```bash
cp .env.example .env   # 填入 API Key 等配置
./start.sh
```

- 后端 API：http://127.0.0.1:8000
- Admin UI：http://localhost:5173
- 按 `Ctrl+C` 同时停止前后端

### 分别启动

#### 1. 配置 `.env`

参考 `.env.example` 填写千问、MySQL、火山方舟、OSS 配置。

#### 2. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 http://localhost:5173

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/dishes/seed | 千问生成 50 道菜 |
| GET | /api/dishes | 菜品列表（按最近操作排序） |
| GET | /api/dishes/{id} | 菜品详情 |
| POST | /api/dishes/{id}/prompts | 生成新版提示词 |
| DELETE | /api/prompts/{id} | 删除提示词及关联视频 |
| POST | /api/dishes/prompts/{id}/videos | 生成视频 |
| GET | /api/videos/{id} | 查询视频状态 |
| DELETE | /api/videos/{id} | 删除视频 |
