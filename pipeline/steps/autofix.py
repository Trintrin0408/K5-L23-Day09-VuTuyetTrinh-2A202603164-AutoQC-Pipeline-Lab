"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
CLIP_CODES = {"BOX_OUT_OF_IMAGE"}
REMOVE_CODES = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _clip(text):
    """Cắt box về trong [0,1]. Trả về dòng mới, hoặc None nếu sau khi cắt box không còn diện tích."""
    cls, cx, cy, w, h = parse_yolo_line(text)
    x1, x2 = max(0.0, cx - w / 2), min(1.0, cx + w / 2)
    y1, y2 = max(0.0, cy - h / 2), min(1.0, cy + h / 2)
    if x2 <= x1 or y2 <= y1:
        return None
    return f"{cls} {(x1 + x2) / 2:.6f} {(y1 + y2) / 2:.6f} {x2 - x1:.6f} {y2 - y1:.6f}"


def _remove_image(ds, stem):
    """Xoá ảnh + nhãn của `stem` khỏi ds. Trả về fix, hoặc None nếu ảnh đã không còn (chạy lần 2)."""
    img, lbl = ds.image_path(stem), ds.label_path(stem)
    if img is None and not lbl.exists():
        return None
    removed = []
    if img is not None:
        img.unlink()
        removed.append(img.name)
    if lbl.exists():
        lbl.unlink()
        removed.append(lbl.name)
    return {"image": stem, "line": "", "action": "remove_image", "before": ", ".join(removed), "after": "(đã xoá)"}


def _rename_classes(ds, cfg):
    """Ghi lại `names` trong data.yaml theo đúng cfg['classes']. None nếu đã đúng."""
    data = (yaml.safe_load(ds.yaml_path.read_text(encoding="utf-8")) or {}) if ds.yaml_path.exists() else {}
    want = dict(enumerate(cfg["classes"]))
    before = ds.yaml_names()
    if before == want:
        return None
    data["names"] = want
    ds.yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return {"image": "data.yaml", "line": "", "action": "rename_classes", "before": str(before), "after": str(want)}


def fix(ds, issues, cfg):
    errors = [i for i in issues if i.severity == ERROR]      # WARN là việc của người
    fixes = []

    # 1) Xoá ảnh trước: các issue dòng của ảnh đã xoá sẽ bị bỏ qua êm.
    removed = set()
    for stem in dict.fromkeys(i.image for i in errors if i.code in REMOVE_CODES):   # giữ thứ tự, bỏ trùng
        f = _remove_image(ds, stem)
        removed.add(stem)
        if f:
            fixes.append(f)

    # 2) data.yaml: sửa một lần dù có nhiều issue BAD_CLASS_NAME.
    if any(i.code == "BAD_CLASS_NAME" for i in errors):
        f = _rename_classes(ds, cfg)
        if f:
            fixes.append(f)

    # 3) Ảnh chưa có nhãn: KHÔNG tạo file, chỉ chuyển người gán.
    for stem in dict.fromkeys(i.image for i in errors if i.code == "MISSING_LABEL_FILE"):
        if stem not in removed and not ds.label_path(stem).exists():
            fixes.append({"image": stem, "line": "", "action": "needs_label",
                          "before": "(không có file)", "after": "chuyển người gán"})

    # 4) Lỗi theo dòng: gom theo file, mỗi dòng gốc một hành động (xoá thắng cắt), ghi file MỘT lần.
    per_file = defaultdict(dict)                              # stem -> {số dòng gốc: "drop" | "clip"}
    for i in errors:
        if i.line is None or i.image in removed:
            continue
        if i.code in DROP_CODES:
            per_file[i.image][i.line] = "drop"
        elif i.code in CLIP_CODES:
            per_file[i.image].setdefault(i.line, "clip")

    for stem, actions in per_file.items():
        fixes.extend(_fix_label_file(ds, stem, actions))

    return fixes


def _fix_label_file(ds, stem, actions):
    """Áp các hành động {số dòng gốc: 'drop'|'clip'} lên một file nhãn, ghi lại MỘT lần."""
    p = ds.label_path(stem)
    if not p.exists():
        return []
    raw = p.read_text(encoding="utf-8", errors="replace").splitlines()   # giữ dòng trống -> số dòng gốc
    out, fixes = [], []
    for n, text in enumerate(raw, 1):
        act = actions.get(n)
        if act is None or not text.strip():
            out.append(text)
            continue
        new = None
        if act == "clip":
            try:
                new = _clip(text)
            except ValueError:                                # dòng hỏng (check khác sẽ báo) -> xoá cho an toàn
                new = None
        if new is None:
            fixes.append({"image": stem, "line": n, "action": "drop_line", "before": text, "after": ""})
        else:
            fixes.append({"image": stem, "line": n, "action": "clip_box", "before": text, "after": new})
            out.append(new)
    if fixes:
        p.write_text("".join(ln + "\n" for ln in out), encoding="utf-8")
    return fixes
