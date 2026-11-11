import json, time, requests
from modules.map_headers import header_user_agent
from modules.crypto_aes import aes_encrypt, create_sign


# 保存用户的签到信息
def save_user_info(
    user,
    userId,
    token,
    planId,
    province,
    address,
    signType="START",
    device="Android",
    latitude=None,
    longitude=None,
):
    url = "https://" + "api.moguding.net:9000/attendence/clock/v6/save"
    text = device + signType + planId + userId + address
    headers = {
        "roleKey": "student",
        "version": "5.43.6",
        "user-agent": "Dart/2.17 (dart:io)",
        "accept-encoding": "gzip",
        "host": "api.moguding.net:9000",
        "sign": create_sign(text),
        "authorization": token,
        "content-type": "application/json; charset=utf-8",
    }
    data = {
        "country": "中国",
        "address": address,
        "province": province,
        "city": user["city"],
        "area": user["area"],
        "latitude": latitude,
        "description": user["desc"],
        "planId": planId,
        "type": signType,
        "device": device,
        "longitude": longitude,
        "state": "NORMAL",
        "attendanceType": "",
        "keys": {},
        "t": aes_encrypt(str(int(time.time() * 1000))),
        "sign": create_sign(text),
    }
    res = requests.post(
        url, headers=headers, data=json.dumps(data), verify=False
    )
    res_text = res.text
    return res, res_text, res import header_user_agent
from modules.crypto_aes import aes_encrypt, create_sign


# 保存用户的签到信息
def save_user_info(
    user,
    userId,
    token,
    planId,
    province,
    address,
    signType="START",
    device="Android",
    latitude=None,
    longitude=None,
):
    url = "https://" + "api.moguding.net:9000/attendence/clock/v6/save"
    text = device + signType + planId + userId + address
    headers = {
        "roleKey": "student",
        "version": "5.43.6",
        "user-agent": "Dart/2.17 (dart:io)",
        "accept-encoding": "gzip",
        "host": "api.moguding.net:9000",
        "sign": create_sign(text),
        "authorization": token,
        "content-type": "application/json; charset=utf-8",
    }
    data = {
        "country": "中国",
        "address": address,
        "province": province,
        "city": user["city"],
        "area": user["area"],
        "latitude": latitude,
        "description": user["desc"],
        "planId": planId,
        "type": signType,
        "device": device,
        "longitude": longitude,
        "state": "NORMAL",
        "attendanceType": "",
        "keys": {},
        "t": aes_encrypt(str(int(time.time() * 1000))),
        "sign": create_sign(text),
    }
    res = requests.post(
        url, headers=headers, data=json.dumps(data), verify=False
    )
    res_text = res.text
    return res, res_text, res

# 保存用户的签到信息
def save_user_info(
    user,
    userId,
    token,
    planId,
    province,
    address,
    signType="START",
    device="Android",
    latitude=None,
    longitude=None,
):
    text = device + signType + planId + userId + address
    headers = {
        "roleKey": "student","version": "5.43.6",
        
        "user-agent": header_user_agent(user),
        "sign": create_sign(text),
        "authorization": token,
        "content-type": "application/json; charset=UTF-8",
    }
    data = {
        "country": "中国",
        "address": address,
        "province": province,
        "city": user["city"],
        "area": user["area"],
        "latitude": latitude,
        "description": user["desc"],
        "planId": planId,
        "type": signType,
        "device": device,
        "longitude": longitude,
    }
    url = "https://api.moguding.net:9000/attendence/clock/v6/save"
    res = requests.post(url=url, headers=headers, data=json.dumps(data))
    # 检查响应是否有效
    try:
        response_json = res.json()
    except json.JSONDecodeError:
        msg = f"服务器返回了无效的 JSON 响应: {res.text},看到这条提示代表官方接口又更新了, 请在github留issue。"
        return False, msg, None
    # 正常处理响应
    return response_json["code"] == 200, response_json["msg"], response_json
