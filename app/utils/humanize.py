"""拟人化操作辅助：随机等待，模拟真人操作节奏"""
import random
import time


def human_pause(min_s: float = 0.15, max_s: float = 0.45) -> None:
    """通用：人类随机停顿"""
    time.sleep(random.uniform(min_s, max_s))


def wait_random_time(base_time: float = 0.3) -> float:
    """随机等待一段时间，模拟真人操作。返回实际等待秒数"""
    wait_time = base_time + random.uniform(0.2, 0.5)
    time.sleep(wait_time)
    return wait_time
