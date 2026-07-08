# AGENTS.md — AI 协作开发指南

本仓库由多个 AI 编程代理协作开发（Claude Code + Codex），人类负责人：kwinweng。
**任何代理开始工作前，必须先读完本文件和 `docs/HANDOFF.md`。**

## 项目是什么

把 B 站学习课程视频批量转成文字逐字稿，再用 LLM 提炼成团队专有开发知识库。
两个入口：飞书机器人（丢链接→出稿）和管理后台（批量链接→图文稿）。

- 需求与方案对比：`docs/01-开源方案调研.md`
- 系统设计（模块/数据模型/API/目录结构/配置）：`docs/02-架构设计.md`
- 里程碑与验收标准：`docs/03-实施计划.md`
- **当前进度与任务认领：`docs/HANDOFF.md`（唯一的协调真相源）**

## 硬性规则

1. **分支**：所有开发都在 `claude/bilibili-transcription-pipeline-27xuyu` 分支上进行，
   不要新开分支、不要 force push。
2. **开工三步**：`git pull` 拿最新代码 → 读 `docs/HANDOFF.md` → 在其中把你要做的任务
   标记为「🔒 进行中(你的代理名)」并立即 commit+push 这一行改动（这是任务锁，防止
   两个代理同时做一件事）。
3. **收工两步**：更新 `docs/HANDOFF.md`（完成项打勾、写清下一步、记录阻塞）→ push。
4. **小步提交**：每完成一个可运行的子功能就提交，commit message 用
   `feat|fix|docs(scope): 中文描述` 格式。
5. **不要偏离架构文档**：技术选型（FastAPI / SQLite / faster-whisper / DeepSeek 兼容接口
   / BBDown / lark-oapi 长连接）已与需求方确认，如认为必须变更，在 HANDOFF.md 的
   「待人工决策」区提出，不要自行更换。
6. **密钥**：一律走 `.env`（见架构文档 §7 配置清单），提供 `.env.example`，
   绝不提交真实密钥。

## 工程约定

- Python 3.11+，包管理用 `uv`（若不可用则 pip + requirements.txt）
- 代码放 `src/pipeline/` 下，模块名与架构文档 §3 对应：
  `resolver` / `transcriber` / `snapshotter` / `distiller` / `feishu_bot` / `admin`
- 测试：pytest，放 `tests/`；外部接口（B 站 API、LLM）一律 mock，测试不许打真实网络
- 每个模块先写最小可跑版本，通过里程碑验收标准后再打磨

## 验证

实现代码后至少运行：`pytest`。涉及 CLI 的里程碑（M1）需在 HANDOFF.md 里贴一次
真实链接的运行输出（人工提供 SESSDATA 后）。
