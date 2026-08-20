# main.py
import argparse
import json
from urllib.parse import urlparse

from src.core.executor import Executor
from src.domains.action_type import ActionType
from src.domains.platform import Platform
from src.domains.task import Task
from src.models.account import Account

def load_accounts(file_path: str = "accounts.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Account(**item) for item in data]


def platform_from_url(target_url: str) -> Platform:
    host = urlparse(target_url).netloc.lower().removeprefix("www.")
    if host == "instagram.com":
        return Platform.INSTAGRAM
    if host in {"x.com", "twitter.com", "mobile.twitter.com"}:
        return Platform.TWITTER
    if host in {"facebook.com", "m.facebook.com"}:
        return Platform.FACEBOOK
    raise ValueError(f"Unsupported social-media URL: {target_url}")


def build_tasks(
    target_url: str,
    action: ActionType | str = ActionType.LIKE,
    accounts_path: str = "accounts.json",
    comment: str | None = None,
):
    params = {"comment_text": comment} if comment else {}
    target_platform = platform_from_url(target_url)
    return [
        Task(
            account=account,
            platform=Platform.parse(account.platform),
            action=ActionType.parse(action),
            target_url=target_url,
            params=params.copy(),
        )
        for account in load_accounts(accounts_path)
        if Platform.parse(account.platform) is target_platform
    ]


def parse_args():
    parser = argparse.ArgumentParser(description="Run social-media engagement tasks")
    parser.add_argument("target_url", help="Instagram or X post URL")
    parser.add_argument("--accounts", default="accounts.json")
    parser.add_argument(
        "--action",
        choices=("like", "comment", "reply", "repost", "retweet"),
        default="like",
    )
    parser.add_argument("--comment", help="Text used for comment/reply actions")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    tasks = build_tasks(args.target_url, args.action, args.accounts, args.comment)
    if not tasks:
        print("No tasks to process. Check accounts.json.")
    else:
        Executor(tasks).run()
