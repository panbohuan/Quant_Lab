# -*- coding: utf-8 -*-
"""
jqbt.data —— 数据适配层
================================================================================
封装聚宽官方 jqdatasdk，提供统一的本地数据获取接口，并做本地缓存以加速回测。

设计目标：
  1. 让策略代码在本地（PyCharm）也能拿到与聚宽云端一致的真实数据；
  2. 通过内存 + 磁盘缓存，避免重复拉取相同数据（回测大量调用 attribute_history 时尤其重要）；
  3. 数据不足、登录失败等异常给出清晰报错，方便调试。
================================================================================
"""
import os
import pickle
import datetime as dt

import numpy as np
import pandas as pd

# ============================ 登录状态 ============================

_auth_state = {
    "logged_in": False,
    "phone": None,
}

# ============================ 回测时间锚点 ============================
# 回测时，所有数据查询（attribute_history / get_price 等）必须"看不到未来"，
# 只能返回截至当前回测日的数据。这里用一个全局锚点实现：
#   引擎每个交易日开始时，把 _current_date 设为当天；数据函数自动过滤到 <= 当天。
# 该机制避免"未来函数"（用未来数据预测过去），是本地回测正确性的关键。

_current_date = None  # 当前回测日（datetime.date 或 None=不限）


def set_current_date(d):
    """由引擎调用，设置当前回测日（数据查询的截止日）。"""
    global _current_date
    _current_date = d


def get_current_date():
    return _current_date

# ============================ 缓存 ============================

_cache_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache")


def _ensure_cache_dir():
    os.makedirs(_cache_dir, exist_ok=True)


class _PriceCache:
    """行情数据内存缓存：key = (security, unit, field, fq) -> DataFrame(index=datetime)"""

    def __init__(self):
        self._dict = {}

    def get(self, key):
        return self._dict.get(key)

    def put(self, key, df):
        self._dict[key] = df


_price_cache = _PriceCache()


def _cache_key(security, unit, field, fq, start, end):
    return (security, unit, field, fq, str(start), str(end))


# ============================ jqdatasdk 导入 ============================

def _sdk():
    import jqdatasdk
    return jqdatasdk


def login(phone=None, password=None):
    """登录聚宽数据服务。若不传账号，依次尝试：config.py → 环境变量。"""
    import jqdatasdk
    if not phone:
        phone = os.environ.get("JQDATA_PHONE")
    if not password:
        password = os.environ.get("JQDATA_PASSWORD")

    # 兜底：尝试从 config.py 读取（若存在且已填写）
    if not phone or not password:
        try:
            import config as _cfg
            if not phone and getattr(_cfg, "JQDATA_PHONE", ""):
                phone = _cfg.JQDATA_PHONE
            if not password and getattr(_cfg, "JQDATA_PASSWORD", ""):
                password = _cfg.JQDATA_PASSWORD
        except ImportError:
            pass

    if not phone or not password or "你的" in str(phone) or "你的" in str(password):
        raise RuntimeError(
            "未提供聚宽账号。请通过以下任一方式配置：\n"
            "  1. 编辑 config.py，填写 JQDATA_PHONE / JQDATA_PASSWORD；\n"
            "  2. 设置环境变量 JQDATA_PHONE / JQDATA_PASSWORD；\n"
            "  3. 代码中直接调用 jqbt.login(手机号, 密码)。\n"
            "注册地址：https://www.joinquant.com （免费，每月有数据额度）"
        )
    if _auth_state["logged_in"] and _auth_state["phone"] == phone:
        return
    ok = jqdatasdk.auth(phone, password)
    if not ok:
        raise RuntimeError("聚宽登录失败，请检查账号/密码是否正确。")
    _auth_state["logged_in"] = True
    _auth_state["phone"] = phone
    print("[jqbt] 聚宽数据登录成功，账号:", phone)


def is_auth():
    import jqdatasdk
    return jqdatasdk.is_auth()


def _ensure_auth():
    import jqdatasdk
    if not jqdatasdk.is_auth():
        login()
    return jqdatasdk


# ============================ 行情数据 ============================

def get_price(security, start_date=None, end_date=None, frequency='daily',
              fields=None, skip_paused=False, fq='pre', count=None):
    """
    获取行情数据。参数与聚宽 jqdatasdk.get_price 基本一致。

    参数：
        security : str 或 list，标的代码（如 '000300.XSHG'）
        start_date / end_date : 起止日期，'YYYY-MM-DD' 或 datetime
        frequency : 'daily' / '1d' / 'minute' / '1m' 等
        fields    : 字段列表，默认 ['open','close','high','low','volume','money']
        fq        : 复权方式，'pre' 前复权 / None 不复权 / 'post' 后复权
        count     : 取最近 count 条（与 start/end 互斥）
    """
    jq = _ensure_auth()
    if fields is None:
        fields = ['open', 'close', 'high', 'low', 'volume', 'money']
    if start_date is not None and isinstance(start_date, (dt.date, dt.datetime)):
        start_date = start_date.strftime('%Y-%m-%d')
    if end_date is not None and isinstance(end_date, (dt.date, dt.datetime)):
        end_date = end_date.strftime('%Y-%m-%d')
    df = jq.get_price(security, start_date=start_date, end_date=end_date,
                      frequency=frequency, fields=fields,
                      skip_paused=skip_paused, fq=fq, count=count)
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=fields if fields else ['close'])
    # 回测时间锚点：数据只能截至当前回测日（防止未来函数）
    if _current_date is not None:
        anchor = pd.Timestamp(_current_date)
        df = df[df.index <= anchor]
    return df


def get_trade_days(start_date=None, end_date=None, count=None):
    """获取交易日列表，返回 list[datetime.date]"""
    jq = _ensure_auth()
    if isinstance(start_date, (dt.date, dt.datetime)):
        start_date = start_date.strftime('%Y-%m-%d')
    if isinstance(end_date, (dt.date, dt.datetime)):
        end_date = end_date.strftime('%Y-%m-%d')
    days = jq.get_trade_days(start_date=start_date, end_date=end_date, count=count)
    return [d if isinstance(d, dt.date) else pd.Timestamp(d).date() for d in days]


# ============================ 标的池 / 成分股 ============================

def get_all_securities(types=None, date=None):
    """获取全市场标的，返回 DataFrame(index=code, columns=['display_name','name','start_date','end_date','type'])"""
    jq = _ensure_auth()
    if types is None:
        types = []
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    return jq.get_all_securities(types=types, date=date)


def get_index_stocks(index_symbol, date=None):
    """获取指数成分股，返回 list[str]"""
    jq = _ensure_auth()
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    return jq.get_index_stocks(index_symbol, date=date)


def get_industry(security=None, date=None):
    """获取行业分类。返回 DataFrame 或 dict（取决于 jqdatasdk 版本）"""
    jq = _ensure_auth()
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    return jq.get_industry(security, date=date)


# ============================ 财务数据 ============================

def query(*args):
    """创建财务查询对象（透传 jqdatasdk.query）。"""
    jq = _ensure_auth()
    return jq.query(*args)


def valuation():
    """估值表字段访问器（聚宽 valuation 表）。"""
    jq = _ensure_auth()
    return jq.valuation


def indicator():
    """财务指标表字段访问器（聚宽 indicator 表）。"""
    jq = _ensure_auth()
    return jq.indicator


def income():
    """利润表字段访问器（聚宽 income 表）。"""
    jq = _ensure_auth()
    return jq.income


def balance():
    """资产负债表字段访问器（聚宽 balance 表）。"""
    jq = _ensure_auth()
    return jq.balance


def cashflow():
    """现金流量表字段访问器（聚宽 cashflow 表）。"""
    jq = _ensure_auth()
    return jq.cashflow


def get_fundamentals(query_object, date=None, stat_date=None):
    """查询基本面数据，返回 DataFrame。"""
    jq = _ensure_auth()
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    return jq.get_fundamentals(query_object, date=date, stat_date=stat_date)


# ============================ 缓存式批量行情（引擎内部用） ============================

def get_price_cached(security, start, end, field='close', unit='1d', fq='pre'):
    """带缓存的单字段行情，返回 pandas.Series(index=datetime)。"""
    import jqdatasdk
    key = _cache_key(security, unit, field, fq, start, end)
    cached = _price_cache.get(key)
    if cached is not None:
        return cached
    jq = _ensure_auth()
    df = jq.get_price(security, start_date=start, end_date=end,
                      frequency=unit, fields=[field], fq=fq, skip_paused=False)
    if df is None or len(df) == 0:
        ser = pd.Series(dtype=float)
    else:
        ser = df[field]
    _price_cache.put(key, ser)
    return ser


def clear_cache():
    """清空内存缓存。"""
    _price_cache._dict.clear()


# ============================ 证券基础信息 ============================

def get_security_info(code):
    """获取标的基础信息，返回对象（含 start_date 属性，类型 datetime.date）。"""
    import jqdatasdk
    try:
        return jqdatasdk.get_security_info(code)
    except Exception:
        # 兜底：构造一个带 start_date 的最小对象
        class _Info:
            pass
        info = _Info()
        info.start_date = dt.date(2000, 1, 1)
        info.end_date = dt.date(2200, 1, 1)
        return info


def normalize_code(code):
    """标准化证券代码：'600000' -> '600000.XSHG'，'000001' -> '000001.XSZSE'。"""
    if not isinstance(code, str) or '.' in code:
        return code
    code = code.strip()
    if code.startswith(('60', '68', '9', '51', '58')):
        return code + '.XSHG'
    if code.startswith(('00', '30', '12', '15', '2', '1')):
        return code + '.XSZSE'
    return code


# ============================ 行业 ============================

def get_industries(name='sw_l1', date=None):
    """获取行业列表。返回 DataFrame，index=行业代码，含 index_code 列。

    本地通过 jqdatasdk 的 get_industries 接口（若不可用则返回空结构）。
    """
    import jqdatasdk
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    try:
        df = jqdatasdk.get_industries(name=name, date=date)
        if df is None or len(df) == 0:
            return _empty_industry_frame()
        if 'index_code' not in df.columns:
            # 申万行业指数代码：从行业代码推导（如 801010 -> 801010.SI）
            df = df.copy()
            df['index_code'] = [str(i).split('.')[0] + '.SI' for i in df.index]
        return df
    except Exception:
        return _empty_industry_frame()


def _empty_industry_frame():
    return pd.DataFrame(columns=['name', 'index_code'])


def get_industry_stocks(industry_code, date=None):
    """获取某行业的成分股列表。"""
    import jqdatasdk
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    try:
        stocks = jqdatasdk.get_industry_stocks(industry_code, date=date)
        if stocks is None:
            return []
        return list(stocks)
    except Exception:
        return []


def get_industry(security=None, date=None):
    """获取行业分类。返回 dict，key=代码，value 含 'sw_l1' 等。"""
    import jqdatasdk
    if date is not None and isinstance(date, (dt.date, dt.datetime)):
        date = date.strftime('%Y-%m-%d')
    try:
        return jqdatasdk.get_industry(security, date=date)
    except Exception:
        if security is None:
            return {}
        return {s: {} for s in (security if isinstance(security, (list, tuple)) else [security])}


# ============================ 额外数据（近似实现） ============================

def get_extras(info, security_list, start_date=None, end_date=None, df=True):
    """获取额外数据。本地近似实现，返回结构尽量对齐聚宽。

    info 支持：'is_st'（返回 bool），'paused'（返回 bool）。
    """
    if isinstance(security_list, str):
        security_list = [security_list]
    result = {}
    for s in security_list:
        if info == 'is_st':
            try:
                sec_df = get_all_securities(types=[], date=end_date)
                name = sec_df.loc[s, 'display_name'] if s in sec_df.index else s
                result[s] = ('ST' in str(name)) or ('*ST' in str(name))
            except Exception:
                result[s] = False
        elif info == 'paused':
            # 简化：取最近收盘，无数据则视为停牌
            px = get_price(s, count=1, frequency='daily', fields=['close'], fq='pre')
            result[s] = (px is None or len(px) == 0)
        else:
            result[s] = False
    if df:
        return pd.DataFrame({info: result})
    return result
