# 负熵引擎 MVP 最小任务拆分与验收标准

## 0. 文档目标

本文档将 D0 / MVP 压缩为最小可执行任务集。当前仓库的实现状态已经从纯 V1 推进到：

- `T1-T6` 已完成
- `V1.5-A1` 首轮分析层已完成
- `T7` 已完成最小单页壳层版本

本文档的重点不再是“从零开始”，而是明确：

- 哪些任务已经完成
- 哪些任务是当前 MVP 剩余项
- V1.5 首轮已经实现到什么程度

## 1. 已完成任务

### T1. 工程骨架落盘

已完成内容：

- `database/schema.sql`
- `seed/init_self_model.json`
- `backend/main.py`
- `seed.py`
- `requirements.txt`
- 根目录 `README.md`

验收标准：

- `pip install -r requirements.txt` 可执行
- `uvicorn backend.main:app --reload` 可启动
- `/docs` 可访问

### T2. 数据库初始化与 Seed 打通

已完成内容：

- `python seed.py` 每次重建数据库
- D0 基线导入成功
- 核心业务表和关联表可用

验收标准：

- 连续两次运行 `python seed.py` 均成功
- `system_state`
- `channels`
- `traits`
- `skills`
- `key_nodes`
- `goals`
- `events`
- `weekly_reviews`
- `energy_pools`
- `snapshots`

以上核心表存在，且有 D0 基线数据

### T3. 事件录入与查询接口

已完成内容：

- `GET /events`
- `POST /events`
- `POST /events/parse`
- `POST /events/confirm`

验收标准：

- 能写入事件并被查询到
- `occurred_at` 统一归一化到 UTC
- 自然语言事件先解析，再确认写库

### T4. 关键节点查询与更新接口

已完成内容：

- `GET /key-nodes`
- `PATCH /key-nodes/{id}`

当前新增：

- `PATCH /key-nodes/{id}` 支持可选 `source_event_id`
- `PATCH /key-nodes/{id}` 支持可选 `reason`
- 进度变化会写入 `key_node_progress_logs`

验收标准：

- 能更新关键节点 `progress` / `status` / `notes`
- `progress` 变化时会记录日志
- 非法 `source_event_id` 返回 400

### T5. 周复盘生成

已完成内容：

- `POST /weekly-review/generate`
- `GET /weekly-review`

验收标准：

- 能生成非 placeholder 的 markdown 周复盘
- 同一周重复生成时更新原记录，不插入重复脏数据

### T6. 快照生成

已完成内容：

- `POST /snapshot/generate`
- `GET /snapshot`

验收标准：

- 能生成新的 snapshot 记录
- 能读取最新 snapshot

## 2. V1.5 首轮任务

### V1.5-A1. 分析层最小闭环

已完成内容：

- `analytics_runs`
- `energy_rules`
- `progress_rules`
- `analytics_suggestions`
- `analytics_feedback`
- `key_node_progress_logs`

已完成接口：

- `POST /analytics/run`
- `GET /analytics/runs`
- `GET /analytics/runs/{id}`
- `GET /analytics/rules/energy`
- `GET /analytics/rules/progress`
- `GET /analytics/suggestions`
- `POST /analytics/suggestions/{id}/review`
- `GET /analytics/insights/latest`
- `GET /analytics/scheduler/status`

规则生成范围：

- `energy_rules`：按 `event_type` 聚合 `body_delta` / `mind_delta`
- `progress_rules`：按 `event_type + node_type` 聚合 `progress_delta`

审批回流范围：

- `approved` / `edited` 的建议会参与下一轮拟合
- `rejected` 的建议不会进入均值拟合

轻量调度范围：

- 每日 02:00 跑最近 7 天分析
- 每周一 03:00 跑最近 30 天分析
- 可通过 `ANALYTICS_SCHEDULER_ENABLED=0` 关闭

验收标准：

- 空样本执行 `POST /analytics/run` 不报错
- 有事件后能生成 `energy_rules`
- 有绑定事件的节点进度日志后能生成 `progress_rules`
- 能查询建议列表
- 能审批建议
- 下一轮分析能吸收审批结果

## 3. 当前剩余任务

### T7. 最小前端壳层与联调

已完成内容：

- 根路径 `/` 提供单页控制台
- 页面可完成事件解析 / 确认写库
- 页面可更新关键节点
- 页面可生成周复盘和快照
- 页面可运行 V1.5 分析并审批建议

当前剩余增强项：

- 若需要更清晰的信息架构，再拆分为多页面
- 若需要更强展示，再补规则趋势和历史批次对比

验收标准：

- 用户不借助 Postman 也能跑通一次完整闭环
- 能查看 V1.5 最新规则和待审批建议

## 4. 当前总体验收标准

当前本地版本可视为达到“V1 + V1.5 首轮可用”，当且仅当同时满足：

1. `python seed.py` 能初始化系统
2. API 文档可访问
3. 能写入事件
4. 能更新关键节点并记录进度日志
5. 能生成周复盘
6. 能生成快照
7. 能手动运行分析
8. 能产出规则或建议
9. 能审批建议并在下一轮分析中回流
10. 能通过 `/` 页面完成最小联调

## 5. 不纳入当前验收

- 用户系统
- 登录 / 注册
- 云端同步 / 多端同步
- 推荐系统
- 黑箱预测模型
- V2 自动策略执行
- 复杂前端框架膨胀

一句话约束：

> 当前不是做“复杂智能系统”的阶段，而是把运行层和分析层都做成真实可验证、可迭代的本地闭环。
