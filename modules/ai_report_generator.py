import os
import json
import random
import requests

# 预设高质量、生活化、每周各不相同的实习周报模板库（当没有配置 AI API Key 时智能轮换，拒绝重复死板模板）
FALLBACK_WEEKLY_TOPICS = [
    (
        "熟悉工作环境与业务操作规范",
        "本周主要熟悉了所在岗位的日常业务操作规范与工作流程。在带教老师的悉心指导下，认真阅读了各项规章制度，并初步参与了日常任务的梳理与录入工作。"
        "通过实际操作，我掌握了常用工具系统的使用规范，对业务运转链条有了整体认识。在遇到疑难问题时，虚心向同事请教，逐步理清了工作逻辑。"
        "下一步我将继续夯实业务基础，加快任务处理效率，主动分担力所能及的辅助性事务，争取在下一阶段的工作中更加得心应手。"
    ),
    (
        "业务实操演练与工作流程优化",
        "本周进入了更加密集的业务实操阶段。在老师的带领下，我独立完成了几项常规事务性工作的推进，并在操作中注意总结记录易错细节。"
        "在实际跟进过程中，我发现部分交接环节可以通过提前整理台账来提升流转效率，经过与带教老师沟通后做出了小范围调整，得到了老师的肯定。"
        "通过本周的锻炼，我的执行力和细致度有了明显提高。下周计划继续加强跨岗位沟通，进一步提高数据处理与汇报总结的准确性。"
    ),
    (
        "专项问题排查与跨部门协同沟通",
        "本周的工作重点在于日常事务跟进以及部分突发小问题的协助排查。在团队配合中，我更加深刻地体会到了团队协作与信息同步的重要性。"
        "面对突发的协调需求，我冷静梳理优先级，按时完成了老师交办的各项数据核对与材料归档工作，保证了所属环节的稳妥无误。"
        "这周的实践让我明白了不仅要做好手头的工作，更要培养预判问题的意识。下周我将做好阶段性总结，温故知新，持续完善业务知识框架。"
    ),
    (
        "阶段性工作复盘与技能总结提高",
        "转眼已来到实习的中期阶段，本周主要对前几周积累的工作成果进行了系统性复盘。在带教老师的指导下，我整理了业务操作要点与常见问题手册。"
        "通过对比最初的生疏，现在我已经能够沉着应对各类标准工作流程，处理事务的敏捷度与规范性均有长足进步。"
        "带教老师对我的学习态度给予了积极评价，同时也指出了在深度理解业务背景上还可以进一步钻研。下周我将带着这些思考，积极投身新的实践任务中。"
    ),
    (
        "综合实践应用与工作效率进阶",
        "本周主要参与了多项综合性日常业务的执行工作。在保障准确率的前提下，我尝试优化自己的工作节奏，效率较以往有了进一步提升。"
        "期间协助整理了重要的台账信息，配合团队完成了周期性总结工作，对岗位所承担的实际价值有了更立体的体会。"
        "下周我将保持良好的精神状态，紧密配合团队进度，继续主动学习新技能，力求保质保量完成各项既定目标。"
    ),
    (
        "查漏补缺与深化专业业务认知",
        "本周在常规业务处理之余，重点对平时容易忽略的操作细节进行了查漏补缺。结合学校所学的专业知识与企业一线实际需求进行了对照印证。"
        "在老师的指导下，我更加明确了从理论转化为实际生产力的关键节点，工作作风更加严谨求实。"
        "下阶段我将继续巩固已有成果，主动承担更具挑战性的任务，以饱满的热情迎接后续的实习工作。"
    )
]

FALLBACK_MONTHLY_TOPICS = [
    (
        "月度实习总结与综合成长心得",
        "在过去的一个月中，在单位领导与带教老师的关怀指导下，我逐步完成了从校园学习到职场实践的适应与转变。"
        "本月度内，我不仅系统掌握了岗位的核心业务流程，按时按质完成了日常事务的跟进与记录，更在沟通协同、时间管理和解决突发问题的能力上获得了扎实的提升。"
        "工作中我始终保持严谨细致、虚心求学的态度，积极融入团队氛围。展望下个月，我将以更高的标准要求自己，深入钻研业务核心技能，为团队做出更多实质性贡献。"
    ),
    (
        "深化实操与综合能力跃升月度汇报",
        "本月的实习工作进入了深水区与全面提升阶段。在带教老师的信任与支持下，我参与了多项重要节点任务的协助推进工作。"
        "相较于上个月，我的独立操作能力和抗压意识有了质的飞跃，面对复杂琐碎的信息能够条分缕析、高效落地。"
        "通过这一个月的磨砺，我对行业现状和岗位职责有了更深刻的敬畏与理解。接下来的时间里，我将继续脚踏实地、查漏补缺，争取交出一份圆满的实习答卷。"
    )
]

def generate_report_content(report_type="week", title_hint="", extra_context="", user=None):
    """
    智能生成高质量报告内容：
    优先尝试 Gemini API / DeepSeek API（若配置了 GEMINI_API_KEY 或 DEEPSEEK_API_KEY），
    若无配置则自动从高质量、生活化的轮换知识库中抽取并自动延续，拒绝机械化重复。
    """
    company_name = (user.get("address") if user else "") or "实习单位"
    user_desc = (user.get("desc") if user else "") or "日常业务实践"

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("AI_API_KEY")
    if gemini_key:
        try:
            prompt = (
                f"你是一名在【{company_name}】认真参与【{user_desc}】的大学生实习生。\n"
                f"请帮我撰写一篇真实的工学云【{'周报' if report_type == 'week' else '月报'}】。\n"
                f"要求：\n"
                f"1. 标题简练，如'{title_hint or '实习总结'}'\n"
                f"2. 正文字数在 200~300 字左右，分 2~3 段，语言诚恳自然、积极向上，体现学习过程、工作心得和下一步计划；\n"
                f"3. 绝对不要包含 markdown 标记、不要出现'作为一个AI'、不要出现占位符，纯中文正文。\n"
                f"补充上下文信息: {extra_context}\n"
                f"请输出 JSON 格式: {{\"title\": \"标题\", \"content\": \"正文\"}}"
            )
            api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            res = requests.post(
                api_url,
                json={"contents": [{"parts": [{"text": prompt}]}]},
                headers={"Content-Type": "application/json"},
                timeout=12
            )
            if res.status_code == 200:
                text_out = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                if "```json" in text_out:
                    text_out = text_out.split("```json")[1].split("```")[0].strip()
                elif "```" in text_out:
                    text_out = text_out.split("```")[1].split("```")[0].strip()
                data = json.loads(text_out)
                if data.get("title") and data.get("content"):
                    return data["title"], data["content"]
        except Exception as e:
            print(f"[AI_REPORT_WARN] 调用 Gemini API 失败: {e}，启用内置优质文库...", flush=True)

    # 兜底使用内置高质量主题库
    if report_type == "week":
        item = random.choice(FALLBACK_WEEKLY_TOPICS)
        title = title_hint if title_hint else item[0]
        return title, item[1]
    else:
        item = random.choice(FALLBACK_MONTHLY_TOPICS)
        title = title_hint if title_hint else item[0]
        return title, item[1]
