# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s05_quality_roe.py
# 对应聚宽版：strategies/joinquant/beginner/s05_quality_roe.py
# 详细讲解：docs/backtrader/beginner/05_quality_roe.md
"""
策略 5：单因子质量选股策略（ROE 质量因子）
类型：单因子选股（基本面·质量因子） ｜ 难度：★★★☆☆
核心思路：质量投资——买入"赚钱能力强"的好公司。净资产收益率(ROE)越高，
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          roe_panel, asof)

# ============================ 回测参数 ============================
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s05_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
LAG_DAYS = 45               # 报告期 → 可用日 的滞后天数（近似公告延迟）


class QualityROE(PanelStrategy):
    """ROE 质量选股：按 ROE 降序取最高的 TOPN 只，每月等权调仓。"""

    params = (('topn', TOPN), ('rebalance', 'monthly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print(f'  预加载 {len(codes)} 只股票的 ROE 面板（首次较慢，之后读缓存）...')
        self.panel = roe_panel(codes, lag_days=LAG_DAYS)

    def on_rebalance(self, cur):
        row = asof(self.panel, cur)
        if row is None or len(row) < self.p.topn:
            return
        names = [c for c in row.sort_values(ascending=False).index[:self.p.topn]
                 if c in self.getdatanames()]
        top_roe = row.sort_values(ascending=False).iloc[0] if len(row) else float('nan')
        print(f'  [{cur}] ROE 最高 {top_roe:.2f}%')
        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(QualityROE, data, cash=CASH, benchmark=BENCHMARK,
                 title='策略5 单因子质量选股（backtrader · ROE）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
