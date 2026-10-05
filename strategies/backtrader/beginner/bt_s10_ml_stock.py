# -*- coding: utf-8 -*-
# 【backtrader 本地回测版】运行：python strategies/backtrader/beginner/bt_s10_ml_stock.py
# 对应聚宽版：strategies/joinquant/beginner/s10_ml_stock.py
# 详细讲解：docs/backtrader/beginner/10_ml_stock.md
"""
策略 10：机器学习选股（随机森林 Random Forest）
类型：机器学习选股（监督学习 · 二分类） ｜ 难度：★★★★★
核心思路：把"因子选股"抽象成监督学习问题——用历史量价特征预测
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sklearn.ensemble import RandomForestClassifier                   # noqa: E402

from btlab.datasource import load_daily, load_index_members           # noqa: E402
from btlab.runner import PanelStrategy, run_strategy, load_universe    # noqa: E402

# ============================ 回测参数 ============================
START = '2016-01-01'
END = None
CASH = 1_000_000
BENCHMARK = '000300'
PLOT = os.path.join('results', 'bt_s10_result.png')

UNIVERSE_SIZE = 40
TOPN = 10
HORIZON = 20               # 预测窗口：未来 20 个交易日
MIN_SAMPLES = 400          # 训练样本下限，不足则用等权因子兜底
FEATURE_NAMES = ['mom20', 'mom60', 'vol20', 'ma_dev', 'vol_ratio']


class MLStock(PanelStrategy):
    """随机森林选股：逐期滚动训练，预测下期上涨概率并买入概率最高的 TOPN。"""

    params = (('topn', TOPN), ('horizon', HORIZON), ('rebalance', 'monthly'),
              ('min_samples', MIN_SAMPLES),)

    def __init__(self):
        super().__init__()
        self.X, self.y = [], []
        self.pending = []          # 已收集特征、等待标签确认的样本
        self.model = None

    # ---------- 特征工程 ----------
    def _features(self, d):
        c20 = self.hist_close(d, 21)
        c60 = self.hist_close(d, 61)
        if c20 is None or c60 is None:
            return None
        if c60[0] <= 0 or min(c60) <= 0:
            return None
        vols = d.volume.get(size=61)
        if len(vols) < 61:
            return None
        rets = pd.Series(c20, dtype=float).pct_change().dropna()
        return [
            c20[-1] / c20[0] - 1.0,                        # 20 日动量
            c60[-1] / c60[0] - 1.0,                        # 60 日动量
            float(rets.std()),                             # 20 日波动率
            c60[-1] / (sum(c60) / len(c60)) - 1.0,         # 均线偏离度
            float(np.mean(vols[-5:]) / (np.mean(vols) + 1e-9)),   # 量比
        ]

    # ---------- 给到期样本打标签 ----------
    def _label_pending(self):
        still = []
        for code, feats, p0, bars0, miss in self.pending:
            d = self.getdatabyname(code)
            moved = len(d) - bars0
            if moved >= self.p.horizon:                    # 已过预测窗口，标签可确认
                p1 = d.close[0]
                if p0 > 0 and p1 > 0:
                    self.X.append(feats)
                    self.y.append(1 if p1 / p0 - 1.0 > 0 else 0)
            elif moved == 0 and miss >= 4:
                continue                                   # 长期停牌/退市，丢弃不计
            else:
                still.append((code, feats, p0, bars0, miss + (1 if moved == 0 else 0)))
        self.pending = still

    def on_rebalance(self, cur):
        # 1) 先确认上一批样本的标签（时序纪律：只能用已实现收益）
        self._label_pending()

        # 2) 收集本期全部股票的特征
        feats, price = {}, {}
        for d in self.tradables:
            if not self.live(d, cur):
                continue
            f = self._features(d)
            if f is None:
                continue
            feats[d._name] = f
            price[d._name] = d.close[0]
        if len(feats) < self.p.topn:
            return

        # 3) 训练 + 预测
        codes = list(feats)
        if len(self.X) >= self.p.min_samples and len(set(self.y)) > 1:
            self.model = RandomForestClassifier(
                n_estimators=200, max_depth=5, min_samples_leaf=20,
                random_state=42, n_jobs=-1)
            self.model.fit(self.X, self.y)
            proba = self.model.predict_proba([feats[c] for c in codes])[:, 1]
            order = [codes[i] for i in np.argsort(-proba)]
            names = order[:self.p.topn]
            top_p = max(proba)
            print(f'  [{cur}] ML 预测（样本 {len(self.X)} 条）最高上涨概率 {top_p:.3f}')
        else:
            # 样本不足：用 20 日动量兜底（等价于"因子选股"）
            order = sorted(codes, key=lambda c: feats[c][0], reverse=True)
            names = order[:self.p.topn]
            print(f'  [{cur}] 样本不足（{len(self.X)}/{self.p.min_samples}），'
                  f'暂用 20 日动量兜底')

        # 4) 登记本期样本，等 HORIZON 个交易日后打标签
        for c in codes:
            self.pending.append((c, feats[c], price[c], len(self.getdatabyname(c)), 0))

        self.equal_weight_order(names, cur)


def main():
    print(f'[1/3] 获取沪深300成分股（前 {UNIVERSE_SIZE} 只）...')
    codes = load_index_members('000300')[:UNIVERSE_SIZE]

    print('[2/3] 加载日线 ...')
    data = load_universe(codes, start=START, end=END, adjust='qfq', label='股票池')
    data['__CAL__'] = load_daily(BENCHMARK, start=START, end=END)

    print('[3/3] 开始 backtrader 回测 ...')
    run_strategy(MLStock, data, cash=CASH, benchmark=BENCHMARK,
                 title='策略10 机器学习选股（backtrader · 随机森林）',
                 plot_path=PLOT)


if __name__ == '__main__':
    main()
