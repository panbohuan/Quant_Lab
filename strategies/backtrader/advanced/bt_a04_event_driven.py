# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a04_event_driven.py
# 对应聚宽版：strategies/joinquant/advanced/a04_event_driven.py
# 详细讲解：docs/backtrader/advanced/04_event_driven.md
"""
策略 4：事件驱动策略（Event-Driven）
类型：另类策略 / 事件驱动 ｜ 难度：★★★★☆
核心思路：围绕财报发布事件，在事件窗口内交易，捕捉事件冲击带来的定价偏差。
"""
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import (PanelStrategy, run_strategy, load_universe,  # noqa: E402
                          event_calendar)

# ============================ 回测参数 ============================
START = '2018-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a04_result.png')

UNIVERSE_SIZE = 40
TOPN = 10                   # 同时最多持有的事件股数
THRESHOLD = 30.0            # 业绩超预期阈值：净利润增长率 > 30%
EVENT_WINDOW = 25           # 事件有效窗口（自然日）
ANNOUNCE_LAG = 45           # 报告期 → 推定公告日 的滞后天数


class EventDriven(PanelStrategy):
    """业绩超预期事件驱动：公告后窗口内持有，窗口结束自动退出。"""

    params = (('topn', TOPN), ('threshold', THRESHOLD),
              ('window_days', EVENT_WINDOW), ('rebalance', 'weekly'),)

    def __init__(self):
        super().__init__()
        codes = [d._name for d in self.tradables]
        print(f'  构建业绩公告事件日历（{len(codes)} 只，首次较慢）...')
        self.calendar = event_calendar(codes, threshold=self.p.threshold,
                                       lag_days=ANNOUNCE_LAG)
        n_events = sum(len(v) for v in self.calendar.values())
        print(f'  共 {len(self.calendar)} 只有"好事件"，合计 {n_events} 次')

    def on_rebalance(self, cur):
        lo = pd.Timestamp(cur) - pd.Timedelta(days=self.p.window_days)
        active = []
        for code, events in self.calendar.items():
            if code not in set(self.getdatanames()):
                continue
            d = self.getdatabyname(code)
            if not self.live(d, cur):            # 停牌不参与
                continue
            if any(lo <= dt <= pd.Timestamp(cur) for dt, _ in events):
                active.append(code)

        if not active:
            self.close_all(cur)                  # 没有事件 → 空仓等待
            return
        self.equal_weight_order(active[:self.p.topn], cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(EventDriven, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶4 事件驱动策略（backtrader · 业绩超预期）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
