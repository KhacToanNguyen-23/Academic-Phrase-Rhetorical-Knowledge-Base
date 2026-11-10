from uuid import uuid4

from openpyxl import load_workbook

from aprkb.modules.mining.labelers import AI_LABEL_FIELDS
from aprkb.modules.mining.review_workbook import (
    FRAME_COLUMNS,
    read_review_decisions,
    write_review_workbook,
)
from aprkb.policies.loader import load_policy_bundle


def test_workbook_defaults_to_no_examples_and_uses_vocabulary_dropdowns(tmp_path) -> None:
    output = tmp_path / "review.xlsx"
    candidate_id = uuid4()
    labels = {
        field: {
            "value": "unclear",
            "confidence": 0.4,
            "agreement": "both_agree",
            "needs_attention": field == "intent",
        }
        for field in AI_LABEL_FIELDS
    }
    write_review_workbook(
        [
            {
                "candidate_id": str(candidate_id),
                "canonical_frame": "[X] report [Y]",
                "family": "Tier 1",
                "paper_count": 2,
                "sentence_count": 4,
                "section_distribution": "RESULTS 100%",
                "labels": labels,
                "examples": ["must not appear by default"],
                "paper_ids": ["opaque-one", "opaque-two"],
            }
        ],
        output,
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    workbook = load_workbook(output, data_only=True)
    sheet = workbook["Frames"]
    assert [cell.value for cell in sheet[1]] == FRAME_COLUMNS
    assert sheet.cell(row=2, column=FRAME_COLUMNS.index("Câu gốc ví dụ 1") + 1).value is None
    assert sheet.freeze_panes == "A2"
    assert workbook["_Vocabulary"].sheet_state == "hidden"
    assert any(validation.type == "list" for validation in sheet.data_validations.dataValidation)
    assert sheet.cell(row=2, column=1).fill.fgColor.rgb == "00FCE4D6"
    workbook.close()


def test_workbook_decisions_expand_to_api_decisions(tmp_path) -> None:
    output = tmp_path / "review.xlsx"
    candidate_id = uuid4()
    labels = {
        field: {"value": None, "confidence": None, "agreement": "disagree"}
        for field in AI_LABEL_FIELDS
    }
    labels["intent"] = {"value": "report_finding", "confidence": 0.7, "agreement": "both_agree"}
    write_review_workbook(
        [
            {
                "candidate_id": str(candidate_id),
                "canonical_frame": "[X] report [Y]",
                "family": "Tier 1",
                "paper_count": 2,
                "sentence_count": 4,
                "labels": labels,
            }
        ],
        output,
        vocabulary=load_policy_bundle().frame_label_vocabulary,
    )
    workbook = load_workbook(output)
    sheet = workbook["Frames"]
    sheet.cell(row=2, column=FRAME_COLUMNS.index("Đánh giá duyệt") + 1, value="DUYỆT")
    workbook.save(output)
    workbook.close()

    decisions = read_review_decisions(output)
    assert len(decisions) == 1
    assert decisions[0].candidate_id == candidate_id
    assert decisions[0].label_code == "intent"
    assert decisions[0].decision == "approve"
