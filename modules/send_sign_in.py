import os, random, threading
from modules.get_plan_id import get_plan_id
from modules.get_login_token import get_token
from modules.crypto_aes import create_sign
from modules.check_sign_in import check_sign
from modules.save_user_info import save_user_info
from datetime import datetime, timezone, timedelta
from modules.load_config import dprint


# 操作地时区设置
shanghai_tz = timezone(timedelta(hours=8))
gmt_time = datetime.now(shanghai_tz)
now = datetime.now(shanghai_tz)
# 以16时为分界线, 判断打卡是上班还是下班 (适配下午17:30开机的下班打卡)
is_start = now.hour < 16
# 中文映射字典, 用于控制台输出罢了
sign_type_mapping = {"START": "上班", "END": "下班"}
# 收集所有线程签到结果
global_sign_results = []
# 覆盖打卡，设置为True会导致每次运行都不检查签到历史从而重复签到，用于测试环境调试
RepeatCheckIn = False


# 处理单个用户的签到流程, 包括获取登录令牌、签到计划 ID、检查是否已签到以及执行签到操作。
def send_sign_in(user_info, timeout):
    try:
        timer = threading.Timer(timeout, lambda: None)
        timer.start()
        userInfo = get_token(user_info)
        phone = user_info["phone"]
        remark = user_info.get("remark", "")

        user_info_prefix = f"[{remark}/{phone}]"

        # ❗开发环境输出, 包含敏感内容, 打印登录响应内容
        # dprint(f"{user_info_prefix} 登录响应: {userInfo}\n")

        # 智能拟人化 GPS 经纬度微小漂移 (约 20~60 米范围内随机自然浮动，模拟真实定位误差与不同站位)
        try:
            base_lat = float(user_info.get("latitude", 0))
            base_lng = float(user_info.get("longitude", 0))
            if base_lat != 0 and base_lng != 0:
                # 0.0001 纬度约等于 11 米；0.0001 经度约等于 9 米
                delta_lat = random.uniform(-0.00035, 0.00035)
                delta_lng = random.uniform(-0.00035, 0.00035)
                user_info["latitude"] = f"{base_lat + delta_lat:.6f}"
                user_info["longitude"] = f"{base_lng + delta_lng:.6f}"
                dprint(f"{user_info_prefix} GPS拟真坐标微调: ({user_info['latitude']}, {user_info['longitude']})\n")
        except Exception as e:
            dprint(f"{user_info_prefix} GPS拟真浮动计算异常: {e}\n")

        if not user_info:
            global_sign_results.append(
                f"{user_info_prefix}打卡失败, 错误原因: {userInfo['msg']}"
            )
            return
        userId = userInfo["userId"]
        token = userInfo["token"]
        sign_info = create_sign(userId + "student")
        planId = get_plan_id(user_info, token, sign_info)
        # 检查是否由环境变量显式指定 (START=上班, END=下班)
        sign_type_env = os.environ.get("SIGN_TYPE", "").strip().upper()
        if sign_type_env in ["START", "END"]:
            signType = sign_type_env
        else:
            signType = "START" if is_start else "END"
        # 检查是否已经打过卡，避免重复打卡, 不需要检查的话可以注释掉整个if块
        force_checkin = os.environ.get("FORCE_CHECKIN", "").strip().lower() in ["1", "true", "yes"]
        if check_sign(token, signType, userId=userId, sign_info=sign_info) and not RepeatCheckIn and not force_checkin:
            msg_skipped = f"{user_info_prefix}今日已打过{sign_type_mapping[signType]}卡，无需重复打卡（任务正常跳过）。"
            dprint(f"{user_info_prefix}")
            print(f"已打过{sign_type_mapping[signType]}卡, 任务跳过。\n")
            global_sign_results.append(msg_skipped)
            from modules.msg_pusher import push_to_pushplus
            push_key = user_info.get("pushKey") or os.environ.get("PUSHPLUS_TOKEN") or os.environ.get("SECRET")
            if push_key:
                push_to_pushplus([user_info], f"工学云{sign_type_mapping[signType]}打卡状态确认", msg_skipped, push_key)
            return
        dprint(f"{user_info_prefix}", end="")
        print(f"准备{sign_type_mapping[signType]}打卡\n")
        # 发送请求
        try:
            signResp, msg, full_response = save_user_info(
                user_info,
                userId,
                token,
                planId,
                user_info["province"],
                user_info["address"],
                signType=signType,
                latitude=user_info["latitude"],
                longitude=user_info["longitude"],
            )
            # 打印完整的打卡响应内容
            dprint(f"{user_info_prefix}打卡响应状态: {signResp.status_code}, 响应内容: {msg}\n")
        except Exception as e:
            error_message = f"{user_info_prefix}打卡失败, 错误原因: {str(e)}"
            dprint(error_message)
            global_sign_results.append(error_message)
            return
        # 构建推送消息
        pushSignType = "上班" if signType == "START" else "下班"
        status_detail = ""
        try:
            resp_dict = full_response.json()
            code = resp_dict.get("code")
            msg_str = str(resp_dict.get("msg", ""))
            if code == 200 and msg_str != "304":
                status_detail = "成功！"
            elif msg_str == "304" or "304" in msg_str:
                status_detail = "需支付宝实名安全验证(已生成验证链接)"
            else:
                status_detail = f"失败({msg_str})"
        except Exception:
            status_detail = "成功！" if signResp.status_code == 200 else f"失败({signResp.status_code})"

        signStatus = "打卡"
        hourNow = gmt_time.hour
        if hourNow == 11 or hourNow == 23:
            signStatus = "补签"
        global_sign_results.append(
            f"{user_info_prefix}工学云{pushSignType}{signStatus}{status_detail}\n"
        )
    finally:
        timer.cancel()
