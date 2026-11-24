import os
import json
import time
import requests
from datetime import datetime, timezone, timedelta
from modules.crypto_aes import create_sign, aes_encrypt
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
        if res_json.get("code") == 200:
            data = res_json.get("data")
            if isinstance(data, dict):
                job_id = data.get("jobId") or data.get("id")
                student_id = data.get("studentId")
                return job_id, student_id, data
            elif isinstance(data, list) and len(data) > 0:
                item = data[0]
                job_id = item.get("jobId") or item.get("id")
                student_id = item.get("studentId")
                return job_id, student_id, item
    except Exception as e:
        print(f"[REPORT_JOB_WARN] 获取岗位信息异常: {e}", flush=True)
    return None, None, {}

def get_submitted_history(token, user_id, plan_id):
    """
    查询用户此前已提交的历史周报与月报结构，打印并探测真实字段规范
    """
    sign_info = create_sign(str(user_id) + "student")
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
    endpoints = [
        f"{BASE_URL}/practice/paper/v2/listByStu",
        f"{BASE_URL}/practice/paper/v1/listByStu",
        f"{BASE_URL}/practice/paper/v3/listByStu"
    ]
    for ep in endpoints:
        for r_type in ["week", "month", "2", "3"]:
            try:
                res = requests.post(ep, json={"userId": user_id, "planId": plan_id, "reportType": r_type, "currPage": 1, "pageSize": 5}, headers=headers, verify=False, timeout=8)
                rj = res.json()
                print(f"[REPORT_HIST_PROBE] {ep} ({r_type}): code={rj.get('code')}, msg={rj.get('msg')}", flush=True)
                if rj.get("code") == 200:
                    d = rj.get("data")
                    print(f"[REPORT_HIST_DATA] 样例数据: {json.dumps(d, ensure_ascii=False)[:500]}", flush=True)
                    return d
            except Exception as e:
                pass
    return None

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

def submit_single_report(user, token, user_id, plan_id, job_id, student_id, report_type, title, content, week_obj=None, user_week_num=None, yearmonth=None, start_time=None, end_time=None):
    """
    向工学云提交单篇报告 (周报 / 月报)，含自适应版本回退与严格请求体矩阵探测
    """
    address = user.get("address", "")
    province = user.get("province", "")
    city = user.get("city", "")
    lat = str(user.get("latitude", "")) if user.get("latitude") is not None else ""
    lng = str(user.get("longitude", "")) if user.get("longitude") is not None else ""
    device = "Android"

    # 提取周次相关元数据
    weeks_str = ""
    w_digits = ""
    week_id = ""
    if week_obj:
        if isinstance(week_obj, dict):
            weeks_str = week_obj.get("weeks") or week_obj.get("week") or ""
            week_id = week_obj.get("id") or week_obj.get("weekId") or ""
        else:
            weeks_str = str(week_obj)
        for ch in str(weeks_str):
            if ch.isdigit():
                w_digits += ch
    if not w_digits and user_week_num:
        w_digits = str(user_week_num)

    # 生成内容三段式（content, summary, plan），覆盖高校端必填项
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    part_content = paragraphs[0] if len(paragraphs) > 0 else content
    part_summary = paragraphs[1] if len(paragraphs) > 1 else "本周工作扎实推进，理论与实践结合紧密，基本达到了预期实习目标。"
    part_plan = paragraphs[2] if len(paragraphs) > 2 else "下阶段将继续向带教老师虚心请教，加深业务实操技能，提高整体工作效率。"

    # 签名方案
    sign_std = create_sign(str(user_id) + "student")
    sign_act = create_sign(device + report_type + plan_id + str(user_id) + address)
    signs_to_try = [sign_std, sign_act]

    # 优先使用真实响应的 v2/save 与 v5/save
    api_urls = [
        f"{BASE_URL}/practice/paper/v2/save",
        f"{BASE_URL}/practice/paper/v5/save",
    ]

    num_type = "2" if report_type == "week" else "3"

    payload_variants = []

    if report_type == "week":
        # 变体 1: 标准三段式 (含 summary, plan, weeks="第5周", week="第5周", userId)
        p1 = {
            "userId": user_id,
            "planId": plan_id,
            "title": title,
            "content": content,
            "summary": part_summary,
            "plan": part_plan,
            "reportType": "week",
            "weeks": weeks_str or f"第{w_digits}周",
            "week": weeks_str or f"第{w_digits}周",
            "startTime": start_time,
            "endTime": end_time,
            "address": address,
            "longitude": lng,
            "latitude": lat,
        }
        if job_id:
            p1["jobId"] = job_id
        if student_id:
            p1["studentId"] = student_id
        if week_id:
            p1["weekId"] = week_id
            p1["id"] = week_id
        payload_variants.append(("三段式完整体(字符周次)", p1))

        # 变体 2: 纯数字周次三段式 (weeks=数字, week=数字)
        p2 = p1.copy()
        p2["weeks"] = w_digits
        p2["week"] = w_digits
        payload_variants.append(("三段式完整体(数字周次)", p2))

        # 变体 3: 数字类型 reportType=2
        p3 = p1.copy()
        p3["reportType"] = "2"
        payload_variants.append(("三段式数字类型(reportType=2)", p3))

        # 变体 4: 极简双字段 (content + summary + plan)
        p4 = {
            "userId": user_id,
            "planId": plan_id,
            "title": title,
            "content": content,
            "summary": part_summary,
            "plan": part_plan,
            "reportType": "week",
            "weeks": weeks_str or f"第{w_digits}周",
        }
        payload_variants.append(("精简三段式", p4))

    else:
        # 月报变体
        m1 = {
            "userId": user_id,
            "planId": plan_id,
            "title": title,
            "content": content,
            "summary": part_summary,
            "plan": part_plan,
            "reportType": "month",
            "yearmonth": yearmonth,
            "yearMonth": yearmonth,
            "startTime": start_time,
            "endTime": end_time,
            "address": address,
            "longitude": lng,
            "latitude": lat,
        }
        if job_id:
            m1["jobId"] = job_id
        if student_id:
            m1["studentId"] = student_id
        payload_variants.append(("月报三段式(reportType=month)", m1))

        m2 = m1.copy()
        m2["reportType"] = "3"
        payload_variants.append(("月报三段式(reportType=3)", m2))

        m3 = {
            "userId": user_id,
            "planId": plan_id,
            "title": title,
            "content": content,
            "summary": part_summary,
            "plan": part_plan,
            "reportType": "month",
            "yearmonth": yearmonth,
            "yearMonth": yearmonth,
        }
        payload_variants.append(("月报精简三段式", m3))

    last_res = None

    for api_url in api_urls:
        endpoint_name = api_url.split("/")[-2] + "/" + api_url.split("/")[-1]
        for p_name, p_data in payload_variants:
            for s_idx, current_sign in enumerate(signs_to_try):
                headers = {
                    "roleKey": "student",
                    "version": "v6.0",
                    "appversion": "6.0.0",
                    "device": device,
                    "authorization": token,
                    "sign": current_sign,
                    "content-type": "application/json; charset=utf-8",
                    "user-agent": "Dart/3.7 (dart:io)",
                }

                try:
                    res = requests.post(api_url, json=p_data, headers=headers, verify=False, timeout=8)
                    res_json = res.json()
                    last_res = res_json

                    code = res_json.get("code")
                    msg = str(res_json.get("msg", ""))
                    print(f"[REPORT_TRY] [{title}] -> {endpoint_name} [{p_name}] (签名{s_idx+1}): status={res.status_code}, code={code}, msg={msg}", flush=True)

                    if code == 200:
                        print(f"[REPORT_SUBMIT_SUCCESS] 🎉 报告 [{title}] 提交成功！通道: {endpoint_name}, 变体: {p_name}", flush=True)
                        return res_json

                    if "已经" in msg or "已存在" in msg or "重复" in msg:
                        print(f"[REPORT_SUBMIT_INFO] 报告提示: {msg}", flush=True)
                        return res_json
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

        # 0. 尝试查询历史已提交报告作为参考
        get_submitted_history(token, user_id, plan_id)

        # 1. 查询系统全部开放的周次
        open_weeks_data = get_available_weeks(user, token, plan_id, sign_info)
        print(f"[REPORT_MANAGER] 系统开放周次总数: {len(open_weeks_data)} 周", flush=True)

        # 筛选待补齐周次：所有 startTime >= '2026-10-26'
        unsubmitted_weeks = []
        for w in open_weeks_data:
            w_start = w.get("startTime", "")
            if w_start and w_start >= "2026-10-26":
                unsubmitted_weeks.append(w)

        # 按时间正向排序（10-26~11-01, 11-02~11-08, 11-09~11-15, 11-16~11-22, 11-23~11-29）
        unsubmitted_weeks.sort(key=lambda x: x.get("startTime", ""))
        print(f"[REPORT_MANAGER] 待补齐与提交的周报数量: {len(unsubmitted_weeks)} 篇", flush=True)

        # 用户此前填至第14周，接下来从第15周开始延续
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
            print(f"[REPORT_WEEK_RAW] 原始周次元数据: {json.dumps(w, ensure_ascii=False)}", flush=True)
            sub_res = submit_single_report(
                user, token, user_id, plan_id, job_id, student_id, "week",
                title=title, content=content,
                week_obj=w, user_week_num=user_week_index,
                start_time=w_start, end_time=w_end
            )
            msg_res = sub_res.get("msg", "已处理")
            results.append(f"周报【{title}】({w_start[:10]}~{w_end[:10]}): {msg_res}")
            user_week_index += 1
            time.sleep(1)

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
                user, token, user_id, plan_id, job_id, student_id, "month",
                title=m_title, content=content,
                yearmonth=ym, start_time=m_start, end_time=m_end
            )
            m_msg = m_res.get("msg", "已处理")
            results.append(f"月报【{m_title}】: {m_msg}")
            time.sleep(1)

    except Exception as e:
        print(f"[REPORT_MANAGER_ERROR] 自动管理周月报异常: {e}", flush=True)
        results.append(f"报告自动处理异常: {e}")

    summary_msg = "；".join(results) if results else "全部报告已处于最新状态。"
    print(f"[REPORT_MANAGER] 最终报告处理概况: {summary_msg}", flush=True)
    return {"status": "success", "message": summary_msg}
