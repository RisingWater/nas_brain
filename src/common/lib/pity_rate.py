"""保底概率计算器 — 类似网游暴击率的随机触发机制

固定概率独立判定时，长期触发率等于设定值但可能连续很久不触发（脸黑）。
PityRate 用软保底消除长连空：连续未触发时实际概率递增，直到必中。

关键：配置的概率是**数学期望**。递增会天然拉高实际触发率，所以构造时
数值求解一个更低的初始概率，使整个保底过程的长期期望精确等于目标值
（即「面板暴击率 = 实际期望暴击率」）。

用法:
    pity = PityRate(0.5, pity_steps=5)   # 目标期望 50%，最多连续 5 次未中后必中
    if pity.roll():
        # 触发了
    print(pity.current_prob)             # 当前实际概率（随未触发递增）
"""
import random
import logging

logger = logging.getLogger(__name__)


def _expected_prob(base: float, increment: float, steps: int) -> float:
    """马尔可夫递推：给定初始概率 base、步进 increment，计算长期期望触发率

    状态 i = 连续未触发次数（0..steps），状态概率 q_i = min(base + i*inc, 1)。
    q_steps = 1（必中）。E_i = 从状态 i 出发到命中的期望剩余尝试次数：
        E_steps = 1
        E_i = 1 + (1 - q_i) * E_{i+1}
    期望触发率 = 1 / E_0
    """
    E = 1.0
    for i in range(steps - 1, -1, -1):
        q = min(base + i * increment, 1.0)
        E = 1 + (1 - q) * E
    return 1.0 / E


def _solve_initial(target: float, steps: int) -> float:
    """数值二分：求解初始概率 base，使期望触发率 == target

    期望随 base 单调递增（base=0 → 期望 0；base=target → 期望 > target），
    故二分收敛，50 次迭代误差 < 2^-50。
    """
    lo, hi = 0.0, target
    for _ in range(50):
        mid = (lo + hi) / 2
        increment = (1 - mid) / steps  # 保证 steps 次未触发后概率到 1.0
        if _expected_prob(mid, increment, steps) < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


class PityRate:
    """保底概率计算器

    非线程安全：同一个实例应由单线程调用（engine 按 user_id 各持一个实例）。
    """

    def __init__(self, target_prob: float = 0.5, pity_steps: int = 5):
        """
        Args:
            target_prob: 目标期望概率（0~1，0.5 = 长期平均 50% 触发）
            pity_steps: 软保底步数（>=1），连续未触发 pity_steps 次后概率达到
                100% 必中。步数越大分布越平缓，越小越激进（更快保底）。
        """
        if not 0 <= target_prob <= 1:
            raise ValueError(f"target_prob 需在 0~1 之间: {target_prob}")
        if pity_steps < 1:
            raise ValueError(f"pity_steps 需 >= 1: {pity_steps}")
        self.target_prob = target_prob
        self.pity_steps = pity_steps
        # 求解初始概率使期望 == target_prob
        self.initial_prob = _solve_initial(target_prob, pity_steps)
        self.increment = (1 - self.initial_prob) / pity_steps
        self._misses = 0
        logger.debug("PityRate 初始化: 目标期望=%.0f%% 初始概率=%.0f%% 递增=%.0f%%/次",
                     target_prob * 100, self.initial_prob * 100, self.increment * 100)

    @property
    def current_prob(self) -> float:
        """当前实际概率（初始 + 递增，封顶 100%）"""
        return min(self.initial_prob + self._misses * self.increment, 1.0)

    @property
    def misses(self) -> int:
        """连续未触发次数"""
        return self._misses

    def roll(self) -> bool:
        """按当前概率判定一次

        - 触发：重置连续未触发次数，返回 True
        - 未触发：连续次数 +1（下次概率提升），返回 False
        """
        if random.random() < self.current_prob:
            if self._misses > 0:
                logger.debug("保底概率触发: 连续 %d 次未中后命中", self._misses)
            self._misses = 0
            return True
        self._misses += 1
        logger.debug("保底概率未触发: 累计 %d 次, 下次概率 %.0f%%",
                     self._misses, self.current_prob * 100)
        return False

    def reset(self):
        """重置连续未触发次数"""
        self._misses = 0
