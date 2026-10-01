"""
SO SÁNH HAI PHIÊN BẢN VĂN BẢN - "THÔNG TƯ MỚI KHÁC GÌ THÔNG TƯ CŨ?"
=================================================================
Câu hỏi này giáo viên hỏi nhiều nhất mỗi đầu năm học, mà RAG thuần làm kém:
truy hồi lấy vài đoạn GIỐNG câu hỏi nhất, trong khi trả lời đúng phải đặt hai
văn bản cạnh nhau rồi dò từng Điều. Mô hình ngôn ngữ chỉ thấy 4 đoạn thì đoán
khác biệt - đúng loại câu trả lời trông có lý mà sai.

Việc dò được thì làm bằng Python (cùng tinh thần với tinh_luong.py): đồ thị
quan hệ cho biết văn bản nào thay văn bản nào, phần còn lại là đối chiếu chuỗi:

  1. tach_dieu(): gom chunk thành từng Điều. Theo dãy chunk LIỀN NHAU cùng tiêu
     đề, không theo số Điều: Thông tư "ban hành kèm theo Quy chế" thường chung
     một tệp, số Điều 1-3 của Thông tư trùng số Điều 1-3 của Quy chế.
  2. ghep_dieu(): ghép Điều cũ - Điều mới theo độ giống tiêu đề và nội dung
     (Jaccard trên 4-gram ký tự của chuỗi đã nén - bền với OCR chèn khoảng
     trắng). Ghép THAM LAM: cặp giống nhất trước, hòa thì cặp gần vị trí hơn.
     Thuật toán Hungarian cho tổng điểm tối ưu (O(n^3)), nhưng giữa hai phiên
     bản văn bản, mỗi Điều thường có một bản đối ứng rõ ràng nên tham lam cho
     cùng kết quả mà đơn giản hơn - và không cần thêm scipy.
  3. so_sanh_khoan(): trong mỗi cặp Điều, khoản nào mới/bỏ/sửa và số liệu nào
     đổi ("25 tín chỉ → 30 tín chỉ").

GIỚI HẠN: Điều bị đổi tên VÀ viết lại gần hết sẽ hiện thành một Điều "bỏ" và
một Điều "mới". Kết quả là đối chiếu chữ, không phải đánh giá pháp lý - câu trả
lời nói rõ điều này.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tham_chieu
from hieu_luc_bo_sung import nen
from hybrid_retrieval import bo_dau

# Viết không dấu: so trên câu hỏi đã bỏ dấu. Hai mức:
#   - hỏi thẳng cái MỚI ("có gì mới", "thay đổi gì"): nêu một văn bản là đủ;
#   - so sánh chung ("khác gì", "so sánh"): "Học bạ số theo Thông tư 15/2026
#     khác gì học bạ giấy?", "So sánh Điều 5 và Điều 6 Thông tư 15/2026" không
#     phải hỏi hai phiên bản - cần hai số hiệu, hoặc câu nói rõ mới/cũ.
MAU_Y_DINH_MOI = re.compile(
    r"\b(?:diem moi|co gi moi|nhung gi moi|nhung diem moi|noi dung moi"
    r"|thay doi (?:gi|nhung gi|the nao|ra sao|nhung diem nao|nhung noi dung nao))\b"
)
MAU_Y_DINH = re.compile(
    r"\b(?:khac gi|co gi khac|khac nhau|khac biet|khac (?:the nao|ra sao|o (?:diem|cho) nao)"
    r"|so sanh|moi so voi|khac so voi|khac voi)\b"
)
# Không nêu số hiệu thì phải nói rõ là hỏi về hai phiên bản: "so sánh học phí
# công lập và tư thục" cũng có chữ "so sánh".
MAU_HAI_PHIEN_BAN = re.compile(
    r"\bmoi\b.*\bcu\b|\bcu\b.*\bmoi\b|\bban (?:cu|moi|truoc)\b|\btruoc day\b|\bphien ban\b|\bthay the\b"
)

K_GRAM = 4
NGUONG_GHEP = 0.3        # dưới mức này thì không coi là cùng một Điều
NGUONG_GIU_NGUYEN = 0.9  # từ mức này (và không đổi số liệu) thì coi như giữ nguyên
SO_DIEU_CHI_TIET = 3
SO_DONG_BANG = 12
DO_DAI_TRICH = 180


def _chuoi_y_dinh(cau_hoi: str) -> str:
    return " ".join(bo_dau(cau_hoi or "").lower().split())


def muc_y_dinh(cau_hoi: str) -> str | None:
    """"moi" (hỏi thẳng cái mới), "so_sanh" (so sánh chung) hoặc None."""
    chuoi = _chuoi_y_dinh(cau_hoi)
    if MAU_Y_DINH_MOI.search(chuoi):
        return "moi"
    return "so_sanh" if MAU_Y_DINH.search(chuoi) else None


def la_cau_hoi_so_sanh(cau_hoi: str) -> bool:
    return muc_y_dinh(cau_hoi) is not None


def noi_hai_phien_ban(cau_hoi: str) -> bool:
    return bool(MAU_HAI_PHIEN_BAN.search(_chuoi_y_dinh(cau_hoi)))


@dataclass
class Dieu:
    tieu_de: str
    noi_dung: str
    tep: str
    vi_tri: int  # thứ tự trong văn bản, để hòa điểm thì ưu tiên cặp gần vị trí
    so_trang: int | None = None
    _gram: set = field(default_factory=set, repr=False)
    _gram_tieu_de: set = field(default_factory=set, repr=False)

    def __post_init__(self):
        self._gram = _gram(self.noi_dung)
        self._gram_tieu_de = _gram(self.tieu_de)


def _gram(chuoi: str) -> set:
    chuoi = nen(chuoi)
    return {chuoi[i: i + K_GRAM] for i in range(max(0, len(chuoi) - K_GRAM + 1))}


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def tach_dieu(cac_doan: list) -> list[Dieu]:
    """Các Điều của một tệp, theo thứ tự chunk (thứ tự lập chỉ mục). Phần mở
    đầu không thuộc Điều nào (quốc hiệu, căn cứ) thì bỏ."""
    ket_qua: list[Dieu] = []
    tieu_de_truoc, phan, trang, doan_dau = None, [], None, None
    for doan in list(cac_doan) + [None]:
        tieu_de = doan.metadata.get("article") if doan is not None else None
        if phan and (doan is None or tieu_de != tieu_de_truoc):
            ket_qua.append(Dieu(
                tieu_de_truoc, "\n".join(phan), doan_dau.metadata.get("source_file"), len(ket_qua), trang,
            ))
            phan = []
        if doan is None or not tieu_de:
            tieu_de_truoc = None
            continue
        if not phan:
            doan_dau, trang = doan, doan.metadata.get("so_trang")
        # Chunk gối đầu (Điều dài bị cắt) có thể lặp nguyên văn: bỏ bản lặp.
        if not phan or doan.page_content != phan[-1]:
            phan.append(doan.page_content)
        tieu_de_truoc = tieu_de
    return ket_qua


def do_giong(a: Dieu, b: Dieu) -> float:
    return 0.3 * _jaccard(a._gram_tieu_de, b._gram_tieu_de) + 0.7 * _jaccard(a._gram, b._gram)


def ghep_dieu(cu: list[Dieu], moi: list[Dieu]) -> list[tuple[Dieu | None, Dieu | None, float]]:
    """[(Điều cũ, Điều mới, độ giống)] - None một bên là Điều bị bỏ / Điều mới.
    Thứ tự: theo văn bản mới, các Điều bị bỏ xếp cuối theo văn bản cũ."""
    so_cu, so_moi = max(1, len(cu)), max(1, len(moi))
    ung_vien = []
    for i, a in enumerate(cu):
        for j, b in enumerate(moi):
            diem = do_giong(a, b)
            if diem >= NGUONG_GHEP:
                lech = abs(i / so_cu - j / so_moi)
                ung_vien.append((-diem, lech, i, j))
    ung_vien.sort()
    cap_cua_moi: dict[int, tuple[int, float]] = {}
    da_dung_cu: set[int] = set()
    for am_diem, _, i, j in ung_vien:
        if i in da_dung_cu or j in cap_cua_moi:
            continue
        da_dung_cu.add(i)
        cap_cua_moi[j] = (i, -am_diem)
    ket_qua = [
        (cu[cap_cua_moi[j][0]] if j in cap_cua_moi else None, b, cap_cua_moi.get(j, (None, 0.0))[1])
        for j, b in enumerate(moi)
    ]
    ket_qua += [(a, None, 0.0) for i, a in enumerate(cu) if i not in da_dung_cu]
    return ket_qua


# ============================================================
# MỨC KHOẢN VÀ SỐ LIỆU
# ============================================================
# "25 tín chỉ", "12,5%", "3 năm" - con số kèm đơn vị đứng sau nó. Số đứng sau
# "Điều/khoản/ngày/năm/lớp/số" là số thứ tự, ngày tháng hay số hiệu, không phải
# số liệu; số dính dấu "/" là ngày hoặc số hiệu.
MAU_SO_DON_VI = re.compile(
    r"(?<![\w/.,])(\d+(?:[.,]\d+)?)(?![\d/])\s*(%|[^\W\d_]+(?:[ \t]+[^\W\d_]+)?)"
)
TU_DUNG_TRUOC_SO_THU_TU = {
    "dieu", "khoan", "diem", "chuong", "muc", "so", "ngay", "thang", "nam", "lop",
    "mau", "phu", "luc", "tiet", "bai",
}


def cum_so_lieu(chuoi: str) -> list[tuple[str, str]]:
    """[(cụm nguyên văn, khóa đơn vị)] - '25 tín chỉ' -> ('25 tín chỉ', 'tin')."""
    ket_qua = []
    for khop in MAU_SO_DON_VI.finditer(chuoi or ""):
        truoc = bo_dau(chuoi[max(0, khop.start() - 12): khop.start()]).lower().split()
        if truoc and truoc[-1] in TU_DUNG_TRUOC_SO_THU_TU:
            continue
        don_vi = khop.group(2)
        ket_qua.append((
            f"{khop.group(1)}{'' if don_vi == '%' else ' '}{don_vi}",
            bo_dau(don_vi.split()[0]).lower(),
        ))
    return ket_qua


def thay_doi_so_lieu(cu: str, moi: str) -> list[str]:
    """'25 tín chỉ → 30 tín chỉ' khi cùng đơn vị một bên bỏ một bên thêm;
    còn lại 'bỏ: ...' / 'thêm: ...'."""
    con_cu = [c for c in cum_so_lieu(cu)]
    con_moi = [c for c in cum_so_lieu(moi)]
    for cum in list(con_cu):
        if cum in con_moi:
            con_cu.remove(cum)
            con_moi.remove(cum)
    ket_qua = []
    for cum_cu, don_vi in list(con_cu):
        cung_don_vi = [c for c in con_moi if c[1] == don_vi]
        if cung_don_vi:
            ket_qua.append(f"{cum_cu} → {cung_don_vi[0][0]}")
            con_cu.remove((cum_cu, don_vi))
            con_moi.remove(cung_don_vi[0])
    ket_qua += [f"bỏ {c}" for c, _ in con_cu] + [f"thêm {c}" for c, _ in con_moi]
    return ket_qua


@dataclass
class SoSanhKhoan:
    them: list[str] = field(default_factory=list)            # nguyên văn khoản mới
    bo: list[str] = field(default_factory=list)              # nguyên văn khoản bỏ
    sua: list[tuple[str, str]] = field(default_factory=list)  # (cũ, mới)
    so_lieu: list[str] = field(default_factory=list)

    @property
    def co_thay_doi(self) -> bool:
        return bool(self.them or self.bo or self.sua or self.so_lieu)


def _tach_khoan(noi_dung: str) -> list[str]:
    cac = tham_chieu.cac_khoan(noi_dung)
    return [noi_dung[dau:cuoi].strip() for _, dau, cuoi in cac] or [noi_dung.strip()]


def so_sanh_khoan(cu: str, moi: str) -> SoSanhKhoan:
    """Ghép khoản cũ - khoản mới (tham lam như ghep_dieu) rồi đếm khác biệt.
    Không dựa vào số thứ tự khoản: chèn một khoản là mọi số phía sau lệch."""
    khoan_cu, khoan_moi = _tach_khoan(cu), _tach_khoan(moi)
    gram_cu, gram_moi = [_gram(k) for k in khoan_cu], [_gram(k) for k in khoan_moi]
    cap = sorted(
        (-_jaccard(a, b), i, j)
        for i, a in enumerate(gram_cu) for j, b in enumerate(gram_moi)
        if _jaccard(a, b) >= NGUONG_GHEP
    )
    da_cu, da_moi, ket_qua = set(), set(), SoSanhKhoan()
    for am_diem, i, j in cap:
        if i in da_cu or j in da_moi:
            continue
        da_cu.add(i)
        da_moi.add(j)
        so_lieu = thay_doi_so_lieu(khoan_cu[i], khoan_moi[j])
        ket_qua.so_lieu += so_lieu
        if -am_diem < NGUONG_GIU_NGUYEN or so_lieu:
            ket_qua.sua.append((khoan_cu[i], khoan_moi[j]))
    ket_qua.bo = [k for i, k in enumerate(khoan_cu) if i not in da_cu]
    ket_qua.them = [k for j, k in enumerate(khoan_moi) if j not in da_moi]
    return ket_qua


# ============================================================
# KẾT QUẢ
# ============================================================
@dataclass
class KetQuaSoSanh:
    giu_nguyen: list[tuple[Dieu, Dieu]] = field(default_factory=list)
    sua: list[tuple[Dieu, Dieu, float, SoSanhKhoan]] = field(default_factory=list)
    moi: list[Dieu] = field(default_factory=list)
    bo: list[Dieu] = field(default_factory=list)


def so_sanh(cac_dieu_cu: list[Dieu], cac_dieu_moi: list[Dieu]) -> KetQuaSoSanh:
    ket_qua = KetQuaSoSanh()
    for a, b, diem in ghep_dieu(cac_dieu_cu, cac_dieu_moi):
        if a is None:
            ket_qua.moi.append(b)
        elif b is None:
            ket_qua.bo.append(a)
        else:
            khoan = so_sanh_khoan(a.noi_dung, b.noi_dung)
            if _jaccard(a._gram, b._gram) >= NGUONG_GIU_NGUYEN and not khoan.so_lieu:
                ket_qua.giu_nguyen.append((a, b))
            else:
                ket_qua.sua.append((a, b, diem, khoan))
    # Điều đổi nhiều nhất lên đầu: người hỏi "có gì mới" cần cái đó trước.
    ket_qua.sua.sort(key=lambda m: (-len(m[3].so_lieu), m[2]))
    return ket_qua


def _ngan(chuoi: str, do_dai: int = DO_DAI_TRICH) -> str:
    chuoi = " ".join((chuoi or "").split())
    return chuoi if len(chuoi) <= do_dai else chuoi[:do_dai].rsplit(" ", 1)[0] + "…"


def _o_bang(chuoi: str) -> str:
    return _ngan(chuoi, 70).replace("|", "/")


def dinh_dang(ten_moi: str, ten_cu: str, ket_qua: KetQuaSoSanh, mo_dau: str = "") -> str:
    """Câu trả lời markdown: tóm tắt, Điều mới/bỏ, bảng Điều sửa, chi tiết vài
    Điều đổi nhiều nhất. [1] là văn bản mới, [2] là văn bản cũ."""
    dong = [f"**So sánh {ten_moi} [1] với {ten_cu} [2]**", ""]
    if mo_dau:
        dong += [mo_dau, ""]
    dong.append(
        f"Đối chiếu từng Điều: **{len(ket_qua.sua)}** Điều có thay đổi, **{len(ket_qua.moi)}** Điều mới, "
        f"**{len(ket_qua.bo)}** Điều không còn, {len(ket_qua.giu_nguyen)} Điều gần như giữ nguyên."
    )
    if ket_qua.moi:
        dong += ["", "**Điều mới** [1]:"] + [f"- {_ngan(d.tieu_de, 120)}" for d in ket_qua.moi[:SO_DONG_BANG]]
    if ket_qua.bo:
        dong += ["", "**Điều không còn trong văn bản mới** [2]:"] + [
            f"- {_ngan(d.tieu_de, 120)}" for d in ket_qua.bo[:SO_DONG_BANG]
        ]
    if ket_qua.sua:
        dong += ["", "**Điều có thay đổi:**", "", "| Văn bản mới [1] | Văn bản cũ [2] | Thay đổi |", "|---|---|---|"]
        for a, b, _, khoan in ket_qua.sua[:SO_DONG_BANG]:
            phan = []
            if khoan.so_lieu:
                phan.append("số liệu: " + "; ".join(khoan.so_lieu[:3]))
            if khoan.them:
                phan.append(f"thêm {len(khoan.them)} khoản")
            if khoan.bo:
                phan.append(f"bỏ {len(khoan.bo)} khoản")
            if khoan.sua and not khoan.so_lieu:
                phan.append(f"sửa {len(khoan.sua)} khoản")
            dong.append(f"| {_o_bang(b.tieu_de)} | {_o_bang(a.tieu_de)} | {_o_bang('; '.join(phan) or 'sửa câu chữ')} |")
        if len(ket_qua.sua) > SO_DONG_BANG:
            dong.append(f"\n…và {len(ket_qua.sua) - SO_DONG_BANG} Điều khác có thay đổi.")
        for a, b, _, khoan in ket_qua.sua[:SO_DIEU_CHI_TIET]:
            dong += ["", f"**{_ngan(b.tieu_de, 120)}**"]
            for cu, moi in khoan.sua[:2]:
                dong.append(f"- Trước [2]: «{_ngan(cu)}»\n  Nay [1]: «{_ngan(moi)}»")
            for moi in khoan.them[:2]:
                dong.append(f"- Thêm [1]: «{_ngan(moi)}»")
            for cu in khoan.bo[:2]:
                dong.append(f"- Bỏ [2]: «{_ngan(cu)}»")
    dong += [
        "",
        "_Bảng do máy đối chiếu chữ giữa hai văn bản (ghép Điều theo tiêu đề và nội dung), không "
        "phải đánh giá pháp lý: Điều bị đổi tên và viết lại gần hết có thể hiện thành một Điều bỏ "
        "và một Điều mới. Hãy đọc nguyên văn ở nguồn [1], [2] trước khi áp dụng._",
    ]
    return "\n".join(dong)
