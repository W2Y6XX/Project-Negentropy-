# 负熵引擎

负熵引擎是一个面向个人使用的本地可运行 MVP，目标是把“记录事件 -> 更新能量与节点 -> 生成周复盘 -> 生成快照 -> 提取经验规则”这条最小闭环工程化。

当前仓库已经完成：

- `T1-T6` 的 V1 运行层后端
- V1.5 首轮分析层后端
- `T7` 最小前端单页壳层

当前仍未完成：

- 多页面或更完整的前端信息架构
- V2 决策层

## 当前状态

- 当前处于 D0 / MVP 冻结阶段。
- 仓库已具备真实可运行的本地后端，不再只是资料集。
- `seed.py` 会重建 SQLite 数据库并导入 D0 基线。
- 现有后端已支持事件录入、自然语言事件解析、关键节点更新、周复盘生成、快照生成。
- 新增 V1.5 分析层，已支持 `energy_rules`、`progress_rules`、审批回流和轻量调度。

## 系统阶段

```text
V1   -> Runtime Layer
V1.5 -> Analytics Layer
V2   -> Decision Layer
```

### V1

V1 负责运行时闭环，解决“数据问题”：

- 记录事件
- 更新能量和节点进度
- 生成周复盘
- 生成快照

### V1.5

V1.5 是参数识别阶段，解决“模型问题”：

- 从真实事件数据中提取 `energy_rules`
- 从事件绑定的节点进度日志中提取 `progress_rules`
- 生成待审批建议
- 接收人工修改 / 批准 / 拒绝
- 将审批结果回流到下一轮拟合

当前首轮 V1.5 保持“分析层”定位：

- 不直接改写 `events`
- 不直接改写 `system_state`
- 不直接自动驱动 `key_nodes`
- 只通过分析表、建议表和反馈表表达结果

### V2

V2 将读取 V1.5 产出的规则和参数，生成策略、调度和风险预警。当前不在实现范围内。

## 当前仓库结构

```text
negentropy-engine/
├── frontend/
│   ├── index.html
│   └── assets/
│       ├── app.css
│       └── app.js
├── database/
│   └── schema.sql
├── seed/
│   └── init_self_model.json
├── backend/
│   └── main.py
├── seed.py
├── requirements.txt
└── README.md
```

说明：

- SQLite 是唯一运行时主数据源。
- `init_self_model.json` 只用于 seed。
- 压缩包和历史文档仍作为输入资料保留，不参与运行时写入。

## 快速启动

```bash
pip install -r requirements.txt
python seed.py
uvicorn backend.main:app --reload
```

启动后访问：

```text
http://127.0.0.1:8000/docs
```

注意：

- `python seed.py` 会删除旧的 `negentropy.db` 并重新初始化 schema
- 若设置 `OPENAI_API_KEY` 和 `OPENAI_MODEL`，自然语言事件解析会调用 OpenAI 兼容接口
- 可选设置 `OPENAI_BASE_URL`
- 若设置 `ANALYTICS_SCHEDULER_ENABLED=0`，将关闭 V1.5 内置轻量调度

## 当前接口

### V1 运行层

- `GET /health`
- `GET /events`
- `POST /events`
- `POST /events/parse`
- `POST /events/confirm`
- `GET /key-nodes`
- `PATCH /key-nodes/{id}`
- `POST /weekly-review/generate`
- `GET /weekly-review`
- `POST /snapshot/generate`
- `GET /snapshot`
- `GET /`

### V1.5 分析层

- `POST /analytics/run`
- `GET /analytics/runs`
- `GET /analytics/runs/{id}`
- `GET /analytics/rules/energy`
- `GET /analytics/rules/progress`
- `GET /analytics/suggestions`
- `POST /analytics/suggestions/{id}/review`
- `GET /analytics/insights/latest`
- `GET /analytics/scheduler/status`

## 当前行为边界

### V1

- `POST /events` 兼容正式字段和 starter 简版字段
- `POST /events/parse` 只生成结构化草稿，不直接写库
- `POST /events/confirm` 负责确认后写库
- `PATCH /key-nodes/{id}` 现在支持可选 `source_event_id` 和 `reason`
- 当 `progress` 发生变化时，会写入 `key_node_progress_logs`
- 若提供 `source_event_id`，则将这次进度变化绑定到具体事件
- `GET /` 提供一个最小单页控制台，覆盖事件、节点、周复盘、快照和分析审批

### V1.5

- `POST /analytics/run` 默认分析最近 30 天数据
- `energy_rules` 以 `events.event_type` 为分组键
- `progress_rules` 以 `event_type + node_type` 为分组键
- 审批通过或人工编辑后的建议会在下一轮分析中作为加权监督样本参与拟合
- 被拒绝的建议不会直接进入均值拟合
- 内置轻量调度：
  - 每日 02:00 运行最近 7 天日分析
  - 每周一 03:00 运行最近 30 天周分析

## D0 边界

### 当前目标

1. 初始化系统
2. seed D0 self model
3. 记录事件和 delta
4. 更新关键节点
5. 生成周复盘
6. 生成快照
7. 从运行数据中提取最小可解释规则

### 当前非目标

- 泛化超级 Agent
- 全自动人生决策系统
- 云端同步或多端同步
- 微服务拆分
- 向量数据库
- 黑箱预测建模
- 推荐系统
- 复杂前端框架膨胀
- V2 自动策略执行

## 成功标准

当前本地版本可视为完成，当且仅当至少满足：

- 能初始化一个 D0 self model
- 能录入事件并查询
- 能更新关键节点并记录进度日志
- 能生成周复盘
- 能生成快照
- 能手动运行一次 V1.5 分析
- 能得到至少一条 `energy_rules` 或 `progress_rules`
- 能对建议进行审批并在下一轮分析中回流
- 能通过 `/` 页面完成最小联调，而不只依赖接口工具

## 关联文档

- 详细项目背景：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_PROJECT_BRIEF_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_PROJECT_BRIEF_CN.md)
- MVP 任务拆分：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_MVP_TASK_BREAKDOWN_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_MVP_TASK_BREAKDOWN_CN.md)
- 术语文档：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_GLOSSARY_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_GLOSSARY_CN.md)
- 字段字典：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_FIELD_DICTIONARY_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_FIELD_DICTIONARY_CN.md)

## 对开发者 / Agent 的约束

- 优先完成 MVP 闭环，不擅自扩功能
- 需求不清晰时优先选择最小可运行实现
- 优先保留可解释规则，不提前引入黑箱模型
- V1.5 只做分析、建议和审批回流，不直接篡改 V1 运行态

一句话提醒：

> 这个项目的核心不是“做一个看起来很强的系统”，而是先做一个可记录、可更新、可复盘、可快照、可学习的本地运行内核。
