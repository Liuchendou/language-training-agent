# Language Training Agent

> **状态：`p0-accepted`**（2026-08-26，P0 ACCEPTED WITH KNOWN LIMITATIONS，详见 [P0_ACCEPTANCE_REPORT.md](P0_ACCEPTANCE_REPORT.md)）

P0 本地优先的语言训练工作区。当前已具备素材预处理、可恢复训练状态机、听写提交校验，以及盲听/理解检查/Part 完成/二次复听/朗读骨架 API。

## 技术边界

- 前端：React + Vite
- 后端：FastAPI
- 数据库：SQLite
- 文件：本地素材、录音和预处理产物
- AI 能力：通过 adapters 接入，不由 Training Core 直接绑定供应商

## 本地启动

**新机器首次使用**：双击根目录的 `setup.bat` 做一次性环境准备（Python 依赖 → ffmpeg 与语音模型 → 前端构建，全部幂等可重跑）。完整说明见 [docs/transfer-guide.md](docs/transfer-guide.md)。

**日常启动**：双击根目录的 `start-local.bat`——单进程启动（后端 8000 端口同时托管已构建的 `frontend/dist`），自动等待健康检查后打开浏览器，无需 Vite dev server。

以下为手动步骤（等价于上面两个脚本所做的事）：

1. 创建虚拟环境并安装后端依赖：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

   `requirements.txt` 是**运行必需**依赖（Web 服务 + URL 视频导入链路）。开发与验收另需测试/静态检查工具：

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   ```

2. 启动后端：

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
   ```

3. 构建前端 —— **这是启动的硬前提**：后端在启动时挂载 `frontend/dist` 来托管 Web 界面，而该目录是构建产物、不随仓库分发（`.gitignore` 已忽略）。缺失时后端仍会启动并继续服务 `/api/*`，但会打印明确告警、根路径 404。Windows 上 Vite dev server 有崩溃风险，故默认不使用：

   ```powershell
   cd frontend
   npm install
   npm run build
   ```

4. 补齐外部依赖（ffmpeg 与语音模型）—— **两者都不随仓库分发**（整个 `tools/` 约 444 MB，已被 `.gitignore` 忽略）。缺失时服务照常启动，但相关功能不可用：

   | 依赖 | 缺失后果 | 影响范围 |
   |---|---|---|
   | `ffmpeg` / `ffprobe` | 下载后的转码步骤直接失败 | 「贴链接导入」与自动搜索素材 |
   | faster-whisper 模型 | 首次转写会尝试从 Hugging Face 下载，网络受限时超时 | 同上（生成句级时间戳） |

   **ffmpeg** —— 三种方式任选其一，代码的查找顺序就是 `LTA_FFMPEG` → `PATH` → 项目内 `tools/ffmpeg/bin/`（见 `backend/app/core/media_tools.py`）：

   - 装进 PATH：`winget install "FFmpeg (Essentials Build)"`（也可用 `choco install ffmpeg` / `scoop install ffmpeg-essentials`）。
   - 便携版放进项目：从 gyan.dev 的 builds 页（<https://www.gyan.dev/ffmpeg/builds/>）下载 `ffmpeg-release-essentials.zip`，把解压后 `bin/` 里的 `ffmpeg.exe`、`ffprobe.exe`、`ffplay.exe` 放到 `tools/ffmpeg/bin/`。本机实测版本串为 `ffmpeg version 9.0.2-essentials_build-www.gyan.dev`。
   - 已装在别处：设 `LTA_FFMPEG` 指向 `ffmpeg.exe` 的绝对路径。

   **语音模型** —— 目录名跟着 `LTA_WHISPER_MODEL` 走（默认 `base`），即 `tools/models/faster-whisper-base/`，内容需含 `config.json` + `model.bin` + `tokenizer.json` + `vocabulary.txt`；也可以用 `LTA_WHISPER_MODEL_DIR` 指向任意位置的同类目录（该项优先于项目内副本）。**不提供也能跑**：会退回按模型名自动下载，可用 `LTA_HF_ENDPOINT` 指定镜像（默认已指向 `hf-mirror.com`）。

## 配置

全部可配置项见根目录的 `.env.example`（28 个 `LTA_*` 变量，每项都标注了内置默认值）。

⚠️ 应用**不会自动读取** `.env` 文件——代码只读进程环境变量。要让配置文件生效，需显式传入：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --env-file .env
```

`--env-file` 依赖 `python-dotenv`，已随 `uvicorn[standard]` 一并安装；也可以直接在 shell 里设置环境变量后再启动。

## 部署到另一台电脑

**逐步操作 + 故障排查见 [docs/transfer-guide.md](docs/transfer-guide.md)。** 要点如下。

仓库里只有源码（136 个文件）。`.venv/`、`node_modules/`、`frontend/dist/`、`tools/`、`data/*.sqlite3` 都是本机构建或运行时产物，不在版本库内。新机器上需要：

1. 装好 **Python ≥ 3.12**（下限由 `numpy==2.5.3` 声明的 `Requires-Python` 决定，是已装依赖中最高的一条；本机实测 3.13.9）与 **Node.js**——分别用于后端运行与前端构建。
2. 双击 `setup.bat`：重建 `.venv`、装后端依赖、下载 ffmpeg 与语音模型、构建前端。**不要直接拷贝 `.venv/`**（其内部脚本记录的是原机器的绝对路径）。注意 ffmpeg 一项的下载速度可能很慢，替代路径见指南 4.2 节。
3. 双击 `start-local.bat` 启动，再自检环境：`GET /api/materials/import-capabilities`。本机实测返回：

   ```json
   {"ffmpeg":true,"yt_dlp":true,"faster_whisper":true,"problems":[],"whisper_model":"...\\tools\\models\\faster-whisper-base","whisper_model_local":true,"ready":true}
   ```

   `ready` 为 `false` 时读 `problems` 数组，里面逐条写明缺哪一项、怎么补；`whisper_model_local` 为 `false` 表示模型还没落到本地，首次识别会联网下载。

**平台差异**：`start-local.bat` 与 `tools/ffmpeg/bin/*.exe` 是 Windows 专用。macOS / Linux 上需自行安装 ffmpeg（会命中 `PATH` 分支），并改用上面「本地启动」的手动命令。

**数据隔离**：`data/language_training.sqlite3` 不在仓库内，新机器首次启动会自动建空库，不会带入原机器的训练与素材记录。

**部署到公网（让手机浏览器访问同一套后端）**：**尚未执行**。方案对比、改造清单与开工前待确认事项见 [docs/cloud-backend-plan.md](docs/cloud-backend-plan.md)。

## 质量门

```powershell
# 后端测试
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q

# 后端静态检查（规则集锁定在 pyproject.toml 的 [tool.ruff.lint]）
.\.venv\Scripts\python.exe -m ruff check backend

# 后端类型检查（当前为「报警不阻断」，见下）
.\.venv\Scripts\python.exe -m mypy

# 前端静态检查与测试
cd frontend
npm run lint
npm test
```

- **ruff**：`backend` 全量零告警（`E4/E7/E9/F/I/UP/B/C4/SIM/RUF`，规则集显式锁定，避免随 ruff 版本漂移）。
- **mypy**：已接入 `backend/app`（40 个源文件），但存量类型标注较松（大量 `dict[str, object]`），2026-10-06 基线为 **43 条告警**（`arg-type` 13 / `attr-defined` 9 / `return-value` 5 / `assignment` 5，其余为 `index`、`var-annotated`、`union-attr` 等），按「报警不阻断」处理，逐步收紧。
- **ESLint**：`frontend` 全量零告警。注意 ESLint 已是 **10.x**，只支持 flat config（`frontend/eslint.config.js`），且 `eslint-plugin-react-hooks` 的 flat 预设挂在 `configs.flat` 下（`configs.recommended` 是给已废弃的 eslintrc 用的）。少数 `react-hooks/exhaustive-deps` 与 `set-state-in-effect` 采用**精确抑制并就地注明原因**——把依赖补全会改变触发频率甚至造成请求循环，属主动决策而非遗漏。
- **Vitest**：26 个用例（`readJson`/`detailOf` 12 个、`encodeWav` 8 个、App 冒烟 6 个）。默认 `node` 环境（纯逻辑用例更快），需要 DOM 的用例在文件顶部用 `// @vitest-environment jsdom` 单独声明。App 冒烟用例同时守护 P3 拆分后的组件装配与 `React.lazy` 按需加载，详见「前端结构」。

## 当前阶段验收

- 后端 `/api/health` 返回 `{"status":"ok"}`。
- SQLite 数据库可以初始化，并为旧听写表补齐播放次数和 Memory 目标字段。
- 听写只能在已解锁的 Part 中按句子顺序提交；Part 未完成不能推进。
- 盲听、理解检查、Part 完成、二次复听和朗读骨架接口可驱动主状态机。
- “声音训练素材”入口支持本地素材搜索、详情进入、文本导入和音频播放；当前搜索范围是本地已导入素材。
- 学习时长日志会汇总到 session、weekly 和 total 统计；周测按听写与朗读必测项决定通过或强化。
- 朗读全篇接口已支持语速、停顿、重音和时长结果字段，具体 ASR/朗读分析仍通过 adapter 接入。
- 听写上下文接口不返回句子文本（盲听边界在服务端），Reveal 后才返回原文；Reveal 不降低逐字正确通过标准。
- 前端可完成 L0 听力闭环：首页（进行中素材优先）/素材搜索导入/训练页（盲听→理解检查→逐句听写：播放计数、占位、提示、Reveal、Diff 色块→二次复听可看原文）。
- 朗读评分闭环：本地确定性音频分析（时长/停顿/RMS 能量起伏，重音为简化代理待校准）→ Rule Engine 三维独立 PASS/CLOSE/FAIL（阈值经 Settings 参数化）→ 评分落库后才可完成 Part / 全文验收；前端支持浏览器录音（WAV 编码）与段尾三维反馈。
- 学习时长按周窗口聚合（LTA_WEEKLY_WINDOW：calendar 自然周 / rolling7 近 7 天，时间可注入测试），activity_type 限定 Spec 13.1 活动集合。
- 后端测试（133 个，含 acceptance 黑盒、并发、跨天恢复、朗读评分、周窗口、周测闭环、异常处理）；前端 26 个单测与生产构建均通过。
- 验收复核（2026 第二轮）：真实素材 E2E（BBC 人声素材全链路至 FULLY_COMPLETED）、真实人声朗读评分（慢读 FAIL / 匹配朗读三维 PASS，pause 阈值经真实语音校准：最小停顿 500ms + 比例容差）、Targeted Retest 显式状态流（强化全对 → TARGETED_RETEST → 确认 → GATE_PASS）、盲听完成需播放到结尾（前端锁定）、强化闭环前端修复。
- **P1-1（候选素材 + 难度升级）**：候选管线（`MaterialCandidateService`）——VOA 慢速为初始 Provider，15–20 分钟硬时长区间，音频质量三档分级（Clear/Acceptable/Poor，`AudioQualityAnalyzer` 带指标/版本审计），Transcript 完整性校验（`TranscriptValidator`），最多 3 候选按质量/语速/时长排序，Poor 与缺失字段永不进入候选；候选仅以 `material_candidates` 存在，用户选择后 `prepare`（幂等键、失败可恢复）才创建正式 Material（`source_candidate_id`/`speed_stage`/`prepare_status` 关联）。难度升级（`DifficultyProgressionService`）——读 P0 周测生成幂等 `WeeklyGateRecord`，连续 8 训练周 PASS（听写 ≥80、朗读通过、无强化、周间隔容差）才 `upgrade_eligible`；提示-确认流程（UPGRADE_CONFIRMED/KEEP_CURRENT/DECIDE_LATER），KEEP/DECIDE 进入 4 周冷却，确认后仅推进一个 `speed_stage`（STAGE_1→2→3，时长等变量不变），Stage 3 封顶。P0 训练核心零改动。API：`/api/p1/material-candidates/search|prepare`、`/api/p1/difficulty/weekly-gate|profile|prompt|upgrade-decision`。
- **P2（长期仪表盘 / 记忆深化 / 难度历史）**：只读观察与解释层，P0/P1 零改动。仪表盘（`/api/p2/dashboard`）——有效时长聚合（闭日志）、首次理解曲线（冻结映射 15/40/60/85 + raw band + 版本 + 样本数）、周测趋势（原始分与 Gate 独立展示）、朗读三维分布（不平均）、正式 streak（P1 weekly_gate_records）；时间范围/粒度可切换且响应显式返回。听写记忆深化（`/api/p2/memory*`）——四层对象（目标/出现/识别会话/聚合）、first-correct 用 listen_count（Reveal/Hint 排除）、SPELLING 与周测天然隔离、用户阈值配置（短 14 天/长 8 周/最少 3 会话/2 日期，版本化、未配置返回 UNCONFIGURED）、复习建议（默认启用、7 天频率限制、禁用/暂停/恢复/历史删除且不删原始训练）。难度历史（`/api/p2/difficulty/history*`）——13 类不可变事件（幂等事件键）、P1 流程自动接线（Gate/Streak/Eligible/Prompted/Decided/Cooldown/StageChanged）、降级流程（连续 2 周未过 → 仅建议；确认才执行、单级、8 周计数归零）、回填审计（reliability/版本/时间）。
- 预置素材：`preset-002`《The Story of Rain》——166 句原创英文、15.6 分钟慢速清晰语音（edge-tts 逐句合成 + 精确句级时间戳），按 Spec 3.1 的 15–20 分钟设定生成；三段切分优先自然语义段落边界（`natural_part_boundaries`，Spec 3.2）；生成脚本 `backend/scripts/generate_preset_material2.py` 可复现。**注意：该素材不随仓库分发**，需运行生成脚本产出；截至 2026-10-06，`data/language_training.sqlite3` 的 `materials` 表为 0 行（本地素材库为空）。
- 自动搜索素材：素材完成后（训练页「获取下一篇」或 `POST /api/materials/next`）按难度规则自动搜索并导入下一篇。**源优先级：VOA Learning English 慢速英语（标准，公版）→ BBC Learning English 6 Minute English（兜底）**；搜索条件含**音质门槛**（采样率/SNR/静音比例/时长，阈值经 Settings 配置）。管线：下载 → ffmpeg 转码 → 本地 ASR（faster-whisper）生成段级时间戳 → 文稿句子按词序列锚点对齐（未匹配句在锚点间按词数插值，时间戳单调且在音频范围内）→ 三段切分 → 发布。VOA 官方文稿由客户端 JS 加载无法服务端获取，其文稿由更高精度 ASR（small 模型）生成并标注；BBC 使用官方文稿。
- **素材可跳过**：训练页「跳过此素材，换一篇」——素材标记 SKIPPED 并从后续搜索排除，自动搜索替代素材（对应 Spec 12 训练节奏控制）。
- 难度规则（Spec 3.1/16）：档位 = 时长（short/standard/long）× 语速（slow/medium/fast）；**一次只升级一个变量**（先时长后语速）；升级由周测连续稳定通过触发（`MaterialRecommender.stable_pass_rounds`，默认 2 次），累计时长不触发；`upgrade_available` 随搜索返回。

## 前端结构

`frontend/src/` 按「状态集中在 App、视图各自成文件」划分：

- `App.jsx`：持有跨视图状态与全部 API 交互，含训练状态机 `trainingBody()`。
- `views/`：6 个视图组件。`HomeView` 静态导入（首屏），其余 5 个经 `React.lazy` 按需加载，并连同各自较重的子组件独立成 chunk。
- `viewUtils.js`：视图共享的展示层常量与纯函数（`COMPLETED_STATES` / `STATE_TEXT` / `VIEW_TITLES` / `TRAINING_MODES` / `stateText`）。独立成模块是为了避免视图反向 import App 形成循环依赖。

2026-10-06 实测构建产物（`npm run build`，拆分前为单个 250,265 字节 bundle）：

| chunk | 原始 | gzip |
|---|---|---|
| `index`（首屏） | 219.43 kB | 69.99 kB |
| `P2View` | 10.72 kB | 3.38 kB |
| `WeeklyView` | 8.24 kB | 3.00 kB |
| `CandidatesView` | 6.73 kB | 2.92 kB |
| `MaterialsView` | 6.45 kB | 2.65 kB |
| `TrainingView` | 1.40 kB | 0.74 kB |

**已知未拆干净**：`DictationPanel` 与 `ReadingPanel` 仍随首屏加载——渲染它们的 `trainingBody()` 留在 `App.jsx` 内。要彻底分开，需把训练状态机连同其状态一并迁入 `TrainingView`（属独立改动，未在本次进行）。

