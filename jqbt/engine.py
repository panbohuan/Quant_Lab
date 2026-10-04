# -*- coding: utf-8 -*-
"""
jqbt.engine —— 基于 backtrader 内核的本地回测引擎
================================================================================
撮合、手续费、持仓与资金账务全部交由成熟的 backtrader 引擎完成，
本模块只做两件事：

  1. 聚宽风格 API 适配：让策略继续用 initialize / run_daily / attribute_history /
     order_target_value / g / log 等熟悉的写法，策略代码零改动；
  2. 动态股票池发现：backtrader 要求在运行前提供全部数据源，而选股策略的
     股票池是运行时才确定的（如全市场选股）。因此先做一轮"发现"（不真实
     撮合），记录策略实际下单过的标的，再把它们作为数据源喂给 backtrader。

回测流程（run_backtest）：
    登录聚宽 → 获取交易日 → 发现阶段（记录交易标的）→ 预取行情
    → backtrader 正式回测（Cheat-On-Close：当日收盘价撮合）
    → 组装绩效报告与净值曲线

已知限制（日线级别教学回测）：
    - 不支持分钟级撮合（分钟数据仍可通过 get_price 获取做研究）；
    - 未实现 A 股 T+1、涨跌停不能成交等实盘细则；
    - 发现阶段会多执行一遍策略逻辑（结果不受影响，仅消耗数据额度）。
================================================================================
"""
import datetime as dt

import numpy as np
import pandas as pd

from . import data as _data
from . import api as _api


# ============================ 上下文对象 ============================

class Portfolio(object):
    """组合账户：现金、持仓、总资产（数值由引擎每日从 backtrader 同步）。"""

    def __init__(self, cash):
        self.starting_cash = cash
        self.cash = cash
        self.positions = {}      # code -> Position
        self.total_value = cash  # 总资产（现金 + 持仓市值）

    def update_total_value(self, prices):
        """兼容保留：发现阶段无撮合，总资产默认等于现金。"""
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
        self.amount = amount          # 持股数量（负数=空头）
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
                # 聚宽 run_weekly(weekday=1) 表示每周第 1 个交易日
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


# ============================ 下单路由 ============================

class _OrderRouterBase(object):
    """jqbt 下单 API 的公共基类：order / order_value / order_target / order_target_value。

    api.order* 委托到 _order_broker（本路由），子类实现 _execute()。
    """

    def __init__(self):
        self.trades = []          # 成交记录
        self._warned_codes = set()

    # ---- 对齐聚宽语义的四个下单入口 ----
    def order(self, security, amount):
        return self._execute(security, 'size', int(amount))

    def order_value(self, security, value):
        return self._execute(security, 'value', float(value))

    def order_target(self, security, amount):
        return self._execute(security, 'target_size', int(amount))

    def order_target_value(self, security, value):
        return self._execute(security, 'target_value', float(value))

    # ---- 子类接口 ----
    def _execute(self, code, kind, value):
        raise NotImplementedError

    def _warn_once(self, code, reason):
        if code not in self._warned_codes:
            self._warned_codes.add(code)
            _api.log.error("下单失败: %s (%s)", code, reason)


class _DiscoveryRouter(_OrderRouterBase):
    """发现阶段路由：不真实撮合，仅记录策略下单过的标的。"""

    def __init__(self):
        super().__init__()
        self.codes = set()

    def _execute(self, code, kind, value):
        self.codes.add(code)
        return None


# ============================ backtrader 适配（延迟导入） ============================

def _make_comm_info_cls():
    """构造符合聚宽 OrderCost 语义的 backtrader 佣金类。"""
    import backtrader as bt

    class JqCommInfo(bt.CommInfoBase):
        """聚宽 OrderCost 适配：
        - 买入：佣金 open_commission（最低 min_commission）
        - 卖出：佣金 close_commission + 印花税 close_tax（佣金部分设下限）
        """

        def __init__(self, oc):
            super().__init__()
            self._oc = oc

        def _getcommission(self, size, price, pseudoexec):
            value = abs(size) * price
            if size > 0:
                commission = value * self._oc.open_commission
                tax = 0.0
            else:
                commission = value * self._oc.close_commission
                tax = value * self._oc.close_tax
            if commission > 0 and commission < self._oc.min_commission:
                commission = self._oc.min_commission
            return commission + tax

    return JqCommInfo


def _make_bt_adapter():
    """构造 backtrader 适配策略 + 正式下单路由（需延迟导入 backtrader）。"""
    import backtrader as bt

    class _BTRouter(_OrderRouterBase):
        """正式回测路由：把聚宽风格下单映射到 backtrader。"""

        def __init__(self, eng):
            super().__init__()
            self.eng = eng

        def _execute(self, code, kind, value):
            strat = self.eng.bt_adapter
            d = strat.datas_by_code.get(code)
            if d is None:
                # 发现阶段未出现过的标的（本轮策略分支与发现轮不同）
                self._warn_once(code, "不在回测数据源中（发现阶段未记录该标的）")
                return None
            if kind == 'size':
                strat.order(d, value)
            elif kind == 'value':
                strat.order_value(d, value)   # bt 支持负数=卖出
            elif kind == 'target_size':
                strat.order_target_size(d, value)
            elif kind == 'target_value':
                strat.order_target_value(d, value)
            return None

    class _BTAdapter(bt.Strategy):
        """逐日推进的"钟表"策略：
        - 用基准指数数据源（feeds[0]）作为主时钟，保证逐日对齐；
        - 每根日线：同步账户状态 → 执行当日到期任务（策略代码）；
        - notify_order 收集成交记录。
        """

        params = (('engine', None),)

        def __init__(self):
            eng = self.params.engine
            eng.bt_adapter = self
            # feeds 添加顺序 == eng.feed_codes 顺序（index 0 为基准时钟）
            self.datas_by_code = dict(zip(eng.feed_codes[1:], self.datas[1:]))
            eng.router_bt = _BTRouter(eng)
            _api._set_broker(eng.router_bt)
            self._today = None
            self._code_by_data = {v: k for k, v in self.datas_by_code.items()}

        def next(self):
            eng = self.params.engine
            ctx = eng.context
            day = self.datas[0].datetime.date(0)
            self._today = day

            # 同步上下文日期
            ctx.current_date = day
            ctx.current_dt = dt.datetime.combine(day, dt.time(15, 0))
            ctx.previous_date = eng._prev_date.get(day)

            # 数据锚点 + 当日实时数据重置（防未来函数）
            _data.set_current_date(day)
            _api._reset_current_data(day)

            # 同步账户状态（backtrader broker → 聚宽风格 portfolio）
            self._sync_portfolio()

            # 执行当日到期任务
            for func in eng.scheduler.due_tasks(day):
                try:
                    func(ctx)
                except Exception as e:
                    _api.log.error("任务 %s 执行出错: %s", func.__name__, e)

            # 收盘后记录净值
            port = ctx.portfolio
            eng.records.append({
                'date': day,
                'total_value': port.total_value,
                'cash': port.cash,
                'positions': {k: v.amount for k, v in port.positions.items()},
            })

        def _sync_portfolio(self):
            eng = self.params.engine
            broker = self.broker
            port = eng.context.portfolio
            port.cash = broker.getcash()
            port.total_value = broker.getvalue()
            port.positions = {}
            for code, d in self.datas_by_code.items():
                pos = broker.getposition(d)
                if pos.size != 0:
                    port.positions[code] = Position(code, int(pos.size), float(pos.price or 0.0))

        def notify_order(self, order):
            eng = self.params.engine
            code = self._code_by_data.get(order.data, '?')
            if order.status in [bt.Order.Margin, bt.Order.Rejected]:
                _api.log.error("订单被拒绝/保证金不足: %s", code)
                return
            if order.status == bt.Order.Completed:
                size = order.executed.size
                # 成交日期取自订单执行时间戳（而非通知到达日）
                exec_day = bt.num2date(order.executed.dt).date()
                eng.router_bt.trades.append({
                    'date': exec_day,
                    'code': code,
                    'side': 'buy' if size > 0 else 'sell',
                    'amount': abs(int(size)),
                    'price': round(float(order.executed.price), 4),
                    'fee': round(float(order.executed.comm), 4),
                })

    return _BTAdapter


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
        self.records = []     # 每日净值记录
        self.feed_codes = []  # 最终进入 backtrader 的标的（index0=基准时钟）
        self.bt_adapter = None
        self.router_bt = None
        self._prev_date = {}

    # ---------- 运行时注入 ----------

    def _install_runtime_functions(self, router, scheduler):
        """把调度、配置、下单函数注入内置命名空间，供策略 initialize 使用。"""
        import builtins
        setattr(builtins, 'run_daily', scheduler.run_daily)
        setattr(builtins, 'run_weekly', scheduler.run_weekly)
        setattr(builtins, 'run_monthly', scheduler.run_monthly)
        setattr(builtins, 'set_benchmark', lambda b: setattr(self.context, 'benchmark', b))
        setattr(builtins, 'set_option', lambda *a, **k: None)
        setattr(builtins, 'set_order_cost', self._set_order_cost)
        setattr(builtins, 'set_slippage', self._set_slippage)
        _api._set_broker(router)

    def _set_order_cost(self, oc, type='stock'):
        self.context.order_cost = oc

    def _set_slippage(self, slip):
        self.context.slippage = slip

    # ---------- 主流程 ----------

    def run(self):
        # 1. 交易日序列
        trade_days = _data.get_trade_days(self.start_date.strftime('%Y-%m-%d'),
                                          self.end_date.strftime('%Y-%m-%d'))
        trade_days = [pd.Timestamp(d).date() for d in trade_days]
        if not trade_days:
            raise RuntimeError("回测区间内没有交易日，请检查起止日期。")
        # 首个交易日的 previous_date 兜底：取前一交易日；接口失败则用前一自然日。
        # （教学策略常在首个调仓日使用 context.previous_date 计算上市天数，避免 None 报错）
        try:
            _prev = _data.get_trade_days(
                end_date=(trade_days[0] - dt.timedelta(days=1)).strftime('%Y-%m-%d'), count=1)
            prev0 = pd.Timestamp(_prev[-1]).date() if len(_prev) else trade_days[0] - dt.timedelta(days=1)
        except Exception:
            prev0 = trade_days[0] - dt.timedelta(days=1)
        self._prev_date = {d: (trade_days[i - 1] if i > 0 else prev0)
                           for i, d in enumerate(trade_days)}
        self.context.current_dt = dt.datetime.combine(trade_days[0], dt.time(9, 30))
        self.context.current_date = trade_days[0]
        self.context.previous_date = None

        # 2. 发现阶段：跑一遍策略逻辑，记录实际下单过的标的
        discovered = self._discovery_pass(trade_days)

        # 3. 预取行情数据（基准时钟 + 各标的）
        bench_df = self._prefetch(self.benchmark)
        if bench_df is None or len(bench_df) == 0:
            raise RuntimeError("无法获取基准 %s 的行情数据。" % self.benchmark)
        feeds = [(self.benchmark, bench_df)]  # index 0 = 主时钟
        for code in sorted(discovered):
            if code == self.benchmark:
                continue  # 基准已作为时钟数据源
            df = self._prefetch(code)
            if df is not None and len(df) > 0:
                feeds.append((code, df))
            else:
                _api.log.error("标的 %s 在回测区间内无行情数据，其订单将被跳过。", code)
        self.feed_codes = [c for c, _ in feeds]

        # 4. backtrader 正式回测
        return self._bt_run(feeds, trade_days)

    # ---------- 发现阶段 ----------

    def _discovery_pass(self, trade_days):
        """执行一遍策略逻辑（不真实撮合），收集策略下单过的标的集合。"""
        router = _DiscoveryRouter()
        scheduler = _Scheduler()
        self._install_runtime_functions(router, scheduler)
        scheduler.set_trade_days(trade_days)

        self.initialize_func(self.context)

        for day in trade_days:
            self.context.current_date = day
            self.context.current_dt = dt.datetime.combine(day, dt.time(15, 0))
            self.context.previous_date = self._prev_date.get(day)
            _data.set_current_date(day)
            _api._reset_current_data(day)
            for func in scheduler.due_tasks(day):
                try:
                    func(self.context)
                except Exception as e:
                    _api.log.error("[发现阶段] 任务 %s 出错: %s", func.__name__, e)

        return router.codes

    # ---------- 数据预取 ----------

    def _prefetch(self, code):
        """预取某标的回测区间内的日线 OHLCV（backtrader 数据源格式）。"""
        try:
            df = _data.get_price(code, self.start_date.strftime('%Y-%m-%d'),
                                 self.end_date.strftime('%Y-%m-%d'),
                                 frequency='daily',
                                 fields=['open', 'high', 'low', 'close', 'volume'],
                                 fq='pre', skip_paused=False)
        except Exception as e:
            _api.log.error("预取 %s 行情失败: %s", code, e)
            return None
        if df is None or len(df) == 0:
            return None
        df = df.copy()
        df.index = pd.to_datetime(df.index)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col not in df.columns:
                df[col] = 0.0
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        df['openinterest'] = 0.0
        return df[['open', 'high', 'low', 'close', 'volume', 'openinterest']]

    # ---------- backtrader 正式回测 ----------

    def _bt_run(self, feeds, trade_days):
        import backtrader as bt

        JqCommInfo = _make_comm_info_cls()
        _BTAdapter = _make_bt_adapter()

        cerebro = bt.Cerebro(stdstats=False)
        cerebro.broker.set_coc(True)  # 当日收盘价撮合（对齐聚宽日线回测语义）

        # 滑点：FixedSlippage.value 为万分比 → backtrader 百分比滑点
        slip = self.context.slippage
        if slip is not None and getattr(slip, 'value', 0):
            cerebro.broker.set_slippage_perc(slip.value / 10000.0)

        cerebro.broker.setcash(self.initial_cash)

        for i, (code, df) in enumerate(feeds):
            data = bt.feeds.PandasData(dataname=df)
            cerebro.adddata(data, name=code)
            if i > 0:  # 基准时钟不交易；其余按聚宽佣金规则
                cerebro.broker.addcommissioninfo(data, JqCommInfo(self.context.order_cost))

        # bt 阶段重新注册调度任务与配置（initialize 会重新执行）
        self.scheduler = _Scheduler()
        self.scheduler.set_trade_days(trade_days)
        self._install_runtime_functions(None, self.scheduler)  # router 在 Adapter.__init__ 注入
        self.context.portfolio = Portfolio(self.initial_cash)
        self.records = []

        self.initialize_func(self.context)  # 再次注册 run_daily / set_* 等

        cerebro.addstrategy(_BTAdapter, engine=self)
        cerebro.run(runonce=False)  # 逐根 K 线驱动策略

        # 基准行情（用于对比）
        bench_closes = self._get_benchmark_series(trade_days)
        return self._build_result(trade_days, bench_closes)

    # ---------- 绩效组装 ----------

    def _get_benchmark_series(self, trade_days):
        try:
            df = _data.get_price(self.benchmark, self.start_date.strftime('%Y-%m-%d'),
                                 self.end_date.strftime('%Y-%m-%d'), 'daily', ['close'], fq='pre')
            if df is None or len(df) == 0:
                return None
            closes = df['close']
            series = pd.Series(index=[pd.Timestamp(d) for d in trade_days], dtype=float)
            for d in trade_days:
                ts = pd.Timestamp(d)
                if ts in closes.index:
                    series[ts] = closes.loc[ts]
                else:
                    earlier = closes.index[closes.index <= ts]
                    if len(earlier) > 0:
                        series[ts] = closes.loc[earlier[-1]]
            return series
        except Exception:
            return None

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

        trades = self.router_bt.trades if self.router_bt is not None else []
        return BacktestResult(df, self.initial_cash, trades)


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
        lines.append("回测绩效报告（backtrader 内核）")
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
    一键回测入口（策略文件无需改动）。

    参数：
        initialize_func : 策略的 initialize 函数
        start_date / end_date : 回测起止日期 'YYYY-MM-DD'
        initial_cash   : 初始资金（元）
        benchmark      : 基准标的
    """
    engine = BacktestEngine(initialize_func, start_date, end_date, initial_cash, benchmark)
    return engine.run()
