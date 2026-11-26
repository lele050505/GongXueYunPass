import os
import sys
import argparse
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from urllib.parse import urlsplit

import requests
import compat_adapter
from modules.load_config import load_config
from modules.send_sign_in_threading import send_sign_in_threading

def _mask_proxy_url(proxy_url: str) -> str:
    """
    脱敏代理 URL 中的认证凭据，防止账号密码以明文形式输出到日志
    """
    if not proxy_url:
        return ""
    try:
        parsed = urlsplit(proxy_url)
        if parsed.username is not None or parsed.password is not None:
            host_port = parsed.hostname or ""
            if parsed.port:
                host_port = f"{host_port}:{parsed.port}"
            scheme = f"{parsed.scheme}://" if parsed.scheme else ""
            path = parsed.path or ""
            return f"{scheme}***@{host_port}{path}"
    except Exception:
        pass
    if "@" in proxy_url:
        scheme_sep = proxy_url.find("://")
        at_idx = proxy_url.rfind("@")
        if scheme_sep != -1 and at_idx > scheme_sep:
            return f"{proxy_url[:scheme_sep + 3]}***@{proxy_url[at_idx + 1:]}"
        return f"***@{proxy_url[at_idx + 1:]}"
    return proxy_url

def setup_proxy():
    proxy_url = os.environ.get("PROXY_URL", "").strip()
    proxy_api_url = os.environ.get("PROXY_API_URL", "").strip()
    selected_proxy = None

    if proxy_api_url:
        try:
            print(f"[PROXY] Fetching dynamic proxy from API: {proxy_api_url}")
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
                    print(f"[PROXY] Obtained proxy from API: {_mask_proxy_url(selected_proxy)}")
        except Exception as e:
            print(f"[PROXY] Failed to fetch proxy from API: {e}")

    if not selected_proxy and proxy_url:
        selected_proxy = proxy_url if (proxy_url.startswith("http") or proxy_url.startswith("socks")) else f"http://{proxy_url}"
        print(f"[PROXY] Using static PROXY_URL: {_mask_proxy_url(selected_proxy)}")

    if selected_proxy:
        os.environ["HTTP_PROXY"] = selected_proxy
        os.environ["HTTPS_PROXY"] = selected_proxy
        os.environ["http_proxy"] = selected_proxy
        os.environ["https_proxy"] = selected_proxy
        existing_no_proxy = [item.strip() for item in os.environ.get("NO_PROXY", "").split(",") if item.strip()]
        for host in ("api.github.com", "github.com", "localhost", "127.0.0.1"):
            if host not in existing_no_proxy:
                existing_no_proxy.append(host)
        no_proxy_val = ",".join(existing_no_proxy)
        os.environ["NO_PROXY"] = no_proxy_val
        os.environ["no_proxy"] = no_proxy_val
        print(f"[PROXY] Proxy configured successfully: {_mask_proxy_url(selected_proxy)}")
        print(f"[PROXY] NO_PROXY configured: {no_proxy_val}")
    else:
        print("[PROXY] 直连模式（Direct Connection，直连工学云 9000 端口）")
        try:
            from modules.network_patch import apply_network_patch
            apply_network_patch()
        except Exception as e:
            print(f"[NET_PATCH_WARN] 物理网卡补丁载入提示: {e}")

def send_email(subject, content, recipient="jule85610@gmail.com"):
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_user = os.getenv("SMTP_USER", "jule85610@gmail.com")
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    if not smtp_password:
        print(f"[CLOCK_API_RAW] SMTP_PASSWORD not provided. Email notification to {recipient} skipped.")
        return False
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = Header(smtp_user, 'utf-8')
        msg['To'] = Header(recipient, 'utf-8')
        msg['Subject'] = Header(subject, 'utf-8')
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [recipient], msg.as_string())
        server.quit()
        print(f"[CLOCK_API_RAW] Email successfully sent to {recipient}")
        return True
    except Exception as e:
        print(f"[CLOCK_API_RAW] Email send error: {e}")
        return False

def submit_reports(users):
    """
    智能周报与月报自动管理：
    自动检查历史周报与月报，无缝延续已有序号，对漏交的周报进行智能补齐提交
    """
    if not users:
        return {"status": "skipped", "message": "No user found"}
    user = users[0]
    try:
        from modules.get_login_token import get_token
        userInfo = get_token(user)
        if userInfo and userInfo.get("token") and userInfo.get("userId"):
            from modules.report_manager import auto_manage_reports
            res = auto_manage_reports(user, userInfo["token"], userInfo["userId"])
            print(f"[CLOCK_API_RAW] Report submission result: {json.dumps(res, ensure_ascii=False)}")
            return res
        err_res = {"status": "error", "message": "登录未返回有效 token/userId，跳过周月报提交"}
        print(f"[CLOCK_API_RAW] Report submission result: {json.dumps(err_res, ensure_ascii=False)}")
        return err_res
    except Exception as e:
        print(f"[REPORT_SUBMIT_WARN] 自动提交报告流程异常: {e}")
        report_res = {"status": "error", "message": f"自动提交报告异常: {e}"}
        print(f"[CLOCK_API_RAW] Report submission result: {json.dumps(report_res, ensure_ascii=False)}")
        return report_res

def main():
    parser = argparse.ArgumentParser(description="GongXueYun Pass Auto Clock & Report")
    parser.add_argument("--mode", type=str, default="auto", help="Execution mode: auto, clock, report")
    args = parser.parse_args()

    print(f"[CLOCK_API_RAW] Initializing GongXueYun Auto with mode={args.mode}")

    # 1. 节假日智能跳过（周六除外打卡）检测（报告模式不跳过）
    force_checkin = os.environ.get("FORCE_CHECKIN", "").strip().lower() in ["1", "true", "yes"]
    if args.mode != "report":
        try:
            from modules.holiday_filter import check_workday_status
            should_checkin, holiday_reason = check_workday_status()
            print(f"[HOLIDAY_CHECK] {holiday_reason}", flush=True)
            if not should_checkin and not force_checkin:
                print(f"[HOLIDAY_CHECK] 任务跳过: {holiday_reason}")
                # 推送一条休息日轻量提醒
                compat_adapter.notify_all("工学云休息日提醒", f"📅 {holiday_reason}\n今日不执行自动打卡，祝您休息愉快！")
                return
        except Exception as e:
            print(f"[HOLIDAY_CHECK_WARN] 节假日检测异常: {e}，默认继续执行打卡")

    # 2. 拟人化随机延迟 (0~5 分钟随机抖动，避免秒级固定打卡特征)
    if os.environ.get("GITHUB_ACTIONS") and not force_checkin and args.mode != "report":
        import random, time
        # 随机 10 到 180 秒微延迟
        delay_sec = random.randint(15, 150)
        print(f"[JITTER] 开启防风控拟人化时间随机抖动，随机延迟 {delay_sec} 秒后开始打卡...", flush=True)
        time.sleep(delay_sec)

    setup_proxy()

    compat_adapter.ensure_user_env()
    users = load_config()
    if isinstance(users, dict):
        users = [users] if users else []
    print(f"[CLOCK_API_RAW] Loaded {len(users)} user configuration(s)")

    if not users:
        print("[CLOCK_API_RAW] No valid user configuration found. Skipping sign-in.")
        return

    clock_res = {}
    report_res = {}

    if args.mode == "report":
        print("[CLOCK_API_RAW] 当前为周月报专项模式，跳过打卡直接执行周月报自动管理与补齐", flush=True)
        clock_res = {"status": "skipped", "message": "Report mode"}
        report_res = submit_reports(users)
    elif args.mode == "clock":
        clock_res = send_sign_in_threading(users)
        print(f"[CLOCK_API_RAW] Clock/Sign-in result: {json.dumps(clock_res, ensure_ascii=False)}")
        report_res = {"status": "skipped", "message": "Clock only mode"}
    else:
        clock_res = send_sign_in_threading(users)
        print(f"[CLOCK_API_RAW] Clock/Sign-in result: {json.dumps(clock_res, ensure_ascii=False)}")
        report_res = submit_reports(users)

    auth_notice = ""
    try:
        from modules.save_user_info import latest_auth_info
        if latest_auth_info and latest_auth_info.get("registerUrl"):
            reg_url = latest_auth_info.get("registerUrl")
            out_no = latest_auth_info.get("outRegisterNo")
            auth_notice = (
                f"\n\n【重要：工学云 304 安全风控提示】\n"
                f"平台检测到异地/海外 IP 访问，需在手机支付宝完成一次实名验证：\n"
                f"1. 最新验证单号: {out_no}\n"
                f"2. 支付宝直跳验证链接: {reg_url}\n"
                f"（提示：若后续在 GitHub Secrets 配置国内 PROXY_URL，可避开海外 IP 风控直接打卡成功）"
            )
            print(f"[CLOCK_API_RAW] {auth_notice}")
    except Exception as e:
        print(f"[CLOCK_API_RAW] Error compiling auth notice: {e}")

    notify_content = f"工学云自动化运行结果 ({args.mode}):\n打卡结果: {json.dumps(clock_res, ensure_ascii=False)}\n报告结果: {json.dumps(report_res, ensure_ascii=False)}{auth_notice}"
    compat_adapter.notify_all("工学云打卡与周月报通知", notify_content)

    email_subject = "工学云需要安全验证提醒" if auth_notice else "工学云自动打卡与报告结果通知"
    send_email(email_subject, notify_content, recipient="jule85610@gmail.com")

    # 3. 自动清理与归档已超时的历史 Issue，保持仓库看板清爽干净
    try:
        from modules.clean_issues import clean_old_issues
        clean_old_issues(keep_open_max=2)
    except Exception as e:
        print(f"[ISSUE_CLEAN_WARN] 清理历史 Issue 异常: {e}")

if __name__ == "__main__":
    main()
