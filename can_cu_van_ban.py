"""CĂN CỨ PHÁP LÝ DÙNG CHUNG CHO CÁC CÔNG CỤ TÍNH
==================================================
Mọi công cụ tính của dự án (tinh_luong.py, dinh_muc_tiet_day.py) đều phải trả
lời được cùng một câu hỏi: con số này lấy ở đâu ra. Phần trả lời đó - một hằng
số gắn với đúng điều khoản quy định nó, và chip nguồn bấm vào mở được tài liệu
- là như nhau ở mọi công cụ, nên nằm ở đây thay vì được chép lại từng nơi.

NGUYÊN TẮC XUYÊN SUỐT: hằng số nào chưa có văn bản trong kho chứng minh thì
đánh dấu `trong_kho=False`, và kết quả phải nói rõ. Thà hiện "chưa có căn cứ
trong kho" còn hơn im lặng đưa ra một con số trông như đã được kiểm chứng.
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote


@dataclass(frozen=True)
class CanCu:
    """Một con số kèm nơi nó được quy định.

    `trong_kho=False` nghĩa là kho tài liệu của chatbot CHƯA có văn bản này -
    con số vẫn dùng được nhưng kết quả phải cảnh báo, không được trình bày như
    thể đã tra được nguồn.
    """

    van_ban: str
    dieu_khoan: str
    trong_kho: bool = True
    ten_tep: str | None = None
    trich: str = ""

    def mo_ta(self) -> str:
        return f"{self.van_ban}, {self.dieu_khoan}"


# ============================================================
# CHUẨN HÓA CÂU HỎI
# ============================================================
def bo_dau(chuoi: str) -> str:
    """Bỏ dấu tiếng Việt và hạ chữ thường, để so mẫu không phụ thuộc bộ gõ.

    Người dùng gõ "tinh luong giao vien THPT hang III bac 1" nhiều không kém
    gõ có dấu - trên điện thoại, trên máy chưa cài bộ gõ, hoặc chỉ vì gõ nhanh.
    Trước đây mỗi công cụ tự liệt kê hai biến thể cho từng cụm từ ("trung học
    phổ thông|trung hoc pho thong"), vừa dài vừa bỏ sót: chỉ cần quên một cụm -
    thường là mấy chữ dẫn như "tính", "giữa kì" - là cả câu rơi khỏi cổng nhận.

    Bỏ dấu một lần rồi viết mẫu không dấu thì cả hai cách gõ đi chung một đường.
    Đổi lại, mọi mẫu so khớp phải viết KHÔNG DẤU - mẫu có dấu sẽ không bao giờ
    khớp nữa, vì chuỗi đem so đã sạch dấu.

    Chữ đ không phân rã được bằng NFD nên phải thay tay; đây cũng là chữ hay
    gặp nhất trong kho văn bản giáo dục ("điều", "đánh giá", "định mức").
    """
    chuoi = unicodedata.normalize("NFD", chuoi)
    chuoi = "".join(c for c in chuoi if unicodedata.category(c) != "Mn")
    return chuoi.replace("đ", "d").replace("Đ", "D").lower()


def _thu_muc_kho() -> str:
    return os.path.abspath(os.getenv(
        "RAG_DATA_PATH",
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "ollama-rag-desktop", "data_giao_duc",
        ),
    ))


_ten_tep_trong_kho: list[str] | None = None


def ten_tep_that(ten: str) -> str | None:
    """Tên tệp thật trong kho ứng với `ten`, hoặc None nếu kho không có.

    Không so khớp nguyên văn vì kho tự đặt lại tên tài liệu khi nạp - một bản
    trong kho đang mang tên bị cắt ngắn so với tiêu đề đầy đủ của Nghị định.
    Ghim cứng tên tệp vào hằng số thì chip nguồn sẽ hỏng lặng lẽ ở lần đổi tên
    tiếp theo, nên ở đây đối chiếu theo tiền tố dài nhất còn trùng.
    """
    global _ten_tep_trong_kho
    if _ten_tep_trong_kho is None:
        _ten_tep_trong_kho = []
        for thu_muc, _, cac_tep in os.walk(_thu_muc_kho()):
            del thu_muc
            _ten_tep_trong_kho.extend(cac_tep)

    chuan = lambda s: unicodedata.normalize("NFC", s).lower()
    muc = chuan(ten)
    if any(chuan(t) == muc for t in _ten_tep_trong_kho):
        return ten

    goc = _bo_duoi(muc)
    ung_vien = [
        t for t in _ten_tep_trong_kho
        if goc.startswith(_bo_duoi(chuan(t))) or _bo_duoi(chuan(t)).startswith(goc)
    ]
    # Tiền tố trùng càng dài thì càng chắc là cùng một văn bản.
    return max(ung_vien, key=len) if ung_vien else None


def _bo_duoi(ten: str) -> str:
    """Bỏ đuôi tệp để so tiền tố. Kho có cả .pdf, .doc và .docx - so nguyên đuôi
    thì một Thông tư bản .doc sẽ không khớp với hằng số ghi tên bản .pdf."""
    goc, _, duoi = ten.rpartition(".")
    return goc if goc and len(duoi) <= 4 else ten


def nguon_tu_can_cu(cac_can_cu: list[CanCu]) -> list[dict]:
    """Chip nguồn cho giao diện, đúng hình dạng mà RAGService._sources trả ra.

    Chỉ liệt kê văn bản CÓ trong kho: chip nguồn bấm vào phải mở được tài liệu,
    còn văn bản ngoài kho đã được nêu ở phần "Căn cứ" kèm nhãn cảnh báo.
    """
    nguon = []
    so = 0
    for cc in cac_can_cu:
        if not cc.trong_kho or not cc.ten_tep:
            continue
        ten = ten_tep_that(cc.ten_tep)
        if ten is None:
            # Kho không có tệp thì thà bỏ chip còn hơn để người dùng bấm vào
            # một liên kết 404; phần "Căn cứ" vẫn nêu đủ số hiệu và điều khoản.
            continue
        so += 1
        nguon.append({
            "evidence": so,
            "name": ten,
            "van_ban": None,
            "validity": None,
            "page": None,
            "chapter": None,
            "article": cc.dieu_khoan,
            "context": cc.van_ban,
            "excerpt": cc.trich,
            "url": f"/api/source?name={quote(cc.ten_tep)}",
            "external": False,
            "kind": "van_ban",
            "time_start": None,
        })
    return nguon
