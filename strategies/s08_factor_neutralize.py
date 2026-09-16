# -*- coding: utf-8 -*-
"""
================================================================================
策略 8：因子中性化选股（Barra 风格：市值 + 行业中性化）
================================================================================
策略类型：多因子进阶（因子提纯）
难度等级：★★★★☆
核心思路：原始因子往往"污染"了其他风格的影响。例如动量因子可能与市值、行业强相关。
          中性化 = 用回归把因子里"市值、行业"的影响剔除，取残差作为"纯因子"，
          再按纯因子选股，避免组合在市值/行业上暴露过度。

本策略新增的关键函数/知识：
  - get_industry(...)            查询股票所属行业（申万一级）
  - numpy.log                    市值取对数
  - pandas.get_dummies           行业哑变量编码
  - statsmodels OLS              截面回归
================================================================================
"""
from jqdata import *
import pandas as pd
import numpy as np
import statsmodels.api as sm


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
    g.lookback = 60
    g.factor = 'momentum'     # 待中性化的因子：动量（可换成 roe/pb 等）

    run_monthly(rebalance, 1, time='09:30')


def get_sw1_industry(codes, date):
    """获取每只股票的申万一级行业名称，返回 Series（索引=代码）。"""
    info = get_industry(codes, date=date)   # 返回 dict
    mapping = {}
    for c in codes:
        d = info.get(c)
        if d and 'sw_l1' in d:
            mapping[c] = d['sw_l1']['industry_name']
        else:
            mapping[c] = '未知'
    return pd.Series(mapping)


def neutralize(factor, log_cap, industry):
    """截面回归：factor ~ const + log_cap + 行业哑变量，返回残差（纯因子）。"""
    # 行业哑变量（drop_first 避免完全共线性）
    industry_dummies = pd.get_dummies(industry, drop_first=True)
    X = pd.concat([log_cap, industry_dummies], axis=1)
    X = sm.add_constant(X)          # 加入截距项
    model = sm.OLS(factor, X).fit()
    return model.resid              # 残差 = 剔除市值和行业影响后的因子


def rebalance(context):
    # 1. 全市场股票池 + 过滤
    pool = get_all_securities(['stock'], date=context.current_dt.date()).index.tolist()
    current_data = get_current_data()
    pool = [s for s in pool
            if not current_data[s].is_st and not current_data[s].paused]

    # 2. 查询市值（作为中性化变量之一）
    q = query(valuation.code, valuation.market_cap).filter(valuation.code.in_(pool))
    df = get_fundamentals(q, date=context.current_dt.date())
    df = df[df['market_cap'] > 0]

    # 3. 计算原始因子（动量）
    momentum = {}
    for s in df.index:
        h = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(h) >= g.lookback:
            momentum[s] = h['close'].iloc[-1] / h['close'].iloc[0] - 1
    df['factor'] = pd.Series(momentum)
    df = df.dropna(subset=['factor'])

    if len(df) < g.stock_num:
        return

    # 4. 准备中性化变量：对数市值 + 申万一级行业
    df['log_cap'] = np.log(df['market_cap'])
    df['industry'] = get_sw1_industry(df.index.tolist(), context.current_dt.date())

    # 5. 中性化：取回归残差作为纯因子
    try:
        df['alpha'] = neutralize(df['factor'], df['log_cap'], df['industry'])
    except Exception as e:
        # 回归失败（如样本太少）时，降级为原始因子
        log.warn('中性化回归失败，使用原始因子: %s', e)
        df['alpha'] = df['factor']

    # 6. 按纯因子降序取前 stock_num 只
    target = df.sort_values('alpha', ascending=False).index[:g.stock_num].tolist()

    # 7. 卖出不在目标列表中的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 8. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
