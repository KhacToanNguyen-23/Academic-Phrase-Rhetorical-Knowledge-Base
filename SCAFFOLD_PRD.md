# AP-RKB — PRD dựng khung (Scaffold) v0.2

> **Đối tượng đọc:** coding agent dùng để dựng bộ khung ban đầu cho dự án.
> **Mục tiêu:** tạo ra một repo **chạy được, test được, nhưng gần như chưa có logic nghiệp vụ**. Mọi module có đủ ranh giới, interface, schema và test giữ chỗ để các bước sau chỉ còn việc "điền ruột".
> **Tài liệu gốc:** `Academic_Wordbank_PRD_VN.pdf`, `Academic_Wordbank_System_Design_VN.pdf`, `WordBank_brainstorm.md`. Khi tài liệu này mâu thuẫn với tài liệu gốc, **lấy tài liệu này** cho giai đoạn scaffold.

---

## 0. Hướng dẫn cho agent

1. Đọc hết tài liệu này trước khi tạo file.
2. Làm đúng **Phạm vi** (mục 2). Không tự ý thêm tính năng, thư viện hay service ngoài danh sách.
3. Chỗ nào ghi `TODO(owner)` thì giữ nguyên dạng `TODO`, **không tự bịa nội dung nghiệp vụ** (ví dụ tên rule, ngưỡng, từ vựng).
4. Logic chưa làm: viết `raise NotImplementedError("<mã yêu cầu>")` hoặc trả giá trị stub đã mô tả. Mỗi stub phải ghi mã yêu cầu liên quan (`BR-xx`, `FR-xx`, `AT-xx`, `V0x`).
5. Hoàn thành khi đạt toàn bộ **Definition of Done** (mục 12).

---

## 1. Các quyết định đã chốt

| # | Quyết định | Giá trị |
|---|---|---|
| D1 | Ngôn ngữ / framework | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x (async), Alembic |
| D2 | CSDL | PostgreSQL 16 + extension `pgvector` |
| D3 | Hàng đợi job | Bảng `jobs` trong Postgres + worker polling (`SELECT … FOR UPDATE SKIP LOCKED`). **Chưa dùng** Redis/Celery |
| D4 | Lưu file | Thư mục local `./data/blobs` qua interface `BlobStore`. **Chưa dùng** MinIO |
| D5 | Ranh giới hệ thống | AP-RKB là **server**: REST API `/v1` + admin console. Writing Engine là **client bên ngoài**, không nằm trong repo |
| D6 | Xác thực | API key (header `X-API-Key`) + RBAC theo role |
| D7 | Versioning | `pattern_versions` chỉ được thêm, không được sửa (append-only). Taxonomy phát hành theo `taxonomy_release`. API có prefix `/v1` |
| D8 | Cấu hình nghiệp vụ | File YAML có version trong `app/policies/`, không hard-code trong code |
| D9 | Enum nghiệp vụ | Lưu ở bảng tham chiếu trong DB (seed được), không dùng Postgres ENUM |
| D10 | Công cụ | `uv` (quản lý package), `ruff`, `mypy --strict` (với `app/`), `pytest`, `pytest-asyncio` |
| D11 | Admin console | Ngoại lệ M2: thêm review gold tại `/gold` và API `/v1/admin/gold/*`; Groq key chỉ lấy từ `.env` local khi owner chủ động chạy thử; các màn hình admin khác chưa làm |
| D12 | Nguồn bài báo | SLR Repository API qua `SlrRepositorySource`. Curator cấu hình bộ lọc trên web (`ImportProfile`) rồi bấm lấy bài. License fail closed theo `policies/licenses.yaml` ([ADR-0006](doc/adr/0006-slr-repository-import.md)) |

---

## 2. Phạm vi scaffold

### Làm

- Cấu trúc thư mục đầy đủ (mục 3).
- `docker-compose.yml` chạy Postgres + pgvector.
- Model SQLAlchemy và **một migration Alembic ban đầu** cho mọi entity ở mục 4.
- Toàn bộ interface lõi (mục 5) kèm ít nhất một implementation đơn giản hoặc stub.
- Khung pipeline cho recommendation, validation và mining (mục 6), nối các class qua registry.
- Router `/v1` cho mọi endpoint ở mục 7, có schema request/response Pydantic. Endpoint chưa làm trả `501`.
- Xác thực bằng API key + RBAC, ghi audit log cho mọi request ghi dữ liệu.
- Các file policy YAML mẫu (mục 8) và loader có kiểm tra schema.
- Seed tối thiểu (mục 9) và lệnh nạp seed.
- Test: unit test cho khung (phải pass) và acceptance test AT-01..AT-12 dạng skip (mục 10).
- `Makefile` với các lệnh chuẩn (mục 11).
- Nhập bài từ SLR Repository API (ADR-0006): adapter `SlrRepositorySource`, entity `ImportProfile` + API quản lý profile, job `import_articles` nhận `profile_id`, `policies/licenses.yaml` (danh sách license + bảng ánh xạ chuỗi license của nguồn).
- Màn hình web **Import từ SLR** trong `apps/web`, chạy như web bình thường và gọi API thật: chọn/sửa profile, chọn ngành qua taxonomy SLR, bấm "Lấy bài báo", xem tiến độ job.

### Không làm

- Production move/intent/epistemic classifiers, NER, LLM và clustering bằng embedding vẫn để sau; các stage tương ứng vẫn là stub. Ngoại lệ M2 có giới hạn được ghi ở mục 6.3 không cho phép bật extraction chưa được đánh giá.
- Tích hợp nguồn bài báo khác ngoài SLR. Không dùng OpenAlex API (ID taxonomy OpenAlex chỉ là giá trị bộ lọc do SLR trả về); phân loại ngành giữ interface + `NullDisciplineSource`.
- Đẩy bài lên SLR (`POST /works/import`) và dùng kết quả phân tích của SLR (`analysis-*`).
- Journal fingerprint. Chỉ làm stub, trả `None`.
- Parse PDF thật (GROBID). Chỉ làm interface + parser stub.
- Các màn hình admin console khác ngoài Import từ SLR (review queue, pattern, API key…).
- Deploy, CI/CD, monitoring.

---

## 3. Cấu trúc thư mục

```
ap-rkb/
├─ pyproject.toml
├─ Makefile
├─ docker-compose.yml
├─ .env.example
├─ alembic.ini
├─ README.md
│
├─ app/
│  ├─ main.py                     # tạo FastAPI app, gắn router, middleware
│  ├─ api/
│  │  ├─ deps.py                  # get_db, get_current_client, require_role(...)
│  │  └─ v1/
│  │     ├─ __init__.py           # gom router
│  │     ├─ taxonomy.py
│  │     ├─ patterns.py
│  │     ├─ recommendations.py
│  │     ├─ validate.py
│  │     ├─ feedback.py
│  │     ├─ overrides.py
│  │     ├─ journals.py
│  │     └─ admin/
│  │        ├─ review_queue.py
│  │        ├─ api_keys.py
│  │        ├─ corpus.py
│  │        └─ releases.py
│  │
│  ├─ core/
│  │  ├─ config.py                # Settings (pydantic-settings), đọc .env
│  │  ├─ auth.py                  # hash API key, Role, kiểm quyền
│  │  ├─ audit.py                 # ghi AuditEvent
│  │  ├─ errors.py                # AppError + handler → định dạng lỗi chung
│  │  ├─ blobstore.py             # interface BlobStore + LocalBlobStore
│  │  └─ logging.py
│  │
│  ├─ db/
│  │  ├─ base.py                  # DeclarativeBase, mixin created_at/created_by
│  │  ├─ session.py
│  │  ├─ models/                  # mỗi nhóm entity một file (xem mục 4)
│  │  └─ migrations/              # Alembic
│  │
│  ├─ policies/                   # YAML có version (mục 8)
│  │  ├─ evidence_matrix.yaml
│  │  ├─ ranking_weights.yaml
│  │  ├─ fallback_tiers.yaml
│  │  ├─ validation_rules.yaml
│  │  └─ lexicon/
│  │     └─ epistemic_markers.yaml
│  │
│  ├─ modules/
│  │  ├─ policy/                  # logic nghiệp vụ DÙNG CHUNG
│  │  │  ├─ loader.py             # nạp + kiểm tra schema các YAML
│  │  │  ├─ evidence_policy.py
│  │  │  ├─ epistemic_lexicon.py
│  │  │  └─ guideline_policy.py
│  │  │
│  │  ├─ taxonomy/                # PRD-01  P0
│  │  │  ├─ schemas.py  service.py  repository.py
│  │  ├─ patterns/                # PRD-02  P0
│  │  │  ├─ schemas.py  service.py  repository.py
│  │  │  └─ review.py             # duyệt Candidate → PatternVersion
│  │  ├─ journals/                # PRD-05  P0
│  │  │  ├─ schemas.py  service.py  repository.py
│  │  │  └─ fingerprint.py        # stub, trả None
│  │  ├─ recommendation/          # PRD-07  P0
│  │  │  ├─ context.py
│  │  │  ├─ pipeline.py
│  │  │  ├─ gates/
│  │  │  │  ├─ __init__.py        # build_gates()
│  │  │  │  ├─ base.py
│  │  │  │  ├─ approval_gate.py
│  │  │  │  ├─ license_gate.py
│  │  │  │  ├─ intent_section_gate.py
│  │  │  │  ├─ evidence_gate.py
│  │  │  │  ├─ retired_gate.py
│  │  │  │  └─ guideline_gate.py
│  │  │  ├─ scorers/
│  │  │  │  ├─ __init__.py        # build_scorers()
│  │  │  │  ├─ base.py
│  │  │  │  ├─ intent_scorer.py
│  │  │  │  ├─ discipline_scorer.py
│  │  │  │  ├─ journal_genre_scorer.py
│  │  │  │  ├─ evidence_scorer.py
│  │  │  │  ├─ linguistic_scorer.py
│  │  │  │  ├─ provenance_scorer.py
│  │  │  │  └─ aggregator.py
│  │  │  ├─ fallback.py
│  │  │  └─ diversifier.py
│  │  ├─ validation/              # PRD-08  P0
│  │  │  ├─ pipeline.py
│  │  │  └─ rules/
│  │  │     ├─ __init__.py        # build_rules()
│  │  │     ├─ base.py
│  │  │     └─ v01_*.py … v08_*.py   # 8 file, tên ở mục 6.2
│  │  ├─ corpus/                  # PRD-04  P1 (stub)
│  │  │  ├─ ingest.py
│  │  │  ├─ license_check.py
│  │  │  ├─ parsers/
│  │  │  │  ├─ base.py
│  │  │  │  ├─ jats_xml_parser.py
│  │  │  │  └─ pdf_parser.py
│  │  │  ├─ section_detector.py
│  │  │  └─ sentence_splitter.py
│  │  ├─ mining/                  # PRD-06  P1 (stub)
│  │  │  ├─ pipeline.py
│  │  │  ├─ candidate_writer.py
│  │  │  ├─ stages/
│  │  │  │  ├─ __init__.py        # build_stages()
│  │  │  │  ├─ base.py
│  │  │  │  ├─ sentence_filter.py
│  │  │  │  ├─ move_classifier.py
│  │  │  │  ├─ epistemic_tagger.py
│  │  │  │  ├─ slot_abstractor.py
│  │  │  │  ├─ frame_normalizer.py
│  │  │  │  ├─ clusterer.py
│  │  │  │  └─ dedup_matcher.py
│  │  │  └─ models/               # wrapper cho model NLP (để trống + README)
│  │  └─ discipline/              # PRD-03  P2
│  │     ├─ base.py               # DisciplineSource
│  │     └─ null_source.py        # NullDisciplineSource
│  │
│  └─ workers/
│     ├─ runner.py                # vòng lặp polling bảng jobs
│     └─ handlers/
│        ├─ ingest_article.py
│        └─ mine_article.py
│
├─ admin-console/
│  └─ README.md                   # giữ chỗ: Review Queue, Pattern Explorer, API Keys
│
├─ seeds/
│  ├─ reference_enums.json
│  ├─ taxonomy.json
│  ├─ patterns.json
│  └─ load.py                     # python -m seeds.load
│
├─ eval/
│  └─ mining/
│     ├─ gold_sentences.jsonl     # rỗng, có 1 dòng mẫu đúng định dạng
│     └─ run_eval.py              # stub
│
└─ tests/
   ├─ conftest.py                 # DB test (schema riêng), client, fixture API key
   ├─ unit/
   │  ├─ policy/
   │  ├─ recommendation/
   │  │  ├─ gates/
   │  │  └─ scorers/
   │  ├─ validation/rules/
   │  └─ mining/stages/
   ├─ integration/
   │  └─ api/
   └─ acceptance/
      └─ test_at_01.py … test_at_12.py
```

---

## 4. Data model

Mọi bảng có `id` (UUID), `created_at`, `created_by` (FK `api_clients.id`, nullable với dữ liệu seed). Bảng nào sửa được thì có thêm `updated_at`.

### 4.1 Taxonomy

| Entity | Trường chính | Ghi chú |
|---|---|---|
| `TaxonomyRelease` | `version` (semver), `status` (draft/published), `published_at` | Mọi node taxonomy thuộc về một release |
| `Section` | `code`, `name`, `order`, `release_id` | Có cả section SLR (`TODO(owner)`: danh sách chính xác) |
| `Move` | `code`, `name`, `section_id` | |
| `Step` | `code`, `name`, `move_id` | |
| `Intent` | `code`, `name`, `step_id`, `description` | |
| `ArticleGenre` | `code`, `name` | Chiều độc lập, **không** nằm trong cây Section→Intent |

### 4.2 Pattern

| Entity | Trường chính | Ghi chú |
|---|---|---|
| `PhrasePattern` | `intent_id`, `status` (draft/in_review/approved/retired), `current_version_id` | Đối tượng định danh |
| `PatternVersion` | `pattern_id`, `version_no`, `canonical_frame`, `slots` (JSONB: tên + kiểu), `epistemic_strength`, `claim_type`, `change_note` | **Append-only**. Không có API UPDATE/DELETE |
| `PhraseVariant` | `pattern_version_id`, `text`, `register` | |
| `UsageConstraint` | `pattern_version_id`, `evidence_min`, `forbidden_contexts` (JSONB), `allowed_sections`, `allowed_genres` | |
| `EvidenceProvenance` | `pattern_version_id`, `source_type` (authored/mined), `article_id?`, `sentence_ids` (array), `license_id` | Bắt buộc với pattern sinh từ mining |
| `DisciplineAffinity` | `pattern_version_id`, `discipline_code`, `score` | Ở MVP để trống |
| `ReviewDecision` | `candidate_id` hoặc `pattern_version_id`, `round` (1/2), `decision`, `reviewer_id`, `comment` | HITL hai vòng |

### 4.3 Journal

| Entity | Trường chính | Ghi chú |
|---|---|---|
| `JournalProfile` | `name`, `issn`, `publisher`, `field`, `subfield`, `similar_journal_ids` | |
| `GuidelineRule` | `journal_id`, `rule_type`, `payload` (JSONB), `is_mandatory`, `active_from`, `active_to` | |
| `JournalFingerprint` | `journal_id`, `genre_id`, `vector` (pgvector), `computed_at` | Chỉ tạo bảng, chưa có logic |

### 4.4 Corpus và mining

| Entity | Trường chính | Ghi chú |
|---|---|---|
| `License` | `code`, `name`, `allows_mining`, `allows_display` | Phục vụ BR-10. Nạp từ `policies/licenses.yaml` |
| `ImportProfile` | `name`, `source` (`slr`), `filters` (JSONB, chỉ các field lọc của SLR `/works`), `artifact_kinds` (thứ tự ưu tiên), `batch_limit`, `is_active` | Curator sửa trên web. Job chụp lại `filters` vào payload |
| `Article` | `doi`, `title`, `journal_id?`, `genre_id?`, `license_id`, `blob_key`, `ingest_status` | |
| `ArticleSection` | `article_id`, `section_code?`, `heading`, `order` | |
| `Sentence` | `article_id`, `article_section_id`, `text`, `char_start`, `char_end`, `embedding` (pgvector, nullable) | |
| `Candidate` | `canonical_frame`, `slots`, `intent_id?`, `confidence`, `epistemic_strength?`, `source_sentence_ids`, `cluster_key?`, `matched_pattern_id?`, `status` (pending/accepted/rejected/merged) | Mining chỉ ghi vào bảng này |

### 4.5 Hệ thống

| Entity | Trường chính | Ghi chú |
|---|---|---|
| `ApiClient` | `name`, `key_hash`, `key_prefix`, `role`, `is_active` | Role: `admin`, `reviewer`, `curator`, `client` |
| `AuditEvent` | `actor_id`, `action`, `entity_type`, `entity_id`, `before` (JSONB), `after` (JSONB), `request_id` | Mọi thao tác ghi đều phải có |
| `Feedback` | `client_id`, `recommendation_id`, `pattern_version_id`, `signal` (accepted/rejected/edited), `payload` | |
| `Override` | `client_id`, `validation_id`, `rule_code`, `rationale` | Ghi đè kết quả validation phải có lý do |
| `RecommendationLog` | `request` (JSONB), `results` (JSONB: điểm từng scorer, gate bị loại, fallback_tier), `policy_versions` | Phục vụ giải thích kết quả và ablation |
| `Job` | `type`, `payload`, `status`, `attempts`, `locked_at`, `error` | |
| `RefEnum` | `group`, `code`, `label`, `order` | D9: claim_type, evidence_level, epistemic_strength… |

### 4.6 Thang Evidence (bản nháp, chỉ để scaffold chạy được)

```
evidence_level      : none < anecdotal < single_study < multiple_consistent < systematic_synthesis
epistemic_strength  : low < moderate < high < absolute
claim_type          : TODO(owner) — dùng tạm: descriptive, causal, comparative, generalization
```

Cả ba thang lưu trong `RefEnum` và có thứ tự (`order`). Code so sánh mức độ qua `order`, **không** so sánh chuỗi.

---

## 5. Interface lõi

Agent tạo đúng các chữ ký dưới đây (có thể thêm field, không đổi tên).

```python
# modules/recommendation/context.py
@dataclass(frozen=True)
class RecommendationContext:
    intent_code: str
    section_code: str
    genre_code: str | None
    journal_id: UUID | None
    claim_type: str | None
    evidence_level: str | None
    discipline_code: str | None
    client_id: UUID
    limit: int = 10

# modules/recommendation/gates/base.py
@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str | None = None

class HardGate(ABC):
    code: ClassVar[str]                      # "GATE_APPROVAL", ...
    @abstractmethod
    def check(self, pattern: PatternView, ctx: RecommendationContext) -> GateResult: ...

# modules/recommendation/scorers/base.py
class Scorer(ABC):
    key: ClassVar[str]                       # khớp key trong ranking_weights.yaml
    @abstractmethod
    def score(self, pattern: PatternView, ctx: RecommendationContext) -> float | None:
        """Trả về 0..1. None = không đủ dữ liệu → aggregator chuẩn hóa lại trọng số."""

# modules/validation/rules/base.py
class Severity(StrEnum): PASS = "pass"; WARN = "warn"; BLOCK = "block"

@dataclass(frozen=True)
class RuleResult:
    code: str                                # "V01".."V08"
    severity: Severity
    message: str
    span: tuple[int, int] | None = None

class ValidationRule(ABC):
    code: ClassVar[str]
    @abstractmethod
    def evaluate(self, text: str, ctx: ValidationContext) -> RuleResult: ...

# modules/mining/stages/base.py
class MiningStage(ABC):
    name: ClassVar[str]
    @abstractmethod
    def process(self, batch: list[MiningItem]) -> list[MiningItem]: ...

# modules/corpus/parsers/base.py
class DocumentParser(ABC):
    @abstractmethod
    def supports(self, mime_type: str) -> bool: ...
    @abstractmethod
    def parse(self, blob: bytes) -> ParsedDocument: ...   # sections + raw text

# modules/policy/evidence_policy.py
class EvidencePolicy(Protocol):
    version: str
    def max_strength(self, claim_type: str, evidence_level: str) -> str: ...
    def is_allowed(self, claim_type: str, evidence_level: str, strength: str) -> bool: ...

# modules/discipline/base.py
class DisciplineSource(Protocol):
    def classify_journal(self, journal: JournalProfile) -> list[tuple[str, float]] | None: ...
    # NullDisciplineSource luôn trả None → DisciplineScorer trả None
```

`PatternView` là DTO đọc-chỉ, gộp `PhrasePattern` + `PatternVersion` hiện hành + `UsageConstraint` + `EvidenceProvenance`, được nạp một lần cho mỗi request. Gate và scorer **không được truy vấn DB**. Ngoại lệ: `GuidelineGate`, đọc qua `GuidelinePolicy` đã cache theo `journal_id`.

---

## 6. Pipeline

### 6.1 Recommendation (`modules/recommendation/pipeline.py`)

```
load candidates (PatternView[]) theo intent/section/release
  → gates: chạy theo thứ tự build_gates(); pattern trượt gate nào thì ghi lại code của gate đó
  → nếu số còn lại < limit: fallback.py mở rộng phạm vi theo fallback_tiers.yaml
  → scorers: mỗi scorer cho điểm; aggregator tính tổng có trọng số + breakdown
  → diversifier: tránh các kết quả gần trùng (stub: giữ nguyên thứ tự)
  → ghi RecommendationLog
  → trả về: items[{pattern_version_id, score, breakdown, fallback_tier, explanations}]
```

Thứ tự gate (rẻ trước, đắt sau):

| Gate | Mã yêu cầu | Trạng thái ở scaffold |
|---|---|---|
| `ApprovalGate` | BR-01, AT-01 | **Cài thật**: `status == approved` |
| `RetiredGate` | — | **Cài thật**: loại pattern `retired` |
| `LicenseGate` | BR-10, AT-05 | **Cài thật**: pattern từ mining thì license phải có `allows_display` |
| `IntentSectionGate` | — | **Cài thật**: section nằm trong `allowed_sections` |
| `EvidenceGate` | AT-02, AT-07 | **Cài thật** qua `EvidencePolicy` |
| `GuidelineGate` | AT-06 | Stub: luôn pass, có `TODO` |

Scorer:

| Scorer | Trọng số mặc định | Trạng thái ở scaffold |
|---|---|---|
| `IntentScorer` | 0.25 | Khớp chính xác intent = 1.0 |
| `DisciplineScorer` | 0.20 | Trả `None` (dùng NullDisciplineSource) |
| `JournalGenreScorer` | 0.20 | Trả `None` (chưa có fingerprint) |
| `EvidenceScorer` | 0.15 | Stub: 1.0 nếu strength ≤ max cho phép |
| `LinguisticScorer` | 0.10 | Stub: 0.5 |
| `ProvenanceScorer` | 0.10 | Stub: authored = 1.0, mined = 0.7 |

Quy tắc của aggregator: bỏ các scorer trả `None`, chia lại trọng số các scorer còn lại cho tổng bằng 1, trả `breakdown` gồm cả các scorer bị bỏ (đánh dấu `null`). Bật/tắt một scorer bằng cách đặt trọng số `0` trong YAML, không sửa code.

### 6.2 Validation (`modules/validation/pipeline.py`)

Chạy mọi rule trong `build_rules()` rồi trả danh sách `RuleResult`. Severity tổng hợp = mức cao nhất. Severity của từng rule đọc từ `validation_rules.yaml`.

| File | Mã | Nội dung | Ở scaffold |
|---|---|---|---|
| `v01_*.py` | V01 | `TODO(owner)` | Stub, trả `PASS` |
| `v02_claim_evidence.py` | V02 | Claim mạnh hơn evidence | **Cài thật** qua `EvidencePolicy` + `EpistemicLexicon` |
| `v03_*.py` … `v07_*.py` | V03–V07 | `TODO(owner)` | Stub, trả `PASS` |
| `v08_*.py` | V08 | Journal có ít mẫu tham chiếu | Stub, trả `PASS` |

> Agent: các rule `TODO(owner)` đặt tên file theo dạng `v0X_todo.py` và ghi chú lấy tên thật từ PRD gốc.

**Ràng buộc:** `EvidenceGate` và `V02` phải gọi **cùng một** `EvidencePolicy`. Có một test khẳng định rằng với cùng input, hai bên cho kết quả nhất quán (mục 10).

### 6.3 Mining (`modules/mining/pipeline.py`) — chạy trong worker

**Mở rộng M2 được chủ sở hữu duyệt ngày 2026-10-31:** triển khai slot abstraction regex, protected spans, lexicon reporting/subject và keying bảo thủ, bật trong worker; candidate vẫn pending và qua hai vòng review. Kiểm thử bằng dữ liệu giả tự viết. Chưa đánh giá chất lượng trên dữ liệu thật; gold và evaluator chờ API bài báo. Từ phase 2, spaCy được dùng ở ingest sau lớp boundary rule-first qua `NLP_ENGINE` (mặc định `regex`); phase 3 cho phép `SentenceFilter` và `SlotAbstractor` đọc token feature hợp lệ với regex fallback. NER vẫn hoãn. Xem [ADR-0007](doc/adr/0007-rule-based-slot-abstraction.md) và [ADR-0010](doc/adr/0010-spacy-ingest-token-features.md).

**Mở rộng có giới hạn phase 4–6:** mining nhận token feature đã lưu để khớp ba nhóm construction tự viết trong YAML có version, với closed-world matching; reporting-verb path luôn được ưu tiên. Frame syntax giữ nguyên lead-in đã duyệt, verb group và connector `that`; nội dung ngoài slot nếu không thuộc policy đóng sẽ bị loại với reason count. Tense và modality là thuộc tính riêng; modality hiện chưa được lưu vào DB. Ownership của `we`, `our` và các cụm prior là cố định; `this`/`these`/`the only` cần cue trong câu trước cùng section và không có citation/prior blocker. Nhánh imperative có policy flag và chỉ được tính aggregate. CLI `phrase-stats` so sánh document frequency của masked frame giữa hai nhóm bài; đây là số mô tả, không phải kiểm định ý nghĩa thống kê. Không có parser PDF/JATS, NER, classifier tổng quát, endpoint thống kê hay lưu văn bản bài báo trong report. Danh sách cue provisional có `TODO(owner, FR-06.2)`.

**Cập nhật phase 7:** ownership được quyết định theo determiner và danh từ đầu với bốn tier trong `slot_abstraction.yaml`; `own_study_cues` đã bị loại bỏ. Epistemic tagging chạy sau reporting/construction extraction trên masked frame. `show` là neutral với strength `None`; `epistemic_status` chỉ tồn tại trong `MiningItem`, không được lưu hoặc đưa vào `cluster_key`. Tier, verb modifier và neutral verb lists còn provisional (`TODO(owner, FR-06.2)`). Xem ADR-0012.

```
job "ingest_article": corpus.ingest → license_check → parser → section_detector → sentence_boundary_resolver → sentence_features?
job "mine_article"  : Sentence[] → sentence_filter → move_classifier → slot_abstractor
                      → epistemic_tagger → frame_normalizer → clusterer → dedup_matcher
                      → candidate_writer (Candidate.status = pending)
```

- `license_check`: nếu `allows_mining = false` thì dừng job, ghi lý do. **Cài thật.**
- `sentence_boundary_resolver`: boundary rule-first dùng chung cho regex và spaCy, giữ nguyên `char_start/char_end`; `NLP_ENGINE=regex` là mặc định, `NLP_ENGINE=spacy` lưu feature token vào `sentences.nlp_features`. **Cài thật** (phase 2).
- `sentence_filter`: lọc theo độ dài, bỏ trích dẫn dạng `[12]`, `(Author, 2020)`, và khi có token feature thì kiểm tra finite verb/ROOT. **Cài thật**; ngưỡng syntax còn `TODO(owner, FR-07)`.
- `slot_abstractor`: dùng dependency ROOT/subject/that-clause khi có token feature hợp lệ; frame giữ cả câu bằng các slot có kiểu, verb group và lead-in đã duyệt. Nội dung ngoài policy đóng bị từ chối có reason count; dữ liệu token thiếu hoặc hỏng fallback về regex. **Cài thật (phase 3–6); quyết định ở ADR-0012**.
- `candidate_writer`: **bắt buộc** ghi `source_sentence_ids`. Mining **không bao giờ** ghi vào `phrase_patterns` / `pattern_versions`.

Duyệt candidate (`modules/patterns/review.py`): chỉ con đường này mới tạo `PatternVersion` từ `Candidate`, sau khi đủ 2 vòng `ReviewDecision` approve.

---

## 7. API `/v1`

Định dạng lỗi chung: `{"error": {"code": str, "message": str, "details": object | null}, "request_id": str}`.
Mọi response có header `X-Request-ID`. Mọi thao tác ghi đều ghi `AuditEvent`.

| Method | Path | Role | Ở scaffold |
|---|---|---|---|
| GET | `/v1/health` | public | 200 + kiểm tra kết nối DB |
| GET | `/v1/taxonomy` | client+ | Trả cây của release đang published |
| GET | `/v1/taxonomy/releases` | client+ | List |
| GET | `/v1/patterns` | client+ | List có lọc theo intent/section/status, phân trang |
| GET | `/v1/patterns/{id}` | client+ | Chi tiết + version hiện hành |
| GET | `/v1/patterns/{id}/versions` | client+ | Lịch sử version |
| POST | `/v1/patterns` | curator+ | Tạo pattern draft (version 1) |
| POST | `/v1/patterns/{id}/versions` | curator+ | Thêm version mới (append-only) |
| POST | `/v1/patterns/{id}/retire` | admin | |
| POST | `/v1/recommendations` | client+ | **Chạy pipeline thật** (mục 6.1) |
| POST | `/v1/validate` | client+ | **Chạy pipeline thật** (mục 6.2) |
| POST | `/v1/feedback` | client+ | Lưu Feedback |
| POST | `/v1/overrides` | client+ | Lưu Override, bắt buộc có `rationale` |
| GET | `/v1/journals` / `/v1/journals/{id}` | client+ | |
| POST | `/v1/journals/{id}/guidelines` | curator+ | |
| GET | `/v1/admin/review-queue` | reviewer+ | List Candidate pending |
| POST | `/v1/admin/review-queue/{candidate_id}/decisions` | reviewer+ | Ghi ReviewDecision |
| POST | `/v1/admin/corpus/articles` | curator+ | Upload, tạo job ingest → trả `202` |
| POST | `/v1/admin/corpus/articles/{id}/mine` | curator+ | Tạo job mine → trả `202` |
| POST | `/v1/admin/corpus/imports` | curator+ | Tạo job `import_articles` từ nguồn ngoài, nhận `profile_id` (bộ lọc được chụp vào payload) → `202`; `409` khi `ARTICLE_SOURCE=null` |
| GET/POST | `/v1/admin/corpus/import-profiles` | curator+ | List / tạo profile bộ lọc |
| GET/PATCH | `/v1/admin/corpus/import-profiles/{id}` | curator+ | Xem / sửa profile; bộ lọc được validate theo danh sách field cho phép |
| GET | `/v1/admin/corpus/sources/slr/taxonomy` | curator+ | Gọi qua `GET /taxonomy` của SLR (`level`, `parentId`, `cursor`) để giao diện chọn ngành |
| GET | `/v1/admin/jobs/{id}` | curator+ | Trạng thái job |
| POST/GET/DELETE | `/v1/admin/api-keys` | admin | Tạo key (chỉ trả plaintext **một lần**), list, thu hồi |
| POST | `/v1/admin/releases/{id}/publish` | admin | `501` |

Thứ bậc role: `admin > curator > reviewer > client`. `curator+` nghĩa là curator và admin. `reviewer` **không** có quyền curator.

Request/response chi tiết của `/v1/recommendations`:

```jsonc
// request
{ "intent": "INTRO_GAP_INDICATE", "section": "INTRO", "genre": "RESEARCH_ARTICLE",
  "journal_id": null, "claim_type": "causal", "evidence_level": "single_study",
  "discipline": null, "limit": 10 }
// response
{ "items": [ { "pattern_version_id": "…", "canonical_frame": "…", "score": 0.82,
               "breakdown": { "intent": 1.0, "discipline": null, "journal_genre": null,
                              "evidence": 1.0, "linguistic": 0.5, "provenance": 1.0 },
               "fallback_tier": "generic_genre", "explanations": ["…"] } ],
  "excluded": { "GATE_EVIDENCE": 3, "GATE_APPROVAL": 5 },
  "policy_versions": { "ranking_weights": "0.1.0", "evidence_matrix": "0.1.0" },
  "recommendation_id": "…" }
```

---

## 8. File policy (nội dung mẫu)

Mỗi file có `version` ở đầu. `loader.py` kiểm tra schema bằng Pydantic khi app khởi động. Sai schema thì app **không** khởi động.

```yaml
# ranking_weights.yaml
version: 0.1.0
weights:
  intent: 0.25
  discipline: 0.20
  journal_genre: 0.20
  evidence: 0.15
  linguistic: 0.10
  provenance: 0.10
```

```yaml
# fallback_tiers.yaml
version: 0.1.0
tiers: [journal_genre, similar_journal_genre, subfield_genre, field_genre, generic_genre]
```

```yaml
# evidence_matrix.yaml  — BẢN NHÁP, TODO(owner) duyệt
version: 0.1.0
default_max_strength: low
matrix:            # claim_type → evidence_level → max epistemic_strength
  descriptive:
    none: low
    anecdotal: moderate
    single_study: high
    multiple_consistent: high
    systematic_synthesis: high
  causal:
    none: low
    anecdotal: low
    single_study: moderate
    multiple_consistent: high
    systematic_synthesis: high
  # comparative, generalization: TODO(owner)
```

```yaml
# validation_rules.yaml
version: 0.1.0
rules:
  V01: { enabled: true, severity: warn }
  V02: { enabled: true, severity: block }
  # V03..V08: enabled: true, severity: warn — TODO(owner)
```

```yaml
# lexicon/epistemic_markers.yaml — BẢN NHÁP
version: 0.1.0
markers:
  low:      [may, might, could, possibly, appears to]
  moderate: [suggest, indicate, is likely]
  high:     [demonstrate, confirm, establish]
  absolute: [prove, establish beyond doubt, always]
```

---

## 9. Seed

`python -m seeds.load` nạp theo thứ tự `reference_enums → taxonomy → patterns`. Chạy lại nhiều lần không sinh dữ liệu trùng (idempotent: upsert theo `code`).

- `reference_enums.json`: các thang ở mục 4.6, role.
- License nạp từ `policies/licenses.yaml`: `CC0`, `CC-BY`, `CC-BY-SA` cho phép mining + display; các biến thể NC/ND tạm chặn với `TODO(owner)`; `PROPRIETARY` không cho cả hai.
- `taxonomy.json`: 1 release `0.1.0` published, gồm 2 section (`INTRO`, `DISCUSSION`), mỗi section 1–2 move, mỗi move 1 step, mỗi step 1–2 intent. `TODO(owner)`: thay bằng taxonomy thật.
- `patterns.json`: khoảng 6 pattern authored để phủ test, gồm:
  - 1 pattern `approved`, strength `low`
  - 1 pattern `approved`, strength `high`
  - 1 pattern `draft` (phải bị ApprovalGate loại)
  - 1 pattern `retired`
  - 1 pattern dạng mined, license `PROPRIETARY` (phải bị LicenseGate loại)
  - 1 pattern `approved` có `allowed_sections` không chứa `INTRO`

Seed chỉ dùng câu mẫu học thuật chung chung do nhóm tự viết, **không** chép câu từ bài báo có bản quyền.

---

## 10. Test

### Phải pass

- `unit/policy`: loader từ chối YAML sai schema; `EvidencePolicy.max_strength` đúng với ma trận mẫu.
- `unit/recommendation/gates`: mỗi gate được "cài thật" có ít nhất 1 case pass và 1 case fail.
- `unit/recommendation/scorers/test_aggregator.py`: khi có scorer trả `None` thì trọng số được chuẩn hóa lại, tổng vẫn bằng 1; trọng số `0` thì scorer bị bỏ qua.
- `unit/validation/rules/test_v02.py`: "This proves …" với `single_study` → `BLOCK`.
- `unit/test_policy_consistency.py`: với cùng `(claim_type, evidence_level, strength)`, `EvidenceGate` trượt ⇔ `V02` trả `BLOCK`.
- `unit/mining/stages`: `sentence_filter` bỏ được trích dẫn; `candidate_writer` báo lỗi khi thiếu `source_sentence_ids`.
- `integration/api`:
  - `/v1/health` = 200
  - Thiếu API key → 401; sai role → 403
  - `/v1/recommendations` với seed: không trả pattern draft/retired/proprietary
  - Không có route nào UPDATE/DELETE `pattern_versions`
  - Thao tác ghi tạo ra `AuditEvent`

### Giữ chỗ (skip)

`tests/acceptance/test_at_01.py` … `test_at_12.py`, mỗi file có dạng:

```python
import pytest

@pytest.mark.skip(reason="AT-05 — chưa cài đặt")
def test_at_05_license_blocks_display():
    """TODO(owner): chép tiêu chí chấp nhận AT-05 từ PRD gốc vào đây."""
```

Đã biết: AT-01 (chỉ gợi ý pattern approved), AT-02 / AT-07 (claim–evidence), AT-05 (license), AT-06 (guideline journal), AT-12 (phân quyền). Với các AT khác, phần docstring để `TODO(owner)`. Test nào đã được bao phủ bởi integration test ở trên thì **bỏ skip** và gọi lại cùng logic đó.

---

## 11. Công cụ dev

`Makefile`:

| Lệnh | Việc |
|---|---|
| `make up` / `make down` | Bật/tắt Postgres (docker compose) |
| `make install` | `uv sync` |
| `make migrate` | `alembic upgrade head` |
| `make seed` | `python -m seeds.load` |
| `make run` | `uvicorn app.main:app --reload` |
| `make worker` | `python -m app.workers.runner` |
| `make test` | `pytest` |
| `make lint` | `ruff check . && ruff format --check . && mypy app` |
| `make bootstrap-key` | Tạo API key admin đầu tiên, in ra màn hình |

`docker-compose.yml`: image `pgvector/pgvector:pg16`, cổng 5432, volume có tên. `.env.example` chứa `DATABASE_URL`, `BLOB_DIR`, `LOG_LEVEL`.

Migration ban đầu phải chạy `CREATE EXTENSION IF NOT EXISTS vector`.

---

## 12. Definition of Done

Từ repo sạch, chạy lần lượt các lệnh sau đều thành công:

```
make up && make install && make migrate && make seed && make bootstrap-key
make lint
make test            # mọi test ở mục 10 pass, AT chưa làm ở trạng thái skip
make run             # mở /docs thấy đủ endpoint ở mục 7
```

Và:

- [ ] `POST /v1/recommendations` với seed trả kết quả có `breakdown` và `fallback_tier`; `discipline` và `journal_genre` là `null`.
- [ ] `POST /v1/validate` với câu chứa "prove" và `evidence_level=single_study` trả `V02: block`.
- [ ] Tạo `ImportProfile`, gọi `POST /v1/admin/corpus/imports` với `profile_id` trên SLR giả lập → bài có license cho phép được nhập, bài thiếu/không rõ license bị bỏ qua và không tải nội dung.
- [ ] Màn hình Import từ SLR lưu được profile, bấm "Lấy bài báo" tạo job và hiển thị tiến độ.
- [ ] Upload 1 file `.txt` qua `/v1/admin/corpus/articles` rồi chạy mine → worker tạo ít nhất 1 `Candidate` có `source_sentence_ids` (các stage stub giữ nguyên câu).
- [ ] Không file nào trong `app/` chứa trọng số, ngưỡng hay danh sách từ vựng hard-code; tất cả nằm trong `app/policies/`.
- [ ] Mỗi stub đều có `TODO` kèm mã yêu cầu.
- [ ] `README.md` mô tả cách chạy, cấu trúc module, và bảng truy vết (Phụ lục A).

---

## 13. Quy ước code

- Theo từng module: `router (api/v1) → service → repository → model`. Router không gọi repository trực tiếp.
- Gate, scorer, rule, stage là các class thuần, **không phụ thuộc** FastAPI hay SQLAlchemy, để unit test được mà không cần DB.
- Phụ thuộc truyền qua constructor (policy, source). Không dùng biến global.
- Mọi class gate/scorer/rule/stage được đăng ký qua hàm `build_*()` trong `__init__.py` của thư mục tương ứng.
- Tên bảng dạng snake_case số nhiều; tên class dạng PascalCase số ít.
- Thời gian lưu UTC, kiểu `timestamptz`.
- Không ghi log nội dung API key hay toàn văn bài báo.

---

## 14. Để sau scaffold (không làm bây giờ)

- NER khoa học, LLM, production move/intent/epistemic classifiers và clustering bằng embedding. Slot abstraction theo luật có phạm vi M2 giới hạn theo mục 6.3; chưa được xem là đã triển khai hoặc áp dụng.
- Journal fingerprint, `JournalGenreScorer` thật.
- Diversifier thật (FR-07.6).

**Ngoại lệ M2 được owner duyệt 2026-11-01:** gold dev từ câu SLR được lưu dưới dạng tham chiếu/hash trong `gold_items`; AI nháp và một người duyệt cuối qua UI. Groq key chỉ ở `.env` local, không có UI/API lưu key. Chưa có đánh giá production. LLM bên thứ ba chỉ bật local/test cho tới quyết định quyền xử lý theo `TODO(owner, BR-10)`.
- Các màn hình admin console còn lại.
- Lịch tự động chạy import theo profile.
- Quy trình publish taxonomy release.
- Mẫu gold dev 300 câu từ SLR đã được tạo; chưa có AI draft hay nhãn người duyệt. Theo quyết định owner, AI sẽ gán nhãn mọi item và một người duyệt cuối toàn bộ nhãn. Quy trình dev này không đáp ứng validation hai editor của FR-06.6. Evaluator, tuning và đánh giá chất lượng chờ nhãn người duyệt; kiểm thử mock không chứng minh chất lượng production.

---

## Phụ lục A — Bảng truy vết (agent đưa vào README)

| Yêu cầu | Module / file | Test |
|---|---|---|
| BR-01 chỉ dùng pattern approved | `recommendation/gates/approval_gate.py`, `patterns/review.py` | `unit/.../test_approval_gate.py`, AT-01 |
| BR-10 license | `recommendation/gates/license_gate.py`, `corpus/license_check.py`, `policies/licenses.yaml` | AT-05 |
| Import SLR theo profile | `corpus/sources/slr_source.py`, `corpus/import_profiles.py`, `apps/web/src/features/slr-import` | `unit/corpus/test_slr_source.py`, `integration/corpus/test_import_profiles.py` |
| Claim ≤ evidence | `policy/evidence_policy.py`, `gates/evidence_gate.py`, `validation/rules/v02_*.py` | `test_policy_consistency.py`, AT-02, AT-07 |
| Guideline journal | `policy/guideline_policy.py`, `gates/guideline_gate.py` | AT-06 |
| Ranking có trọng số | `scorers/*`, `aggregator.py`, `policies/ranking_weights.yaml` | `test_aggregator.py` |
| Fallback | `recommendation/fallback.py`, `policies/fallback_tiers.yaml` | TODO |
| HITL 2 vòng | `patterns/review.py`, `api/v1/admin/review_queue.py` | TODO |
| RBAC / audit | `core/auth.py`, `core/audit.py` | `integration/api`, AT-12 |
| Mining → Candidate | `mining/*`, `workers/handlers/mine_article.py` | `unit/mining/stages` |
| Discipline (P2) | `discipline/null_source.py` | — |


**Cập nhật phase 8–9.1:** `author_action` dùng danh sách adjunct đóng, có phiên bản: preposition
được giữ literal và object thành slot; purpose `advcl`/`xcomp` chỉ được chấp nhận khi có marker
`to`. Frame thay đúng span slot trên câu nguồn, giữ nguyên phần còn lại; adjunct không được
đăng ký bị đếm là `unlisted_adjunct`, quá hai adjunct là `too_many_adjuncts`. Phase 9.1 chỉ thêm
chủ ngữ chủ động literal `this paper`, `this study`, `this article`; chủ ngữ khác bị từ chối với
reason riêng. Không thêm anchor hoặc adjunct. Passive, chủ ngữ `it`, copula `be` và dạng adjunct
chưa đăng ký vẫn ngoài phạm vi. Anchor và adjunct lists còn provisional
(`TODO(owner, FR-06.2)`). Xem ADR-0013.

**Cập nhật hybrid slot engine (Phase 0–6, 2026-11-06):** bổ sung Tier 2 mở giới hạn trong
ADR-0014 với tám family dependency (`discourse_gap` đang tắt), Purity Gate và `MINING_HYBRID_ENABLED` (mặc định tắt). Tier 1
giữ nguyên quyền quyết định; Tier 2 chỉ chạy sau hai lần không khớp và khi token spaCy đã lưu tồn
tại. Candidate tiếp tục qua hàng đợi pending hiện tại. Chưa bật switch trước khi đo coverage trên
blob có quyền mining và review volume; xem ADR-0014.

## Job operations extension (2026-11-05)

The user approved bounded PostgreSQL retries and the subsequent operational workflow:
curator/admin manual retry, per-attempt error history, live stage progress and in-app
repeated-failure alerts. See ADR-0013 and ADR-0014. This adds `/jobs` and the documented
admin job APIs; it does not introduce Redis/Celery, bypass license checks, change
Extract/Publication review rules or automatically send external notifications.

## Metric & Measurement extension (2026-11-09)

Task 3 adds a separate, self-authored catalog of metrics, measurement methods and protocols,
answering "how to measure" alongside the phrase core's "how to write". It is off by default
(`MEASUREMENT_ENABLED`). It adds `/v1/measurements` read routes, curator import and slot-link
review under `/v1/admin/measurements`, and a `/measurements` page. Approved slot links only
suggest values for a pattern slot (FR-07.5/AT-08: never auto-filled). While enabled,
`/v1/validate` adds report-only `metric_warnings` (FR-08.2) without changing severity. It does
not change ranking, render or pack export, and it adds no NLP extractor. `measurement-purge`
removes the catalog. See ADR-0015.
