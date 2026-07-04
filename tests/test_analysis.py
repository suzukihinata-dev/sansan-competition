from __future__ import annotations

from datetime import datetime
import unittest

from sansan_competition.analysis import analyze_submissions, build_ai_task_input
from sansan_competition.models import AgentTaskType, JST
from sansan_competition.normalization import (
    normalize_course,
    normalize_coursework,
    normalize_submission_batch,
)


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.default_now = datetime(2026, 7, 5, 9, 0, tzinfo=JST)
        self.course = normalize_course(
            {
                "id": "course_001",
                "name": "数学I",
                "section": "1年A組",
                "studentCount": 4,
            }
        )
        self.course_work = self._coursework()
        self.base_raw_submissions = [
            self._submission(
                submission_id="sub_001",
                student_id="student_001",
                student_name="山田太郎",
                state="NEW",
            ),
            self._submission(
                submission_id="sub_002",
                student_id="student_002",
                student_name="佐藤花子",
                state="TURNED_IN",
                submissionTime="2026-07-05T10:00:00+09:00",
                attachments=[{"driveFile": {"id": "file_001"}}],
            ),
            self._submission(
                submission_id="sub_003",
                student_id="student_003",
                student_name="鈴木一郎",
                state="TURNED_IN",
                submissionTime="2026-07-05T13:15:00+09:00",
                late=True,
            ),
            self._submission(
                submission_id="sub_004",
                student_id="student_004",
                student_name="高橋未来",
                state="NEW",
            ),
        ]
        self.submissions, self.issues = normalize_submission_batch(
            self.base_raw_submissions
        )

    def _coursework(self, **overrides: object):
        raw = {
            "id": "cw_001",
            "courseId": "course_001",
            "title": "二次関数プリント",
            "workType": "ASSIGNMENT",
            "dueDate": "2026-07-05",
            "dueTime": "12:00",
        }
        raw.update(overrides)
        return normalize_coursework(raw)

    def _submission(
        self,
        *,
        submission_id: str,
        student_id: str,
        student_name: str,
        state: str,
        **overrides: object,
    ) -> dict[str, object]:
        raw: dict[str, object] = {
            "id": submission_id,
            "courseId": "course_001",
            "courseWorkId": "cw_001",
            "studentId": student_id,
            "studentName": student_name,
            "state": state,
        }
        raw.update(overrides)
        return raw

    def _analysis_from_raw(
        self,
        raw_submissions: list[dict[str, object]],
        *,
        course_work=None,
        now: datetime | None = None,
    ):
        submissions, issues = normalize_submission_batch(raw_submissions)
        return analyze_submissions(
            self.course,
            course_work or self.course_work,
            submissions,
            now=now or self.default_now,
            normalization_issues=issues,
        )

    def test_analyze_submissions_counts_due_soon_late_and_attachment_flags(self) -> None:
        analysis = analyze_submissions(
            self.course,
            self.course_work,
            self.submissions,
            now=self.default_now,
            normalization_issues=self.issues,
        )

        counts = analysis.counts()
        self.assertEqual(counts["unsubmittedCount"], 2)
        self.assertEqual(counts["dueSoonCount"], 2)
        self.assertEqual(counts["lateCount"], 1)
        self.assertEqual(counts["attachmentMissingPossibleCount"], 1)

    def test_build_ai_task_input_omits_personal_identifiers_by_default(self) -> None:
        analysis = analyze_submissions(
            self.course,
            self.course_work,
            self.submissions,
            now=self.default_now,
        )

        payload = build_ai_task_input(AgentTaskType.REMINDER_GENERATION, analysis)
        detailed_payload = build_ai_task_input(
            AgentTaskType.REMINDER_GENERATION,
            analysis,
            include_student_names=True,
        )

        first_entry = payload["facts"]["submissions"][0]
        detailed_first_entry = detailed_payload["facts"]["submissions"][0]

        self.assertNotIn("studentId", first_entry)
        self.assertNotIn("studentName", first_entry)
        self.assertIn("studentId", detailed_first_entry)
        self.assertIn("studentName", detailed_first_entry)

    def test_build_ai_task_input_for_reminder_targets_only_unsubmitted_students(self) -> None:
        analysis = analyze_submissions(
            self.course,
            self.course_work,
            self.submissions,
            now=self.default_now,
        )

        payload = build_ai_task_input(
            AgentTaskType.REMINDER_GENERATION,
            analysis,
            output_formats=["classroomReminder"],
            tone="polite",
            teacher_instruction="締切日を入れてください。",
        )

        self.assertEqual(payload["focus"]["selectionMode"], "unsubmitted_targets")
        self.assertEqual(payload["delivery"]["outputFormats"], ["classroomReminder"])
        self.assertEqual(
            payload["delivery"]["teacherInstruction"],
            "締切日を入れてください。",
        )
        self.assertEqual(payload["facts"]["targetSummary"]["targetStudentCount"], 2)
        self.assertEqual(len(payload["facts"]["submissions"]), 2)
        self.assertTrue(
            all(entry["isMissing"] for entry in payload["facts"]["submissions"])
        )

    def test_build_ai_task_input_for_course_summary_uses_aggregate_only_mode(self) -> None:
        analysis = analyze_submissions(
            self.course,
            self.course_work,
            self.submissions,
            now=self.default_now,
        )

        payload = build_ai_task_input(AgentTaskType.COURSE_SUMMARY, analysis)

        self.assertEqual(payload["focus"]["selectionMode"], "aggregate_only")
        self.assertEqual(payload["facts"]["submissions"], [])
        self.assertEqual(payload["privacy"]["appliedDetailMode"], "aggregate_only")
        self.assertEqual(payload["privacy"]["studentIdentifierMode"], "no_student_identifiers")

    def test_short_answer_submission_is_not_flagged_as_attachment_missing(self) -> None:
        short_answer_work = normalize_coursework(
            {
                "id": "cw_short",
                "courseId": "course_001",
                "title": "確認問題",
                "workType": "SHORT_ANSWER_QUESTION",
                "dueDate": "2026-07-05",
                "dueTime": "12:00",
            }
        )
        analysis = self._analysis_from_raw(
            [
                self._submission(
                    submission_id="sub_short",
                    student_id="student_001",
                    student_name="山田太郎",
                    state="TURNED_IN",
                    shortAnswerSubmission={"answer": "x=2"},
                )
            ],
            course_work=short_answer_work,
        )

        self.assertEqual(analysis.counts()["attachmentMissingPossibleCount"], 0)

    def test_due_date_only_boundary_uses_2359_and_turns_over_after_midnight(self) -> None:
        date_only_work = self._coursework(
            id="cw_date_only",
            title="日付のみ課題",
            dueTime=None,
        )
        raw_submissions = [
            self._submission(
                submission_id="sub_date_only",
                student_id="student_001",
                student_name="山田太郎",
                state="NEW",
                courseWorkId="cw_date_only",
            )
        ]

        at_deadline = self._analysis_from_raw(
            raw_submissions,
            course_work=date_only_work,
            now=datetime(2026, 7, 5, 23, 59, tzinfo=JST),
        )
        after_deadline = self._analysis_from_raw(
            raw_submissions,
            course_work=date_only_work,
            now=datetime(2026, 7, 6, 0, 0, tzinfo=JST),
        )

        self.assertEqual(at_deadline.counts()["dueSoonCount"], 1)
        self.assertEqual(at_deadline.evaluations[0].status_label, "期限接近未提出")
        self.assertEqual(after_deadline.counts()["dueSoonCount"], 0)
        self.assertEqual(after_deadline.evaluations[0].status_label, "期限超過未提出")

    def test_exact_due_time_is_not_late_and_unsubmitted_late_flag_is_ignored(self) -> None:
        analysis = self._analysis_from_raw(
            [
                self._submission(
                    submission_id="sub_exact",
                    student_id="student_001",
                    student_name="山田太郎",
                    state="TURNED_IN",
                    submissionTime="2026-07-05T12:00:00+09:00",
                    attachments=[{"driveFile": {"id": "file_001"}}],
                ),
                self._submission(
                    submission_id="sub_after",
                    student_id="student_002",
                    student_name="佐藤花子",
                    state="TURNED_IN",
                    submissionTime="2026-07-05T12:00:01+09:00",
                    attachments=[{"driveFile": {"id": "file_002"}}],
                ),
                self._submission(
                    submission_id="sub_missing",
                    student_id="student_003",
                    student_name="鈴木一郎",
                    state="NEW",
                    late=True,
                ),
            ],
            now=datetime(2026, 7, 5, 12, 0, tzinfo=JST),
        )

        exact = next(
            entry for entry in analysis.evaluations if entry.student_id == "student_001"
        )
        after = next(
            entry for entry in analysis.evaluations if entry.student_id == "student_002"
        )
        missing = next(
            entry for entry in analysis.evaluations if entry.student_id == "student_003"
        )

        self.assertFalse(exact.is_late)
        self.assertTrue(after.is_late)
        self.assertFalse(missing.is_late)
        self.assertEqual(analysis.counts()["lateCount"], 1)
        self.assertEqual(analysis.counts()["dueSoonCount"], 1)

    def test_returned_submission_is_treated_as_submitted_and_can_flag_attachment_gap(self) -> None:
        analysis = self._analysis_from_raw(
            [
                self._submission(
                    submission_id="sub_returned",
                    student_id="student_001",
                    student_name="山田太郎",
                    state="RETURNED",
                    submissionTime="2026-07-05T11:00:00+09:00",
                    attachments=[],
                )
            ]
        )

        entry = analysis.evaluations[0]
        self.assertTrue(entry.is_submitted)
        self.assertTrue(entry.is_returned)
        self.assertFalse(entry.is_missing)
        self.assertEqual(entry.status_label, "返却済み")
        self.assertEqual(analysis.counts()["unsubmittedCount"], 0)
        self.assertEqual(analysis.counts()["attachmentMissingPossibleCount"], 1)
        self.assertIn("教師によって返却済みです。", entry.notes)
        self.assertIn("提出済みですが添付不足の可能性があります。", entry.notes)

    def test_graded_unsubmitted_state_is_treated_as_exempt_like_and_excluded_from_targets(self) -> None:
        analysis = self._analysis_from_raw(
            [
                self._submission(
                    submission_id="sub_excused",
                    student_id="student_001",
                    student_name="山田太郎",
                    state="NEW",
                    assignedGrade=100,
                )
            ]
        )

        entry = analysis.evaluations[0]
        counts = analysis.counts()
        reminder_payload = build_ai_task_input(
            AgentTaskType.REMINDER_GENERATION,
            analysis,
        )
        rubric_payload = build_ai_task_input(
            AgentTaskType.RUBRIC_SUPPORT,
            analysis,
        )

        self.assertTrue(entry.is_exempt_like)
        self.assertFalse(entry.is_missing)
        self.assertFalse(entry.is_due_soon)
        self.assertFalse(entry.is_late)
        self.assertEqual(entry.status_label, "提出免除の可能性")
        self.assertEqual(counts["submittedCount"], 1)
        self.assertEqual(counts["unsubmittedCount"], 0)
        self.assertFalse(analysis.teacher_action_required())
        self.assertEqual(
            analysis.recommended_action(),
            "大きな対応は不要です。必要ならレポートを出力して共有してください。",
        )
        self.assertEqual(reminder_payload["facts"]["targetSummary"]["targetStudentCount"], 0)
        self.assertEqual(reminder_payload["facts"]["submissions"], [])
        self.assertTrue(
            any("提出免除" in warning for warning in reminder_payload["facts"]["warnings"])
        )
        self.assertEqual(rubric_payload["facts"]["targetSummary"]["targetStudentCount"], 0)

    def test_rubric_support_targets_only_actual_submissions_when_exempt_like_is_mixed_in(self) -> None:
        analysis = self._analysis_from_raw(
            [
                self._submission(
                    submission_id="sub_returned",
                    student_id="student_001",
                    student_name="山田太郎",
                    state="RETURNED",
                    submissionTime="2026-07-05T11:00:00+09:00",
                    attachments=[{"driveFile": {"id": "file_001"}}],
                ),
                self._submission(
                    submission_id="sub_excused",
                    student_id="student_002",
                    student_name="佐藤花子",
                    state="NEW",
                    draftGrade=80,
                ),
            ]
        )

        payload = build_ai_task_input(AgentTaskType.RUBRIC_SUPPORT, analysis)

        self.assertEqual(payload["facts"]["targetSummary"]["targetStudentCount"], 1)
        self.assertEqual(len(payload["facts"]["submissions"]), 1)
        self.assertEqual(payload["facts"]["submissions"][0]["submissionState"], "RETURNED")

    def test_warnings_are_reserved_for_heuristics_and_data_quality_not_normal_statuses(self) -> None:
        analysis = self._analysis_from_raw(
            [
                self._submission(
                    submission_id="sub_missing",
                    student_id="student_001",
                    student_name="山田太郎",
                    state="NEW",
                ),
                self._submission(
                    submission_id="sub_late",
                    student_id="student_002",
                    student_name="佐藤花子",
                    state="TURNED_IN",
                    submissionTime="2026-07-05T13:00:00+09:00",
                    attachments=[{"driveFile": {"id": "file_001"}}],
                ),
            ]
        )

        payload = build_ai_task_input(AgentTaskType.SUBMISSION_ANALYSIS, analysis)

        self.assertEqual(payload["facts"]["warnings"], [])
        self.assertEqual(payload["facts"]["submissionSummary"]["unsubmittedCount"], 1)
        self.assertEqual(payload["facts"]["submissionSummary"]["dueSoonCount"], 1)
        self.assertEqual(payload["facts"]["submissionSummary"]["lateCount"], 1)


if __name__ == "__main__":
    unittest.main()
