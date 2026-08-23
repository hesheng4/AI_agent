# 前端代码审查报告

> 审查时间：2026-06-19  
> 审查范围：frontend/src/api.ts、frontend/src/auth.tsx、Dockerfile、frontend/src/sections/

---

## 一、安全问题

### P1 - 安全中风险

#### 1. `api.ts:19` — Token 存储于 `localStorage`，存在 XSS 风险

**文件**：`D:\AI_agent\frontend\src\api.ts`  
**行号**：第19行  
**问题**：
```typescript
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
```
`localStorage` 可被任意 JavaScript 读取，若存在 XSS 漏洞，攻击者可以窃取 JWT Token。相比 `httpOnly` Cookie，`localStorage` 的安全性较低。

**修复建议**：
- **方案A（推荐）**：改用 `httpOnly` + `Secure` Cookie，Token 由后端设置，前端不存储。
- **方案B（妥协）**：若必须前后端分离，使用 `sessionStorage` 代替 `localStorage`，页面关闭后自动清除，降低持久化风险。

---

#### 2. `api.ts:54-56` — 401 时自动清除 Token 并跳转

**文件**：`D:\AI_agent\frontend\src\api.ts`  
**行号**：第54-56行  
**问题**：
```typescript
if (res.status === 401) {
    clearToken();
    throw new ApiError(401, '未授权，请重新登录');
}
```
前端自行处理 401 并清除 Token，但若后端已设置 `httpOnly` Cookie，前端不应操作 Token。当前逻辑假设 Token 在前端存储，与最佳实践不符。

**修复建议**：配合后端改为 Cookie 认证后，删除前端的 Token 管理逻辑。

---

## 二、代码质量问题

### P1 - 建议修复

#### 3. `api.ts` — 单文件 406 行，应按域拆分

**文件**：`D:\AI_agent\frontend\src\api.ts`  
**行号**：全文（406行）  
**问题**：所有 API 函数集中在一个文件中，随着功能增加会难以维护。

**拆分方案**：
```
frontend/src/api/
├── index.ts          // 导出统一 request() 和 ApiError
├── auth.ts           // authApi
├── literature.ts     // literatureApi
├── library.ts        // libraryApi
├── data.ts           // dataApi
├── writing.ts        // writingApi
├── experiment.ts     // experimentApi
├── billing.ts        // billingApi
├── ascend.ts         // ascendApi
├── alignment.ts      // alignmentApi
├── profiling.ts      // profilingApi
├── perfTuning.ts     // perfTuningApi
├── toolchain.ts      // toolchainApi
├── validator.ts      // validatorApi
├── debugging.ts      // debuggingApi
├── historyToSkill.ts // historyToSkillApi
└── adaptation.ts     // adaptationApi
```

**迁移步骤**：
1. 创建 `frontend/src/api/` 目录
2. 将 `request()` 和 `ApiError` 保留在 `index.ts`
3. 按域拆分各 API 对象到独立文件
4. 更新各页面组件的导入路径

---

### P2 - 可选优化

#### 4. `sections/Adaptation.tsx` 和 `PerfTuning.tsx` — 大文件拆分

**问题**：`Adaptation.tsx` 和 `PerfTuning.tsx` 约 30KB+，可能包含多个职责。

**建议**：按功能拆分子组件，如 `Adaptation.tsx` 可拆分为：
- `AdaptationWizard.tsx` — 向导容器
- `Step1SelectModel.tsx` — 步骤1
- `Step2ConfigDataset.tsx` — 步骤2
- ...

---

## 三、Dockerfile 问题

### P0 - 必须修复

#### 5. `Dockerfile` — 缺少前端构建阶段

**文件**：`D:\AI_agent\Dockerfile`  
**问题**：
- 第33行 `COPY frontend/ ./frontend/` 直接复制前端源码，但未执行 `npm run build`
- FastAPI 的 `StaticFiles` 指向 `frontend/dist/`，但 `dist/` 目录不存在（未构建）
- 当前配置下，前端页面无法正常工作

**修复建议**（多阶段构建）：
```dockerfile
# 阶段1：构建前端
FROM node:20-alpine as frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --only=production
COPY frontend/ ./
RUN npm run build

# 阶段2：构建后端（原有 builder 阶段）
FROM python:3.11-slim as builder
# ... 原有内容 ...

# 阶段3：生产镜像
FROM python:3.11-slim
# ... 原有内容 ...

# 从前端构建阶段复制 dist/
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
```

---

## 四、遗留文件检查

### P2 - 可选清理

#### 6. `frontend/public/` 可能存在遗留文件

**建议检查**：
- `frontend/public/app.js` — 是否为旧版入口
- `frontend/public/index_legacy.html` — 是否为旧版 HTML
- `frontend/public/css/` — 是否为未使用的 CSS
- `frontend/public/pages/` — 是否为未使用的页面

**操作**：确认这些文件是否仍在服务，若否，从版本控制中删除。

---

## 五、总结

| 严重程度 | 数量 | 需立即修复 |
|---------|------|-----------|
| P0 | 1 | 是（Dockerfile 前端构建） |
| P1 | 3 | 建议 |
| P2 | 2 | 可选 |

**优先修复顺序**：
1. **Dockerfile** — 添加前端构建多阶段构建（P0）
2. **`api.ts` Token 存储** — 迁移到 `httpOnly` Cookie（P1）
3. **`api.ts` 拆分** — 按域拆分为多个文件（P1）
4. **大组件拆分** — `Adaptation.tsx`、`PerfTuning.tsx`（P2）
5. **清理遗留文件**（P2）
