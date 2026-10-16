"""Xuất toàn bộ đoạn của nguồn gắn nhãn để chấm; độc lập kết quả truy hồi."""
import json
from pathlib import Path
import pickle
import sys

import chi_so_ir

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "nhat_ky_do_test" / "thuc_nghiem_20261015"


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sample = json.loads((OUT / "mau_40_cau.json").read_text(encoding="utf-8"))
    with (ROOT / "faiss_index_data_giao_duc" / "index.pkl").open("rb") as f:
        store, _ = pickle.load(f)
    docs = list(store._dict.items())
    dest = OUT / "nguon_chuan_40_cau"
    dest.mkdir(exist_ok=True)
    summary = []
    for i, item in enumerate(sample, 1):
        refs = []
        for key, doc in docs:
            name = doc.metadata.get("source_file", "")
            if any(chi_so_ir.khop_nhan(name, label) for label in item.get("nguon_mong_doi", [])):
                refs.append({"chunk_id": key, "metadata": doc.metadata, "page_content": doc.page_content})
        row = {"stt": i, **item, "chu_y": "Nhãn là nguồn mong đợi, chưa bảo đảm văn bản còn hiệu lực hoặc đủ đáp án. Chấm viên phải đọc và kiểm tra.", "doan_nguon": refs}
        (dest / f"nguon_{i:02d}.json").write_text(json.dumps(row, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        summary.append({"stt": i, "cau_hoi": item["cau_hoi"], "so_doan": len(refs), "nguon": sorted(set(r["metadata"].get("source_file", "") for r in refs))})
    (dest / "muc_luc.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã xuất nguồn chuẩn độc lập cho {len(summary)} câu; {sum(not r['so_doan'] for r in summary)} câu thiếu nguồn khớp nhãn.")


if __name__ == "__main__":
    main()
