# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a02_sector_rotation.py
# 对应聚宽版：strategies/joinquant/advanced/a02_sector_rotation.py
# 详细讲解：docs/backtrader/advanced/02_sector_rotation.md
"""
策略 2：行业轮动策略（Sector Rotation）
类型：中观配置 / 行业轮动 ｜ 难度：★★★★☆
核心思路：在 31 个申万一级行业之间轮动，买入动量最强的 K 个行业，
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_sw_universe           # noqa: E402
from btlab.runner import PanelStrategy, run_strategy                   # noqa: E402

# ============================ 回测参数 ============================
START = '2010-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a02_result.png')

TOPN = 5                    # 持有动量最强的几个行业
LOOKBACK = 60               # 行业动量回看期


class SectorRotation(PanelStrategy):
    """申万一级行业动量轮动：每月买动量最强的 TOPN 个行业。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        self.names = {d._name: d._name for d in self.tradables}

    def on_rebalance(self, cur):
        scores = {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            scores[d._name] = closes[-1] / closes[0] - 1.0
        if len(scores) < self.p.topn:
            return
        target = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
        self.equal_weight_order(target, cur)


def main():
    print('[1/3] 加载申万一级行业指数（用行业指数当标的 → 无幸存者偏差）...')
    data = load_sw_universe(start=START, end=END, min_bars=LOOKBACK + 1)

    print('[2/3] 加入交易日历 ...')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(SectorRotation, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶2 行业轮动策略（backtrader · 申万一级行业指数）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
