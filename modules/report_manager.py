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

def get_job_info(token, plan_id):
    """
    获取学生在当前实习计划下的岗位详情，提取 jobId
    """
    url = f"{BASE_URL}/practice/job/v4/infoByStu"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "content-type": "application/json; charset=UTF-8"
    }
    try:
        res = requests.post(url, json={"planId": plan_id}, headers=headers, verify=False, timeout=10)
        print(f"[REPORT_DEBUG] infoByStu 响应: status={res.status_code}, body={res.text[:300]}", flush=True)
        res_json = res.json()
        if res_json.get("code") == 200 and isinstance(res_json.get("data"), dict):
            data = res_json["data"]
            job_id = data.get("jobId") or data.get("id")
            return job_id, data
    except Exception as e:
        print(f"[REPORT_JOB_WARN] 获取岗位信息异常: {e}", flush=True)
    return None, {}

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
    type_param = "week" if report_type == "week" else "month"
    payload = {
        "planId": plan_id,
        "reportType": type_param,
        "page": 1,
        "pageSize": 100
    }
    try:
        res = requests.post(url, json=payload, headers=headers, verify=False, timeout=10)
        print(f"[REPORT_DEBUG] listByStu ({report_type}) 响应: status={res.status_code}, body={res.text[:300]}", flush=True)
        res_json = res.json()
        if res_json.get("code") == 200:
            data = res_json.get("data")
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                for k in ["list", "rows", "records", "data", "papers"]:
                    if isinstance(data.get(k), list):
                        return data[k]
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
        print(f"[REPORT_DEBUG] getWeeks1 响应: status={res.status_code}, body={res.text[:300]}", flush=True)
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

def submit_single_report(user, token, plan_id, job_id, report_type, title, content, weeks_str=None, yearmonth=None, start_time=None, end_time=None):
    """
    向工学云提交单篇报告 (周报 / 月报)，含自适应参数修复与多变体容错
    """
    url = f"{BASE_URL}/practice/paper/v5/save"
    headers = {
        "roleKey": "student",
        "authorization": token,
        "content-type": "application/json; charset=UTF-8",
        "user-agent": header_user_agent(user),
    }

    address = user.get("address", "")
    lat = str(user.get("latitude", "")) if user.get("latitude") is not None else ""
    lng = str(user.get("longitude", "")) if user.get("longitude") is not None else ""

    def build_payload(r_type, w_val, att_val):
        p = {
            "planId": plan_id,
            "reportType": r_type,
            "title": title,
            "content": content,
            "address": address,
            "longitude": lng,
            "latitude": lat,
            "formFieldDtoList": []
        }
        if att_val is not None:
            p["attachments"] = att_val
        if job_id:
            p["jobId"] = job_id

        if r_type in ["week", "2", 2]:
            if w_val:
                p["weeks"] = str(w_val)
            if start_time and end_time:
                p["startTime"] = start_time
                p["endTime"] = end_time
        elif r_type in ["month", "3", 3]:
            if yearmonth:
                p["yearmonth"] = yearmonth
                p["yearMonth"] = yearmonth
            if start_time and end_time:
                p["startTime"] = start_time
                p["endTime"] = end_time
        return p

    candidates = []
    norm_week = str(weeks_str) if weeks_str is not None else ""
    week_alt = ""
    if norm_week:
        if norm_week.isdigit():
            week_alt = f"第{norm_week}周"
        elif norm_week.startswith("第") and ("周" in norm_week):
            week_alt = norm_week.replace("第", "").replace("周", "").strip()

    # 主方案：标准 reportType + 空数组 attachments
    candidates.append(build_payload(report_type, norm_week, []))
    # 备选 A：周次格式互换 (如 "1" <-> "第1周")
    if week_alt:
        candidates.append(build_payload(report_type, week_alt, []))
    # 备选 B：数字 reportType ("2" / "3")
    num_type = "2" if report_type == "week" else "3"
    candidates.append(build_payload(num_type, norm_week or week_alt, []))
    # 备选 C：不带 attachments 键
    candidates.append(build_payload(report_type, norm_week, None))

    last_res = None
    for idx, payload in enumerate(candidates):
        try:
            print(f"[REPORT_SUBMIT_ATTEMPT_{idx+1}] 尝试提交 [{title}]，payload: {json.dumps(payload, ensure_ascii=False)}", flush=True)
            res = requests.post(url, json=payload, headers=headers, verify=False, timeout=15)
            print(f"[REPORT_SUBMIT_RESP_{idx+1}] 响应: status={res.status_code}, body={res.text}", flush=True)
            res_json = res.json()
            last_res = res_json
            if res_json.get("code") == 200:
                print(f"[REPORT_SUBMIT_SUCCESS] 报告 [{title}] 提交成功！", flush=True)
                return res_json
            msg = res_json.get("msg", "")
            if "已经" in msg or "已存在" in msg or "重复" in msg:
                print(f"[REPORT_SUBMIT_INFO] 提示: {msg}", flush=True)
                return res_json
            time.sleep(1)
        except Exception as e:
            print(f"[REPORT_SUBMIT_ERROR_{idx+1}] 提交异常: {e}", flush=True)
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

        job_id, job_info = get_job_info(token, plan_id)
        print(f"[REPORT_MANAGER] 获取到实习岗位 jobId: {job_id}", flush=True)

        # 1. 查询已提交的周报记录
        submitted_weeks_data = get_submitted_reports(token, plan_id, report_type="week")
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
        open_weeks_data = get_available_weeks(token, plan_id)

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
                        user, token, plan_id, job_id, "week",
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
                    user, token, plan_id, job_id, "week",
                    title=title, content=content,
                    weeks_str=f"第{next_week_num}周"
                )
                results.append(f"周报【{title}】提交: {submit_res.get('msg', '成功')}")

        # 3. 检查月报
        now_dt = datetime.now(shanghai_tz)
        current_yearmonth = now_dt.strftime("%Y-%m")
        submitted_months = get_submitted_reports(token, plan_id, report_type="month")
        month_done = any(current_yearmonth in (str(m.get("yearmonth", "")) or str(m.get("yearMonth", "")) or str(m.get("title", ""))) for m in submitted_months)
        print(f"[REPORT_MANAGER] 已提交月报数量: {len(submitted_months)} 篇，当月({current_yearmonth})是否已交: {month_done}", flush=True)

        if not month_done and now_dt.day >= 20:
            title_hint = f"{now_dt.month}月份实习月报总结"
            title, content = generate_report_content("month", title_hint=title_hint, extra_context=f"月份:{current_yearmonth}", user=user)
            print(f"[REPORT_MANAGER] 准备提交当月月报: {title}", flush=True)
            submit_res = submit_single_report(
                user, token, plan_id, job_id, "month",
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
