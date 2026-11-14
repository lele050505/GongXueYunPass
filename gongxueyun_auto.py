import os
import sys
import argparse
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header

import requests
import compat_adapter
from modules.load_config import load_config
from modules.send_sign_in_threading import send_sign_in_threading

def setup_proxy():
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    proxy_api_url = os.environ.get("PROXY_API_URL", "").strip()
    selected_proxy = None

    if proxy_api_url:
        try:
            print(f"[PROXY] 从 API 获取动态代理: {proxy_api_url}")
            resp = requests.get(proxy_api_url, timeout=10)
            text = resp.text.strip()
            if text:
                if text.startswith("{"):
                    try:
                        data = json.loads(text)
                        ip = data.get("ip") or (data.get("data") and data["data"][0].get("ip"))
                        port = data.get("port") or (data.get("data") and data["data"][0].get("port"))
                        if ip and port:
                            selected_proxy = f"http://{ip}:{port}"
                    except Exception:
                        pass
                else:
                    selected_proxy = text if text.startswith("http") else f"http://{text}"
                if selected_proxy:
                    print(f"[PROXY] 成功获取 API 代理: {selected_proxy}")
        except Exception as e:
            print(f"[PROXY] 从 API 获取代理失败: {e}")

    if not selected_proxy and proxy_url:
        selected_proxy = proxy_url if (proxy_url.startswith("http") or proxy_url.startswith("socks")) else f"http://{proxy_url}"
        print(f"[PROXY] 使用静态 PROXY_URL: {selected_proxy}")

    if selected_proxy:
        os.environ["HTTP_PROXY"] = selected_proxy
        os.environ["HTTPS_PROXY"] = selected_proxy
        os.environ["http_proxy"] = selected_proxy
        os.environ["https_proxy"] = selected_proxy
        print(f"[PROXY] 代理配置成功: {selected_proxy}")
    else:
        print("[PROXY] 未配置或无需使用代理，采用默认直连模式。")

def push_email(mail_host, mail_user, mail_pass, sender, receivers, title, content):
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = Header(sender, 'utf-8')
    message['To'] = Header(receivers[0], 'utf-8')
    message['Subject'] = Header(title, 'utf-8')
    try:
        smtpObj = smtplib.SMTP_SSL(mail_host, 465)
        smtpObj.login(mail_user, mail_pass)
        smtpObj.sendmail(sender, receivers, message.as_string())
        print("[EMAIL] 邮件发送成功")
    except smtplib.SMTPException as e:
        print(f"[EMAIL] 邮件发送失败: {e}")

def main():
    parser = argparse.ArgumentParser(description="GongXueYun Auto Checkin & Report Script")
    parser.add_argument("--mode", choices=["auto", "clock", "report", "all"], default="auto", help="运行模式: auto(打卡或日报), clock(仅打卡), report(仅日报), all(全执行)")
    args = parser.parse_args()

    setup_proxy()

    try:
        config = load_config()
    except Exception as e:
        print(f"[CONFIG] 配置加载失败: {e}")
        sys.exit(1)

    users = config.get("users", [])
    if not users:
        print("[CONFIG] 警告: 未检测到配置的用户列表，请检查环境变量或配置文件。")
        sys.exit(0)

    print(f"[MAIN] 运行模式: {args.mode}，用户总数: {len(users)}")
    send_sign_in_threading(users, mode=args.mode)

if __name__ == "__main__":
    main()
