# LLA 项目现状确认与优化建议

**日期：** 2026-10-06
**工作目录：** `E:\Software\LLA-master\LLA-master`
**结论：** 工程可运行、测试全绿；但**版本控制基线缺失**为最高优先级风险，另有 3 项可复现性/质量门缺口。

---

## 1. 位置确认

| 项 | 结果 |
|---|---|
| 目标目录 | `E:\Software\LLA-master\LLA-master` |
| 目录性质 | ✅ 真实项目根（含 `backend/`、`frontend/`、`data/`、`docs/`、`.venv/`） |
| 上层目录 | `E:\Software\LLA-master\` 为外层包裹目录，仅含 `.workbuddy/`、`.pytest_cache/`、`tools/`、`LLA-master/` |
| git 仓库 | ❌ **不存在**（`LLA-master/LLA-master` 与其父目录均无 `.git`） |

> 注意：`docs/engineering-constraints.md` 规定标准仓库根为 `D:\CODEX\LLA`，并要求每次开发/验收前 `git status` 必须 clean、交付必须绑定 commit SHA。**当前环境与该约束完全不符**：路径已变、且无 git 仓库，无法产出 HEAD SHA。

---

## 2. 工作内容确认（现状盘点）

### 2.1 项目定位

P0→P2 全阶段**本地优先**语言训练工作台。React + Vite 前端、FastAPI 后端、SQLite 存储，单进程运行（后端托管 `frontend/dist`）。

### 2.2 代码规模

| 部分 | 规模 |
|---|---|
| 后端业务代码 | ~6,772 行（`core/` + `api/` + `adapters/`） |
| 前端源码 | ~2,268 行（含 `styles.css` 259 行） |
| API 端点 | 58 个（`backend/app/api/routes.py` 734 行） |
| 后端测试 | 27 个测试文件 |
| 文档 | 9 份 md + 5 张截图 |

最大单文件：`api/routes.py`(734) > `core/video_import.py`(582) > `core/memory_deepening.py`(508) > `src/App.jsx`(550)。

### 2.3 已实现能力（代码可验证）

- **P0 训练核心**：状态机、盲听→理解检查→逐句听写（播放计数/占位/提示/Reveal/Diff）、二次复听、朗读评分三维（语速/停顿/重音）、Crash/Resume、学习时长周窗口聚合。
- **P1**：候选素材管线（质量三档 + Transcript 校验 + 幂等 prepare）、难度升级（8 周 PASS → 提示确认 → 单级推进）。
- **P2**：只读仪表盘、听写记忆深化（四层对象）、难度历史（13 类不可变事件 + 降级流程）。
- **素材获取**：VOA / BBC / Bilibili 三 Provider；URL 视频导入（yt-dlp → ffmpeg → faster-whisper 时间戳对齐）；`preset-002`《The Story of Rain》166 句预置素材。

### 2.4 运行环境就绪情况（已实测）

| 检查项 | 结果 |
|---|---|
| `.venv\Scripts\python.exe` | ✅ 存在 |
| `frontend/dist/index.html` + assets | ✅ 已构建（2026-10-06 14:48） |
| `data/language_training.sqlite3` | ✅ 340 KB |
| `tools/ffmpeg/bin/ffmpeg.exe` | ✅ 便携版 |
| `tools/models/faster-whisper-base/model.bin` | ✅ 145 MB，可离线推理 |
| 语音链路依赖 | ✅ faster-whisper 1.2.1 / yt-dlp 2026.8.19 / av 19.0.1 / onnxruntime 1.30.0 |
| **后端测试** | ✅ **128 passed, 1 warning, 76.53s** |

> **实测与文档不一致：** `README.md` 与 `P0_ACCEPTANCE_REPORT.md` 均记录「62 passed」，实际已是 **128 passed**（P1/P2 新增测试未回写文档）。

---

## 3. 关键发现（按严重度）

### 🔴 P0 — 阻塞级

**F1. 无 git 仓库，验收基线不可追溯**
`.gitignore` 存在但从未 `git init`。这直接违反 `docs/engineering-constraints.md` §2/§3（必须 clean + 绑定 SHA），也是该文档 §5 记载的历史事故（commit 错位导致「已实现/未实现」判断失真）的同类风险。当前任何改动都无法回滚、无法比对。

**F2. `tools/` 444 MB 未纳入 `.gitignore`**
`.gitignore` 忽略了 `.venv/`、`node_modules/`、`dist/`，但**未忽略 `tools/`**。其中仅 ffmpeg 三个 exe 就 317 MB。一旦 `git init && git add .`，仓库将被二进制撑爆。

### 🟠 P1 — 高优先级

**F3. `requirements.txt` 不完整，环境无法复现**
仅 4 行（fastapi / uvicorn / pytest / httpx），而**视频导入链路实际依赖 faster-whisper、yt-dlp、numpy、av、onnxruntime**——这些只在当前 `.venv` 里手工装过。换机 `pip install -r requirements.txt` 后，「URL 导入」功能必崩。

**F4. lint / typecheck 仍未接入（P0 遗留限制 #5 未闭环）**
`pyproject.toml` 已预置 `[tool.ruff]` 配置（line-length 100 / py312），但 venv 内 `ruff`、`mypy` 均未安装。静态检查零覆盖。

**F5. 文档落后于实现**
- 测试数 62 → 实际 128；
- `docs/architecture.md` 仍把 adapters 描述为「骨架、供应商未接入」，实际 VOA/BBC/Bilibili/ASR/ffmpeg 均已落地；
- `docs/engineering-constraints.md` 的仓库根 `D:\CODEX\LLA` 已失效。

### 🟡 P2 — 中优先级

**F6. `Settings.whisper_model_dir` 是死配置**
`config.py:51` 声明该字段、`media_tools.py:94` 消费它，但 `from_env()` **从未读取 `LTA_WHISPER_MODEL_DIR`**，永远为空。目前靠 `resolve_whisper_model()` 回退到 `tools/models/faster-whisper-{size}` 才没暴露问题——一旦用户想自定义模型目录会静默失效。

**F7. 双启动脚本并存**
`start.bat`（含 Vite dev server，有 Windows 崩溃风险）与 `start-local.bat`（单进程，推荐）并存，容易误用。

**F8. 构建产物与忽略规则冲突**
`.gitignore` 的 `dist/` 会忽略 `frontend/dist/`，但单进程运行**强依赖**该目录。虽然 `start-local.bat` 会在缺失时自动构建，属于「用脚本兜底掩盖了配置不一致」。

**F9. 仓库内测试残留**
`backend/tests/tmp-f5/test.sqlite3` 是 `test_p1_critical_fixes.py:244` 的运行残留，未被忽略规则覆盖（`*.sqlite3` 只匹配根目录外的任意层级其实可以匹配，但它属于污染源，宜加入忽略/清理）。

**F10. `.env.example` 缺失**
`.gitignore` 保留 `!.env.example` 例外，但文件不存在——`Settings.from_env()` 支持 24 个 `LTA_*` 变量却无任何样例文件，用户无从发现可配置项。

### 🔵 P3 — 改善项

**F11. 前端 `App.jsx` 550 行、无路由**
`view` 状态手工切换 6 个面板，随功能增长将持续膨胀；无代码分割，单个 bundle 250 KB。
**F12. 前端零测试**，且无 lint 配置（无 eslint/prettier）。
**F13. 根目录遗留 `.pytest_cache/`**（父目录 `E:\Software\LLA-master\.pytest_cache` 也有一份），属共享工作区污染。

---

## 4. 优化建议

### 阶段一：工程基线（建议今天就做，约 30 分钟）

1. **`git init` 并建立首个基线提交**
   ```bash
   cd /e/Software/LLA-master/LLA-master
   git init
   git add -A
   git commit -m "chore: baseline snapshot (P0-P2, tests 128 passed)"
   git rev-parse HEAD   # 记录 SHA，后续验收绑定
   ```
2. **修正 `.gitignore`**：新增 `tools/`、`backend/tests/tmp-f5/`、`.pytest_cache/`（含父级）；确认 `frontend/dist/` 的取舍——**建议保留忽略 + 明确「运行前必须 build」**，而非提交 250 KB 产物。
3. **同步 `docs/engineering-constraints.md`**：仓库根改为 `E:\Software\LLA-master\LLA-master`，并保留「必须绑定 SHA」硬约束。

### 阶段二：可复现性与质量门（建议本周）

4. **拆分 `requirements.txt`**
   - `requirements.txt`：运行必需（fastapi、uvicorn[standard]、httpx、numpy）
   - `requirements-import.txt`：重依赖（faster-whisper、yt-dlp、av、onnxruntime）
   - 或统一放一份并加注释分组；**用 `pip freeze` 的版本区间回填**，保证换机可复现。
5. **接入静态检查**：`pip install ruff mypy` → `ruff check backend` + `mypy backend/app`，先以「报警不阻断」接入，再逐步收紧；顺手清理现有告警即可关闭 P0 遗留限制 #5。
6. **补 `.env.example`**：枚举 `LTA_*` 变量并标注默认值；同时修复 F6，让 `from_env()` 读取 `LTA_WHISPER_MODEL_DIR`（一行修复）。
7. **CI 化（可选）**：一个 `scripts/check.ps1` 串起 `pytest → ruff → npm run build`，本地一键复现验收。

### 阶段三：结构性优化（按需推进）

8. **前端拆分**：引入 `react-router` 或至少把 `App.jsx` 的 6 个面板抽成页面级组件 + `lib/api/` 模块；配合 `React.lazy` 做路由级代码分割，`index-*.js` 可显著瘦身。
9. **前端质量**：接入 ESLint + Prettier，为 `api.js`/`wavRecorder.js`/听写判分逻辑补 Vitest 单测。
10. **文档收敛**：`README.md` 测试数、`docs/architecture.md` 适配器描述同步到实现；把 5 份阶段文档合并为「当前态 + 变更日志」，避免累计漂移。
11. **启动脚本归一**：删除或重命名 `start.bat` 为 `start-dev.bat` 并加风险提示，默认入口只保留 `start-local.bat`。

---

## 5. 执行优先级一览

| 优先级 | 项 | 影响 | 成本 |
|---|---|---|---|
| 🔴 P0 | git init + 基线提交（F1） | 验收可追溯、可回滚 | 5 min |
| 🔴 P0 | `.gitignore` 补 `tools/`（F2） | 避免 444 MB 入库 | 2 min |
| 🟠 P1 | `requirements.txt` 补全（F3） | 换机可复现 | 15 min |
| 🟠 P1 | ruff + mypy 接入（F4） | 关闭遗留限制 #5 | 30 min |
| 🟠 P1 | 文档同步（F5） | 决策依据不失真 | 20 min |
| 🟡 P2 | `whisper_model_dir` env 修复（F6） | 消除静默失效 | 5 min |
| 🟡 P2 | `.env.example`（F10） | 配置可发现 | 15 min |
| 🟡 P2 | 启动脚本归一（F7） | 避免误用崩溃路径 | 10 min |
| 🔵 P3 | 前端拆分 + 前端测试（F11/F12） | 长期可维护性 | 1–2 天 |

---

**一句话总结：** 功能面（P0–P2）实现完整且 128 项测试全绿，可以正常运行；**当前最大的风险不是代码，而是「没有 git 仓库」——它让 engineering-constraints 里最核心的 SHA 绑定约束彻底失效**，应作为第一件事处理。
