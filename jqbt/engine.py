# -*- coding: utf-8 -*-
"""
jqbt.engine —— 本地回测引擎核心
================================================================================
自研轻量回测引擎，让聚宽风格策略在本地（PyCharm）一键回测。

核心能力：
  1. 调度：支持 run_daily / run_weekly / run_monthly 定时任务；
  2. 撮合：order / order_value / order_target / order_target_value，含手续费与滑点；
  3. 持仓与资金：维护现金、持仓市值、总资产；
  4. 记录：每日净值、持仓、成交明细；
  5. 绩效：年化收益、累计收益、最大回撤、夏普、胜率、换手率等。

用法（策略文件中）：
    from jqbt import run_backtest
    # ... 定义 initialize(context) 与调仓函数 ...
    run_backtest(initialize, start_date='2016-01-01', end_date='2026-01-01',
                 initial_cash=1000000, benchmark='000300.XSHG')
================================================================================
"""
import datetime as dt

import numpy as np
import pandas as pd

from . import data as _data
from . import api as _api


# ============================ 上下文对象 ============================

class Portfolio(object):
    """组合账户：现金、持仓、总资产。"""

    def __init__(self, cash):
        self.starting_cash = cash
        self.cash = cash
        self.positions = {}      # code -> Position
        self.total_value = cash  # 总资产（现金 + 持仓市值）

    def update_total_value(self, prices):
        """用当日价格更新持仓市值与总资产（负持仓=空头，市值为负）。"""
        market_value = 0.0
        for code, pos in self.positions.items():
            if code in prices and prices[code] is not None:
                pos.price = prices[code]
                pos.value = pos.amount * prices[code]
                market_value += pos.value
        self.total_value = self.cash + market_value


class Position(object):
    def __init__(self, code, amount=0, price=0.0):
        self.code = code
        self.amount = amount          # 持股数量
        self.price = price            # 当前价格
        self.value = amount * price   # 当前市值
        self.avg_cost = price if amount > 0 else 0.0  # 持仓均价


class Context(object):
    """聚宽风格上下文，策略函数里通过 context 访问。"""

    def __init__(self):
        self.portfolio = None
        self.current_dt = None      # 当前时间（datetime.datetime）
        self.current_date = None    # 当前日期（datetime.date）
        self.previous_date = None   # 上一交易日
        self.benchmark = None
        self.order_cost = None
        self.slippage = None


# ============================ 定时任务 ============================

class _Scheduler(object):
    """定时任务调度器，模拟聚宽的 run_daily / run_weekly / run_monthly。"""

    def __init__(self):
        self.tasks = []  # 每个元素: dict(kind, func, time, extra)

    def run_daily(self, func, time='09:30'):
        self.tasks.append({'kind': 'daily', 'func': func, 'time': time})

    def run_weekly(self, func, weekday, time='09:30'):
        self.tasks.append({'kind': 'weekly', 'func': func, 'time': time, 'weekday': weekday})

    def run_monthly(self, func, monthday, time='09:30'):
        self.tasks.append({'kind': 'monthly', 'func': func, 'time': time, 'monthday': monthday})

    def due_tasks(self, current_date):
        """返回当前日期应执行的任务列表。"""
        due = []
        for t in self.tasks:
            if t['kind'] == 'daily':
                due.append(t['func'])
            elif t['kind'] == 'weekly':
                # 聚宽 run_weekly(weekday=1) 表示每周第 1 个交易日，而非周一
                # 这里用"周内第 N 个交易日"近似：判断当前日期是该周的第几个交易日
                if self._is_nth_trade_day_of_week(current_date, t['weekday']):
                    due.append(t['func'])
            elif t['kind'] == 'monthly':
                if self._is_nth_trade_day_of_month(current_date, t['monthday']):
                    due.append(t['func'])
        return due

    def _is_nth_trade_day_of_week(self, date, n):
        return self._nth_trade_day(date, 'week') == n

    def _is_nth_trade_day_of_month(self, date, n):
        return self._nth_trade_day(date, 'month') == n

    def _nth_trade_day(self, date, period):
        """返回 date 在其周期（week/month）内是第几个交易日。"""
        if period == 'week':
            days = [d for d in self.trade_days
                    if d.isocalendar()[:2] == date.isocalendar()[:2]]
        else:
            days = [d for d in self.trade_days if (d.year, d.month) == (date.year, date.month)]
        for i, d in enumerate(days, 1):
            if d == date:
                return i
        return -1

    def set_trade_days(self, trade_days):
        self.trade_days = trade_days


# ============================ 撮合 Broker ============================

class _Broker(object):
    """负责撮合下单，计算手续费与滑点。"""

    def __init__(self, context, order_cost, slippage):
        self.context = context
        self.order_cost = order_cost
        self.slippage = slippage
        self.prices = {}  # 当日价格表（由引擎在开盘前填充）
        self.trades = []  # 成交记录
        self._set_broker()

    def _set_broker(self):
        _api._set_broker(self)

    def _exec_price(self, code, side):
        """计算成交价：买入价 + 滑点，卖出价 - 滑点。"""
        px = self.prices.get(code)
        if px is None:
            # 动态取当日收盘价（截至当前回测日）
            px = self._fetch_price(code)
            if px is not None:
                self.prices[code] = px
        if px is None or px <= 0:
            raise RuntimeError(f"无法获取 {code} 当日价格，无法成交（可能停牌或无行情）。")
        slip = self.slippage.value / 10000.0  # 万分比转小数
        if side == 'buy':
            return px * (1 + slip)
        else:
            return px * (1 - slip)

    def _fetch_price(self, code):
        df = _data.get_price(code, frequency='daily', fields=['close'], fq='pre', count=400)
        if df is not None and len(df) > 0:
            return float(df['close'].iloc[-1])
        return None

    def _commission(self, value, side):
        """计算佣金与印花税。"""
        oc = self.order_cost
        if side == 'buy':
            tax = value * oc.open_tax
            commission = value * oc.open_commission
        else:
            tax = value * oc.close_tax
            commission = value * oc.close_commission
        if commission > 0 and commission < oc.min_commission:
            commission = oc.min_commission
        return tax + commission

    def order(self, code, amount):
        """按股数下单。amount>0 买入（平空/开多），<0 卖出（平多/开空）。"""
        if amount == 0:
            return
        if amount > 0:
            self._buy(code, amount)
        else:
            self._sell(code, -amount)

    def order_value(self, code, value):
        """按金额下单。value>0 买入，<0 卖出。"""
        px = self._exec_price(code, 'buy' if value > 0 else 'sell')
        amount = int(abs(value) / px)
        if value > 0:
            self._buy(code, amount)
        else:
            self._sell(code, amount)

    def order_target(self, code, target_amount):
        """调整到目标股数（target_amount 可为负，表示净空头）。"""
        pos = self.context.portfolio.positions.get(code)
        cur = pos.amount if pos else 0
        delta = target_amount - cur
        if delta > 0:
            self._buy(code, delta)
        elif delta < 0:
            self._sell(code, -delta)

    def order_target_value(self, code, target_value):
        """调整到目标市值。target_value 为负表示建立空头。"""
        px = self._exec_price(code, 'buy' if target_value > 0 else 'sell')
        target_amount = int(target_value / px)
        self.order_target(code, target_amount)

    def _buy(self, code, amount):
        """买入：若已有空头先平空，否则开多。"""
        if amount <= 0:
            return
        price = self._exec_price(code, 'buy')
        port = self.context.portfolio
        pos = port.positions.get(code)

        # 若当前是空头，先平掉空头部分
        if pos is not None and pos.amount < 0:
            close = min(amount, -pos.amount)
            self._close_short(code, close, price)
            amount -= close
            if amount <= 0:
                return
            pos = port.positions.get(code)  # 空头可能已被平掉

        cost = amount * price
        fee = self._commission(cost, 'buy')
        total = cost + fee
        if total > port.cash:
            amount = int(port.cash / (price * (1 + self.order_cost.open_commission + self.order_cost.open_tax)))
            if amount <= 0:
                return
            cost = amount * price
            fee = self._commission(cost, 'buy')
            total = cost + fee
        port.cash -= total
        pos = port.positions.get(code)
        if pos is None:
            pos = Position(code, amount, price)
            port.positions[code] = pos
        else:
            old_cost = pos.avg_cost * pos.amount
            new_amount = pos.amount + amount
            pos.avg_cost = (old_cost + cost) / new_amount if new_amount > 0 else 0
            pos.amount = new_amount
            pos.price = price
            pos.value = new_amount * price
        self.trades.append({
            'date': self.context.current_date, 'code': code, 'side': 'buy',
            'amount': amount, 'price': round(price, 4), 'fee': round(fee, 4)
        })

    def _sell(self, code, amount):
        """卖出：若持仓不足则开空头（融券），否则平多头。"""
        if amount <= 0:
            return
        price = self._exec_price(code, 'sell')
        port = self.context.portfolio
        pos = port.positions.get(code)

        # 若当前是多头，先平掉多头部分
        if pos is not None and pos.amount > 0:
            close = min(amount, pos.amount)
            self._close_long(code, close, price)
            amount -= close
            if amount <= 0:
                return
            pos = port.positions.get(code)

        # 剩余部分开空头（融券卖出）
        proceeds = amount * price
        fee = self._commission(proceeds, 'sell')
        net = proceeds - fee
        port.cash += net
        pos = port.positions.get(code)
        if pos is None:
            pos = Position(code, -amount, price)
            port.positions[code] = pos
        else:
            pos.amount -= amount
            pos.price = price
            pos.value = pos.amount * price
        self.trades.append({
            'date': self.context.current_date, 'code': code, 'side': 'sell',
            'amount': amount, 'price': round(price, 4), 'fee': round(fee, 4)
        })

    def _close_long(self, code, amount, price):
        """平多头：卖出已有正持仓。"""
        port = self.context.portfolio
        pos = port.positions[code]
        amount = min(amount, pos.amount)
        proceeds = amount * price
        fee = self._commission(proceeds, 'sell')
        port.cash += proceeds - fee
        pos.amount -= amount
        pos.price = price
        pos.value = pos.amount * price
        if pos.amount <= 0:
            del port.positions[code]
        self.trades.append({
            'date': self.context.current_date, 'code': code, 'side': 'sell',
            'amount': amount, 'price': round(price, 4), 'fee': round(fee, 4)
        })

    def _close_short(self, code, amount, price):
        """平空头：买回已融券卖出的部分。"""
        port = self.context.portfolio
        pos = port.positions[code]
        amount = min(amount, -pos.amount)
        cost = amount * price
        fee = self._commission(cost, 'buy')
        port.cash -= cost + fee
        pos.amount += amount
        pos.price = price
        pos.value = pos.amount * price
        if pos.amount >= 0:
            del port.positions[code]
        self.trades.append({
            'date': self.context.current_date, 'code': code, 'side': 'buy',
            'amount': amount, 'price': round(price, 4), 'fee': round(fee, 4)
        })


# ============================ 引擎主体 ============================

class BacktestEngine(object):
    def __init__(self, initialize_func, start_date, end_date, initial_cash,
                 benchmark='000300.XSHG', use_real_price=True):
        self.initialize_func = initialize_func
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date)
        self.initial_cash = initial_cash
        self.benchmark = benchmark

        self.context = Context()
        self.context.portfolio = Portfolio(initial_cash)
        self.context.benchmark = benchmark
        self.context.order_cost = _api.OrderCost()
        self.context.slippage = _api.FixedSlippage(0.0)

        self.scheduler = _Scheduler()
        self.broker = None
        self.records = []  # 每日净值记录

        # 把调度器函数注入 api 的全局命名空间，供策略 initialize 里调用
        self._install_runtime_functions()

    def _install_runtime_functions(self):
        """把 run_daily 等调度函数、set_* 配置函数暴露给策略。"""
        import builtins
        self._saved = {}
        for name, fn in [
            ('run_daily', self.scheduler.run_daily),
            ('run_weekly', self.scheduler.run_weekly),
            ('run_monthly', self.scheduler.run_monthly),
        ]:
            self._saved[name] = getattr(builtins, name, None)
            setattr(builtins, name, fn)

        # set_* 配置函数
        setattr(builtins, 'set_benchmark', lambda b: setattr(self.context, 'benchmark', b))
        setattr(builtins, 'set_option', lambda *a, **k: None)
        setattr(builtins, 'set_order_cost', self._set_order_cost)
        setattr(builtins, 'set_slippage', self._set_slippage)

    def _set_order_cost(self, oc, type='stock'):
        self.context.order_cost = oc

    def _set_slippage(self, slip):
        self.context.slippage = slip

    def run(self):
        # 1. 获取交易日序列
        trade_days = _data.get_trade_days(self.start_date.strftime('%Y-%m-%d'),
                                          self.end_date.strftime('%Y-%m-%d'))
        trade_days = [pd.Timestamp(d) for d in trade_days]
        if not trade_days:
            raise RuntimeError("回测区间内没有交易日，请检查起止日期。")
        self.scheduler.set_trade_days(trade_days)

        # 2. 设置上下文初始日期（initialize 里可能访问 context.current_dt）
        self.context.current_dt = pd.Timestamp(trade_days[0]).to_pydatetime()
        self.context.current_date = pd.Timestamp(trade_days[0]).date()
        self.context.previous_date = None

        # 3. 执行 initialize（策略注册定时任务、配置参数）
        self.initialize_func(self.context)

        # 4. 基准行情（用于对比）
        bench_closes = self._get_benchmark_series(trade_days)

        # 5. 逐日回测
        self.broker = _Broker(self.context, self.context.order_cost, self.context.slippage)

        # 预取交易日列表的上一交易日映射
        prev_map = {}
        for i, d in enumerate(trade_days):
            prev_map[d] = trade_days[i - 1] if i > 0 else None

        for i, day in enumerate(trade_days):
            self.context.current_dt = pd.Timestamp(day).to_pydatetime()
            self.context.current_date = pd.Timestamp(day).date()
            self.context.previous_date = prev_map[day].date() if prev_map[day] is not None else None

            # 设置数据时间锚点：当日数据查询只能看到截至当天（防未来函数）
            _data.set_current_date(self.context.current_date)

            # 重置当日实时数据缓存（get_current_data 惰性构造）
            _api._reset_current_data(self.context.current_date)

            # 预取当日价格供撮合使用
            self._preload_prices_for_day()

            # 执行当日到期任务
            for func in self.scheduler.due_tasks(self.context.current_date):
                try:
                    func(self.context)
                except Exception as e:
                    _api.log.error("任务 %s 执行出错: %s", func.__name__, e)

            # 收盘后：更新持仓市值与总资产
            self._mark_to_market()

            # 记录净值
            self.records.append({
                'date': self.context.current_date,
                'total_value': self.context.portfolio.total_value,
                'cash': self.context.portfolio.cash,
                'positions': {k: v.amount for k, v in self.context.portfolio.positions.items()},
            })

        # 5. 组装结果
        return self._build_result(trade_days, bench_closes)

    def _preload_prices_for_day(self):
        """预取当日（以及当前持仓）的收盘价，供撮合时定价。"""
        # 取当日收盘价：用截至当日的最近一根收盘
        date_str = self.context.current_date.strftime('%Y-%m-%d')
        prices = {}
        # 持仓标的
        for code in list(self.context.portfolio.positions.keys()):
            prices[code] = self._last_close(code)
        self.broker.prices = prices

    def _last_close(self, code):
        """取某标的截至当前回测日的最近收盘价。"""
        df = _data.get_price(code, frequency='daily', fields=['close'], fq='pre',
                             count=400)
        if df is not None and len(df) > 0:
            return float(df['close'].iloc[-1])
        return None

    def _get_benchmark_series(self, trade_days):
        try:
            df = _data.get_price(self.benchmark, self.start_date.strftime('%Y-%m-%d'),
                                 self.end_date.strftime('%Y-%m-%d'), 'daily', ['close'], fq='pre')
            if df is None or len(df) == 0:
                return None
            closes = df['close']
            # 对齐到回测交易日
            series = pd.Series(index=[pd.Timestamp(d) for d in trade_days], dtype=float)
            for d in trade_days:
                ts = pd.Timestamp(d)
                if ts in closes.index:
                    series[ts] = closes.loc[ts]
                else:
                    # 取最近的前一个收盘
                    earlier = closes.index[closes.index <= ts]
                    if len(earlier) > 0:
                        series[ts] = closes.loc[earlier[-1]]
            return series
        except Exception:
            return None

    def _mark_to_market(self):
        """收盘后用当日收盘价更新持仓市值。"""
        port = self.context.portfolio
        codes = list(port.positions.keys())
        prices = {}
        for code in codes:
            try:
                df = _data.get_price(code, count=1, frequency='daily', fields=['close'], fq='pre')
                if df is not None and len(df) > 0:
                    prices[code] = float(df['close'].iloc[-1])
            except Exception:
                prices[code] = None
        # 也填充 broker.prices，供策略在下一次撮合前引用
        self.broker.prices.update({k: v for k, v in prices.items() if v is not None})
        port.update_total_value(prices)

    def _build_result(self, trade_days, bench_closes):
        df = pd.DataFrame(self.records)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')

        # 净值（归一化到 1）
        df['nav'] = df['total_value'] / self.initial_cash
        df['returns'] = df['nav'].pct_change().fillna(0.0)

        # 基准净值
        if bench_closes is not None and len(bench_closes) > 0:
            bench_nav = bench_closes / bench_closes.iloc[0]
            df['benchmark_nav'] = bench_nav
        else:
            df['benchmark_nav'] = np.nan

        result = BacktestResult(df, self.initial_cash, self.broker.trades)
        return result


class BacktestResult(object):
    """回测结果封装，提供绩效指标计算。"""

    def __init__(self, df, initial_cash, trades):
        self.df = df
        self.initial_cash = initial_cash
        self.trades = pd.DataFrame(trades) if trades else pd.DataFrame(
            columns=['date', 'code', 'side', 'amount', 'price', 'fee'])

    # ---------- 基础指标 ----------
    @property
    def total_return(self):
        return self.df['nav'].iloc[-1] - 1.0

    @property
    def annual_return(self):
        nav = self.df['nav']
        n = len(nav)
        if n < 2:
            return 0.0
        years = n / 252.0
        total = nav.iloc[-1] / nav.iloc[0]
        return total ** (1 / years) - 1 if years > 0 else 0.0

    @property
    def max_drawdown(self):
        nav = self.df['nav']
        peak = nav.cummax()
        dd = nav / peak - 1.0
        return dd.min()

    @property
    def sharpe(self):
        r = self.df['returns']
        if r.std() == 0:
            return 0.0
        return (r.mean() / r.std()) * np.sqrt(252)

    @property
    def volatility(self):
        return self.df['returns'].std() * np.sqrt(252)

    @property
    def win_rate(self):
        """日胜率（当日收益 > 0 的占比）。"""
        r = self.df['returns']
        r = r[r != 0]
        if len(r) == 0:
            return 0.0
        return (r > 0).mean()

    @property
    def turnover(self):
        """换手率（累计买入金额 / 平均资产）。"""
        if len(self.trades) == 0:
            return 0.0
        buy = self.trades[self.trades['side'] == 'buy']
        if len(buy) == 0:
            return 0.0
        total_buy = (buy['amount'] * buy['price']).sum()
        avg_asset = self.df['total_value'].mean()
        return total_buy / avg_asset if avg_asset > 0 else 0.0

    @property
    def trade_count(self):
        return len(self.trades)

    # ---------- 汇总报告 ----------
    def summary(self):
        bench_ret = np.nan
        if self.df['benchmark_nav'].notna().any():
            b = self.df['benchmark_nav'].dropna()
            bench_ret = b.iloc[-1] / b.iloc[0] - 1.0

        lines = []
        lines.append("=" * 60)
        lines.append("回测绩效报告")
        lines.append("=" * 60)
        lines.append(f"初始资金        : {self.initial_cash:,.0f} 元")
        lines.append(f"期末资产        : {self.df['total_value'].iloc[-1]:,.0f} 元")
        lines.append(f"累计收益率      : {self.total_return * 100:8.2f}%")
        lines.append(f"年化收益率      : {self.annual_return * 100:8.2f}%")
        lines.append(f"基准累计收益率  : {bench_ret * 100:8.2f}%")
        lines.append(f"最大回撤        : {self.max_drawdown * 100:8.2f}%")
        lines.append(f"夏普比率        : {self.sharpe:8.2f}")
        lines.append(f"年化波动率      : {self.volatility * 100:8.2f}%")
        lines.append(f"日胜率          : {self.win_rate * 100:8.2f}%")
        lines.append(f"总成交笔数      : {self.trade_count}")
        lines.append(f"换手率          : {self.turnover * 100:8.2f}%")
        lines.append("=" * 60)
        return "\n".join(lines)

    def __repr__(self):
        return self.summary()


def run_backtest(initialize_func, start_date, end_date, initial_cash=1000000,
                 benchmark='000300.XSHG'):
    """
    一键回测入口。

    参数：
        initialize_func : 策略的 initialize 函数
        start_date / end_date : 回测起止日期 'YYYY-MM-DD'
        initial_cash   : 初始资金（元）
        benchmark      : 基准标的
    """
    engine = BacktestEngine(initialize_func, start_date, end_date, initial_cash, benchmark)
    return engine.run()
