"""
工具函数模块
技术原理：环境变量加载、日志配置
面试考点：Python 项目基础架构
"""
import os
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


def get_env(key, default=None):
    """
    获取环境变量的辅助函数
    
    使用示例：
    API_KEY = get_env("API_KEY")  # 必填
    PORT = get_env("PORT", 5000)  # 有默认值
    """
    return os.getenv(key, default)


def setup_logging():
    """
    配置日志系统
    
    技术原理：
    - logging 是 Python 标准库日志模块
    - basicConfig 配置全局日志级别和格式
    - getLogger 获取 logger 实例
    
    面试考点：为什么用 logging 而不是 print？
    答：
    - 可配置日志级别（DEBUG/INFO/WARNING/ERROR）
    - 可输出到文件/控制台/远程服务
    - 线程安全，支持并发
    - 生产环境可动态调整日志级别
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)


# 全局 logger 实例
logger = setup_logging()
