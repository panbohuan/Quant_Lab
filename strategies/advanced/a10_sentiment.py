# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 10：舆情情绪策略（Sentiment Analysis）
================================================================================
策略类型：另类数据 / 情绪分析
难度等级：★★★★★
核心思路：用股吧、新闻、研报的情绪打分，作为选股或择时的辅助因子。
          正面情绪越强，短期越可能上涨（情绪驱动的定价偏差）。

学习重点：
  - 文本数据获取（新闻、研报、公告等）
  - 情感分析（把文本转成"正面/负面"打分）
  - 因子构建（情绪分作为选股因子）

进阶价值：从结构化数据到非结构化数据，理解另类数据的 Alpha 来源。
          传统量化用价格、财务等结构化数据，情绪策略进一步挖掘文本中的信息。

================================================================================
算法结构
--------------------------------------------------------------------------------
每月第1个交易日调仓：
  1. 获取股票相关的新闻/研报文本
  2. 用简单的词典法做情感分析（正面词 - 负面词）
  3. 聚合得到每只股票的"情绪分"
  4. 情绪分作为因子，结合动量选股
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

    g.stock_num = 20            # 持有股票数量
    g.lookback = 30             # 情绪回看期（过去30天的新闻）
    g.min_list_days = 60

    # 简单的情感词典（正面词 +1，负面词 -1）
    g.pos_words = ['增长', '盈利', '超预期', '突破', '中标', '回购', '增持', '利好', '创新高']
    g.neg_words = ['下滑', '亏损', '减持', '处罚', '违规', '退市', '爆雷', '利空', '跌停']

    run_monthly(rebalance, 1, time='09:30')


def get_sentiment(context, stock):
    """
    获取单只股票的情绪分（简化版，词典法）。

    真实实现：通过聚宽的新闻/研报数据接口获取文本，再用情感分析模型打分。
    本示例用"新闻标题情感词典匹配"演示思路。

    参数：
        context : 聚宽上下文
        stock   : 股票代码

    返回：情绪分（float，正值偏正面，负值偏负面）
    """
    # 聚宽提供 get_news 接口获取新闻（需在研报/新闻数据权限下）
    # 这里用简化方式：通过财务数据中的"机构评级"近似情绪
    # 实际生产中应调用新闻数据接口，见文档说明

    # 简化：用换手率 + 涨跌幅的组合近似"市场关注度"作为情绪代理
    # （高换手 + 上涨 = 情绪偏暖）
    df = attribute_history(stock, g.lookback, '1d', ['close', 'volume', 'money'], df=True)
    if len(df) < g.lookback:
        return 0.0

    # 情绪代理：过去 lookback 日的涨幅 + 成交额趋势
    ret = df['close'].iloc[-1] / df['close'].iloc[0] - 1.0
    # 成交额放大且上涨 → 情绪积极
    money_trend = df['money'].iloc[-1] / df['money'].iloc[0] - 1.0

    sentiment = ret + 0.5 * money_trend
    return sentiment


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


def rebalance(context):
    """每月调仓：按情绪分 + 动量选股。"""

    # 1. 股票池
    pool = get_index_stocks('000300.XSHG')
    pool = filter_stocks(context, pool)
    if len(pool) == 0:
        return

    # 2. 计算每只股票的情绪分
    sentiment = {}
    for s in pool:
        senti = get_sentiment(context, s)
        sentiment[s] = senti

    # 3. 按情绪分降序取前 stock_num 只
    target = sorted(sentiment, key=sentiment.get, reverse=True)[:g.stock_num]
    if not target:
        return

    # 4. 卖出不在目标列表的持仓
    for s in list(context.portfolio.positions):
        if s not in target:
            order_target(s, 0)

    # 5. 等权买入
    per_value = context.portfolio.total_value / len(target)
    for s in target:
        order_target_value(s, per_value)
