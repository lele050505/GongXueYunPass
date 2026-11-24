import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from modules.map_headers import header_user_agent
from modules.crypto_aes import create_sign
from modules.get_plan_id import get_plan_id
from modules.ai_report_generator import generate_report_content

shanghai_tz = timezone(timedelta(hours=8))
BASE_URL = "https://api.moguding.net:9000"

def get_submitted_reports(token, plan_id, report_type="week"):
    """
    获取学生在当前实习计划下已提交的报告列表
    report_type: 'week' (周报) 或 'month' (月报)
    """
    url = f"{BASE_URL}/practice/paper/v2/listByStu"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "content-type": "application/json; charset=UTF-8"
    }
    # 工学云 reportType 参数：通常 2 或 'week'
    type_param = "week" if report_type == "week" else "month"
    payload = {
        "planId": plan_id,
        "reportType": type_param,
        "page": 1,
        "pageSize": 50
    }
    try:
        res = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
        res_json = res.json()
        if res_json.get("code") == 200 and isinstance(res_json.get("data"), list):
            return res_json["data"]
    except Exception as e:
        print(f"[REPORT_QUERY_WARN] 查询历史已提交报告失败: {e}", flush=True)
    return []

def get_available_weeks(token, plan_id):
    """
    获取当前实习计划的所有开放周次列表
    """
    url = f"{BASE_URL}/practice/paper/v3/getWeeks1"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "content-type": "application/json; charset=UTF-8"
    }
    try:
        res = requests.post(url, json={"planId": plan_id}, headers=headers, verify=False, timeout=10)
        res_json = res.json()
        if res_json.get("code") == 200 and isinstance(res_json.get("data"), list):
            return res_json["data"]
    except Exception as e:
        print(f"[REPORT_WEEKS_WARN] 查询开放周次列表失败: {e}", flush=True)
    return []

def submit_single_report(user, token, plan_id, report_type, title, content, weeks_str=None, yearmonth=None, start_time=None, end_time=None):
    """
    向工学云提交单篇报告 (周报 / 月报)
    """
    url = f"{BASE_URL}/practice/paper/v5/save"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": header_user_agent(user),
    }

    address = user.get("address", "")
    lat = user.get("latitude", "")
    lng = user.get("longitude", "")

    payload = {
        "planId": plan_id,
        "reportType": report_type,
        "title": title,
        "content": content,
        "address": address,
        "longitude": lng,
        "latitude": lat,
        "attachments": ""
    }

    if report_type == "week":
        if weeks_str:
            payload["weeks"] = weeks_str
        if start_time and end_time:
            payload["startTime"] = start_time
            payload["endTime"] = end_time
    elif report_type == "month":
        if yearmonth:
            payload["yearmonth"] = yearmonth

    try:
        res = requests.post(url, json=payload, headers=headers, verify=False, timeout=12)
        print(f"[REPORT_SUBMIT_RESP] 提交报告 [{title}] 响应: {res.text}", flush=True)
        return res.json()
    except Exception as e:
        print(f"[REPORT_SUBMIT_ERROR] 提交报告 [{title}] 异常: {e}", flush=True)
        return {"code": 500, "msg": str(e)}

def auto_manage_reports(user, token, user_id):
    """
    自动检查历史周报/月报：
    1. 查询已提交报告，避免重复提交；
    2. 延续历史序号，自动补交此前漏交的周报；
    3. 若本周周报尚未提交，则通过 AI 生成高质量内容并提交；
    4. 若本月月报尚未提交，则补齐提交。
    """
    results = []
    try:
        sign_info = create_sign(str(user_id) + "student")
        plan_id = get_plan_id(user, token, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习计划 planId: {plan_id}", flush=True)

        # 1. 查询已提交的周报记录
        submitted_weeks_data = get_submitted_reports(token, plan_id, report_type="week")
        submitted_titles = [r.get("title", "") for r in submitted_weeks_data]
        submitted_weeks = [r.get("weeks", "") for r in submitted_weeks_data if r.get("weeks")]
        print(f"[REPORT_MANAGER] 已提交周报数量: {len(submitted_weeks_data)} 篇，已提交周次: {submitted_weeks}", flush=True)

        # 2. 查询系统支持的所有周次
        open_weeks_data = get_available_weeks(token, plan_id)
        
        # 如果获取到了周次列表，检查是否有遗漏未提交的周次
        if open_weeks_data:
            print(f"[REPORT_MANAGER] 系统开放周次数量: {len(open_weeks_data)} 周", flush=True)
            for w in open_weeks_data:
                w_str = w.get("weeks") or w.get("week")
                w_start = w.get("startTime")
                w_end = w.get("endTime")
                if not w_str:
                    continue
                
                # 判断当前周是否已经提交过
                already_done = any(w_str in sub or sub in w_str for sub in submitted_weeks)
                if not already_done:
                    # 补交该周周报！
                    title_hint = f"第{w_str}周实习周报"
                    title, content = generate_report_content("week", title_hint=title_hint, extra_context=f"第{w_str}周, 日期{w_start}~{w_end}", user=user)
                    print(f"[REPORT_MANAGER] 发现未提交周报，开始自动提交: {title}", flush=True)
                    submit_res = submit_single_report(
                        user, token, plan_id, "week",
                        title=title, content=content,
                        weeks_str=w_str, start_time=w_start, end_time=w_end
                    )
                    results.append(f"周报【{title}】补交结果: {submit_res.get('msg', '已提交')}")
                    time.sleep(2) # 间隔防止频繁
        else:
            # 兜底：若接口未返回详细周次列表，根据已提交数量推算并生成下一篇周报
            next_week_num = len(submitted_weeks_data) + 1
            # 仅在周末或周五/周六执行提交
            today_weekday = datetime.now(shanghai_tz).weekday()
            if today_weekday in [4, 5, 6] or len(submitted_weeks_data) == 0:
                title_hint = f"第{next_week_num}周实习周报"
                title, content = generate_report_content("week", title_hint=title_hint, extra_context=f"第{next_week_num}周", user=user)
                print(f"[REPORT_MANAGER] 推算提交本周周报: {title}", flush=True)
                submit_res = submit_single_report(
                    user, token, plan_id, "week",
                    title=title, content=content,
                    weeks_str=str(next_week_num)
                )
                results.append(f"周报【{title}】提交: {submit_res.get('msg', '成功')}")

        # 3. 检查月报
        now_dt = datetime.now(shanghai_tz)
        current_yearmonth = now_dt.strftime("%Y-%m")
        submitted_months = get_submitted_reports(token, plan_id, report_type="month")
        month_done = any(current_yearmonth in (m.get("yearmonth", "") or m.get("title", "")) for m in submitted_months)
        if not month_done and now_dt.day >= 20:
            # 每月 20 号之后自动提交当月月报
            title_hint = f"{now_dt.month}月份实习月报总结"
            title, content = generate_report_content("month", title_hint=title_hint, extra_context=f"月份:{current_yearmonth}", user=user)
            print(f"[REPORT_MANAGER] 准备提交当月月报: {title}", flush=True)
            submit_res = submit_single_report(
                user, token, plan_id, "month",
                title=title, content=content,
                yearmonth=current_yearmonth
            )
            results.append(f"月报【{title}】提交: {submit_res.get('msg', '成功')}")

    except Exception as e:
        print(f"[REPORT_MANAGER_ERROR] 自动管理周月报异常: {e}", flush=True)
        results.append(f"报告自动处理异常: {e}")

    summary_msg = "；".join(results) if results else "本周与本月报告均已提交或已处于最新状态，无需重复补交。"
    print(f"[REPORT_MANAGER] 最终报告处理概况: {summary_msg}", flush=True)
    return {"status": "success", "message": summary_msg}
