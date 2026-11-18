# Báo cáo Day 09 — Vũ Tuyết Trinh, 2A202603164

## 1. Kết luận trước
Pipeline kết luận **HOLD** (mã thoát 10). Vào **224** ảnh; cửa vào loại **22** ảnh (hỏng, sai cỡ, trùng, rò rỉ test); dataset `clean_v1` xuất ra **202** ảnh dưới dạng **bản nháp, chưa phát hành**.

Lý do: không còn lỗi bắt buộc nào (0 ERROR sau người duyệt), nhưng **38/202 ảnh (18,8%)** còn cảnh báo chưa được người xem, vượt ngưỡng 10%. Hàng đợi duyệt có **125 ảnh**, mà ngân sách chỉ có **80**.

## 2. Lỗi và phân việc
Số liệu từ `02_error_list_v1.csv` (trước khi sửa; dạng "số issue / số ảnh").

| Mã lỗi | Số ảnh/dòng | Ai sửa (máy/người) | Vì sao |
|---|---:|---|---|
| DUP_IMAGE_EXACT | 8 ảnh | máy (loại ở cửa vào) | md5 trùng, chắc chắn là bản sao |
| DUP_IMAGE_NEAR | 4 ảnh | máy (loại ở cửa vào) | phash ≤ 10; đã mở xem, các cặp đều trùng thật (cắt/đổi màu) |
| LEAK_TEST | 5 ảnh | máy (loại ở cửa vào) | trùng ảnh test/gold_val; giữ lại sẽ làm số đo cuối bị thổi phồng |
| CORRUPT_IMAGE | 2 ảnh | máy (loại ở cửa vào) | ảnh không mở được |
| BAD_SIZE | 3 ảnh | máy (loại ở cửa vào) | cạnh < 250 px (quy tắc dự án) |
| BAD_CLASS_NAME | 1 file (2 tên) | máy (`rename_classes`) | `data.yaml` ghi `Person`, `Bus`; quy tắc đã cố định là `cfg.classes` |
| BAD_CLASS_ID | 6 dòng / 6 ảnh | máy (`drop_line`) | ID lạ (-1, 4, 7, 93): không đoán được lớp đúng nên xoá dòng |
| BAD_FORMAT | 3 dòng / 3 ảnh | máy (`drop_line`) | không đúng 5 cột số |
| BOX_ZERO | 4 dòng / 4 ảnh | máy (`drop_line`) | box w hoặc h ≤ 0 |
| DUP_BOX | 7 dòng / 7 ảnh | máy (`drop_line`) | cùng lớp, IoU > 0,9 với dòng trước |
| BOX_OUT_OF_IMAGE | 8 dòng / 8 ảnh | máy (`clip_box`) | cắt về [0,1], giữ lớp |
| MISSING_LABEL_FILE | 6 ảnh | **người** (`needs_label`) | máy không bịa nhãn; ảnh lên đầu hàng đợi (trọng số 10) |
| POSSIBLE_MISSING | 53 / 52 ảnh | **người** | model lớn thấy vật mà nhãn không có; model có thể sai |
| POSSIBLE_FALSE_POS | 29 / 27 ảnh | **người** | box nhãn không khớp vật nào model thấy |
| POSSIBLE_LOOSE_BOX | 28 / 24 ảnh | **người** | đúng vật nhưng IoU < 0,5 |
| POSSIBLE_WRONG_CLASS | 18 / 18 ảnh | **người** | model nói lớp khác với IoU ≥ 0,5 |
| EMPTY_LABEL | 12 ảnh | **người** | file rỗng: ảnh nền hay quên gán? chỉ người biết |
| BOX_TINY / BOX_HUGE | 6 / 4 ảnh; 3 / 3 ảnh | **người** | quy tắc guideline, có thể hợp lệ |
| CLASS_RARE | 4 (cấp dataset) | máy (gián tiếp) | do ID lạ -1/4/7/93; hết sau khi xoá dòng BAD_CLASS_ID |

Máy tự sửa **35** thay đổi (`03_fixes.csv`): 20 `drop_line`, 8 `clip_box`, 1 `rename_classes`, 6 `needs_label`.

**Thứ tự hàng đợi.** `05_review_queue.csv` xếp theo tổng trọng số cảnh báo của từng ảnh (`review.weights`): `NEEDS_LABEL` = 10, nên 6 ảnh chưa có nhãn nằm ngay đầu. Tiếp theo là ảnh có nhiều cảnh báo ngữ nghĩa nặng (WRONG_CLASS 3, MISSING 2, FALSE_POS 2…). Ảnh đứng đầu, img_0020, có điểm 11,5 vì dính cùng lúc FIXED_DROP_LINE + MISSING + WRONG_CLASS.

**Người xem được bao nhiêu.** Sau khi máy sửa, có **123 cảnh báo ngữ nghĩa (POSSIBLE_*) trên 103 ảnh**. Ngân sách 80 ảnh phủ được **94/123 cảnh báo (76%), trên 74/103 ảnh**. Ảnh thứ 80 có điểm 3,34 và ảnh thứ 81 có 3,33, nên điểm cắt rơi đúng vào nhóm ảnh có một cảnh báo nặng. Sau khi duyệt, `07_error_list_v3` vẫn còn 57 cảnh báo ngữ nghĩa chưa ai xem.

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
**Chưa chạy.** Tôi chọn chỉ làm phần lõi (`make check-core`) và không train trên Colab. Vì vậy báo cáo này **không** đưa ra kết luận nào về việc dữ liệu `clean` có giúp model tốt hơn `raw` hay không.

## 6. Quyết định và ghi chú AI
**(a) Quyết định cuối: HOLD**, chưa phát hành `clean_v1`. Tôi không đổi ngưỡng chỉ để đạt Release (với `conf = 0.8` sẽ ra Release, xem mục 3). Để thành Release:
1. Người duyệt thêm khoảng 45 ảnh còn lại trong hàng đợi (125 − 80), ưu tiên 38 ảnh còn cảnh báo, để tỉ lệ ảnh còn cảnh báo xuống dưới 10% (tối đa 20/202 ảnh).
2. Nếu ngân sách không tăng được thì giảm báo nhầm của `POSSIBLE_FALSE_POS` (precision trên calib chỉ 0,31), ví dụ chuẩn hoá lại guideline về vật bị che hoặc rất nhỏ. Việc này phải đi qua guideline dự án, không phải sửa ngưỡng cố định trong config.
3. Chạy lại `make run` và chỉ phát hành khi gate trả về Release.

**(b) Ghi chú AI.** Có dùng AI (Claude Code) để viết 4 module.
- **Prompt chính:** Với mỗi module, tôi đưa AI đọc docstring của stub cùng file test tương ứng, `pipeline/common.py` và `configs/pipeline.yaml`. Tôi yêu cầu viết theo thứ tự label_format → gate → autofix → second_opinion, không viết cứng ngưỡng (lấy từ `cfg`), và chỉ sửa 4 file được phép.
- **Cách kiểm:** (1) Chạy `pytest` từng file rồi cả bộ: 79/79 xanh. (2) Tự thử 3 ca ngoài test: một dòng dính 2 lỗi (tràn ảnh + DUP_BOX) chỉ bị xoá một lần, không ghi thêm `clip_box`; dòng trống ở giữa file không làm lệch số dòng, chạy lại sau khi sửa chỉ còn WARN; một ảnh có nhiều dự đoán thì mỗi dự đoán sinh tối đa 1 issue, đúng thứ tự. (3) Chạy `python -m pipeline.run` và đối chiếu với 3 lỗi tôi tự thấy (mục 4b). Tôi cũng đọc từng dòng để kiểm code có xoá/ghi đè file ngoài `ds` không và có `except` nuốt lỗi không.
- **Một lần AI sai/thiếu:** Bản đầu của `autofix.fix` gói hết mọi việc trong một hàm, linter báo độ phức tạp 39 (giới hạn 15). Tôi yêu cầu tách phần sửa từng file nhãn ra hàm `_fix_label_file` rồi chạy lại test. Cả 4 module đều qua test ngay lần đầu, nên tôi không coi "test xanh" là đủ mà tự thử thêm các ca ở trên.

*(Thưởng +2, tùy chọn)* CVAT: lọc `width < 20`, ảnh/số box khớp, đối chiếu `BOX_TINY` (xem docs/CVAT_FILTER.md), 1 câu về `can_review`.
