# DUIX 工会知识库部署指南

## ⚠️ 重要安全提醒

**请立即修改你的 Render 密码！** 不要在对话中分享密码，这是非常重要的安全习惯。

## 部署流程概览

```
步骤1: 创建 GitHub 仓库 → 步骤2: 推送代码 → 步骤3: Render 部署 API → 步骤4: 部署前端
```

---

## 步骤 1: 创建 GitHub 仓库

1. 打开 https://github.com/new
2. 填写仓库信息：
   - **Repository name**: `duix-knowledge-base`
   - **Description**: `DUIX 数字人 + 工会知识库问答系统`
   - **Public**: ✅ 勾选（免费部署需要公开仓库）
3. 点击 **Create repository**

---

## 步骤 2: 推送代码到 GitHub

### 方法 A: 使用 GitHub Desktop（推荐新手）

1. 下载安装 GitHub Desktop: https://desktop.github.com/
2. 登录你的 GitHub 账号
3. 点击 **File → Add Local Repository**
4. 选择项目文件夹：`duix-knowledge-base`
5. 如果提示不是 git 仓库，选择 **create a repository**
6. 填写名称 `duix-knowledge-base`，点击 **Create Repository**
7. 在左侧看到文件变更，填写提交信息（如"初始提交"），点击 **Commit**
8. 点击 **Publish repository**，选择你的账号，点击 **Publish**

### 方法 B: 使用命令行

```bash
cd duix-knowledge-base
git init
git add .
git commit -m "初始提交"
git branch -M main
git remote add origin https://github.com/你的用户名/duix-knowledge-base.git
git push -u origin main
```

---

## 步骤 3: 在 Render 上部署 API

1. 打开 https://dashboard.render.com/
2. 登录你的账号（3023558117@qq.com）
3. 点击 **New +** → **Web Service**
4. 选择 **Build and deploy from a Git repository** → **Next**
5. 选择你的 GitHub 账号，找到 `duix-knowledge-base` 仓库 → **Connect**
6. 填写配置信息：
   - **Name**: `duix-kb-api`
   - **Region**: `Oregon (US West)` 或离你最近的区域
   - **Branch**: `main`
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: `Free`
7. 点击 **Create Web Service**
8. 等待部署完成（约 2-5 分钟）
9. 部署成功后，复制 API 地址，格式类似：`https://duix-kb-api.onrender.com`

---

## 步骤 4: 测试 API

部署完成后，访问以下地址测试：

- **健康检查**: `https://你的域名.onrender.com/api/health`
- **问答测试**: 
  ```
  POST https://你的域名.onrender.com/api/ask
  Content-Type: application/json
  
  {
    "question": "工会福利有哪些？"
  }
  ```

可以使用在线工具测试：https://hoppscotch.io/ 或 https://www.postman.com/

---

## 步骤 5: 配置前端 API 地址

1. 打开 `index.html` 文件
2. 找到第 120 行左右：
   ```javascript
   const KB_API_URL = 'http://localhost:5000/api/ask';
   ```
3. 修改为你的 Render API 地址：
   ```javascript
   const KB_API_URL = 'https://duix-kb-api.onrender.com/api/ask';
   ```

---

## 步骤 6: 部署前端页面

### 方案 A: 使用 Vercel（推荐，最简单）

1. 打开 https://vercel.com/
2. 使用 GitHub 登录
3. 点击 **Add New Project**
4. 选择 `duix-knowledge-base` 仓库
5. 点击 **Deploy**
6. 等待部署完成，获取访问地址（如 `https://duix-kb.vercel.app`）

### 方案 B: 使用 Netlify

1. 打开 https://www.netlify.com/
2. 使用 GitHub 登录
3. 拖拽 `index.html` 文件到 Netlify 页面
4. 或点击 **Add new site** → **Import an existing project** → 选择 GitHub 仓库
5. 部署完成后获取访问地址

### 方案 C: 使用 GitHub Pages

1. 在 GitHub 仓库页面，点击 **Settings**
2. 左侧选择 **Pages**
3. **Source** 选择 **Deploy from a branch**
4. **Branch** 选择 `main` / `root` → **Save**
5. 等待部署完成，访问地址：`https://你的用户名.github.io/duix-knowledge-base/`

**注意**：GitHub Pages 需要修改 `index.html` 中的 DUIX SDK 路径为相对路径

---

## 步骤 7: 完整测试

1. 打开前端页面（Vercel/Netlify/GitHub Pages 地址）
2. 点击 **启动数字人** 按钮
3. 等待数字人加载完成
4. 在输入框输入问题，如"工会福利有哪些？"
5. 观察数字人是否播报答案

---

## 常见问题

### Q1: Render 部署失败
- 检查 `requirements.txt` 是否包含所有依赖
- 查看 Render 的 **Logs** 页面查看错误信息
- 确保 Python 版本兼容（推荐 Python 3.9+）

### Q2: API 返回 CORS 错误
- 确保 `app.py` 中已启用 CORS
- 前端地址和 API 地址都必须是 HTTPS

### Q3: DUIX 数字人不显示
- 检查 appId 和 appKey 是否正确
- 查看浏览器控制台错误信息
- 确保页面通过 HTTPS 访问

### Q4: 知识库问答不准确
- 可以调整 `app.py` 中的匹配阈值（默认 0.3）
- 或优化 `knowledge_base.json` 中的关键词

---

## 技术支持

如有问题，可以：
1. 查看 Render 文档：https://render.com/docs
2. 查看 DUIX 文档：https://github.com/duix-team/duix-guiji
3. 在对话中继续向我咨询
