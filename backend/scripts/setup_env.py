"""在新机器上一键把运行环境准备好（Windows / 可联网）。

`setup.bat` 只是本脚本的最小包装；真正的逻辑都在这里，便于逐项排查。

依次完成 5 件事，全部幂等，可重复运行：

1. 检查 Python 与 Node.js 是否满足要求
2. 创建虚拟环境 ``.venv``
3. 安装后端依赖（``requirements.txt``）
4. 下载外部依赖（ffmpeg + 语音模型，见 ``prepare_assets.py``）
5. 构建前端 ``frontend/dist``

用法（在项目根目录执行）：

    python backend\\scripts\\setup_env.py
    python backend\\scripts\\setup_env.py --check-only

版本要求来自实测的包元数据，不是估计值：

===========  ============================================
项目          实测 Requires-Python
===========  ============================================
Python         >= 3.12（由 ``numpy==2.5.3`` 决定，为已装依赖中最高的一条）
Node.js        仅需可运行 ``npm``；本机实测 v22.22.2 / npm 10.9.7
===========  ============================================

可用环境变量覆盖：

    LTA_PIP_INDEX   pip 索引地址（默认 https://mirrors.aliyun.com/pypi/simple/）
                    设成空字符串即改用官方 PyPI
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_PYTHON_MIN = (3, 12)
PIP_INDEX_DEFAULT = "https://mirrors.aliyun.com/pypi/simple/"
PIP_TRUSTED_HOST = "mirrors.aliyun.com"
ASSET_FALLBACK_ENDPOINT = "https://huggingface.co"


def _enable_utf8_stdout() -> None:
    """Windows 控制台编码不确定，遇到无法表示的字符时替换而非崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def _say(message: str = "") -> None:
    print(message, flush=True)


def _run(argv: list[str], cwd: Path | None = None) -> int:
    """执行外部命令并把输出直接接到当前控制台。"""
    _say(f"        > {' '.join(argv)}")
    try:
        completed = subprocess.run(argv, cwd=str(cwd or PROJECT_ROOT), check=False)
    except OSError as error:
        _say(f"        [失败] 无法执行：{error}")
        return 1
    return completed.returncode


def venv_dir() -> Path:
    return PROJECT_ROOT / ".venv"


def venv_python() -> Path | None:
    """返回虚拟环境解释器路径；Windows 与 POSIX 布局不同，两者都试。"""
    for candidate in (venv_dir() / "Scripts" / "python.exe", venv_dir() / "bin" / "python"):
        if candidate.is_file():
            return candidate
    return None


def python_version() -> tuple[int, int, int] | None:
    info = sys.version_info
    return (info.major, info.minor, info.micro)


def check_python() -> bool:
    current = python_version()
    if current is None or current[:2] < PROJECT_PYTHON_MIN:
        want = ".".join(str(part) for part in PROJECT_PYTHON_MIN)
        _say(f"        [失败] 当前 Python 为 {sys.version.split()[0]}，需要 {want} 或更新。")
        _say("               下载：https://www.python.org/downloads/")
        _say('               安装时务必勾选 "Add python.exe to PATH"。')
        return False
    _say(f"        Python {sys.version.split()[0]}  OK")
    return True


def check_node() -> tuple[bool, str | None]:
    npm = shutil.which("npm")
    node = shutil.which("node")
    if npm is None or node is None:
        _say("        [失败] 未找到 Node.js / npm（构建前端界面需要）。")
        _say("               下载 LTS 版：https://nodejs.org/en/download")
        return False, None
    version = subprocess.run(
        [node, "--version"], check=False, capture_output=True, text=True
    ).stdout.strip()
    _say(f"        Node.js {version or '未知版本'}  OK")
    return True, npm


def create_venv() -> bool:
    if venv_python() is not None:
        _say("        已存在，跳过。")
        return True
    if _run([sys.executable, "-m", "venv", str(venv_dir())]) != 0:
        _say("        [失败] 创建虚拟环境失败。")
        return False
    if venv_python() is None:
        _say("        [失败] 虚拟环境创建后找不到解释器。")
        return False
    return True


def install_requirements(python: Path, index: str) -> bool:
    _run([str(python), "-m", "pip", "install", "--upgrade", "pip", "--quiet",
          "--disable-pip-version-check"])

    base = [str(python), "-m", "pip", "install", "-r", "requirements.txt",
            "--disable-pip-version-check"]
    if index:
        _say(f"        使用索引：{index}")
        if _run([*base, "-i", index, "--trusted-host", PIP_TRUSTED_HOST]) == 0:
            return True
        _say("        镜像安装失败，改用官方 PyPI 重试 ...")
    if _run(base) == 0:
        return True
    _say("        [失败] 后端依赖安装失败。请检查网络后重试本脚本。")
    return False


def install_assets(python: Path) -> bool:
    script = PROJECT_ROOT / "backend" / "scripts" / "prepare_assets.py"
    endpoint = os.getenv("HF_ENDPOINT", "")
    argv = [str(python), str(script)]
    if endpoint:
        argv += ["--hf-endpoint", endpoint]
    if _run(argv) == 0:
        return True
    if endpoint != ASSET_FALLBACK_ENDPOINT:
        _say(f"        镜像端点未成功，改用 {ASSET_FALLBACK_ENDPOINT} 重试 ...")
        if _run([str(python), str(script), "--hf-endpoint", ASSET_FALLBACK_ENDPOINT]) == 0:
            return True
    _say("        [失败] 外部依赖未备齐。上面已写明缺哪一项；不影响其他功能使用。")
    return False


def build_frontend(npm: str) -> bool:
    frontend = PROJECT_ROOT / "frontend"
    if (frontend / "dist" / "index.html").is_file():
        _say("        已存在，跳过。")
        return True
    if not (frontend / "node_modules").is_dir() and _run([npm, "install"], cwd=frontend) != 0:
        _say("        [失败] npm install 失败。")
        return False
    if _run([npm, "run", "build"], cwd=frontend) != 0:
        _say("        [失败] 前端构建失败。")
        return False
    if not (frontend / "dist" / "index.html").is_file():
        _say("        [失败] 构建结束但未生成 frontend/dist/index.html。")
        return False
    return True


def report_status() -> int:
    python = venv_python()
    _say("当前环境状态")
    _say(f"  Python          {sys.version.split()[0]}（需要 >= 3.12）")
    _say(f"  .venv           {'已创建' if python else '未创建'}")
    _say(f"  Node.js         {'已安装' if shutil.which('npm') else '未安装'}")
    assets = PROJECT_ROOT / "backend" / "scripts" / "prepare_assets.py"
    if python is not None:
        _run([str(python), str(assets), "--check-only"])
    dist = PROJECT_ROOT / "frontend" / "dist" / "index.html"
    _say(f"  frontend/dist   {'已构建' if dist.is_file() else '未构建'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    _enable_utf8_stdout()
    parser = argparse.ArgumentParser(description="Language Training Agent 环境准备")
    parser.add_argument("--check-only", action="store_true", help="只报告状态，不改动任何文件")
    parser.add_argument(
        "--pip-index",
        default=os.getenv("LTA_PIP_INDEX", PIP_INDEX_DEFAULT),
        help="pip 索引地址；设为空字符串则用官方 PyPI",
    )
    args = parser.parse_args(argv)

    _say("=" * 60)
    _say("  Language Training Agent 环境准备")
    _say("=" * 60)
    _say()
    _say(f"项目目录：{PROJECT_ROOT}")
    _say()

    if args.check_only:
        return report_status()

    _say("预计下载约 460 MB（Python 依赖 + ffmpeg + 语音模型），视网速需要 5-20 分钟。")
    _say()

    _say("[1/5] 检查 Python 与 Node.js")
    if not check_python():
        return 1
    node_ok, npm = check_node()
    if not node_ok or npm is None:
        return 1
    _say()

    _say("[2/5] 创建虚拟环境 .venv")
    if not create_venv():
        return 1
    _say()

    python = venv_python()
    if python is None:
        _say("[失败] 虚拟环境解释器不可用。")
        return 1

    _say("[3/5] 安装后端依赖")
    if not install_requirements(python, args.pip_index):
        return 1
    _say()

    _say("[4/5] 准备外部依赖（ffmpeg + 语音模型）")
    assets_ok = install_assets(python)
    _say()

    _say("[5/5] 构建前端界面")
    frontend_ok = build_frontend(npm)
    _say()

    _say("=" * 60)
    if assets_ok and frontend_ok:
        _say("  环境已就绪")
        _say("=" * 60)
        _say()
        _say("下一步：双击项目根目录的 start-local.bat，浏览器会自动打开。")
        return 0

    _say("  环境未完全就绪（部分功能会不可用）")
    _say("=" * 60)
    _say()
    if not assets_ok:
        _say("- 外部依赖缺失：服务能启动，但「贴链接导入」与自动搜索素材会失败。")
        _say("  可单独重试：.venv\\Scripts\\python.exe backend\\scripts\\prepare_assets.py")
    if not frontend_ok:
        _say("- 前端未构建：后端仍会启动并服务 /api/*，但根路径 404（没有界面）。")
        _say("  可单独重试：cd frontend && npm install && npm run build")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
