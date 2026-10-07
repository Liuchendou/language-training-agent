"""准备不随仓库分发的外部依赖：ffmpeg 与 faster-whisper 语音模型。

仓库刻意不包含 ``tools/``（ffmpeg 三个 exe 约 304 MB、模型约 139 MB，
且 ffmpeg.exe 为 Windows 专用），新机器上需把这两项补回 ``tools/``，
否则「贴链接导入」与自动搜索素材会失败（服务本身仍能启动）。

落盘位置必须与 ``backend/app/core/media_tools.py`` 的解析顺序一致：

* ffmpeg  -> ``tools/ffmpeg/bin/ffmpeg.exe`` 与 ``ffprobe.exe``
* 模型    -> ``tools/models/faster-whisper-<名>/``（含 ``model.bin``）

用法（在项目根目录执行）：

    .venv\\Scripts\\python.exe backend\\scripts\\prepare_assets.py --check-only
    .venv\\Scripts\\python.exe backend\\scripts\\prepare_assets.py

如果官方下载链路太慢，可先手动下载那个 zip，再让脚本只做解压与落位：

    .venv\\Scripts\\python.exe backend\\scripts\\prepare_assets.py --ffmpeg-archive D:\\下载\\ffmpeg-release-essentials.zip

可用环境变量覆盖：

    LTA_FFMPEG_URL     ffmpeg 压缩包地址（默认 gyan.dev 的 release-essentials）
    LTA_WHISPER_MODEL  模型名（默认 base，对应 Hugging Face 的 Systran/faster-whisper-<名>）
    HF_ENDPOINT        模型下载端点（默认 https://hf-mirror.com）

本脚本只负责「把文件放对位置」，不修改任何配置；模型改为手动放置时，
设置 ``LTA_WHISPER_MODEL_DIR`` 亦可（优先级高于项目内副本）。
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FFMPEG_DEFAULT_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_NEEDED = ("ffmpeg.exe", "ffprobe.exe")
HF_ENDPOINT_DEFAULT = "https://hf-mirror.com"
MODEL_WEIGHT = "model.bin"
#: 与 faster_whisper.utils.download_model 的 allow_patterns 对齐。
MODEL_PATTERNS = (
    "config.json",
    "preprocessor_config.json",
    "model.bin",
    "tokenizer.json",
    "vocabulary.*",
)


def _enable_utf8_stdout() -> None:
    """Windows 控制台编码不确定，遇到无法表示的字符时替换而非崩溃。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")


def _say(message: str = "") -> None:
    print(message, flush=True)


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


def ffmpeg_dir() -> Path:
    return PROJECT_ROOT / "tools" / "ffmpeg" / "bin"


def model_dir(model_size: str) -> Path:
    return PROJECT_ROOT / "tools" / "models" / f"faster-whisper-{model_size}"


def ffmpeg_ready() -> bool:
    return all((ffmpeg_dir() / name).is_file() for name in FFMPEG_NEEDED)


def model_ready(model_size: str) -> bool:
    return (model_dir(model_size) / MODEL_WEIGHT).is_file()


def _download(url: str, dest: Path, attempts: int = 40, stall_limit: int = 2) -> None:
    """流式下载，带断点续传与自动重试。

    内容先写入 ``<dest>.part``，全部收完才改名成 ``dest``；中断时保留 ``.part``，
    下一次尝试用 Range 请求从断点继续。

    重试是必需的而非可选：2026-10-06 实测，gyan.dev 的 ffmpeg 包在本机会在下载
    数 MB 后断流，单次尝试无法完成 109 MB 的传输。为了在「每次都会断、但每次都有
    进展」的链路上仍能收敛，重试次数取较大值；但若连续 ``stall_limit`` 次尝试都
    零进展，说明链路本身不可用，直接放弃而不白等。
    """
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    no_progress = 0

    for attempt in range(1, attempts + 1):
        already = part.stat().st_size if part.is_file() else 0
        headers = {"User-Agent": "LLA-setup/1.0"}
        if already:
            headers["Range"] = f"bytes={already}-"
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                status = getattr(response, "status", None) or response.getcode()
                resumed = status == 206 and already > 0
                if attempt > 1:
                    if resumed:
                        _say(f"        第 {attempt} 次尝试：断点续传（已有 {_human(already)}）")
                    else:
                        _say(f"        第 {attempt} 次尝试：服务端未续传，从头开始")
                if not resumed:
                    already = 0
                length = int(response.headers.get("Content-Length") or 0)
                total = already + length if length else 0
                done = already
                last_report = 0.0
                with part.open("ab" if resumed else "wb") as handle:
                    while True:
                        chunk = response.read(1 << 20)
                        if not chunk:
                            break
                        handle.write(chunk)
                        done += len(chunk)
                        now = time.monotonic()
                        # 慢速链路上按百分比会长时间没有反馈，故同时按时间刷新
                        if last_report == 0.0 or now - last_report >= 5:
                            last_report = now
                            if total:
                                percent = done * 100 // total
                                _say(f"        {percent}%  {_human(done)} / {_human(total)}")
                            else:
                                _say(f"        已下载 {_human(done)}")
            if total and done < total:
                raise OSError(f"连接提前结束：期望 {total} 字节，仅收到 {done} 字节")
        except KeyboardInterrupt:
            raise
        except Exception as error:
            after = part.stat().st_size if part.is_file() else 0
            no_progress = 0 if after > already else no_progress + 1
            if no_progress >= stall_limit or attempt >= attempts:
                raise
            _say(f"        第 {attempt} 次中断（{type(error).__name__}），5 秒后重试 ...")
            time.sleep(5)
            continue
        part.replace(dest)
        return


def _extract_ffmpeg_binaries(archive: Path, target: Path) -> list[str]:
    """从官方 zip 里只取出 ``*/bin/*.exe``，忽略文档与 license。"""
    target.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            parts = Path(info.filename).parts
            if len(parts) < 3 or parts[-2] != "bin":
                continue
            if not parts[-1].lower().endswith(".exe"):
                continue
            with bundle.open(info) as source, (target / parts[-1]).open("wb") as sink:
                shutil.copyfileobj(source, sink)
            copied.append(parts[-1])
    return copied


def ensure_ffmpeg(url: str, archive: Path | None = None) -> bool:
    if ffmpeg_ready():
        _say("        已存在，跳过。")
        return True

    if archive is not None and not archive.is_file():
        _say(f"        [失败] 指定的压缩包不存在：{archive}")
        return False

    provided = archive
    target = archive if provided is not None else (
        PROJECT_ROOT / "tools" / "ffmpeg" / "ffmpeg-release-essentials.zip"
    )

    if provided is not None:
        _say(f"        使用本地压缩包：{provided}")
    else:
        _say(f"        未找到，开始下载：{url}")
        try:
            _download(url, target)
        except Exception as error:
            _say(f"        [失败] {type(error).__name__}: {error}")
            _say("        已下载的字节保留在同名 .part 文件，重跑会从断点继续。")
            _say("        若链路持续过慢，可手动下载该 zip，再用 --ffmpeg-archive 指定：")
            _say("        ... prepare_assets.py --ffmpeg-archive <本地 zip 路径>")
            return False

    _say("        正在解压 ...")
    try:
        copied = _extract_ffmpeg_binaries(target, ffmpeg_dir())
    except Exception as error:
        _say(f"        [失败] 解压失败：{type(error).__name__}: {error}")
        return False

    if provided is None:
        target.unlink(missing_ok=True)
    if not ffmpeg_ready():
        _say(f"        [失败] 解压后仍缺少 {FFMPEG_NEEDED}，已取到：{copied}")
        return False
    _say(f"        就绪 -> {ffmpeg_dir()}")
    return True


def ensure_model(model_size: str, endpoint: str) -> bool:
    if model_ready(model_size):
        _say("        已存在，跳过。")
        return True

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        _say("        [失败] 缺少 huggingface_hub。请先安装后端依赖：")
        _say("               .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        return False

    # 先设环境变量再调用，兼容不同 huggingface_hub 版本读取端点的方式。
    if endpoint:
        os.environ.setdefault("HF_ENDPOINT", endpoint)
    repo_id = f"Systran/faster-whisper-{model_size}"
    target = model_dir(model_size)
    _say(f"        未找到，开始下载：{repo_id}（端点 {os.environ.get('HF_ENDPOINT', '')}）")
    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(target),
            allow_patterns=list(MODEL_PATTERNS),
        )
    except Exception as error:
        _say(f"        [失败] {type(error).__name__}: {error}")
        _say("        可改用其他端点：set HF_ENDPOINT=https://huggingface.co 后重试。")
        return False

    if not model_ready(model_size):
        _say(f"        [失败] 下载结束但未出现 {MODEL_WEIGHT}。")
        return False
    _say(f"        就绪 -> {target}")
    return True


def report(model_size: str) -> bool:
    ffmpeg_ok = ffmpeg_ready()
    model_ok = model_ready(model_size)
    ffmpeg_target = ffmpeg_dir()
    whisper_target = model_dir(model_size)
    _say(f"  ffmpeg          {'就绪' if ffmpeg_ok else '缺失'}  {ffmpeg_target}")
    _say(f"  whisper 模型    {'就绪' if model_ok else '缺失'}  {whisper_target}")
    return ffmpeg_ok and model_ok


def main(argv: list[str] | None = None) -> int:
    _enable_utf8_stdout()
    parser = argparse.ArgumentParser(description="下载并放置 ffmpeg 与 faster-whisper 模型")
    parser.add_argument("--check-only", action="store_true", help="只检查状态，不下载")
    parser.add_argument(
        "--ffmpeg-url",
        default=os.getenv("LTA_FFMPEG_URL", FFMPEG_DEFAULT_URL),
        help="ffmpeg 压缩包地址",
    )
    parser.add_argument(
        "--ffmpeg-archive",
        type=Path,
        default=None,
        help="改用本地已下载的 ffmpeg 压缩包（跳过下载）",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("LTA_WHISPER_MODEL", "base"),
        help="模型名（base / small / medium ...）",
    )
    parser.add_argument(
        "--hf-endpoint",
        default=os.getenv("HF_ENDPOINT", HF_ENDPOINT_DEFAULT),
        help="模型下载端点",
    )
    args = parser.parse_args(argv)

    _say("外部依赖检查（这两项不随仓库分发）")
    if args.check_only:
        ready = report(args.model)
        _say()
        _say("结论：全部就绪。" if ready else "结论：有缺失，去掉 --check-only 重新运行即可补齐。")
        return 0 if ready else 1

    _say()
    _say("[1/2] ffmpeg（约 109 MB 压缩包，解压后约 304 MB）")
    ffmpeg_ok = ensure_ffmpeg(args.ffmpeg_url, args.ffmpeg_archive)

    _say()
    _say("[2/2] faster-whisper 语音模型（约 142 MB）")
    model_ok = ensure_model(args.model, args.hf_endpoint)

    _say()
    if ffmpeg_ok and model_ok:
        _say("结果：两项均就绪，导入与语音转写功能可用。")
        return 0
    _say("结果：仍有缺失，上面标 [失败] 的项需要处理。其余功能不受影响。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
