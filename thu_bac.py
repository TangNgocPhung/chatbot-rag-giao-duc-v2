"""
THỨ BẬC HIỆU LỰC PHÁP LÝ CỦA VĂN BẢN
====================================
Kho trộn Luật, Nghị định, Thông tư với công văn, quyết định cá biệt. Đồ thị
hiệu lực (quan_he_van_ban) và trọng số "văn bản mới hơn" (hybrid_retrieval)
coi chúng ngang nhau, trong khi:

  - văn bản cấp dưới không sửa, không thay được văn bản cấp trên: một công văn
    2026 "hướng dẫn" khác Thông tư 2020 thì Thông tư vẫn là căn cứ;
  - công văn, quyết định cá biệt KHÔNG phải văn bản quy phạm pháp luật: chúng
    hướng dẫn thực hiện, không đặt ra quy định mới.

Cấp được suy từ SỐ HIỆU, không từ nội dung: số hiệu văn bản quy phạm luôn có
năm ban hành ("81/2021/NĐ-CP"), còn công văn và quyết định cá biệt thì không
("5512/BGDĐT-GDTrH", "527/QĐ-TTg"). Đây là quy định về thể thức (Luật Ban hành
VBQPPL 2015 - cần đối chiếu điều tương ứng của Luật 2025), nên là dấu hiệu
chắc hơn mọi từ khóa trong thân bài.

Thứ bậc dùng ở mức THÔ - đủ cho việc so cao/thấp, không thay được việc tra
cứu pháp lý:
  1 Luật, Nghị quyết của Quốc hội
  2 Pháp lệnh, Nghị quyết của Ủy ban Thường vụ Quốc hội
  3 Nghị định, Nghị quyết của Chính phủ
  4 Quyết định (quy phạm) của Thủ tướng
  5 Thông tư, Thông tư liên tịch; Quyết định quy phạm của Bộ trưởng (trước 2009)
  6 Nghị quyết HĐND, Quyết định UBND (quy phạm)
  9 Văn bản hành chính: công văn, quyết định cá biệt, chỉ thị, kế hoạch
Số càng nhỏ, hiệu lực càng cao. Không suy được (số hiệu lạ, tài liệu không có
số hiệu như sách giáo khoa) thì None - không so sánh gì cả.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CAP_HANH_CHINH = 9

TEN_CAP = {
    1: "Luật/Nghị quyết của Quốc hội",
    2: "văn bản của Ủy ban Thường vụ Quốc hội",
    3: "Nghị định/Nghị quyết của Chính phủ",
    4: "Quyết định của Thủ tướng",
    5: "Thông tư/văn bản quy phạm cấp Bộ",
    6: "văn bản quy phạm của địa phương",
    CAP_HANH_CHINH: "văn bản hành chính",
}

# "81/2021/NĐ-CP" -> (năm, loại, cơ quan); "43/2019/QH14" -> (năm, "QH14", "").
MAU_CO_NAM = re.compile(r"^\d+/(\d{4})/([^-–]+)(?:[-–](.+))?$")
MAU_KHONG_NAM = re.compile(r"^\d+/([^/]+)$")


@dataclass(frozen=True)
class ThuBac:
    cap: int
    ten: str  # "Thông tư", "văn bản hành chính"...

    @property
    def la_qppl(self) -> bool:
        return self.cap < CAP_HANH_CHINH


def thu_bac(so_hieu: str | None) -> ThuBac | None:
    """'81/2021/NĐ-CP' -> ThuBac(3, ...); '5512/BGDĐT-GDTrH' -> ThuBac(9, ...)."""
    so_hieu = (so_hieu or "").strip()
    if khop := MAU_CO_NAM.match(so_hieu):
        loai, co_quan = khop.group(2).upper(), (khop.group(3) or "").upper()
        cap = None
        if loai.startswith("QH"):
            cap = 1
        elif co_quan.startswith("UBTVQH"):
            cap = 2
        elif co_quan == "CP":
            cap = 3
        elif loai == "QĐ" and co_quan == "TTG":
            cap = 4
        elif loai in ("TT", "TTLT") or (loai == "QĐ" and co_quan.startswith("B")):
            cap = 5
        elif "HĐND" in co_quan or "UBND" in co_quan:
            cap = 6
        elif loai == "CT":
            # Chỉ thị không phải văn bản quy phạm, kể cả khi số hiệu có năm.
            cap = CAP_HANH_CHINH
        return ThuBac(cap, TEN_CAP[cap]) if cap else None
    if MAU_KHONG_NAM.match(so_hieu):
        return ThuBac(CAP_HANH_CHINH, TEN_CAP[CAP_HANH_CHINH])
    return None


def thap_hon(a: str | None, b: str | None) -> bool:
    """Văn bản `a` có hiệu lực pháp lý THẤP hơn hẳn `b` (cả hai suy được cấp)."""
    cap_a, cap_b = thu_bac(a), thu_bac(b)
    return bool(cap_a and cap_b and cap_a.cap > cap_b.cap)


# Văn bản hành chính gọi theo mã loại đứng đầu ký hiệu ("123/KH-SGDĐT");
# ký hiệu mở đầu bằng tên cơ quan ("5512/BGDĐT-GDTrH") là công văn.
TEN_HANH_CHINH = {
    "QĐ": "Quyết định", "CT": "Chỉ thị", "KH": "Kế hoạch", "HD": "Hướng dẫn",
    "TB": "Thông báo", "CĐ": "Công điện", "BC": "Báo cáo", "TTR": "Tờ trình",
}


def ten_loai(so_hieu: str | None, loai: str | None = None) -> str | None:
    """Tên loại để hiện: lấy từ van_ban_meta nếu có, không thì theo mã ký hiệu."""
    muc = thu_bac(so_hieu)
    if muc is None:
        return loai
    if muc.la_qppl:
        return loai or muc.ten
    ky_hieu = so_hieu.rsplit("/", 1)[-1]
    ma = re.split(r"[-–]", ky_hieu, maxsplit=1)[0].upper()
    return TEN_HANH_CHINH.get(ma) or ("Công văn" if "-" in ky_hieu or "–" in ky_hieu else loai or "Văn bản")


def mo_ta(loai: str | None, so_hieu: str | None) -> str | None:
    """Dòng "Loại:" cho prompt: 'Nghị định - văn bản quy phạm pháp luật',
    'Công văn - văn bản hành chính, không phải văn bản quy phạm pháp luật'."""
    muc = thu_bac(so_hieu)
    if muc is None:
        return None
    ten = ten_loai(so_hieu, loai)
    if muc.la_qppl:
        return f"{ten} - văn bản quy phạm pháp luật"
    return f"{ten} - văn bản hành chính, không phải văn bản quy phạm pháp luật"
