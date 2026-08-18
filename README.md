# 工会知识库 + DUIX 数字人问答系统

## 项目结构

```
duix-knowledge-base/
├── app.py                  # Flask API 服务（知识库检索 + CORS）
├── index.html              # 前端页面（DUIX 数字人 + 知识库问答）
├── requirements.txt        # Python 依赖
├── Procfile                # Render/Railway 部署配置
├── knowledge_base/
│   └── knowledge_base.json # 知识库数据（154 条）
└── README.md               # 本文件
```

## 快速开始

### 1. 本地运行 API

```bash
pip install -r requirements.txt
python app.py
```

API 启动后访问：`http://localhost:5000/api/health`

测试问答：
```bash
curl "http://localhost:5000/api/ask?question=职工生日慰问标准是多少"
```

### 2. 本地测试前端

直接用浏览器打开 `index.html`，确保 API 已在本地运行。

### 3. 部署 API 到云端

推荐使用 **Render**（免费）：

#### 方式 A：Render 部署（推荐）

1. 将本项目上传到 GitHub
2. 访问 https://render.com → 注册/登录
3. 点击 "New +" → "Web Service"
4. 选择你的 GitHub 仓库
5. 配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
6. 点击 "Create Web Service"
7. 等待部署完成，获取 API 地址（如 `https://your-app.onrender.com`）

#### 方式 B：Railway 部署

1. 访问 https://railway.app
2. 新建项目 → 从 GitHub 导入
3. 自动识别 Python，开始部署
4. 获取 API 地址

### 4. 配置前端

部署完成后：

1. 修改 `index.html` 中的 `KB_API_URL` 为你的 API 地址：
   ```javascript
   let KB_API_URL = 'https://your-app.onrender.com';
   ```

2. 确认 DUIX 配置已填入：
   ```javascript
   const DUIX_CONFIG = {
       appId: '1539357019641876480',
       appKey: '7bf9f999-d214-441d-91dd-3833d0bb24be'
   };
   ```

3. 将 `index.html` 部署到任意静态托管（GitHub Pages、Vercel、Netlify）或直接在本地打开

### 5. 部署前端（可选）

#### GitHub Pages
1. 将代码推送到 GitHub
2. Settings → Pages → Source 选择 main 分支
3. 获取访问地址

#### Vercel
1. 访问 https://vercel.com
2. Import 你的 GitHub 仓库
3. 直接部署（纯静态 HTML）

## API 接口说明

### POST /api/ask
```json
// 请求
{ "question": "职工生日慰问标准是多少" }

// 响应
{
    "success": true,
    "answer": "具体答案内容...",
    "source": "西安公司工会职业生涯全过程福利手册",
    "source_file": "工会福利梳理 - 副本.docx",
    "chapter": "六、职工生日",
    "confidence": 78.5,
    "related": [...]
}
```

### GET /api/health
返回知识库状态信息。

### GET /api/sources
返回知识库来源文件列表。

## 知识库覆盖范围

- **工会福利梳理**：福利标准速查表（11 条）
- **职业生涯全过程关爱服务实施意见**：十大关爱服务（26 条）
- **三不让帮扶救助实施办法**：困难补助/助学/医疗救助（43 条）
- **工会财务管理办法**：预算/经费/资产/监督（74 条）

共 **154 条**知识条目，每条标注来源文件。

## 注意事项

1. API 必须支持 CORS（代码已配置）
2. 前端页面需要 HTTPS（DUIX SDK 要求）
3. 知识库答案严格基于文件内容，不会编造
4. 找不到答案时会明确提示"未找到相关信息"
