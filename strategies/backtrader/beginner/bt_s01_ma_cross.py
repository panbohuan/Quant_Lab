# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s01_ma_cross.py
# 对应聚宽版：strategies/joinquant/beginner/s01_ma_cross.py
# 详细讲解：docs/backtrader/beginner/01_ma_cross.md
"""
策略 1：双均线趋势跟踪策略（MA Cross）
类型：技术指标择时（单标的，非选股） ｜ 难度：★☆☆☆☆（入门）
核心思路：短期均线上穿长期均线（金叉）→ 买入；下穿（死叉）→ 卖出。
注意：backtrader 里 close[-1] 是昨天、close[1] 是明天（未来），回测只允许 [0] 和负索引。
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import backtrader as bt                                               # noqa: E402

from btlab.datasource import load_daily                               # noqa: E402
from btlab.runner import run_strategy, round_lot                      # noqa: E402

# ============================ 回测参数（改这里即可） ============================
START = '2013-01-01'        # 数据起点（沪深300ETF 2012-05 上市）
END = None                  # None = 到今天
CASH = 1_000_000            # 初始资金
BENCHMARK = '000300'        # 基准：沪深300指数
SYMBOL = '510300'           # 交易标的：沪深300ETF
PLOT = os.path.join('results', 'bt_s01_result.png')  # 净值图输出文件名


class MaCross(bt.Strategy):
    """双均线趋势跟踪：金叉满仓买入，死叉清仓。"""

    params = (
        ('fast', 5),        # 短期均线周期
        ('slow', 20),       # 长期均线周期
        ('stake', 0.95),    # 买入时使用的资金比例（留 5% 缓冲，避免因滑点/费用下单失败）
    )

    def __init__(self):
        """建指标：只在这里建一次，next() 里只读不算。"""
        self.ma_fast = bt.ind.SMA(self.data.close, period=self.p.fast)
        self.ma_slow = bt.ind.SMA(self.data.close, period=self.p.slow)
        # CrossOver > 0 表示今日发生「上穿」，< 0 表示「下穿」
        self.cross = bt.ind.CrossOver(self.ma_fast, self.ma_slow)

    def next(self):
        """每个交易日收盘后执行：出信号 → 下单（次日开盘成交）。"""
        if not self.position:
            # 空仓 + 金叉 → 买入
            if self.cross[0] > 0:
                size = round_lot(self.broker.getcash() * self.p.stake / self.data.close[0])
                if size > 0:
                    self.buy(size=size)
        elif self.cross[0] < 0:
            # 持仓 + 死叉 → 清仓
            self.close()


def main():
    print(f'[1/2] 加载 {SYMBOL} 日线数据 ...')
    df = load_daily(SYMBOL, start=START, end=END)
    print(f'      区间 {df.index[0].date()} ~ {df.index[-1].date()}，共 {len(df)} 个交易日')

    print('[2/2] 开始 backtrader 回测 ...')
    run_strategy(
        MaCross,
        {SYMBOL: df},
        cash=CASH,
        benchmark=BENCHMARK,
        title='策略1 双均线趋势跟踪（backtrader · 沪深300ETF）',
        plot_path=PLOT,
    )


if __name__ == '__main__':
    main()
