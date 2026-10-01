"""
PHÂN CẤP CHO ĐỊA PHƯƠNG VÀ CƠ SỞ - "BỘ CHỈ QUY ĐỊNH KHUNG"
=========================================================
Nhiều câu hỏi không có MỘT đáp số toàn quốc: Nghị định chỉ quy định khung học
phí, còn "mức thu cụ thể do Hội đồng nhân dân cấp tỉnh quyết định"; Điều lệ
trường cho "Hiệu trưởng quyết định" số lớp mỗi khối. Chatbot trích khung rồi
trình bày như mức áp dụng cho mọi nơi là sai với tỉnh, với trường của người
hỏi - và nếu không tìm ra con số thì lại trả lời "không tìm thấy", trong khi
câu trả lời đúng là "pháp luật trung ương giao việc này cho cơ quan X".

Module này nhận ra câu GIAO QUYỀN trong đoạn được trích, để rag_service báo cho
mô hình (nêu khung nếu có, nói rõ mức cụ thể do ai quyết định) và cho người đọc.

Chỉ nhận dạng giao quyền: "do / giao / ủy quyền cho / theo quy định của" + cơ
quan + "quyết định / quy định / ban hành / phê duyệt". KHÔNG nhận "Ủy ban nhân
dân cấp tỉnh có trách nhiệm ..." - các Điều "Trách nhiệm" liệt kê nhiệm vụ của
từng cơ quan chứ không giao quyền đặt ra mức.

Danh mục cơ quan chỉ gồm địa phương và cơ sở giáo dục: "do Bộ trưởng quy định"
thì văn bản của Bộ thường đã có trong kho, không phải trường hợp này.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hybrid_retrieval import bo_dau

# (tên hiển thị, mẫu trên chữ đã bỏ dấu, chữ thường, gộp khoảng trắng). Cụ thể
# đứng trước: "giám đốc sở giáo dục" phải khớp Sở chứ không khớp "giám đốc".
CO_QUAN = [
    ("Hội đồng nhân dân cấp tỉnh", r"(?:hoi dong nhan dan|hdnd)(?: cap)? tinh"),
    ("Ủy ban nhân dân cấp tỉnh", r"(?:uy ban nhan dan|ubnd)(?: cap)? tinh"),
    ("Ủy ban nhân dân cấp xã/huyện", r"(?:uy ban nhan dan|ubnd)(?: cap)? (?:xa|huyen)"),
    ("Sở Giáo dục và Đào tạo", r"(?:giam doc )?so giao duc va dao tao|so gd ?dt"),
    ("Hội đồng trường", r"hoi dong (?:truong|dai hoc)"),
    ("người đứng đầu cơ sở giáo dục", (
        r"hieu truong|thu truong (?:co so|don vi)(?: giao duc)?|nguoi dung dau (?:co so|don vi)"
        r"|giam doc (?:trung tam|co so|dai hoc)"
    )),
]
_CO_QUAN = "|".join(f"(?P<cq{i}>{mau})" for i, (_, mau) in enumerate(CO_QUAN))
MAU_GIAO_QUYEN = re.compile(
    rf"\b(?P<dan>do|giao(?: cho)?|uy quyen cho|theo quy dinh cua|theo quyet dinh cua|duoc)\s+"
    rf"(?:{_CO_QUAN})\b(?P<sau>[^.;]{{0,60}})"
)
MAU_DONG_TU = re.compile(r"\b(?:quyet dinh|quy dinh|ban hanh|phe duyet|xem xet quyet dinh)\b")
MAU_KHUNG = re.compile(
    r"\b(?:khung|toi da|toi thieu|muc tran|tran hoc phi|khong vuot qua|khong thap hon|khong cao hon"
    r"|trong pham vi)\b|\btu \d[\d.,]* .{0,30}\bden \d"
)
# Cặp từ quá chung để coi là "cùng chủ đề" giữa câu hỏi và câu giao quyền.
CAP_TU_CHUNG = {
    "quy dinh", "quyet dinh", "bao nhieu", "giao duc", "dao tao", "co so", "cap tinh", "nhan dan",
    "uy ban", "hoi dong", "theo quy", "thuc hien", "nhu the", "the nao", "la gi", "duoc khong",
    "hien nay", "hien hanh", "co duoc", "phai khong",
}
DO_DAI_TRICH = 300


@dataclass(frozen=True)
class PhanCap:
    co_quan: str
    trich: str       # nguyên văn câu giao quyền (gọn khoảng trắng)
    co_khung: bool   # câu nêu khung/mức trần: trả lời được khung, không được mức cụ thể


def _chuan(chuoi: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9%]+", " ", bo_dau(chuoi or "").lower()).split())


def _cac_cau(noi_dung: str) -> list[str]:
    # Cắt ở dấu chấm/chấm phẩy và ở đầu khoản/điểm; KHÔNG cắt ở mọi xuống dòng
    # (OCR ngắt dòng giữa câu).
    return [c for c in re.split(r"(?<=[.;:])\s+|\n(?=\s*(?:\d{1,2}\.|[a-zđ]\)|[-–+]))", noi_dung or "") if c.strip()]


def trich_phan_cap(noi_dung: str) -> list[PhanCap]:
    """Các câu giao quyền trong đoạn, mỗi cặp (cơ quan, câu) một lần."""
    ket_qua, da_co = [], set()
    for cau in _cac_cau(noi_dung):
        chuan = _chuan(cau)
        for khop in MAU_GIAO_QUYEN.finditer(chuan):
            dan = khop.group("dan")
            # "theo quy định của X" tự nó đã là giao quyền; "do/giao/được X"
            # phải có động từ quyết định/quy định ngay sau.
            if not dan.startswith("theo") and not MAU_DONG_TU.search(khop.group("sau")):
                continue
            # "được Hiệu trưởng ... quyết định" thì được; "được Sở ..." mà
            # không phải quyết định thì đã bị chặn ở trên.
            co_quan = next(CO_QUAN[i][0] for i in range(len(CO_QUAN)) if khop.group(f"cq{i}"))
            trich = " ".join(cau.split())
            if len(trich) > DO_DAI_TRICH:
                trich = trich[:DO_DAI_TRICH].rsplit(" ", 1)[0] + "…"
            if (co_quan, trich) not in da_co:
                da_co.add((co_quan, trich))
                ket_qua.append(PhanCap(co_quan, trich, bool(MAU_KHUNG.search(chuan))))
    return ket_qua


def _cap_tu(chuoi: str) -> set[str]:
    tu = _chuan(chuoi).split()
    return {f"{a} {b}" for a, b in zip(tu, tu[1:])} - CAP_TU_CHUNG


def lien_quan(cau_hoi: str, phan_cap: PhanCap) -> bool:
    """Câu giao quyền nói về đúng thứ câu hỏi hỏi: có chung ít nhất một cặp
    từ có nghĩa ("hoc phi"). Một đoạn về học phí có thể chứa câu giao quyền về
    việc khác (miễn giảm, thủ tục) - báo cả những câu đó chỉ làm nhiễu."""
    return bool(_cap_tu(cau_hoi) & _cap_tu(phan_cap.trich))


def ghi_chu_prompt(cac_phan_cap: list[tuple[int, PhanCap]]) -> str | None:
    """Dòng PHÂN CẤP cho prompt: [(số EVIDENCE, câu giao quyền)]."""
    if not cac_phan_cap:
        return None
    cac_cau = " ".join(f'Khối [{so}]: "{pc.trich}" ({pc.co_quan}).' for so, pc in cac_phan_cap)
    co_khung = any(pc.co_khung for _, pc in cac_phan_cap)
    return (
        "PHÂN CẤP: " + cac_cau + " Đây là việc văn bản trung ương giao cho cơ quan nêu trên quyết "
        "định, nên không có một mức chung cho mọi địa phương/cơ sở: "
        + ("nêu khung (tối đa/tối thiểu) theo khối, rồi nói rõ mức cụ thể do cơ quan đó quyết định; "
           if co_khung else "nói rõ việc này do cơ quan đó quyết định; ")
        + "không trình bày con số nào như mức áp dụng ở mọi nơi. Người hỏi nêu địa phương/cơ sở cụ "
        "thể mà không khối nào là văn bản của nơi đó thì nói rõ tài liệu hiện có chưa có văn bản ấy."
    )


def canh_bao(cac_phan_cap: list[tuple[int, PhanCap]]) -> list[dict]:
    """Cảnh báo cho giao diện, cùng dạng quan_he_van_ban.SoQuanHe.canh_bao()."""
    ket_qua, da_bao = [], set()
    for so, pc in cac_phan_cap:
        if (so, pc.co_quan) in da_bao:
            continue
        da_bao.add((so, pc.co_quan))
        ket_qua.append({
            "evidence": so,
            "loai": "phan_cap",
            "thong_bao": (
                f"Nguồn [{so}] giao cho {pc.co_quan} quyết định"
                + (" trong khung nêu ở nguồn" if pc.co_khung else "")
                + " - mức áp dụng ở địa phương, cơ sở của bạn có thể khác; hãy đối chiếu văn bản của nơi đó."
            ),
        })
    return ket_qua
