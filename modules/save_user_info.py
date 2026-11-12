import json, time, requests, os
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
    longitude=None
):
    url = "https://" + "api.moguding.net:9000/attendence/clock/v6/save"
    text = device + signType + planId + userId + address
    headers = {
        "roleKey": "student",
        "version": "v6.0",
        "user-agent": "Dart/3.7 (dart:io)",
        "appversion": "6.0.0",
        "device": "Android",
        "accept-encoding": "gzip",
        "host": "api.moguding.net:9000",
        "sign": create_sign(text),
        "authorization": token,
        "content-type": "application/json; charset=utf-8"
    }
    out_reg = os.getenv("OUT_REGISTER_NO", "")
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
        "outRegisterNo": out_reg if out_reg else None
    }
    res = requests.post(url, headers=headers, data=json.dumps(data), verify=False)
    res_text = res.text
    print(f"[CLOCK_API_RAW] status={res.status_code} body={res.text}", flush=True)
    if "304" in res.text:
        h2 = headers.copy()
        h2["client_id"] = "428a8310cd442757ae699df5d89vmgh"
        alipay_url = url.replace("/attendence/clock/v6/save", "/usercenter/alipay/v1/createAxdjk")
        r2 = requests.post(alipay_url, headers=h2, json={}, verify=False)
        print(f"[ALIPAY_304_CREATE] {r2.text}", flush=True)
    return res, res_text, res
  
