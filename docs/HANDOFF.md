# HANDOFF — 进度与任务协调（唯一真相源）

> 所有 AI 代理（Claude / Codex）开工前先读这里并认领任务，收工前更新这里。
> 规则见根目录 `AGENTS.md`。

## 当前状态

- **阶段**：M1 代码完成（21 个单测全过），待真实联调；下一步 M2
- **最后更新**：2026-07-08 by Claude（自动续开发第 1 轮）
- **分支**：`claude/bilibili-transcription-pipeline-27xuyu`

## 任务板（M1 · 转写核心）

| 任务 | 状态 | 认领 |
| --- | --- | --- |
| 项目脚手架（FastAPI 工程、配置加载、SQLite 迁移、.env.example） | ✅ 完成 | Claude |
| resolver：BV / b23.tv / 分P / 合集展开 | ✅ 完成 | Claude |
| transcriber-A：字幕直抓（wbi 签名 + SESSDATA + 限频 + CC/AI 字幕解析） | ✅ 完成 | Claude |
| transcriber-B：BBDown 音频下载 + faster-whisper（引擎可插拔） | ✅ 完成 | Claude |
| 统一 Transcript 结构 + transcript.md/json 落盘 | ✅ 完成 | Claude |
| CLI 批量入口 | ✅ 完成 | Claude |
| M1 真实联调（3 条链接验收，见 docs/03 验收标准） | ⛔ 阻塞(需 SESSDATA + 可访问 B 站的环境) | - |

状态取值：`待办` / `🔒 进行中(代理名)` / `✅ 完成(commit)` / `⛔ 阻塞(原因)`

## 任务板（M2 · 任务队列 + 管理后台）

| 任务 | 状态 | 认领 |
| --- | --- | --- |
| 任务表即队列的 asyncio worker（重启恢复、失败重试） | 🔒 进行中(Claude) | Claude |
| REST API（提交/列表/详情/重试） | 🔒 进行中(Claude) | Claude |
| 后台页面：任务提交（批量）、任务列表、成果详情（逐字稿预览） | 🔒 进行中(Claude) | Claude |
| 审核队列页骨架 | 🔒 进行中(Claude) | Claude |

M3~M5 任务见 `docs/03-实施计划.md`，进入相应里程碑时把任务拆到此表。

## 开发环境注意（给所有代理）

- `uv venv .venv && uv pip install -e ".[dev]"`，测试 `.venv/bin/pytest`
- **本远程执行环境的代理禁止访问 api.bilibili.com（403）**——不要试图真实联调，
  单测一律 mock 外部接口；真实联调在用户自己的机器上做
- wbi 签名已用 bilibili-API-collect 官方文档测试向量验证（tests/test_wbi.py）
- faster-whisper 是可选依赖（`.[asr]`），本环境未安装，ASR 代码路径靠接口抽象保证可测

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
- 2026-07-08 Claude（自动续开发第 1 轮）：完成 M1 全部编码——脚手架（pyproject/config/
  db/app）、wbi 签名（过官方测试向量）、BiliClient（限频+字幕+合集）、resolver、
  transcriber（字幕优先+ASR 兜底，引擎可插拔）、storage 落盘、CLI。21 个单测全过。
  M1 真实联调阻塞于 SESSDATA 与网络环境。下一步：M2 任务队列 + REST API。
