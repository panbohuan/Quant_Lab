# -*- coding: utf-8 -*-
"""
================================================================================
策略 2：单因子动量选股策略（Momentum）
================================================================================
策略类型：单因子选股（量价因子）
难度等级：★★☆☆☆
核心思路：动量效应——过去一段时间涨幅靠前的股票，未来一段时间倾向于继续跑赢。
          每个调仓日计算股票池内各股过去 N 日收益率，买入涨幅最大的 K 只，等权持有。

本策略新增的关键函数（聚宽）：
  - get_index_stocks(...)         获取指数成分股列表（股票池）
  - get_current_data()            当日实时数据，用于过滤 ST / 停牌 / 退市 / 涨跌停
  - get_security_info(...)        个股基本信息（上市日期，用于过滤次新股）
  - run_monthly(func, monthday)   每月第 monthday 个交易日运行
  - context.portfolio.positions   当前持仓字典，用于遍历卖出
  - order_target(security, 0)     清仓某只股票

================================================================================
过滤函数 filter_stocks 详解（本策略的重点，后续所有选股策略复用同一套逻辑）
--------------------------------------------------------------------------------
1. 剔除 ST / *ST：用 current_data[s].is_st 或名称含 "ST"
2. 剔除退市股：名称含 "退"（退市整理期）
3. 剔除停牌：current_data[s].paused
4. 剔除次新股：上市不足 min_list_days 天（次新股无足够历史数据，且波动异常）
5. 剔除当日无行情：day_open <= 0
6. 剔除涨跌停：价格触及涨停（买入会失败）或跌停（卖出会失败）
================================================================================
"""
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

    # 策略参数
    g.stock_num = 20          # 持有股票数量
    g.lookback = 60           # 动量回看期：过去60个交易日（约3个月）的涨幅
    g.min_list_days = 60      # 次新股过滤：上市不足60个自然日则剔除

    # 每月第一个交易日 09:30 调仓
    run_monthly(rebalance, 1, time='09:30')


def filter_stocks(context, stock_list):
    """
    统一的股票池过滤函数：剔除 ST、退市、停牌、次新股、当日无行情、涨跌停。

    参数：
        context     : 聚宽全局上下文对象
        stock_list  : 待过滤的股票代码列表

    返回：
        过滤后的股票代码列表（list）

    说明：
        这些过滤是"防御性"的，目的是保证选出的股票在当前时刻真的能正常交易，
        同时剔除基本面/交易状态异常的高风险标的。
    """
    current_data = get_current_data()
    yesterday = context.previous_date   # 上一个交易日（用于判断次新股）

    result = []
    for s in stock_list:
        d = current_data[s]

        # 1) 剔除 ST / *ST（财务异常风险警示）
        if d.is_st:
            continue
        # 2) 剔除退市整理期股票（名称含"退"）
        if '退' in d.name:
            continue
        # 3) 剔除停牌股票（停牌期间无法成交）
        if d.paused:
            continue
        # 4) 剔除当日无行情的股票（day_open=0 通常表示未开盘/无交易）
        if d.day_open <= 0:
            continue
        # 5) 剔除次新股（上市时间不足，历史数据不稳定）
        info = get_security_info(s)
        if info is None:
            continue
        if (yesterday - info.start_date).days < g.min_list_days:
            continue
        # 6) 剔除涨停/跌停股（涨停买不进，跌停卖不出）
        #    high_limit/low_limit 分别为当日涨停价、跌停价；停牌时二者相等
        if d.high_limit <= d.last_price:   # 已涨停（或触及涨停价）
            continue
        if d.low_limit >= d.last_price:    # 已跌停
            continue

        result.append(s)

    return result


def rebalance(context):
    """每月调仓：选出动量最强的 stock_num 只股票等权持有。"""

    # 1. 股票池：沪深300成分股（换成 get_all_securities 可用全市场，见文档）
    pool = get_index_stocks('000300.XSHG')

    # 2. 过滤：剔除 ST、退市、停牌、次新、涨跌停等（保证可正常交易）
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 3. 计算每只股票的动量因子：过去 lookback 日收益率
    momentum = {}
    for s in pool:
        df = attribute_history(s, g.lookback, '1d', 'close', df=True)
        # 历史K线不足（如次新股）则跳过
        if len(df) >= g.lookback:
            momentum[s] = df['close'].iloc[-1] / df['close'].iloc[0] - 1

    # 4. 按动量降序排序，取前 stock_num 只
    target = sorted(momentum, key=momentum.get, reverse=True)[:g.stock_num]
    if not target:
        return

    # 5. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)          # 目标股数=0 → 清仓

    # 6. 等权买入：每只股票分配相同金额
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
