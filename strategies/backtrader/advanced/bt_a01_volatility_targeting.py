# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a01_volatility_targeting.py
# 对应聚宽版：strategies/joinquant/advanced/a01_volatility_targeting.py
# 详细讲解：docs/backtrader/advanced/01_volatility_targeting.md
"""
策略 1：波动率目标策略（Volatility Targeting）
类型：风险控制 / 仓位管理 ｜ 难度：★★★★☆
核心思路：根据市场波动率动态调整仓位，让组合波动率维持在目标水平。
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import backtrader as bt                                               # noqa: E402

from btlab.datasource import load_daily                               # noqa: E402
from btlab.runner import run_strategy                                 # noqa: E402

# ============================ 回测参数 ============================
START = '2013-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
SYMBOL = '510300'
PLOT = os.path.join('results', 'bt_a01_result.png')

LOOKBACK = 20               # 波动率估计窗口（交易日）
TARGET_VOL = 0.15           # 目标年化波动率 15%
MAX_LEVERAGE = 1.0          # 最大仓位（1.0 = 不加杠杆，最多满仓）


class VolTarget(bt.Strategy):
    """每周按「目标波动率 / 已实现波动率」调整仓位。"""

    params = (('lookback', LOOKBACK), ('target_vol', TARGET_VOL),
              ('max_leverage', MAX_LEVERAGE),)

    def __init__(self):
        self._last_week = None
        self.weights = []

    def next(self):
        cur = self.data.datetime.date(0)
        week = cur.isocalendar()[:2]              # (ISO 年, ISO 周) —— 周度调仓
        if week == self._last_week:
            return
        self._last_week = week

        closes = self.data.close.get(size=self.p.lookback + 1)
        if len(closes) < self.p.lookback + 1:
            return
        rets = pd.Series(closes, dtype=float).pct_change().dropna()
        vol = float(rets.std() * (252 ** 0.5))    # 年化波动率
        if vol <= 1e-6:
            return
        w = min(self.p.target_vol / vol, self.p.max_leverage)
        self.weights.append(w)
        self.order_target_percent(target=w)       # backtrader 官方 API：目标仓位比例

    def stop(self):
        if self.weights:
            print(f'  仓位区间 {min(self.weights) * 100:.1f}% ~ '
                  f'{max(self.weights) * 100:.1f}%，平均 {sum(self.weights) / len(self.weights) * 100:.1f}%')


def main():
    print(f'[1/2] 加载 {SYMBOL} 日线（含分红口径）...')
    df = load_daily(SYMBOL, start=START, end=END)
    print(f'      区间 {df.index[0].date()} ~ {df.index[-1].date()}，共 {len(df)} 个交易日')

    print('[2/2] 开始 backtrader 回测 ...')
    run_strategy(VolTarget, {SYMBOL: df}, cash=CASH, benchmark=BENCHMARK,
                 title='进阶1 波动率目标策略（backtrader · 沪深300ETF）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
