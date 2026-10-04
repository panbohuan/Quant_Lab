# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/beginner/s03_value_pe_pb.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/beginner/bt_s03_value_pe_pb.py
#
# 与聚宽版的差异：
#   1) 聚宽用 query(valuation.pb_ratio) 取历史任意时点的估值；
#      本地免费源（东方财富个股估值）只有 **2018 年起** 的日频数据，因此回测起点为 2018-01-01。
#   2) 估值面板用 asof() 严格取「不晚于调仓日」的最近一条，不用未来数据。
#   3) 股票池为「当前」沪深300成分股，存在幸存者偏差，仅作教学用途。
# ==========================================================================================
"""
================================================================================
策略 3：单因子低估值选股策略（PE / PB 估值因子）· backtrader 本地版
================================================================================
策略类型：单因子选股（基本面·估值因子）
难度等级：★★☆☆☆
核心思路：价值投资——买入"便宜"的股票。市净率(PB)越低代表估值越便宜，
          历史统计上低估值组合长期能跑赢市场（价值溢价）。
          每月按 PB 升序买入最低估的 K 只，等权持有。

【学习重点】
  - 基本面数据的「面板」结构：DataFrame(index=日期, columns=股票代码)
  - asof(panel, cur)：只取调仓日及之前的数据 —— 防未来函数的核心习惯
  - value_panel(codes, 'pb')：一次性把几十只股票的 PB 拼成面板
================================================================================
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          value_panel, asof)

# ============================ 回测参数 ============================
START = '2018-01-01'        # 估值数据（东财）约 2018 年起
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s03_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
FACTOR = 'pb'               # 估值因子列名：'pb'（市净率）或 'pe_ttm'（滚动市盈率）


class LowValuation(PanelStrategy):
    """低估值选股：按 PB 升序取最便宜的 TOPN 只，每月等权调仓。"""

    params = (('topn', TOPN), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print(f'  预加载 {len(codes)} 只股票的 {FACTOR} 面板 ...')
        self.panel = value_panel(codes, FACTOR)

    def on_rebalance(self, cur):
        row = asof(self.panel, cur)           # 只取 <= cur 的最近一行，防未来函数
        if row is None or len(row) < self.p.topn:
            return
        row = row[row > 0]                    # 剔除负 PB（净资产为负的异常公司）
        if len(row) < self.p.topn:
            return
        names = [c for c in row.sort_values().index[:self.p.topn]
                 if c in self.getdatanames()]
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print(f'[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(LowValuation, data, cash=CASH, benchmark=BENCHMARK,
                 title=f'策略3 单因子低估值选股（backtrader · 因子={FACTOR}）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
