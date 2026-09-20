# -*- coding: utf-8 -*-
"""
================================================================================
策略 9：因子 IC/IR 加权选股（动态权重多因子）
================================================================================
策略类型：多因子进阶（因子有效性度量 + 动态加权）
难度等级：★★★★★
核心思路：前面策略用"等权"合成因子，但不同因子的有效性随时间变化。
          本策略引入 IC（信息系统）与 IR（信息比率）来度量每个因子的有效性，
          用滚动 IC 的均值/标准差（IR）作为因子权重，动态加权合成综合分。

本策略新增的关键函数/知识：
  - history(count, unit, field, security_list)   批量取行情（向量化）
  - IC / IR 概念（因子与未来收益的相关性）
  - 滚动窗口动态权重
  - df.set_index('code')                         【关键】把查询结果索引设为股票代码
================================================================================
"""
from jqdata import *
import pandas as pd
import numpy as np
from datetime import timedelta


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

    g.stock_num = 30
    g.lookback = 60            # 动量回看期
    g.ic_window = 12           # 滚动IC窗口（过去12期）
    g.min_list_days = 60

    # 因子列表与方向（+1 越大越好，-1 越小越好）
    g.factor_names = ['momentum', 'pb', 'roe', 'market_cap']
    g.direction = {'momentum': 1, 'pb': -1, 'roe': 1, 'market_cap': -1}

    # 用于记录历史：每个因子的 IC 序列；上一期因子快照
    g.ic = {f: [] for f in g.factor_names}
    g.snapshots = []           # 元素为 {'factors': DataFrame, 'price': Series}

    run_monthly(monthly, 1, time='09:30')


def filter_stocks(context, stock_list):
    """统一的股票池过滤函数（剔除 ST/退市/停牌/次新/涨跌停）。"""
    current_data = get_current_data()
    yesterday = context.previous_date
    result = []
    for s in stock_list:
        d = current_data[s]
        if d.is_st or '退' in d.name:
            continue
        if d.paused:
            continue
        if d.day_open <= 0:
            continue
        info = get_security_info(s)
        if info is None or (yesterday - info.start_date).days < g.min_list_days:
            continue
        if d.high_limit <= d.last_price or d.low_limit >= d.last_price:
            continue
        result.append(s)
    return result


def get_universe(context):
    """股票池：全市场 + 过滤 ST/停牌/退市/次新/涨跌停。"""
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    return filter_stocks(context, pool)


def compute_factors(codes, context):
    """计算四个因子的横截面值，返回 DataFrame（索引=代码，列=因子名）。"""
    # 基本面因子：pb / roe / market_cap
    q = query(
        valuation.code, valuation.pb_ratio, valuation.market_cap, indicator.roe
    ).filter(valuation.code.in_(codes))
    df = get_fundamentals(q, date=context.current_dt.date())
    df = df.set_index('code')              # 【关键】索引设为股票代码
    df = df.dropna()
    df = df[df['pb_ratio'] > 0]

    # 量价因子：动量（用 history 批量取，向量化计算，比逐股循环快得多）
    close_df = history(g.lookback, '1d', 'close', df.index.tolist(), df=True)
    momentum = close_df.iloc[-1] / close_df.iloc[0] - 1    # 过去60日涨幅
    df['momentum'] = momentum

    df = df.rename(columns={'pb_ratio': 'pb', 'roe': 'roe', 'market_cap': 'market_cap'})
    return df[g.factor_names].dropna()


def get_last_close(codes):
    """批量获取最新收盘价（最近一根已完成的日K线），返回 Series。"""
    df = history(1, '1d', 'close', codes, df=True)
    return df.iloc[-1]


def monthly(context):
    # 1. 股票池
    codes = get_universe(context)
    if len(codes) == 0:
        return

    # 2. 计算当期因子值
    factors = compute_factors(codes, context)
    if len(factors) < g.stock_num:
        return
    cur_price = get_last_close(factors.index.tolist())

    # 3. 用上一期快照计算各因子的 IC（因子值与未来一期收益的相关性）
    if g.snapshots:
        prev = g.snapshots[-1]
        prev_factors, prev_price = prev['factors'], prev['price']
        realized_ret = cur_price / prev_price - 1           # 上期实际收益
        for f in g.factor_names:
            common = prev_factors[f].dropna().index.intersection(realized_ret.dropna().index)
            if len(common) > 20:
                ic = prev_factors[f].loc[common].corr(realized_ret.loc[common])
                g.ic[f].append(ic)
        # 滚动窗口裁剪
        for f in g.factor_names:
            g.ic[f] = g.ic[f][-g.ic_window:]

    # 4. 存储当期快照（只保留最近两期）
    g.snapshots.append({'factors': factors, 'price': cur_price})
    g.snapshots = g.snapshots[-2:]

    # 5. 用 IR（IC均值/IC标准差）作为因子权重；无历史时等权
    weights = {}
    for f in g.factor_names:
        ics = g.ic[f]
        weights[f] = (np.mean(ics) / (np.std(ics) + 1e-12)) if len(ics) > 0 else 1.0

    # 6. 标准化 + 方向 + 加权合成
    score = pd.Series(0.0, index=factors.index)
    for f in g.factor_names:
        z = (factors[f] - factors[f].mean()) / (factors[f].std() + 1e-12)
        score += weights[f] * g.direction[f] * z

    target = score.sort_values(ascending=False).index[:g.stock_num].tolist()

    # 7. 换仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)

    # 8. 输出当期因子权重，便于观察（调试用）
    log.info('因子IR权重: %s', {k: round(v, 3) for k, v in weights.items()})
