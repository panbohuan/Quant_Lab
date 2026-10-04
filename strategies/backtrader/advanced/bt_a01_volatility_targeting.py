# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a01_volatility_targeting.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a01_volatility_targeting.py
#
# 与聚宽版的差异：
#   1) 聚宽用 run_weekly 每周一触发；这里用「周切换检测」（isocalendar 的 (年,周) 变化）等效实现。
#   2) 聚宽用 order_target_value 按目标市值下单；这里用 backtrader 官方的
#      order_target_percent(target=仓位比例)，语义更直接。
# ==========================================================================================
"""
================================================================================
进阶策略 1：波动率目标策略（Volatility Targeting）· backtrader 本地版
================================================================================
策略类型：风险控制 / 仓位管理
难度等级：★★★★☆
核心思路：根据市场波动率动态调整仓位，让组合波动率维持在目标水平。
          波动率低时加仓（市场平静、风险可控），波动率高时减仓（市场动荡、风险放大）：
              目标仓位 = 目标波动率 / 已实现波动率       （上限封顶，避免过度杠杆）
交易标的：沪深300ETF（510300）

【学习重点】
  - 已实现波动率 = std(日收益率) × sqrt(252)   （252 是 A 股一年约 252 个交易日）
  - 风险预算：把"风险"而不是"收益"作为配置依据
  - backtrader 官方 API：self.order_target_percent(target=w)
  - 为什么需要封顶：波动率极低时 目标波动率/波动率 会算出 >1 的杠杆，
    而 A 股 ETF 不能加杠杆（聚宽也要显式允许），所以必须 min(·, max_leverage)
================================================================================
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
