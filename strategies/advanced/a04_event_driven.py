# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 4：事件驱动策略（Event-Driven）
================================================================================
策略类型：另类策略 / 事件驱动
难度等级：★★★★☆
核心思路：围绕财报发布、分红送转、指数调仓、股东增持等事件，在事件前后交易，
          捕捉事件冲击带来的短期定价偏差。

学习重点：
  - 事件数据获取（财报日期、分红送转、股东增持等）
  - 事件窗口选择（事件日前买入，事件后卖出）
  - 防未来函数（用事件"公告日"而非"实际发生日"）

进阶价值：从"连续因子"到"离散事件"，理解事件冲击的短期定价偏差。

================================================================================
算法结构（本策略以"财报发布"事件为例）
--------------------------------------------------------------------------------
每日运行：
  1. 找出未来 N 天内将发布财报（业绩预告/正式财报）的股票
  2. 买入这些股票，持有到财报公告后第 M 天卖出
  3. 核心假设：财报发布前后存在"业绩超预期"的上涨动量

注：聚宽中财报发布日期可通过 get_fundamentals 查询 income 表的 report_date
    或通过 valuation 表。本示例用简化的事件发现逻辑。
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
    g.stock_num = 20            # 最多持有股票数
    g.hold_days = 5             # 事件后持有天数
    g.min_list_days = 60

    # 用于记录每只股票的"买入日期"，到期后卖出
    g.buy_date = {}

    # 每日开盘后检查
    run_daily(trade, time='09:30')


def filter_stocks(context, stock_list):
    """过滤 ST/退市/停牌/次新/涨跌停。"""
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


def find_event_stocks(context):
    """
    找出近期将发布财报的股票（事件发现）。

    简化实现：用财务数据表 income 的 report_date 字段，找出未来 10 天内
    将披露财报的股票。实际生产中应结合业绩预告、快报等更丰富的事件源。

    返回：事件股票列表
    """
    # 查询所有股票的财报披露日期（这里用最近一期财报）
    # 注意：query 需要指定日期，这里取当前日期前能看到的最新披露计划
    q = query(
        income.code,
        income.report_date
    ).filter(
        income.code.in_(get_index_stocks('000300.XSHG'))
    )
    df = get_fundamentals(q, date=context.current_dt.date())
    if df is None or len(df) == 0:
        return []

    df = df.set_index('code')
    event_stocks = []

    today = context.current_dt.date()
    for code in df.index:
        report_date = df.loc[code, 'report_date']
        if report_date is None:
            continue
        # report_date 可能是 datetime.date 或字符串，统一转成 date
        if isinstance(report_date, str):
            from datetime import datetime
            report_date = datetime.strptime(report_date, '%Y-%m-%d').date()
        # 财报将在未来 10 天内披露 → 视为事件
        if 0 <= (report_date - today).days <= 10:
            event_stocks.append(code)

    return event_stocks


def trade(context):
    """每日：发现新事件买入，持有到期卖出。"""

    # 1. 卖出持有超过 hold_days 的股票
    today = context.current_dt.date()
    for s in list(g.buy_date.keys()):
        if (today - g.buy_date[s]).days >= g.hold_days:
            order_target(s, 0)
            del g.buy_date[s]

    # 2. 发现新事件股票
    event_stocks = find_event_stocks(context)
    event_stocks = filter_stocks(context, event_stocks)

    # 3. 买入新事件股票（控制在 stock_num 上限内）
    current_num = len(context.portfolio.positions)
    available = g.stock_num - current_num
    for s in event_stocks[:available]:
        order_target_value(s, context.portfolio.total_value / g.stock_num)
        g.buy_date[s] = today
