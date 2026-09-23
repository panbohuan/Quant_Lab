# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 9：高频均值回归策略（Intraday Mean Reversion）
================================================================================
策略类型：日内交易 / 均值回归
难度等级：★★★★★
核心思路：在分钟级数据上，捕捉短期超跌反弹。比如开盘 30 分钟跌幅超过 2% 的
          股票，日内可能反弹。利用"过度反应"后的均值回归效应。

学习重点：
  - 分钟数据获取（get_price frequency='minute' / get_bars）
  - 日内交易成本（T+1 约束、手续费、滑点对高频策略的影响）
  - 超跌反弹的统计规律

进阶价值：从日频到日内，理解高频交易的逻辑和成本结构。
          高频策略的核心不是"预测准"，而是"成本控制"——交易太频繁，
          手续费和滑点会吃掉所有收益。

================================================================================
算法结构
--------------------------------------------------------------------------------
每分钟运行（run_daily 分钟级）：
  1. 获取当日开盘至今的分钟数据
  2. 计算开盘以来累计跌幅
  3. 若某股开盘30分钟内跌幅超过阈值（如 -2%），标记为"超跌"
  4. 买入超跌股，博取日内反弹（注意 T+1：当日买入次日才能卖）
================================================================================
"""


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

    g.drop_threshold = -0.02     # 超跌阈值：开盘以来跌幅超过 -2%
    g.max_hold = 5               # 最多持有股票数
    g.min_list_days = 60

    # 记录已买入的股票（当日不再重复买入）
    g.bought_today = set()

    # 每分钟运行（分钟级回测）
    run_daily(minute_trade, time='every_bar')


def minute_trade(context):
    """每分钟检查：发现超跌股则买入，博取反弹。"""

    # 只在前 30 分钟内执行买入（开盘超跌最有意义）
    current_time = context.current_dt.time()
    if current_time.hour < 9 or (current_time.hour == 9 and current_time.minute < 30):
        return
    if current_time.hour > 10:  # 10点后不再买入
        return

    # 1. 股票池
    pool = get_index_stocks('000300.XSHG')

    # 2. 计算每只股票"开盘至今"的累计跌幅
    current_data = get_current_data()
    for s in pool:
        # 已买入或已持有则跳过
        if s in g.bought_today or s in context.portfolio.positions:
            continue

        d = current_data[s]
        if d.paused or d.day_open <= 0:
            continue

        # 开盘价 day_open，当前价 last_price
        open_price = d.day_open
        last_price = d.last_price
        if open_price <= 0:
            continue

        # 开盘以来跌幅
        change = last_price / open_price - 1.0

        # 超跌（跌幅超过阈值）且未跌停 → 买入博反弹
        if change <= g.drop_threshold and last_price < d.high_limit:
            # 买入
            per_value = context.portfolio.total_value / g.max_hold
            order_target_value(s, per_value)
            g.bought_today.add(s)

            # 达到持仓上限则停止
            if len(g.bought_today) >= g.max_hold:
                return


def after_trading_end(context):
    """收盘后：清空当日买入记录，次日重新开始。"""
    g.bought_today = set()
