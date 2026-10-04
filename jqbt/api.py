# -*- coding: utf-8 -*-
"""
jqbt.api —— 聚宽风格 API 兼容层
================================================================================
让策略代码在本地（PyCharm）也能用聚宽熟悉的写法，几乎无需改动业务逻辑。

提供：
  - g             : 全局参数对象（聚宽的 g，回测全程可读写）
  - context       : 上下文对象（portfolio / current_dt / previous_date 等）
  - log           : 日志对象（log.info / log.warn / log.error / log.set_level）
  - OrderCost     : 交易成本对象
  - FixedSlippage : 固定滑点对象
  - attribute_history / get_price / history : 行情获取（本地数据）
  - get_index_stocks / get_all_securities / get_industry / get_fundamentals 等
  - query / valuation / indicator / income / balance / cashflow
  - order / order_value / order_target / order_target_value : 下单（由引擎执行）
================================================================================
"""

# ============================ 全局对象 g ============================

class _Global(object):
    """聚宽风格的全局参数对象：g.xxx 任意属性读写。"""
    pass


g = _Global()


# ============================ 日志对象 log ============================

class _Log(object):
    def __init__(self):
        self._level = {'order': 'info'}

    def set_level(self, name, level):
        self._level[name] = level

    def info(self, msg, *args):
        if args:
            try:
                msg = msg % args
            except Exception:
                pass
        print("[INFO]", msg)

    def warn(self, msg, *args):
        if args:
            try:
                msg = msg % args
            except Exception:
                pass
        print("[WARN]", msg)

    def error(self, msg, *args):
        if args:
            try:
                msg = msg % args
            except Exception:
                pass
        print("[ERROR]", msg)


log = _Log()


# ============================ 交易成本 / 滑点 ============================

class OrderCost(object):
    """交易成本配置（与聚宽一致）。"""

    def __init__(self, open_tax=0, close_tax=0, open_commission=0,
                 close_commission=0, close_today_commission=0,
                 min_commission=0):
        self.open_tax = open_tax
        self.close_tax = close_tax
        self.open_commission = open_commission
        self.close_commission = close_commission
        self.close_today_commission = close_today_commission
        self.min_commission = min_commission


class FixedSlippage(object):
    """固定滑点（万分比，如 0.02 表示 0.02% 的滑点）。"""

    def __init__(self, value):
        self.value = value  # 单位是万分比（0.02 = 2/10000）


# ============================ 下单状态（由引擎填充） ============================

_order_broker = None  # 由 engine 注入，负责真实撮合


def _set_broker(broker):
    global _order_broker
    _order_broker = broker


def _check_broker():
    if _order_broker is None:
        raise RuntimeError("下单前必须由回测引擎初始化 broker。")


def order(security, amount):
    """按股数下单（正买入 / 负卖出）。"""
    _check_broker()
    return _order_broker.order(security, amount)


def order_value(security, value):
    """按金额下单（value 元）。"""
    _check_broker()
    return _order_broker.order_value(security, value)


def order_target(security, amount):
    """调整到目标股数。"""
    _check_broker()
    return _order_broker.order_target(security, amount)


def order_target_value(security, value):
    """调整到目标市值（value 元）。"""
    _check_broker()
    return _order_broker.order_target_value(security, value)


# ============================ 数据 API（本地数据适配） ============================

from . import data as _data


# attribute_history 内存缓存：回测中同一 (标的, 数量, 截至日) 只拉一次。
# 发现阶段 + 正式回测会重复调用相同数据，缓存可省一半数据额度与时间。
_attr_history_cache = {}


def attribute_history(security, count, unit='1d', fields=('close',),
                      skip_paused=True, df=True, fq='pre'):
    """
    获取单个标的过去 count 个周期的历史数据，返回 DataFrame。
    与聚宽 attribute_history 行为一致（返回最近 count 条，含当天已收盘的K线）。
    """
    # 兼容 fields 为字符串（如 'close'）的情况
    if isinstance(fields, str):
        fields = [fields]
    else:
        fields = list(fields)
    anchor = _data.get_current_date()
    if anchor is not None:
        key = (security, int(count), unit, tuple(fields), skip_paused, fq, str(anchor))
        cached = _attr_history_cache.get(key)
        if cached is not None:
            return cached.copy()
    result = _data.get_price(security, frequency=unit, fields=fields,
                             count=count, fq=fq, skip_paused=skip_paused)
    if anchor is not None:
        if len(_attr_history_cache) > 80000:  # 内存保护：防止极端场景无限膨胀
            _attr_history_cache.clear()
        _attr_history_cache[key] = result
    return result.copy() if result is not None else result


def get_price(security, start_date=None, end_date=None, frequency='daily',
              fields=None, skip_paused=False, fq='pre', count=None):
    """获取行情（与聚宽 get_price 一致）。"""
    return _data.get_price(security, start_date=start_date, end_date=end_date,
                           frequency=frequency, fields=fields,
                           skip_paused=skip_paused, fq=fq, count=count)


def history(count, unit='1d', field='avg', security_list=None,
            df=True, skip_paused=False, fq='pre'):
    """批量获取多标的的历史数据，返回 DataFrame（index=时间，columns=标的）或 dict。"""
    if isinstance(security_list, str):
        security_list = [security_list]
    result = {}
    for s in security_list:
        df = _data.get_price(s, frequency=unit, fields=[field] if field != 'avg' else None,
                             count=count, fq=fq, skip_paused=skip_paused)
        if field == 'avg':
            # avg = (high + low) / 2 的简化：用 close 代替
            ser = df['close'] if 'close' in df.columns else df.iloc[:, 0]
        else:
            ser = df[field]
        result[s] = ser
    if df:
        return pd.DataFrame(result)
    return result


def get_index_stocks(index_symbol, date=None):
    return _data.get_index_stocks(index_symbol, date=date)


def get_all_securities(types=None, date=None):
    return _data.get_all_securities(types=types, date=date)


def get_industry(security=None, date=None):
    return _data.get_industry(security, date=date)


def get_trade_days(start_date=None, end_date=None, count=None):
    return _data.get_trade_days(start_date=start_date, end_date=end_date, count=count)


def query(*args):
    return _data.query(*args)


# ============================ 财务表对象 ============================
# 聚宽中 valuation / indicator / income / balance / cashflow 是「表对象」，
# 用法是 valuation.code、indicator.roe 等（属性访问），而非函数调用。
# 这里用惰性代理，首次访问时才从 jqdatasdk 取真实表对象。

class _TableProxy(object):
    """财务表对象代理：把 jqdatasdk 的表对象暴露为 valuation.code 等属性。"""

    def __init__(self, getter):
        self._getter = getter
        self._table = None

    def _ensure(self):
        if self._table is None:
            self._table = self._getter()
        return self._table

    def __getattr__(self, name):
        return getattr(self._ensure(), name)


valuation = _TableProxy(lambda: _data.valuation())
indicator = _TableProxy(lambda: _data.indicator())
income = _TableProxy(lambda: _data.income())
balance = _TableProxy(lambda: _data.balance())
cashflow = _TableProxy(lambda: _data.cashflow())


def get_fundamentals(query_object, date=None, stat_date=None):
    return _data.get_fundamentals(query_object, date=date, stat_date=stat_date)


def get_security_info(code):
    """获取标的基础信息（上市日期等），返回对象，含 start_date 属性。"""
    return _data.get_security_info(code)


def get_industries(name='sw_l1', date=None):
    """获取行业列表（申万等），返回 DataFrame（index=行业代码，含 index_code 列）。"""
    return _data.get_industries(name=name, date=date)


def get_industry_stocks(industry_code, date=None):
    """获取某行业的成分股，返回 list[str]。"""
    return _data.get_industry_stocks(industry_code, date=date)


def get_bars(security, count, unit='1d', fields=('close',),
             include_now=False, end_dt=None, fq_ref_date=None, df=True):
    """获取历史K线（对齐聚宽 get_bars）。unit 支持 '1d'/'1m'。"""
    freq = 'minute' if unit in ('1m', '1min', 'minute') else 'daily'
    return _data.get_price(security, frequency=freq, fields=list(fields),
                           count=count, fq='pre')


def get_extras(info, security_list, start_date=None, end_date=None, df=True):
    """获取额外数据（如 is_st、paused、high_limit 等），本地用近似实现。"""
    return _data.get_extras(info, security_list, start_date=start_date,
                            end_date=end_date, df=df)


def normalize_code(code):
    """标准化证券代码（如 '600000' -> '600000.XSHG'）。"""
    return _data.normalize_code(code)


def get_all_trade_days():
    """获取所有交易日。"""
    return _data.get_trade_days(start_date='2005-01-01',
                                end_date=dt.date.today().strftime('%Y-%m-%d'))


# ============================ 当日实时数据 ============================

class _CurrentDatum(object):
    """单只标的的"当日"状态对象，对齐聚宽 get_current_data()[code] 的属性。"""

    def __init__(self, code):
        self.code = code
        self.last_price = 0.0    # 最新价
        self.day_open = 0.0      # 当日开盘价
        self.high_limit = 0.0    # 涨停价
        self.low_limit = 0.0     # 跌停价
        self.paused = False      # 是否停牌
        self.is_st = False       # 是否 ST
        self.name = code         # 证券名称
        self.volume = 0.0        # 成交量

    def __repr__(self):
        return f"<CurrentDatum {self.code} last={self.last_price}>"


class _CurrentData(object):
    """聚宽 get_current_data() 返回的类 dict 对象（惰性构造）。

    本地数据无法提供"当日实时"的 ST/涨跌停状态，故用可获取的数据近似：
      - last_price / day_open / volume : 截至当前回测日的行情
      - paused : 当日无行情视为停牌
      - high_limit / low_limit : 用前收盘价 ± 比例近似（A股主板 10%）
      - is_st / name : 用证券名称判断

    惰性构造：策略遍历股票池时，每只股票首次访问 __getitem__ 才拉取并缓存，
    避免一次性拉全市场导致过慢 / 超额。
    """

    def __init__(self):
        self._data = {}
        self._names_cache = None   # 全市场名称缓存（首次访问时拉取一次）
        self._anchor = None

    def _reset(self, anchor_date):
        """每日开盘前调用，清空缓存并记录锚点日期。"""
        self._data = {}
        self._anchor = anchor_date
        self._names_cache = None

    def _get_names(self):
        if self._names_cache is None:
            try:
                sec_df = _data.get_all_securities(types=[], date=self._anchor)
                self._names_cache = sec_df['display_name'].to_dict() \
                    if sec_df is not None and 'display_name' in sec_df.columns else {}
            except Exception:
                self._names_cache = {}
        return self._names_cache

    def __getitem__(self, code):
        if code not in self._data:
            self._data[code] = self._build_one(code)
        return self._data[code]

    def get(self, code, default=None):
        try:
            return self[code]
        except Exception:
            return default

    def __contains__(self, code):
        return code in self._data

    def _build_one(self, code):
        d = _CurrentDatum(code)
        names = self._get_names()
        d.name = names.get(code, code)
        d.is_st = ('ST' in str(d.name)) or ('*ST' in str(d.name))

        df = _data.get_price(code, frequency='daily',
                             fields=['open', 'close', 'high', 'low', 'volume'],
                             count=2, fq='pre')
        if df is not None and len(df) > 0:
            last = df.iloc[-1]
            d.last_price = float(last['close'])
            d.day_open = float(last['open'])
            d.volume = float(last['volume']) if 'volume' in df.columns else 0.0
            prev_close = float(df.iloc[-2]['close']) if len(df) >= 2 else float(last['close'])
            d.high_limit = round(prev_close * 1.1, 2)
            d.low_limit = round(prev_close * 0.9, 2)
            d.paused = (d.volume <= 0) and (abs(d.last_price - d.day_open) < 1e-6)
        else:
            d.paused = True
        return d


_current_data_obj = _CurrentData()


def get_current_data():
    """获取当日实时数据对象（由引擎每日自动填充，惰性构造）。"""
    return _current_data_obj


def _reset_current_data(anchor_date):
    """由引擎每日开盘前调用，重置当日状态缓存。"""
    _current_data_obj._reset(anchor_date)


import datetime as dt  # noqa: E402  (供 get_all_trade_days 使用)
import pandas as pd  # noqa: E402  (供 history 使用)
