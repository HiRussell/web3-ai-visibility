# Web3 AI Visibility Tracker — 项目协议

## 项目背景

业余项目（vibe-code mode）。追踪 Perplexity / ChatGPT / Grok / Gemini 等 AI 搜索产品对加密协议的提及与引用情况，每周出公开 leaderboard。

详见 `README.md` + `.web3seo-dev/`（progress / decisions / failures）。

设计方法论继承 `~/Library/CloudStorage/Dropbox/Mirror_Lake/corvus/CLAUDE.md`（具体应用见本项目 `.web3seo-dev/decisions.md` D-001 ~ D-010）。

---

## Git 操作约定（覆盖全局 CLAUDE.md 部分条款）

**用户明确允许，本项目不再继承全局以下硬规则：**

- ✅ **可以未授权 commit**（仅本项目，2026-05-08 用户授权）
- ✅ **可以未授权 push**（仅 push 到 origin main 的 fast-forward）

**仍继承全局规则、不被覆盖的硬底线：**

- ❌ **严禁 `git add -A` / `git add .` / `git add *`**——Corvus 2026-04-24 docx leak 的教训不因 hobby 就消失。每次 commit 必须显式列文件名。
- ❌ **严禁 force-push / history rewrite / `git reset --hard`** 不经用户授权
- ❌ **严禁删 `.env`、`data/store.db`、`data/defillama_protocols.json` 等用户运行时产物**

**Commit 规范：**
- 每个 commit 单一目的（fix / feat / chore / docs）
- 消息以 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` 结尾

---

## 开发约定

主要原则（继承 Corvus 方法论中真正适用本项目的部分；不适用的别 cargo-cult，参见全局 memory `feedback_no_principle_decoration.md` 的教训）：

- **Map ≠ Territory**：LLM 输出（地图）必须用独立通道（DefiLlama canonical 列表 / HTTP citation 验证 / 真实 SQLite 数据）做疆域 check。
- **Inversion**：写新功能前先列失败模式（`.web3seo-dev/failures.md`）。
- **如无必要勿增实体**：v1 不做 user 系统、不做 sentiment、不做实时、不做花哨 UI。每加一项都要说清"换来什么用户可感知收益"。
- **Three-stage idempotent pipeline**：fetch → extract → aggregate，每阶段 idempotent on 不同 key，可独立重跑。

---

## 进入项目的第一件事

按顺序读：

1. `.web3seo-dev/progress.md` —— 当前进度状态
2. `.web3seo-dev/failures.md` —— 真实运行踩过的坑
3. `.web3seo-dev/decisions.md` —— 关键设计决策（为什么这么做）

不要凭代码猜上下文。这三个文件就是 anti-amnesia 知识库。

---

## 当前状态（2026-05-08）

- A、B 阶段完成（脚手架 + OpenRouter 抽象 + 23 测试）
- GitHub: `HiRussell/web3-ai-visibility`（private）
- 已经过第一次实弹（10 query × Perplexity），暴露并修复了 protocol-name false-positive（见 failures.md 2026-05-08）
- 接下来：扩 50 query × Perplexity → 看密度数据 → 决定要不要扩到 4 模型
