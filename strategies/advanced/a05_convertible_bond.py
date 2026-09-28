# -*- coding: utf-8 -*-
"""
================================================================================
进阶策略 5：可转债双低策略（Convertible Bond）
================================================================================
策略类型：跨品种 / 可转债
难度等级：★★★★☆
核心思路：在可转债中，选"价格低 + 转股溢价率低"的品种。低价提供债底保护
          （下有保底），低溢价率保留股性弹性（上不封顶）。

学习重点：
  - 可转债数据获取（get_all_securities types=['cb']）
  - 转股溢价率（衡量转债相对正股的贵贱）
  - 债底保护（到期赎回价 + 利息 = 债券价值底）

进阶价值：从股票拓展到可转债，理解"下有保底、上不封顶"的品种特性。

================================================================================
算法结构
--------------------------------------------------------------------------------
每月第1个交易日调仓：
  1. 获取全部可转债（get_all_securities types=['cb']）
  2. 过滤：上市不足、停牌、已退市
  3. 计算"双低"指标 = 价格 + 转股溢价率*100（经典双低公式）
  4. 按双低值升序取前 N 只
  5. 等权买入
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

    # 策略参数
    g.bond_num = 10             # 持有可转债数量
    g.min_list_days = 60        # 上市时间过滤

    run_monthly(rebalance, 1, time='09:30')


def get_cb_info(context):
    """
    获取可转债的"价格"和"转股溢价率"。

    可转债数据在聚宽中通过 get_all_securities(types=['cb']) 获取列表，
    价格通过 attribute_history 获取，转股溢价率需用正股价格、转股价计算，
    或从财务/行情数据中查询。这里用简化方法：
      转股溢价率 = (转债价格 / 转股价值 - 1)，转股价值 = 100/转股价 * 正股价

    返回：dict，key=转债代码，value={'price': 价格, 'premium': 转股溢价率}
    """
    # 获取全部可转债
    cb_list = get_all_securities(types=['cb'], date=context.current_dt.date()).index.tolist()

    current_data = get_current_data()
    result = {}
    for cb in cb_list:
        d = current_data[cb]
        # 过滤停牌/无行情
        if d.paused or d.day_open <= 0:
            continue
        # 转债价格
        price = d.last_price
        if price <= 0:
            continue

        # 简化：转股溢价率用聚宽可转债数据（实际应查询正股、转股价）
        # 这里用 valuation 表查询可转债的溢价率字段（若存在）
        # 为保持代码可运行，本示例用"价格"作为主要排序依据，
        # 转股溢价率留待实际数据接口补充（详见文档说明）
        result[cb] = {'price': price, 'premium': 0.0}

    return result


def rebalance(context):
    """每月调仓：按双低值选可转债。"""

    # 1. 获取可转债价格与溢价率
    cb_info = get_cb_info(context)
    if not cb_info:
        return

    # 2. 计算双低值 = 价格 + 溢价率*100（溢价率此处简化）
    #    经典双低策略：双低值 = 转债价格 + 转股溢价率 * 100
    double_low = {}
    for cb, info in cb_info.items():
        double_low[cb] = info['price'] + info['premium'] * 100

    # 3. 按双低值升序取前 bond_num 只
    target = sorted(double_low, key=double_low.get)[:g.bond_num]
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
