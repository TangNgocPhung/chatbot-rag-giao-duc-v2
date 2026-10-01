"""CÔNG CỤ TÍNH HẠN - "NỘP HỒ SƠ NGÀY 25/9, 15 NGÀY LÀM VIỆC THÌ ĐẾN NGÀY NÀO?"
=============================================================================
Thủ tục hành chính trong giáo dục (chuyển trường, công nhận văn bằng, cấp
phép...) đều có thời hạn kiểu "trong thời hạn 15 ngày làm việc kể từ ngày nhận
đủ hồ sơ hợp lệ". Đếm ngày làm việc qua cuối tuần và ngày lễ là việc mô hình
ngôn ngữ làm sai rất thường xuyên - cùng lý lẽ với tinh_luong.py, việc tính
được thì Python tính, kèm cách tính để người đọc tự kiểm lại.

CÁCH TÍNH (Bộ luật Dân sự 2015):
  - Điều 147: thời hạn tính bằng ngày thì ngày đầu tiên không tính, bắt đầu từ
    ngày tiếp theo.
  - Điều 148: ngày cuối cùng là ngày nghỉ cuối tuần hoặc ngày nghỉ lễ thì thời
    hạn kết thúc vào ngày làm việc tiếp theo.
  - "Ngày làm việc" = trừ thứ Bảy, Chủ nhật và ngày nghỉ lễ.

NGÀY NGHỈ LỄ (Bộ luật Lao động 2019, Điều 112): các ngày dương lịch cố định
(1/1, 30/4, 1/5, 2/9) tính sẵn. Tết Nguyên đán, Giỗ Tổ Hùng Vương (âm lịch),
ngày nghỉ liền kề Quốc khánh, ngày nghỉ bù và hoán đổi do Chính phủ công bố
TỪNG NĂM - cố ý KHÔNG tự suy ra, mà đọc từ ngay_nghi_le.json do quản trị viên
nhập theo thông báo chính thức. Năm nào chưa nhập thì kết quả nói rõ là có thể
sớm hơn thực tế, thay vì im lặng đưa ra một ngày trông như chính xác.

CỔNG NHẬN CÂU HẸP như tinh_toan.py: phải có MỘT mốc ngày (hoặc "hôm nay"), MỘT
khoảng thời hạn và chữ hỏi ngày kết thúc. Thiếu một là trả về None để câu hỏi đi
đường RAG thường.

    python tinh_han.py "nộp hồ sơ ngày 25/9/2026, 15 ngày làm việc thì đến ngày nào"
"""

from __future__ import annotations

import calendar
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

from can_cu_van_ban import CanCu, bo_dau, nguon_tu_can_cu

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_NGAY_NGHI = os.path.abspath(os.getenv(
    "RAG_NGAY_NGHI_LE", os.path.join(THU_MUC_DU_AN, "ngay_nghi_le.json")
))

BLDS_BAT_DAU = CanCu(
    van_ban="Bộ luật Dân sự 2015", dieu_khoan="Điều 147 (thời điểm bắt đầu thời hạn)", trong_kho=False,
)
BLDS_KET_THUC = CanCu(
    van_ban="Bộ luật Dân sự 2015", dieu_khoan="Điều 148 (kết thúc thời hạn)", trong_kho=False,
)
BLLD_NGHI_LE = CanCu(
    van_ban="Bộ luật Lao động 2019", dieu_khoan="Điều 112 (nghỉ lễ, tết)", trong_kho=False,
)

# Ngày lễ dương lịch cố định (tháng, ngày).
NGAY_LE_CO_DINH = {(1, 1): "Tết Dương lịch", (4, 30): "Ngày Chiến thắng", (5, 1): "Quốc tế Lao động", (9, 2): "Quốc khánh"}
THU = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ nhật"]
SO_NGAY_TOI_DA = 3660  # mười năm: đủ cho mọi thời hạn hành chính, chặn vòng lặp vô lý
# Khoảng dương lịch mà ngày nghỉ KHÔNG cố định có thể rơi vào (kể cả ngày nghỉ
# bù, hoán đổi kèm theo): Tết Nguyên đán (mùng 1 rơi từ 21/1 tới 20/2), Giỗ Tổ
# (10/3 âm lịch, cuối tháng 3 tới cuối tháng 4, hay ghép với 30/4-1/5), ngày
# liền kề Quốc khánh. Thời hạn không đi qua khoảng nào thì thiếu bảng cũng không sao.
KHOANG_NGHI_THAY_DOI = [
    ("Tết Nguyên đán", (1, 15), (2, 28)),
    ("Giỗ Tổ Hùng Vương và dịp 30/4-1/5", (3, 25), (5, 5)),
    ("Quốc khánh", (8, 29), (9, 5)),
]


@dataclass
class LichNghi:
    """Ngày nghỉ theo bảng nhập tay: {ISO: tên}, ngày làm bù (thứ Bảy đi làm),
    và các năm đã nhập đủ (để biết năm nào còn thiếu)."""

    ngay_nghi: dict[str, str] = field(default_factory=dict)
    ngay_lam_bu: set[str] = field(default_factory=set)
    nam_da_nhap: set[int] = field(default_factory=set)


def tai_lich_nghi(duong_dan: str = DUONG_DAN_NGAY_NGHI) -> LichNghi:
    try:
        with open(duong_dan, encoding="utf-8") as tep:
            du_lieu = json.load(tep)
    except (OSError, ValueError):
        return LichNghi()
    lich = LichNghi()
    for nam, muc in (du_lieu.get("theo_nam") or {}).items():
        lich.nam_da_nhap.add(int(nam))
        for ngay, ten in (muc.get("ngay_nghi") or {}).items():
            lich.ngay_nghi[ngay] = ten
        lich.ngay_lam_bu.update(muc.get("ngay_lam_bu") or [])
    return lich


def ly_do_nghi(ngay: date, lich: LichNghi) -> str | None:
    """Tên ngày nghỉ, hoặc None nếu là ngày làm việc."""
    iso = ngay.isoformat()
    if iso in lich.ngay_lam_bu:
        return None
    if iso in lich.ngay_nghi:
        return lich.ngay_nghi[iso]
    if (ngay.month, ngay.day) in NGAY_LE_CO_DINH:
        return NGAY_LE_CO_DINH[(ngay.month, ngay.day)]
    if ngay.weekday() >= 5:
        return THU[ngay.weekday()]
    return None


@dataclass
class KetQua:
    bat_dau: date
    so: int
    don_vi: str            # "ngày làm việc" | "ngày" | "tuần" | "tháng"
    ket_thuc: date
    bo_qua: list[tuple[date, str]] = field(default_factory=list)  # ngày nghỉ đã bỏ qua / lùi qua
    lui_ngay_cuoi: date | None = None  # ngày cuối "thô" trước khi lùi theo Điều 148
    canh_bao: list[str] = field(default_factory=list)
    can_cu: list[CanCu] = field(default_factory=list)


def _cong_thang(ngay: date, so_thang: int) -> date:
    thang = ngay.month - 1 + so_thang
    nam, thang = ngay.year + thang // 12, thang % 12 + 1
    return date(nam, thang, min(ngay.day, calendar.monthrange(nam, thang)[1]))


def tinh(bat_dau: date, so: int, don_vi: str, lich: LichNghi | None = None) -> KetQua:
    """Ngày kết thúc thời hạn `so` `don_vi` kể từ `bat_dau` (ngày đầu không tính)."""
    lich = lich if lich is not None else tai_lich_nghi()
    kq = KetQua(bat_dau, so, don_vi, bat_dau, can_cu=[BLDS_BAT_DAU])
    if don_vi == "ngày làm việc":
        ngay, dem = bat_dau, 0
        while dem < so and (ngay - bat_dau).days < SO_NGAY_TOI_DA:
            ngay += timedelta(days=1)
            ly_do = ly_do_nghi(ngay, lich)
            if ly_do:
                kq.bo_qua.append((ngay, ly_do))
            else:
                dem += 1
        kq.ket_thuc = ngay
    else:
        if don_vi == "tháng":
            tho = _cong_thang(bat_dau, so)
        else:
            tho = bat_dau + timedelta(days=so * (7 if don_vi == "tuần" else 1))
        ngay = tho
        while (ly_do := ly_do_nghi(ngay, lich)) and (ngay - tho).days < 30:
            kq.bo_qua.append((ngay, ly_do))
            ngay += timedelta(days=1)
        kq.ket_thuc = ngay
        if ngay != tho:
            kq.lui_ngay_cuoi = tho
            kq.can_cu.append(BLDS_KET_THUC)
    kq.can_cu.append(BLLD_NGHI_LE)
    dip = _dip_chua_co_lich(bat_dau + timedelta(days=1), kq.ket_thuc, lich)
    if dip:
        kq.canh_bao.append(
            f"Thời hạn đi qua dịp {', '.join(dip)} nhưng ngay_nghi_le.json chưa có lịch nghỉ của năm đó "
            "(ngày nghỉ theo âm lịch, ngày liền kề, nghỉ bù) - các ngày nghỉ này chưa được trừ, hạn thật "
            "có thể muộn hơn vài ngày."
        )
    return kq


def _dip_chua_co_lich(tu: date, den: date, lich: LichNghi) -> list[str]:
    """Các dịp nghỉ không cố định mà khoảng [tu, den] đi qua, ở năm chưa nhập lịch."""
    ket_qua = []
    for nam in range(tu.year, den.year + 1):
        if nam in lich.nam_da_nhap:
            continue
        for ten, (t1, n1), (t2, n2) in KHOANG_NGHI_THAY_DOI:
            if tu <= date(nam, t2, n2) and date(nam, t1, n1) <= den:
                ket_qua.append(f"{ten} {nam}")
    return ket_qua


# ============================================================
# NHẬN DIỆN CÂU HỎI
# ============================================================
MAU_NGAY = re.compile(r"(?<![\d/])(\d{1,2})\s*[/-]\s*(\d{1,2})(?:\s*[/-]\s*(\d{4}))?(?![\d/])")
MAU_NGAY_CHU = re.compile(r"\bngay\s+(\d{1,2})\s+thang\s+(\d{1,2})(?:\s+nam\s+(\d{4}))?\b")
MAU_HOM_NAY = re.compile(r"\bhom nay\b")
MAU_THOI_HAN = re.compile(r"\b(\d{1,4})\s*(ngay lam viec|ngay|tuan|thang)\b")
MAU_HOI_NGAY = re.compile(
    r"\b(?:den ngay nao|la ngay nao|vao ngay nao|ngay nao|khi nao|bao gio|han cuoi|han chot|het han"
    r"|tinh han|han la)\b"
)
DON_VI = {"ngay lam viec": "ngày làm việc", "ngay": "ngày", "tuan": "tuần", "thang": "tháng"}


@dataclass
class ThamSo:
    bat_dau: date
    so: int
    don_vi: str


def nhan_dien(cau_hoi: str, hom_nay: date | None = None) -> ThamSo | None:
    chuoi = " ".join(bo_dau(cau_hoi or "").lower().split())
    if not MAU_HOI_NGAY.search(chuoi):
        return None
    hom_nay = hom_nay or date.today()
    # Bỏ số hiệu văn bản ("Thông tư 15/2026") khỏi chỗ dò mốc ngày.
    khong_so_hieu = re.sub(r"\b\d{1,4}\s*/\s*\d{4}\s*/\s*[a-z]{2,}[-\w]*", " ", chuoi)
    cac_ngay = []
    for khop in list(MAU_NGAY_CHU.finditer(khong_so_hieu)) + list(MAU_NGAY.finditer(khong_so_hieu)):
        ngay, thang, nam = int(khop.group(1)), int(khop.group(2)), int(khop.group(3) or hom_nay.year)
        try:
            cac_ngay.append(date(nam, thang, ngay))
        except ValueError:
            continue
    if len(set(cac_ngay)) > 1:
        return None  # hai mốc ngày: không đoán mốc nào là ngày bắt đầu
    if cac_ngay:
        bat_dau = cac_ngay[0]
    elif MAU_HOM_NAY.search(chuoi):
        bat_dau = hom_nay
    else:
        return None
    # Thời hạn tìm sau khi bỏ phần ngày tháng ("ngày 25 tháng 9" không phải "25 ngày").
    con_lai = MAU_NGAY.sub(" ", MAU_NGAY_CHU.sub(" ", khong_so_hieu))
    cac_han = MAU_THOI_HAN.findall(con_lai)
    if len(cac_han) != 1:
        return None
    so, don_vi = int(cac_han[0][0]), DON_VI[cac_han[0][1]]
    if not 1 <= so <= 3650:
        return None
    return ThamSo(bat_dau, so, don_vi)


# ============================================================
# TRÌNH BÀY
# ============================================================
def _viet(ngay: date) -> str:
    return f"{THU[ngay.weekday()]}, {ngay.day}/{ngay.month}/{ngay.year}"


def dinh_dang(kq: KetQua) -> str:
    dong = [
        f"**Hạn: {_viet(kq.ket_thuc)}**",
        "",
        f"- Mốc: {_viet(kq.bat_dau)} - ngày này không tính, đếm từ ngày hôm sau.",
    ]
    if kq.don_vi == "ngày làm việc":
        dong.append(f"- Đếm {kq.so} ngày làm việc, bỏ qua {len(kq.bo_qua)} ngày nghỉ (thứ Bảy, Chủ nhật, ngày lễ).")
        le = [(n, ly_do) for n, ly_do in kq.bo_qua if not ly_do.startswith(("Thứ", "Chủ"))]
        if le:
            dong.append("- Ngày lễ đã trừ: " + "; ".join(f"{n.day}/{n.month}/{n.year} ({ly_do})" for n, ly_do in le))
    else:
        dong.append(f"- Cộng {kq.so} {kq.don_vi}.")
        if kq.lui_ngay_cuoi:
            dong.append(
                f"- Ngày cuối rơi vào {_viet(kq.lui_ngay_cuoi)} là ngày nghỉ, nên hạn lùi sang ngày làm việc tiếp theo."
            )
    for canh_bao in kq.canh_bao:
        dong.append(f"- ⚠️ {canh_bao}")
    dong += ["", "Căn cứ cách tính:"]
    for cc in kq.can_cu:
        dong.append(f"- {cc.mo_ta()}" + ("" if cc.trong_kho else " *(chưa có trong kho tài liệu)*"))
    dong += [
        "",
        "_Mốc bắt đầu là ngày bạn nêu. Thời hạn trong thủ tục thường tính \"kể từ ngày nhận đủ hồ sơ "
        "hợp lệ\" - hồ sơ phải bổ sung thì mốc tính lại từ ngày bổ sung đủ._",
    ]
    return "\n".join(dong)


def tra_loi(cau_hoi: str, hom_nay: date | None = None) -> tuple[str, list[dict]] | None:
    ts = nhan_dien(cau_hoi, hom_nay)
    if ts is None:
        return None
    kq = tinh(ts.bat_dau, ts.so, ts.don_vi)
    return dinh_dang(kq), nguon_tu_can_cu(kq.can_cu)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    ket_qua = tra_loi(" ".join(argv[1:]))
    if ket_qua is None:
        print("Không nhận ra câu hỏi tính hạn (cần một mốc ngày, một thời hạn và chữ hỏi ngày nào).")
        return 1
    print(ket_qua[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
