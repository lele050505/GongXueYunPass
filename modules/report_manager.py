# -*- coding: utf-8 -*-
import os
import re
import json
import time
import calendar
import requests
from datetime import datetime, timezone, timedelta
from modules.crypto_aes import create_sign, aes_encrypt
from modules.get_plan_id import get_plan_id
from modules.ai_report_generator import generate_report_content

shanghai_tz = timezone(timedelta(hours=8))
BASE_URL = "https://api.moguding.net:9000"

# 报告类型与表单模板 formType 的对应关系（日报: 7, 周报: 8, 月报: 9）
FORM_TYPE_MAP = {
    "day": 7,
    "week": 8,
    "month": 9,
}


def _build_headers(token, user_id, sign_val, device="Android"):
    """
    构造工学云/蘑菇丁标准请求头
    """
    return {
        "roleKey": "student",
        "rolekey": "student",
        "userid": str(user_id),
        "version": "v6.0",
        "appversion": "6.0.0",
        "device": device,
        "authorization": token,
        "sign": sign_val,
        "content-type": "application/json; charset=utf-8",
        "user-agent": "Dart/3.7 (dart:io)",
    }


def _fill_survey_first_option(form_fields):
    """
    为问卷题目列表中的所有题目默认选择第一个选项：
    优先取 optionEntity[0]['opt']，其次解析 optionJson[0]['opt']，兜底 'a'
    """
    if not form_fields or not isinstance(form_fields, list):
        return []

    filled = []
    for item in form_fields:
        if not isinstance(item, dict):
            continue
        new_item = dict(item)
        first_opt = None

        option_entity = new_item.get("optionEntity")
        if isinstance(option_entity, list) and len(option_entity) > 0:
            first_opt = option_entity[0].get("opt")

        if not first_opt and new_item.get("optionJson"):
            try:
                parsed = json.loads(new_item["optionJson"])
                if isinstance(parsed, list) and len(parsed) > 0:
                    first_opt = parsed[0].get("opt")
            except Exception:
                pass

        new_item["value"] = first_opt if first_opt else "a"
        filled.append(new_item)
    return filled


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
        t_now = aes_encrypt(str(int(time.time() * 1000)))
        res = requests.post(url, json={"planId": plan_id, "t": t_now}, headers=headers, verify=False, timeout=10)
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


def get_report_form_fields(token, user_id, form_type):
    """
    调用 /practice/paper/v2/info 拉取指定类型报告的问卷模板，并全部默认选中第一个选项
    """
    url = f"{BASE_URL}/practice/paper/v2/info"
    sign = create_sign(str(user_id), "student")
    headers = _build_headers(token, user_id, sign)
    try:
        t_now = aes_encrypt(str(int(time.time() * 1000)))
        res = requests.post(url, json={"formType": form_type, "t": t_now}, headers=headers, verify=False, timeout=10)
        res_json = res.json()
        if res_json.get("code") == 200:
            data = res_json.get("data") or {}
            raw_fields = data.get("formFieldDtoList") or []
            if not raw_fields:
                return []
            filled = _fill_survey_first_option(raw_fields)
            opts_summary = [f.get("value") for f in filled]
            print(f"[REPORT_SURVEY] 检测到问卷模板 (formType={form_type}) 共 {len(filled)} 题，已默认全选第一项: {opts_summary}", flush=True)
            return filled
        else:
            print(f"[REPORT_SURVEY_WARN] 拉取问卷模板 (formType={form_type}) 返回: code={res_json.get('code')}, msg={res_json.get('msg')}", flush=True)
    except Exception as e:
        print(f"[REPORT_SURVEY_WARN] 拉取问卷模板异常: {e}", flush=True)
    return []


def update_report_survey_if_missing(token, user_id, report_id, form_type=8):
    """
    检查已提交且未批阅的报告是否缺失问卷：
    若缺失且学校模板存在问卷，则调用 /practice/paper/v3/update 原位补填第一项；
    若平台不支持原位修改，保守保留原周报不做删除，仅返回 failed 提示手动补选。
    """
    info_url = f"{BASE_URL}/practice/paper/v2/info"
    sign_std = create_sign(str(user_id), "student")
    headers_std = _build_headers(token, user_id, sign_std)
    try:
        t_now = aes_encrypt(str(int(time.time() * 1000)))
        info_res = requests.post(
            info_url,
            json={"reportId": report_id, "formType": form_type, "t": t_now},
            headers=headers_std,
            verify=False,
            timeout=10,
        ).json()
        if info_res.get("code") != 200:
            return "failed", f"查询详情失败: {info_res.get('msg')}"

        detail = info_res.get("data") or {}
        template_fields = detail.get("formFieldDtoList") or []
        existing_fields = detail.get("fieldEntityList")

        # 模板无问卷，无需补填
        if not template_fields:
            return "no_survey", "无问卷模板"

        # 已有完整问卷答案，跳过
        if (
            isinstance(existing_fields, list)
            and len(existing_fields) >= len(template_fields)
            and all(item.get("value") for item in existing_fields)
        ):
            return "already_filled", "问卷已填写完整"

        # 老师已批阅（state != 0）时不允许修改
        if detail.get("state") not in (0, None):
            return "locked", "报告已批阅锁定"

        filled_fields = _fill_survey_first_option(template_fields)
        plan_id = detail.get("planId") or ""
        report_type = detail.get("reportType") or "week"
        title = detail.get("title") or ""

        payload = {
            "reportId": report_id,
            "planId": plan_id,
            "reportType": report_type,
            "title": title,
            "content": detail.get("content") or "",
            "weeks": detail.get("weeks"),
            "yearmonth": detail.get("yearmonth"),
            "startTime": detail.get("startTime"),
            "endTime": detail.get("endTime"),
            "jobId": detail.get("jobId") or "",
            "attachments": detail.get("attachments") or "",
            "address": detail.get("address"),
            "longitude": detail.get("longitude"),
            "latitude": detail.get("latitude"),
            "formFieldDtoList": filled_fields,
            "fieldEntityList": filled_fields,
            "isWarning": 0,
        }

        update_urls = [
            f"{BASE_URL}/practice/paper/v3/update",
            f"{BASE_URL}/practice/paper/v2/update",
        ]
        signs_to_try = [
            ("标准标题签名", create_sign(str(user_id), report_type, plan_id, title)),
            ("学生身份签名", sign_std),
        ]

        last_msg = "更新失败"
        for up_url in update_urls:
            ep_name = up_url.split("/")[-2] + "/" + up_url.split("/")[-1]
            for s_name, s_val in signs_to_try:
                payload["t"] = aes_encrypt(str(int(time.time() * 1000)))
                up_res = requests.post(
                    up_url,
                    json=payload,
                    headers=_build_headers(token, user_id, s_val),
                    verify=False,
                    timeout=10,
                ).json()
                code = up_res.get("code")
                msg = str(up_res.get("msg", ""))
                last_msg = msg
                print(f"[REPORT_SURVEY_UPDATE] [{title}] -> {ep_name} ({s_name}): code={code}, msg={msg}", flush=True)
                if code == 200:
                    return "updated", "问卷已原位补填(全选第一项)"
        return "failed", f"原位更新失败({last_msg})，请在APP手动补选"
    except Exception as e:
        return "failed", f"补填问卷异常: {e}"


def get_submitted_history(token, user_id, plan_id, report_type="week"):
    """
    调用 /practice/paper/v2/listByStu 分页查询用户已提交的全部历史周报/月报记录
    """
    url = f"{BASE_URL}/practice/paper/v2/listByStu"
    sign = create_sign(str(user_id), "student", report_type)
    headers = _build_headers(token, user_id, sign)

    all_rows = []
    curr_page = 1
    page_size = 50
    try:
        while curr_page <= 20:
            t_now = aes_encrypt(str(int(time.time() * 1000)))
            body = {
                "currPage": curr_page,
                "pageSize": page_size,
                "reportType": report_type,
                "planId": plan_id,
                "t": t_now,
            }
            res = requests.post(url, json=body, headers=headers, verify=False, timeout=10)
            res_json = res.json()
            if res_json.get("code") == 200:
                rows = res_json.get("data") or []
                if not isinstance(rows, list) or not rows:
                    break
                all_rows.extend(rows)
                if len(rows) < page_size:
                    break
                curr_page += 1
            else:
                print(f"[REPORT_HIST_INFO] 查询历史 {report_type} 返回: code={res_json.get('code')}, msg={res_json.get('msg')}", flush=True)
                break

        print(f"[REPORT_HIST] 成功查询到已提交的 {report_type} 历史记录共 {len(all_rows)} 篇", flush=True)
        for idx, item in enumerate(all_rows[:5]):
            t_str = (item.get("title") or "").strip()
            w_str = item.get("weeks") or ""
            ym_str = item.get("yearmonth") or ""
            c_time = item.get("createTime") or ""
            print(f"  - [{report_type}#{idx+1}] 标题: {t_str}, 周次: {w_str}, 月份: {ym_str}, 提交时间: {c_time}", flush=True)
    except Exception as e:
        print(f"[REPORT_HIST_WARN] 查询历史报告异常: {e}", flush=True)
    return all_rows


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
        t_now = aes_encrypt(str(int(time.time() * 1000)))
        body = {"planId": plan_id, "t": t_now}
        res = requests.post(url, json=body, headers=headers, verify=False, timeout=10)
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


def submit_single_report(
    user, token, user_id, plan_id, job_id, student_id,
    report_type, title, content,
    user_week_num=None, yearmonth=None, start_time=None, end_time=None,
    form_fields=None
):
    """
    向工学云提交单篇报告 (周报 / 月报)
    采用蘑菇丁 AES-128-ECB 加密时间戳 `t`、官方对称签名及自动问卷字段（默认全选第一项）
    """
    address = user.get("address", "")
    lat = str(user.get("latitude", "")) if user.get("latitude") is not None else ""
    lng = str(user.get("longitude", "")) if user.get("longitude") is not None else ""
    device = "Android"

    # 若未显式传入问卷字段，则按报告类型自动拉取并默认选中第一项
    if form_fields is None:
        ft = FORM_TYPE_MAP.get(report_type)
        form_fields = get_report_form_fields(token, user_id, ft) if ft else []

    target_week_str = f"第{user_week_num}周" if user_week_num else ""
    w_digits = str(user_week_num) if user_week_num else ""

    # 生成内容三段式（content, summary, plan），覆盖高校端必填项
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    part_summary = paragraphs[1] if len(paragraphs) > 1 else "本阶段工作扎实推进，理论与实践紧密结合，严格遵守各项实习操作规范。"
    part_plan = paragraphs[2] if len(paragraphs) > 2 else "下阶段将继续向带教老师虚心请教，加深业务实操技能，进一步提高工作质量。"

    # 准备签名方案（优先官方标准标题签名）
    signs_to_try = [
        ("标准标题签名", create_sign(str(user_id), report_type, plan_id, title)),
        ("通用报告签名", create_sign(str(user_id), report_type, plan_id, "报告")),
        ("学生身份签名", create_sign(str(user_id), "student")),
        ("时空动作签名", create_sign(device, report_type, plan_id, str(user_id), address)),
    ]

    # 保存接口: 优先使用支持完整问卷的 v6/save，备用 v5/save 与 v2/save
    api_urls = [
        f"{BASE_URL}/practice/paper/v6/save",
        f"{BASE_URL}/practice/paper/v5/save",
        f"{BASE_URL}/practice/paper/v2/save",
    ]

    payload_variants = []

    if report_type == "week":
        p1 = {
            "userId": user_id,
            "planId": plan_id,
            "reportType": "week",
            "title": title,
            "content": content,
            "summary": part_summary,
            "plan": part_plan,
            "weeks": target_week_str,
            "week": target_week_str,
            "startTime": start_time,
            "endTime": end_time,
            "address": address,
            "longitude": lng,
            "latitude": lat,
            "attachment": "",
            "attachments": "",
            "formFieldDtoList": form_fields,
            "fieldEntityList": form_fields,
            "isWarning": 0,
        }
        if job_id:
            p1["jobId"] = job_id
        if student_id:
            p1["studentId"] = student_id
        payload_variants.append((f"延续周次完整体({target_week_str})", p1))

        p2 = p1.copy()
        p2["weeks"] = w_digits
        p2["week"] = w_digits
        payload_variants.append((f"延续周次纯数字({w_digits})", p2))

        p3 = {
            "userId": user_id,
            "planId": plan_id,
            "reportType": "week",
            "title": title,
            "content": content,
            "weeks": target_week_str,
            "jobId": job_id if job_id else "",
            "startTime": start_time,
            "endTime": end_time,
            "attachments": "",
            "formFieldDtoList": form_fields,
            "fieldEntityList": form_fields,
            "isWarning": 0,
        }
        payload_variants.append(("官方精简体", p3))

    else:
        m1 = {
            "userId": user_id,
            "planId": plan_id,
            "reportType": "month",
            "title": title,
            "content": content,
            "summary": part_summary,
            "plan": part_plan,
            "yearmonth": yearmonth,
            "yearMonth": yearmonth,
            "startTime": start_time,
            "endTime": end_time,
            "address": address,
            "longitude": lng,
            "latitude": lat,
            "attachment": "",
            "attachments": "",
            "formFieldDtoList": form_fields,
            "fieldEntityList": form_fields,
            "isWarning": 0,
        }
        if job_id:
            m1["jobId"] = job_id
        if student_id:
            m1["studentId"] = student_id
        payload_variants.append(("月报完整体", m1))

        m2 = {
            "userId": user_id,
            "planId": plan_id,
            "reportType": "month",
            "title": title,
            "content": content,
            "yearmonth": yearmonth,
            "jobId": job_id if job_id else "",
            "startTime": start_time,
            "endTime": end_time,
            "attachments": "",
            "formFieldDtoList": form_fields,
            "fieldEntityList": form_fields,
            "isWarning": 0,
        }
        payload_variants.append(("月报精简体", m2))

    last_res = None

    for api_url in api_urls:
        endpoint_name = api_url.split("/")[-2] + "/" + api_url.split("/")[-1]
        for p_name, p_data in payload_variants:
            p_data["t"] = aes_encrypt(str(int(time.time() * 1000)))

            for s_name, current_sign in signs_to_try:
                headers = _build_headers(token, user_id, current_sign, device=device)
                try:
                    res = requests.post(api_url, json=p_data, headers=headers, verify=False, timeout=8)
                    res_json = res.json()
                    last_res = res_json

                    code = res_json.get("code")
                    msg = str(res_json.get("msg", ""))
                    print(f"[REPORT_TRY] [{title}] -> {endpoint_name} [{p_name}] ({s_name}): status={res.status_code}, code={code}, msg={msg}", flush=True)

                    if code == 200:
                        print(f"[REPORT_SUBMIT_SUCCESS] 🎉 报告 [{title}] 提交成功！通道: {endpoint_name}, 变体: {p_name}, 签名: {s_name}", flush=True)
                        return res_json

                    if "已经" in msg or "已存在" in msg or "重复" in msg:
                        print(f"[REPORT_SUBMIT_INFO] 报告提示已存在: {msg}", flush=True)
                        return res_json
                except Exception as e:
                    last_res = {"code": 500, "msg": str(e)}

    return last_res or {"code": 500, "msg": "提交失败"}


def _extract_week_number(weeks_str):
    """从 '第19周' 或 '19' 中提取周序号整数"""
    if not weeks_str:
        return 0
    m = re.search(r"(\d+)", str(weeks_str))
    return int(m.group(1)) if m else 0


def _generate_month_range(start_ym, end_ym):
    """生成从 start_ym 到 end_ym（含）的所有 YYYY-MM 列表"""
    sy, sm = map(int, start_ym.split("-"))
    ey, em = map(int, end_ym.split("-"))
    months = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def auto_manage_reports(user, token, user_id):
    """
    智能自动延续并补交周报与月报：
    1. 拉取云端真实历史周报/月报记录进行精准去重，杜绝重复提交；
    2. 自动检测未批阅周报中缺失问卷的记录，尝试通过 v3/update 原位补选第一项（不删除原周报）；
    3. 对未提交的开放周次及月份，自动拉取最新问卷模板（全选第一项）并延续序号准时提交。
    """
    results = []
    try:
        sign_info = create_sign(str(user_id), "student")
        plan_id = get_plan_id(user, token, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习计划 planId: {plan_id}", flush=True)

        job_id, student_id, job_info = get_job_info(user, token, plan_id, sign_info)
        print(f"[REPORT_MANAGER] 获取到实习岗位 jobId: {job_id}, studentId: {student_id}", flush=True)

        # 0. 拉取云端全部历史周报与月报，用于精准去重与序号延续
        print(f"[REPORT_MANAGER] 正在拉取用户云端历史周报与月报记录...", flush=True)
        hist_weeks = get_submitted_history(token, user_id, plan_id, "week")
        hist_months = get_submitted_history(token, user_id, plan_id, "month")

        submitted_week_starts = set()
        max_week_num = 14
        for item in hist_weeks:
            st = (item.get("startTime") or "")[:10]
            if st:
                submitted_week_starts.add(st)
            wn = _extract_week_number(item.get("weeks"))
            if wn > max_week_num:
                max_week_num = wn

        submitted_months = set()
        for item in hist_months:
            ym = (item.get("yearmonth") or "").strip()
            if ym:
                submitted_months.add(ym)

        print(f"[REPORT_MANAGER] 历史去重基线: 已交周报 {len(submitted_week_starts)} 篇 (最大序号: 第{max_week_num}周), 已交月报 {sorted(submitted_months)}", flush=True)

        # 1. 自动检查近期未批阅周报（startTime >= 2026-10-26 且 state == 0）是否缺失问卷并原位补填
        for item in hist_weeks:
            st = (item.get("startTime") or "")[:10]
            rid = item.get("reportId")
            w_label = item.get("weeks") or item.get("title") or rid
            if st >= "2026-10-26" and rid and item.get("state") in (0, None):
                status, msg = update_report_survey_if_missing(token, user_id, rid, form_type=8)
                if status == "updated":
                    results.append(f"周报【{w_label}】问卷补填: {msg}")
                    time.sleep(0.5)
                elif status == "failed":
                    results.append(f"周报【{w_label}】问卷待手动补选: {msg}")

        # 2. 查询系统全部开放的周次，仅提交尚未入库的新周次
        open_weeks_data = get_available_weeks(user, token, plan_id, sign_info)
        print(f"[REPORT_MANAGER] 系统开放周次总数: {len(open_weeks_data)} 周", flush=True)

        unsubmitted_weeks = []
        for w in open_weeks_data:
            w_start = w.get("startTime", "")
            w_start_date = w_start[:10]
            if w_start_date and w_start_date >= "2026-10-26" and w_start_date not in submitted_week_starts:
                unsubmitted_weeks.append(w)

        unsubmitted_weeks.sort(key=lambda x: x.get("startTime", ""))
        print(f"[REPORT_MANAGER] 待新提交的周报数量: {len(unsubmitted_weeks)} 篇", flush=True)

        if unsubmitted_weeks:
            week_form_fields = get_report_form_fields(token, user_id, FORM_TYPE_MAP["week"])
            user_week_index = max_week_num + 1
            for w in unsubmitted_weeks:
                w_str = w.get("weeks") or ""
                w_start = w.get("startTime", "")
                w_end = w.get("endTime", "")
                title = f"第{user_week_index}周实习周报"

                _, content = generate_report_content(
                    "week",
                    title_hint=title,
                    extra_context=f"实习第{user_week_index}周，周期{w_start[:10]}至{w_end[:10]}",
                    user=user
                )

                print(f"\n[REPORT_MANAGER] >>> 开始提交新周报 [{title}]（系统周次: {w_str}, 日期: {w_start[:10]}~{w_end[:10]}）...", flush=True)
                sub_res = submit_single_report(
                    user, token, user_id, plan_id, job_id, student_id, "week",
                    title=title, content=content,
                    user_week_num=user_week_index,
                    start_time=w_start, end_time=w_end,
                    form_fields=week_form_fields,
                )
                msg_res = sub_res.get("msg", "已处理")
                results.append(f"周报【{title}】({w_start[:10]}~{w_end[:10]}): {msg_res}")
                user_week_index += 1
                time.sleep(1)

        # 3. 动态补齐/延续月报（从 2026-10 至当前年月，自动跳过已提交月份）
        current_ym = datetime.now(shanghai_tz).strftime("%Y-%m")
        all_target_months = _generate_month_range("2026-10", current_ym) if current_ym >= "2026-10" else []
        unsubmitted_months = [ym for ym in all_target_months if ym not in submitted_months]
        print(f"[REPORT_MANAGER] 待新提交的月报数量: {len(unsubmitted_months)} 篇 ({unsubmitted_months})", flush=True)

        if unsubmitted_months:
            month_form_fields = get_report_form_fields(token, user_id, FORM_TYPE_MAP["month"])
            for ym in unsubmitted_months:
                y_val, m_val = map(int, ym.split("-"))
                last_day = calendar.monthrange(y_val, m_val)[1]
                m_start = f"{ym}-01 00:00:00"
                m_end = f"{ym}-{last_day:02d} 23:59:59"
                m_title = f"{m_val}月份实习月报总结"

                _, content = generate_report_content(
                    "month",
                    title_hint=m_title,
                    extra_context=f"月份: {ym}",
                    user=user
                )
                print(f"\n[REPORT_MANAGER] >>> 开始提交新月报 [{m_title}]（月份: {ym}）...", flush=True)
                m_res = submit_single_report(
                    user, token, user_id, plan_id, job_id, student_id, "month",
                    title=m_title, content=content,
                    yearmonth=ym, start_time=m_start, end_time=m_end,
                    form_fields=month_form_fields,
                )
                m_msg = m_res.get("msg", "已处理")
                results.append(f"月报【{m_title}】: {m_msg}")
                time.sleep(1)

    except Exception as e:
        print(f"[REPORT_MANAGER_ERROR] 自动管理周月报异常: {e}", flush=True)
        results.append(f"报告自动处理异常: {e}")

    summary_msg = "；".join(results) if results else "全部周报/月报及问卷均已处于最新完整状态。"
    print(f"\n[REPORT_MANAGER] ==========================================", flush=True)
    print(f"[REPORT_MANAGER] 最终报告处理概况: {summary_msg}", flush=True)
    print(f"[REPORT_MANAGER] ==========================================", flush=True)
    return {"status": "success", "message": summary_msg}
