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
| `duplicates.phash_dist` | 2 | TODO(học viên) | | |
| `second_opinion.conf` | 0.25 | TODO(học viên) | | |

TODO(học viên): **một chỗ calibration có thể đánh lừa bạn**, kèm bằng chứng từ dữ liệu của bạn (vd. mở xem vài cặp ảnh bị cho là trùng; số ảnh bị loại ở bước 1 có hợp lý không?).

## 4. Cửa chặn và điều pipeline KHÔNG bắt được
TODO(học viên): (a) chứng minh gate chặn đúng: chạy `python -m pipeline.run --budget 0 --reports work/rep_nb --export-dir work/exp_nb` (không có người duyệt nên ảnh thiếu file nhãn còn nguyên), chỉ ra kết luận **Rework**, mã thoát 20 và việc **không xuất** dataset. (Đừng sửa tay `work/run/ds`: pipeline dựng lại thư mục này từ raw mỗi lần chạy.)

**(b) Điểm mù.** Ở Bước 1 tôi tự xem ảnh vẽ nhãn (`scripts/viz_labels.py`) và ghi 3 lỗi, rồi đối chiếu với `02_error_list_v1.csv` (chạy với ngưỡng khởi đầu `second_opinion.conf = 0.25`):

| Lỗi tôi tự thấy | Pipeline bắt? | Bằng chứng |
|---|---|---|
| img_0001: 2 box person gần trùng trên cùng một người; người lính ở giữa không có nhãn | Có, cả hai | `DUP_BOX` dòng 3 (IoU 0,995, máy tự xoá); `POSSIBLE_MISSING` (model: person, conf 0,95) |
| img_0101: ô tô con màu trắng bị gán **truck** | Có, nhưng mong manh | `POSSIBLE_WRONG_CLASS`, model nói car với **conf chỉ 0,56** (IoU 0,58) |
| img_0150: box person bên trái trùm cả cái ghế (box lỏng) | Có, nhưng **sai loại** | `POSSIBLE_FALSE_POS` dòng 3 (IoU tốt nhất 0,23), không phải `POSSIBLE_LOOSE_BOX` |

Từ đó rút ra 2 điểm mù:
1. **Box lỏng nhẹ không bị bắt.** `POSSIBLE_LOOSE_BOX` chỉ bật khi IoU với dự đoán nằm trong [0,3; 0,5). Box lỏng nặng như img_0150 (IoU 0,23) rơi xuống thành FALSE_POS, nên người duyệt vẫn thấy nhưng nhận sai tên lỗi. Box lỏng nhẹ (IoU ≥ 0,5) thì không bị cờ gì.
2. **Nhầm lớp mà model kém tự tin thì lọt.** Lỗi ở img_0101 chỉ được bắt vì conf 0,56 vượt ngưỡng 0,25. Nếu calibrate `second_opinion.conf` lên trên 0,56 thì lỗi này biến mất khỏi báo cáo. Nếu model lớn cũng nhầm lớp thì pipeline không thể biết.

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
