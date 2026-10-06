# P0 Architecture Baseline

## 系统边界

`Training Core` 是唯一的训练流程控制者。前端只负责交互和状态展示；LLM、ASR、朗读分析和素材来源均通过 adapter 接入。

```text
React/Vite UI
    |
FastAPI API
    |
Training Core ---- adapters (speech / llm / material)
    |
SQLite + local files
```

## 模块所有权

- `backend/app/core/`: 领域模型、状态机和确定性训练规则
- `backend/app/db/`: SQLite 连接、schema 和持久化实现
- `backend/app/api/`: HTTP API 与请求响应模型
- `backend/app/adapters/`: 可替换的外部能力实现（`speech` = 本地 ASR、`audio` = 确定性朗读分析、`voa_material` / `web_material` / `bilibili_material` = 素材源）；LLM 未接入，训练规则全部为确定性实现（Spec 2.1）
- `backend/app/preprocess/`: 预置素材校验、对齐、切句和分 Part
- `frontend/src/`: 页面、训练交互、音频录制与 API 调用
- `backend/tests/`: 后端和领域测试

## 阶段 1 决策

当前实现提供确定性的训练状态机、预置素材预处理、听写提交校验和事件 API。`adapters/` 已是可替换的实现层：本地 ASR（faster-whisper）、朗读音频分析（时长/停顿/RMS）、素材源（VOA / BBC / Bilibili）均已接入并参与主链路。**仍未接入**的能力只有两项，不得描述为已具备：LLM 生成（文稿重组、提示生成），以及 ASR 音素级对比（重音维度当前是 RMS 简化代理，阈值待校准）。

## P2 最小服务

- `LearningTimeService` 将显式结束的活动区间写入 `training_time_logs`，并更新 `learning_stats`。
- `WeeklyAssessmentService` 保存周测听写分数、朗读维度和 gate 结果；必测项未完成或失败时进入 `REINFORCEMENT_REQUIRED`。
- 全篇朗读接口只保存评分结果，不自行冒充 ASR 分析；语速与停顿由本地确定性音频分析（`WaveAudioAnalyzer`）产出，重音维度为 RMS 简化代理、阈值待校准；音素级对比仍需 speech adapter 后续实现。
- 素材搜索当前查询 SQLite 中已导入的本地素材；外部搜索结果必须通过 `MaterialProvider` 接入并经过预处理后才能进入训练状态机。
