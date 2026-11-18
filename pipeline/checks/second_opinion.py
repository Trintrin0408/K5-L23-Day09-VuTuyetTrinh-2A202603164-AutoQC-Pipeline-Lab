"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★ (khó nhất, đáng điểm nhất)

Test:  pytest tests/test_second_opinion.py -q

Máy kiểm quy tắc, người kiểm ý nghĩa (slide). Các lỗi như thiếu nhãn / gán nhầm lớp hợp lệ / box lỏng
KHÔNG bắt được bằng quy tắc cú pháp. Ta nhờ một model mạnh hơn "nhìn lại" và CHỈ CẢNH BÁO (model cũng có thể sai):
những ảnh bị cờ sẽ vào hàng đợi cho NGƯỜI duyệt.

`preds[stem]` = list `[id_lớp, conf, cx, cy, w, h]` của model (lấy qua `get_preds(ds, cfg, "checker")` nếu preds=None).
`L = ds.valid_boxes(stem)` = list `(id_lớp, cx, cy, w, h)` của nhãn (đã bỏ dòng hỏng).
Ngưỡng ở `cfg["second_opinion"]`: conf, min_area_px, fp_conf, iou_missing, iou_match, iou_loose.

Thuật toán gợi ý, với từng ảnh (bỏ qua ảnh không có trong preds hoặc không có file nhãn):
  P = dự đoán có conf >= conf  VÀ diện tích px (w*W * h*H) >= min_area_px
  Với mỗi dự đoán r trong P: lấy các nhãn có IoU(r, nhãn) >= iou_missing  (cands)
   - không có cands                            -> POSSIBLE_MISSING     (model thấy vật mà nhãn không có box)
   - có cands cùng lớp, tốt nhất IoU < iou_loose -> POSSIBLE_LOOSE_BOX  (đúng vật, box lỏng/lệch)
   - không có cands cùng lớp, nhưng cands tốt nhất IoU >= iou_match (khác lớp) -> POSSIBLE_WRONG_CLASS
  Với mỗi dòng nhãn hợp lệ: nếu IoU với MỌI dự đoán (conf >= fp_conf, không lọc diện tích) đều < iou_missing
                                             -> POSSIBLE_FALSE_POS  (box nhãn không khớp vật nào model thấy; Issue.line = số dòng)

Chi tiết các ca biên (test kiểm đúng các ca này)
- `cands` gồm nhãn MỌI lớp có IoU >= iou_missing; "tốt nhất cùng lớp" = cands cùng lớp có IoU lớn nhất; "tốt nhất khác lớp" tương tự với cands khác lớp.
- Thứ tự quyết định cho mỗi dự đoán: (1) cands rỗng -> MISSING. (2) có cands cùng lớp: IoU tốt nhất < iou_loose -> LOOSE_BOX, ngược lại KHÔNG cờ
  (nhãn đúng lớp đã phủ vật này, kể cả khi còn nhãn khác lớp chồng lên). (3) không có cands cùng lớp: nếu IoU tốt nhất khác lớp >= iou_match -> WRONG_CLASS;
  nếu chỉ có khác lớp với IoU trong [iou_missing, iou_match) -> không cờ gì (mơ hồ: để cho FALSE_POS / lần duyệt khác).
- Một dự đoán sinh tối đa MỘT issue (MISSING / LOOSE_BOX / WRONG_CLASS); một ảnh có thể có nhiều issue.
- Thứ tự issue: theo `ds.image_files()` rồi theo thứ tự dự đoán trong `preds[stem]`, cuối cùng là các FALSE_POS theo số dòng; `Issue.image` = stem, `Issue.line` chỉ đặt cho FALSE_POS.

Lưu ý số dòng: dùng `ds.read_label_lines(stem)` (giữ số dòng gốc, kể cả dòng hỏng/trống) để lấy `Issue.line`; `valid_boxes` KHÔNG giữ số dòng.

Tất cả severity WARN; `Issue.extra` nên có {"conf": ...} hoặc {"iou": ...} (hàng đợi duyệt dùng conf để xếp ưu tiên).

Gợi ý
- `iou_xywh` có sẵn. Dòng nhãn hỏng không được làm script chết (dùng `ds.valid_boxes` và `parse_yolo_line` trong try).
- Kết quả phụ thuộc mạnh vào ngưỡng: calibrate chúng ở Bước 3 thay vì đoán.
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401
from ..model_cache import get_preds  # noqa: F401


CHECK = "second_opinion"


def _label_boxes(ds, stem):
    """[(số dòng gốc, (id, cx, cy, w, h))] cho các dòng nhãn hợp lệ; dòng hỏng/ID lạ bị bỏ (check khác báo)."""
    out = []
    for line_no, text in ds.read_label_lines(stem) or []:
        try:
            b = parse_yolo_line(text)
        except ValueError:
            continue
        if 0 <= b[0] < len(ds.classes):
            out.append((line_no, b))
    return out


def _judge(pred_cls, pbox, labels, c):
    """Phán xét MỘT dự đoán so với nhãn. Trả về (code, extra) hoặc None nếu không cờ."""
    cands = [(iou_xywh(pbox, lb[1:]), lb[0]) for _, lb in labels]
    cands = [(iou, cls) for iou, cls in cands if iou >= c["iou_missing"]]
    if not cands:
        return "POSSIBLE_MISSING", {}
    same = [iou for iou, cls in cands if cls == pred_cls]
    if same:
        best = max(same)
        return ("POSSIBLE_LOOSE_BOX", {"iou": round(best, 4)}) if best < c["iou_loose"] else None
    best_iou, best_cls = max(cands)                         # chỉ còn nhãn khác lớp
    if best_iou >= c["iou_match"]:
        return "POSSIBLE_WRONG_CLASS", {"iou": round(best_iou, 4), "label_class": best_cls}
    return None                                             # mơ hồ: không cờ


def _check_image(stem, rows, labels, size, c, classes):
    issues = []
    W, H = size

    # 1) Từng dự đoán đủ tin cậy & đủ lớn -> MISSING / LOOSE_BOX / WRONG_CLASS (tối đa 1 issue mỗi dự đoán)
    for cls, conf, *pbox in rows:
        cls = int(cls)
        if conf < c["conf"] or (pbox[2] * W) * (pbox[3] * H) < c["min_area_px"]:
            continue
        verdict = _judge(cls, pbox, labels, c)
        if verdict:
            code, extra = verdict
            name = classes[cls] if 0 <= cls < len(classes) else cls
            issues.append(Issue(CHECK, WARN, code, stem, f"model ({name}, conf={conf:.2f}): {code}",
                                extra={"conf": conf, "pred_class": cls, **extra}))

    # 2) Từng dòng nhãn không khớp dự đoán nào (conf >= fp_conf, KHÔNG lọc diện tích) -> FALSE_POS
    fp_preds = [r[2:] for r in rows if r[1] >= c["fp_conf"]]
    for line_no, (cls, *lbox) in labels:
        best = max((iou_xywh(lbox, p) for p in fp_preds), default=0.0)
        if best < c["iou_missing"]:
            issues.append(Issue(CHECK, WARN, "POSSIBLE_FALSE_POS", stem,
                                f"box nhãn lớp {classes[cls]} không khớp dự đoán nào (IoU tốt nhất {best:.2f})",
                                line=line_no, extra={"iou": round(best, 4)}))
    return issues


def run(ds, cfg, preds=None):
    c = cfg["second_opinion"]
    if preds is None:
        preds = get_preds(ds, cfg, "checker")
    issues = []
    for img in ds.image_files():
        stem = img.stem
        if stem not in preds or not ds.label_path(stem).exists():
            continue
        size = ds.image_size(stem)
        if size is None:                                    # ảnh hỏng: check images đã báo
            continue
        issues += _check_image(stem, preds[stem], _label_boxes(ds, stem), size, c, ds.classes)
    return issues
