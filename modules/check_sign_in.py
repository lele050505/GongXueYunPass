import requests
from modules.load_config import dprint
from datetime import datetime, timezone, timedelta

shanghai_tz = timezone(timedelta(hours=8))


# 查用户是否已经打卡
def check_sign(check_sign_token, sign_type):
    check_sign_url = "https://api.moguding.net:9000/attendence/clock/v2/listSynchro"
    search_start_time, search_end_time = get_current_day()
    data = {
        "startTime": search_start_time,
        "endTime": search_end_time,
    }
    headers = {"Authorization": f"{check_sign_token}"}
    response = requests.post(check_sign_url, json=data, headers=headers)
    response_data = response.json()

    if not isinstance(response_data, dict) or 'data' not in response_data or not response_data['data']:
        return False
    for record in response_data["data"]:
        if record["type"] == sign_type:
            return True
    return False


# 获取当天起始时间（以东八区上海时间为基准）
def get_current_day():
    now = datetime.now(shanghai_tz)
    start_of_day = datetime(now.year, now.month, now.day)
    end_of_day = start_of_day + timedelta(days=1, seconds=-1)
    day_start_time = start_of_day.strftime("%Y-%m-%d 00:00:00")
    day_end_time = end_of_day.strftime("%Y-%m-%d 23:59:59")
    return day_start_time, day_end_time
