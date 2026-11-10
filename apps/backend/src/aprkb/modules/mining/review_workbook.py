"""Local-only workbook rendering and decision parsing for frame-label review."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any
from uuid import UUID

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from aprkb.modules.mining.label_review_schemas import FrameLabelDecision
from aprkb.modules.mining.labelers import AI_LABEL_FIELDS, vocabulary_codes
from aprkb.policies.schemas import FrameLabelVocabularyPolicy

BASE_COLUMNS = [
    "STT",
    "Frame",
    "Family",
    "Số bài",
    "Số câu",
    "Phân bố Section (IMRaD %)",
    "epistemic_strength",
    "Câu gốc ví dụ 1",
    "Câu gốc ví dụ 2",
    "intent",
    "move",
    "General function",
    "Đánh giá duyệt",
]
PROPOSAL_COLUMNS = [
    column
    for label in AI_LABEL_FIELDS
    for column in (f"{label} đề xuất", f"{label} confidence", f"{label} agreement")
]
CORRECTION_COLUMNS = [f"Sửa {label}" for label in AI_LABEL_FIELDS]
HELPER_COLUMNS = [
    "Gợi ý từ luật",
    "Nhóm chức năng (gợi ý)",
    "Candidate ID",
    "Paper ID 1",
    "Paper ID 2",
]
FRAME_COLUMNS = [*BASE_COLUMNS, *PROPOSAL_COLUMNS, *CORRECTION_COLUMNS, *HELPER_COLUMNS]
DECISIONS = ("DUYỆT", "SỬA", "LOẠI")


def write_review_workbook(
    rows: Iterable[Mapping[str, Any]],
    output_path: Path,
    *,
    vocabulary: FrameLabelVocabularyPolicy,
    with_examples: bool = False,
    existing_path: Path | None = None,
) -> None:
    """Write proposals with sentence examples omitted unless explicitly enabled."""
    rows = list(rows)
    workbook = Workbook()
    frames = workbook.active
    assert isinstance(frames, Worksheet)
    frames.title = "Frames"
    frames.append(FRAME_COLUMNS)
    for index, row in enumerate(rows, start=1):
        examples = row.get("examples", []) if with_examples else []
        examples = [str(example)[:300] for example in examples[:2]]
        labels = row.get("labels", {})
        base = [
            index,
            row.get("canonical_frame", ""),
            row.get("family", ""),
            row.get("paper_count", 0),
            row.get("sentence_count", 0),
            row.get("section_distribution", "UNKNOWN"),
            row.get("epistemic_strength"),
            examples[0] if examples else None,
            examples[1] if len(examples) > 1 else None,
            _label_value(labels, "intent"),
            _label_value(labels, "move"),
            _label_value(labels, "general_function"),
            None,
        ]
        proposal_values: list[Any] = []
        for label in AI_LABEL_FIELDS:
            record = labels.get(label, {})
            proposal_values.extend(
                [record.get("value"), record.get("confidence"), record.get("agreement")]
            )
        corrections = [None] * len(AI_LABEL_FIELDS)
        helpers = [
            row.get("anchor_suggestion"),
            labels.get("function_group", {}).get("value"),
            str(row.get("candidate_id", "")),
            *(row.get("paper_ids", [])[:2]),
        ]
        helpers.extend([None] * (5 - len(helpers)))
        frames.append([*base, *proposal_values, *corrections, *helpers])

    _style_sheet(frames)
    decision_column = FRAME_COLUMNS.index("Đánh giá duyệt") + 1
    decision_validation = DataValidation(type="list", formula1='"DUYỆT,SỬA,LOẠI"')
    frames.add_data_validation(decision_validation)
    decision_validation.add(
        f"{get_column_letter(decision_column)}2:{get_column_letter(decision_column)}1048576"
    )
    codes_by_label = vocabulary_codes(vocabulary)
    vocabulary_sheet = workbook.create_sheet("_Vocabulary")
    vocabulary_sheet.sheet_state = "hidden"
    choices_by_name: dict[str, list[str]] = {**codes_by_label, "decision": list(DECISIONS)}
    for column_number, (name, choices) in enumerate(choices_by_name.items(), start=1):
        for row_number, code in enumerate(choices, start=1):
            vocabulary_sheet.cell(row=row_number, column=column_number, value=code)
        column_letter = get_column_letter(column_number)
        defined_name = f"Frame_{name}_codes"
        workbook.defined_names.add(
            DefinedName(
                defined_name,
                attr_text=f"'_Vocabulary'!${column_letter}$1:${column_letter}${len(choices)}",
            )
        )
    decision_validation.formula1 = "=Frame_decision_codes"
    for label in AI_LABEL_FIELDS:
        formula = f"=Frame_{label}_codes"
        for column_name in (f"{label} đề xuất", f"Sửa {label}"):
            column = FRAME_COLUMNS.index(column_name) + 1
            validation = DataValidation(type="list", formula1=formula, allow_blank=True)
            frames.add_data_validation(validation)
            validation.add(f"{get_column_letter(column)}2:{get_column_letter(column)}1048576")
    attention_fill = PatternFill("solid", fgColor="FCE4D6")
    for index, row in enumerate(rows, start=2):
        labels = row.get("labels", {})
        if any(bool(record.get("needs_attention")) for record in labels.values()):
            for cell in frames[index]:
                cell.fill = attention_fill

    guide = workbook.create_sheet("Hướng dẫn")
    guide.append(["CHỈ DÙNG CỤC BỘ — không commit hoặc chia sẻ workbook này."])
    guide.append(
        ["Mỗi dòng là một frame được nhóm theo cluster_key; không thêm câu gốc vào ghi chú."]
    )
    guide.append(
        [
            "STT: số thứ tự; Frame: canonical frame đã che slot; "
            "Family: tier hoặc construction family."
        ]
    )
    guide.append(
        [
            "Số bài: distinct source articles; Số câu: source sentence count; "
            "Phân bố Section: mã section và tỷ lệ đã quan sát."
        ]
    )
    guide.append(
        [
            "epistemic_strength: nhãn rule hiện có; Câu gốc ví dụ: trống mặc định, "
            "chỉ điền qua tùy chọn --with-examples."
        ]
    )
    guide.append(
        [
            "Các cột intent, move, General function và các cột đề xuất là gợi ý AI; "
            "confidence là độ tin cậy tự báo; agreement là kết quả hai lượt."
        ]
    )
    guide.append(
        [
            "Đánh giá duyệt: DUYỆT chấp nhận các giá trị có sẵn; SỬA dùng cột Sửa tương ứng; "
            "LOẠI từ chối mọi nhãn được đề xuất."
        ]
    )
    guide.append(
        [
            "Các trường sửa dùng dropdown vocabulary; unclear và none_of_these "
            "biểu thị hai lựa chọn từ chối đoán."
        ]
    )
    guide.append(
        [
            "Constraints do người duyệt quyết định; không được AI tự điền. "
            "Sequence hint chưa có đề xuất."
        ]
    )
    guide.append(
        [
            "Mọi quyết định qua frame_labels_apply_review.py cần reviewer id; "
            "import ghi audit không chứa câu nguồn."
        ]
    )
    column_help = {
        "STT": "Số thứ tự của dòng trong lần xuất này.",
        "Frame": "Canonical frame đã che các slot bằng placeholder.",
        "Family": "Tier hoặc construction family đã nhận dạng.",
        "Số bài": "Số bài nguồn khác nhau.",
        "Số câu": "Số câu nguồn gắn với frame.",
        "Phân bố Section (IMRaD %)": "Các section quan sát được và tỷ lệ trên nguồn đã biết.",
        "epistemic_strength": "Nhãn từ rule tagger hiện có.",
        "Câu gốc ví dụ 1": "Ví dụ nguồn chỉ xuất hiện khi chạy exporter với --with-examples.",
        "Câu gốc ví dụ 2": "Ví dụ từ bài khác khi có thể; tắt theo mặc định.",
        "intent": "Giá trị intent được đề xuất; DUYỆT chấp nhận, SỬA dùng cột sửa, LOẠI từ chối.",
        "move": "Giá trị move được đề xuất theo cây từ vựng.",
        "General function": "Đề xuất general function; không suy ra từ section.",
        "Đánh giá duyệt": "Quyết định cho toàn bộ proposal của frame: DUYỆT, SỬA, hoặc LOẠI.",
        "Gợi ý từ luật": "Anchor suggestion hiện có; chỉ là gợi ý.",
        "Nhóm chức năng (gợi ý)": "Function group được gợi ý từ AI hoặc anchor.",
        "Candidate ID": "UUID dùng để áp dụng quyết định qua service.",
        "Paper ID 1": "Mã băm opaque của một bài nguồn.",
        "Paper ID 2": "Mã băm opaque của bài nguồn thứ hai nếu có.",
    }
    for label in AI_LABEL_FIELDS:
        column_help[f"{label} đề xuất"] = (
            f"Mã từ vựng được đề xuất cho {label}; để trống nếu hai lượt chưa thống nhất."
        )
        column_help[f"{label} confidence"] = f"Confidence thấp hơn giữa hai lượt cho {label}."
        column_help[f"{label} agreement"] = f"Kết quả đồng thuận hai lượt cho {label}."
        column_help[f"Sửa {label}"] = f"Giá trị thay thế cho {label} khi chọn SỬA."
    guide.append(["Ý nghĩa từng cột"])
    for column_name in FRAME_COLUMNS:
        guide.append(
            [
                f"{column_name}: "
                f"{column_help.get(column_name, 'Cột phụ trợ trong quy trình duyệt.')} "
            ]
        )
    guide.freeze_panes = "A2"
    guide.column_dimensions["A"].width = 110
    for row in guide.iter_rows():
        row[0].alignment = Alignment(wrap_text=True, vertical="top")
    for row in guide.iter_rows():
        guide.row_dimensions[row[0].row].height = 34

    if existing_path is not None and existing_path.exists():
        _copy_epistemic_sheet(existing_path, workbook)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def read_review_decisions(path: Path) -> list[FrameLabelDecision]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["Frames"]
    headers = [cell.value for cell in sheet[1]]
    index = {str(value): position for position, value in enumerate(headers)}
    required = {
        "Candidate ID",
        "Đánh giá duyệt",
        *[f"{label} đề xuất" for label in AI_LABEL_FIELDS],
    }
    if not required <= set(index):
        raise ValueError("Reviewed workbook is missing expected columns")
    decisions: list[FrameLabelDecision] = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        candidate_value = row[index["Candidate ID"]]
        decision_value = row[index["Đánh giá duyệt"]]
        if not candidate_value or not decision_value:
            continue
        if decision_value not in DECISIONS:
            raise ValueError("Review decision must be DUYỆT, SỬA, or LOẠI")
        candidate_id = UUID(str(candidate_value))
        for label in AI_LABEL_FIELDS:
            proposed = row[index[f"{label} đề xuất"]]
            correction_column = f"Sửa {label}"
            correction = row[index[correction_column]] if correction_column in index else None
            if decision_value == "DUYỆT" and proposed:
                decisions.append(
                    FrameLabelDecision(
                        candidate_id=candidate_id,
                        label_code=label,
                        decision="approve",
                    )
                )
            elif decision_value == "SỬA" and correction:
                decisions.append(
                    FrameLabelDecision(
                        candidate_id=candidate_id,
                        label_code=label,
                        decision="edit",
                        value=str(correction),
                    )
                )
            elif decision_value == "LOẠI":
                decisions.append(
                    FrameLabelDecision(
                        candidate_id=candidate_id,
                        label_code=label,
                        decision="reject",
                    )
                )
    workbook.close()
    return decisions


def _label_value(labels: Mapping[str, Any], key: str) -> Any:
    record = labels.get(key, {})
    return record.get("value") if record.get("value") is not None else None


def _style_sheet(sheet: Any) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(FRAME_COLUMNS))}{sheet.max_row}"
    header_fill = PatternFill("solid", fgColor="1F4E78")
    for cell in sheet[1]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for column_index, title in enumerate(FRAME_COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(column_index)].width = min(
            max(len(title) + 4, 14), 32
        )
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")


def _copy_epistemic_sheet(existing_path: Path, workbook: Workbook) -> None:
    source_workbook = load_workbook(existing_path, read_only=False, data_only=False)
    if "Epistemic" not in source_workbook.sheetnames:
        source_workbook.close()
        return
    source = source_workbook["Epistemic"]
    target = workbook.create_sheet("Epistemic")
    for row in source.iter_rows():
        for cell in row:
            copied = target.cell(row=cell.row, column=cell.column, value=cell.value)
            if cell.has_style and isinstance(cell, Cell):
                copied._style = cell._style  # type: ignore[attr-defined]
            if cell.number_format:
                copied.number_format = cell.number_format
            if cell.alignment:
                copied.alignment = cell.alignment
    for key, dimension in source.column_dimensions.items():
        target.column_dimensions[key].width = dimension.width
    target.freeze_panes = source.freeze_panes or "A2"
    source_workbook.close()
