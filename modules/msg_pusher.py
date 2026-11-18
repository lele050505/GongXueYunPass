import requests
from modules.load_config import dprint


# 推送消息到PushPlus
def push_to_pushplus(users, title, content, token):
    if not token or not str(token).strip():
        return
    url = "https://www.pushplus.plus/send"
    try:
        resp = requests.post(url, json={
            "token": str(token).strip(),
            "title": title,
            "content": content,
            "template": "html"
        }, timeout=10)
        result = resp.json()
        if result.get("code") == 200:
            for user in users:
                dprint(f'[{user["remark"]}/{user["phone"]}]', end="")
                print(f"√ 微信消息推送成功！", end="")
                dprint(f"响应内容: {resp.text}")
        else:
            for user in users:
                dprint(f'[{user["remark"]}/{user["phone"]}]', end="")
                print(f"X 微信消息推送失败！", end="")
                dprint(f"响应内容: {resp.text}")
    except Exception as e:
        print(f"X 微信消息推送异常: {e}")
