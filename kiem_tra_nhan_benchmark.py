"""
ĐỐI CHIẾU NHÃN NGUỒN CỦA BỘ CÂU HỎI BENCHMARK VỚI KHO TÀI LIỆU THẬT
====================================================================
Chạy:              python kiem_tra_nhan_benchmark.py
Chỉ một tập:       python kiem_tra_nhan_benchmark.py --tap test

VÌ SAO CẦN
  Nhãn `nguon_mong_doi` là một phần tên tệp, khớp bằng chi_so_ir.khop_nhan.
  Gõ sai một chữ, tệp bị đổi tên, hay tệp có trên đĩa nhưng chưa lập chỉ mục
  thì câu đó LUÔN trượt - và benchmark ghi nhận là "truy hồi kém", không phải
  "nhãn hỏng". Hai lỗi đó sửa ở hai chỗ khác nhau, nên phải tách ra TRƯỚC khi
  chạy benchmark, nhất là trước khi chạy tập test (chạy lại tập test sau khi
  sửa nhãn là nhìn kết quả test hai lần).

KIỂM TRA GÌ - với từng nhãn của từng câu:
  khong_co          không khớp tệp nào, cả trong sổ chỉ mục lẫn trên đĩa -> LỖI
  chua_lap_chi_muc  có trên đĩa nhưng chưa vào chỉ mục -> LỖI, cập nhật chỉ mục
  mo_ho             khớp hơn NGUONG_MO_HO tệp -> CẢNH BÁO: nhãn quá rộng, lấy
                    nhầm tài liệu cũng được tính là đúng
  Thoát mã 1 khi có lỗi, để chặn được trong script chạy benchmark.

KHÔNG KIỂM TRA ĐƯỢC
  - Tài liệu được gắn nhãn có thật sự trả lời được câu hỏi không: phải đọc.
  - Nhãn có THIẾU tài liệu liên quan nào không (sách giáo khoa và bài giảng
    cùng bài là chuyện thường): thiếu nhãn làm điểm bị đánh giá THẤP đi.
  - Câu ngoai_pham_vi có thật sự nằm ngoài kho không.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field

from chi_so_ir import khop_nhan

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_BO_CAU_HOI = os.path.join(THU_MUC_DU_AN, "bo_cau_hoi_benchmark.json")
# PHẢI khớp với main.py / capnhat_tailieu_moi.py. Không import main.py vì nó
# kéo theo langchain và Ollama, trong khi ở đây chỉ cần đọc hai đường dẫn.
DATA_PATH = os.path.abspath(os.getenv(
    "RAG_DATA_PATH",
    os.path.join(THU_MUC_DU_AN, "ollama-rag-desktop", "data_giao_duc"),
))
DUONG_DAN_SO_GHI_CHEP = os.getenv(
    "RAG_LEDGER_PATH", os.path.join(THU_MUC_DU_AN, "data_giao_duc_da_xu_ly.json")
)

NGUONG_MO_HO = 5

KHONG_CO = "khong_co"
CHUA_LAP_CHI_MUC = "chua_lap_chi_muc"
MO_HO = "mo_ho"
LA_LOI = (KHONG_CO, CHUA_LAP_CHI_MUC)


@dataclass
class VanDeNhan:
    cau_hoi: str
    nhom: str
    tap: str
    nhan: str
    loai: str
    tep_khop: list[str] = field(default_factory=list)


def tep_khop(nhan: str, cac_ten_tep: list[str]) -> list[str]:
    """Các tên tệp mà nhãn khớp, theo đúng luật khớp của benchmark."""
    return [ten for ten in cac_ten_tep if khop_nhan(ten, nhan)]


def doi_chieu(
    danh_sach: list[dict],
    tep_chi_muc: list[str],
    tep_tren_dia: list[str],
    nguong_mo_ho: int = NGUONG_MO_HO,
) -> list[VanDeNhan]:
    """Mọi vấn đề của mọi nhãn. Danh sách tên tệp là TÊN, không phải đường dẫn,
    vì benchmark so nhãn với metadata `source_file` - cũng chỉ là tên tệp."""
    van_de: list[VanDeNhan] = []
    for muc in danh_sach:
        for nhan in muc.get("nguon_mong_doi") or []:
            trong_chi_muc = tep_khop(nhan, tep_chi_muc)
            loai = None
            if not trong_chi_muc:
                loai = CHUA_LAP_CHI_MUC if tep_khop(nhan, tep_tren_dia) else KHONG_CO
            elif len(trong_chi_muc) > nguong_mo_ho:
                loai = MO_HO
            if loai:
                van_de.append(VanDeNhan(
                    cau_hoi=muc["cau_hoi"], nhom=muc.get("nhom", ""),
                    tap=muc.get("tap", ""), nhan=nhan, loai=loai,
                    tep_khop=trong_chi_muc or tep_khop(nhan, tep_tren_dia),
                ))
    return van_de


def doc_tep_chi_muc(duong_dan: str) -> list[str] | None:
    """Tên các tệp đã lập chỉ mục, lấy từ sổ ghi chép; None nếu chưa có sổ."""
    try:
        with open(duong_dan, encoding="utf-8") as f:
            so_ghi_chep = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(so_ghi_chep, dict):
        return None
    return sorted({os.path.basename(duong_dan_tep) for duong_dan_tep in so_ghi_chep})


def doc_tep_tren_dia(thu_muc: str) -> list[str]:
    return sorted({ten for _, _, cac_tep in os.walk(thu_muc) for ten in cac_tep})


def main() -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tap", choices=("dev", "test", "tat_ca"), default="tat_ca")
    tham_so = parser.parse_args()

    with open(DUONG_DAN_BO_CAU_HOI, encoding="utf-8") as f:
        danh_sach = [
            muc for muc in json.load(f)["cau_hoi"]
            if tham_so.tap == "tat_ca" or muc.get("tap") == tham_so.tap
        ]

    tep_tren_dia = doc_tep_tren_dia(DATA_PATH)
    tep_chi_muc = doc_tep_chi_muc(DUONG_DAN_SO_GHI_CHEP)
    if tep_chi_muc is None:
        if not tep_tren_dia:
            print(f"Không thấy sổ chỉ mục ({DUONG_DAN_SO_GHI_CHEP}) lẫn kho ({DATA_PATH}).")
            return 2
        print(f"Chưa có sổ chỉ mục {DUONG_DAN_SO_GHI_CHEP}: chỉ đối chiếu với tệp trên đĩa.")
        tep_chi_muc = tep_tren_dia
    print(f"{len(tep_chi_muc)} tệp trong chỉ mục, {len(tep_tren_dia)} tệp trên đĩa, "
          f"{sum(len(m.get('nguon_mong_doi') or []) for m in danh_sach)} nhãn "
          f"của {len(danh_sach)} câu (tập {tham_so.tap}).\n")

    van_de = doi_chieu(danh_sach, tep_chi_muc, tep_tren_dia)
    tieu_de = {
        KHONG_CO: "LỖI - nhãn không khớp tệp nào trong kho",
        CHUA_LAP_CHI_MUC: "LỖI - tệp có trên đĩa nhưng chưa lập chỉ mục",
        MO_HO: f"CẢNH BÁO - nhãn khớp hơn {NGUONG_MO_HO} tệp, quá rộng",
    }
    for loai, dong_dau in tieu_de.items():
        cua_loai = [v for v in van_de if v.loai == loai]
        if not cua_loai:
            continue
        print(f"{dong_dau} ({len(cua_loai)}):")
        for v in cua_loai:
            print(f"  [{v.tap}/{v.nhom}] nhãn {v.nhan!r} - {v.cau_hoi[:70]}")
            for ten in v.tep_khop[:8]:
                print(f"      {ten}")
        print()

    so_loi = sum(1 for v in van_de if v.loai in LA_LOI)
    print("Mọi nhãn đều khớp tệp đã lập chỉ mục." if not so_loi else
          f"{so_loi} nhãn hỏng: sửa nhãn (hoặc cập nhật chỉ mục) trước khi chạy benchmark.")
    return 1 if so_loi else 0


if __name__ == "__main__":
    raise SystemExit(main())
