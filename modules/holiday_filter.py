import urllib.request
import json
from datetime import datetime, timezone, timedelta

shanghai_tz = timezone(timedelta(hours=8))

def check_workday_status(dt=None):
    """
    检查指定日期是否需要打卡（支持节假日跳过，周六除外打卡）：
    规则：
    1. 周一至周五：若是法定节假日休假则跳过，否则打卡；
    2. 周六：用户特别指定“节假日周六除外”，即周六照常上班打卡（除非周六是国家法定节假日放假）；
    3. 周日：休息日跳过（若周日遇到法定调休补班则打卡）。
    返回：
        (should_checkin: bool, reason: str)
    """
    if dt is None:
        dt = datetime.now(shanghai_tz)

    date_str = dt.strftime("%Y-%m-%d")
    weekday = dt.weekday()  # 0=周一, ..., 5=周六, 6=周日
    weekday_name = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][weekday]

    # 1. 尝试从 timor.tech 查询节假日 API
    try:
        req = urllib.request.Request(
            f"https://timor.tech/api/holiday/info/{date_str}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 0 and "type" in data:
                t = data["type"].get("type")
                # type: 0 基础工作日, 1 基础周末休息日, 2 法定节假日休息, 3 节假日调休补班
                holiday_info = data.get("holiday")
                holiday_name = holiday_info.get("name", "") if holiday_info else ""

                if t == 2:
                    # 法定节假日（如国庆、春节等放假日）
                    return False, f"今日为法定节假日【{holiday_name or '节日'}放假】，自动跳过打卡"
                elif t == 3:
                    # 节假日调休上班
                    return True, f"今日为法定调休工作日【{holiday_name or '补班'}】，正常打卡"
                elif t == 1:
                    # 普通周末
                    if weekday == 5:
                        # 周六：按用户配置“周六除外”，周六照常打卡
                        return True, f"今日为周六（按用户需求正常打卡）"
                    else:
                        # 周日：普通休息日
                        return False, f"今日为周日休息日，自动跳过打卡"
                elif t == 0:
                    # 普通工作日
                    return True, f"今日为工作日（{weekday_name}），正常打卡"
    except Exception as e:
        print(f"[HOLIDAY_API_WARN] timor.tech API 请求失败: {e}，尝试备用接口...", flush=True)

    # 2. 尝试从 jiejiariapi.com 备用接口查询
    try:
        req = urllib.request.Request(
            f"https://api.jiejiariapi.com/v1/holidays/{dt.year}",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, dict):
                day_info = data.get(date_str)
                if day_info:
                    is_off = day_info.get("isOffDay", False)
                    h_name = day_info.get("name", "节假日")
                    if is_off:
                        return False, f"今日为法定节假日【{h_name}放假】，自动跳过打卡"
                    else:
                        return True, f"今日为法定调休工作日【{h_name}补班】，正常打卡"
    except Exception as e:
        print(f"[HOLIDAY_API_WARN] jiejiariapi API 请求失败: {e}，启用内置兜底规则...", flush=True)

    # 3. 兜底本地规则（若所有外部 API 均不可达）
    if weekday == 6:
        # 默认周日休息
        return False, f"今日为周日休息日（本地规则），自动跳过打卡"
    elif weekday == 5:
        # 周六正常打卡
        return True, f"今日为周六（本地规则，按需求正常打卡）"
    else:
        # 周一至周五正常打卡
        return True, f"今日为常规工作日（本地规则，{weekday_name}），正常打卡"
