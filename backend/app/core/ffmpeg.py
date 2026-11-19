"""
ffmpeg 自动探测与 PATH 注入

whisper.transcribe() 内部用 subprocess.run(["ffmpeg", ...]) 解码 webm/wav，
Windows 上必须能直接找到 ffmpeg.exe，否则报 FileNotFoundError WinError 2。

winget/choco 装完后二进制通常在：
  %LOCALAPPDATA%\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_*\\ffmpeg-*-full_build\\bin\\ffmpeg.exe
但 Git Bash / Anaconda Python 启动时**不继承**该路径（Anaconda 有自己的 PATH 逻辑），
所以必须在应用启动时主动探测并注入 os.environ['PATH']。
"""
from __future__ import annotations

import os
import shutil
from logging import getLogger
from pathlib import Path


logger = getLogger(__name__)


# winget 安装位置（按 Gyan.FFmpeg 包名匹配）
_WINGET_BASES: tuple[str, ...] = (
    r"%LOCALAPPDATA%\Microsoft\WinGet\Packages",
)

# 常见手动安装位置（备选）
_FALLBACK_DIRS: tuple[str, ...] = (
    r"C:\ffmpeg\bin",
    r"C:\Program Files\ffmpeg\bin",
    r"C:\Program Files (x86)\ffmpeg\bin",
    r"D:\ffmpeg\bin",
)


def ensure_ffmpeg_in_path() -> str | None:
    """确保 ffmpeg.exe 在 os.environ['PATH'] 里。

    Returns:
        找到的 ffmpeg.exe 绝对路径；找不到返回 None。
    """
    found = shutil.which("ffmpeg")
    if found:
        logger.info("ffmpeg_already_in_path", extra={"ffmpeg_path": found})
        return found

    # 探测 winget 路径（最新版本通常最深一层）
    candidates: list[Path] = []
    for base in _WINGET_BASES:
        base_path = Path(os.path.expandvars(base))
        if not base_path.is_dir():
            continue
        for pkg_dir in base_path.iterdir():
            if "Gyan.FFmpeg" not in pkg_dir.name:
                continue
            # 形如 Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/
            for ver_dir in pkg_dir.iterdir():
                bin_dir = ver_dir / "bin"
                if (bin_dir / "ffmpeg.exe").is_file():
                    candidates.append(bin_dir)
                # 部分版本直接是 bin/
                if (ver_dir / "ffmpeg.exe").is_file():
                    candidates.append(ver_dir)

    for fallback in _FALLBACK_DIRS:
        p = Path(fallback)
        if (p / "ffmpeg.exe").is_file():
            candidates.append(p)

    if not candidates:
        logger.warning("ffmpeg_not_found", searched=[str(c) for c in candidates])
        return None

    # 取第一个，加到 PATH 最前面（避免被同名工具覆盖）
    chosen = str(candidates[0])
    os.environ["PATH"] = chosen + os.pathsep + os.environ.get("PATH", "")

    # Windows 下 shutil.which 不一定走 os.environ['PATH']，重新检查
    ffmpeg_exe = candidates[0] / "ffmpeg.exe"
    if ffmpeg_exe.is_file():
        # 用绝对路径再试一次（兜底）
        os.environ["PATH"] = str(ffmpeg_exe.parent) + os.pathsep + os.environ.get("PATH", "")
        logger.info("ffmpeg_path_injected", extra={"ffmpeg_path": str(ffmpeg_exe)})
        return str(ffmpeg_exe)

    return None