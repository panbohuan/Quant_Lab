# -*- coding: utf-8 -*-
"""
btlab.runner —— backtrader 回测样板封装

只做三件样板事：build_cerebro() 建引擎（A 股费用 + 滑点）、run_strategy() 一键回测
出报告、PanelStrategy 多标的调仓骨架。撮合、持仓、账务全由 backtrader 引擎负责。

A 股费用口径：佣金买卖各 0.03%（单笔最低 5 元）、印花税仅卖出（2023-08-28 起
0.05%，之前 0.1%）、滑点单边 0.02%。
"""
import datetime
import os
import sys

import backtrader as bt
import pandas as pd

# 允许脚本被直接运行时找到 btlab 包
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from btlab.datasource import load_daily, normalize_code          # noqa: E402
from btlab.metrics import perf_from_nav, format_report, plot_equity  # noqa: E402


# ============================ A 股手续费模型 ============================

# 印花税减半的日子：2023-08-28 之前 0.1%，之后 0.05%
_STAMP_DUTY_CUTOFF = datetime.date(2023, 8, 28)


class AStockCommission(bt.CommInfoBase):
    """A 股费用模型：佣金双边（每股最低 5 元）+ 印花税仅卖出。

    这是 backtrader 官方的 `CommInfoBase` 扩展点，不是自研撮合逻辑。
    印花税按成交日切换，成交日由 NavRecorder 每根 K 线写入 ``self.today``。
    """

    params = (
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
        ('percabs', True),           # commission 按绝对百分比解释：0.0003 = 0.03%
        ('commission', 0.0003),      # 佣金（买卖双边）
        ('stamp_duty', 0.0005),      # 印花税（仅卖出，2023-08-28 起）
        ('stamp_duty_pre', 0.0010),  # 印花税（2023-08-28 之前）
        ('min_comm', 5.0),           # 单笔最低佣金（元）
    )

    def _getcommission(self, size, price, pseudoexec):
        value = abs(size) * price
        if value <= 0:
            return 0.0
        comm = value * self.p.commission
        if comm < self.p.min_comm:                # 最低佣金只在佣金上兜底
            comm = self.p.min_comm
        if size < 0:                              # 只有卖出方向收印花税
            today = getattr(self, 'today', None)
            rate = (self.p.stamp_duty_pre
                    if today is not None and today < _STAMP_DUTY_CUTOFF
                    else self.p.stamp_duty)
            comm += value * rate
        return comm


# ============================ 净值记录器 ============================

class NavRecorder(bt.Analyzer):
    """逐日记录账户总资产；同时把当前日期发给费用模型（用于按日取印花税）。"""

    params = (('comm', None),)

    def start(self):
        self._d, self._v = [], []

    def _rec(self):
        if self.p.comm is not None:
            self.p.comm.today = self.strategy.datetime.date(0)
        self._d.append(self.strategy.datetime.date(0))
        self._v.append(self.strategy.broker.getvalue())

    def prenext(self):
        self._rec()

    def nextstart(self):
        self._rec()

    def next(self):
        self._rec()

    def get_analysis(self):
        return pd.Series(self._v, index=pd.to_datetime(self._d), name='nav')


# ============================ Cerebro 构建 ============================

def build_cerebro(cash=1_000_000, commission=0.0003, stamp_duty=0.0005, min_comm=5.0,
                  slippage=0.0002):
    """建一个配置好 A 股费用/滑点的 backtrader Cerebro。"""
    cerebro = bt.Cerebro(stdstats=False)
    cerebro.broker.setcash(cash)
    comm = AStockCommission(commission=commission, stamp_duty=stamp_duty,
                            min_comm=min_comm)
    cerebro.broker.addcommissioninfo(comm)
    cerebro.broker.set_slippage_perc(slippage)
    cerebro.addanalyzer(NavRecorder, _name='nav', comm=comm)
    cerebro.addanalyzer(bt.analyzers.Transactions, _name='txn')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    return cerebro


def add_feed(cerebro, df, name):
    """把一份 OHLCV DataFrame 作为数据源加入 Cerebro（backtrader 官方 PandasData）。"""
    cerebro.adddata(bt.feeds.PandasData(dataname=df), name=str(name))
    return cerebro


def add_feeds(cerebro, data):
    """批量加入数据源。data 支持 {name: DataFrame} 或 [DataFrame, ...]。"""
    if isinstance(data, dict):
        for name, df in data.items():
            add_feed(cerebro, df, name)
    else:
        for i, df in enumerate(data):
            add_feed(cerebro, df, getattr(df, 'attrs', {}).get('code', f'data{i}'))
    return cerebro


# ============================ 一键回测 ============================

def run_strategy(strategy_cls, data, cash=1_000_000, benchmark='000300',
                 commission=0.0003, stamp_duty=0.0005, slippage=0.0002,
                 title=None, plot_path=None, print_report=True, **strat_kwargs):
    """跑一个 backtrader 策略并输出绩效报告（+ 可选净值图）。

    参数：
        strategy_cls : bt.Strategy 子类
        data         : {名字: DataFrame} 或 [DataFrame, ...]，来自 btlab.datasource
        cash         : 初始资金
        benchmark    : 基准代码（None 表示不对比）
        title        : 报告 / 图表标题
        plot_path    : 净值图保存路径（None 表示不画图）
        strat_kwargs : 透传给策略的 params
    返回：
        dict(metrics=..., nav=..., benchmark_ret=..., trade_count=..., turnover=...)
    """
    cerebro = build_cerebro(cash=cash, commission=commission,
                            stamp_duty=stamp_duty, slippage=slippage)
    add_feeds(cerebro, data)
    cerebro.addstrategy(strategy_cls, **strat_kwargs)

    strat = cerebro.run()[0]

    # ---- 取净值序列 ----
    nav = strat.analyzers.nav.get_analysis()
    nav = pd.Series(nav).dropna()
    if len(nav) < 2:
        raise RuntimeError('回测没有产生有效净值，请检查数据区间与策略逻辑')

    # ---- 取成交记录 ----
    txn = strat.analyzers.txn.get_analysis()
    trade_count, amount = _summarize_txn(txn)
    turnover = (amount / cash) if cash else None      # 累计成交额 / 初始资金

    # ---- 绩效指标（nav 为账户总资产，单位：元）----
    metrics = perf_from_nav(nav)

    # ---- 基准对比 ----
    bench_nav, benchmark_ret = None, None
    if benchmark:
        try:
            bdf = load_daily(benchmark, start=nav.index[0].strftime('%Y-%m-%d'),
                             end=nav.index[-1].strftime('%Y-%m-%d'))
            bench_nav = (bdf['close'] / bdf['close'].iloc[0]).reindex(nav.index).ffill()
            benchmark_ret = float(bdf['close'].iloc[-1] / bdf['close'].iloc[0] - 1.0)
        except Exception as e:  # noqa: BLE001
            print(f'[btlab] 基准 {benchmark} 加载失败，跳过对比：{str(e)[:60]}')

    title = title or f'{strategy_cls.__name__} 回测绩效报告'
    if print_report:
        print(format_report(metrics, cash, benchmark_ret, trade_count,
                            turnover, title=title))

    if plot_path:
        d = os.path.dirname(plot_path)
        if d:
            os.makedirs(d, exist_ok=True)
        plot_equity(nav, bench_nav, save_path=plot_path, title=title)

    return {'metrics': metrics, 'nav': nav, 'benchmark_ret': benchmark_ret,
            'benchmark_nav': bench_nav, 'trade_count': trade_count,
            'turnover': turnover, 'strategy': strat}


def _summarize_txn(txn):
    """从 backtrader Transactions 分析器结果里汇总成交笔数与成交金额。"""
    count, amount = 0, 0.0
    for _dt, rows in (txn or {}).items():
        for row in rows:
            count += 1
            try:
                # backtrader 记录格式：(size, price, sid, symbol, value)
                amount += abs(float(row[4]))
            except Exception:  # noqa: BLE001
                try:
                    amount += abs(float(row[0]) * float(row[1]))
                except Exception:  # noqa: BLE001
                    pass
    return count, amount


# ============================ 多标的调仓骨架 ============================

CAL_NAME = '__CAL__'


class PanelStrategy(bt.Strategy):
    """多标的（选股类）策略骨架 —— backtrader 的常规子类写法。

    撮合、持仓、账务、盈亏仍全部由 backtrader 引擎负责；这里只统一三件琐事：
      1. **交易日历**：外部把基准指数日线命名为 '__CAL__' 一起喂进来（它每个交易日
         都有行情），用它当"时钟"，避免某只股票停牌时判断不出今天是几号；
      2. **调仓频率**：只需实现 `on_rebalance(cur_date)`，骨架按 monthly/weekly/daily
         自动调度（默认每月第 1 个交易日）；
      3. **下单工具**：`equal_weight_order()` / `value_weight_order()` / `close_all()`。

    约定：`self.tradables` 是可交易标的（自动排除日历源）。
    """

    params = (('rebalance', 'monthly'),)     # 'daily' | 'weekly' | 'monthly'

    def __init__(self):
        super().__init__()
        names = self.getdatanames()
        self.cal = self.getdatabyname(CAL_NAME) if CAL_NAME in names else self.datas[0]
        self.tradables = [d for d in self.datas if d._name != CAL_NAME]
        self._last_key = None

    # ---- 调度 ----
    def prenext(self):
        self.next()

    def next(self):
        cur = self.cal.datetime.date(0)
        mode = self.p.rebalance
        if mode == 'daily':
            key = cur
        elif mode == 'weekly':
            key = cur.isocalendar()[:2]
        else:
            key = (cur.year, cur.month)
        if key == self._last_key:
            return
        self._last_key = key
        self.on_rebalance(cur)

    def on_rebalance(self, cur):
        raise NotImplementedError('请在子类里实现 on_rebalance(cur)')

    # ---- 工具 ----
    def live(self, d, cur):
        """该标的今天是否有行情（停牌 / 未上市时返回 False）。"""
        return len(d) > 0 and d.datetime.date(0) == cur

    def _frozen_value(self, cur):
        """今天无法交易的持仓市值（停牌等）。"""
        total = 0.0
        for d in self.tradables:
            if self.getposition(d).size and not self.live(d, cur):
                total += abs(self.getposition(d).size) * d.close[0]
        return total

    def hist_close(self, d, n):
        """取标的最近 n 个收盘价（含今日）；不足 n 个返回 None。"""
        if len(d) < n:
            return None
        return d.close.get(size=n)

    def close_all(self, cur=None):
        """清仓所有持仓。"""
        cur = cur or self.cal.datetime.date(0)
        for d in self.tradables:
            if self.getposition(d).size and self.live(d, cur):
                self.close(d)

    def equal_weight_order(self, names, cur=None, cap=0.98):
        """等权调仓到 names：先卖出不在名单里的，再把名单内标的对齐到目标股数。"""
        cur = cur or self.cal.datetime.date(0)
        live_names = [n for n in names if self.live(self.getdatabyname(n), cur)]
        if not live_names:
            return
        # 停牌股今天卖不掉，先从调仓预算里扣掉它们的市值，避免下单被拒/超配
        budget = max(self.broker.getvalue() - self._frozen_value(cur), 0.0)
        per = budget * cap / len(live_names)
        for d in self.tradables:                       # 1) 先卖（腾出现金）
            if d._name not in live_names and self.getposition(d).size and self.live(d, cur):
                self.close(d)
        for name in live_names:                        # 2) 再买/调仓
            d = self.getdatabyname(name)
            price = d.close[0]
            if price <= 0:
                continue
            delta = round_lot(per / price) - self.getposition(d).size
            if delta > 0:
                self.buy(d, size=delta)
            elif delta < 0:
                self.sell(d, size=-delta)

    def value_weight_order(self, weights, cur=None, cap=0.98):
        """按 {name: 权重} 调仓，权重自动归一化后再乘 cap 使用。"""
        cur = cur or self.cal.datetime.date(0)
        weights = {k: v for k, v in weights.items() if v > 0}
        if not weights:
            self.close_all(cur)
            return
        total_w = sum(weights.values())
        live_names = [n for n in weights if self.live(self.getdatabyname(n), cur)]
        if not live_names:
            return
        total = max(self.broker.getvalue() - self._frozen_value(cur), 0.0)
        for d in self.tradables:
            if d._name not in live_names and self.getposition(d).size and self.live(d, cur):
                self.close(d)
        for name in live_names:
            d = self.getdatabyname(name)
            price = d.close[0]
            if price <= 0:
                continue
            target_value = total * cap * weights[name] / total_w
            delta = round_lot(target_value / price) - self.getposition(d).size
            if delta > 0:
                self.buy(d, size=delta)
            elif delta < 0:
                self.sell(d, size=-delta)


# ============================ 常用数据准备助手 ============================

def prepare_benchmark(code='000300', start='2010-01-01', end=None):
    """加载基准指数日线（供 run_strategy 的 benchmark 参数使用或自行对比）。"""
    return load_daily(code, start=start, end=end)


def load_universe(codes, start, end=None, adjust='qfq', kind=None,
                  grace_days=90, verbose=True, label='股票池'):
    """加载候选池日线，并剔除「上市太晚、覆盖不了回测区间」的标的。

    返回 {代码: DataFrame}。这样多标的策略的 next() 能从区间开头就正常触发。
    """
    from btlab.datasource import load_many
    data = load_many(codes, start=start, end=end, adjust=adjust, kind=kind,
                     verbose=verbose)
    limit = pd.Timestamp(str(start)[:10]) + pd.Timedelta(days=grace_days)
    kept = {k: v for k, v in data.items() if len(v) and v.index[0] <= limit}
    if verbose:
        print(f'[btlab] {label}：候选 {len(codes)} 只 → 数据可用 {len(kept)} 只')
    return kept


def round_lot(size, lot=100):
    """取整到整手（A 股 1 手 = 100 股/份），按绝对值向下取整。"""
    size = int(size)
    return (size // lot) * lot if size >= 0 else -((-size) // lot * lot)


# ============================ 基本面面板（因子策略用） ============================

def asof(panel, cur):
    """取面板中「不晚于 cur」的最近一期数据 —— 只用已公布的信息，防未来函数。

    逐列前向填充后再取最后一行：某只股票当天没有数据时，用它的上一期值，
    而不是把这只股票整只丢掉。返回 Series(index=标的代码)。
    """
    if panel is None or len(panel) == 0:
        return None
    sub = panel.loc[:pd.Timestamp(cur)]
    if len(sub) == 0:
        return None
    row = sub.ffill().iloc[-1]
    return row.dropna() if hasattr(row, 'dropna') else row


def value_panel(codes, field='pb', verbose=True):
    """把多只股票的某个估值字段拼成面板 DataFrame(index=date, columns=code)。

    field 可选：'close' / 'total_mv' / 'circ_mv' / 'pe_ttm' / 'pe' / 'pb' / 'ps'
    """
    from btlab.datasource import load_stock_value
    cols = {}
    for c in codes:
        try:
            s = load_stock_value(c)[field]
            cols[str(c)] = s[~s.index.duplicated(keep='last')]
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f'  [跳过] {c} 估值{field}: {str(e)[:50]}')
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def roe_panel(codes, lag_days=45, verbose=True):
    """把各股票的 ROE 拼成面板，并把「报告期」后移 lag_days 天模拟公告滞后。

    这是为了避免未来函数：季报在报告期结束后约 1~1.5 个月才公告，
    回测中只能使用公告之后的 ROE。
    """
    from btlab.datasource import roe_series
    cols = {}
    for c in codes:
        try:
            s = roe_series(c)
            s = s.copy()
            s.index = s.index + pd.Timedelta(days=lag_days)
            cols[str(c)] = s[~s.index.duplicated(keep='last')]
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f'  [跳过] {c} ROE: {str(e)[:50]}')
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def growth_panel(codes, field='净利润增长率(%)', lag_days=45, verbose=True):
    """把各股票的成长性指标拼成面板（用法同 roe_panel）。"""
    from btlab.datasource import load_financial_indicator
    cols = {}
    for c in codes:
        try:
            df = load_financial_indicator(c)
            if field not in df.columns:
                continue
            s = pd.to_numeric(df[field], errors='coerce').dropna()
            s.index = s.index + pd.Timedelta(days=lag_days)
            cols[str(c)] = s[~s.index.duplicated(keep='last')]
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f'  [跳过] {c} {field}: {str(e)[:50]}')
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).sort_index()


def event_calendar(codes, field='净利润增长率(%)', lag_days=45, threshold=30.0,
                   verbose=True):
    """构建「业绩公告事件日历」：{代码: [(推定公告日, 指标值), ...]}。

    只保留指标超过 threshold 的"好事件"。
    注意：本地免费源只有财务「报告期」没有「公告日」，这里用
    **报告期 + lag_days 天** 近似公告日，属于教学用简化（真实公告日可在聚宽查到）。
    """
    from btlab.datasource import load_financial_indicator
    cal = {}
    for c in codes:
        try:
            df = load_financial_indicator(c)
            if field not in df.columns:
                continue
            s = pd.to_numeric(df[field], errors='coerce').dropna()
            if not len(s):
                continue
            s = s[s > threshold]
            if not len(s):
                continue
            cal[str(c)] = [(d + pd.Timedelta(days=lag_days), float(v))
                           for d, v in s.items()]
        except Exception as e:  # noqa: BLE001
            if verbose:
                print(f'  [跳过] {c} 事件: {str(e)[:50]}')
    return cal


def industry_map(codes=None, verbose=True):
    """构建「股票代码 → 申万一级行业名」的映射（用于行业中性化）。

    数据来源：申万宏源行业指数成分（免费）。注意：上游接口对部分行业会返回异常结构，
    因此实际只能覆盖约一半的申万一级行业；未映射到的股票在回归中归入「未知」类别。
    """
    from btlab.datasource import sw_industries, load_sw_members, normalize_code
    m = {}
    try:
        sw = sw_industries()
    except Exception as e:  # noqa: BLE001
        if verbose:
            print(f'  [跳过] 申万行业列表: {str(e)[:50]}')
        return m
    ok = 0
    for _, row in sw.iterrows():
        try:
            members = load_sw_members(row['code'])
            for c in members:
                m[normalize_code(c, kind='stock')] = row['name']
            ok += 1
        except Exception:  # noqa: BLE001
            pass
    if verbose:
        print(f'  行业映射：{ok}/{len(sw)} 个申万一级行业可用，共 {len(m)} 只股票')
    if codes:
        keep = set(codes)
        m = {c: v for c, v in m.items() if c in keep}
    return m
