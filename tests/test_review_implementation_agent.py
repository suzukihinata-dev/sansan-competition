from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sansan_competition.review_implementation_agent import (
    PullRequestContext,
    ReviewEvent,
    ReviewInlineComment,
    MergedPullRequestEvent,
    build_merged_progress_prompt,
    build_prompt,
    format_agent_command,
    is_actionable_review,
    load_role_definition,
    load_state,
    save_state,
    select_pending_merged_pull_requests,
    select_pending_reviews,
)


def make_review(
    *,
    review_id: int = 1,
    state: str = "COMMENTED",
    body: str = "",
    comments: tuple[ReviewInlineComment, ...] = (),
) -> ReviewEvent:
    return ReviewEvent(
        review_id=review_id,
        state=state,
        author="review-bot",
        submitted_at="2026-07-03T15:00:00Z",
        body=body,
        comments=comments,
        pull_request=PullRequestContext(
            repo_full_name="owner/repo",
            pr_number=12,
            title="Improve review automation",
            url="https://github.com/owner/repo/pull/12",
            head_ref="feature/review-agent",
            base_ref="master",
        ),
    )


def make_merged_pull_request(
    *,
    number: int = 8,
    merged_at: str = "2026-07-03T16:00:00Z",
) -> MergedPullRequestEvent:
    return MergedPullRequestEvent(
        number=number,
        title="Merge shared JSON contract work",
        url="https://github.com/owner/repo/pull/8",
        author="teammate",
        body="Shared JSON fields and tests were aligned.",
        merged_at=merged_at,
        head_ref="feature/shared-contract",
        base_ref="master",
    )


class ReviewImplementationAgentTests(unittest.TestCase):
    def test_actionable_review_detected_from_inline_comment(self) -> None:
        review = make_review(
            comments=(ReviewInlineComment(body="Fix the branch name.", path="README.md", line=3),),
        )
        self.assertTrue(is_actionable_review(review))

    def test_approved_review_is_not_actionable(self) -> None:
        review = make_review(state="APPROVED", body="Looks good to me.")
        self.assertFalse(is_actionable_review(review))

    def test_select_pending_reviews_filters_processed_ids(self) -> None:
        pending = select_pending_reviews(
            [
                make_review(review_id=1, body="Please update docs."),
                make_review(review_id=2, body="Please add a test."),
            ],
            {1},
        )
        self.assertEqual([review.review_id for review in pending], [2])

    def test_build_prompt_includes_inline_locations(self) -> None:
        review = make_review(
            body="Address the review findings.",
            comments=(
                ReviewInlineComment(
                    body="This message is inaccurate.",
                    path="README.md",
                    line=14,
                    side="RIGHT",
                ),
            ),
        )
        prompt = build_prompt(review)
        self.assertIn("PR: #12 Improve review automation", prompt)
        self.assertIn("README.md:14 (RIGHT)", prompt)
        self.assertIn("This message is inaccurate.", prompt)

    def test_format_agent_command_renders_repo_root_placeholder(self) -> None:
        command = format_agent_command(
            "codex exec --cd {repo_root} --sandbox workspace-write",
            Path("/tmp/example"),
        )
        self.assertEqual(
            command,
            ["codex", "exec", "--cd", "/tmp/example", "--sandbox", "workspace-write"],
        )

    def test_state_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = Path(temp_dir) / "state.json"
            save_state(state_path, {"processed_review_ids": [3, 4]})
            self.assertEqual(load_state(state_path), {"processed_review_ids": [3, 4]})

    def test_select_pending_merged_pull_requests_filters_processed_numbers(self) -> None:
        pending = select_pending_merged_pull_requests(
            [make_merged_pull_request(number=8), make_merged_pull_request(number=9)],
            {8},
        )
        self.assertEqual([pull.number for pull in pending], [9])

    def test_build_merged_progress_prompt_mentions_role_and_merge_context(self) -> None:
        prompt = build_merged_progress_prompt(
            make_merged_pull_request(),
            role_name="hinata",
            role_definition="### 2.1 hinata — AI生成・品質責任者\n- リマインド文の生成処理",
        )
        self.assertIn("implementation architect", prompt)
        self.assertIn("`hinata`", prompt)
        self.assertIn("Merge shared JSON contract work", prompt)
        self.assertIn("ROLE.md", prompt)

    def test_load_role_definition_extracts_matching_role_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            role_path = Path(temp_dir) / "ROLE.md"
            role_path.write_text(
                "\n".join(
                    [
                        "# 開発役割定義",
                        "",
                        "### 2.1 hinata — AI生成・品質責任者",
                        "- AI生成",
                        "",
                        "### 2.2 kimu — AIデータ処理・JSON契約責任者",
                        "- JSON契約",
                    ]
                ),
                encoding="utf-8",
            )
            excerpt = load_role_definition(role_path, role_name="kimu")
            self.assertIn("### 2.2 kimu", excerpt)
            self.assertNotIn("### 2.1 hinata", excerpt)


if __name__ == "__main__":
    unittest.main()
