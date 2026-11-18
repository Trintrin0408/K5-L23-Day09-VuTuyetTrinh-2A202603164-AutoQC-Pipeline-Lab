# Báo cáo Day 09 — <Họ và tên>, <MSHV>

> Xoá mọi `TODO(học viên)` và dòng gợi ý. Mỗi ý trả lời bằng **số lấy từ `submission/reports/`**, kèm mẫu số. Cả báo cáo ~1–2 trang.

## 1. Kết luận trước
TODO(học viên): pipeline kết luận **Release / Hold / Rework**? Bao nhiêu ảnh vào, bao nhiêu ảnh ra dataset? Lý do chính (1–3 câu).

## 2. Lỗi và phân việc
Lấy từ `02_error_list_v1` (gom theo mã lỗi). Cột "ai sửa": **máy** (autofix) hay **người** (hàng đợi); chỉ ghi những mã có mặt trong lô của bạn.

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| TODO(học viên) | | | |

TODO(học viên): vì sao `05_review_queue.csv` xếp ảnh đầu hàng như vậy? Với ngân sách 80 ảnh, người xem được bao nhiêu lỗi ngữ nghĩa?

## 3. Calibration (2 ngưỡng)
| Tham số | Khởi đầu | Đã chọn | Precision / Recall (trước → sau) | Lý do (đánh đổi) |
|---|---|---|---|---|
| `duplicates.phash_dist` | 2 | **10** | DUP_IMAGE_NEAR: 1.00 / 0.50 → 1.00 / 0.67 (EXACT giữ 1.00 / 1.00) | Recall tăng mà precision không giảm. Mở xem các cặp mới bị bắt trên raw: img_0223↔0077, img_0186↔0061 trùng thật, và **img_0101 là bản cắt của test/test_039** (rò rỉ test, mức 2 bỏ sót). Trên raw, các mức 10–14 cho kết quả giống hệt nhau; tôi chọn 10 là mức nhỏ nhất bắt được mọi cặp trùng thật đã kiểm bằng mắt, cách xa mức 16 (nơi bắt đầu báo nhầm) |
| `second_opinion.conf` | 0.25 | **0.6** | MISSING: 0.50 / 1.00 → 0.57 / 1.00; WRONG_CLASS: 0.56 / 0.83 → 0.62 / 0.83; LOOSE_BOX: 0.29 / 0.40 → 0.20 / 0.20; FALSE_POS không đổi (dùng `fp_conf`) | Tăng precision mà giữ recall MISSING = 1.00, đổi lại mất recall LOOSE_BOX. Hàng đợi người duyệt giảm từ 143 xuống 125 ảnh. Không chọn 0.8 dù F1 WRONG_CLASS cao nhất (0.91) và cho ra Release (7,9% ảnh còn cảnh báo): recall MISSING sẽ giảm còn 0.75, tức bỏ lọt 2/8 vật thiếu nhãn. Chọn ngưỡng để "đạt" Release là sai mục đích |

**Calibration có thể đánh lừa ở đâu.** Trên calib, `phash_dist = 16` có F1 trùng gần đúng cao nhất (0.91 so với 0.80). Nhưng calib chỉ có 6 cặp trùng gần đúng, nên chênh 1 cặp đã đổi F1 rất nhiều. Chạy trên raw, mức 16 làm số ảnh bị coi là rò rỉ test tăng từ 5 lên 11 và trùng gần đúng tăng từ 4 lên 7. Mở xem thì thấy nó ghép những cặp **hoàn toàn khác nhau**: tay vợt tennis ↔ hai người trượt tuyết (img_0011/0008), người lướt sóng ↔ người đàn ông ngồi bàn (img_0177/0113). Nếu tin theo calib, pipeline sẽ xoá nhầm ảnh tốt.

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
**(a) Gate chặn đúng.** Chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt). Kết luận **REWORK — còn 6 lỗi bắt buộc (MISSING_LABEL_FILE)**, mã thoát **20**, log in "KHÔNG xuất: còn lỗi bắt buộc (Rework)", và thư mục `work/exp_nb` **không được tạo**. Máy không bịa nhãn cho 6 ảnh chưa có file nhãn, và khi không có người gán thì gate không cho qua.

**(b) Điểm mù.** Ở Bước 1 tôi tự xem ảnh vẽ nhãn (`scripts/viz_labels.py`) và ghi 3 lỗi, rồi đối chiếu với `02_error_list_v1.csv` (ngưỡng đã calibrate):

| Lỗi tôi tự thấy | Pipeline bắt? | Bằng chứng |
|---|---|---|
| img_0001: 2 box person gần trùng trên cùng một người; người lính ở giữa không có nhãn | Có, cả hai | `DUP_BOX` dòng 3 (IoU 0,995, máy tự xoá); `POSSIBLE_MISSING` (model: person, conf 0,95) |
| img_0101: ô tô con màu trắng bị gán **truck** | Ảnh bị loại ở cửa vào | `LEAK_TEST` (trùng test/test_039). Với `phash_dist = 2` ảnh này lọt qua, khi đó lỗi nhầm lớp chỉ bị bắt nhờ model nói car với conf 0,56 |
| img_0150: box person bên trái trùm cả cái ghế (box lỏng) | Có, nhưng **sai loại** | `POSSIBLE_FALSE_POS` dòng 3 (IoU tốt nhất 0,23), không phải `POSSIBLE_LOOSE_BOX` |

Hai điểm mù:
1. **Box lỏng nhẹ không bị bắt.** `POSSIBLE_LOOSE_BOX` chỉ bật khi IoU với dự đoán nằm trong [0,3; 0,5). Box lỏng nặng như img_0150 (IoU 0,23) rơi xuống thành FALSE_POS, nên người duyệt vẫn thấy nhưng nhận sai tên lỗi. Box lỏng nhẹ (IoU ≥ 0,5) thì không bị cờ gì. Trên calib, recall LOOSE_BOX ở ngưỡng đã chọn chỉ 0.20 (1/5).
2. **Nhầm lớp mà model kém tự tin thì lọt.** So với `conf = 0.25`, ngưỡng 0.6 làm mất 3 cảnh báo WRONG_CLASS trên raw: img_0092 (model nói truck, conf 0,47), img_0124 (truck, 0,48), img_0180 (bus, 0,31). Ví dụ img_0101 cho thấy lỗi thật có thể nằm đúng trong vùng conf này. Ngay cả ở conf 0.1, recall WRONG_CLASS trên calib cũng chỉ 0.83 (5/6): khi model lớn cũng nhầm hoặc không thấy vật, pipeline không thể biết.

## 5. Train: raw vs clean (tùy chọn, chấm riêng)
Chưa train: ghi "chưa chạy" và lý do, rồi bỏ qua phần còn lại của mục này. Nếu đã train: dán bảng từ `submission/results/comparison.md` (model, epoch, seed, số ảnh train mỗi biến thể).

TODO(học viên): chênh mAP50 (clean − raw) so với **độ lệch chuẩn giữa các seed**; kết luận **trung thực** (nằm trong nhiễu thì nói là chưa kết luận được); ≥ 2 giả thuyết giải thích (ảnh trùng/rò rỉ test trong `raw`, nhãn máy còn lại trong `clean`, test chỉ 100 ảnh…) và cách kiểm.

## 6. Quyết định và ghi chú AI
TODO(học viên): (a) quyết định cuối; nếu Hold/Rework cần làm gì để thành Release?

**(b) Ghi chú AI.** Có dùng AI (Claude Code) để viết 4 module.
- **Prompt chính:** Với mỗi module, tôi đưa AI đọc docstring của stub cùng file test tương ứng, `pipeline/common.py` và `configs/pipeline.yaml`. Tôi yêu cầu viết theo thứ tự label_format → gate → autofix → second_opinion, không viết cứng ngưỡng (lấy từ `cfg`), và chỉ sửa 4 file được phép.
- **Cách kiểm:** (1) Chạy `pytest` từng file rồi cả bộ: 79/79 xanh. (2) Tự thử 3 ca ngoài test: một dòng dính 2 lỗi (tràn ảnh + DUP_BOX) chỉ bị xoá một lần, không ghi thêm `clip_box`; dòng trống ở giữa file không làm lệch số dòng, chạy lại sau khi sửa chỉ còn WARN; một ảnh có nhiều dự đoán thì mỗi dự đoán sinh tối đa 1 issue, đúng thứ tự. (3) Chạy `python -m pipeline.run` và đối chiếu với 3 lỗi tôi tự thấy (mục 4b). Tôi cũng đọc từng dòng để kiểm code có xoá/ghi đè file ngoài `ds` không và có `except` nuốt lỗi không.
- **Một lần AI sai/thiếu:** Bản đầu của `autofix.fix` gói hết mọi việc trong một hàm, linter báo độ phức tạp 39 (giới hạn 15). Tôi yêu cầu tách phần sửa từng file nhãn ra hàm `_fix_label_file` rồi chạy lại test. Cả 4 module đều qua test ngay lần đầu, nên tôi không coi "test xanh" là đủ mà tự thử thêm các ca ở trên.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
