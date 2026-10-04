# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】
# 对应聚宽版：strategies/joinquant/beginner/s01_ma_cross.py
#
# 回测内核：backtrader（官方开源框架，本文件不含任何自研撮合/账务逻辑）
# 数据来源：btlab.datasource —— 免费长历史数据（新浪财经），无需聚宽账号、无需注册
#
# 运行方式（在项目根目录执行）：
#     python strategies/backtrader/beginner/bt_s01_ma_cross.py
# 首次运行会联网拉数据并缓存到 data_cache/，之后秒开；净值图存为 bt_s01_result.png
#
# 与聚宽版的差异（务必了解）：
#   1) 聚宽用 run_daily(trade, time='14:50') 在盘中触发；这里用「日线收盘出信号、
#      次日开盘成交」，同样不存在未来函数，且更贴近"隔夜决策"的真实约束。
#   2) 聚宽用 order_target_value 按目标市值下单；这里按「整手股数」下单（A 股 1 手 = 100 份）。
#   3) ETF 用新浪接口，只有不复权价；btlab 已按分红记录做「加回分红」修正，使区间收益接近真实总收益。
# ==========================================================================================
"""
================================================================================
策略 1：双均线趋势跟踪策略（MA Cross）· backtrader 本地版
================================================================================
策略类型：技术指标择时（单标的，非选股）
难度等级：★☆☆☆☆（入门）
核心思路：短期均线上穿长期均线（金叉）→ 买入；下穿（死叉）→ 卖出。
交易标的：沪深300ETF（510300）

【学习重点】
  - 用 bt.ind.SMA / bt.ind.CrossOver 表达择时信号
  - 用 self.position 判断当前是否有持仓
  - 用 self.buy() / self.close() 下单（backtrader 官方 API）
  - 手续费/滑点的建模（见 btlab/runner.py 的 AStockCommission）

【关键 backtrader API】
  - bt.Strategy                    策略基类
  - params = ((...), (...))        策略参数（self.p.xxx 访问）
  - __init__                       只在回测开始时执行一次，适合建指标
  - next()                         每根 K 线（这里=每个交易日）执行一次
  - self.data.close[0]             当日收盘价
    self.data.close[-1]            昨天（负号 = 往回看，[-2] 就是前天）
    self.data.close[1]             是「明天」！正号 = 未来，回测里绝对不能用
                                   （实数序列里这样写会直接报 IndexError；
                                     更危险的是第一根 K 线的 [-1] 会静默绕到
                                     数据集最后一行，等于偷看未来，务必靠
                                     minperiod / 长度判断挡住）
  - self.broker.getcash()          当前可用现金
================================================================================
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
