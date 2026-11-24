import os
import requests

def clean_old_issues(keep_open_max=2):
    """
    自动清理与归档历史 GitHub Issue，保持仓库 Issues 列表整洁干净：
    1. 关闭所有超过当前保留范围的未关闭超时 Issue；
    2. 为历史已解决的 Issue 自动打上标签或关闭。
    """
    gh_token = os.getenv("GITHUB_TOKEN")
    gh_repo = os.getenv("GITHUB_REPOSITORY")
    if not gh_token or not gh_repo:
        return

    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "GongXueYun-Notifier"
    }

    try:
        # 获取仓库当前的 open issues
        url = f"https://api.github.com/repos/{gh_repo}/issues?state=open&per_page=30"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return

        open_issues = resp.json()
        # 排除 PR（若有）
        issues_list = [i for i in open_issues if "pull_request" not in i]

        # 如果未关闭的 Issue 数量大于保留值，自动将较早过期的打卡 Issue 关闭
        if len(issues_list) > keep_open_max:
            # 按创建时间降序排序，保留最新的 keep_open_max 个
            issues_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            to_close = issues_list[keep_open_max:]
            for iss in to_close:
                num = iss.get("number")
                title = iss.get("title", "")
                if "工学云" in title:
                    patch_url = f"https://api.github.com/repos/{gh_repo}/issues/{num}"
                    requests.patch(
                        patch_url,
                        headers=headers,
                        json={"state": "closed", "state_reason": "completed"},
                        timeout=10
                    )
                    print(f"[ISSUE_CLEANUP] 已自动关闭历史过期 Issue #{num}: {title}", flush=True)
    except Exception as e:
        print(f"[ISSUE_CLEANUP_WARN] 清理历史 Issue 异常: {e}", flush=True)
