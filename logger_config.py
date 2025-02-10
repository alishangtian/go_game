import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    """设置日志记录器"""
    # 创建logs目录（如果不存在）
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # 创建日志记录器
    logger = logging.getLogger('go_game')
    logger.setLevel(logging.DEBUG)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 创建文件处理器（带有文件轮转）
    file_handler = RotatingFileHandler(
        'logs/go_game.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 添加处理器到日志记录器
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
