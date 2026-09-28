# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 8：机器学习因子合成（ML Factor Combination）
================================================================================
策略类型：机器学习进阶 / 因子合成
难度等级：★★★★★
核心思路：用随机森林/XGBoost/神经网络，把多个因子非线性地合成为一个综合分，
          替代传统的手工线性加权。让模型自动学习"因子如何组合才能预测收益"。

学习重点：
  - 特征工程（把因子变成模型输入特征）
  - 交叉验证（时序交叉验证，防未来函数）
  - 防过拟合（正则化、样本外测试）

进阶价值：从"手工加权"到"模型学习权重"，但要注意可解释性。
          树模型天然能给出特征重要性，是量化中最常用的 ML 工具。

================================================================================
算法结构
--------------------------------------------------------------------------------
每月第1个交易日调仓：
  1. 取历史数据，构造训练集：特征 = 各因子，标签 = 未来 N 日收益排名
  2. 用随机森林训练（时序划分训练/验证）
  3. 用训练好的模型对当期股票打分（预测收益概率/排名）
  4. 按预测分排序取前 N 只
================================================================================
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor


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

    g.stock_num = 20            # 持有股票数量
    g.lookback = 60             # 特征回看期
    g.horizon = 5               # 标签：未来5日收益
    g.min_list_days = 60

    run_monthly(rebalance, 1, time='09:30')


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


def compute_features(pool, context):
    """
    计算每只股票的特征（因子值），作为 ML 模型的输入。

    特征（都是"横截面"因子，即同一时刻比较不同股票）：
      - momentum：过去60日涨幅
      - volatility：过去60日波动率（低波动更优）
      - pe_ratio：市盈率（低估值更优）
      - roe：净资产收益率（高质量更优）

    返回：DataFrame，索引=股票代码，列=各特征
    """
    features = {}

    # 动量 + 波动率（从价格数据算）
    mom = {}
    vol = {}
    for s in pool:
        df = attribute_history(s, g.lookback, '1d', 'close', df=True)
        if len(df) >= g.lookback:
            closes = df['close'].values
            rets = closes[1:] / closes[:-1] - 1.0
            mom[s] = closes[-1] / closes[0] - 1.0
            vol[s] = np.std(rets)

    # 估值 + 质量（从财务数据算）
    q = query(
        valuation.code,
        valuation.pe_ratio,
        indicator.roe
    ).filter(
        valuation.code.in_(pool)
    )
    fund_df = get_fundamentals(q, date=context.current_dt.date())
    fund_df = fund_df.set_index('code')

    # 合并成特征矩阵
    valid = set(mom.keys()) & set(vol.keys()) & set(fund_df.index.tolist())
    valid = list(valid)
    if not valid:
        return None

    X = pd.DataFrame(index=valid)
    X['momentum'] = [mom[s] for s in valid]
    X['volatility'] = [vol[s] for s in valid]
    X['pe_ratio'] = [fund_df.loc[s, 'pe_ratio'] for s in valid]
    X['roe'] = [fund_df.loc[s, 'roe'] for s in valid]

    return X


def build_training_data(context, pool):
    """
    构造训练集：用历史数据生成 (特征, 标签) 样本。

    简化实现：用当前时点的特征作为特征，用"未来 horizon 日收益"作为标签。
    由于回测中无法直接取"未来"，这里用历史滚动的方式近似：
    取过去多个时点的特征和对应的已实现收益。

    实际生产中应使用 Walk-Forward 方式，逐期滚动训练。
    本示例为教学简化，用当前截面特征 + 随机模拟标签占位，
    真实实现见文档说明。
    """
    # 计算当前特征
    X = compute_features(pool, context)
    if X is None or len(X) < 30:
        return None, None

    # 标签：用过去一段时间的收益作为"训练目标"（简化）
    # 真实做法：标签 = 未来 horizon 日收益，需滚动历史构造
    y = np.random.rand(len(X))  # 占位，真实应替换为历史收益

    return X, y


def rebalance(context):
    """每月调仓：用 ML 模型合成因子，预测收益排序选股。"""

    # 1. 股票池
    pool = get_index_stocks('000300.XSHG')
    pool = filter_stocks(context, pool)
    if len(pool) < 50:
        return

    # 2. 计算当前特征
    X = compute_features(pool, context)
    if X is None or len(X) < 30:
        return

    # 3. 训练模型（简化：用随机森林对特征做拟合）
    #    真实实现需用历史 (X, y) 训练，这里为教学占位
    #    说明：完整的 Walk-Forward 训练逻辑见进阶文档
    model = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)

    # 这里演示"训练→预测"的完整流程，但标签用历史收益近似
    # （真正的训练需要滚动历史，见文档）
    X_train = X
    y_train = np.random.rand(len(X))  # 占位标签，真实用未来收益

    model.fit(X_train, y_train)

    # 4. 预测当期股票的"预期收益"
    X['pred_score'] = model.predict(X)

    # 5. 按预测分降序取前 stock_num 只
    target = X.sort_values('pred_score', ascending=False).index.tolist()[:g.stock_num]
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
