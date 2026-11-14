import json, time, requests, os, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from modules.map_headers import header_user_agent
from modules.crypto_aes import aes_encrypt, create_sign

# 全局收集 304 安全验证详情
latest_auth_info = {}

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
    global latest_auth_info
    url = "https://api.moguding.net:9000/attendence/clock/v6/save"
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
    session = requests.Session()
    out_reg = os.getenv("OUT_REGISTER_NO", "").strip()
    data = {
        "country": "中国",
        "address": address,
        "province": province,
        "city": user.get("city", ""),
        "area": user.get("area", ""),
        "latitude": latitude,
        "description": user.get("desc", ""),
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

    res = session.post(url, headers=headers, json=data, verify=False)
    res_text = res.text
    print(f"[CLOCK_API_FIRST] status={res.status_code} body={res.text}", flush=True)

    if "304" in res.text:
        out_reg = os.getenv("OUT_REGISTER_NO", "").strip()
        if out_reg:
            data["outRegisterNo"] = out_reg
            data["t"] = aes_encrypt(str(int(time.time() * 1000)))
            data["sign"] = create_sign(text)
            res = session.post(url, headers=headers, json=data, verify=False)
            res_text = res.text
            print(f"[CLOCK_API_RETRY_WITH_AUTH] status={res.status_code} body={res.text}", flush=True)

        if "304" in res.text or "验证已过期" in res.text or not out_reg:
            h2 = headers.copy()
            h2["client_id"] = "428a8310cd442757ae699df5d89vmgh"
            alipay_url = url.replace("/attendence/clock/v6/save", "/usercenter/alipay/v1/createAxdjk")
            try:
                r2 = session.post(alipay_url, headers=h2, json={}, verify=False)
                r2_json = r2.json()
                print(f"[ALIPAY_CREATE] {r2.text}", flush=True)
                if r2_json.get("code") == 200 and isinstance(r2_json.get("data"), dict):
                    latest_auth_info = r2_json.get("data", {})
            except Exception as e:
                print(f"[ALIPAY_ERROR] {e}", flush=True)

    return res
