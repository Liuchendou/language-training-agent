# 跨设备传输与使用指南

> 适用场景：把这套项目从**一台 Windows 电脑**搬到**另一台 Windows 电脑**并跑起来。
> 前提：目标机器**可以联网**（外部依赖由脚本自行下载）。
> 全程不需要命令行经验，两步双击即可。
> 本文所有体积、版本、接口返回均为 2026-10-06 在源机器上的实测值。

---

## 0. 一句话流程

```
拷源码  →  双击 setup.bat  →  双击 start-local.bat
```

`setup.bat` 只跑一次（约 460 MB 下载）；以后每次使用都只双击 `start-local.bat`。

---

## 1. 哪些东西要带过去，哪些不要带

仓库里**只有源码**。下面这些是本机构建或运行时产物，走 `.gitignore` 排除，**不要拷**：

| 目录 / 文件 | 本机体积 | 为什么不带 | 目标机器怎么来 |
|---|---|---|---|
| `.venv/` | 411 MB | 内部脚本记录的是**原机器的绝对路径**，跨机拷贝会失效 | `setup.bat` 自动重建 |
| `frontend/node_modules/` | 114 MB | 平台相关，且可由 lock 文件还原 | `setup.bat` 跑 `npm install` |
| `frontend/dist/` | 281 KB | 构建产物 | `setup.bat` 跑 `npm run build` |
| `tools/`（ffmpeg + 语音模型） | 444 MB | 体积大且 `ffmpeg.exe` 为 Windows 专用 | `setup.bat` 自动下载 |
| `data/language_training.sqlite3` | 416 KB | **你的训练记录与素材库**，属于个人数据 | 首次启动自动建空库 |
| `.env`（若存在） | — | 可能含个人配置 | 需要时从 `.env.example` 复制一份 |

> 结论：只需要拷**源码**（136 个文件）。其余全部由 `setup.bat` 在目标机器上自动补齐。

---

## 2. 目标机器先装两样东西

只装一次。装完建议重启一次终端/资源管理器，让 PATH 生效。

### 2.1 Python 3.12 或更新版本

- 下载：<https://www.python.org/downloads/>
- 安装时**务必勾选 `Add python.exe to PATH`**——漏勾会导致 `setup.bat` 找不到 Python。
- 为什么是 3.12：本项目的 `numpy==2.5.3` 声明 `Requires-Python: >=3.12`，它是已安装依赖里要求最高的一条（实测自包元数据）。源机器实际在用的是 Python 3.13.9。

### 2.2 Node.js（含 npm）

- 下载 LTS 版：<https://nodejs.org/en/download>
- 用途：构建前端界面 `frontend/dist`。源机器实测 Node v22.22.2 / npm 10.9.7。

### 2.3 自查（可选）

在目标机器上打开「命令提示符」逐个敲：

```bat
python --version
node --version
npm --version
```

三条都能打印出版本号，就可以进入下一步。若提示「不是内部或外部命令」，说明没装好或 PATH 没生效。

---

## 3. 拿到源码（两种方式，任选其一）

### 方式 A：从 GitHub 克隆（推荐）

```bat
git clone https://github.com/Liuchendou/language-training-agent.git
cd language-training-agent
```

优点：干净、带版本历史、以后 `git pull` 就能更新。

### 方式 B：整个文件夹拷过去

用 U 盘或共享目录拷贝，但**必须跳过第 1 节表格里的那几项**（尤其是 `.venv/` 和 `tools/`）。跳过 `tools/` 的前提是目标机器能联网。
只拷源码时，忽略 `.venv`、`node_modules`、`frontend/dist`、`tools`、`data\*.sqlite3` 即可。

---

## 4. 一键准备环境：双击 `setup.bat`

在项目根目录双击 **`setup.bat`**。窗口会自动执行 5 步。**耗时差异很大，主要取决于 ffmpeg 那一项的网速**（本机实测该项可能超过 1.5 小时，见 4.2 节；模型约 10 分钟）：

| 步骤 | 做什么 | 网络需求 |
|---|---|---|
| 1/5 | 检查 Python ≥ 3.12 与 Node.js | — |
| 2/5 | 创建虚拟环境 `.venv` | — |
| 3/5 | 安装后端依赖（`requirements.txt`） | 约 200 MB |
| 4/5 | 下载 ffmpeg 与语音模型到 `tools/` | 约 248 MB |
| 5/5 | 构建前端界面 `frontend/dist` | 依赖第 1 步的 npm |

已完成的步骤会自动跳过，**可以反复双击**，不会重复下载。

### 4.1 它把文件放到哪里

位置与后端代码的查找顺序一致（`backend/app/core/media_tools.py`）：

| 内容 | 落盘位置 | 大小 |
|---|---|---|
| `ffmpeg.exe` / `ffprobe.exe` / `ffplay.exe` | `tools\ffmpeg\bin\` | 303 MB |
| 语音模型 `faster-whisper-base` | `tools\models\faster-whisper-base\` | 142 MB |
| 前端界面 | `frontend\dist\` | 281 KB |

### 4.2 下载来源与实测速度

| 内容 | 来源 | 本机实测速度 |
|---|---|---|
| ffmpeg | `https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip`（HTTP 303 跳转后为 `ffmpeg-9.0.2-essentials_build.zip`，114,768,076 字节） | **约 30 KB/s**，完整下载需 1.5 小时以上 |
| 语音模型 | Hugging Face `Systran/faster-whisper-base`，默认端点 `https://hf-mirror.com` | 约 236 KB/s，约 10 分钟 |
| Python 包 | 默认走阿里云镜像 `https://mirrors.aliyun.com/pypi/simple/` | — |

脚本解压 ffmpeg 时只取 `bin\*.exe`，文档与 license 丢弃；模型取 `config.json`、`model.bin`、`tokenizer.json`、`vocabulary.txt`（以及仓库里若存在的 `preprocessor_config.json`）。

**ffmpeg 这一项是本指南里最慢的一步**，我也实测过替代源，结论是换不了：

- 清华 TUNA（`mirrors.tuna.tsinghua.edu.cn/github-release/`）与南大 NJU 镜像均**未收录** FFmpeg 构建（访问返回 404）；
- BtbN/FFmpeg-Builds 的 GitHub Release 资源在当前网络不可达（连接失败，curl 退出码 7）。

所以 ffmpeg 请三选一：

1. **交给脚本慢慢下**——支持断点续传，中途中断（关窗口、断网）后重跑会从已下载的字节继续，不会白下。
2. **自己下好再让脚本解压**：用浏览器或下载工具拿到那个 zip，然后
   ```bat
   .venv\Scripts\python.exe backend\scripts\prepare_assets.py --ffmpeg-archive D:\下载\ffmpeg-release-essentials.zip
   ```
   注意 `.venv` 必须先存在，所以顺序是：先跑 `setup.bat`（跑到这一步会较慢，可以 Ctrl+C 中断），或者先只做前两步再执行上面的命令。
3. **已有 ffmpeg 就直接用**：设环境变量指向 `ffmpeg.exe` 的绝对路径，脚本这一步会自动跳过（后端的查找顺序是 `LTA_FFMPEG` → PATH → `tools\ffmpeg\bin\`）。
   ```bat
   set LTA_FFMPEG=D:\tools\ffmpeg\bin\ffmpeg.exe
   ```

想换下载地址，用环境变量覆盖即可：

```bat
set LTA_FFMPEG_URL=<你的 ffmpeg 压缩包地址>
set HF_ENDPOINT=https://huggingface.co
set LTA_PIP_INDEX=
```

`HF_ENDPOINT` 会被透传给模型下载步骤；`LTA_PIP_INDEX` 设为空字符串即改用官方 PyPI。

### 4.3 只想看状态、不想下载

```bat
python backend\scripts\setup_env.py --check-only
```

它会打印 Python 版本、`.venv` 是否已建、Node.js 是否可用、两项外部依赖是否就位、`frontend/dist` 是否已构建。

---

## 5. 启动：双击 `start-local.bat`

- 单进程启动：后端在 **8000 端口**同时托管已构建的前端界面。
- 若 `frontend/dist` 缺失，它会自动补跑一次 `npm install` + `npm run build`。
- 启动后会自动打开浏览器 <http://127.0.0.1:8000>。
- 关闭方式：关掉标题为 `Language Training Agent API` 的那个窗口。
- 若 `.venv` 不存在（没跑过 `setup.bat`），它会直接提示你先跑 `setup.bat`，而不是静默失败。

---

## 6. 自检环境是否完整

浏览器打开 <http://127.0.0.1:8000/api/materials/import-capabilities>，或命令行：

```bat
curl http://127.0.0.1:8000/api/materials/import-capabilities
```

本机实测返回（`whisper_model` 路径随机器不同）：

```json
{"ffmpeg":true,"yt_dlp":true,"faster_whisper":true,"problems":[],
 "whisper_model":"...\\tools\\models\\faster-whisper-base",
 "whisper_model_local":true,"ready":true}
```

- `ready` 为 `true`：导入与语音转写链路可用。
- `ready` 为 `false`：看 `problems` 数组，里面逐条写明缺哪一项、怎么补。
- `whisper_model_local` 为 `false`：模型还没落到本地，首次识别会尝试联网下载。

---

## 7. 常见问题

### 双击后窗口一闪而过
多半是脚本自己退出了。改用「命令提示符」进入项目目录手动执行，就能看到完整报错：

```bat
cd /d <项目目录>
python backend\scripts\setup_env.py
```

### `[ERROR] Python was not found`
Python 没装，或装了没勾 `Add python.exe to PATH`。重装并勾上，或手动把 Python 目录加进系统 PATH。

### `[ERROR] Python 3.12 or newer is required`
版本过低。项目依赖 `numpy==2.5.3` 要求 ≥ 3.12。

### `[ERROR] 未找到 Node.js / npm`
前端构建必需。装 Node.js LTS 后重新双击 `setup.bat`。

### 下载卡住 / 中断
重跑 `setup.bat` 即可——已完成的步骤会跳过。ffmpeg 采用断点续传：先写入 `.part` 文件，全部收完才改名到目标位置，所以中断后重跑会从已下载的字节继续，不会白下。模型由 huggingface_hub 负责下载，重跑同样会复用已有进度。

**如果 ffmpeg 下载实在太慢**（本机实测约 30 KB/s），走 4.2 节的替代路径，别干等。

若镜像端点长时间无响应，可改用官方端点单独重试模型：

```bat
.venv\Scripts\python.exe backend\scripts\prepare_assets.py --hf-endpoint https://huggingface.co
```

### 8000 端口被占用
说明已经有一个实例在跑。要么直接用它（关掉重复启动），要么先关掉原来的 `Language Training Agent API` 窗口。可先用浏览器访问 <http://127.0.0.1:8000/api/health> 确认：返回 `{"status":"ok"}` 就是在跑。

### 打开首页是 404
`frontend/dist` 没构建成功。后端此时仍会启动并服务 `/api/*`，但根路径没有界面。执行：

```bat
cd frontend
npm install
npm run build
```

### 「贴链接导入」报错
先看第 6 节的自检接口。若 `ffmpeg` 或 `faster_whisper` 为 `false`，说明 `tools/` 没补齐，重跑 `setup.bat` 第 4 步。

### 目标机器不能联网
把源机器的 `tools\` 整个目录（444 MB）用 U 盘拷到目标机器的同名位置即可，Python 包则需要提前用 `pip download` 之类的离线方式准备，本指南不覆盖该场景。

---

## 8. 平台差异

- `start-local.bat`、`setup.bat`、`tools\ffmpeg\bin\*.exe` 均为 **Windows 专用**。
- macOS / Linux 上需要：
  - 自行安装 ffmpeg（后端会命中 PATH 分支找到它，见 `backend/app/core/media_tools.py` 的解析顺序）；
  - 用 README「本地启动」里的手动命令代替两个 `.bat`；
  - Python 侧脚本（`backend/scripts/*.py`）本身是跨平台的，`prepare_assets.py` 会自动适配 `.venv/bin/python` 布局。

---

## 9. 相关文件

| 文件 | 作用 |
|---|---|
| `setup.bat` | 一键环境准备（本指南第 4 节） |
| `start-local.bat` | 一键启动（本指南第 5 节） |
| `backend/scripts/setup_env.py` | `setup.bat` 的实际逻辑；`--check-only` 可只查状态 |
| `backend/scripts/prepare_assets.py` | 单独下载/检查 ffmpeg 与语音模型 |
| `.env.example` | 全部 28 个 `LTA_*` 可配置项 |
| `README.md` | 技术边界、手动步骤、质量门 |
