"""
THAM CHIẾU CHÉO VÀ ĐỊNH NGHĨA THUẬT NGỮ
=======================================
Chunk theo Điều giữ trọn một Điều, nhưng một Điều hiếm khi đọc riêng được:

  - "Sinh viên được miễn học phần, trừ trường hợp quy định tại khoản 2 Điều 9
    Quy chế này" - ngoại lệ nằm ở Điều 9, truy hồi chỉ ra Điều 8;
  - "giáo viên cốt cán được ..." - "giáo viên cốt cán" là ai thì Điều 2. Giải
    thích từ ngữ mới nói.

Mô hình không thấy Điều 9 hay Điều 2 thì trả lời thiếu ngoại lệ, hoặc tự hiểu
thuật ngữ theo nghĩa thường. Module này làm phần đối chiếu chuỗi để
rag_service kéo thêm đúng phần được viện dẫn:

  1. trich_tham_chieu(): các cụm "khoản 2 Điều 9 Quy chế này", "Điều 10 Nghị
     định số 115/2020/NĐ-CP" trong một đoạn.
  2. trich_khoan(): cắt đúng khoản được viện dẫn ra khỏi Điều - đưa nguyên
     Điều vào prompt thì vài nghìn ký tự cho một ý, quá đắt trên CPU.
  3. trich_dinh_nghia() / dinh_nghia_lien_quan(): thuật ngữ của Điều "Giải
     thích từ ngữ" và thuật ngữ nào thật sự dính tới câu hỏi.

GIỚI HẠN CÓ CHỦ ĐÍCH:
  - Tham chiếu tới văn bản chỉ gọi bằng tên ("Điều 5 Luật Giáo dục") bị bỏ
    qua: không có số hiệu thì không chắc là văn bản nào, Luật nào năm nào.
  - Liệt kê gộp ("các Điều 5, 6 và 7") chỉ lấy số đầu.
  - Văn bản sửa đổi: "khoản 2 Điều 5 được sửa đổi như sau" nói về Điều 5 của
    văn bản BỊ sửa, nên tham chiếu không ghi văn bản ở loại văn bản này bị bỏ
    (rag_service quyết định nhờ hồ sơ văn bản; ở đây chỉ trả cờ `tran`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import van_ban_meta
from hieu_luc_bo_sung import nen

# OCR hay mất dấu hoặc tách chữ: "Ðiều", "Dieu", "kho ản".
_DIEU = r"[ĐĐD]\s*i\s*[ềeêé]\s*u"
_KHOAN = r"kho\s*[ảaá]\s*n"
_DIEM = r"đ\s*i\s*[ểeê]\s*m"
MAU_THAM_CHIEU = re.compile(
    rf"(?:\b{_DIEM}\s+([a-zđ])\s*\)?\s*,?\s+)?(?:\b{_KHOAN}\s+(\d{{1,2}})\s*,?\s+)?\b{_DIEU}\s+(\d{{1,3}})\b",
    re.IGNORECASE,
)
_LOAI = r"(?:Thông\s*tư\s*liên\s*tịch|Thông\s*tư|Nghị\s*định|Luật|Quyết\s*định|Nghị\s*quyết|Quy\s*chế|Quy\s*định|Điều\s*lệ)"
# Phần ngay sau "Điều n" nói đó là điều của văn bản nào.
MAU_CUA_NAY = re.compile(rf"^\s*,?\s*(?:của\s+)?{_LOAI}\s+này\b", re.IGNORECASE)
MAU_CUA_VAN_BAN = re.compile(rf"^\s*,?\s*(?:của\s+)?{_LOAI}", re.IGNORECASE)
# "Điều 5." ở đầu dòng là tiêu đề của chính Điều đó, không phải lời viện dẫn.
MAU_TIEU_DE_SAU = re.compile(r"^\s*[.:]")

DO_DAI_TOI_DA = 700
# Thuật ngữ ngắn ("Học sinh") gặp ở mọi đoạn: chỉ kéo định nghĩa khi chính câu
# hỏi nhắc tới. Thuật ngữ dài, đặc thù ("giáo viên cốt cán cấp tỉnh") thì kéo
# cả khi chỉ đoạn được trích nhắc tới.
DO_DAI_THUAT_NGU_TOI_THIEU = 6
DO_DAI_THUAT_NGU_DAC_THU = 12


@dataclass(frozen=True)
class ThamChieu:
    """Một lời viện dẫn trong đoạn.

    so_hieu: văn bản được viện dẫn; None khi là chính văn bản đang đọc.
    tran: không ghi văn bản nào ("theo quy định tại Điều 9") - mặc định là
        chính văn bản này, trừ ở văn bản sửa đổi (xem đầu module).
    """

    dieu: int
    khoan: int | None = None
    diem: str | None = None
    so_hieu: str | None = None
    tran: bool = False
    cum: str = ""


def so_dieu(tieu_de: str | None) -> int | None:
    """'Điều 12. Đăng ký học phần' -> 12."""
    khop = re.match(rf"\s*{_DIEU}\s+(\d{{1,3}})", tieu_de or "", re.IGNORECASE)
    return int(khop.group(1)) if khop else None


def trich_tham_chieu(noi_dung: str, dieu_hien_tai: int | None = None) -> list[ThamChieu]:
    """
    Các lời viện dẫn Điều/khoản trong đoạn, theo thứ tự xuất hiện, không lặp.
    Bỏ: tiêu đề Điều ("\\nĐiều 5. ..."), viện dẫn chính Điều đang đọc, và viện
    dẫn tới văn bản chỉ gọi bằng tên.
    """
    noi_dung = noi_dung or ""
    ket_qua: list[ThamChieu] = []
    da_co: set[tuple] = set()
    for khop in MAU_THAM_CHIEU.finditer(noi_dung):
        diem, khoan, dieu = khop.group(1), khop.group(2), int(khop.group(3))
        sau = noi_dung[khop.end(): khop.end() + 120]
        truoc = noi_dung[max(0, khop.start() - 2): khop.start()]
        dau_dong = khop.start() == 0 or "\n" in truoc
        if dau_dong and not khoan and MAU_TIEU_DE_SAU.match(sau):
            continue
        so_hieu, tran = None, False
        if MAU_CUA_NAY.match(sau):
            pass
        elif MAU_CUA_VAN_BAN.match(sau):
            # "Điều 10 Nghị định số 115/2020/NĐ-CP": số hiệu phải đứng ngay sau
            # tên loại - số hiệu ở xa hơn thuộc về mệnh đề khác.
            cac_so = van_ban_meta.trich_so_hieu(sau[:70])
            if not cac_so:
                continue
            so_hieu = cac_so[0]
        else:
            tran = True
        if so_hieu is None and dieu == dieu_hien_tai:
            continue
        khoa = (dieu, int(khoan) if khoan else None, so_hieu)
        if khoa in da_co:
            continue
        da_co.add(khoa)
        ket_qua.append(ThamChieu(
            dieu=dieu,
            khoan=int(khoan) if khoan else None,
            diem=diem.lower() if diem else None,
            so_hieu=so_hieu,
            tran=tran,
            cum=" ".join(khop.group(0).split()),
        ))
    return ket_qua


# "1. ", "2." ở đầu dòng: số thứ tự khoản (điểm dùng "a)", không lẫn).
MAU_DAU_KHOAN = re.compile(r"(?:^|\n)[ \t]*(\d{1,2})[ \t]*\.(?!\d)")


def _cac_khoan(noi_dung: str) -> list[tuple[int, int, int]]:
    """[(số khoản, đầu, cuối)] theo thứ tự tăng dần liên tiếp 1, 2, 3...

    Chỉ nhận dãy tăng đúng một đơn vị: "2." của một danh sách lồng bên trong
    hay ngày "15. " lạc do OCR không cắt nhầm khoản."""
    moc = []
    can = 1
    for khop in MAU_DAU_KHOAN.finditer(noi_dung):
        if int(khop.group(1)) == can:
            moc.append((can, khop.start() + (1 if noi_dung[khop.start()] == "\n" else 0)))
            can += 1
    return [
        (so, dau, moc[i + 1][1] if i + 1 < len(moc) else len(noi_dung))
        for i, (so, dau) in enumerate(moc)
    ]


def _cat_gon(chuoi: str, do_dai: int = DO_DAI_TOI_DA) -> str:
    chuoi = chuoi.strip()
    if len(chuoi) <= do_dai:
        return chuoi
    return chuoi[:do_dai].rsplit(" ", 1)[0] + " …"


def trich_khoan(noi_dung_dieu: str, khoan: int | None, do_dai: int = DO_DAI_TOI_DA) -> str:
    """Khoản `khoan` của Điều (giữ nguyên chữ để còn tô sáng được trên trang
    gốc); không có số khoản hoặc không tìm ra thì phần đầu của Điều."""
    if khoan:
        for so, dau, cuoi in _cac_khoan(noi_dung_dieu):
            if so == khoan:
                return _cat_gon(noi_dung_dieu[dau:cuoi], do_dai)
    return _cat_gon(noi_dung_dieu, do_dai)


# ============================================================
# ĐỊNH NGHĨA THUẬT NGỮ
# ============================================================
MAU_DIEU_GIAI_THICH = re.compile(r"giaithich(?:tungu|thuatngu|cactungu)")
# "Giáo viên cốt cán là ...", "Học bạ số: là ...", "“Hồ sơ” được hiểu là ..."
MAU_THUAT_NGU = re.compile(
    r"^\s*\d{1,2}\s*\.\s*[“\"']?(?P<tu>[^\n:“”\"']{2,90}?)[”\"']?\s*(?::\s*)?"
    r"(?:là|được hiểu là|bao gồm|gồm)\s",
    re.IGNORECASE,
)


def la_dieu_giai_thich(tieu_de: str | None) -> bool:
    return bool(MAU_DIEU_GIAI_THICH.search(nen(tieu_de or "")))


def trich_dinh_nghia(noi_dung_dieu: str) -> list[tuple[str, str]]:
    """[(thuật ngữ, nguyên văn khoản định nghĩa)] của một Điều "Giải thích từ ngữ"."""
    ket_qua = []
    for _, dau, cuoi in _cac_khoan(noi_dung_dieu):
        khoan = noi_dung_dieu[dau:cuoi].strip()
        khop = MAU_THUAT_NGU.match(khoan)
        if khop:
            ket_qua.append((" ".join(khop.group("tu").split()), khoan))
    return ket_qua


def dinh_nghia_lien_quan(
    dinh_nghia: list[tuple[str, str]], cau_hoi: str, cac_doan: list[str], so_toi_da: int = 3,
) -> list[tuple[str, str, bool]]:
    """
    [(thuật ngữ, khoản định nghĩa, câu hỏi có nhắc tới không)] đáng kéo vào:
    thuật ngữ câu hỏi nhắc tới đứng trước, rồi tới thuật ngữ đặc thù mà đoạn
    được trích nhắc tới. Thuật ngữ dài hơn đứng trước vì cụ thể hơn ("giáo
    viên cốt cán" trước "giáo viên").
    """
    cau_hoi_nen = nen(cau_hoi)
    doan_nen = nen(" ".join(cac_doan))
    trong_cau_hoi, trong_doan = [], []
    for tu, khoan in dinh_nghia:
        tu_nen = nen(tu)
        if len(tu_nen) < DO_DAI_THUAT_NGU_TOI_THIEU:
            continue
        if tu_nen in cau_hoi_nen:
            trong_cau_hoi.append((tu, khoan, True))
        elif len(tu_nen) >= DO_DAI_THUAT_NGU_DAC_THU and tu_nen in doan_nen:
            trong_doan.append((tu, khoan, False))
    theo_do_dai = lambda muc: -len(nen(muc[0]))  # noqa: E731
    return (sorted(trong_cau_hoi, key=theo_do_dai) + sorted(trong_doan, key=theo_do_dai))[:so_toi_da]
