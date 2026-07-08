# 产品方案定稿：B 站课程 → AI 可消费的 Agent Skills 知识库

> 产出自与需求方（kwinweng）的 brainstorming 对齐，2026-07-08。
> 本文档是产品方向的**最终裁决依据**，与 docs/02-架构设计.md 冲突时以本文为准。

## 1. 一句话定位

把 B 站学习课程自动转成**AI 编程助手可直接加载的 Agent Skills**，让团队的
Claude Code / Codex 在写代码时自动运用视频里学到的方法论——人只负责丢链接和审核。

## 2. Brainstorming 确认的关键决策

| # | 决策点 | 结论 | 影响 |
| --- | --- | --- | --- |
| 1 | 知识消费方 | **AI 编程助手**（非人类阅读） | 产出格式面向机器：结构化、规则化、去冗余 |
| 2 | 注入形态 | **Agent Skills（SKILL.md）** | M3 产出从"知识卡片"升级为符合 skills 规范的技能包（含触发描述 + 方法论正文），Claude Code / Codex 按需加载，不占常驻上下文 |
| 3 | 分发方式 | **本仓库即技能库** | skills 沉淀在 `knowledge-base/skills/`，目标项目用 git submodule / 插件 marketplace 引用；一处维护多项目共享 |
| 4 | 质量门禁 | **草稿区 + 人工审核后生效** | 新提炼先进 `knowledge-base/drafts/`，在管理后台（或飞书卡片按钮）点「采纳」后移入 `skills/`；防止 ASR 误识别、过时内容污染 AI 助手 |
| 5 | 项目上下文 | **需求方提供一段背景描述**（`project-context.md`） | 提炼时作为相关性判断依据；⛔ 当前阻塞：待提供 |
| 6 | 图文稿优先级 | **保留但后置**（移出 M2，排到飞书之后） | AI 价值优先；截图/图文稿是人看的增强功能 |

## 3. 修订后的产物流水线

```
B 站链接
  → 逐字稿（字幕优先 + whisper 兜底，不变）
  → 清洗稿 cleaned.md（不变）
  → 【变更】skill 草稿：knowledge-base/drafts/{topic}/SKILL.md
  → 【新增】人工审核（后台/飞书按钮：采纳 / 退回 / 丢弃）
  → 【变更】正式技能库：knowledge-base/skills/{topic}/SKILL.md（可被目标项目引用）
```

### Skill 草稿格式

```markdown
---
name: topic-slug
description: 何时使用本技能的触发描述（面向 AI 的加载判据）
source: BV1xxx《视频标题》时间戳区间；提炼时间；confidence: high|medium|low
status: draft   # 采纳后由流水线改为 approved 并移入 skills/
---

# 技能正文
面向 AI 的操作性方法论（步骤/规则/反例），保留到源视频时间戳的溯源引用。
```

一条视频可产出 0~N 个 skill 草稿（按主题拆分）；LLM 依据 `project-context.md`
判断相关性，不相关的主题不产出（决策 5，避免知识库噪音）。

### 与原架构的差异清单

- `distiller` 第二段的输出：知识卡片 → **skill 草稿**（格式如上）；`cards` 表改为
  `skills` 表（增加 `status: draft|approved|rejected` 与审核时间/操作人）
- 管理后台新增**审核队列页**：草稿列表 → 预览 → 采纳/退回/丢弃
- 飞书完成通知卡片附「采纳/退回」按钮（M4 实现；之前只能后台审）
- `snapshotter`（截图/图文稿）从 M2 移到 M5
- `knowledge-base/INDEX.md` 改为技能索引（按 status 与主题归组）

## 4. 修订后的里程碑

| 里程碑 | 内容 | 变化 |
| --- | --- | --- |
| M1 转写核心 | 不变（链接 → 逐字稿 CLI） | 无 |
| M2 服务化+后台 | 任务队列、提交/列表/详情页 | **移除图文稿**，增加审核队列页骨架 |
| M3 AI 提炼 | 清洗 + skill 草稿生成 + 审核流 + 技能库索引 | 产出形态变更为 SKILL.md |
| M4 飞书机器人 | 链接受理 + 完成卡片 + 卡片内审核按钮 | 增加审核按钮 |
| M5 图文稿+部署 | snapshotter 图文稿、Docker、告警、文档 | 图文稿移入 |

## 5. 待需求方提供（新增/变更）

1. **`project-context.md` 背景描述**（M3 前需要）：团队技术栈、业务域、当前开发流程痛点，
   200~500 字即可，越具体提炼越准；
2. 原有阻塞项不变：SESSDATA（M1 联调）、DeepSeek/Qwen Key（M3）、飞书应用（M4）。

## 6. 明确不做（YAGNI）

- 向量检索/RAG 基础设施（技能库靠 skills 的 description 触发机制按需加载，量大再说）
- 自动向目标项目提 PR 的跨仓库分发（先 submodule/手动引用，跑通再自动化）
- 多语言字幕、非 B 站平台（架构留了 resolver/downloader 扩展点，本期不实现）
