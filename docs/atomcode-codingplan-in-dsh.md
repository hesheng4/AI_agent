# 在 DeepSeek Harness 中使用 AtomCode CodingPlan

## 背景：为什么不能直接加 API Key

AtomCode 的 CodingPlan 网关（`https://llm-api.atomgit.com/v1`）**不认普通 API Key**。
它要求每个请求都带 atomcode 官方二进制的**签名**（时间戳 + nonce + HMAC，HKDF 派生密钥，
带防重放和时间窗校验，见二进制中的 `atomcode-codingplan-crypto` 模块）。
因此 `auth.toml` 里的 access_token / refresh_token 直接当 Bearer 调用会得到：

```json
{"error":{"message":"Authentication Error, Gitcode auth: token rejected (status=401)", ...}}
```

正确姿势：让 **atomcode 自己的 daemon** 做签名请求，Harness 通过一个本地
OpenAI 兼容桥接层使用 CodingPlan 模型。

```
DeepSeek Harness (llm-pi-ai)
        │  OpenAI 兼容 /v1/chat/completions
        ▼
codingplan-bridge.py (127.0.0.1:13458)   ← 本仓库 scripts/
        │  自定义 /chat SSE（Bearer token）
        ▼
atomcode daemon (127.0.0.1:13456)        ← 由本机 atomcode 启动
        │  签名请求（HMAC + 时间戳）
        ▼
llm-api.atomgit.com/v1  (CodingPlan 免费额度)
```

## 架构

| 组件 | 端口 | 说明 |
|---|---|---|
| `atomcode daemon` | 13456 | atomcode 的 IDE 集成 HTTP 服务，内部完成 CodingPlan 签名鉴权 |
| `codingplan-bridge.py` | 13458 | 把 daemon 的 `/chat` SSE 翻译成 OpenAI `chat.completions` |
| DSH provider `atomgit-codingplan` | — | 注册在 `~/.dsh/settings.yaml` 的 `llm-pi-ai.providers` |

可用模型（CodingPlan 免费额度，选择器显示名）：
- `deepseek-v4-flash`（显示名 `CodingPlan V4 Flash`，1M 上下文）
- `Qwen/Qwen3-VL-8B-Instruct`（显示名 `CodingPlan Qwen3-VL`，128K，支持视觉）

## 一、启动（需要在普通终端里跑，不要在 Harness 沙箱内跑）

```bat
scripts\codingplan-start.bat
```

脚本会开两个窗口：atomcode daemon + 桥接层。停止用 `scripts\codingplan-stop.bat`。

### 开机自启（已配置，自愈式）

登录 Windows 时自动运行 `scripts\codingplan-watchdog.py`（窗口隐藏、常驻）：

- 启动文件夹已放入 `codingplan-autostart.cmd`，用 pythonw 无窗口启动 watchdog
- watchdog 每 20 秒自检 daemon(13456) 和 bridge(13458)，**挂了或卡死就自动重启**
- 默认模型已设为 `atomgit-codingplan / deepseek-v4-flash`（新会话自动使用；现有会话保持原选择）
- 日志：`logs\codingplan-watchdog.log`

验证：重新登录后执行
`(Invoke-WebRequest http://127.0.0.1:13458/health -UseBasicParsing).Content` 应返回 ok。
手动启停仍可用 `codingplan-start.bat` / `codingplan-stop.bat`。

验证自启是否生效：重新登录后执行
`(Invoke-WebRequest http://127.0.0.1:13458/health -UseBasicParsing).Content` 应返回 ok。

也可以手动：

```bat
set ATOMCODE_DAEMON_TOKEN=dsh-codingplan-2026-08
atomcode daemon --port 13456 --no-telemetry        REM 窗口1
set ATOMCODE_WORKING_DIR=D:\AI_agent
python scripts\codingplan-bridge.py                 REM 窗口2
```

> 注意：daemon 需要写 `~/.atomcode/sessions` 等文件，Harness 的文件沙箱会拦截
> （workspace-write 只允许写工作区），所以务必在 Harness 之外的终端启动。
> 若在 Harness 内用 pwsh 启动，需以完整文件权限运行。

## 二、在 Harness 中选择模型

配置已经写入（`llm-pi-ai.providers.atomgit-codingplan`，settings.yaml 热加载，无需重启）：

```yaml
llm-pi-ai:
  providers:
    atomgit-codingplan:
      displayName: CodingPlan (bridge)
      apiKeyEnv: ATOMCODE_BRIDGE_KEY
      api: openai-completions
      baseURL: http://127.0.0.1:13458/v1
      models:
        - id: deepseek-v4-flash
          name: CodingPlan V4 Flash
          contextWindow: 1000000
          reasoningEfforts:
            off:
            low: low
            medium: medium
            high: high
            max: max
        - id: Qwen/Qwen3-VL-8B-Instruct
          name: CodingPlan Qwen3-VL
          contextWindow: 128000
```

凭据（`~/.dsh/.credentials.yaml`，占位即可，桥接层校验的是 daemon token）：

```yaml
ATOMCODE_BRIDGE_KEY: dsh-bridge-key
```

在 Harness 界面的**模型选择器**里选 provider **CodingPlan (bridge)**，
模型选 `deepseek-v4-flash`（显示名 CodingPlan V4 Flash）即可。

> 注：`Qwen3-VL` 虽支持视觉，但桥接层只透传文本（图片会被降级为占位符），
> 且 provider 未声明 image 输入，Harness 会在发图前拒绝——所以视觉能力当前不可用。

## 三、原理与限制

- 桥接层把每次请求的完整消息历史压成一个 prompt，作为一条消息发给 daemon 的新会话
  （每次请求自包含，无跨请求会话复用）。
- 桥接层做**真实流式**：daemon 的 SSE `text` 事件逐 token 转发给 Harness，
  首 token ≈ 4.7–6.3s（daemon 的真实首 token 时间），不再整轮缓冲。
- 桥接层会**压缩 Harness 的 system/developer 消息**（截断到 ~2K 字符，剥掉
  `<available_skills>`/`<system-reminder>` 目录）——这些是 DSH 自己的工具/技能目录，
  对 daemon 无用，转发只会浪费 token 并拖慢速度。实测总 prompt 可降 ~40%。
- CodingPlan 有免费额度/限流窗口，用量可在 atomcode 里看 `/codingplan`（用量页）。
- 桥接层仅监听 127.0.0.1，不暴露局域网。

### 安全模型（重要）

daemon 本质就是 atomcode——一个拥有你**完整机器权限**的 agent。桥接层默认以
`approval_mode = "bypass"` 运行，让它能真正改文件、执行编码任务（等价于你自己
在机器上跑 atomcode；Harness 的文件沙箱对它不生效）。

- **注意**：daemon 修改文件是它自己在 `ATOMCODE_WORKING_DIR` 下做的，Harness 自己的
  diff/文件视图不会追踪这些改动。
- 需要只读时可设 `ATOMCODE_APPROVAL_MODE=plan`（阻止写入，但也会让模型拒绝输出代码、
  变成"计划"式回答——这正是之前"一直显示计划模式无法修改"的原因，现已改回 bypass）。

### 推理等级（Reasoning Effort）

切换模型后点开"推理等级"可选：**Default / Off / Low / Medium / High / Max**
（来自 `settings.yaml` 中 `reasoningEfforts` 声明，daemon 已验证接受全部等级）。

- `Off`：不传 effort，模型用提供方默认（无思考）
- `Low`：不触发思考，响应快
- `Medium / High / Max`：触发思考（流式 `reasoning` 事件），更慢但更深入

注意：思考会显著拉长首 token 时间（见下）。日常快速问答建议用 Default/Off/Low。

### 速度与稳定性

- **首 token ≈ 4.7–6.3s（真实流式）**：实测最小请求（"hi"）也要 **~1.8 万 token 输入**——
  这是 daemon 自带的 atomcode agent 系统提示词（工具定义 + skills 目录 + 行为规则）的固定成本，
  与问题长短无关。真实 Harness 调用还会叠加 Harness 自己的系统提示词，prompt 更大、更慢。
- **速度的根本限制**：CodingPlan 网关要求 atomcode 签名，只能经 daemon 代理，而 daemon 必然
  带着 agent 提示词。这是架构下限，无法用代码绕过。
  **要快 → 用官方 DeepSeek**（`deepseek-official`，无 agent 包裹，亚秒级首 token）；
  **要免费额度 → 用 CodingPlan**（约 6s 首 token）。二者按需切换。
- **daemon 空闲 30 分钟会自动退出**（默认 idle-timeout），之后调用会连接被拒。
  `codingplan-start.bat` 和 watchdog 均已加 `--idle-timeout 0` 禁用自动退出。
- **watchdog 自愈**：每 20 秒自检 daemon+bridge，挂了或卡死自动重启（`logs\codingplan-watchdog.log`）。
- **桥接层对客户端断连免疫**：流式写入已做容错，单个异常请求不会拖垮服务。

### 常见故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 切换模型后发消息报连接被拒 | bridge 或 daemon 没在运行 | `codingplan-start.bat` 重启；`http://127.0.0.1:13458/health` 应为 ok |
| daemon 退出导致失败 | 空闲 30 分钟自动退出 | 已加 `--idle-timeout 0`；或手动加该参数 |
| 推理等级无法选择 | 旧配置未声明 `reasoningEfforts` | 已声明 off/low/medium/high/max；重新打开选择器 |
| 模型名覆盖推理等级行 | 模型名过长溢出 250px 菜单 | 已缩短为 `CodingPlan V4 Flash` / `CodingPlan Qwen3-VL` |

## 四、备选方案

如果不需要"模型进 Harness 选择器"，还有两种更简单的用法：

1. **daemon 自带 Web UI**：`atomcode daemon` 后浏览器打开 `http://127.0.0.1:13456`，
   就是一个浏览器版 CodingPlan 编程助手（和 Harness 并行用）。
2. **Harness 直接调 atomcode CLI**：在 Harness 的终端工具里执行
   `atomcode -C D:\AI_agent -p "plan: ..." -y --no-telemetry`（headless），
   由 atomcode 消耗 CodingPlan 额度完成编码任务，结果回到对话里。
   同样需要完整文件权限（沙箱会拦截 `~/.atomcode` 写入）。
