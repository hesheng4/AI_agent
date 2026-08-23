# UI/UX Pro Max — 设计规范参考手册

> 综合设计指南：67 种风格 · 96 套配色 · 57 组字体 · 99 条 UX 准则 · 25 类图表 · 13 个技术栈

---

## 目录

1. [设计系统快速生成](#1-设计系统快速生成)
2. [配色方案库](#2-配色方案库)
3. [字体搭配库](#3-字体搭配库)
4. [UI 风格库](#4-ui-风格库)
5. [Landing Page 结构模式](#5-landing-page-结构模式)
6. [图表选型指南](#6-图表选型指南)
7. [UX 准则（按优先级）](#7-ux-准则按优先级)
8. [Tailwind 实践规范](#8-tailwind-实践规范)
9. [交付前检查清单](#9-交付前检查清单)
10. [常见易错规则](#10-常见易错规则)

---

## 1. 设计系统快速生成

使用 `--design-system` 一键生成完整设计系统：

```bash
python skills/ui-ux-pro-max/scripts/search.py "<产品类型> <行业> <风格关键词>" --design-system -p "项目名称" -f markdown
```

**示例输出：**

| 维度 | 推荐 |
|------|------|
| **Pattern** | Minimal Single Column — 单 CTA 聚焦、大字体、大量留白 |
| **Style** | Glassmorphism — 毛玻璃、透明背景、模糊层叠 |
| **Colors** | Primary `#0891B2` / Secondary `#22D3EE` / CTA `#22C55E` / BG `#ECFEFF` / Text `#164E63` |
| **Typography** | Heading: Outfit / Body: Work Sans |
| **Effects** | Backdrop blur 10-20px, 1px solid rgba(255,255,255,0.2), Z-depth |
| **避免** | 过度动画、默认深色模式 |

---

## 2. 配色方案库

### 按产品类型

| 产品类型 | Primary | Secondary | CTA | Background | Text | 备注 |
|----------|---------|-----------|-----|------------|------|------|
| Healthcare App | `#0891B2` | `#22D3EE` | `#059669` | `#ECFEFF` | `#164E63` | 冷静青色 + 健康绿 |
| Fintech/Crypto | `#F59E0B` | `#FBBF24` | `#8B5CF6` | `#0F172A` | `#F8FAFC` | 金色信任 + 紫色科技 |
| Micro SaaS | `#6366F1` | `#818CF8` | `#10B981` | `#F5F3FF` | `#1E1B4B` | 靛蓝主色 + 绿色行动 |
| Dashboard/Tech | `#1E293B` | `#334155` | `#22C55E` | `#0F172A` | `#F8FAFC` | 暗色科技 + 状态绿 |

### 配色使用规则

- **Primary** — 品牌色，用于导航、标题、关键 UI
- **Secondary** — 辅助色，用于次要元素、悬停态
- **CTA** — 行动号召色，仅用于主要按钮、关键操作
- **Background** — 页面背景色
- **Text** — 正文主色，确保与背景对比度 ≥ 4.5:1

---

## 3. 字体搭配库

### 精选搭配

| 搭配名称 | Heading | Body | 风格关键词 | 适用场景 |
|----------|---------|------|------------|----------|
| **Minimal Swiss** | Inter | Inter | 极简、瑞士、功能、专业 | Dashboard、管理后台、文档系统 |
| **Classic Elegant** | Playfair Display | Inter | 优雅、奢侈、永恒、高端 | 奢侈品牌、时尚、美容、杂志 |
| **Luxury Serif** | Cormorant | Montserrat | 奢华、精致、高端 | 时尚品牌、珠宝、高端服务 |
| **Modern Professional** | Outfit | Work Sans | 几何、现代、干净、平衡 | 通用、作品集、机构、Landing |
| **Real Estate Luxury** | Cinzel | Josefin Sans | 房产、优雅、精致 | 房地产、建筑、室内设计 |
| **Brutalist Raw** | Space Mono | Space Mono | 粗野、技术、极简 | 开发者作品集、实验性设计 |

### CSS 导入示例

```css
/* Modern Professional — Outfit + Work Sans */
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Work+Sans:wght@300;400;500;600;700&display=swap');

/* Classic Elegant — Playfair Display + Inter */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@400;500;600;700&display=swap');
```

### Tailwind 配置

```js
// tailwind.config.js
fontFamily: {
  heading: ['Outfit', 'sans-serif'],
  body: ['Work Sans', 'sans-serif'],
  serif: ['Playfair Display', 'serif'],
  mono: ['Space Mono', 'monospace'],
}
```

### 字体使用规则

- **行高**：正文 1.5–1.75，标题 1.1–1.3
- **行宽**：每行 65–75 字符
- **字重**：标题 600–700，正文 400，辅助 300
- **字体加载**：使用 `font-display: swap` 避免 FOIT

---

## 4. UI 风格库

### 核心风格速查

| 风格 | 关键词 | 主色系 | 性能 | 无障碍 | 复杂度 | 适用场景 |
|------|--------|--------|------|--------|--------|----------|
| **Glassmorphism** | 毛玻璃、透明、模糊、层叠 | 品牌色 + 透明层 | ⚠ 良好 | ⚠ 需 4.5:1 | 中 | 现代 SaaS、金融、高端企业 |
| **Dark Mode (OLED)** | 深黑、护眼、省电、高对比 | `#000000` / `#121212` | ⚡ 优秀 | ✓ WCAG AAA | 低 | 夜间模式、编码、娱乐 |
| **Neumorphism** | 柔和、浮雕、凹凸、圆润 | 单色系浅色背景 | ⚠ 良好 | ⚠ 对比度低 | 中 | 设置面板、音乐播放器 |
| **Cyberpunk** | 霓虹、终端、HUD、故障 | 霓虹绿/洋红/青 + 暗底 | ⚠ 中等 | ⚠ 有限 | 中 | 游戏、加密、开发者工具 |
| **Minimalism** | 极简、留白、功能、克制 | 黑白 + 单一强调色 | ⚡ 优秀 | ✓ 优秀 | 低 | 产品展示、内容优先 |

### Glassmorphism 实现要点

```css
/* 核心 CSS */
.glass-card {
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 16px;
}

/* 浅色模式修正 — 不要用 bg-white/10 */
.glass-card-light {
  background: rgba(255, 255, 255, 0.8); /* 至少 80% 不透明 */
  backdrop-filter: blur(16px);
  border: 1px solid rgba(0, 0, 0, 0.08);
}
```

### Dark Mode (OLED) 实现要点

```css
:root {
  --bg-black: #000000;
  --bg-dark-grey: #121212;
  --text-primary: #FFFFFF;
  --text-secondary: #B0B0B0;
  --accent-neon: #00FF88;
  --glow-effect: 0 0 10px rgba(0, 255, 136, 0.3);
}
```

---

## 5. Landing Page 结构模式

### 按转化目标选型

| 模式名称 | 区块顺序 | CTA 位置 | 转化优化要点 |
|----------|----------|----------|-------------|
| **Hero + Testimonials + CTA** | Hero → 问题 → 方案 → 评价 → CTA | Hero(粘性) + 评价后 | 社交证明前置 CTA，3-5 条带照片评价 |
| **Pricing-Focused** | Hero → 定价卡(3档) → 功能对比 → FAQ → CTA | 每张卡 + 导航粘性 + 底部 | 年付折扣 20-30%，推荐中间档 |
| **Waitlist/Coming Soon** | 倒计时 Hero → 预览 → 邮箱表单 → 等待人数 | 邮箱表单置顶 + 滚动粘性 | 稀缺感 + 排他性，显示等待人数 |
| **Newsletter** | 价值主张+表单 → 往期内容 → 订阅者数 → 作者简介 | Hero 内联表单 + 粘性头部 | 单字段(邮箱)，显示"加入 X,000 读者" |
| **Comparison Table** | Hero(问题) → 对比矩阵 → 深度功能 → CTA | 表格右列 + 底部 | 事实性对比，35% 转化提升 |
| **Before-After** | Hero(问题) → 变换对比 → 工作原理 → CTA | 变换展示后 + 底部 | 视觉证明，45% 转化提升 |

### 定价页面最佳实践

- **3 档定价**：Free → Starter → Pro（或 Pro → Business → Enterprise）
- **推荐中间档**：用 "Most Popular" 徽章 + 品牌色边框高亮
- **年付折扣**：20-30% 折扣，切换开关控制月/年
- **FAQ 解疑**：底部 FAQ 处理常见顾虑

---

## 6. 图表选型指南

### 数据类型 → 图表类型映射

| 数据类型 | 推荐图表 | 备选 | 配色要点 | 无障碍 | 推荐库 |
|----------|----------|------|----------|--------|--------|
| **时间趋势** | 折线图 | 面积图 | 主色 `#0080FF`，多系列用不同色，填充 20% 透明 | ✓ 加图案叠加 | Chart.js, Recharts |
| **类别比较** | 柱状图 | 分组柱状图 | 每柱不同色或同色，降序排列 | ✓ 加数值标签 | Chart.js, Recharts |
| **部分占整体** | 饼图/环形图 | 堆叠柱、树图 | ≤6 色，大块在前，加标签 | ⚠ 难无障碍，>5 项用堆叠柱 | Chart.js, D3.js |
| **漏斗/流程** | 漏斗图 | 桑基图 | 渐变色，显示转化率 | ✓ 清晰标签即可 | D3.js, Recharts |
| **多变量对比** | 雷达图 | 平行坐标、分组柱 | 单数据 20% 填充，多用不同色 | ⚠ 限 5-8 轴，加数据表 | Chart.js, Recharts |
| **比例/百分比** | 华夫饼图 | 堆叠柱 100% | 10×10 格，≤5 类，2-3px 间距 | ✓ 优于饼图 | D3.js, 自定义 CSS Grid |

### 图表无障碍规则

1. 不依赖颜色传达信息 — 加图案、标签、数值
2. 饼图 > 5 项时改用堆叠柱状图
3. 提供数据表格替代方案
4. 雷达图限制 5-8 个维度

---

## 7. UX 准则（按优先级）

### 🔴 CRITICAL — 可访问性（必须遵守）

| 规则 | Do ✅ | Don't ❌ |
|------|-------|---------|
| **颜色对比度** | 正文 ≥ 4.5:1，大字 ≥ 3:1 | 浅灰文字 `#94A3B8` 做正文 |
| **焦点状态** | `focus:ring-2 focus:ring-blue-500` | `outline-none` 无替代 |
| **替代文本** | 有意义的图片加描述性 alt | `alt=""` 或缺失 |
| **ARIA 标签** | 图标按钮加 `aria-label="关闭菜单"` | `<button><Icon/></button>` |
| **键盘导航** | Tab 顺序与视觉顺序一致 | 键盘陷阱或不可达元素 |
| **表单标签** | `<label for="email">` | 仅用 placeholder |

### 🔴 CRITICAL — 触控与交互

| 规则 | Do ✅ | Don't ❌ |
|------|-------|---------|
| **触控目标** | 最小 44×44px | 小于 44px 的按钮/链接 |
| **加载按钮** | `disabled={loading}` + spinner | 加载中仍可点击 |
| **错误反馈** | 清晰错误信息靠近问题字段 | 仅有顶部通用错误 |
| **光标** | 可点击元素加 `cursor-pointer` | 交互元素默认光标 |

### 🟡 HIGH — 性能与布局

| 规则 | Do ✅ | Don't ❌ |
|------|-------|---------|
| **图片优化** | WebP + srcset + lazy loading | 所有图片 eager 加载 |
| **减少动画** | `prefers-reduced-motion` 媒体查询 | 无视用户偏好 |
| **内容跳动** | 为异步内容预留空间 | 内容加载后布局位移 |
| **视口** | `width=device-width, initial-scale=1` | 缺少 viewport meta |
| **字体大小** | 移动端正文 ≥ 16px | 移动端 12-14px |
| **水平滚动** | 内容适配视口宽度 | 移动端横向溢出 |
| **z-index 管理** | 定义层级：10, 20, 30, 50 | 随意使用 9999 |

### 🟢 MEDIUM — 动画与排版

| 规则 | Do ✅ | Don't ❌ |
|------|-------|---------|
| **动画时长** | 微交互 150-300ms | < 100ms 或 > 500ms |
| **动画属性** | `transform` / `opacity` | 动画 `width` / `height` |
| **加载状态** | 骨架屏或 spinner | 界面冻结无反馈 |
| **行高** | 正文 1.5-1.75 | 紧凑行高 < 1.4 |
| **行宽** | 65-75 字符/行 | 过宽 > 90 字符 |

---

## 8. Tailwind 实践规范

### 响应式断点

| 断点 | 宽度 | 典型设备 |
|------|------|----------|
| `sm:` | ≥640px | 大手机横屏 |
| `md:` | ≥768px | 平板 |
| `lg:` | ≥1024px | 笔记本 |
| `xl:` | ≥1280px | 桌面 |
| `2xl:` | ≥1536px | 大桌面 |

### 常用模式

```html
<!-- 响应式间距 -->
<div class="px-4 sm:px-6 lg:px-8">

<!-- 响应式网格 -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

<!-- 浮动导航栏 -->
<nav class="fixed top-4 left-4 right-4 z-50 rounded-2xl bg-white/80 backdrop-blur-lg">

<!-- 可点击卡片 -->
<div class="cursor-pointer transition-colors duration-200 hover:bg-gray-50">

<!-- 加载骨架屏 -->
<div class="animate-pulse bg-gray-200 rounded h-4 w-3/4"></div>

<!-- 响应式图片 -->
<img srcset="small.jpg 480w, medium.jpg 768w, large.jpg 1200w"
     sizes="(max-width: 768px) 100vw, 50vw"
     src="medium.jpg" alt="描述">

<!-- 表单标签 -->
<label for="email" class="block text-sm font-medium text-gray-700">邮箱</label>
<input id="email" type="email" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm">
```

### 浅色/深色模式对比修正

| 元素 | 浅色模式 | 深色模式 |
|------|----------|----------|
| 毛玻璃卡片 | `bg-white/80` | `bg-white/10` |
| 正文文字 | `text-slate-900` (#0F172A) | `text-slate-50` (#F8FAFC) |
| 辅助文字 | `text-slate-600` (#475569) 最浅 | `text-slate-400` (#94A3B8) |
| 边框 | `border-gray-200` | `border-white/10` |

---

## 9. 交付前检查清单

### 视觉质量

- [ ] 无 Emoji 作图标 — 使用 SVG（Heroicons / Lucide）
- [ ] 图标风格统一 — 同一图标集
- [ ] 品牌Logo 正确 — 从 Simple Icons 验证
- [ ] 悬停不引起布局位移 — 用颜色/阴影/边框而非缩放
- [ ] 直接使用主题色 — `bg-primary` 而非 `var()` 包装

### 交互

- [ ] 所有可点击元素有 `cursor-pointer`
- [ ] 悬停提供明确视觉反馈
- [ ] 过渡流畅 150-300ms
- [ ] 键盘焦点可见

### 浅色/深色模式

- [ ] 浅色文字对比度 ≥ 4.5:1
- [ ] 毛玻璃/透明元素浅色模式可见
- [ ] 边框在两种模式下可见
- [ ] 两种模式均已测试

### 布局

- [ ] 浮动元素距边缘有间距 — `top-4 left-4 right-4`
- [ ] 内容不被固定导航栏遮挡
- [ ] 375px / 768px / 1024px / 1440px 响应式
- [ ] 移动端无水平滚动

### 无障碍

- [ ] 所有图片有 alt 文本
- [ ] 表单输入有 label
- [ ] 颜色不是唯一指示器
- [ ] 尊重 `prefers-reduced-motion`

---

## 10. 常见易错规则

### 图标与视觉元素

| 规则 | ✅ Do | ❌ Don't |
|------|-------|---------|
| **不用 Emoji 做图标** | 使用 SVG 图标（Heroicons、Lucide） | 使用 🎨 🚀 ⚙️ 等 Emoji |
| **稳定悬停态** | 颜色/透明度过渡 | 缩放变换导致布局移位 |
| **品牌 Logo** | 从 Simple Icons 获取官方 SVG | 猜测或使用错误路径 |
| **图标尺寸统一** | 固定 viewBox 24×24 + `w-6 h-6` | 随意混用不同尺寸 |

### 交互与光标

| 规则 | ✅ Do | ❌ Don't |
|------|-------|---------|
| **光标指针** | 所有可点击/可悬停卡片加 `cursor-pointer` | 交互元素默认光标 |
| **悬停反馈** | 颜色/阴影/边框变化 | 无任何交互指示 |
| **平滑过渡** | `transition-colors duration-200` | 瞬变或 > 500ms |

### 浅色/深色模式对比

| 规则 | ✅ Do | ❌ Don't |
|------|-------|---------|
| **浅色毛玻璃** | `bg-white/80` 或更高不透明度 | `bg-white/10`（太透明） |
| **浅色文字对比** | 正文用 `#0F172A` (slate-900) | 正文用 `#94A3B8` (slate-400) |
| **浅色辅助文字** | 最浅 `#475569` (slate-600) | gray-400 或更浅 |
| **边框可见性** | 浅色用 `border-gray-200` | `border-white/10`（不可见） |

### 布局与间距

| 规则 | ✅ Do | ❌ Don't |
|------|-------|---------|
| **浮动导航** | `top-4 left-4 right-4` 留间距 | `top-0 left-0 right-0` 紧贴 |
| **内容留白** | 考虑固定导航栏高度 | 内容隐藏在固定元素后 |
| **统一最大宽度** | 同一 `max-w-6xl` 或 `max-w-7xl` | 混用不同容器宽度 |

---

## 快速命令参考

```bash
# 1. 生成完整设计系统（必须先做）
python skills/ui-ux-pro-max/scripts/search.py "关键词" --design-system -p "项目名" -f markdown

# 2. 持久化设计系统（Master + 页面覆盖模式）
python skills/ui-ux-pro-max/scripts/search.py "关键词" --design-system --persist -p "项目名"
python skills/ui-ux-pro-max/scripts/search.py "关键词" --design-system --persist -p "项目名" --page "dashboard"

# 3. 按域搜索补充
python skills/ui-ux-pro-max/scripts/search.py "关键词" --domain style
python skills/ui-ux-pro-max/scripts/search.py "关键词" --domain typography
python skills/ui-ux-pro-max/scripts/search.py "关键词" --domain color
python skills/ui-ux-pro-max/scripts/search.py "关键词" --domain ux
python skills/ui-ux-pro-max/scripts/search.py "关键词" --domain landing
python skills/ui-ux-pro-max/scripts/search.py "关键词" --domain chart

# 4. 技术栈指南
python skills/ui-ux-pro-max/scripts/search.py "关键词" --stack html-tailwind
```

---

*本规范由 UI/UX Pro Max Skill 自动生成，涵盖 67 种风格、96 套配色、57 组字体、99 条 UX 准则、25 类图表。*
