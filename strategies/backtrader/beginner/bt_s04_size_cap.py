# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/beginner/s04_size_cap.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/beginner/bt_s04_size_cap.py
#
# 与聚宽版的差异：
#   1) 聚宽用 valuation.market_cap 取任意时点市值；本地免费源只有 2018 年起的日频总市值。
#   2) 股票池限定为「当前沪深300成分股」——它们都是大市值股，因此本策略在本地跑出来的
#      小市值效应会明显弱于「全市场小市值」的聚宽版。要看真正的全市场小市值效应，
#      需要全市场股票列表 + 全市场行情（数据量很大，本教学版本不这么做）。
# ==========================================================================================
"""
================================================================================
策略 4：单因子小市值选股策略（Size / 市值因子）· backtrader 本地版
================================================================================
策略类型：单因子选股（基本面·规模因子）
难度等级：★★☆☆☆
核心思路：小市值效应——长期看，小市值股票的平均收益高于大市值股票（A股尤甚）。
          用总市值作为因子，市值越小排名越靠前，每月等权买入最小的 K 只。

【学习重点】
  - 市值因子面板：value_panel(codes, 'total_mv')（单位：元）
  - 因子"方向"的处理：小市值 → 升序取前 N（sort_values() 默认升序）
  - 与动量这类"越大越好"的因子如何区分方向
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
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s04_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
FACTOR = 'total_mv'         # 'total_mv' 总市值 / 'circ_mv' 流通市值


class SmallCap(PanelStrategy):
    """小市值选股：按总市值升序取最小的 TOPN 只，每月等权调仓。"""

    params = (('topn', TOPN), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print(f'  预加载 {len(codes)} 只股票的市值面板 ...')
        self.panel = value_panel(codes, FACTOR)

    def on_rebalance(self, cur):
        row = asof(self.panel, cur)
        if row is None or len(row) < self.p.topn:
            return
        row = row[row > 0]
        names = [c for c in row.sort_values().index[:self.p.topn]   # 升序 = 市值最小
                 if c in self.getdatanames()]
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(SmallCap, data, cash=CASH, benchmark=BENCHMARK,
                 title=f'策略4 单因子小市值选股（backtrader · 因子={FACTOR}）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
