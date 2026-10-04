# -*- coding: utf-8 -*-
"""
聚宽账号配置模板
================================================================================
本文件是模板（已提交到 GitHub）。使用步骤：
  1. 把本文件复制一份，改名为 config.py（与本文件同目录）；
  2. 在 config.py 里填写你的真实手机号和密码；
  3. config.py 已被 .gitignore 忽略，不会被提交，放心填密码。

还没有聚宽账号？免费注册：https://www.joinquant.com
（免费账号每月有数据额度，足够本地回测学习使用）

也可以不复制文件，改用环境变量：JQDATA_PHONE / JQDATA_PASSWORD
================================================================================
"""

# 在这里填写你的聚宽账号（手机号）和密码
JQDATA_PHONE = "你的手机号"
JQDATA_PASSWORD = "你的密码"


def auth():
    """登录聚宽数据服务（策略文件里的 login() 会自动读取本文件的账号）。"""
    from jqbt import login
    login(JQDATA_PHONE, JQDATA_PASSWORD)
