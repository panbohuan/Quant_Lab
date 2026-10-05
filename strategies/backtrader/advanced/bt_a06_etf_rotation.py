# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/advanced/bt_a06_etf_rotation.py
# 对应聚宽版：strategies/joinquant/advanced/a06_etf_rotation.py
# 详细讲解：docs/backtrader/advanced/06_etf_rotation.md
"""
策略 6：ETF 轮动策略（ETF Rotation）
类型：资产配置 / ETF 轮动 ｜ 难度：★★★★☆
核心思路：在宽基、行业、跨境、商品、债券 ETF 之间按动量轮动，买入近期表现最强的
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from btlab.datasource import load_daily                               # noqa: E402
from btlab.runner import PanelStrategy, run_strategy                  # noqa: E402

# ============================ 回测参数 ============================
START = '2014-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_a06_result.png')

POOL = {
    '510050': '上证50ETF',
    '510300': '沪深300ETF',
    '510500': '中证500ETF',
    '159915': '创业板ETF',
    '518880': '黄金ETF',
    '513100': '纳指ETF',
}
DEFENSIVE = '511010'        # 避险资产：国债ETF
DEFENSIVE_NAME = '国债ETF'

TOPN = 3                    # 持有动量最强的 3 只
LOOKBACK = 60               # 动量回看期


class ETFRotation(PanelStrategy):
    """ETF 动量轮动 + 风险开关（动量全负时躲进国债）。"""

    params = (('topn', TOPN), ('lookback', LOOKBACK), ('rebalance', 'monthly'),
              ('defensive', None),)

    def on_rebalance(self, cur):
        scores = {}
        for d in self.tradables:
            if d._name == self.p.defensive:       # 避险资产不参与动量排序
                continue
            if not self.live(d, cur):
                continue
            closes = self.hist_close(d, self.p.lookback + 1)
            if closes is None or closes[0] <= 0:
                continue
            scores[d._name] = closes[-1] / closes[0] - 1.0
        if not scores:
            return

        target = sorted(scores, key=scores.get, reverse=True)[:self.p.topn]
        best = max(scores.values())

        # 风险开关：最强资产动量仍为负 → 全部转入避险资产
        if best <= 0 and self.p.defensive:
            d = self.getdatabyname(self.p.defensive)
            if self.live(d, cur):
                print(f'  [{cur}] 风险开关触发（最强动量 {best * 100:.2f}%）→ 转入 {DEFENSIVE_NAME}')
                self.equal_weight_order([self.p.defensive], cur)
                return
        self.equal_weight_order(target, cur)


def main():
    print(f'[1/2] 加载 {len(POOL) + 1} 只 ETF 日线 ...')
    data = {}
    for code, name in POOL.items():
        data[f'{name}({code})'] = load_daily(code, start=START, end=END)
    data[f'{DEFENSIVE_NAME}({DEFENSIVE})'] = load_daily(DEFENSIVE, start=START, end=END)
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)
    for name, df in list(data.items())[:-1]:
        print(f'      {name}: {df.index[0].date()} ~ {df.index[-1].date()}  {len(df)} 行')

    print('[2/2] 开始 backtrader 回测 ...')
    run_strategy(ETFRotation, data, cash=CASH, benchmark=BENCHMARK,
                 title='进阶6 ETF轮动策略（backtrader · 6 类资产 + 国债避险开关）',
                 plot_path=PLOT, defensive=f'{DEFENSIVE_NAME}({DEFENSIVE})')


if __name__ == '__main__':
    main()
