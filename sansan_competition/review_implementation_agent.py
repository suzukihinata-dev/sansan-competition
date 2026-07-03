from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import dedent
from typing import Any, Sequence

ACTIONABLE_REVIEW_STATES = {"COMMENTED", "CHANGES_REQUESTED"}
DEFAULT_STATE_DIR_NAME = ".review-implementation-agent"
DEFAULT_PROMPTS_DIR_NAME = "prompts"
DEFAULT_MERGED_PR_LIMIT = 20


@dataclass(frozen=True, slots=True)
class ReviewInlineComment:
    body: str
    path: str
    line: int | None = None
    side: str | None = None


@dataclass(frozen=True, slots=True)
class PullRequestContext:
    repo_full_name: str
    pr_number: int
    title: str
    url: str
    head_ref: str
    base_ref: str


@dataclass(frozen=True, slots=True)
class ReviewEvent:
    review_id: int
    state: str
    author: str
    submitted_at: str
    body: str
    comments: tuple[ReviewInlineComment, ...]
    pull_request: PullRequestContext


@dataclass(frozen=True, slots=True)
class MergedPullRequestEvent:
    number: int
    title: str
    url: str
    author: str
    body: str
    merged_at: str
    head_ref: str
    base_ref: str


def run_command(args: Sequence[str], *, repo_root: Path) -> tuple[int, str]:
    completed = subprocess.run(
        list(args),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout.strip()
    if completed.stderr.strip():
        if output:
            output = f"{output}\n{completed.stderr.strip()}"
        else:
            output = completed.stderr.strip()
    return completed.returncode, output


def run_gh_json(args: Sequence[str], *, repo_root: Path) -> Any:
    returncode, output = run_command(["gh", *args], repo_root=repo_root)
    if returncode != 0:
        raise RuntimeError(output or f"gh command failed: {' '.join(args)}")
    return json.loads(output)


def resolve_pull_request_context(
    repo_root: Path,
    *,
    pr_number: int | None = None,
) -> PullRequestContext:
    pr_args = ["pr", "view", "--json", "number,title,url,headRefName,baseRefName"]
    if pr_number is not None:
        pr_args.insert(2, str(pr_number))
    pr_info = run_gh_json(pr_args, repo_root=repo_root)
    repo_info = run_gh_json(["repo", "view", "--json", "nameWithOwner"], repo_root=repo_root)
    return PullRequestContext(
        repo_full_name=repo_info["nameWithOwner"],
        pr_number=pr_info["number"],
        title=pr_info["title"],
        url=pr_info["url"],
        head_ref=pr_info["headRefName"],
        base_ref=pr_info["baseRefName"],
    )


def resolve_default_branch(repo_root: Path) -> str:
    repo_info = run_gh_json(
        ["repo", "view", "--json", "defaultBranchRef"],
        repo_root=repo_root,
    )
    return repo_info["defaultBranchRef"]["name"]


def fetch_reviews(repo_root: Path, pr: PullRequestContext) -> list[ReviewEvent]:
    reviews_payload = run_gh_json(
        ["api", f"repos/{pr.repo_full_name}/pulls/{pr.pr_number}/reviews"],
        repo_root=repo_root,
    )
    reviews: list[ReviewEvent] = []
    for review_payload in reviews_payload:
        review_id = int(review_payload["id"])
        comments_payload = run_gh_json(
            [
                "api",
                f"repos/{pr.repo_full_name}/pulls/{pr.pr_number}/reviews/{review_id}/comments",
            ],
            repo_root=repo_root,
        )
        comments = tuple(
            ReviewInlineComment(
                body=(comment.get("body") or "").strip(),
                path=comment.get("path") or "",
                line=comment.get("line"),
                side=comment.get("side"),
            )
            for comment in comments_payload
            if (comment.get("body") or "").strip()
        )
        user = review_payload.get("user") or {}
        reviews.append(
            ReviewEvent(
                review_id=review_id,
                state=(review_payload.get("state") or "").upper(),
                author=user.get("login") or "unknown",
                submitted_at=review_payload.get("submitted_at") or "",
                body=(review_payload.get("body") or "").strip(),
                comments=comments,
                pull_request=pr,
            )
        )
    return sorted(reviews, key=lambda item: (item.submitted_at, item.review_id))


def fetch_merged_pull_requests(
    repo_root: Path,
    *,
    base_branch: str | None = None,
    limit: int = DEFAULT_MERGED_PR_LIMIT,
) -> list[MergedPullRequestEvent]:
    pulls_payload = run_gh_json(
        [
            "pr",
            "list",
            "--state",
            "merged",
            "--limit",
            str(limit),
            "--json",
            "number,title,url,author,body,mergedAt,headRefName,baseRefName",
        ],
        repo_root=repo_root,
    )
    merged_prs: list[MergedPullRequestEvent] = []
    for pull_payload in pulls_payload:
        if base_branch and pull_payload.get("baseRefName") != base_branch:
            continue
        author = pull_payload.get("author") or {}
        merged_prs.append(
            MergedPullRequestEvent(
                number=int(pull_payload["number"]),
                title=pull_payload.get("title") or "",
                url=pull_payload.get("url") or "",
                author=author.get("login") or "unknown",
                body=(pull_payload.get("body") or "").strip(),
                merged_at=pull_payload.get("mergedAt") or "",
                head_ref=pull_payload.get("headRefName") or "",
                base_ref=pull_payload.get("baseRefName") or "",
            )
        )
    return sorted(merged_prs, key=lambda item: (item.merged_at, item.number))


def is_actionable_review(review: ReviewEvent) -> bool:
    if review.state not in ACTIONABLE_REVIEW_STATES:
        return False
    if review.body.strip():
        return True
    return any(comment.body.strip() for comment in review.comments)


def build_review_prompt(review: ReviewEvent) -> str:
    lines = [
        "You are the implementation agent for this repository.",
        "Apply the review feedback below to the checked-out branch with minimal, correct changes.",
        "",
        "Requirements:",
        "- Inspect the actual repository state before editing.",
        "- Implement every actionable requested change from the review.",
        "- If a comment is unclear, infer the narrowest safe fix instead of broad refactors.",
        "- Run the smallest relevant validation after editing.",
        "- Leave unrelated local changes untouched.",
        "",
        "Pull request context:",
        f"- Repository: {review.pull_request.repo_full_name}",
        f"- PR: #{review.pull_request.pr_number} {review.pull_request.title}",
        f"- URL: {review.pull_request.url}",
        f"- Branch: {review.pull_request.head_ref} -> {review.pull_request.base_ref}",
        "",
        "Review trigger:",
        f"- Review ID: {review.review_id}",
        f"- Reviewer: {review.author}",
        f"- State: {review.state}",
        f"- Submitted at: {review.submitted_at or 'unknown'}",
    ]
    if review.body:
        lines.extend(["", "Top-level review body:", review.body])
    if review.comments:
        lines.extend(["", "Inline review comments:"])
        for comment in review.comments:
            location = comment.path
            if comment.line is not None:
                location = f"{location}:{comment.line}"
            if comment.side:
                location = f"{location} ({comment.side})"
            lines.append(f"- {location}")
            lines.append(f"  {comment.body}")
    lines.extend(
        [
            "",
            "Deliverable:",
            "- Make the code changes now.",
            "- Summarize what changed and what validation you ran.",
        ]
    )
    return "\n".join(lines)


def build_prompt(review: ReviewEvent) -> str:
    return build_review_prompt(review)


def build_merged_progress_prompt(
    merged_pr: MergedPullRequestEvent,
    *,
    role_name: str,
    role_definition: str,
) -> str:
    return dedent(
        f"""
        You are the implementation architect for the `{role_name}` scope in this repository.
        A pull request has just been merged. First absorb what landed, then continue implementation within your own assigned scope.

        Requirements:
        - Inspect the actual repository state after the merge before changing anything.
        - Use `ROLE.md` as the source of truth for your ownership boundaries.
        - Stay inside the `{role_name}` scope. Do not take over another owner's responsibilities unless the role document explicitly overlaps.
        - Identify the highest-value next step that became unblocked or clearer because of this merged PR.
        - Prefer a small, concrete implementation step over a broad speculative refactor.
        - Run the smallest relevant validation after editing.
        - Leave unrelated local changes untouched.

        Merged pull request:
        - PR: #{merged_pr.number} {merged_pr.title}
        - URL: {merged_pr.url}
        - Author: {merged_pr.author}
        - Branch: {merged_pr.head_ref} -> {merged_pr.base_ref}
        - Merged at: {merged_pr.merged_at or 'unknown'}

        Merged PR body:
        {merged_pr.body or '(no body)'}

        Role definition excerpt:
        {role_definition}

        Deliverable:
        - Explain briefly what changed in the merged PR that matters for `{role_name}`.
        - Choose the next concrete task inside the `{role_name}` ownership boundary.
        - Implement that task now.
        - Summarize what changed and what validation you ran.
        """
    ).strip()


def load_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {"processed_review_ids": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(state_path: Path, state: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def select_pending_reviews(
    reviews: Sequence[ReviewEvent],
    processed_review_ids: set[int],
) -> list[ReviewEvent]:
    return [
        review
        for review in reviews
        if review.review_id not in processed_review_ids and is_actionable_review(review)
    ]


def select_pending_merged_pull_requests(
    merged_prs: Sequence[MergedPullRequestEvent],
    processed_pull_numbers: set[int],
) -> list[MergedPullRequestEvent]:
    return [
        merged_pr
        for merged_pr in merged_prs
        if merged_pr.number not in processed_pull_numbers and merged_pr.merged_at
    ]


def format_agent_command(command_text: str, repo_root: Path) -> list[str]:
    rendered = command_text.format(repo_root=str(repo_root))
    return shlex.split(rendered)


def default_agent_command(repo_root: Path) -> list[str]:
    return [
        "codex",
        "exec",
        "--cd",
        str(repo_root),
        "--sandbox",
        "workspace-write",
        "--ask-for-approval",
        "never",
    ]


def run_agent_for_review(
    review: ReviewEvent,
    *,
    repo_root: Path,
    command: Sequence[str],
    prompt: str,
) -> int:
    completed = subprocess.run(
        [*command, prompt],
        cwd=repo_root,
        text=True,
        check=False,
    )
    return completed.returncode


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="review-implementation-agent")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument(
        "--mode",
        choices=("review", "merged-progress", "all"),
        default="all",
    )
    parser.add_argument("--base-branch", default="")
    parser.add_argument("--role-name", default=os.environ.get("REVIEW_IMPLEMENT_ROLE_NAME", "hinata"))
    parser.add_argument("--role-file", default="ROLE.md")
    parser.add_argument("--merged-pr-limit", type=int, default=DEFAULT_MERGED_PR_LIMIT)
    parser.add_argument("--state-path", default="")
    parser.add_argument("--prompts-dir", default="")
    parser.add_argument("--agent-command", default="")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def load_role_definition(role_file: Path, *, role_name: str) -> str:
    text = role_file.read_text(encoding="utf-8")
    if role_name:
        sections = text.split("\n### ")
        for index, section in enumerate(sections):
            block = section if index == 0 else f"### {section}"
            if f" {role_name} " in block:
                return block.strip()
    return text.strip()


def resolve_agent_command(args: argparse.Namespace, repo_root: Path) -> list[str]:
    if args.agent_command:
        return format_agent_command(args.agent_command, repo_root)
    if command_text := os.environ.get("REVIEW_IMPLEMENT_AGENT_COMMAND"):
        return format_agent_command(command_text, repo_root)
    return default_agent_command(repo_root)


def process_reviews(
    *,
    repo_root: Path,
    state: dict[str, Any],
    prompts_dir: Path,
    command: Sequence[str],
    pr_number: int | None,
    dry_run: bool,
) -> tuple[int, int]:
    try:
        pull_request = resolve_pull_request_context(repo_root, pr_number=pr_number)
    except RuntimeError as exc:
        print(f"skipping review mode: {exc}")
        return 0, 0
    reviews = fetch_reviews(repo_root, pull_request)
    processed_review_ids = {int(value) for value in state.get("processed_review_ids", [])}
    pending_reviews = select_pending_reviews(reviews, processed_review_ids)
    if not pending_reviews:
        print("no new actionable reviews")
        return 0, 0

    updated_processed = set(processed_review_ids)
    for review in pending_reviews:
        prompt = build_review_prompt(review)
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompts_dir / f"review-{review.review_id}.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if dry_run:
            print(f"detected actionable review {review.review_id} from {review.author}")
            print(f"prompt written to {prompt_path}")
            continue

        exit_code = run_agent_for_review(
            review,
            repo_root=repo_root,
            command=command,
            prompt=prompt,
        )
        if exit_code != 0:
            print(f"agent command failed for review {review.review_id}", file=sys.stderr)
            return exit_code, 0
        updated_processed.add(review.review_id)

    state["processed_review_ids"] = sorted(updated_processed)
    return 0, len(pending_reviews)


def process_merged_pull_requests(
    *,
    repo_root: Path,
    state: dict[str, Any],
    prompts_dir: Path,
    command: Sequence[str],
    base_branch: str,
    role_name: str,
    role_file: Path,
    merged_pr_limit: int,
    dry_run: bool,
) -> tuple[int, int]:
    role_definition = load_role_definition(role_file, role_name=role_name)
    target_base_branch = base_branch or resolve_default_branch(repo_root)
    merged_prs = fetch_merged_pull_requests(
        repo_root,
        base_branch=target_base_branch,
        limit=merged_pr_limit,
    )
    processed_pull_numbers = {
        int(value) for value in state.get("processed_merged_pull_request_numbers", [])
    }
    pending_merged_prs = select_pending_merged_pull_requests(merged_prs, processed_pull_numbers)
    if not pending_merged_prs:
        print("no new merged pull requests for scope progression")
        return 0, 0

    updated_processed = set(processed_pull_numbers)
    for merged_pr in pending_merged_prs:
        prompt = build_merged_progress_prompt(
            merged_pr,
            role_name=role_name,
            role_definition=role_definition,
        )
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompts_dir / f"merged-pr-{merged_pr.number}.md"
        prompt_path.write_text(prompt, encoding="utf-8")

        if dry_run:
            print(f"detected merged pull request #{merged_pr.number} for {role_name}")
            print(f"prompt written to {prompt_path}")
            continue

        completed = subprocess.run([*command, prompt], cwd=repo_root, text=True, check=False)
        if completed.returncode != 0:
            print(
                f"agent command failed for merged pull request {merged_pr.number}",
                file=sys.stderr,
            )
            return completed.returncode, 0
        updated_processed.add(merged_pr.number)

    state["processed_merged_pull_request_numbers"] = sorted(updated_processed)
    return 0, len(pending_merged_prs)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    state_dir = repo_root / DEFAULT_STATE_DIR_NAME
    state_path = Path(args.state_path).resolve() if args.state_path else state_dir / "state.json"
    prompts_dir = (
        Path(args.prompts_dir).resolve()
        if args.prompts_dir
        else state_dir / DEFAULT_PROMPTS_DIR_NAME
    )
    state = load_state(state_path)
    command = resolve_agent_command(args, repo_root)

    processed_count = 0
    if args.mode in {"review", "all"}:
        exit_code, review_count = process_reviews(
            repo_root=repo_root,
            state=state,
            prompts_dir=prompts_dir,
            command=command,
            pr_number=args.pr_number,
            dry_run=args.dry_run,
        )
        if exit_code != 0:
            return exit_code
        processed_count += review_count

    if args.mode in {"merged-progress", "all"}:
        exit_code, merged_count = process_merged_pull_requests(
            repo_root=repo_root,
            state=state,
            prompts_dir=prompts_dir,
            command=command,
            base_branch=args.base_branch,
            role_name=args.role_name,
            role_file=(repo_root / args.role_file).resolve(),
            merged_pr_limit=args.merged_pr_limit,
            dry_run=args.dry_run,
        )
        if exit_code != 0:
            return exit_code
        processed_count += merged_count

    save_state(state_path, state)
    print(f"processed {processed_count} event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
