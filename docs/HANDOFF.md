# HANDOFF — 进度与任务协调（唯一真相源）

> 所有 AI 代理（Claude / Codex）开工前先读这里并认领任务，收工前更新这里。
> 规则见根目录 `AGENTS.md`。

## 当前状态

- **阶段**：设计完成，等待进入 M1 开发
- **最后更新**：2026-07-08 by Claude
- **分支**：`claude/bilibili-transcription-pipeline-27xuyu`

## 任务板（M1 · 转写核心）

| 任务 | 状态 | 认领 |
| --- | --- | --- |
| 项目脚手架（FastAPI 工程、配置加载、SQLite 迁移、.env.example） | 🔒 进行中(Claude) | Claude |
| resolver：BV / b23.tv / 分P / 合集展开 | 🔒 进行中(Claude) | Claude |
| transcriber-A：字幕直抓（wbi 签名 + SESSDATA + 限频 + CC/AI 字幕解析） | 🔒 进行中(Claude) | Claude |
| transcriber-B：BBDown 音频下载 + faster-whisper（引擎可插拔） | 🔒 进行中(Claude) | Claude |
| 统一 Transcript 结构 + transcript.md/json 落盘 | 🔒 进行中(Claude) | Claude |
| CLI 批量入口 | 🔒 进行中(Claude) | Claude |

状态取值：`待办` / `🔒 进行中(代理名)` / `✅ 完成(commit)` / `⛔ 阻塞(原因)`

M2~M5 任务见 `docs/03-实施计划.md`，进入相应里程碑时把任务拆到此表。

## 阻塞项（需要人工提供）

| 事项 | 影响 | 状态 |
| --- | --- | --- |
| B 站账号 SESSDATA | transcriber-A 真实联调（开发和单测可先 mock） | 未提供 |
| DeepSeek/Qwen API Key | M3 才需要 | 未提供 |
| 项目背景描述（project-context.md，200~500 字） | M3 提炼相关性判断 | 未提供 |
| 飞书 App ID/Secret | M4 才需要 | 未提供 |

## 待人工决策

（无——如代理认为需要变更已确认的技术选型，在此提出并停止相关开发）

## 历史日志

- 2026-07-08 Claude：完成调研（docs/01）、架构设计（docs/02）、实施计划（docs/03），
  搭好协作机制（AGENTS.md + 本文件 + 每小时自动续开发 Routine）。代码未开始。
- 2026-07-08 Claude：与需求方 brainstorming 定稿产品方向——知识产出改为
  **AI 可加载的 Agent Skills**（drafts 草稿区 + 人工审核门禁），图文稿后置到 M5。
  详见 docs/superpowers/specs/2026-07-08-knowledge-skills-design.md，
  docs/03 里程碑已同步修订。**所有代理实现 M3 时以该 spec 为准。**
