# 负熵引擎

负熵引擎是一个面向个人使用的本地可运行 MVP，目标是把“记录事件 -> 更新节点/能量池 -> 生成周复盘 -> 生成快照”这条最小闭环工程化。

本文档是当前仓库的主入口，服务对象是开发者和代码代理。当前仓库已经完成首轮 `T1-T2` 底座构建：工程骨架已落盘、数据库 schema 可反复初始化、FastAPI 服务可启动，但完整 MVP 闭环尚未进入实现阶段。

## 当前状态

- 当前处于 D0 / MVP 冻结阶段。
- 当前仓库已完成 `T1-T2` 底座版整理，具备最小工程结构与启动条件。
- 当前实现只覆盖 schema 初始化、服务启动、只读查询接口与未实现占位接口。
- `init_self_model.json` 已保留为后续 `T3+` 输入，但本轮不导入数据库。
- 当前目标不是扩展功能，而是先把真实工程底座做稳。

## 资料来源

### 1. starter 工程骨架

`negentropy_engine_engineering_starter (1).zip` 提供了最小工程轮廓和启动方式，核心内容包括：

- `requirements.txt`
- `seed.py`
- `backend/main.py`
- `README_STARTER.txt`

它说明了目标工程的基本目录形态和最小 API 外壳。本仓库当前的底座文件就是据此整理出来的，但业务层仍然是未完成状态。

### 2. schema 数据包

`negentropy_engine_schema_bundle (1).zip` 提供了 D0 的结构化数据基础：

- `schema.sql`
- `self_model.schema.json`
- `init_self_model.json`

其中：

- `schema.sql` 用于初始化 SQLite 表结构
- `init_self_model.json` 用于后续 seed 初始自我模型
- `self_model.schema.json` 用于描述数据结构和字段约束

### 3. 中文项目文档

`NEGENTROPY_ENGINE_DOCS_CN (2).zip` 和当前目录中的 `0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/` 提供了中文背景资料：

- `NEGENTROPY_ENGINE_PROJECT_BRIEF_CN.md`
- `NEGENTROPY_ENGINE_GLOSSARY_CN.md`
- `NEGENTROPY_ENGINE_FIELD_DICTIONARY_CN.md`

这些文档分别承担项目概述、术语说明、字段释义。README 只保留开发入口需要的信息，不重复承载字段级细节。

## 目标仓库结构

当前仓库已整理为如下基础结构：

```text
negentropy-engine/
├─ database/
│  └─ schema.sql
├─ seed/
│  └─ init_self_model.json
├─ backend/
│  └─ main.py
├─ seed.py
├─ requirements.txt
└─ README.md
```

说明：

- SQLite 是唯一主数据源
- `init_self_model.json` 只用于 seed，不应与数据库形成双真源
- 当前桌面目录中的压缩包和文档，仍作为输入材料保留

## 快速启动

当前底座可直接使用以下命令启动：

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

- `python seed.py` 会删除旧的 `negentropy.db` 并重新执行 `database/schema.sql`
- 本轮 `seed.py` 不导入 `seed/init_self_model.json`，只保留该文件供后续任务使用
- 当前目录已具备底座运行条件，但不代表完整 MVP 已完成

## 当前已知实现边界

根据当前仓库中的 `backend/main.py` 与 `seed.py`，本轮可用接口和行为如下。

### 已有接口

- `GET /health`
- `GET /events`
- `GET /snapshot`
- `GET /weekly-review`

### 当前行为

- `seed.py` 每次运行都会删除旧数据库并重新建表
- `seed.py` 只执行 `database/schema.sql`，不写入任何 seed 数据
- `GET /events` 读取正式 `events` 表，在空库状态下返回空列表
- `GET /snapshot` 读取 `snapshots` 最新记录，在空库状态下返回空值
- `GET /weekly-review` 明确返回未实现占位响应

### 明确未完成

- `POST /events`
- `GET /key-nodes` / `PATCH /key-nodes/{id}`
- JSON seed 导入与引用解析
- 周复盘生成逻辑
- snapshot 生成功能
- 可用的正式前端页面

## D0 业务边界

### MVP 目标

当前阶段只要求完成以下最小闭环：

1. 初始化系统
2. seed D0 self model
3. 记录事件和 delta
4. 更新至少一个关键节点进度
5. 生成周复盘 markdown
6. 生成 snapshot

### 当前非目标

以下内容不是 D0 主线，不应抢占当前开发时间：

- 泛化超级 Agent
- 全自动人生决策系统
- 云端同步或多端同步
- 微服务拆分
- 向量数据库
- 复杂预测建模、聚类、自动采集
- 推荐系统
- 复杂前端框架膨胀

## 建模摘要

系统采用五大模块建模：

- Body
- Mind
- Spirit
- Vocation
- Channel

工程上应使用以下理解：

- `Body / Mind` 是基础层，承载能量池和能力状态
- `Spirit / Vocation` 是高维实现层，承载长期方向、角色路径和关键节点
- `Channel` 是资源投放方向和优先级的高阶变量

冻结规则摘要：

- `Level` 只对应 `Body / Mind`
- D0 默认使用整数等级
- `Phase` 描述系统阶段，不是短期情绪
- `Traits` 是系统化标签，不是随意备注

详细定义见项目概述和字段字典，不在 README 中展开。

## 开发优先顺序

完整 MVP 推荐顺序如下：

1. 统一数据模型与数据库 schema
2. 完成 FastAPI 最小接口
3. 完成 seed / init 流程
4. 完成事件录入和 delta 更新
5. 完成 key nodes 展示与修改
6. 完成 weekly review 生成
7. 完成 snapshot 生成
8. 最后补最小前端

并行开发时也应保持：

- 后端闭环优先
- 前端只做最少页面，不扩范围

## 成功标准

D0 / MVP 可视为完成，当且仅当至少满足：

- 能初始化一个 D0 self model
- 能录入一条事件
- 能写入对应 delta
- 能更新至少一个关键节点进度
- 能生成一份周复盘 markdown
- 能生成一份 snapshot
- 全流程可在本地跑通

## 本轮底座完成标准

首轮 `T1-T2` 可视为完成，当且仅当至少满足：

- 已落盘 `database/`、`seed/`、`backend/`、`seed.py`、`requirements.txt`
- `python seed.py` 能连续执行两次且每次都成功重建数据库
- `uvicorn backend.main:app --reload` 能启动
- `/docs` 可访问
- `GET /health` 返回 200
- `GET /events` 返回空列表
- `GET /snapshot` 返回空值
- `GET /weekly-review` 返回明确的未实现响应而不是 500

## 关联文档

- 详细项目背景：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_PROJECT_BRIEF_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_PROJECT_BRIEF_CN.md)
- MVP 任务拆分：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_MVP_TASK_BREAKDOWN_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_MVP_TASK_BREAKDOWN_CN.md)
- 术语文档：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_GLOSSARY_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_GLOSSARY_CN.md)
- 字段字典：[0.0.1 D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_FIELD_DICTIONARY_CN.md](./0.0.1%20D0/NEGENTROPY_ENGINE_DOCS_CN/NEGENTROPY_ENGINE_FIELD_DICTIONARY_CN.md)

## 对开发者 / Agent 的约束

- 优先完成 MVP 闭环，不擅自扩功能
- 需求不清晰时，优先选择最保守、最小实现
- 保持命名清晰、schema 可扩展、注释说明业务语义
- 不要默认加入登录、同步、推荐、预测、复杂编排等系统
- 下一轮从 `T3` 开始时，再实现事件写入与双字段兼容，不在本轮提前埋复杂逻辑

一句话提醒：

> 这个项目的核心不是“做一个看起来很强的系统”，而是把个人负熵框架压缩成一个可记录、可更新、可复盘、可快照的本地运行内核。
