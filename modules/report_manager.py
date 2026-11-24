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
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": header_user_agent(user),
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

def get_submitted_reports(user, token, plan_id, job_id, sign_info, report_type="week"):
    """
    获取学生在当前实习计划下已提交的报告列表，自适应支持 currPage 分页与多个候选端点
    """
    headers = {
        "roleKey": "student",
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": header_user_agent(user),
    }
    type_param = "week" if report_type == "week" else "month"
    num_type = "2" if report_type == "week" else "3"

    url_candidates = [
        f"{BASE_URL}/practice/paper/v2/listByStu",
        f"{BASE_URL}/practice/paper/v1/listByStu",
    ]

    payload_candidates = [
        # 针对工学云后端的分页规范：currPage
        {"planId": plan_id, "reportType": type_param, "currPage": 1, "pageSize": 50},
        {"planId": plan_id, "jobId": job_id, "reportType": type_param, "currPage": 1, "pageSize": 50} if job_id else None,
        {"planId": plan_id, "reportType": num_type, "currPage": 1, "pageSize": 50},
        {"planId": plan_id, "reportType": type_param, "page": 1, "pageSize": 50},
    ]
    payload_candidates = [p for p in payload_candidates if p is not None]

    for api_url in url_candidates:
        for p in payload_candidates:
            try:
                res = requests.post(api_url, json=p, headers=headers, verify=False, timeout=10)
                res_json = res.json()
                if res_json.get("code") == 200:
                    data = res_json.get("data")
                    print(f"[REPORT_DEBUG] listByStu 成功响应 ({api_url})！", flush=True)
                    if isinstance(data, list):
                        return data
                    elif isinstance(data, dict):
                        for k in ["list", "rows", "records", "data", "papers"]:
                            if isinstance(data.get(k), list):
                                return data[k]
                        if "totalCount" in data and not data.get("list"):
                            return []
            except Exception:
                continue

    print(f"[REPORT_QUERY_WARN] 查询历史已提交报告未返回列表，默认作为 0 篇继续处理", flush=True)
    return []

def get_available_weeks(user, token, plan_id, sign_info):
    """
    获取当前实习计划的所有开放周次列表
    """
    url = f"{BASE_URL}/practice/paper/v3/getWeeks1"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": header_user_agent(user),
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

def submit_single_report(user, token, user_id, plan_id, job_id, student_id, sign_info, report_type, title, content, weeks_str=None, yearmonth=None, start_time=None, end_time=None):
    """
    向工学云提交单篇报告 (周报 / 月报)，自适应探测版本与参数组合
    """
    headers = {
        "roleKey": "student",
        "authorization": token,
        "sign": sign_info,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": header_user_agent(user),
    }

    address = user.get("address", "")
    lat = str(user.get("latitude", "")) if user.get("latitude") is not None else ""
    lng = str(user.get("longitude", "")) if user.get("longitude") is not None else ""

    norm_week = str(weeks_str) if weeks_str is not None else ""
    week_alt = ""
    if norm_week:
        if norm_week.isdigit():
            week_alt = f"第{norm_week}周"
        elif norm_week.startswith("第") and ("周" in norm_week):
            week_alt = norm_week.replace("第", "").replace("周", "").strip()

    num_type = "2" if report_type == "week" else "3"

    # 尝试不同端点版本：v1, v2, v5
    api_urls = [
        f"{BASE_URL}/practice/paper/v1/save",
        f"{BASE_URL}/practice/paper/v2/save",
        f"{BASE_URL}/practice/paper/v5/save"
    ]

    # 构造多种参数组合
    def make_body(r_type, w_val, with_stu_id=False, att_val="omit", with_form_field=False):
        b = {
            "planId": plan_id,
            "reportType": r_type,
            "title": title,
            "content": content,
            "address": address,
            "longitude": lng,
            "latitude": lat,
        }
        if job_id:
            b["jobId"] = job_id
        if with_stu_id and student_id:
            b["studentId"] = student_id

        if r_type in ["week", "2", 2]:
            if w_val:
                b["weeks"] = str(w_val)
            if start_time and end_time:
                b["startTime"] = start_time
                b["endTime"] = end_time
        elif r_type in ["month", "3", 3]:
            if yearmonth:
                b["yearmonth"] = yearmonth
                b["yearMonth"] = yearmonth
            if start_time and end_time:
                b["startTime"] = start_time
                b["endTime"] = end_time

        if att_val == "array":
            b["attachments"] = []
        elif att_val == "str_array":
            b["attachments"] = "[]"
        elif att_val == "empty_str":
            b["attachments"] = ""

        if with_form_field:
            b["formFieldDtoList"] = []

        return b

    payload_variants = [
        # 变体 1：极简纯净版（无多余扩展键，最符合 v1/v2 标准）
        make_body(report_type, norm_week, with_stu_id=False, att_val="omit", with_form_field=False),
        # 变体 2：带 studentId 纯净版
        make_body(report_type, norm_week, with_stu_id=True, att_val="omit", with_form_field=False),
        # 变体 3：数字 reportType ("2"/"3")
        make_body(num_type, norm_week, with_stu_id=False, att_val="omit", with_form_field=False),
        # 变体 4：周次纯数字/第X周转换
        make_body(report_type, week_alt, with_stu_id=False, att_val="omit", with_form_field=False) if week_alt else None,
        # 变体 5：带空列表 attachments
        make_body(report_type, norm_week, with_stu_id=False, att_val="array", with_form_field=False),
        # 变体 6：带字符串 "[]" attachments
        make_body(report_type, norm_week, with_stu_id=False, att_val="str_array", with_form_field=False),
    ]
    payload_variants = [p for p in payload_variants if p is not None]

    last_res = None
    step_count = 0
    for api_url in api_urls:
        for payload in payload_variants:
            step_count += 1
            try:
                res = requests.post(api_url, json=payload, headers=headers, verify=False, timeout=12)
                res_json = res.json()
                last_res = res_json
                print(f"[REPORT_TRY_{step_count}] [{title}] -> {api_url.split('/')[-2]}/{api_url.split('/')[-1]}: status={res.status_code}, code={res_json.get('code')}, msg={res_json.get('msg')}", flush=True)
                
                if res_json.get("code") == 200:
                    print(f"[REPORT_SUBMIT_SUCCESS] 🎉 报告 [{title}] 提交成功！通道: {api_url}", flush=True)
                    return res_json

                msg = str(res_json.get("msg", ""))
                if "已经" in msg or "已存在" in msg or "重复" in msg:
                    print(f"[REPORT_SUBMIT_INFO] 报告提示: {msg}", flush=True)
                    return res_json
                time.sleep(0.5)
            except Exception as e:
                last_res = {"code": 500, "msg": str(e)}

    return last_res or {"code": 500, "msg": "提交失败"}

def auto_manage_reports(user, token, user_id):
    """
    自动检查历史周报/月报：
    1. 查询已提交报告，避免重复提交；
    2. 延续历史序号，自动补齐此前漏交的周报；
    3. 若本周周报尚未提交，则通过 AI 生成高质量内容并提交；
    4. 若本月月报尚未提交，则补齐提交。
    """
    results = []
    try:
        sign_info = create_sign(str(user_id) + "student")
        plan_id = get_plan_id(user, token, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习计划 planId: {plan_id}", flush=True)

        job_id, student_id, job_info = get_job_info(user, token, plan_id, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习岗位 jobId: {job_id}, studentId: {student_id}", flush=True)

        # 1. 查询已提交的周报记录
        submitted_weeks_data = get_submitted_reports(user, token, plan_id, job_id, sign_info, report_type="week")
        submitted_weeks = []
        for r in submitted_weeks_data:
            w = r.get("weeks") or r.get("week")
            if w:
                submitted_weeks.append(str(w))
            t = r.get("title", "")
            if "第" in t and "周" in t:
                try:
                    w_sub = t.split("第")[1].split("周")[0]
                    if w_sub:
                        submitted_weeks.append(w_sub)
                        submitted_weeks.append(f"第{w_sub}周")
                except Exception:
                    pass
        print(f"[REPORT_MANAGER] 已提交周报数量: {len(submitted_weeks_data)} 篇，已提交周次: {list(set(submitted_weeks))}", flush=True)

        # 2. 查询系统支持的所有开放周次
        open_weeks_data = get_available_weeks(user, token, plan_id, sign_info)

        if open_weeks_data:
            print(f"[REPORT_MANAGER] 系统开放周次数量: {len(open_weeks_data)} 周", flush=True)
            for w in open_weeks_data:
                w_str = str(w.get("weeks") or w.get("week") or "")
                w_start = w.get("startTime")
                w_end = w.get("endTime")
                if not w_str:
                    continue

                is_done = False
                for sw in submitted_weeks:
                    if w_str == sw or (w_str in sw) or (sw in w_str):
                        is_done = True
                        break

                if not is_done:
                    title_hint = f"第{w_str}周实习周报" if not w_str.startswith("第") else f"{w_str}实习周报"
                    title, content = generate_report_content("week", title_hint=title_hint, extra_context=f"第{w_str}周, 日期{w_start}~{w_end}", user=user)
                    print(f"[REPORT_MANAGER] 发现未提交周报，开始自动提交: {title}", flush=True)
                    submit_res = submit_single_report(
                        user, token, user_id, plan_id, job_id, student_id, sign_info, "week",
                        title=title, content=content,
                        weeks_str=w_str, start_time=w_start, end_time=w_end
                    )
                    results.append(f"周报【{title}】提交: {submit_res.get('msg', '成功')}")
                    time.sleep(2)
        else:
            # 兜底：若开放周次接口未返回，根据已提交数量延续推算下一周
            next_week_num = len(submitted_weeks_data) + 1
            today_weekday = datetime.now(shanghai_tz).weekday()
            # 若周末(五/六/日)或此前从未提交过任何周报，则提交下一篇
            if today_weekday in [4, 5, 6] or len(submitted_weeks_data) == 0:
                title_hint = f"第{next_week_num}周实习周报"
                title, content = generate_report_content("week", title_hint=title_hint, extra_context=f"第{next_week_num}周", user=user)
                print(f"[REPORT_MANAGER] 推算提交本周周报: {title}", flush=True)
                submit_res = submit_single_report(
                    user, token, user_id, plan_id, job_id, student_id, sign_info, "week",
                    title=title, content=content,
                    weeks_str=f"第{next_week_num}周"
                )
                results.append(f"周报【{title}】提交: {submit_res.get('msg', '成功')}")

        # 3. 检查月报
        now_dt = datetime.now(shanghai_tz)
        current_yearmonth = now_dt.strftime("%Y-%m")
        submitted_months = get_submitted_reports(user, token, plan_id, job_id, sign_info, report_type="month")
        month_done = any(current_yearmonth in (str(m.get("yearmonth", "")) or str(m.get("yearMonth", "")) or str(m.get("title", ""))) for m in submitted_months)
        print(f"[REPORT_MANAGER] 已提交月报数量: {len(submitted_months)} 篇，当月({current_yearmonth})是否已交: {month_done}", flush=True)

        if not month_done and now_dt.day >= 20:
            title_hint = f"{now_dt.month}月份实习月报总结"
            title, content = generate_report_content("month", title_hint=title_hint, extra_context=f"月份:{current_yearmonth}", user=user)
            print(f"[REPORT_MANAGER] 准备提交当月月报: {title}", flush=True)
            submit_res = submit_single_report(
                user, token, user_id, plan_id, job_id, student_id, sign_info, "month",
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
