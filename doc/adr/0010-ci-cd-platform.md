# ADR-0010: Nền tảng CI/CD — registry, lưu trữ blob, và chính sách downtime

- Trạng thái: Accepted
- Ngày: 2026-11-04
- Liên quan: `plans/ci-cd-team-standard/plan.md` (Phase 04)

## Bối cảnh

Phase 01–03 của plan CI/CD đã hoàn thành: governance baseline, CI bắt buộc
(`backend-quality-and-tests`, `frontend-quality-and-build`), và production container
contract (một image chạy cả API và worker, xem `apps/backend/Dockerfile`). Phase 04 là
điểm dừng bắt buộc để chủ sở hữu production quyết định nền tảng deploy trước khi viết
CD workflow thật (Phase 05), tránh đoán sai platform rồi phải viết lại.

Input đã xác nhận trước đó (`plans/ci-cd-team-standard/plan.md`, "Validated Deployment
Inputs"):

- Hosting: homeserver tự quản, chạy cả API, worker, và frontend.
- Release control: CI build/publish tự động; deploy production cần một người approve
  thủ công.
- Deployment adapter: Docker Compose trên homeserver.

Ba câu hỏi còn lại được chủ sở hữu production trả lời ngày 2026-11-04:

## Quyết định

1. **Container registry: GHCR (`ghcr.io`)**. Tận dụng tích hợp sẵn với GitHub Actions
   (`GITHUB_TOKEN`), không cần tạo/luân chuyển secret riêng cho bước push image. Image
   được tag bằng commit SHA (immutable) và một tag mutable theo track (ví dụ `dev`)
   dùng để tham chiếu "mới nhất đã qua CI", không dùng để deploy trực tiếp — production
   luôn tham chiếu digest SHA.
   - **TODO(owner):** xác nhận chính sách retention cụ thể (bao nhiêu ngày/bao nhiêu
     tag giữ lại) trước khi registry đầy; cho tới lúc đó không xoá tag tự động.

2. **`BLOB_DIR`: Docker named volume `aprkb_blobs`**, mount cùng path vào cả API và
   worker container trong Compose production. Không dùng bind-mount tới một đường dẫn
   host cụ thể ở giai đoạn này — đơn giản hơn, không cần chuẩn bị quyền thư mục trên
   homeserver trước khi deploy lần đầu.
   - **TODO(owner):** named volume không tự có cơ chế backup ra ngoài host; Phase 05
     phải thêm một lệnh backup định kỳ (ví dụ chạy một container tạm mount volume và
     `tar` ra một thư mục host, rồi đồng bộ thư mục đó ra ngoài homeserver) và xác định
     nơi lưu bản backup đó.

3. **Downtime: chấp nhận downtime ngắn (vài phút) mỗi lần deploy.** Không yêu cầu
   rolling/zero-downtime. Do đó:
   - Không cần expand/contract migration hai bước hay chạy song song N-1 image với
     schema mới trong lúc chuyển đổi.
   - Quy trình release: dừng container cũ → migrate một lần qua image mới → start
     container mới → health check → nếu fail, rollback về image digest trước đó.
   - Nguyên tắc "forward-fix trước, downgrade không coi là an toàn" trong
     `doc/runbooks/migrations.md` vẫn áp dụng không đổi.

## Hệ quả

- Phase 05 được phép bắt đầu với phạm vi đã giảm tương ứng: không cần dựng compatibility
  matrix N-1/N/N+1 đầy đủ như một track zero-downtime sẽ cần, nhưng **vẫn phải** chứng
  minh rollback về digest cũ hoạt động được — đây là yêu cầu không đổi trong "Global
  Acceptance Criteria" của `plan.md`.
- CD workflow build và push image lên GHCR chỉ từ nhánh mặc định đã qua CI; production
  deploy luôn tham chiếu một digest cụ thể, không rebuild.
- Backup/restore cho volume `aprkb_blobs` và cho PostgreSQL production là TODO(owner)
  cụ thể, phải có trước khi coi Phase 05 là "production-ready" — không chỉ
  "staging-proven".
- Nhiều tiêu chí nghiệm thu của `phase-05-track-specific-cd-and-rollout.md` (game day,
  rehearsal bởi một thành viên khác, xác minh trên staging/production thật) đòi hỏi hạ
  tầng thật (homeserver, GHCR credentials, một người review khác) mà một phiên làm
  việc một mình không thể tự chứng minh được; phạm vi triển khai ban đầu của Phase 05
  là **scaffolding đã kiểm thử cục bộ** (workflow, compose, script, runbook), không
  phải "đã rehearsal production".
