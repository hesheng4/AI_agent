# 研究Agent平台 - 详细使用指南

## 第一步：启动服务

```bash
cd D:\AI_agent
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

看到以下输出表示启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

---

## 第二步：访问API文档

浏览器打开：**http://localhost:8000/docs**

可以看到 Swagger UI 交互式文档，所有API都可以在这里测试。

---

## 第三步：注册用户

1. 展开 `POST /api/v1/auth/register`
2. 点击 **"Try it out"**
3. 输入：

```json
{
  "email": "test@example.com",
  "username": "testuser",
  "password": "testpass123"
}
```

4. 点击 **"Execute"**
5. 返回 200 表示注册成功

---

## 第四步：登录获取Token

1. 展开 `POST /api/v1/auth/login`
2. 点击 **"Try it out"**
3. 输入：

```json
{
  "email": "test@example.com",
  "password": "testpass123"
}
```

4. 点击 **"Execute"**
5. 复制返回的 `access_token`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## 第五步：使用Token调用接口

1. 点击页面右上角 **"Authorize"** 按钮（🔒图标）
2. 在弹窗中输入：`Bearer eyJhbGciOiJIUzI1NiIs...`（你的token）
3. 点击 **"Authorize"**
4. 点击 **"Close"**

现在所有API都可以调用了。

---

## 第六步：测试各功能

### 6.1 文献搜索

**接口：** `POST /api/v1/literature/search`

**请求体：**
```json
{
  "query": "机器学习 医学影像",
  "filters": {}
}
```

**返回示例：**
```json
{
  "status": "success",
  "papers": [
    {
      "id": "2301.12345",
      "title": "Deep Learning for Medical Image Analysis",
      "authors": ["Author A", "Author B"],
      "abstract": "...",
      "year": 2024,
      "journal": "arXiv",
      "citation_count": 0,
      "url": "http://arxiv.org/abs/2301.12345",
      "source": "arxiv"
    }
  ],
  "suggestions": "...",
  "total_results": 10
}
```

---

### 6.2 数据分析

**接口：** `POST /api/v1/data/analyze`

#### 描述性统计
```json
{
  "data": [
    {"age": 25, "salary": 5000, "score": 85},
    {"age": 30, "salary": 7000, "score": 90},
    {"age": 35, "salary": 9000, "score": 78},
    {"age": 40, "salary": 11000, "score": 92},
    {"age": 45, "salary": 13000, "score": 88}
  ],
  "analysis_type": "descriptive"
}
```

#### 相关性分析
```json
{
  "data": [...],
  "analysis_type": "correlation"
}
```

#### 异常值检测
```json
{
  "data": [...],
  "analysis_type": "outlier"
}
```

#### 分组比较
```json
{
  "data": [
    {"group": "A", "value": 10},
    {"group": "A", "value": 12},
    {"group": "B", "value": 20},
    {"group": "B", "value": 22}
  ],
  "analysis_type": "group",
  "group_col": "group",
  "value_col": "value"
}
```

---

### 6.3 论文大纲

**接口：** `POST /api/v1/writing/outline`

**请求体：**
```json
{
  "topic": "深度学习在医疗影像诊断中的应用研究"
}
```

**返回示例：**
```json
{
  "status": "success",
  "outline": {
    "title": "深度学习在医疗影像诊断中的应用研究",
    "sections": [
      {
        "title": "引言",
        "subsections": ["研究背景", "研究目的", "研究意义", "论文结构"]
      },
      {
        "title": "文献综述",
        "subsections": ["国内外研究现状", "研究理论基础", "文献评述"]
      },
      ...
    ],
    "estimated_pages": 18,
    "word_count_range": "4800-9000"
  }
}
```

---

### 6.4 实验设计

**接口：** `POST /api/v1/experiment/design`

**请求体：**
```json
{
  "research_goal": "测试新药对高血压的疗效",
  "variables": ["药物剂量", "治疗周期", "血压变化"],
  "design_type": "between"
}
```

**返回示例：**
```json
{
  "status": "success",
  "plan": {
    "goal": "测试新药对高血压的疗效",
    "design_type": "between",
    "design_description": "被试间设计 - 不同组接受不同处理",
    "variables": {
      "independent": ["药物剂量"],
      "dependent": ["治疗周期"],
      "control": ["血压变化"]
    },
    "groups": [
      {"name": "控制组", "description": "不接受处理"},
      {"name": "实验组", "description": "接受处理"}
    ],
    "steps": [
      "1. 明确研究假设",
      "2. 确定变量和测量指标",
      ...
    ],
    "sample_size_recommendation": {
      "min": 30,
      "recommended": 50,
      "per_group": 25
    }
  }
}
```

---

### 6.5 查看配额

**接口：** `GET /api/v1/billing/check-quota`

**返回示例：**
```json
{
  "allowed": true,
  "plan": "免费版"
}
```

---

## 使用前端界面

除了API文档，还可以使用前端界面：

1. 浏览器打开：**http://localhost:8000**
2. 注册/登录账号
3. 使用可视化界面：
   - 📚 **文献检索**：输入关键词搜索文献
   - 📊 **数据分析**：上传CSV数据进行分析
   - ✍️ **论文写作**：生成大纲、语法检查
   - 🧪 **实验设计**：设计实验方案

---

## 常见问题

### Q1: 注册返回 400
**原因：** 邮箱已注册
**解决：** 使用其他邮箱或直接登录

### Q2: 登录返回 401
**原因：** 密码错误
**解决：** 检查密码或重新注册

### Q3: 搜索文献返回空
**原因：** 外部API限流
**解决：** 等待几秒后重试

### Q4: 数据分析返回 500
**原因：** 数据格式错误
**解决：** 确保数据是数组格式，每行是对象

---

## cURL 命令行测试

```bash
# 注册
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","username":"testuser","password":"testpass123"}'

# 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# 保存token
TOKEN="eyJhbGciOiJIUzI1NiIs..."

# 搜索文献
curl -X POST http://localhost:8000/api/v1/literature/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query":"机器学习"}'

# 数据分析
curl -X POST http://localhost:8000/api/v1/data/analyze \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"data":[{"x":1,"y":2},{"x":3,"y":4}],"analysis_type":"descriptive"}'
```

---

## Python 测试脚本

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# 1. 注册
resp = requests.post(f"{BASE_URL}/auth/register", json={
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpass123"
})
print(f"注册: {resp.status_code}")

# 2. 登录
resp = requests.post(f"{BASE_URL}/auth/login", json={
    "email": "test@example.com",
    "password": "testpass123"
})
token = resp.json()["access_token"]
print(f"登录成功，token: {token[:20]}...")

# 3. 设置token
headers = {"Authorization": f"Bearer {token}"}

# 4. 搜索文献
resp = requests.post(f"{BASE_URL}/literature/search",
    headers=headers,
    json={"query": "机器学习"}
)
print(f"文献搜索: {resp.status_code}, 结果: {len(resp.json().get('papers', []))} 篇")

# 5. 数据分析
resp = requests.post(f"{BASE_URL}/data/analyze",
    headers=headers,
    json={
        "data": [{"x": 1, "y": 2}, {"x": 3, "y": 4}],
        "analysis_type": "descriptive"
    }
)
print(f"数据分析: {resp.status_code}")

# 6. 生成大纲
resp = requests.post(f"{BASE_URL}/writing/outline",
    headers=headers,
    json={"topic": "深度学习研究"}
)
print(f"大纲生成: {resp.status_code}")

# 7. 实验设计
resp = requests.post(f"{BASE_URL}/experiment/design",
    headers=headers,
    json={
        "research_goal": "测试新药疗效",
        "variables": ["剂量", "疗程"]
    }
)
print(f"实验设计: {resp.status_code}")
```
