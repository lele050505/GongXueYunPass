import requests
from modules.load_config import dprint
from datetime import datetime, timezone, timedelta

shanghai_tz = timezone(timedelta(hours=8))

def build_dashboard_html(title, content, sign_type="打卡", extra_stats=None):
    """
    构造美观、直观的每日打卡看板卡片 (HTML)
    包含：打卡状态、打卡时间、定位信息、周报状态与温馨提示
    """
    now_str = datetime.now(shanghai_tz).strftime("%Y-%m-%d %H:%M:%S")
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][datetime.now(shanghai_tz).weekday()]
    
    # 提取状态标签颜色
    is_success = "成功" in content or "通过" in content or "已打过" in content
    status_color = "#52c41a" if is_success else ("#faad14" if "验证" in content else "#f5222d")
    status_text = "打卡成功" if is_success else ("需要人脸核验" if "验证" in content else "打卡异常")

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;max-width:560px;margin:0 auto;border:1px solid #e8e8e8;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
      <div style="background:linear-gradient(135deg, #1677ff 0%, #36cfc9 100%);padding:18px 20px;color:#ffffff;">
        <h3 style="margin:0;font-size:18px;font-weight:600;">🎓 工学云考勤运行看板</h3>
        <p style="margin:4px 0 0;font-size:13px;opacity:0.9;">{now_str} ({weekday_cn})</p>
      </div>
      <div style="padding:20px;background:#ffffff;">
        <div style="display:flex;align-items:center;margin-bottom:16px;">
          <span style="display:inline-block;padding:4px 12px;border-radius:20px;font-size:13px;font-weight:600;color:#ffffff;background:{status_color};">
            {status_text}
          </span>
          <span style="margin-left:10px;font-size:14px;color:#555;font-weight:500;">
            类型: {sign_type}
          </span>
        </div>
        
        <div style="background:#f7f9fa;border-radius:8px;padding:12px 14px;margin-bottom:14px;font-size:13px;color:#444;line-height:1.6;">
          <div style="margin-bottom:6px;"><b>📋 详细回执：</b><br>{content.replace(chr(10), '<br>')}</div>
        </div>

        <div style="border-top:1px dashed #e8e8e8;padding-top:12px;font-size:12px;color:#8c8c8c;line-height:1.5;">
          <div>💡 <b>防风控智能保障：</b>已开启自动节假日免扰（周六正常打卡）、随机时间微颤与 GPS 拟真微漂。</div>
          <div>☁️ <b>运行托管：</b>GitHub Actions 纯云端免设备全自动执行。</div>
        </div>
      </div>
    </div>
    """
    return html

# 推送消息到PushPlus
def push_to_pushplus(users, title, content, token, sign_type="打卡"):
    if not token or not str(token).strip():
        return
    url = "https://www.pushplus.plus/send"
    try:
        # 如果 content 本身已经是带有结构的 HTML，则直接使用，否则包装为看板
        if not content.strip().startswith("<div") and not content.strip().startswith("<h3>"):
            content_html = build_dashboard_html(title, content, sign_type=sign_type)
        else:
            content_html = content

        resp = requests.post(url, json={
            "token": str(token).strip(),
            "title": title,
            "content": content_html,
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
