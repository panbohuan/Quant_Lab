# -*- coding: utf-8 -*-
"""
================================================================================
策略 6：双因子组合选股（动量 + 市值，排序打分法）
================================================================================
策略类型：双因子选股（量价 + 规模）
难度等级：★★★☆☆
核心思路：单因子过于单一，容易受单一风格影响。本策略把两个因子合成：
          动量（越大越好）+ 市值（越小越好）。
          方法：分别对两个因子排名，再把两个排名相加得到综合分，
          选综合分最小（即综合排名最靠前）的 K 只。

本策略新增的关键函数/知识：
  - pandas Series.rank()            因子值转"排名"
  - Series.intersection / 索引对齐  多因子数据对齐
  - 因子合成：排序打分法（Rank Sum）
  - df.set_index('code')            【关键】把查询结果索引设为股票代码
================================================================================
"""
from jqdata import *
import pandas as pd
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
    g.lookback = 60         # 动量回看期
    g.min_list_days = 60    # 次新股过滤天数

    run_monthly(rebalance, 1, time='09:30')


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


def rebalance(context):
    # 1. 全市场股票池 + 过滤
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 2. 因子一：市值（越小越好），用 query 查询
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(pool))
    mkt_df = get_fundamentals(q, date=context.current_dt.date())
    mkt_df = mkt_df.set_index('code')                    # 【关键】索引设为股票代码
    mkt_df = mkt_df[mkt_df['market_cap'] > 0]

    # 3. 因子二：动量（越大越好），用历史行情计算
    momentum = {}
    for s in mkt_df.index:
        h = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(h) >= g.lookback:
            momentum[s] = h['close'].iloc[-1] / h['close'].iloc[0] - 1
    mom = pd.Series(momentum)

    # 4. 对齐两个因子的股票集合（只保留两个因子都有效的股票）
    codes = mkt_df.index.intersection(mom.index)
    if len(codes) < g.stock_num:
        return

    # 5. 排序打分法：
    #    动量降序排名（涨幅最大的排第1，rank 值最小）
    #    市值升序排名（市值最小的排第1）
    mom_rank = mom[codes].rank(ascending=False)
    mkt_rank = mkt_df.loc[codes, 'market_cap'].rank(ascending=True)
    total_rank = mom_rank + mkt_rank          # 综合排名分，越小越好

    # 6. 取综合排名最靠前的 stock_num 只
    target = total_rank.sort_values().index[:g.stock_num].tolist()

    # 7. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 8. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
