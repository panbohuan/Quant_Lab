# -*- coding: utf-8 -*-
"""
================================================================================
策略 3：单因子低估值选股策略（PE / PB 估值因子）
================================================================================
策略类型：单因子选股（基本面·估值因子）
难度等级：★★☆☆☆
核心思路：价值投资——买入"便宜"的股票。市盈率(PE)、市净率(PB)越低代表估值越便宜，
          历史统计上低估值组合长期能跑赢市场（价值溢价）。
          每个调仓日按估值因子从小到大排序，买入最低估的 K 只，等权持有。

本策略新增的关键函数（聚宽）：
  - from jqdata import *                导入聚宽数据模块（query/valuation等）
  - query(...) / get_fundamentals(...)  查询基本面财务数据
  - valuation.pe_ratio / pb_ratio       估值表字段（市盈率/市净率）
================================================================================
"""
from jqdata import *


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
    g.factor = 'pe_ratio'     # 可改为 'pb_ratio' 比较市净率因子

    run_monthly(rebalance, 1, time='09:30')


def rebalance(context):
    # 1. 全市场股票池
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()

    # 2. 过滤 ST、停牌
    current_data = get_current_data()
    pool = [s for s in pool
            if not current_data[s].is_st
            and not current_data[s].paused]

    # 3. 用 query + get_fundamentals 查询估值因子
    q = query(
        valuation.code,          # 股票代码（作为结果索引）
        valuation.pe_ratio,      # 市盈率
        valuation.pb_ratio       # 市净率
    ).filter(
        valuation.code.in_(pool)               # 只查股票池内的股票
    ).order_by(
        valuation.pe_ratio.asc()               # 按PE升序（越便宜越靠前）
    ).limit(g.stock_num * 3)                   # 先取3倍数量，再手动过滤无效值

    df = get_fundamentals(q, date=context.current_dt.date())

    # 4. 清洗：去掉因子缺失值，并剔除负值（PE/PB为负=亏损/资不抵债，无估值意义）
    df = df.dropna(subset=[g.factor])
    df = df[df[g.factor] > 0]

    # 5. 取前 stock_num 只（df 的索引就是股票代码）
    target = df.index.tolist()[:g.stock_num]
    if not target:
        return

    # 6. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 7. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
