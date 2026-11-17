import random


# 统一客户端官方 User-Agent (Flutter/Dart 官方内核，与打卡接口保持绝对一致)
def header_user_agent(user=None):
    ua = "Dart/3.7 (dart:io)"
    if user and isinstance(user, dict):
        user["user-agent"] = ua
    return ua
