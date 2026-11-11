import compat_adapter
compat_adapter.ensure_user_env()

from modules.load_config import load_config, dprint
from modules.send_sign_in_threading import send_sign_in_threading

dprint.DEBUG = False

def handler(event, context):
    compat_adapter.ensure_user_env()
    users = load_config()
    if not users:
        print("未检测到有效的用户配置，跳过打卡任务。")
        return
    res = send_sign_in_threading(users)
    compat_adapter.notify_all("工学云打卡结果通知", str(res))

handler(0, 0)
