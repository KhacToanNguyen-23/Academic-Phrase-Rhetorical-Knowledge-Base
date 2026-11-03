# AP-RKB — Evidence Contract v0.1 (bản đề xuất)

> **Trạng thái:** ĐỀ XUẤT CHƯA DUYỆT; không phải nguồn policy runtime. Backend MVP hiện dùng `apps/backend/src/aprkb/policies/evidence_matrix.yaml`, `lexicon/epistemic_markers.yaml` và thứ tự `RefEnum` theo `SCAFFOLD_PRD.md` §4.6/§8. Nội dung dưới đây chỉ là phương án mở rộng để nhóm xem xét.
> **Mục đích:** quy định **một câu khẳng định được phép mạnh đến đâu** so với **bằng chứng mà người viết có**.
> **Dự kiến nếu được duyệt:** `EvidenceGate` (lọc pattern khi gợi ý) và rule `V02` (kiểm câu người viết) sẽ cùng đọc `EvidencePolicy`. Hiện backend nạp policy runtime từ các YAML trong `apps/backend/src/aprkb/policies/`.
> **Đề xuất đầu ra nếu được duyệt:** các file policy runtime nói trên. Hiện các bảng/mặc định trong tài liệu này chưa được áp dụng tự động.

---

## 1. Nguyên tắc

| # | Nguyên tắc |
|---|---|
| P1 | Độ mạnh của câu **không được vượt** độ mạnh mà bằng chứng cho phép (chống *overclaim*). |
| P2 | Câu yếu hơn mức cho phép thì **không sai**, chỉ được gợi ý nhẹ (*underclaim*), không bao giờ bị chặn. |
| P3 | Mức `absolute` (prove, always, beyond doubt…) **không được phép** với bất kỳ khẳng định thực nghiệm nào. |
| P4 | Người viết (client) **khai báo** `claim_type` và `evidence_level`. AP-RKB không tự suy ra mức bằng chứng ở MVP. |
| P5 | Khẳng định thuộc về tài liệu được trích dẫn ("Smith (2020) showed…") chịu trách nhiệm theo nguồn gốc, **nằm ngoài** phạm vi kiểm tra này (mục 7). |
| P6 | Gate và validator phải cho kết quả **nhất quán**: pattern bị gate loại ⇔ câu tương ứng không đạt `pass` ở V02. |

**Căn cứ học thuật** (để bảo vệ thiết kế):
- Hyland, K. (1998). *Hedging in Scientific Research Articles*. John Benjamins. Đây là cơ sở cho phân loại hedge/booster ở mục 4.
- Hyland, K. (2005). *Metadiscourse*. Continuum. Cơ sở cho khung hedges / boosters / attitude markers.
- GRADE Working Group (Guyatt và cộng sự, 2008, *BMJ*). Cơ sở cho thang chất lượng bằng chứng ở mục 3 và quan điểm "bằng chứng quan sát yếu hơn thực nghiệm khi khẳng định nhân quả".

---

## 2. `claim_type` — loại khẳng định

| Code | Tên | Định nghĩa | Ví dụ | Dấu hiệu nhận biết |
|---|---|---|---|---|
| `descriptive` | Mô tả | Báo cáo điều đã quan sát **trong phạm vi dữ liệu** của nghiên cứu | "Accuracy increased from 71% to 84% on the test set." | Số liệu, thì quá khứ, có phạm vi rõ |
| `associative` | Tương quan | Hai đại lượng **đi cùng nhau**, không khẳng định nguyên nhân | "Higher screen time is associated with lower sleep quality." | associated with, correlated with, linked to |
| `causal` | Nhân quả | X **gây ra / dẫn tới** Y | "The intervention reduces dropout rates." | cause, lead to, result in, reduce, improve, affect, due to |
| `comparative` | So sánh | X hơn/kém Y **trong điều kiện đã nêu** | "Our model outperforms BERT-base on GLUE." | outperform, superior to, better than |
| `generalization` | Khái quát | Mở rộng kết luận **ra ngoài mẫu** đã nghiên cứu | "Transformer models generally handle long contexts poorly." | generally, in general, typically, most, all, across |
| `normative` | Khuyến nghị | Đề xuất hành động cho người đọc / người thực hành | "Practitioners should adopt early screening." | should, must, recommend, need to |

**Quy tắc phân loại khi lẫn:** chọn loại **khắt khe hơn**. Ví dụ "Our model outperforms baselines across domains" vừa là comparative vừa là generalization, nên tính là `generalization`.

> **Câu hỏi mở Q1:** có cần thêm `novelty` ("This is the first study to…") không? Khẳng định loại này phụ thuộc vào độ bao phủ khi tổng quan tài liệu chứ không phụ thuộc dữ liệu thực nghiệm, nên không hợp với ma trận ở mục 5. Đề xuất: để ngoài phạm vi v0.1.

---

## 3. `evidence_level` — mức bằng chứng

Thang có thứ tự, từ yếu đến mạnh:

| Thứ tự | Code | Tiêu chí | Ví dụ |
|---|---|---|---|
| 0 | `none` | Không có dữ liệu hay trích dẫn hỗ trợ; là giả thuyết hoặc suy đoán | Đoạn Introduction nêu giả thuyết |
| 1 | `anecdotal` | Quan sát lẻ, case study, pilot nhỏ, ý kiến chuyên gia | 1 case, pilot n < 30, phỏng vấn ít người |
| 2 | `single_study` | **Một** nghiên cứu có thiết kế đầy đủ (thường là chính kết quả của bài) | Một thí nghiệm, một khảo sát |
| 3 | `multiple_consistent` | **≥ 2** nghiên cứu **độc lập**, kết quả **cùng chiều** | Kết quả của bài + ≥ 1 nghiên cứu trích dẫn khớp |
| 4 | `systematic_synthesis` | Systematic review hoặc meta-analysis | SLR, meta-analysis |

**Thuộc tính bổ sung tùy chọn `study_design`** (theo tinh thần GRADE), chỉ ảnh hưởng `causal`:

| Code | Ý nghĩa |
|---|---|
| `experimental` | Có can thiệp + đối chứng (RCT, A/B test, ablation có kiểm soát) |
| `observational` | Quan sát, khảo sát, dữ liệu có sẵn |
| `unknown` | Không khai báo (mặc định) |

**Modifier M1:** `claim_type = causal` và `study_design = observational` → mức cho phép **hạ 1 bậc** (tối thiểu `low`).

> **Câu hỏi mở Q2:** ngưỡng "pilot n < 30" chỉ là quy ước tạm. Mỗi ngành có chuẩn khác nhau. Có nên để ngưỡng này cho client tự khai, không ghi cứng không?

---

## 4. `epistemic_strength` — độ mạnh của câu

### 4.1 Thang

| Thứ tự | Code | Ý nghĩa | Từ ngữ đặc trưng |
|---|---|---|---|
| 0 | `low` | Thăm dò, có thể đúng | may, might, could, possibly, perhaps, it is possible that, we speculate, we hypothesize, tentatively |
| 1 | `moderate` | Có cơ sở nhưng thận trọng | suggest, indicate, appear to, seem to, likely, tend to, point to, is consistent with, provide support for |
| 2 | `high` | Khẳng định dựa trên dữ liệu | show, demonstrate, find/found, reveal, confirm, establish, **câu khẳng định trần ở thì hiện tại** ("X reduces Y") |
| 3 | `absolute` | Chắc chắn tuyệt đối | prove, undoubtedly, conclusively, definitively, beyond doubt, it is certain that, always, never, all (không có phạm vi) |

Từ ngữ cho `normative` dùng thang riêng nhưng cùng 4 bậc:

| Bậc | Từ ngữ |
|---|---|
| `low` | could consider, may wish to, one option is |
| `moderate` | should consider, it may be beneficial to |
| `high` | should, we recommend |
| `absolute` | must, it is essential that, have to |

### 4.2 Cách tính độ mạnh của một câu

Áp dụng tuần tự:

1. **Mức gốc** = mức của *động từ khẳng định chính* (suggest → moderate, show → high…). Câu không có marker nào nhưng là câu khẳng định trần thì gốc = `high`.
2. **Hedge** đi kèm (may, might, possibly, likely…) → **hạ 1 bậc**, mỗi câu hạ tối đa 1 bậc. Ví dụ "may suggest": moderate → low.
3. **Booster** đi kèm (clearly, strongly, definitely, convincingly…) → **nâng 1 bậc**. Ví dụ "clearly show": high → absolute.
4. Có bất kỳ marker `absolute` nào → kết quả = `absolute`, bất kể các bước trên.
5. Kẹp kết quả vào khoảng `low`…`absolute`.

| Câu | Gốc | Điều chỉnh | Kết quả |
|---|---|---|---|
| "The results suggest that X improves Y." | moderate | — | moderate |
| "X may improve Y." | high (khẳng định trần "improve") | hedge −1 | moderate |
| "These findings may suggest a link." | moderate | hedge −1 | low |
| "We clearly show that X improves Y." | high | booster +1 | absolute |
| "This proves that X causes Y." | — | marker absolute | absolute |

> Với pattern trong kho, `epistemic_strength` do **curator gán tay** khi soạn hoặc duyệt. Quy tắc 4.2 chỉ dùng để: (a) kiểm câu người viết trong V02; (b) gợi ý giá trị cho curator ở bước `epistemic_tagger` của mining.

---

## 5. Ma trận: mức tối đa được phép

Giá trị trong ô = `epistemic_strength` **tối đa** được dùng.

| claim_type ↓ / evidence → | `none` | `anecdotal` | `single_study` | `multiple_consistent` | `systematic_synthesis` |
|---|---|---|---|---|---|
| `descriptive` | low | **high** | high | high | high |
| `associative` | low | low | moderate | high | high |
| `causal` | low | low | moderate ¹ | high ¹ | high ¹ |
| `comparative` | low | low | high ² | high | high |
| `generalization` | low | low | low | moderate | high |
| `normative` | low | low | low | moderate | high |

¹ Áp dụng modifier M1: nếu `study_design = observational` thì hạ 1 bậc (single → low, multiple → moderate, synthesis → moderate).
² Chỉ khi câu **có nêu phạm vi** (dataset, điều kiện). Không có phạm vi thì câu thuộc `generalization`.

### Lý do từng hàng

- **descriptive**: mô tả đúng dữ liệu của chính mình là sự thật trong phạm vi đó, nên ngay cả case study cũng được viết `high` ("In this case, the patient recovered"). Không có dữ liệu thì không có gì để mô tả, chỉ còn suy đoán, nên `none` → `low`.
- **associative**: một nghiên cứu cho thấy tương quan vẫn có thể là ngẫu nhiên hoặc do nhiễu, nên chỉ được "suggest/indicate". Từ hai nghiên cứu độc lập cùng chiều trở lên mới được "show".
- **causal**: đây là hàng khắt khe nhất về mặt logic. Một nghiên cứu, kể cả thực nghiệm, chỉ cho phép `moderate`. Bằng chứng quan sát bị hạ thêm 1 bậc, vì quan sát không loại trừ được biến gây nhiễu (theo GRADE).
- **comparative**: trong CS và kỹ thuật, "outperforms on dataset D" là kết quả đo được trực tiếp, tương đương `descriptive` nếu có phạm vi.
- **generalization**: mở rộng ra ngoài mẫu cần nhiều nghiên cứu. Một nghiên cứu chỉ được viết thăm dò ("may generalize").
- **normative**: khuyến nghị hành động có hậu quả thực tế, nên yêu cầu bằng chứng giống `generalization`.

### Mặc định khi thiếu thông tin

| Tình huống | Xử lý (đề xuất) |
|---|---|
| Thiếu `evidence_level` | Mức cho phép = `moderate` (`unknown_evidence_cap`); V02 trả thêm `warn` "chưa khai báo bằng chứng" |
| Thiếu `claim_type` | Dùng hàng `associative` (`unknown_claim_type_row`) |
| Thiếu `study_design` | Coi là `unknown`, không áp dụng M1 |

> **Câu hỏi mở Q3:** thiếu `evidence_level` thì nên cho mức `moderate` (thoáng) hay `low` (chặt)? Chọn `low` thì an toàn hơn, nhưng sẽ gợi ý quá ít pattern và người dùng bị cảnh báo liên tục.

---

## 6. Mức nghiêm trọng (severity) trong V02

Đặt `gap = order(strength của câu) − order(max cho phép)`.

| Điều kiện | Severity | Thông điệp gợi ý |
|---|---|---|
| strength = `absolute` (với claim thực nghiệm) | `block` | "Không dùng khẳng định tuyệt đối cho kết quả thực nghiệm." |
| `gap ≥ 2` | `block` | "Câu mạnh hơn nhiều so với bằng chứng ({evidence_level})." |
| `gap = 1` | `warn` | "Câu hơi mạnh so với bằng chứng; cân nhắc dùng '{gợi ý}'." |
| `gap ≤ 0` | `pass` | — |
| `gap ≤ −2` | `pass` + `info` | "Bằng chứng cho phép viết mạnh hơn." (P2) |

Với **EvidenceGate**: pattern có `gap > 0` đều bị loại. Như vậy P6 được hiểu là: **gate loại ⇔ V02 trả `warn` hoặc `block`**.

> ⚠ Điều này khác với một dòng trong `SCAFFOLD_PRD.md` mục 10 ("EvidenceGate trượt ⇔ V02 trả BLOCK"). Khi tài liệu này được duyệt, dòng đó sửa thành "⇔ V02 ≠ PASS".

---

## 7. Ngoài phạm vi v0.1

| Trường hợp | Ví dụ | Xử lý v0.1 |
|---|---|---|
| Khẳng định quy cho nguồn trích dẫn | "Smith (2020) demonstrated that…" | Bỏ qua V02 nếu câu có chủ ngữ là tác giả hoặc trích dẫn đứng trước động từ |
| Phủ định | "This does not prove that…" | Bỏ qua. Câu có `not/no/never` đứng trước marker thì không tính marker đó |
| Câu điều kiện | "If confirmed, this would show…" | Coi như có hedge (−1) |
| Định nghĩa, toán học | "A graph is connected if…", "Theorem 1 proves…" | Không thuộc claim thực nghiệm. Client không gửi `claim_type` cho các câu này |
| Lượng từ | "most", "all", "few" | Chỉ dùng để nhận diện `generalization`, không đổi strength (trừ `all`/`always`/`never` = absolute) |
| `novelty` | "first to…" | Xem Q1 |

---

## 8. File cấu hình sinh ra

```yaml
# app/policies/evidence_matrix.yaml
version: 0.1.0
scales:
  evidence_level: [none, anecdotal, single_study, multiple_consistent, systematic_synthesis]
  epistemic_strength: [low, moderate, high, absolute]
  study_design: [experimental, observational, unknown]
claim_types: [descriptive, associative, causal, comparative, generalization, normative]

defaults:
  unknown_evidence_cap: moderate          # Q3
  unknown_claim_type_row: associative
  absolute_allowed: false                 # P3

matrix:
  descriptive:    { none: low, anecdotal: high, single_study: high,     multiple_consistent: high,     systematic_synthesis: high }
  associative:    { none: low, anecdotal: low,  single_study: moderate, multiple_consistent: high,     systematic_synthesis: high }
  causal:         { none: low, anecdotal: low,  single_study: moderate, multiple_consistent: high,     systematic_synthesis: high }
  comparative:    { none: low, anecdotal: low,  single_study: high,     multiple_consistent: high,     systematic_synthesis: high }
  generalization: { none: low, anecdotal: low,  single_study: low,      multiple_consistent: moderate, systematic_synthesis: high }
  normative:      { none: low, anecdotal: low,  single_study: low,      multiple_consistent: moderate, systematic_synthesis: high }

modifiers:
  - id: M1
    when: { claim_type: causal, study_design: observational }
    effect: { downgrade: 1, floor: low }

severity:                                  # dùng bởi V02
  absolute: block
  gap_ge_2: block
  gap_eq_1: warn
  underclaim_gap_le: -2                    # phát info
```

```yaml
# app/policies/lexicon/epistemic_markers.yaml
version: 0.1.0
base_verbs:
  low:      [speculate, hypothesize]
  moderate: [suggest, indicate, "appear to", "seem to", "tend to", "point to", "is consistent with", "provide support for"]
  high:     [show, demonstrate, find, found, reveal, confirm, establish]
  absolute: [prove]
hedges:      [may, might, could, possibly, perhaps, likely, probably, "it is possible that", tentatively]   # −1
boosters:    [clearly, strongly, definitely, convincingly, undeniably]                                     # +1
absolute_markers: [undoubtedly, conclusively, definitively, "beyond doubt", "it is certain that", always, never]
normative:
  low:      ["could consider", "may wish to"]
  moderate: ["should consider", "it may be beneficial to"]
  high:     [should, recommend]
  absolute: [must, "it is essential that", "have to"]
negators:    [not, no, never, "fail to", "does not"]
default_bare_assertion: high
```

---

## 9. Bộ ví dụ kiểm thử

Dùng làm test case cho `EvidencePolicy`, `EvidenceGate` và `V02`.

| # | Câu | claim_type | evidence | design | strength | max | Kết quả V02 |
|---|---|---|---|---|---|---|---|
| E1 | "This proves that X causes Y." | causal | single_study | experimental | absolute | moderate | **block** (absolute) |
| E2 | "X reduces Y." | causal | single_study | experimental | high | moderate | **warn** (gap 1) |
| E3 | "The results suggest that X reduces Y." | causal | single_study | experimental | moderate | moderate | pass |
| E4 | "The results suggest that X reduces Y." | causal | single_study | observational | moderate | low (M1) | **warn** |
| E5 | "X is associated with Y." | associative | multiple_consistent | — | high | high | pass |
| E6 | "Our model outperforms BERT-base on GLUE." | comparative | single_study | — | high | high | pass |
| E7 | "Transformers generally fail on long contexts." | generalization | single_study | — | high | low | **block** (gap 2) |
| E8 | "These findings may suggest a link." | associative | systematic_synthesis | — | low | high | pass + info (underclaim) |
| E9 | "Practitioners must adopt X." | normative | multiple_consistent | — | absolute | moderate | **block** |
| E10 | "Smith (2020) proved that X causes Y." | causal | — | — | — | — | bỏ qua (quy cho nguồn) |
| E11 | "This does not prove that X causes Y." | causal | single_study | — | — | — | bỏ qua (phủ định) |
| E12 | "X may improve Y." | causal | *(thiếu)* | — | moderate | moderate (cap) | pass + **warn** "chưa khai báo bằng chứng" |

---

## 10. Cần duyệt

| # | Nội dung | Đề xuất hiện tại |
|---|---|---|
| Q1 | Thêm `novelty` vào claim_type? | Không, để v0.2 |
| Q2 | Ngưỡng cỡ mẫu cho `anecdotal` | n < 30, nhưng nên để client khai |
| Q3 | Mặc định khi thiếu `evidence_level` | `moderate` + warn |
| Q4 | Có dùng `study_design` (M1) ở MVP không? | Có, nhưng là trường tùy chọn |
| Q5 | `descriptive` + `anecdotal` = `high` có quá thoáng? | Giữ, vì chỉ mô tả trong phạm vi đã nêu |
| Q6 | Danh sách marker (mục 8) | Cần người có chuyên môn ngôn ngữ duyệt; nên đối chiếu thêm với danh sách hedges/boosters trong Hyland (2005) |
