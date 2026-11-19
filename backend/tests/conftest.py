"""pytest 全局配置（项目根 conftest.py）"""
import os
import sys
import tempfile
from pathlib import Path

# Windows 兼容：把项目根加到 sys.path（防止找不到 app 模块）
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def pytest_configure(config):
    """pytest 启动时设置基础 temp 目录（避免 Windows 系统 Temp 锁问题）"""
    # 用系统 Temp 下的子目录（避免项目目录的 .pytest_tmp 锁问题）
    base = Path(tempfile.gettempdir()) / f"pytest_{os.getpid()}"
    base.mkdir(exist_ok=True, parents=True)
    config.option.basetemp = str(base)