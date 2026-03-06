# 负熵引擎项目概述（详细版）

## 0. 文档定位

本文档是“负熵引擎”的详细背景说明，服务于开发者、代码代理与项目协作者。

它的职责是：

- 解释项目的真实目标和冻结边界
- 说明核心概念、建模语义和工程约束
- 补充 README 未展开的阶段设计和系统逻辑

它不再承担项目主入口职责。项目入口请优先查看仓库根目录 [README.md](../../README.md)。

- `README.md` 负责开发入口、仓库结构、启动方式、当前接口边界和阶段总览
- 本文档负责完整背景、建模理解、冻结规则和阶段演化逻辑

## 1. 一句话定义

负熵引擎是一个本地可运行的个人负熵管理 MVP，目标是将“记录事件 -> 更新节点/能量 -> 生成周复盘 -> 生成快照”闭环工程化。

它不是：

- 泛化超级 Agent
- 全自动人生决策系统
- 先做云端/多端同步的大系统
- 优先做复杂预测建模的研究项目

## 2. 当前阶段定义（D0 / MVP）

当前阶段是 **D0 冻结阶段**。其含义是：

- 核心理论和建模框架已冻结
- MVP 范围已冻结
- 关键节点和优先级已冻结
- 初始数据结构方向已冻结

当前已经落地的工程能力：

- SQLite schema 初始化
- D0 基线 seed 导入
- 事件录入与查询
- 自然语言事件解析 -> 结构化草稿 -> 用户确认 -> 写库
- 关键节点查询与更新
- 周复盘生成与读取
- 快照生成与读取

当前尚未完成的部分：

- 最小前端壳层与联调
- V1.5 参数识别分析任务
- V2 策略与调度能力

因此，当前最重要的任务不是继续扩散需求，而是把最小闭环做稳。

## 3. 系统阶段架构

系统整体架构分为三个层级：

```text
Runtime Layer (V1)
Analytics Layer (V1.5)
Decision Layer (V2)
```

### 3.1 Runtime Layer（V1）

V1 负责系统的基础运行，解决“数据问题”：

- 记录事件（events）
- 更新系统状态（energy、progress）
- 生成快照（snapshots）
- 输出复盘（weekly review）

这一层是系统的核心运行逻辑，也是当前仓库已经实现的主要范围。

### 3.2 Analytics Layer（V1.5）

V1.5 是分析层，也可称为参数识别阶段。它负责从 V1 真实运行数据中识别统计关系和经验规则，解决“模型问题”。

这一层只读取运行数据，不直接修改系统状态，也不执行决策行为。

### 3.3 Decision Layer（V2）

V2 是决策层。它读取 V1.5 生成的参数，用于：

- 行为策略生成
- Channel 权重调整
- 任务调度建议
- 风险预警

V2 的能力依赖 V1.5 已经识别出的规则，不是当前 MVP 范围。

## 4. V1.5 阶段说明（Analytics / Parameter Identification Phase）

在第一代 MVP 系统运行过程中，引入一个 **Analytics Layer（分析层）**，用于对系统运行产生的数据进行统计分析与经验公式拟合。该阶段称为 **V1.5（参数识别阶段）**。

V1.5 的目的不是增加新的系统能力，而是通过对真实运行数据进行结构化分析，从数据中提取稳定的统计关系和经验规则，为第二代系统（V2）的策略与决策模块提供可靠参数基础。

换句话说：

**V1 负责采集数据，V1.5 负责从数据中识别规律，V2 才负责基于这些规律做决策。**

### 4.1 V1.5 的核心目标

V1.5 阶段的核心目标是将系统日志数据转换为可计算的行为模型参数。通过对事件、能量变化、节点推进等数据的统计分析，逐步推导出系统运行中的经验公式与规则。

这些规则主要包括：

1. **能量变化模型（Energy Model）**
   识别不同类型行为对 `mind_energy` 和 `body_energy` 的平均影响。
2. **节点推进模型（Progress Model）**
   识别哪些行为会有效推进关键节点（Key Nodes）或技能发展。
3. **Channel 贡献模型（Channel Contribution Model）**
   计算不同 Channel 在当前阶段对系统目标推进的实际贡献。
4. **风险模型（Risk Model）**
   识别哪些行为组合会提高系统进入 `overload` 或 `low-output` 状态的概率。
5. **阶段判定规则（Phase Transition Rules）**
   根据系统运行状态，推导 Phase（例如 `reconstruction`、`stabilizing`）的客观判定条件。

### 4.2 V1.5 在系统架构中的位置

系统整体架构分为三个层级：

```text
Runtime Layer (V1)
Analytics Layer (V1.5)
Decision Layer (V2)
```

#### Runtime Layer（V1）

负责系统的基础运行：

- 记录事件（events）
- 更新系统状态（energy、progress）
- 生成快照（snapshots）
- 输出复盘（weekly review）

这一层是系统的核心运行逻辑。

#### Analytics Layer（V1.5）

Analytics Layer 只读取系统运行数据，对其进行统计分析与模型拟合。

这一层 **不会直接修改系统状态，也不会执行任何决策行为**。

Analytics Layer 的主要职责包括：

- 数据清洗与特征构建
- 统计分布分析
- 行为模式识别
- 经验公式拟合
- 参数表生成

分析结果以参数形式保存，例如：

```text
energy_rules
progress_rules
channel_scores
risk_rules
phase_rules
```

这些参数将作为 V2 决策模块的输入。

#### Decision Layer（V2）

第二代系统将在此基础上实现策略与调度功能。

Decision Layer 将读取 Analytics Layer 生成的参数，进行：

- 行为策略生成
- Channel 权重调整
- 任务调度建议
- 风险预警

因此，V2 的决策能力依赖于 V1.5 阶段提取出的规则和参数。

### 4.3 V1.5 的运行方式

V1.5 的分析过程以 **周期性数据分析任务** 的形式运行，例如：

- 每日更新统计指标
- 每周更新行为模型参数
- 每月更新阶段判定规则

Analytics Layer 的典型数据处理流程如下：

```text
events
   ↓
feature engineering
   ↓
statistical analysis
   ↓
parameter estimation
   ↓
analytics_rules
```

在此过程中，系统不会修改任何历史数据或当前状态。

### 4.4 V1.5 的输出形式

Analytics Layer 的输出主要是 **参数化规则表**，例如：

#### `energy_rules`

| event_type | expected_mind_delta | expected_body_delta |
| --- | ---: | ---: |
| deep_work | -0.4 | -0.1 |
| exercise | +0.2 | -0.5 |
| social_conflict | -0.8 | -0.2 |

#### `progress_rules`

| event_type | node_type | expected_progress |
| --- | --- | ---: |
| deep_work | research_node | 0.02 |
| practice | skill_node | 0.03 |

#### `channel_scores`

| channel | contribution_score |
| --- | ---: |
| study | 0.42 |
| career | 0.31 |
| health | 0.18 |

#### `risk_rules`

| condition | overload_probability |
| --- | ---: |
| mind_energy < 2 for 3 days | 0.63 |

### 4.5 V1.5 的原则

V1.5 的设计遵循三个原则：

1. **Analytics Layer 不改变系统状态**  
   分析模块只读取数据，不修改任何系统变量。
2. **所有规则来自真实运行数据**  
   规则必须基于系统日志进行统计推导，而不是人为假设。
3. **优先生成可解释规则**  
   优先使用简单统计模型和经验公式，而不是复杂黑箱模型。

### 4.6 V1.5 的意义

V1.5 的存在使系统从单纯的数据记录工具升级为 **可学习的行为系统**。

通过持续分析运行数据，系统能够逐步识别：

- 哪些行为真正有效
- 哪些投入具有最高回报
- 哪些模式容易导致系统失稳

这些发现将为第二代系统的策略和调度能力提供基础。

### 4.7 阶段关系总结

系统演化路径如下：

```text
V1   -> 数据采集
V1.5 -> 参数识别
V2   -> 策略执行
```

其中：

- V1 解决 **数据问题**
- V1.5 解决 **模型问题**
- V2 解决 **决策问题**

## 5. MVP 目标与非目标

### 5.1 MVP 目标

当前 D0 / MVP 只要求打通以下闭环：

1. 初始化系统
2. seed D0 模型
3. 记录事件（含 delta）
4. 更新关键节点进度
5. 生成周复盘 markdown
6. 生成快照

### 5.2 明确非目标

以下能力不是当前阶段优先项：

- AWDMS 自动采集
- HMM / KMeans 等复杂统计建模
- 自动化策略编排
- 云端同步
- 多端同步
- 复杂推荐系统
- 自动人生规划生成
- 黑箱预测模型

## 6. 核心建模总览

系统采用五大模块建模：

- Body
- Mind
- Spirit
- Vocation
- Channel

但它们不是平级并列关系，而是分层结构：

- **Body / Mind = 基础层**
- **Spirit / Vocation = 高维实现层**
- **Channel = 更高维决策性变量**

关键含义：

- Body / Mind 负责“能量池 + 能力层”
- Spirit / Vocation 负责“目标、方向、节点、实现”
- Channel 决定资源投放方向、输出方向和优先级

## 7. 冻结规则

### 7.1 Level

- `Level` 只对应 `Body / Mind`
- 当前 D0 使用整数等级
- 后期允许小数，但当前不追求

### 7.2 Skill Level

Skill Level 是目标导向达成度，不是抽象熟练度。

- `0` = 无法达成
- `3` = 勉强达成
- `5` = 完美达成

技能结构使用树形关系，建议通过 `parent_id` 表达层级。

### 7.3 Phase

`Phase` 用于描述系统阶段，而不是短期情绪。

默认 Phase 枚举：

- `reconstruction`
- `stabilizing`
- `exploration`
- `expansion`
- `overload`
- `recovery`

当前 phase：

- `reconstruction`

### 7.4 Traits

Traits 是系统化标签，不是随意备注。

每个 trait 至少应有：

- `priority`
- `confidence`
- `stability`（`fixed` / `evolving`）

## 8. 当前关键节点与优先级

### 8.1 Spirit 关键节点

按优先级排序：

1. 构建一套自己的决策模型
2. 完善处理家庭关系的机制

以下目标已从 D0 Spirit 节点中移除：

- 长期异性伴侣

原因：

- 当前阶段不应让其占用 D0 核心资源
- 可后置到 `exploration` / `expansion`

### 8.2 Vocation 关键节点

当前采用 **A 策略：稳态复利型，门槛优先，冲刺后置**。

门槛节点：

1. 全国大学生数学竞赛：获得国赛资格
2. 论文写作：完成一轮完整流程

后置冲刺节点：

3. 数学建模比赛：国赛奖
4. 力学竞赛：国赛奖

### 8.3 Channel 优先级

#### priority 5

- 负熵引擎 / 个人助手（RAG / LLM 工程）
- 考研（学硕方向）

#### priority 4

- 身体管理
- 数学建模能力培养
- 学科能力（力学 / 高数）

#### priority 3

- IR / 文献检索系统维护
- 具身智能仿真
- 高中物理授课负荷

## 9. 数据源策略

当前数据源策略已经明确：

- SQLite 是主数据源
- `init_self_model.json` 只用于 seed
- D0 阶段不引入双真源混用
- 结构设计以可扩展为前提，但不提前做复杂分布式设计

## 10. 页面与 API 边界

### 10.1 页面范围

最小前端冻结为 3 个页面：

1. 今日记录
2. 节点进度
3. 周复盘

### 10.2 当前 API 范围

当前已实现或冻结的核心接口：

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

## 11. 编程工具执行协议

当你是 Codex / VS Code Agent / Claude Code 等编程工具时，请遵守以下规则：

### 11.1 首要目标

优先帮助项目**做透 MVP 闭环**，而不是扩展功能。

### 11.2 不要擅自做的事

不要默认加入：

- 用户系统
- 登录注册
- 云端同步
- 微服务拆分
- 向量数据库
- 自动总结 Agent 编排
- 复杂前端膨胀
- 预测模型
- 推荐系统

### 11.3 推荐策略

需求不明确时，优先采用以下策略：

1. 选择最保守、最小实现
2. 保证可运行
3. 保持命名清晰
4. 保持 schema 可扩展
5. 保留必要注释解释业务语义
6. 优先遵守 D0 冻结规则

## 12. 当前最合理的工程优先顺序

推荐顺序如下：

1. 统一数据模型与数据库 schema
2. 完成 FastAPI 最小接口
3. 完成 seed / init 流程
4. 完成事件录入与 delta 更新
5. 完成 key nodes 展示与修改
6. 完成 weekly review 生成
7. 完成 snapshots 生成
8. 补最小前端页面
9. 在 V1 稳定运行后启动 V1.5 参数识别任务
10. 在 V1.5 有稳定参数后再进入 V2

## 13. 成功标准（D0 完成标准）

D0 / MVP 可视为完成，当且仅当至少满足：

- 能初始化一个 D0 self model
- 能录入一条事件
- 能写入对应 delta
- 能更新至少一个关键节点进度
- 能生成一份周复盘 markdown
- 能生成一份 snapshot
- 全流程可在本地跑通

## 14. 一句话提醒

这个项目的核心不是“做一个看起来很强的系统”，而是：

> 把个人负熵框架压缩成一个可记录、可更新、可复盘、可快照，并能在后续逐步演化到参数识别与策略层的本地运行内核。
