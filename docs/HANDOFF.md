# HANDOFF — 进度与任务协调（唯一真相源）

> 所有 AI 代理（Claude / Codex）开工前先读这里并认领任务，收工前更新这里。
> 规则见根目录 `AGENTS.md`。

## 当前状态

- **阶段**：**M1~M5 全部编码完成**（76 个单测全过）；剩余工作=真实环境联调验收（见阻塞项）
- **最后更新**：2026-07-08 by Claude（连续开发模式）
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
| 任务表即队列的 asyncio worker（重启恢复、失败重试） | ✅ 完成 | Claude |
| REST API（提交/列表/详情/重试） | ✅ 完成 | Claude |
| 后台页面：任务提交（批量）、任务列表、成果详情（逐字稿预览） | ✅ 完成 | Claude |
| 审核队列页骨架 | ✅ 完成 | Claude |

## 任务板（M3 · AI 知识提炼）

| 任务 | 状态 | 认领 |
| --- | --- | --- |
| OpenAI 兼容 LLM 客户端（DeepSeek/Qwen 切换）+ 长文本分块 | ✅ 完成 | Claude |
| 清洗 prompt + cleaned.md | ✅ 完成 | Claude |
| skill 草稿生成（SKILL.md 格式见产品定稿 spec §3）+ project-context 机制 | ✅ 完成 | Claude |
| drafts → 审核 → skills 状态流转 + INDEX.md 索引 | ✅ 完成 | Claude |
| 后台审核队列页启用（采纳/退回，含草稿全文预览） | ✅ 完成 | Claude |
| worker 接入 distill 步骤（任务 options.distill=true 时执行） | ✅ 完成 | Claude |
| M3 真实验收（真实视频跑全链路产出可加载 skill） | ⛔ 阻塞(需 LLM API Key + project-context.md) | - |

## 任务板（M4 · 飞书机器人）

| 任务 | 状态 | 认领 |
| --- | --- | --- |
| lark-oapi 长连接接入 + 消息提取 B 站链接 + 事件去重 | ✅ 完成 | Claude |
| 受理回执 + 完成通知卡片（含 skill 草稿数与落盘路径） | ✅ 完成 | Claude |
| 卡片「采纳/退回」审核按钮（与后台同一状态机） | ✅ 完成 | Claude |
| 群聊 @ 与私聊两种场景 | ✅ 完成(消息处理不区分场景，@提及文本同样被解析) | Claude |
| M4 真实验收（真实飞书应用联调） | ⛔ 阻塞(需飞书 App ID/Secret) | - |

M3~M5 任务见 `docs/03-实施计划.md`，进入相应里程碑时把任务拆到此表。

## 任务板（M5 · 图文稿 + 打磨与部署）

| 任务 | 状态 | 认领 |
| --- | --- | --- |
| snapshotter：视频下载 + ffmpeg 按段落抽帧 → article.md 图文稿 | ✅ 完成 | Claude |
| 后台接入图文稿（提交选项 + 详情展示） | ✅ 完成 | Claude |
| 简单鉴权（后台访问口令） + 失败告警 | ✅ 完成 | Claude |
| Docker Compose 一键部署 | ✅ 完成(镜像构建未在本环境验证，Docker 不可用) | Claude |
| 使用文档 | ✅ 完成(docs/04) | Claude |

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
- 2026-07-08 Claude（自动续开发第 2 轮）：完成 M2——service 层（任务表即队列，幂等建任务/
  原子认领/失败重试≤3次/重启恢复）、asyncio worker（runner 可注入）、REST API、
  管理后台（提交/列表/详情+逐字稿预览/审核队列骨架，Jinja2 服务端渲染）。
  38 个单测全过；uvicorn 真实进程冒烟验证了「提交→认领→重试→failed」全链路。
  M3 任务已拆入任务板。下一步：M3 AI 知识提炼（阻塞项：LLM API Key 与
  project-context.md 仍未提供，开发可先 mock LLM，真实提炼需等密钥）。
- 2026-07-08 Claude（连续开发）：完成 M3——OpenAI 兼容 LLM 客户端（DeepSeek/Qwen 配置
  切换，MockTransport 测试）、chunk 分块、两段式提炼（清洗 prompt → skill 草稿 JSON，
  容错解析+字段归一化）、SKILL.md 渲染（frontmatter 含触发 description/溯源/confidence）、
  drafts→approve/reject 状态流转（文件移动+frontmatter 同步+INDEX.md 重建）、
  后台审核队列页（全文预览+采纳/退回按钮）、runner 集成 options.distill
  （无 API Key 时优雅跳过不失败）。58 个单测全过。继续 M4 飞书机器人。
- 2026-07-08 Claude（连续开发）：完成 M4——feishu_bot 模块：链接提取（视频/短链/合集/
  裸BV，去重保序）、事件去重表、handle_message（受理回执+source=feishu+distill 默认开）、
  完成通知卡片（逐字稿来源+落盘路径+每个 skill 草稿的采纳/退回按钮）、失败通知、
  handle_card_action（与后台同一 skills_store 状态机）、worker notifier 钩子
  （done 通知一次/重试耗尽才通知 failed）。lark-oapi 为可选依赖 .[feishu]，
  SDK 接线集中在 serve()（长连接+worker 同进程），业务逻辑纯函数全覆盖测试。
  68 个单测全过。真实联调需飞书凭据。
- 2026-07-08 Claude（连续开发）：完成 M5——snapshotter（视频下载+ffmpeg 抽帧可注入、
  段落起点稀释 min_gap、抽帧失败不阻塞整篇）、articles 表补进 schema（M1 遗漏，
  引发 10 个测试失败已修复）、后台图文稿选项与详情预览、admin_token 鉴权中间件
  （header/query/cookie 三通道，/healthz 豁免）、失败告警群 FEISHU_ALERT_CHAT_ID、
  Dockerfile + docker-compose（admin 与 feishu 双服务共库，feishu 用 profile 开关）、
  docs/04 部署与使用文档、README 状态更新。76 个单测全过。
  **全部里程碑编码完成**，剩余为真实环境联调（需 SESSDATA/LLM Key/飞书凭据）。
