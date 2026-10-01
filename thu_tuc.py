"""
CÂU HỎI THỦ TỤC HÀNH CHÍNH - HỒ SƠ GỒM GÌ, NỘP Ở ĐÂU, BAO LÂU
=============================================================
"Hồ sơ xin chuyển trường gồm những gì, nộp cho ai, mất bao lâu?" có câu trả
lời nằm trong MỘT Điều, nhưng hai thứ hay làm câu trả lời sai:

  1. Danh sách hồ sơ bị CẮT CỤT. Điều thủ tục dài, bị chia nhiều chunk; truy
     hồi lấy được chunk có câu "Hồ sơ gồm:" và vài giấy tờ đầu, phần còn lại
     nằm ở chunk sau - mô hình liệt kê thiếu mà không biết là thiếu. Người đi
     nộp thiếu một giấy tờ là phải đi lại.
  2. Thời hạn bị nói sai mốc: "15 ngày làm việc KỂ TỪ NGÀY NHẬN ĐỦ HỒ SƠ HỢP
     LỆ" thành "15 ngày" trống trơn.

Module này nhận ra câu hỏi thủ tục và đoạn mở đầu danh sách hồ sơ (để
rag_service kéo chunk kế tiếp của cùng Điều), và trích nguyên văn các cụm thời
hạn để prompt nhắc mô hình giữ đúng mốc tính. Tính ra ngày cụ thể là việc của
tinh_han.py.
"""

from __future__ import annotations

import re

from hybrid_retrieval import bo_dau

MAU_CAU_HOI = re.compile(
    r"\b(?:ho so|thu tuc|trinh tu|giay to|nop (?:o|tai|cho|den|ve)|noi nop|nop o dau|thoi han giai quyet"
    r"|mat bao lau|bao lau thi|bao nhieu ngay|can nhung gi|can chuan bi)\b"
)
MAU_DAU_DANH_SACH = re.compile(
    r"\bho so\b[^.:;]{0,150}?\b(?:gom|bao gom)\b[^.:;]{0,40}:"
)
MAU_THOI_HAN = re.compile(
    r"(?:trong\s+(?:thời\s+hạn|vòng)|chậm\s+nhất(?:\s+là|\s+sau)?|không\s+quá|tối\s+đa|sau)\s+"
    r"(\d{1,3})\s+(ngày\s+làm\s+việc|ngày|tháng|giờ)"
    r"(?:[ ,]+(?:kể\s+từ|tính\s+từ)\s+[^.;,\n]{3,90})?",
    re.IGNORECASE,
)


def _chuoi(van_ban: str) -> str:
    return " ".join(bo_dau(van_ban or "").lower().split())


def la_cau_hoi_thu_tuc(cau_hoi: str) -> bool:
    return bool(MAU_CAU_HOI.search(_chuoi(cau_hoi)))


def mo_dau_danh_sach_ho_so(noi_dung: str) -> bool:
    """Đoạn có câu "Hồ sơ ... gồm:" - danh sách có thể chạy sang chunk sau."""
    return bool(MAU_DAU_DANH_SACH.search(_chuoi(noi_dung)))


def trich_thoi_han(noi_dung: str) -> list[str]:
    """Nguyên văn các cụm thời hạn, giữ cả mốc "kể từ ...": 'trong thời hạn 15
    ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ'."""
    ket_qua = []
    for khop in MAU_THOI_HAN.finditer(noi_dung or ""):
        cum = " ".join(khop.group(0).split()).rstrip(" ,")
        if cum not in ket_qua:
            ket_qua.append(cum)
    return ket_qua


def ghi_chu_prompt(cac_thoi_han: list[tuple[int, str]]) -> str:
    """Dòng THỦ TỤC: khung trả lời dạng danh sách và các thời hạn nguyên văn."""
    ghi_chu = (
        "THỦ TỤC: trả lời theo các mục - Hồ sơ (liệt kê ĐỦ từng giấy tờ đúng như khối nêu, không gộp, "
        "không thêm), Nơi nộp/cơ quan giải quyết, Trình tự, Thời hạn, Căn cứ; mục nào các khối không nêu "
        "thì ghi \"tài liệu không nêu\". Nếu danh sách hồ sơ trong khối dừng giữa chừng thì nói rõ có thể "
        "còn thiếu."
    )
    if cac_thoi_han:
        ghi_chu += (
            " Thời hạn trong các khối (giữ nguyên mốc bắt đầu tính, không rút gọn thành số ngày trần): "
            + "; ".join(f"[{so}] \"{cum}\"" for so, cum in cac_thoi_han) + "."
        )
    return ghi_chu
