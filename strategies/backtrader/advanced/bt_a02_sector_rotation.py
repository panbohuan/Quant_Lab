# -*- coding: utf-8 -*-
# ==========================================================================================
# 【backtrader 本地回测版 · 可离线运行】对应聚宽版：strategies/joinquant/advanced/a02_sector_rotation.py
#
# 回测内核：backtrader（官方开源框架）｜数据：btlab.datasource（免费，无需聚宽账号）
# 运行方式（项目根目录）：python strategies/backtrader/advanced/bt_a02_sector_rotation.py
#
# 与聚宽版的差异：
#   1) 聚宽用 get_industries('sw_l1') + get_industry_stocks 逐个行业内选股；
#      本地版直接用**申万一级行业指数**（1999 年起，免费）做轮动标的，
#      相当于"每个行业买一篮子"的简化，省掉了行业内二次选股。
#   2) 行业指数本身不可直接交易，实盘应使用对应的行业 ETF；本策略用于教学演示轮动逻辑。
# ==========================================================================================
"""
================================================================================
进阶策略 2：行业轮动策略（Sector Rotation）· backtrader 本地版
================================================================================
策略类型：中观配置 / 行业轮动
难度等级：★★★★☆
核心思路：在 31 个申万一级行业之间轮动，买入动量最强的 K 个行业，
          实现"自上而下"（先选行业、再选个股）的配置逻辑。

【学习重点】
  - 中观视角：不选个股、不选大类资产，而是在"行业"这一层做配置
  - 行业指数数据（申万宏源，1999 年起）
  - 30+ 个数据源同时喂给 backtrader 的写法（self.tradables 遍历）
  - 动量轮动的最小实现：算动量 → 排序 → 取前 K → 等权
  - 与 s02（个股动量）对比：同样是动量，但作用层级不同
================================================================================
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily, sw_industries, load_sw_index  # noqa: E402
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
    print('[1/3] 获取申万一级行业列表 ...')
    sw = sw_industries()
    print(f'      共 {len(sw)} 个行业')

    print('[2/3] 加载行业指数日线 ...')
    data = {}
    for _, row in sw.iterrows():
        try:
            df = load_sw_index(row['code'], start=START, end=END)
            if len(df) >= LOOKBACK + 1:
                data[row['name']] = df
        except Exception as e:  # noqa: BLE001
            print(f'  [跳过] {row["name"]}: {str(e)[:50]}')
    print(f'      可用行业指数 {len(data)} 个')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(SectorRotation, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶2 行业轮动策略（backtrader · 申万一级行业指数）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
