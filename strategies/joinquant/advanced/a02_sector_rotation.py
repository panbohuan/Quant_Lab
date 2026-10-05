# -*- coding: utf-8 -*-
# 【聚宽原生策略 · 云端运行】粘贴到 joinquant.com 策略编辑器即可，无需本地依赖
# 本地可运行版：strategies/backtrader/advanced/bt_a02_sector_rotation.py
# 详细讲解：docs/joinquant/advanced/02_sector_rotation.md
"""
策略 2：行业轮动策略（Sector Rotation）
类型：中观配置 / 行业轮动 ｜ 难度：★★★★☆
核心思路：在申万一级行业之间轮动，买入动量最强（或估值最低）的 3-5 个行业，
"""
from datetime import timedelta

# ============================ 回测设置说明 ============================
# 回测区间 / 初始资金：在聚宽策略编辑器右上角的「回测面板」中设置（无需改代码）。
# 基准指数：由 initialize() 中的 set_benchmark(BENCHMARK) 指定。
# 以下参数可在代码中直接修改，改完点击「编译运行」即生效。
BENCHMARK    = '000300.XSHG'  # 基准：沪深300指数

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
    g.industry_num = 3           # 轮动的行业数量（3-5个）
    g.stock_per_industry = 10    # 每个行业选多少只股票
    g.lookback = 60              # 动量回看期（交易日）
    g.min_list_days = 60         # 次新股过滤

    # 每月第1个交易日 09:30 调仓
    run_monthly(rebalance, 1, time='09:30')

def get_industry_momentum(context, industries, lookback):
    """
    计算每个行业的动量（过去 lookback 日涨跌幅）。

    行业动量的衡量方式：用申万一级行业指数（如 801010.SI 等）的涨跌幅。
    聚宽中，行业指数代码可通过 get_industries(name='sw_l1') 拿到 index 字段。

    参数：
        context    : 聚宽上下文
        industries : 行业 DataFrame（get_industries 返回）
        lookback   : 回看窗口

    返回：
        dict，key=行业代码，value=行业动量（涨跌幅）
    """
    momentum = {}
    for industry_code in industries.index:
        # 行业指数代码通常以 .SI 结尾（申万指数），需从 industries 的 index_code 列取
        idx_code = industries.loc[industry_code, 'index_code']
        df = attribute_history(idx_code, lookback, '1d', 'close', df=True)
        if len(df) >= lookback:
            momentum[industry_code] = df['close'].iloc[-1] / df['close'].iloc[0] - 1
    return momentum

def filter_stocks(context, stock_list):
    """过滤 ST/退市/停牌/次新/涨跌停（与入门篇相同的防御性过滤）。"""
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
    """每月调仓：先选行业，再在行业内选股。"""

    # 1. 获取申万一级行业列表（含行业指数代码）
    industries = get_industries(name='sw_l1', date=context.current_dt.date())

    # 2. 计算每个行业的动量，选出最强的 industry_num 个行业
    industry_mom = get_industry_momentum(context, industries, g.lookback)
    if not industry_mom:
        return
    top_industries = sorted(industry_mom, key=industry_mom.get, reverse=True)[:g.industry_num]

    # 3. 收集这些行业的成分股
    candidates = []
    for industry_code in top_industries:
        stocks = get_industry_stocks(industry_code, date=context.current_dt.date())
        candidates.extend(stocks)

    # 4. 过滤
    candidates = filter_stocks(context, candidates)
    if not candidates:
        return

    # 5. 在候选股中，按个股动量选出 stock_per_industry * industry_num 只
    #    （这里简单起见，直接按个股动量取前 N 只，跨行业）
    stock_mom = {}
    for s in candidates:
        df = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(df) >= g.lookback:
            stock_mom[s] = df['close'].iloc[-1] / df['close'].iloc[0] - 1

    target = sorted(stock_mom, key=stock_mom.get, reverse=True)[:g.stock_per_industry * g.industry_num]
    if not target:
        return

    # 6. 卖出不在目标列表的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 7. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
