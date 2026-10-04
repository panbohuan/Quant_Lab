# -*- coding: utf-8 -*-
# ==========================================================================================
# 【聚宽原生框架策略 · 云端运行】
# 本文件使用聚宽平台内置 API（initialize / run_daily / attribute_history / order_target_value 等），
# 无需任何 import、无需本地安装依赖。
# 运行方式：登录 https://www.joinquant.com → 策略研究/我的策略 → 新建策略 → 粘贴本文件 → 编译运行。
# 本地的可运行版本（backtrader 框架 + 免费数据源）：见 strategies/backtrader/ 下的同名文件。
# ==========================================================================================
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
  - query(...) / get_fundamentals(...)   查询基本面财务数据（聚宽内置 API）
  - query(...) / get_fundamentals(...)  查询基本面财务数据
  - valuation.pe_ratio / pb_ratio       估值表字段（市盈率/市净率）
  - df.set_index('code')                【关键】把查询结果的索引设为股票代码

================================================================================
【重要 Bug 修复说明】
--------------------------------------------------------------------------------
get_fundamentals 返回的 DataFrame，其索引是 0,1,2,... 的数字序号，而不是股票代码。
如果不调用 df.set_index('code')，后续 df.index.tolist() 拿到的是一串数字，
导致 order_target_value 拿到无效代码、无法正常下单交易。
因此所有用到 get_fundamentals 的策略，都必须：
    df = get_fundamentals(q, date=...)
    df = df.set_index('code')   # 把"code"列设为索引
================================================================================
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

    g.stock_num = 30
    g.factor = 'pe_ratio'       # 可改为 'pb_ratio' 比较市净率因子
    g.min_list_days = 60        # 次新股过滤天数

    run_monthly(rebalance, 1, time='09:30')

def filter_stocks(context, stock_list):
    """统一的股票池过滤函数（同策略2，剔除 ST/退市/停牌/次新/涨跌停）。"""
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
    # 1. 全市场股票池
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()

    # 2. 过滤 ST、退市、停牌、次新、涨跌停
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 3. 用 query + get_fundamentals 查询估值因子
    q = query(
        valuation.code,          # 股票代码（查询后设为索引）
        valuation.pe_ratio,      # 市盈率
        valuation.pb_ratio       # 市净率
    ).filter(
        valuation.code.in_(pool)               # 只查股票池内的股票
    ).order_by(
        valuation.pe_ratio.asc()               # 按PE升序（越便宜越靠前）
    )

    df = get_fundamentals(q, date=context.current_dt.date())

    # 【关键修复】把"code"列设为 DataFrame 的索引，这样 df.index 就是股票代码
    df = df.set_index('code')

    # 4. 清洗：去掉因子缺失值，并剔除负值（PE/PB为负=亏损/资不抵债，无估值意义）
    df = df.dropna(subset=[g.factor])
    df = df[df[g.factor] > 0]

    # 5. 取前 stock_num 只（df 的索引现在就是股票代码）
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
