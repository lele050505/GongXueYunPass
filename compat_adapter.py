import os
import json
import requests

def send_serverchan(sendkey, title, content):
    if not sendkey:
        return None
    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = {
        "title": title,
        "desp": content
    }
    try:
        res = requests.post(url, data=data, timeout=10)
        return res.json()
    except Exception as e:
        print(f"Server酱推送失败: {e}")
        return None

def notify_all(title, content):
    sendkey = os.environ.get("SENDKEY")
    if sendkey:
        send_serverchan(sendkey, title, content)

def validate_coordinates(longitude, latitude):
    if not longitude or not latitude:
        return False
    try:
        lon = float(longitude)
        lat = float(latitude)
        return -180.0 <= lon <= 180.0 and -90.0 <= lat <= 90.0
    except (ValueError, TypeError):
        return False

def ensure_user_env():
    user_env = os.environ.get("USER")
    if user_env and user_env.strip():
        try:
            data = json.loads(user_env)
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass

    phone = os.environ.get("PHONE")
    if not phone or not phone.strip():
        print("提示: 未检测到 USER 或 PHONE 环境变量配置。已跳过打卡流程以避免报错。")
        return []

    lon = os.environ.get("LONGITUDE", "")
    lat = os.environ.get("LATITUDE", "")
    if lon and lat and not validate_coordinates(lon, lat):
        print(f"警告: 经纬度格式不正确 (LONGITUDE={lon}, LATITUDE={lat})")

    user_config = {
        "remark": os.environ.get("DESCRIPTION") or "Default",
        "phone": phone.strip(),
        "password": os.environ.get("PASSWORD", ""),
        "province": os.environ.get("PROVINCE", ""),
        "city": os.environ.get("CITY", ""),
        "area": os.environ.get("AREA", ""),
        "address": os.environ.get("ADDRESS", ""),
        "longitude": lon,
        "latitude": lat,
        "randomLocation": True,
        "enable": True,
        "desc": os.environ.get("DESCRIPTION", ""),
        "pushKey": os.environ.get("PUSHPLUS_TOKEN", "")
    }

    user_list = [user_config]
    os.environ["USER"] = json.dumps(user_list, ensure_ascii=False)
    return user_list
