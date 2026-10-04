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
策略 7：多因子打分模型（四因子：估值 + 质量 + 动量 + 规模）
================================================================================
策略类型：多因子选股（打分法 + z-score 标准化）
难度等级：★★★★☆
核心思路：综合四大类经典因子，用 z-score 标准化后按方向加权合成综合分：
            + 质量(ROE，越高越好)
            - 估值(PB，越低越好)
            + 动量(60日涨幅，越高越好)
            - 规模(市值，越小越好)
          选综合分最高的 K 只，等权持有。

本策略新增的关键函数/知识：
  - z-score 标准化（(x-均值)/标准差）
  - 因子方向处理（正负号）
  - 多因子加权合成
  - df.set_index('code')            【关键】把查询结果索引设为股票代码
================================================================================
"""
import pandas as pd
import numpy as np
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
    g.lookback = 60          # 动量回看期
    g.min_list_days = 60

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

def zscore(series):
    """z-score 标准化：把因子值转换为均值为0、标准差为1的分布。

    公式：z = (x - mean) / std
    分母加 1e-12 防止标准差为 0 时除零报错。
    """
    return (series - series.mean()) / (series.std() + 1e-12)

def rebalance(context):
    # 1. 全市场股票池 + 过滤
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 2. 查询基本面因子（估值 + 质量 + 规模）
    q = query(
        valuation.code,
        valuation.pb_ratio,          # 估值：市净率（越低越好）
        valuation.market_cap,        # 规模：总市值（越小越好）
        indicator.roe                # 质量：ROE（越高越好）
    ).filter(valuation.code.in_(pool))

    df = get_fundamentals(q, date=context.current_dt.date())
    df = df.set_index('code')                     # 【关键】索引设为股票代码
    df = df.dropna()                              # 剔除缺失
    df = df[df['pb_ratio'] > 0]                   # 剔除负PB

    # 3. 计算动量因子（越高越好）
    momentum = {}
    for s in df.index:
        h = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(h) >= g.lookback:
            momentum[s] = h['close'].iloc[-1] / h['close'].iloc[0] - 1
    df['momentum'] = pd.Series(momentum)
    df = df.dropna(subset=['momentum'])

    if len(df) < g.stock_num:
        return

    # 4. 各因子 z-score 标准化后按方向加权合成
    #    正号 = 越大越好，负号 = 越小越好
    df['score'] = (
        zscore(df['roe'])            # 质量 +
        - zscore(df['pb_ratio'])     # 估值 -
        + zscore(df['momentum'])     # 动量 +
        - zscore(df['market_cap'])   # 规模 -
    )

    # 5. 按综合分降序取前 stock_num 只
    target = df.sort_values('score', ascending=False).index[:g.stock_num].tolist()

    # 6. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 7. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
