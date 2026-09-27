"""CÔNG CỤ TÍNH ĐIỂM VÀ XẾP LOẠI HỌC SINH - PYTHON TÍNH, MÔ HÌNH KHÔNG LÀM TOÁN
==============================================================================
Cùng khuôn với tinh_luong.py và dinh_muc_tiet_day.py, cho Thông tư
22/2021/TT-BGDĐT quy định về đánh giá học sinh trung học cơ sở và trung học
phổ thông.

Đây là nhóm câu hỏi mà giáo viên hỏi nhiều nhất và mô hình sai nhiều nhất.
ĐTBmhk không phải trung bình cộng - nó là trung bình CÓ TRỌNG SỐ, điểm giữa kì
nhân 2, điểm cuối kì nhân 3, mẫu số là số điểm thường xuyên cộng 5. Một model
3B trên CPU nhìn thấy dãy điểm rồi cộng chia bình thường sẽ ra một con số rất
gần đáp án đúng, và chính vì gần nên không ai kiểm lại.

Xếp loại còn dễ sai hơn: bốn mức Tốt, Khá, Đạt, Chưa đạt không xét theo điểm
trung bình của tất cả các môn, mà xét theo NGƯỠNG CỦA TỪNG MÔN kèm điều kiện
đếm "ít nhất 06 môn". Chưa kể khoản 3 Điều 9 còn cho nâng lên mức liền kề khi
học sinh bị tụt hai mức chỉ vì đúng một môn - một quy tắc mà đọc lướt là bỏ sót.

    python danh_gia_hoc_sinh.py "điểm thường xuyên 8, 9, giữa kì 7, cuối kì 8"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from can_cu_van_ban import CanCu, bo_dau, nguon_tu_can_cu


# ============================================================
# CĂN CỨ
# ============================================================
TEP_TT22 = "22.signed_02.pdf"

TT22_THANG_DIEM = CanCu(
    van_ban="Thông tư 22/2021/TT-BGDĐT",
    dieu_khoan="Điều 5 khoản 3 điểm b",
    ten_tep=TEP_TT22,
    trich="Điểm đánh giá là số nguyên hoặc số thập phân được lấy đến chữ số "
          "thập phân thứ nhất sau khi làm tròn số.",
)

TT22_SO_DIEM_TX = CanCu(
    van_ban="Thông tư 22/2021/TT-BGDĐT",
    dieu_khoan="Điều 6 khoản 2 điểm b",
    ten_tep=TEP_TT22,
    trich="Môn học có 35 tiết/năm học: 02 ĐĐGtx. Môn học có trên 35 tiết/năm "
          "học đến 70 tiết/năm học: 03 ĐĐGtx. Môn học có trên 70 tiết/năm "
          "học: 04 ĐĐGtx.",
)

TT22_DTB = CanCu(
    van_ban="Thông tư 22/2021/TT-BGDĐT",
    dieu_khoan="Điều 9 khoản 1 điểm b",
    ten_tep=TEP_TT22,
    trich="ĐTBmhk = (TĐĐGtx + 2 x ĐĐGgk + 3 x ĐĐGck) / (Số ĐĐGtx + 5). "
          "ĐTBmcn = (ĐTBmhkI + 2 x ĐTBmhkII) / 3.",
)

TT22_XEP_LOAI = CanCu(
    van_ban="Thông tư 22/2021/TT-BGDĐT",
    dieu_khoan="Điều 9 khoản 2",
    ten_tep=TEP_TT22,
    trich="Kết quả học tập của học sinh trong từng học kì và cả năm học được "
          "đánh giá theo 01 (một) trong 04 (bốn) mức: Tốt, Khá, Đạt, Chưa đạt.",
)

TT22_NANG_MUC = CanCu(
    van_ban="Thông tư 22/2021/TT-BGDĐT",
    dieu_khoan="Điều 9 khoản 3",
    ten_tep=TEP_TT22,
    trich="Nếu mức đánh giá kết quả học tập của học kì, cả năm học bị thấp "
          "xuống từ 02 (hai) mức trở lên so với mức đánh giá quy định tại "
          "điểm a, điểm b khoản 2 Điều này chỉ do kết quả đánh giá của duy "
          "nhất 01 (một) môn học thì mức đánh giá kết quả học tập của học kì "
          "đó, cả năm học đó được điều chỉnh lên mức liền kề.",
)

TT22_KHEN_THUONG = CanCu(
    van_ban="Thông tư 22/2021/TT-BGDĐT",
    dieu_khoan="Điều 15 khoản 1 điểm a",
    ten_tep=TEP_TT22,
    trich="Khen thưởng danh hiệu \"Học sinh Xuất sắc\" đối với những học sinh "
          "có kết quả rèn luyện cả năm học được đánh giá mức Tốt, kết quả học "
          "tập cả năm học được đánh giá mức Tốt và có ít nhất 06 (sáu) môn học "
          "[...] có ĐTBmcn đạt từ 9,0 điểm trở lên.",
)


# Ngưỡng điểm ở Điều 9 khoản 2. Đặt tên theo đúng chữ trong văn bản để đối
# chiếu được, thay vì rải mấy con số 6.5 và 8.0 khắp nơi trong hàm xếp loại.
NGUONG_TOT_MOI_MON = 6.5
NGUONG_TOT_SAU_MON = 8.0
NGUONG_KHA_MOI_MON = 5.0
NGUONG_KHA_SAU_MON = 6.5
NGUONG_DAT_SAU_MON = 5.0
NGUONG_DAT_KHONG_DUOI = 3.5
SO_MON_TOI_THIEU = 6
NGUONG_XUAT_SAC = 9.0

# Thứ tự từ cao xuống thấp; chỉ số trong danh sách chính là "mức liền kề" mà
# khoản 3 Điều 9 nói tới.
CAC_MUC = ["Tốt", "Khá", "Đạt", "Chưa đạt"]

# Câu hỏi đi qua bo_dau() nên mức đọc ra từ câu là chuỗi không dấu; dịch ngược
# về đúng chữ mà CAC_MUC và danh_hieu_khen_thuong() dùng, thay vì so chuỗi
# không dấu ở hai chỗ đó rồi quên mất một chỗ.
MUC_TU_KHONG_DAU = {bo_dau(m): m for m in CAC_MUC}

# Điều 5 khoản 3 điểm a - những môn chỉ đánh giá bằng nhận xét, không có điểm.
MON_NHAN_XET = [
    "Giáo dục thể chất", "Nghệ thuật", "Âm nhạc", "Mĩ thuật",
    "Nội dung giáo dục của địa phương", "Hoạt động trải nghiệm, hướng nghiệp",
]

# Điều 6 khoản 2 điểm b - số điểm đánh giá thường xuyên theo số tiết/năm học.
def so_diem_thuong_xuyen(so_tiet_nam: int) -> int:
    if so_tiet_nam <= 35:
        return 2
    if so_tiet_nam <= 70:
        return 3
    return 4


# ============================================================
# ĐIỂM TRUNG BÌNH MÔN
# ============================================================
def lam_tron(diem: float) -> float:
    """Lấy đến chữ số thập phân thứ nhất sau khi làm tròn - Điều 5 khoản 3
    điểm b.

    Dùng làm tròn nửa lên chứ không dùng round() của Python: round(8.25, 1) ra
    8.2 vì số dấu phẩy động, trong khi sổ điểm và mọi phần mềm quản lý học tập
    đều ghi 8,3. Lệch một phần mười ở đây là lệch cả mức xếp loại khi điểm rơi
    đúng ngưỡng 6,5 hay 8,0.
    """
    from decimal import Decimal, ROUND_HALF_UP

    return float(Decimal(repr(diem)).quantize(Decimal("0.1"), ROUND_HALF_UP))


def dtb_mon_hoc_ki(
    diem_thuong_xuyen: list[float], diem_giua_ki: float, diem_cuoi_ki: float
) -> float:
    """ĐTBmhk theo Điều 9 khoản 1 điểm b.

    Đây KHÔNG phải trung bình cộng: giữa kì nhân 2, cuối kì nhân 3, và mẫu số
    là số điểm thường xuyên cộng 5 (chính là 1 + 2 + 3 của ba loại điểm).
    """
    if not diem_thuong_xuyen:
        raise ValueError("Phải có ít nhất một điểm đánh giá thường xuyên.")
    tong = sum(diem_thuong_xuyen) + 2 * diem_giua_ki + 3 * diem_cuoi_ki
    return lam_tron(tong / (len(diem_thuong_xuyen) + 5))


def dtb_mon_ca_nam(dtb_hoc_ki_1: float, dtb_hoc_ki_2: float) -> float:
    """ĐTBmcn theo Điều 9 khoản 1 điểm b - học kì II nhân đôi."""
    return lam_tron((dtb_hoc_ki_1 + 2 * dtb_hoc_ki_2) / 3)


# ============================================================
# XẾP LOẠI KẾT QUẢ HỌC TẬP
# ============================================================
@dataclass
class KetQuaXepLoai:
    muc: str
    ly_do: list[str] = field(default_factory=list)
    muc_truoc_khi_nang: str | None = None


def xep_loai_hoc_tap(
    diem_cac_mon: list[float],
    mon_nhan_xet_dat: int = 0,
    mon_nhan_xet_chua_dat: int = 0,
) -> KetQuaXepLoai:
    """Xếp loại kết quả học tập theo Điều 9 khoản 2, kèm điều chỉnh ở khoản 3.

    `diem_cac_mon` là ĐTBmhk (xếp loại học kì) hoặc ĐTBmcn (xếp loại cả năm)
    của các môn đánh giá bằng điểm số - văn bản dùng CHUNG một bộ ngưỡng cho cả
    hai, nên hàm này cũng vậy.
    """
    if not diem_cac_mon:
        raise ValueError("Phải có điểm của ít nhất một môn học.")
    del mon_nhan_xet_dat  # chỉ dùng để nhắc chỗ gọi rằng có hai loại môn

    muc = _muc_theo_nguong(diem_cac_mon, mon_nhan_xet_chua_dat)
    ly_do = _giai_thich(diem_cac_mon, mon_nhan_xet_chua_dat, muc)

    nang = _nang_mot_muc_neu_chi_vi_mot_mon(diem_cac_mon, mon_nhan_xet_chua_dat, muc)
    if nang is not None:
        return KetQuaXepLoai(muc=nang, ly_do=ly_do, muc_truoc_khi_nang=muc)
    return KetQuaXepLoai(muc=muc, ly_do=ly_do)


def _muc_theo_nguong(diem: list[float], nhan_xet_chua_dat: int) -> str:
    thap_nhat = min(diem)
    if nhan_xet_chua_dat == 0:
        if (thap_nhat >= NGUONG_TOT_MOI_MON
                and _dem_tu(diem, NGUONG_TOT_SAU_MON) >= SO_MON_TOI_THIEU):
            return "Tốt"
        if (thap_nhat >= NGUONG_KHA_MOI_MON
                and _dem_tu(diem, NGUONG_KHA_SAU_MON) >= SO_MON_TOI_THIEU):
            return "Khá"
    if (nhan_xet_chua_dat <= 1
            and _dem_tu(diem, NGUONG_DAT_SAU_MON) >= SO_MON_TOI_THIEU
            and thap_nhat >= NGUONG_DAT_KHONG_DUOI):
        return "Đạt"
    return "Chưa đạt"


def _dem_tu(diem: list[float], nguong: float) -> int:
    return sum(1 for d in diem if d >= nguong)


def _nang_mot_muc_neu_chi_vi_mot_mon(
    diem: list[float], nhan_xet_chua_dat: int, muc: str
) -> str | None:
    """Khoản 3 Điều 9: tụt từ 02 mức trở lên chỉ vì DUY NHẤT 01 môn thì được
    nâng lên mức liền kề.

    Cách kiểm: bỏ lần lượt từng môn ra, xem mức tính lại được cải thiện bao
    nhiêu. Nếu có đúng một môn mà bỏ nó đi thì mức lên được ít nhất hai bậc,
    môn đó chính là "duy nhất 01 môn học" mà khoản 3 nói tới.
    """
    if len(diem) <= 1 or nhan_xet_chua_dat > 0:
        return None
    hien_tai = CAC_MUC.index(muc)
    if hien_tai == 0:
        return None

    thu_pham = [
        i for i in range(len(diem))
        if hien_tai - CAC_MUC.index(
            _muc_theo_nguong(diem[:i] + diem[i + 1:], nhan_xet_chua_dat)
        ) >= 2
    ]
    if len(thu_pham) != 1:
        return None
    return CAC_MUC[hien_tai - 1]


def _giai_thich(diem: list[float], nhan_xet_chua_dat: int, muc: str) -> list[str]:
    ra = [
        f"{len(diem)} môn tính điểm, thấp nhất {dinh_dang_diem(min(diem))}, "
        f"cao nhất {dinh_dang_diem(max(diem))}.",
        f"Số môn từ 8,0 trở lên: {_dem_tu(diem, NGUONG_TOT_SAU_MON)} · "
        f"từ 6,5 trở lên: {_dem_tu(diem, NGUONG_KHA_SAU_MON)} · "
        f"từ 5,0 trở lên: {_dem_tu(diem, NGUONG_DAT_SAU_MON)}.",
    ]
    if nhan_xet_chua_dat:
        ra.append(f"Môn đánh giá bằng nhận xét ở mức Chưa đạt: {nhan_xet_chua_dat}.")
    if muc == "Chưa đạt":
        ra.append(
            "Không đủ điều kiện của mức Đạt: cần ít nhất 06 môn từ 5,0 trở lên, "
            "không môn nào dưới 3,5 và nhiều nhất 01 môn nhận xét Chưa đạt."
        )
    return ra


# ============================================================
# KHEN THƯỞNG
# ============================================================
def danh_hieu_khen_thuong(
    ren_luyen_ca_nam: str, hoc_tap_ca_nam: str, diem_ca_nam: list[float]
) -> str | None:
    """Danh hiệu cuối năm theo Điều 15 khoản 1 điểm a; None nghĩa là không đạt
    danh hiệu nào trong hai danh hiệu này."""
    if ren_luyen_ca_nam != "Tốt" or hoc_tap_ca_nam != "Tốt":
        return None
    if _dem_tu(diem_ca_nam, NGUONG_XUAT_SAC) >= SO_MON_TOI_THIEU:
        return "Học sinh Xuất sắc"
    return "Học sinh Giỏi"


def dinh_dang_diem(x: float) -> str:
    """Điểm kiểu Việt: 8,3 chứ không phải 8.3 - phải đối chiếu được với sổ
    điểm và với nguyên dạng con số in trong Thông tư."""
    return f"{x:.1f}".replace(".", ",")


# ============================================================
# NHẬN DIỆN CÂU HỎI
# ============================================================
# Cổng 1 - câu này có thuộc chuyện điểm và xếp loại không.
# Mọi mẫu ở đây viết KHÔNG DẤU - câu hỏi đã đi qua bo_dau() trước khi so.
TU_KHOA_DIEM = re.compile(
    r"dtb|diem trung binh|thuong xuyen|giua k[iy]|cuoi k[iy]|xep loai|"
    r"hoc luc|hoc sinh gioi|xuat sac|len lop|"
    # "được danh hiệu gì" là cách hỏi xếp loại thông dụng nhất mà không có chữ
    # "xếp loại" nào trong câu.
    r"danh hieu|khen thuong|giay khen|diem cac mon"
)

# Cổng 2 - câu hỏi về QUY ĐỊNH chứ không phải về một con số.
TU_KHOA_TRA_CUU = re.compile(
    r"quy dinh (?:o dau|tai dau|the nao|nhu the nao)|can cu nao|van ban nao|"
    r"dieu nao|thu tuc|ho so|trach nhiem|ai (?:danh gia|quyet dinh)|"
    r"co hieu luc|khac gi|so voi thong tu"
)

MAU_THUONG_XUYEN = re.compile(
    r"(?:thuong xuyen|dgtx|ddgtx|tx)\s*[:=]?\s*"
    r"((?:\d{1,2}(?:[.,]\d)?\s*[,;+va ]*)+)"
)
MAU_GIUA_KI = re.compile(r"giua\s*k[iy]\s*[:=]?\s*(\d{1,2}(?:[.,]\d)?)")
MAU_CUOI_KI = re.compile(r"cuoi\s*k[iy]\s*[:=]?\s*(\d{1,2}(?:[.,]\d)?)")
MAU_HOC_KI_1 = re.compile(
    r"(?:hoc\s*k[iy]\s*(?:i|1|mot)|hk\s*1|hki)\s*[:=]?\s*(\d{1,2}(?:[.,]\d)?)"
)
MAU_HOC_KI_2 = re.compile(
    r"(?:hoc\s*k[iy]\s*(?:ii|2|hai)|hk\s*2|hkii)\s*[:=]?\s*(\d{1,2}(?:[.,]\d)?)"
)
MAU_CAC_MON = re.compile(
    r"diem\s*(?:cac\s*mon|\d+\s*mon)\s*[:=]?\s*"
    r"((?:\d{1,2}(?:[.,]\d)?\s*[,;va ]*)+)"
)


def _so(chuoi: str) -> float:
    return float(chuoi.replace(",", "."))


def _day_so(chuoi: str) -> list[float]:
    return [_so(s) for s in re.findall(r"\d{1,2}(?:[.,]\d)?", chuoi)]


@dataclass
class ThamSo:
    """Một trong ba dạng câu hỏi, phân biệt bằng `dang`."""

    dang: str                                   # mon_hoc_ki | mon_ca_nam | xep_loai
    diem_thuong_xuyen: list[float] = field(default_factory=list)
    diem_giua_ki: float = 0.0
    diem_cuoi_ki: float = 0.0
    dtb_hoc_ki_1: float = 0.0
    dtb_hoc_ki_2: float = 0.0
    diem_cac_mon: list[float] = field(default_factory=list)
    mon_nhan_xet_chua_dat: int = 0
    ren_luyen: str | None = None


def nhan_dien(cau_hoi: str) -> ThamSo | None:
    """Đọc câu hỏi thành tham số tính điểm; None nghĩa là không đủ số liệu để
    tính, hoặc đây là câu tra cứu quy định."""
    if not cau_hoi:
        return None
    thap = bo_dau(cau_hoi)
    if TU_KHOA_TRA_CUU.search(thap):
        return None
    if not TU_KHOA_DIEM.search(thap):
        return None


    # Dạng 1 - tính ĐTBmhk từ các điểm thành phần.
    tx = MAU_THUONG_XUYEN.search(thap)
    gk = MAU_GIUA_KI.search(thap)
    ck = MAU_CUOI_KI.search(thap)
    if tx and gk and ck:
        day = _day_so(tx.group(1))
        if day:
            return ThamSo(
                dang="mon_hoc_ki",
                diem_thuong_xuyen=day,
                diem_giua_ki=_so(gk.group(1)),
                diem_cuoi_ki=_so(ck.group(1)),
            )

    # Dạng 2 - ĐTBmcn từ hai học kì.
    hk1, hk2 = MAU_HOC_KI_1.search(thap), MAU_HOC_KI_2.search(thap)
    if hk1 and hk2:
        return ThamSo(
            dang="mon_ca_nam",
            dtb_hoc_ki_1=_so(hk1.group(1)),
            dtb_hoc_ki_2=_so(hk2.group(1)),
        )

    # Dạng 3 - xếp loại từ điểm của nhiều môn. Đòi đủ 06 môn vì mọi ngưỡng ở
    # Điều 9 khoản 2 đều đếm "ít nhất 06 môn học" - dưới mức đó thì mọi mức đều
    # rơi về Chưa đạt, và đó là kết luận sai chứ không phải kết luận nghiêm.
    mon = MAU_CAC_MON.search(thap)
    if mon:
        day = _day_so(mon.group(1))
        if len(day) >= SO_MON_TOI_THIEU:
            ts = ThamSo(dang="xep_loai", diem_cac_mon=day)
            m = re.search(r"(\d+)\s*mon\s*(?:nhan xet\s*)?chua dat", thap)
            if m:
                ts.mon_nhan_xet_chua_dat = int(m.group(1))
            m = re.search(r"ren luyen\s*(?:muc\s*)?(chua dat|tot|kha|dat)", thap)
            if m:
                ts.ren_luyen = MUC_TU_KHONG_DAU[m.group(1)]
            return ts

    return None


# ============================================================
# TRÌNH BÀY
# ============================================================
def dinh_dang(ts: ThamSo) -> tuple[str, list[CanCu]]:
    if ts.dang == "mon_hoc_ki":
        return _trinh_bay_hoc_ki(ts)
    if ts.dang == "mon_ca_nam":
        return _trinh_bay_ca_nam(ts)
    return _trinh_bay_xep_loai(ts)


def _trinh_bay_hoc_ki(ts: ThamSo) -> tuple[str, list[CanCu]]:
    diem = dtb_mon_hoc_ki(ts.diem_thuong_xuyen, ts.diem_giua_ki, ts.diem_cuoi_ki)
    tong_tx = sum(ts.diem_thuong_xuyen)
    tu_so = tong_tx + 2 * ts.diem_giua_ki + 3 * ts.diem_cuoi_ki
    mau_so = len(ts.diem_thuong_xuyen) + 5
    day = " + ".join(dinh_dang_diem(d) for d in ts.diem_thuong_xuyen)

    dong = [
        f"Điểm trung bình môn học kì **{dinh_dang_diem(diem)}**.",
        "",
        "| Thành phần | Cách tính | Giá trị |",
        "|---|---|---:|",
        f"| Tổng điểm thường xuyên (TĐĐGtx) | {day} | "
        f"{dinh_dang_diem(tong_tx)} |",
        f"| Điểm giữa kì × 2 | {dinh_dang_diem(ts.diem_giua_ki)} × 2 | "
        f"{dinh_dang_diem(2 * ts.diem_giua_ki)} |",
        f"| Điểm cuối kì × 3 | {dinh_dang_diem(ts.diem_cuoi_ki)} × 3 | "
        f"{dinh_dang_diem(3 * ts.diem_cuoi_ki)} |",
        f"| Tử số | cộng ba dòng trên | {dinh_dang_diem(tu_so)} |",
        f"| Mẫu số | {len(ts.diem_thuong_xuyen)} điểm thường xuyên + 5 | "
        f"{mau_so} |",
        f"| **ĐTBmhk** | {dinh_dang_diem(tu_so)} ÷ {mau_so} | "
        f"**{dinh_dang_diem(diem)}** |",
        "",
        "Công thức: `ĐTBmhk = (TĐĐGtx + 2 × ĐĐGgk + 3 × ĐĐGck) ÷ (Số ĐĐGtx + 5)`",
    ]
    return "\n".join(dong), [TT22_DTB, TT22_THANG_DIEM]


def _trinh_bay_ca_nam(ts: ThamSo) -> tuple[str, list[CanCu]]:
    diem = dtb_mon_ca_nam(ts.dtb_hoc_ki_1, ts.dtb_hoc_ki_2)
    tu_so = ts.dtb_hoc_ki_1 + 2 * ts.dtb_hoc_ki_2
    dong = [
        f"Điểm trung bình môn cả năm **{dinh_dang_diem(diem)}**.",
        "",
        "| Thành phần | Cách tính | Giá trị |",
        "|---|---|---:|",
        f"| ĐTBmhk học kì I | | {dinh_dang_diem(ts.dtb_hoc_ki_1)} |",
        f"| ĐTBmhk học kì II × 2 | {dinh_dang_diem(ts.dtb_hoc_ki_2)} × 2 | "
        f"{dinh_dang_diem(2 * ts.dtb_hoc_ki_2)} |",
        f"| **ĐTBmcn** | {dinh_dang_diem(tu_so)} ÷ 3 | "
        f"**{dinh_dang_diem(diem)}** |",
        "",
        "Công thức: `ĐTBmcn = (ĐTBmhkI + 2 × ĐTBmhkII) ÷ 3` — học kì II nhân "
        "đôi, không phải trung bình cộng hai học kì.",
    ]
    return "\n".join(dong), [TT22_DTB, TT22_THANG_DIEM]


def _trinh_bay_xep_loai(ts: ThamSo) -> tuple[str, list[CanCu]]:
    kq = xep_loai_hoc_tap(
        ts.diem_cac_mon, mon_nhan_xet_chua_dat=ts.mon_nhan_xet_chua_dat
    )
    can_cu = [TT22_XEP_LOAI]

    dong = [f"Kết quả học tập xếp mức **{kq.muc}**.", ""]
    for ly in kq.ly_do:
        dong.append(f"- {ly}")

    if kq.muc_truoc_khi_nang is not None:
        can_cu.append(TT22_NANG_MUC)
        dong += [
            "",
            f"Theo ngưỡng ở khoản 2 thì mức là **{kq.muc_truoc_khi_nang}**, "
            f"nhưng chỉ vì đúng một môn mà tụt từ hai mức trở lên, nên khoản 3 "
            f"Điều 9 cho điều chỉnh lên mức liền kề là **{kq.muc}**.",
        ]

    if ts.ren_luyen:
        danh_hieu = danh_hieu_khen_thuong(ts.ren_luyen, kq.muc, ts.diem_cac_mon)
        can_cu.append(TT22_KHEN_THUONG)
        dong += ["", (
            f"Rèn luyện cả năm mức {ts.ren_luyen} và học tập mức {kq.muc}: "
            + (f"đạt danh hiệu **{danh_hieu}**." if danh_hieu
               else "chưa đạt danh hiệu Học sinh Giỏi hay Học sinh Xuất sắc "
                    "(cả hai đều đòi rèn luyện Tốt và học tập Tốt).")
        )]

    dong += [
        "",
        "Ngưỡng ở Điều 9 khoản 2 — **Tốt**: mọi môn từ 6,5 và ít nhất 06 môn "
        "từ 8,0 · **Khá**: mọi môn từ 5,0 và ít nhất 06 môn từ 6,5 · **Đạt**: "
        "ít nhất 06 môn từ 5,0, không môn nào dưới 3,5 và nhiều nhất 01 môn "
        "nhận xét Chưa đạt.",
    ]
    return "\n".join(dong), can_cu


def _phan_can_cu(can_cu: list[CanCu]) -> str:
    dong = ["", "**Căn cứ:**"]
    for cc in can_cu:
        nhan = "" if cc.trong_kho else " *(chưa có trong kho tài liệu)*"
        dong.append(f"- {cc.mo_ta()}{nhan}")
    dong += [
        "",
        "*Phép tính do công cụ đánh giá học sinh thực hiện, không phải mô hình "
        "ngôn ngữ sinh ra. Công cụ chỉ xét các môn đánh giá bằng điểm số nêu "
        "trong câu hỏi; kết quả rèn luyện và các môn đánh giá bằng nhận xét do "
        "giáo viên chủ nhiệm và giáo viên môn học đánh giá, không tính ra "
        "được.*",
    ]
    return "\n".join(dong)


def tra_loi(cau_hoi: str) -> tuple[str, list[dict]] | None:
    """Đường tắt cho chỗ gọi: câu hỏi vào, (câu trả lời, nguồn) ra, None nếu
    không phải câu tính điểm hoặc thiếu số liệu."""
    ts = nhan_dien(cau_hoi)
    if ts is None:
        return None
    try:
        van_ban, can_cu = dinh_dang(ts)
    except ValueError:
        return None
    return van_ban + "\n" + _phan_can_cu(can_cu), nguon_tu_can_cu(can_cu)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    ket_qua = tra_loi(" ".join(argv[1:]))
    if ket_qua is None:
        print("Không nhận ra đây là câu hỏi tính điểm, hoặc thiếu số liệu "
              "(cần điểm thường xuyên, giữa kì và cuối kì; hoặc hai học kì; "
              "hoặc điểm của ít nhất 06 môn).")
        return 1
    print(ket_qua[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
