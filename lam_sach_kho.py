"""Lập danh mục cách ly logic và báo cáo kiểm kho, giữ nguyên nguồn/chỉ mục."""
import csv
import json
from pathlib import Path
import pickle
from collections import Counter

import loc_nguon

ROOT = Path(__file__).resolve().parent


def main():
    with (ROOT / "faiss_index_data_giao_duc/index.pkl").open("rb") as f:
        store, _ = pickle.load(f)
    grouped = {}
    for doc in store._dict.values():
        grouped.setdefault(doc.metadata.get("source_file", ""), []).append(doc)
    catalog = loc_nguon.xay_dung(grouped)
    out = ROOT / "nhat_ky_lam_sach_kho"
    out.mkdir(exist_ok=True)
    rows = [{"tep": name, **row} for name, row in sorted(catalog.items())]
    summary = dict(Counter(r["trang_thai"] for r in rows))
    for name, obj in (("danh_muc_nguon.json", catalog), ("tong_ket.json", summary)):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "danh_sach_kiem_kho.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (out / "bao_cao_lam_sach.md").write_text(
        "# Kiểm kho và cách ly khỏi truy hồi\n\n"
        + "\n".join(f"- {k}: {v} tệp" for k, v in summary.items())
        + "\n\nCác tệp gắn cờ được loại khỏi truy hồi mặc định trong tiến trình dịch vụ mới. "
        "Bản gốc và chỉ mục được giữ nguyên để kiểm tra/khôi phục. Tên tệp không được dùng để "
        "điền số hiệu khi nội dung có ô trống. Đây là kiểm tra tự động, không thay xác minh pháp lý. "
        "Tệp ký số theo quy ước tên cũ và nguồn OCR hỏng cần kiểm tra riêng.\n",
        encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
