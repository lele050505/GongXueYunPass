import json, time, requests, uuid, random, base64, struct, cv2, os, hashlib
from modules.crypto_aes import aes_encrypt, aes_decrypt, create_sign
from modules.load_config import dprint
import numpy as np
from typing import Optional

APP_VERSION = "5.44.6"
DART_USER_AGENT = "Dart/3.7 (dart:io)"

request_headers = {
    "user-agent": DART_USER_AGENT,
    "content-type": "application/json; charset=utf-8",
    "accept-encoding": "gzip",
    "host": "api.moguding.net:9000",
}

login_url = "https://api.moguding.net:9000/session/user/v6/login"
captcha_url = "https://api.moguding.net:9000/session/captcha/v1/get"
check_slider_url = "https://api.moguding.net:9000/session/captcha/v1/check"

def get_device_id(user):
    dev = user.get("deviceId") or os.getenv("DEVICE_ID")
    if dev and str(dev).strip():
        return str(dev).strip()
    phone = str(user.get("phone", "default_phone")).strip()
    return hashlib.md5(f"gxy_{phone}_salt_2026".encode()).hexdigest()

def get_cache_file():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, "session_cache.json")

def load_cached_session(phone):
    cache_file = get_cache_file()
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cached = data.get(str(phone))
                if cached and cached.get("token") and cached.get("userId"):
                    return cached
        except Exception:
            pass
    return None

def save_cached_session(phone, user_info):
    cache_file = get_cache_file()
    try:
        data = {}
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[str(phone)] = user_info
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        dprint(f"保存会话缓存失败: {e}")

def check_token_alive(token, userId):
    url = "https://api.moguding.net:9000/practice/plan/v3/getPlanByStu"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "sign": create_sign(str(userId) + "student"),
        "content-type": "application/json; charset=UTF-8",
        "user-agent": DART_USER_AGENT,
    }
    try:
        r = requests.post(url, json={"state": ""}, headers=headers, timeout=6, verify=False)
        return r.status_code == 200 and r.json().get("code") == 200
    except Exception:
        return False

def _post_request(url, headers, data, error_message):
    response = requests.post(url, headers=headers, json=data, verify=False)
    if response.status_code != 200:
        raise ValueError(f"{error_message}: {response.text}")
    return response.json()


def get_token(user, force_refresh=False):
    phone = str(user["phone"]).strip()
    
    # 优先复用持久化 Token，避免频繁滑块登录触发异地/机器风控
    if not force_refresh:
        cached = load_cached_session(phone)
        if cached:
            token = cached.get("token")
            userId = cached.get("userId")
            if token and userId and check_token_alive(token, userId):
                print(f"[SESSION] 复用本地长效登录凭证 (固定设备ID: {get_device_id(user)[:8]}***，免滑块登录)")
                return cached
            else:
                dprint("[SESSION] 缓存凭证已失效，重新执行标准登录")

    fixed_device_id = get_device_id(user)
    data = {
        "phone": aes_encrypt(user["phone"]),
        "password": aes_encrypt(user["password"]),
        "captcha": pass_captcha(client_uid=fixed_device_id),
        "loginType": "android",
        "uuid": fixed_device_id,
        "device": "android",
        "version": APP_VERSION,
        "t": aes_encrypt(str(int(time.time() * 1000))),
    }
    rsp = _post_request(
        login_url,
        request_headers,
        data,
        "登陆失败, 看到这条提示代表官方接口又更新了, 请在github留issue。",
    )
    user_info = json.loads(aes_decrypt(rsp.get("data", "")))
    user_info["cached_at"] = int(time.time())
    user_info["deviceId"] = fixed_device_id
    save_cached_session(phone, user_info)
    print(f"[SESSION] 登录成功并缓存会话凭证 (设备ID已永久固化: {fixed_device_id[:8]}***)")
    return user_info


def pass_captcha(max_attempts: Optional[int] = 5, client_uid: Optional[str] = None) -> str:
    """
    通过行为验证码（验证码类型为blockPuzzle）
    """
    if not client_uid:
        client_uid = str(uuid.uuid4()).replace("-", "")
    attempts = 0
    while attempts < max_attempts:
        time.sleep(random.uniform(0.5, 0.7))
        request_data = {
            "clientUid": client_uid,
            "captchaType": "blockPuzzle",
        }
        captcha_info = _post_request(
            captcha_url, request_headers, request_data, "获取验证码失败"
        )
        slider_data = recognize_captcha(
            captcha_info["data"]["jigsawImageBase64"],
            captcha_info["data"]["originalImageBase64"],
        )
        check_slider_data = {
            "pointJson": aes_encrypt(
                slider_data, captcha_info["data"]["secretKey"], "b64"
            ),
            "token": captcha_info["data"]["token"],
            "captchaType": "blockPuzzle",
        }
        check_result = _post_request(
            check_slider_url, request_headers, check_slider_data, "验证验证码失败"
        )
        if check_result.get("code") != 6111:
            return aes_encrypt(
                captcha_info["data"]["token"] + "---" + slider_data,
                captcha_info["data"]["secretKey"],
                "b64",
            )
        attempts += 1
    raise Exception("验证码验证失败超过最大尝试次数")


def recognize_captcha(target: str, background: str) -> str:
    """识别图像验证码。

    :param target: 目标图像的二进制数据的base64编码
    :type target: str
    :param background: 背景图像的二进制数据的base64编码
    :type background: str

    :return: 滑块需要滑动的距离
    :rtype: str
    """
    target_bytes = base64.b64decode(target)
    background_bytes = base64.b64decode(background)
    res = slide_match(target_bytes=target_bytes, background_bytes=background_bytes)
    target_width = extract_png_width(target_bytes)
    slider_distance = calculate_precise_slider_distance(res[0], res[1], target_width)
    slider_data = {"x": slider_distance, "y": 5}
    return json.dumps(slider_data, separators=(",", ":"))


def slide_match(target_bytes: bytes = None, background_bytes: bytes = None) -> list:
    """获取验证区域坐标

    使用目标检测算法

    :param target_bytes: 滑块图片二进制数据
    :type target_bytes: bytes
    :param background_bytes: 背景图片二进制数据
    :type background_bytes: bytes

    :return: 目标区域左边界坐标, 右边界坐标
    :rtype: list
    """
    target = cv2.imdecode(np.frombuffer(target_bytes, np.uint8), cv2.IMREAD_ANYCOLOR)

    background = cv2.imdecode(
        np.frombuffer(background_bytes, np.uint8), cv2.IMREAD_ANYCOLOR
    )

    background = cv2.Canny(background, 100, 200)
    target = cv2.Canny(target, 100, 200)

    background = cv2.cvtColor(background, cv2.COLOR_GRAY2RGB)
    target = cv2.cvtColor(target, cv2.COLOR_GRAY2RGB)

    res = cv2.matchTemplate(background, target, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
    h, w = target.shape[:2]
    bottom_right = (max_loc[0] + w, max_loc[1] + h)
    return [int(max_loc[0]), int(bottom_right[0])]


def extract_png_width(png_binary):
    """从PNG二进制数据中提取图像宽度。

    该函数从给定的PNG格式二进制数据中提取并返回图像的宽度。

    :param png_binary: PNG图像的二进制数据。
    :type png_binary: bytes

    :return: PNG图像的宽度（以像素为单位）。
    :rtype: int

    :raises ValueError: 如果输入数据不是有效的PNG图像, 抛出包含详细错误信息的异常。
    """
    if png_binary[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("无效的PNG签名：不是有效的PNG图像")
    try:
        width = struct.unpack(">I", png_binary[16:20])[0]
    except struct.error:
        raise ValueError("无法从PNG数据中提取宽度信息")

    return width


def calculate_precise_slider_distance(
    target_start_x: int, target_end_x: int, slider_width: int
) -> float:
    """
    计算滑块需要移动的精确距离, 并添加微小随机偏移。

    :param target_start_x: 目标区域的起始x坐标
    :type: int
    :param target_end_x: 目标区域的结束x坐标
    :type: int
    :param slider_width: 滑块的宽度
    :type: int

    :return: 精确到小数点后14位的滑动距离, 包含微小随机偏移
    :rtype: float
    """
    target_center_x = (target_start_x + target_end_x) / 2
    slider_initial_center_x = slider_width / 2
    precise_distance = target_center_x - slider_initial_center_x
    random_offset = random.uniform(-0.1, 0.1)
    final_distance = round(precise_distance + random_offset, 1)

    return final_distance
