"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


CHECK = "label_format"


def _overflow(cx, cy, w, h) -> float:
    """Mức tràn lớn nhất của 4 mép box ra ngoài [0, 1] (0 nếu nằm gọn trong ảnh)."""
    x1, x2 = cx - w / 2, cx + w / 2
    y1, y2 = cy - h / 2, cy + h / 2
    return max(0.0, -x1, x2 - 1.0, -y1, y2 - 1.0)


def run(ds, cfg):
    c = cfg["label_format"]
    n_classes = len(ds.classes)
    issues = []

    for lf in ds.label_files():
        stem = lf.stem
        size = ds.image_size(stem)          # (rộng, cao) px hoặc None nếu ảnh hỏng/không có
        kept = []                           # các box hợp lệ ở dòng TRƯỚC: (số dòng, (id, cx, cy, w, h))

        def add(sev, code, line, msg, **extra):
            issues.append(Issue(CHECK, sev, code, stem, msg, line=line, extra=extra))

        for line_no, text in ds.read_label_lines(stem) or []:   # dòng trống đã bị bỏ, số dòng giữ nguyên
            # 1) định dạng: đúng 5 cột số, không nan/inf
            try:
                cls, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                add(ERROR, "BAD_FORMAT", line_no, f"dòng sai định dạng ({e}): {text.strip()!r}")
                continue
            # 2) id lớp
            if not 0 <= cls < n_classes:
                add(ERROR, "BAD_CLASS_ID", line_no, f"id lớp {cls} ngoài 0..{n_classes - 1}", class_id=cls)
                continue
            # 3) box rỗng
            if w <= 0 or h <= 0:
                add(ERROR, "BOX_ZERO", line_no, f"box rỗng (w={w}, h={h})")
                continue

            box = (cx, cy, w, h)
            # 4) tràn ảnh (có dung sai)
            over = _overflow(*box)
            if over > c["overflow_tol"]:
                add(ERROR, "BOX_OUT_OF_IMAGE", line_no, f"box tràn ảnh {over:.4f}", overflow=round(over, 6))
            # 5) box lặp: cùng lớp với một dòng trước đó, IoU cao -> báo ở dòng sau
            for prev_no, (pcls, *pbox) in kept:
                if pcls == cls:
                    iou = iou_xywh(pbox, box)
                    if iou > c["dup_box_iou"]:
                        add(ERROR, "DUP_BOX", line_no, f"trùng box ở dòng {prev_no} (IoU={iou:.3f})",
                            dup_of=prev_no, iou=round(iou, 4))
                        break
            kept.append((line_no, (cls, *box)))
            # 6) box quá nhỏ (theo px, cạnh ngắn) — cần kích thước ảnh
            if size:
                short_px = min(w * size[0], h * size[1])
                if short_px < c["min_box_px"]:
                    add(WARN, "BOX_TINY", line_no, f"cạnh ngắn {short_px:.1f}px < {c['min_box_px']}px",
                        short_px=round(short_px, 2))
            # 7) box gần phủ hết ảnh
            if w * h > c["max_box_frac"]:
                add(WARN, "BOX_HUGE", line_no, f"box chiếm {w * h:.2%} ảnh", frac=round(w * h, 4))

    return issues
