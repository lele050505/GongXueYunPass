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

def get_job_info(user, token, plan_id, sign_info):
    """
    获取学生在当前实习计划下的岗位详情，提取 jobId 与 studentId
    """
    url = f"{BASE_URL}/practice/job/v4/infoByStu"
    headers = {
        "roleKey": "student",
        "version": "v6.0",
        "appversion": "6.0.0",
        "device": "Android",
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=utf-8",
        "user-agent": "Dart/3.7 (dart:io)",
    }
    try:
        res = requests.post(url, json={"planId": plan_id}, headers=headers, verify=False, timeout=10)
        res_json = res.json()
        print(f"[REPORT_DEBUG] infoByStu 响应状态: {res.status_code}, code: {res_json.get('code')}", flush=True)
        if res_json.get("code") == 200:
            data = res_json.get("data")
            if isinstance(data, dict):
                job_id = data.get("jobId") or data.get("id")
                student_id = data.get("studentId")
                print(f"[REPORT_DEBUG] 成功解析 jobId: {job_id}, studentId: {student_id}", flush=True)
                return job_id, student_id, data
            elif isinstance(data, list) and len(data) > 0:
                item = data[0]
                job_id = item.get("jobId") or item.get("id")
                student_id = item.get("studentId")
                return job_id, student_id, item
    except Exception as e:
        print(f"[REPORT_JOB_WARN] 获取岗位信息异常: {e}", flush=True)
    return None, None, {}

def get_available_weeks(user, token, plan_id, sign_info):
    """
    获取当前实习计划的所有开放周次列表
    """
    url = f"{BASE_URL}/practice/paper/v3/getWeeks1"
    headers = {
        "roleKey": "student",
        "version": "v6.0",
        "appversion": "6.0.0",
        "device": "Android",
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=utf-8",
        "user-agent": "Dart/3.7 (dart:io)",
    }
    try:
        res = requests.post(url, json={"planId": plan_id}, headers=headers, verify=False, timeout=10)
        res_json = res.json()
        if res_json.get("code") == 200:
            data = res_json.get("data")
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                for k in ["list", "rows", "records", "weeks"]:
                    if isinstance(data.get(k), list):
                        return data[k]
    except Exception as e:
        print(f"[REPORT_WEEKS_WARN] 查询开放周次列表失败: {e}", flush=True)
    return []

def submit_single_report(user, token, plan_id, job_id, student_id, sign_info, report_type, title, content, weeks_str=None, user_week_num=None, yearmonth=None, start_time=None, end_time=None):
    """
    向工学云提交单篇报告 (周报 / 月报)，含自适应版本回退与双键对齐
    """
    headers = {
        "roleKey": "student",
        "version": "v6.0",
        "appversion": "6.0.0",
        "device": "Android",
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=utf-8",
        "user-agent": "Dart/3.7 (dart:io)",
    }

    address = user.get("address", "")
    lat = str(user.get("latitude", "")) if user.get("latitude") is not None else ""
    lng = str(user.get("longitude", "")) if user.get("longitude") is not None else ""

    # 尝试不同端点版本：v6, v5, v2
    api_urls = [
        f"{BASE_URL}/practice/paper/v6/save",
        f"{BASE_URL}/practice/paper/v5/save",
        f"{BASE_URL}/practice/paper/v2/save",
    ]

    # 提取周次数字
    w_digits = ""
    if weeks_str:
        for ch in str(weeks_str):
            if ch.isdigit():
                w_digits += ch

    # 构造多种周次表达（字符串 "第5周"、纯数字字符串 "5"、整数 5、用户自然周 15 等）
    weeks_candidates = []
    if report_type == "week":
        if weeks_str:
            weeks_candidates.append(str(weeks_str)) # 如 "第5周"
        if w_digits:
            try:
                weeks_candidates.append(int(w_digits)) # 如 整数 5
            except Exception:
                pass
            weeks_candidates.append(w_digits) # 如 "5"
        if user_week_num:
            weeks_candidates.append(f"第{user_week_num}周") # 如 "第15周"
            weeks_candidates.append(int(user_week_num)) # 如 整数 15

    last_res = None
    success = False

    for api_url in api_urls:
        if success:
            break
        endpoint_name = api_url.split("/")[-2] + "/" + api_url.split("/")[-1]

        # 如果是周报，按周次候选依次测试；如果是月报，直接一次测试
        trials = weeks_candidates if report_type == "week" else [None]
        for w_val in trials:
            # 基础 payload 框架
            payload = {
                "planId": plan_id,
                "jobId": job_id,
                "studentId": student_id,
                "type": report_type,
                "reportType": report_type,
                "title": title,
                "content": content,
                "address": address,
                "longitude": lng,
                "latitude": lat,
                "attachments": [],
            }

            if report_type == "week":
                if w_val is not None:
                    payload["weeks"] = w_val
                if start_time and end_time:
                    payload["startTime"] = start_time
                    payload["endTime"] = end_time
            elif report_type == "month":
                if yearmonth:
                    payload["yearmonth"] = yearmonth
                    payload["yearMonth"] = yearmonth
                if start_time and end_time:
                    payload["startTime"] = start_time
                    payload["endTime"] = end_time

            try:
                res = requests.post(api_url, json=payload, headers=headers, verify=False, timeout=12)
                res_json = res.json()
                last_res = res_json
                print(f"[REPORT_TRY] [{title}] -> {endpoint_name} (weeks={w_val}): status={res.status_code}, code={res_json.get('code')}, msg={res_json.get('msg')}", flush=True)

                if res_json.get("code") == 200:
                    print(f"[REPORT_SUBMIT_SUCCESS] 🎉 报告 [{title}] 提交成功！通道: {endpoint_name}", flush=True)
                    success = True
                    return res_json

                msg = str(res_json.get("msg", ""))
                if "已经" in msg or "已存在" in msg or "重复" in msg:
                    print(f"[REPORT_SUBMIT_INFO] 报告提示: {msg}", flush=True)
                    success = True
                    return res_json
                time.sleep(0.3)
            except Exception as e:
                last_res = {"code": 500, "msg": str(e)}

    return last_res or {"code": 500, "msg": "提交失败"}

def auto_manage_reports(user, token, user_id):
    """
    智能自动延续并补交周报与月报：
    1. 根据用户确认的历史锚点（周报填至 2026-10-25，月报填至 2026-09），按时间顺序精确补齐所有漏交报告；
    2. 对当前周（2026-11-23~2026-11-29）及当月（2026-11）完成准时提交。
    """
    results = []
    try:
        sign_info = create_sign(str(user_id) + "student")
        plan_id = get_plan_id(user, token, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习计划 planId: {plan_id}", flush=True)

        job_id, student_id, job_info = get_job_info(user, token, plan_id, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习岗位 jobId: {job_id}, studentId: {student_id}", flush=True)

        # 1. 查询系统全部开放的 18 周周次
        open_weeks_data = get_available_weeks(user, token, plan_id, sign_info)
        print(f"[REPORT_MANAGER] 系统开放周次总数: {len(open_weeks_data)} 周", flush=True)

        # 筛选待补齐周次：所有 startTime >= '2026-10-26'
        unsubmitted_weeks = []
        for w in open_weeks_data:
            w_start = w.get("startTime", "")
            if w_start and w_start >= "2026-10-26":
                unsubmitted_weeks.append(w)

        # 按时间从早到晚正向排序（10-26~11-01, 11-02~11-08, 11-09~11-15, 11-16~11-22, 11-23~11-29）
        unsubmitted_weeks.sort(key=lambda x: x.get("startTime", ""))
        print(f"[REPORT_MANAGER] 待补齐与提交的周报数量: {len(unsubmitted_weeks)} 篇", flush=True)

        # 用户之前填到了第14周，接下来从第15周开始
        user_week_index = 15
        for w in unsubmitted_weeks:
            w_str = w.get("weeks") or ""
            w_start = w.get("startTime", "")
            w_end = w.get("endTime", "")
            title = f"第{user_week_index}周实习周报"

            title_hint, content = generate_report_content(
                "week",
                title_hint=title,
                extra_context=f"实习第{user_week_index}周，周期{w_start[:10]}至{w_end[:10]}",
                user=user
            )

            print(f"[REPORT_MANAGER] 开始补交周报 [{title}]（系统周次: {w_str}, 日期: {w_start[:10]}~{w_end[:10]}）...", flush=True)
            sub_res = submit_single_report(
                user, token, plan_id, job_id, student_id, sign_info, "week",
                title=title, content=content,
                weeks_str=w_str, user_week_num=user_week_index,
                start_time=w_start, end_time=w_end
            )
            msg_res = sub_res.get("msg", "已处理")
            results.append(f"周报【{title}】({w_start[:10]}~{w_end[:10]}): {msg_res}")
            user_week_index += 1
            time.sleep(1.5)

        # 2. 补齐月报（用户填至 9 月，补交 10 月和 11 月）
        months_to_submit = [
            ("2026-10", "10月份实习月报总结", "2026-10-01 00:00:00", "2026-10-31 23:59:59"),
            ("2026-11", "11月份实习月报总结", "2026-11-01 00:00:00", "2026-11-30 23:59:59")
        ]

        for ym, m_title, m_start, m_end in months_to_submit:
            title, content = generate_report_content(
                "month",
                title_hint=m_title,
                extra_context=f"月份: {ym}",
                user=user
            )
            print(f"[REPORT_MANAGER] 开始补交月报 [{m_title}]（月份: {ym}）...", flush=True)
            m_res = submit_single_report(
                user, token, plan_id, job_id, student_id, sign_info, "month",
                title=m_title, content=content,
                yearmonth=ym, start_time=m_start, end_time=m_end
            )
            m_msg = m_res.get("msg", "已处理")
            results.append(f"月报【{m_title}】: {m_msg}")
            time.sleep(1.5)

    except Exception as e:
        print(f"[REPORT_MANAGER_ERROR] 自动管理周月报异常: {e}", flush=True)
        results.append(f"报告自动处理异常: {e}")

    summary_msg = "；".join(results) if results else "全部报告已处于最新状态。"
    print(f"[REPORT_MANAGER] 最终报告处理概况: {summary_msg}", flush=True)
    return {"status": "success", "message": summary_msg}
