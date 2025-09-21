import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
# 引入新的认证模块和异常类型
from github import Github, Auth, UnknownObjectException

# --- 配置 ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = os.getenv("GITHUB_REPOSITORY_OWNER")
ARCHIVE_DIR = "archive"
README_FILE = "README.md"

if not all([GITHUB_TOKEN, GITHUB_USERNAME]):
    raise ValueError("环境变量 GITHUB_TOKEN 和 GITHUB_REPOSITORY_OWNER 未设置")

def format_event(event):
    """将 GitHub 事件格式化为友好的 Markdown 列表项，并附带仓库描述。"""
    try:
        actor_login = event.actor.login
        actor_url = event.actor.html_url
        repo_name = event.repo.name
        repo_url = f"https://github.com/{repo_name}"
        
        # 尝试获取仓库描述，如果仓库不存在或不可访问，则优雅地处理
        try:
            description = event.repo.description
        except UnknownObjectException:
            print(f"  警告: 仓库 {repo_name} 无法访问 (可能已被删除或设为私有)，跳过描述。")
            description = None

        line = ""
        # 我们只关心部分有意义的事件类型
        if event.type == 'WatchEvent':
            line = f"- 🌟 👤 [{actor_login}]({actor_url}) Starred [{repo_name}]({repo_url})"
        elif event.type == 'ForkEvent':
            forked_to = event.payload['forkee']['full_name']
            line = f"- 🍴 👤 [{actor_login}]({actor_url}) Forked [{repo_name}]({repo_url}) to [{forked_to}](https://github.com/{forked_to})"
        elif event.type == 'CreateEvent' and event.payload.get('ref_type') == 'repository':
            line = f"- ✨ 👤 [{actor_login}]({actor_url}) Created new repo [{repo_name}]({repo_url})"
        elif event.type == 'PublicEvent':
            line = f"- 🚀 👤 [{actor_login}]({actor_url}) Made [{repo_name}]({repo_url}) public"
        
        # 如果事件行成功生成，并且有描述，则附加描述
        if line and description:
            # 截断过长的描述
            max_desc_len = 100
            if len(description) > max_desc_len:
                description = description[:max_desc_len] + '...'
            # 使用 Markdown blockquote 格式化描述，并添加换行和缩进
            line += f"\n  > {description.replace(chr(10), ' ').replace(chr(13), ' ')}"

        return line

    except Exception as e:
        # 捕获其他可能的格式化错误
        print(f"  格式化事件时发生未知错误: {e}")
        return None

def archive_if_yesterday(yesterday_str):
    """如果 README 是昨天的内容，则归档"""
    readme_path = Path(README_FILE)
    if not readme_path.exists():
        return

    content = readme_path.read_text(encoding="utf-8")
    match = re.search(r"\((\d{4}-\d{2}-\d{2})\)", content.splitlines()[0])
    
    if match and match.group(1) == yesterday_str:
        archive_path = Path(ARCHIVE_DIR) / f"{yesterday_str}.md"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(content, encoding="utf-8")
        print(f"成功归档 {yesterday_str} 的报告到 {archive_path}")
    else:
        print("README 无需归档。")

def get_all_events_for_today(g, today_date_utc):
    """获取今天从 00:00 UTC 到现在的所有动态"""
    user = g.get_user(GITHUB_USERNAME)
    events = user.get_received_events()
    
    todays_events = []
    print(f"正在获取 {today_date_utc.strftime('%Y-%m-%d')} 的全部动态...")
    
    for event in events:
        event_date = event.created_at.date()
        if event_date < today_date_utc:
            break
        if event_date == today_date_utc:
            todays_events.append(event)
            
    return todays_events

def generate_markdown_for_events(events):
    """根据事件列表生成 Markdown 内容"""
    if not events:
        return "今天还没有新的公开动态。\n"
        
    events_by_user = {}
    for event in events:
        line = format_event(event)
        if line:
            actor_login = event.actor.login
            if actor_login not in events_by_user:
                events_by_user[actor_login] = []
            if line not in events_by_user[actor_login]:
                events_by_user[actor_login].append(line)
    
    if not events_by_user:
        return "今天还没有符合筛选条件的公开动态。\n"
    
    content = ""
    for username, activities in sorted(events_by_user.items()):
        content += f"### [{username}](https://github.com/{username})\n"
        content += "\n".join(reversed(activities))
        content += "\n\n"
        
    return content

def main():
    """主函数"""
    # 使用新的 Auth 方式初始化
    auth = Auth.Token(GITHUB_TOKEN)
    g = Github(auth=auth)
    
    today_utc = datetime.now(timezone.utc)
    yesterday_utc = today_utc - timedelta(days=1)
    
    today_str = today_utc.strftime('%Y-%m-%d')
    yesterday_str = yesterday_utc.strftime('%Y-%m-%d')

    archive_if_yesterday(yesterday_str)
    
    todays_events = get_all_events_for_today(g, today_utc.date())
    
    todays_events_md = generate_markdown_for_events(todays_events)
    
    readme_content = f"# 每日 GitHub 动态 ({today_str})\n\n"
    readme_content += "我关注用户的今日公开动态 (每15分钟更新)。\n\n"
    readme_content += "## 今日动态\n\n"
    readme_content += todays_events_md
    readme_content += "\n---\n"
    readme_content += f"*最后更新于 {today_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC*\n"
    readme_content += "*历史记录保存在 `archive` 目录中。*\n"
    
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(readme_content)
        
    print(f"成功刷新 {README_FILE}，包含 {len(todays_events)} 条事件。")

if __name__ == "__main__":
    main()
