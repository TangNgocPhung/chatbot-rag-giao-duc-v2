"""
ĐỐI TƯỢNG ÁP DỤNG - CÙNG CÂU HỎI, KHÁC CÂU TRẢ LỜI
=================================================
"Giáo viên dạy bao nhiêu tiết một tuần?" có đáp án khác nhau cho tiểu học và
trung học cơ sở; "học phí bao nhiêu?" khác nhau cho trường công lập và ngoài
công lập. Câu hỏi không nói thì truy hồi trả về đoạn của cả hai, và mô hình
hay chọn đại một con số hoặc gộp hai con số thành một.

Luật 5) của prompt đã dặn "câu hỏi mơ hồ thì nói rõ và hỏi lại", nhưng mô hình
không tự biết khi nào bằng chứng THỰC SỰ trải nhiều phạm vi. Module này đếm
việc đó bằng đối chiếu chuỗi, theo kiểu điền ô (slot filling) của hệ hội thoại:

  - ô nào câu hỏi đã điền (cấp học, loại hình trường, vùng);
  - ô nào còn trống mà các khối bằng chứng lại nói về NHIỀU giá trị khác nhau.

Kết quả dùng hai chỗ: dòng PHẠM VI ÁP DỤNG trong prompt (khối nào nói về giá
trị nào, để mô hình trả lời riêng từng trường hợp) và các câu hỏi gợi ý đã điền
sẵn ô còn trống, để người dùng bấm chọn thay vì gõ lại.

Đối tượng áp dụng KHÔNG phải vai trò người dùng (vai_tro.js): phụ huynh hỏi về
giáo viên thì ô "cấp học" vẫn là cấp học của giáo viên đó.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hybrid_retrieval import bo_dau
from phan_loai_giao_duc import CAP_HOC, cap_hoc_nhac_toi

TEN_CHIEU = {"cap_hoc": "cấp học", "loai_hinh": "loại hình trường", "vung": "vùng"}

# Viết không dấu. "ngoài công lập" chứa "công lập" nên phải chặn bằng lookbehind.
LOAI_HINH = {
    "công lập": re.compile(r"(?<!ngoai )\bcong lap\b"),
    "ngoài công lập": re.compile(r"\bngoai cong lap\b|\btu thuc\b|\bdan lap\b"),
}
# Vùng chỉ có một giá trị đặc thù - phần còn lại là "mức chung", không ai gọi tên.
VUNG = {
    "vùng đặc biệt khó khăn": re.compile(
        r"\b(?:dac biet kho khan|vung kho khan|vung cao|mien nui|hai dao|vung bai ngang)\b"
    ),
}
THU_TU = {
    "cap_hoc": list(CAP_HOC),
    "loai_hinh": list(LOAI_HINH),
    "vung": list(VUNG),
}


def _chuoi(van_ban: str) -> str:
    return " " + " ".join(re.sub(r"[^a-z0-9]+", " ", bo_dau(van_ban or "").lower()).split()) + " "


def nhac_toi(van_ban: str) -> dict[str, set[str]]:
    """{chiều: các giá trị đoạn chữ nhắc tới} - chiều không có giá trị thì vắng."""
    chuoi = _chuoi(van_ban)
    ket_qua = {
        "cap_hoc": set(cap_hoc_nhac_toi(van_ban)),
        "loai_hinh": {ten for ten, mau in LOAI_HINH.items() if mau.search(chuoi)},
        "vung": {ten for ten, mau in VUNG.items() if mau.search(chuoi)},
    }
    return {chieu: gia_tri for chieu, gia_tri in ket_qua.items() if gia_tri}


@dataclass
class MoHo:
    """Một ô câu hỏi để trống mà bằng chứng nói về nhiều giá trị.

    gia_tri: {giá trị: [số EVIDENCE nói về nó]}.
    khac_nguon: các khối KHÁC NHAU nói về những giá trị khác nhau - dấu hiệu
        mạnh rằng câu trả lời thật sự tùy trường hợp (một khối liệt kê "trường
        tiểu học, trung học cơ sở" ở điều phạm vi thì chưa chắc).
    """

    chieu: str
    gia_tri: dict[str, list[int]] = field(default_factory=dict)
    khac_nguon: bool = False


def phan_tich(cau_hoi: str, cac_khoi: list[tuple[int, str, list[str] | None]]) -> list[MoHo]:
    """
    cac_khoi: [(số EVIDENCE, nội dung, cấp học gắn cho cả tệp)]. Cấp học của
    tệp chỉ dùng khi đoạn không tự nhắc cấp nào VÀ tệp chỉ thuộc đúng một cấp
    (Điều lệ trường tiểu học) - tệp gắn nhiều cấp thì không nói được đoạn này
    thuộc cấp nào.
    """
    da_dien = nhac_toi(cau_hoi)
    theo_khoi: list[tuple[int, dict[str, set[str]]]] = []
    for so, noi_dung, cap_tep in cac_khoi:
        nhac = nhac_toi(noi_dung)
        if "cap_hoc" not in nhac and cap_tep and len(cap_tep) == 1:
            nhac["cap_hoc"] = set(cap_tep)
        theo_khoi.append((so, nhac))
    ket_qua = []
    for chieu in TEN_CHIEU:
        if chieu in da_dien:
            continue
        gia_tri: dict[str, list[int]] = {}
        tap_cac_khoi = []
        for so, nhac in theo_khoi:
            if chieu in nhac:
                tap_cac_khoi.append(frozenset(nhac[chieu]))
                for ten in nhac[chieu]:
                    gia_tri.setdefault(ten, []).append(so)
        # Vùng đặc thù: chỉ một giá trị cũng đáng nói (mức chung không được gọi tên).
        if len(gia_tri) >= (1 if chieu == "vung" else 2):
            ket_qua.append(MoHo(
                chieu=chieu,
                gia_tri={ten: gia_tri[ten] for ten in THU_TU[chieu] if ten in gia_tri},
                khac_nguon=len(set(tap_cac_khoi)) >= 2,
            ))
    return ket_qua


def _danh_sach(gia_tri: dict[str, list[int]]) -> str:
    return "; ".join(f"{ten} {''.join(f'[{so}]' for so in cac_so)}" for ten, cac_so in gia_tri.items())


def ghi_chu_prompt(cac_mo_ho: list[MoHo]) -> str | None:
    """Dòng PHẠM VI ÁP DỤNG cho prompt: khối nào nói về giá trị nào."""
    if not cac_mo_ho:
        return None
    phan = []
    for mo_ho in cac_mo_ho:
        if mo_ho.chieu == "vung":
            phan.append(
                f"Có quy định riêng cho {_danh_sach(mo_ho.gia_tri)} - nêu cả mức chung và mức riêng."
            )
        else:
            phan.append(f"Câu hỏi chưa nói rõ {TEN_CHIEU[mo_ho.chieu]}; các khối nói về: {_danh_sach(mo_ho.gia_tri)}.")
    return (
        "PHẠM VI ÁP DỤNG: " + " ".join(phan)
        + " Nếu quy định khác nhau theo các trường hợp này thì trả lời riêng từng trường hợp, mỗi con số "
        "kèm đúng trường hợp của nó, không gộp; rồi hỏi lại người dùng thuộc trường hợp nào."
    )


def cau_hoi_lam_ro(cau_hoi: str, cac_mo_ho: list[MoHo], so_toi_da: int = 3) -> list[str]:
    """Câu hỏi gợi ý đã điền sẵn ô còn trống: "Giáo viên dạy bao nhiêu tiết
    một tuần (Tiểu học)?". Chỉ cho ô mà các khối khác nhau nói về giá trị khác
    nhau - ô "vùng" không có giá trị đối lập để chọn nên không gợi ý."""
    goc = (cau_hoi or "").strip().rstrip("?.! ")
    if not goc:
        return []
    for mo_ho in cac_mo_ho:
        if mo_ho.khac_nguon and mo_ho.chieu != "vung":
            return [f"{goc} ({ten})?" for ten in list(mo_ho.gia_tri)[:so_toi_da]]
    return []


def ghep_goi_y(lam_ro: list[str], goi_y: list[str], so_luong: int) -> list[str]:
    """Câu làm rõ đứng trước, gợi ý thường lấp chỗ còn lại; không lặp."""
    if not lam_ro:
        return goi_y
    return lam_ro + [g for g in goi_y if g not in lam_ro][: max(0, so_luong - len(lam_ro))]
