"""
工具模块
提供日志记录、环境变量读取等通用功能
"""
import logging
import sys
import os
from dotenv import load_dotenv

# 加载 .env 文件（优先加载 backend/.env，否则加载项目根目录的.env）
import pathlib
backend_dir = pathlib.Path(__file__).parent
env_file = backend_dir / '.env'
if not env_file.exists():
    env_file = backend_dir.parent / '.env'
load_dotenv(dotenv_path=str(env_file))

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 创建控制台处理器
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)

# 创建格式器
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# 添加处理器到日志记录器
if not logger.handlers:
    logger.addHandler(handler)


def get_env(key: str, default: str = None) -> str:
    """
    获取环境变量

    Args:
        key: 环境变量名称
        default: 默认值

    Returns:
        环境变量值
    """
    return os.getenv(key, default)
