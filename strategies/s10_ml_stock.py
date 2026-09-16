# -*- coding: utf-8 -*-
"""
================================================================================
策略 10：机器学习选股（随机森林 Random Forest）
================================================================================
策略类型：机器学习选股（监督学习 · 分类）
难度等级：★★★★★
核心思路：把"因子选股"抽象成监督学习问题——用历史特征（量价因子）预测
          "未来N日是否上涨"（二分类），训练随机森林模型，对当期股票预测
          上涨概率，买入概率最高的 K 只。

本策略新增的关键函数/知识：
  - sklearn.ensemble.RandomForestClassifier  随机森林分类器
  - 特征工程 / 标签构造 / 训练-预测流程
  - get_trade_days(...)                       计算交易日
================================================================================
"""
from jqdata import *
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier


def initialize(context):
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    set_order_cost(
        OrderCost(open_tax=0, close_tax=0.001,
                  open_commission=0.0003, close_commission=0.0003,
                  close_today_commission=0, min_commission=5),
        type='stock'
    )
    set_slippage(FixedSlippage(0.02))
    log.set_level('order', 'error')

    g.universe = '000300.XSHG'   # 股票池：沪深300（机器学习需较大训练集，用指数成分股更稳定）
    g.stock_num = 20             # 持有数量
    g.hold_days = 20             # 每20个交易日重训+调仓一次
    g.label_horizon = 20         # 标签：预测未来20个交易日的涨跌
    g.feature_days = 65          # 特征所需最长回看（60日动量+缓冲）
    g.train_days = 500           # 训练窗口：约2年交易日
    g.sample_step = 10           # 每隔10个交易日采样一个训练样本
    g.last_trade = context.current_dt.date()

    run_daily(check_and_trade, time='09:30')


def check_and_trade(context):
    """每隔 hold_days 个交易日重训并调仓一次。"""
    today = context.current_dt.date()
    elapsed = len(get_trade_days(g.last_trade, today)) - 1
    if elapsed < g.hold_days:
        return
    g.last_trade = today
    train_and_trade(context)


def compute_features(close):
    """从收盘价矩阵计算量价特征（向量化）。
    close: DataFrame，索引=时间，列=股票代码。"""
    f = pd.DataFrame(index=close.columns)
    f['mom_5']   = close.iloc[-1]  / close.iloc[-6]  - 1    # 5日动量
    f['mom_10']  = close.iloc[-1]  / close.iloc[-11] - 1    # 10日动量
    f['mom_20']  = close.iloc[-1]  / close.iloc[-21] - 1    # 20日动量
    f['mom_60']  = close.iloc[-1]  / close.iloc[-61] - 1    # 60日动量
    ret = close.pct_change().iloc[1:]                        # 日收益率
    f['vol_20']  = ret.iloc[-20:].std()                      # 20日波动率
    f['ma_bias'] = close.iloc[-1] / close.iloc[-20:].mean() - 1  # 价格相对20日均线偏离
    return f


def train_and_trade(context):
    # 1. 股票池 + 过滤
    pool = get_index_stocks(g.universe)
    current_data = get_current_data()
    pool = [s for s in pool
            if not current_data[s].is_st and not current_data[s].paused]

    # 2. 一次性拉取足够长的收盘价历史（训练窗口 + 特征回看 + 标签未来）
    total = g.train_days + g.feature_days + g.label_horizon + 10
    close = history(total, '1d', 'close', pool, df=True)
    if close.shape[0] < g.feature_days + g.label_horizon + 10:
        return

    n = len(close)

    # 3. 构造训练集：遍历历史时点，特征用"截至该时点"的数据，标签用"未来"收益（无未来函数）
    X_list, y_list = [], []
    for i in range(g.feature_days, n - g.label_horizon, g.sample_step):
        feats = compute_features(close.iloc[:i + 1])                    # 特征：截至 i
        fwd_ret = close.iloc[i + g.label_horizon] / close.iloc[i] - 1   # 未来label_horizon日收益
        label = (fwd_ret > 0).astype(int)                               # 上涨=1，下跌=0
        X_list.append(feats)
        y_list.append(label)

    X = pd.concat(X_list).replace([np.inf, -np.inf], np.nan).dropna()
    y = pd.concat(y_list).loc[X.index]
    if len(X) < 200:
        return

    # 4. 训练随机森林分类器
    model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
    model.fit(X, y)

    # 5. 用当期特征预测"上涨概率"
    cur = compute_features(close).replace([np.inf, -np.inf], np.nan).dropna()
    cur['proba'] = model.predict_proba(cur)[:, 1]      # 第2列 = 正类（上涨）概率

    target = cur.sort_values('proba', ascending=False).index[:g.stock_num].tolist()

    # 6. 换仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
