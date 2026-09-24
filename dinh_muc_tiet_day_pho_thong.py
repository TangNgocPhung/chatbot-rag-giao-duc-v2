"""CÔNG CỤ TÍNH ĐỊNH MỨC TIẾT DẠY GIÁO VIÊN PHỔ THÔNG - PYTHON TÍNH, MÔ HÌNH KHÔNG LÀM TOÁN
=====================================================================================
Anh em của dinh_muc_tiet_day.py (giáo dục thường xuyên, Thông tư 04/2026), cho
giáo viên trường phổ thông và dự bị đại học theo Thông tư 05/2025/TT-BGDĐT.

Vì sao không để RAG trả lời: câu thật 24/9/2026 "tiết dạy của GV THPT cấp 3".
Truy hồi đã đưa đúng Điều 7 vào bằng chứng số 1 - "giáo viên trường trung học
phổ thông là 17 tiết" - vậy mà qwen3.5:4b vẫn kết luận "19 tiết", còn bản có lỗi
OCR thì kết luận "không có thông tin". Một dòng trong bảng 9 con số là thứ mô
hình nhỏ đọc lệch hàng rất dễ; tra bảng bằng Python thì không.

Phạm vi: định mức theo loại trường và cấp học (Điều 7 khoản 3), hiệu trưởng và
phó hiệu trưởng (Điều 8), các khoản giảm có con số cụ thể (Điều 9-12). KHÔNG
tính: tổng phụ trách Đội (định mức riêng theo quy mô trường), quy đổi hoạt
động chuyên môn (Điều 13 - hiệu trưởng quyết định theo từng việc).

    python dinh_muc_tiet_day_pho_thong.py "giáo viên THPT chủ nhiệm dạy bao nhiêu tiết"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from can_cu_van_ban import CanCu, bo_dau, nguon_tu_can_cu
from dinh_muc_tiet_day import (
    QD_DOAN,
    TT_CONG_DOAN,
    TU_KHOA_GDTX,
    TU_KHOA_TRA_CUU,
    Dong,
    KhoanGiam,
    dinh_dang_so,
    dinh_dang_ty_le,
)


# ============================================================
# CĂN CỨ - trích nguyên văn bản OCR đã soát lỗi của 05-bgddt.pdf
# ============================================================
TEP_TT05 = "05-bgddt.pdf"
VAN_BAN = "Thông tư 05/2025/TT-BGDĐT"


def _cc(dieu_khoan: str, trich: str) -> CanCu:
    return CanCu(van_ban=VAN_BAN, dieu_khoan=dieu_khoan, ten_tep=TEP_TT05, trich=trich)


TT05_DINH_MUC = _cc(
    "Điều 7 khoản 3",
    "a) Giáo viên trường tiểu học là 23 tiết, giáo viên trường trung học cơ sở "
    "là 19 tiết, giáo viên trường trung học phổ thông là 17 tiết; b) Giáo viên "
    "trường phổ thông dân tộc bán trú tiểu học là 21 tiết, [...] trung học cơ sở "
    "là 17 tiết, giáo viên trường phổ thông dân tộc nội trú trung học cơ sở là "
    "17 tiết, [...] trung học phổ thông là 15 tiết; c) Giáo viên trường, lớp dành "
    "cho người khuyết tật là 21 tiết đối với cấp tiểu học, 17 tiết đối với cấp "
    "trung học cơ sở, 15 tiết đối với cấp trung học phổ thông; d) Giáo viên "
    "trường dự bị đại học là 12 tiết.",
)
TT05_CONG_THUC = _cc(
    "Điều 7 khoản 2",
    "Định mức tiết dạy trong 01 năm học = Định mức tiết dạy trung bình trong 01 "
    "tuần × Số tuần giảng dạy [...] (không bao gồm số tuần dự phòng).",
)
TT05_THOI_GIAN = _cc(
    "Điều 5 khoản 1 điểm a",
    "Số tuần giảng dạy các nội dung trong chương trình giáo dục phổ thông là 37 "
    "tuần (bao gồm 35 tuần thực dạy và 02 tuần dự phòng).",
)
TT05_THOI_GIAN_DBDH = _cc(
    "Điều 5 khoản 2 điểm a",
    "Số tuần giảng dạy và tổ chức các hoạt động giáo dục theo kế hoạch năm học "
    "là 28 tuần.",
)
TT05_QUAN_LY = _cc(
    "Điều 8 khoản 3, khoản 4",
    "Định mức tiết dạy trung bình trong 01 tuần: a) Hiệu trưởng là 02 tiết; "
    "b) Phó hiệu trưởng là 04 tiết. Hiệu trưởng, phó hiệu trưởng không được quy "
    "đổi chế độ giảm định mức tiết dạy đối với các nhiệm vụ kiêm nhiệm [...] thay "
    "thế cho định mức tiết dạy được quy định tại khoản 3 Điều này.",
)
TT05_D9 = _cc(
    "Điều 9",
    "Giáo viên chủ nhiệm lớp ở các trường phổ thông được giảm 04 tiết/tuần. Giáo "
    "viên chủ nhiệm lớp ở trường dự bị đại học được giảm 03 tiết/tuần. Tổ trưởng "
    "tổ chuyên môn [...] được giảm 03 tiết/tuần; tổ phó tổ chuyên môn [...] được "
    "giảm 01 tiết/tuần.",
)
TT05_D10 = _cc(
    "Điều 10",
    "Giáo viên kiêm bí thư đảng bộ, bí thư chi bộ [...] ở trường có từ 28 lớp "
    "trở lên đối với vùng 2 và vùng 3, 19 lớp trở lên đối với vùng 1 được giảm "
    "04 tiết/tuần; ở trường còn lại được giảm 03 tiết/tuần. [...] chủ tịch hội "
    "đồng trường, thư ký hội đồng trường được giảm 02 tiết/tuần.",
)
TT05_D11 = _cc(
    "Điều 11",
    "Giáo viên kiêm nhiệm công tác công nghệ thông tin (phụ trách cả phòng tin "
    "học) được giảm 03 tiết/tuần. Giáo viên kiêm nhiệm công tác văn thư được giảm "
    "03 tiết/tuần. [...] thư viện [...] được giảm 03 tiết/tuần.",
)
TT05_D12 = _cc(
    "Điều 12",
    "Giáo viên trong thời gian tập sự được giảm 02 tiết/tuần. Giáo viên nữ nuôi "
    "con dưới 12 tháng tuổi giảng dạy ở trường tiểu học được giảm 04 tiết/tuần; "
    "giảng dạy ở các cơ sở giáo dục khác được giảm 03 tiết/tuần.",
)
TT05_NGUYEN_TAC = _cc(
    "Điều 3 khoản 2, khoản 3",
    "Tổng số tiết dạy vượt trong 01 tuần không quá 50% định mức tiết dạy trung "
    "bình trong 01 tuần. Mỗi giáo viên không kiêm nhiệm quá 02 nhiệm vụ quy định "
    "tại Điều 9, Điều 10, Điều 11 Thông tư này.",
)

SO_TUAN_PHO_THONG = 35
SO_TUAN_DU_BI_DAI_HOC = 28
TRAN_VUOT_TUAN = 0.50
SO_NHIEM_VU_KIEM_NHIEM_TOI_DA = 2


# ============================================================
# ĐỊNH MỨC THEO LOẠI TRƯỜNG VÀ CẤP HỌC (Điều 7 khoản 3)
# ============================================================
TEN_CAP = {1: "tiểu học", 2: "trung học cơ sở", 3: "trung học phổ thông"}
DINH_MUC = {
    ("thuong", 1): 23, ("thuong", 2): 19, ("thuong", 3): 17,
    ("dtbt", 1): 21, ("dtbt", 2): 17,
    ("dtnt", 2): 17, ("dtnt", 3): 15,
    ("khuyet_tat", 1): 21, ("khuyet_tat", 2): 17, ("khuyet_tat", 3): 15,
}
TEN_LOAI = {
    "thuong": "Giáo viên trường {cap}",
    "dtbt": "Giáo viên trường phổ thông dân tộc bán trú {cap}",
    "dtnt": "Giáo viên trường phổ thông dân tộc nội trú {cap}",
    "khuyet_tat": "Giáo viên trường, lớp dành cho người khuyết tật cấp {cap}",
}


# ============================================================
# CÁC KHOẢN GIẢM CÓ CON SỐ CỤ THỂ
# ============================================================
# Mẫu viết KHÔNG DẤU - câu hỏi đã qua bo_dau(). Tổ trưởng/tổ phó tổ quản lý học
# sinh (Điều 9 khoản 4) đứng trước tổ trưởng chuyên môn để không bị tính hai lần.
KHOAN_GIAM: list[KhoanGiam] = [
    KhoanGiam("to_truong_qlhs", "Tổ trưởng tổ quản lý học sinh (trường dân tộc nội trú, bán trú)",
              3, TT05_D9, mau=r"\bto truong (?:to )?quan ly hoc sinh"),
    KhoanGiam("to_pho_qlhs", "Tổ phó tổ quản lý học sinh (trường dân tộc nội trú, bán trú)",
              1, TT05_D9, mau=r"\bto pho (?:to )?quan ly hoc sinh"),
    KhoanGiam("to_truong", "Tổ trưởng tổ chuyên môn", 3, TT05_D9,
              mau=r"\bto truong(?! (?:to )?quan ly hoc sinh)"),
    KhoanGiam("to_pho", "Tổ phó tổ chuyên môn", 1, TT05_D9,
              mau=r"\bto pho(?! (?:to )?quan ly hoc sinh)"),
    KhoanGiam("chu_tich_hdt", "Chủ tịch hoặc thư ký hội đồng trường", 2, TT05_D10,
              mau=r"(?:chu tich|thu ky) hoi dong truong"),
    KhoanGiam("ttnd", "Trưởng ban thanh tra nhân dân", 2, TT05_D10,
              mau=r"thanh tra nhan dan"),
    KhoanGiam("cntt", "Kiêm nhiệm công tác công nghệ thông tin (phụ trách cả phòng tin học)",
              3, TT05_D11,
              mau=r"kiem (?:nhiem )?(?:cong tac )?(?:cong nghe thong tin|cntt)|"
                  r"phu trach (?:phong )?(?:tin hoc|may tinh|cntt)|cong tac (?:cong nghe thong tin|cntt)"),
    KhoanGiam("van_thu", "Kiêm nhiệm công tác văn thư", 3, TT05_D11, mau=r"van thu"),
    KhoanGiam("thu_vien", "Kiêm nhiệm công tác thư viện (phụ trách cả phòng thư viện)",
              3, TT05_D11, mau=r"thu vien"),
    KhoanGiam("ho_tro_khuyet_tat", "Kiêm nhiệm công tác hỗ trợ giáo dục người khuyết tật",
              3, TT05_D11, mau=r"ho tro giao duc (?:nguoi |hoc sinh )?khuyet tat"),
    KhoanGiam("tap_su", "Trong thời gian tập sự", 2, TT05_D12, vao_tran=False, mau=r"tap su"),
]

# Kiêm nhiệm theo Điều 9, 10, 11 - đếm để kiểm giới hạn 02 nhiệm vụ ở Điều 3.
# Chủ nhiệm lớp là nhiệm vụ ở Điều 9 khoản 1 nên cũng tính.
KHONG_PHAI_KIEM_NHIEM = {"tap_su", "nuoi_con"}
# Điều 3 khoản 3: đã nhận thù lao, phụ cấp thì mất phần giảm - trừ các nhiệm vụ
# ở khoản 3, 5 Điều 9 và khoản 1, 2, 3 Điều 10. Tập sự, nuôi con không phải
# nhiệm vụ nên không dính.
KHONG_BI_TRU_KHI_CO_PHU_CAP = {"to_truong", "to_pho", "bi_thu", "tap_su", "nuoi_con"}

MAU_CHU_NHIEM = r"chu nhiem|\bgvcn\b"
MAU_NUOI_CON = r"nuoi con (?:nho )?(?:duoi )?12 thang|con (?:nho )?duoi 12 thang"
MAU_BI_THU = r"bi thu (?:dang|chi bo)"
MAU_PHONG_BO_MON = r"phong (?:hoc )?bo mon"
MAU_PHONG_THIET_BI = r"phong thiet bi"
# Hai việc Điều 11 để hiệu trưởng quyết định trong một quỹ tiết chung của trường.
MAU_QUY_TIET = [
    (r"giao vu", "Kiêm nhiệm công tác giáo vụ", "Điều 11 khoản 1"),
    (r"tu van (?:tam ly |hoc duong )?(?:cho )?hoc sinh|tu van tam ly|tu van hoc duong",
     "Kiêm nhiệm công tác tư vấn học sinh", "Điều 11 khoản 2"),
]
NGOAI_KHO = [
    (r"cong doan", TT_CONG_DOAN),
    (r"bi thu doan|tro ly thanh nien|pho bi thu doan|co van doan", QD_DOAN),
]


# ============================================================
# THAM SỐ VÀ KẾT QUẢ
# ============================================================
@dataclass
class ThamSo:
    vai_tro: str = "giao_vien"          # giao_vien | hieu_truong | pho_hieu_truong
    loai: str = "thuong"                # thuong | dtbt | dtnt | khuyet_tat | du_bi_dai_hoc
    cap: int | None = None              # 1 tiểu học, 2 THCS, 3 THPT
    khoan_giam: list[KhoanGiam] = field(default_factory=list)
    so_tuan: int = SO_TUAN_PHO_THONG
    so_tiet_thuc_day: float | None = None
    so_lop: int | None = None
    vung: int | None = None
    can_cu_ngoai_kho: list[CanCu] = field(default_factory=list)
    quy_tiet: list[tuple[str, str]] = field(default_factory=list)
    canh_bao: list[str] = field(default_factory=list)


@dataclass
class KetQua:
    tham_so: ThamSo
    dong: list[Dong] = field(default_factory=list)
    dinh_muc_goc: float = 0.0
    dinh_muc_tuan: float = 0.0
    dinh_muc_nam: float = 0.0
    tong_giam_tuan: float = 0.0
    tiet_vuot_tuan: float = 0.0
    canh_bao: list[str] = field(default_factory=list)
    can_cu_da_dung: list[CanCu] = field(default_factory=list)


def truong_lon(so_lop: int | None, vung: int | None) -> bool | None:
    """Mốc quy mô dùng chung ở Điều 10 khoản 1 và Điều 11: từ 28 lớp trở lên ở
    vùng 2 và vùng 3, từ 19 lớp trở lên ở vùng 1. None khi câu hỏi chưa nói đủ."""
    if so_lop is None or vung is None:
        return None
    return so_lop >= (19 if vung == 1 else 28)


def ten_giao_vien(ts: ThamSo) -> str:
    if ts.vai_tro == "hieu_truong":
        return "Hiệu trưởng"
    if ts.vai_tro == "pho_hieu_truong":
        return "Phó hiệu trưởng"
    if ts.loai == "du_bi_dai_hoc":
        return "Giáo viên trường dự bị đại học"
    return TEN_LOAI[ts.loai].format(cap=TEN_CAP[ts.cap])


# ============================================================
# PHÉP TÍNH
# ============================================================
def tinh(ts: ThamSo) -> KetQua:
    kq = KetQua(tham_so=ts, canh_bao=list(ts.canh_bao))
    thoi_gian = TT05_THOI_GIAN_DBDH if ts.loai == "du_bi_dai_hoc" else TT05_THOI_GIAN

    if ts.vai_tro in ("hieu_truong", "pho_hieu_truong"):
        kq.dinh_muc_goc = 2 if ts.vai_tro == "hieu_truong" else 4
        kq.dong.append(Dong(
            "Định mức tiết dạy trung bình trong 01 tuần",
            f"{kq.dinh_muc_goc} tiết/tuần theo Điều 8",
            kq.dinh_muc_goc, TT05_QUAN_LY,
        ))
        kq.dinh_muc_tuan = kq.dinh_muc_goc
        kq.dinh_muc_nam = kq.dinh_muc_tuan * ts.so_tuan
    else:
        kq.dinh_muc_goc = 12 if ts.loai == "du_bi_dai_hoc" else DINH_MUC[(ts.loai, ts.cap)]
        kq.dong.append(Dong(
            "Định mức tiết dạy trung bình trong 01 tuần",
            f"{kq.dinh_muc_goc} tiết/tuần theo Điều 7",
            kq.dinh_muc_goc, TT05_DINH_MUC,
        ))
        for kg in ts.khoan_giam:
            kq.dong.append(Dong(
                f"Giảm: {kg.ten}",
                (f"tối đa {dinh_dang_so(kg.so_tiet)} tiết/tuần"
                 if kg.toi_da else f"{dinh_dang_so(kg.so_tiet)} tiết/tuần"),
                -kg.so_tiet, kg.can_cu,
            ))
            kq.tong_giam_tuan += kg.so_tiet
        kq.dinh_muc_tuan = kq.dinh_muc_goc - kq.tong_giam_tuan
        kq.dinh_muc_nam = kq.dinh_muc_tuan * ts.so_tuan

        so_kiem_nhiem = sum(1 for kg in ts.khoan_giam if kg.khoa not in KHONG_PHAI_KIEM_NHIEM)
        so_kiem_nhiem += len(ts.quy_tiet) + len(ts.can_cu_ngoai_kho)  # công đoàn, Đoàn: Điều 10
        if so_kiem_nhiem > SO_NHIEM_VU_KIEM_NHIEM_TOI_DA:
            kq.canh_bao.append(
                f"Câu hỏi nêu {so_kiem_nhiem} nhiệm vụ kiêm nhiệm, trong khi Điều 3 "
                f"khoản 3 chỉ cho mỗi giáo viên kiêm tối đa "
                f"{SO_NHIEM_VU_KIEM_NHIEM_TOI_DA} nhiệm vụ ở Điều 9, 10, 11 (chủ nhiệm "
                f"lớp cũng là một nhiệm vụ ở Điều 9)."
            )
            kq.can_cu_da_dung.append(TT05_NGUYEN_TAC)
        if kq.dinh_muc_tuan < 0:
            kq.canh_bao.append(
                f"Các khoản giảm cộng lại đã vượt quá định mức {kq.dinh_muc_goc} "
                f"tiết/tuần. Đây là dấu hiệu phân công sai, không phải một định mức âm."
            )
            kq.dinh_muc_tuan = kq.dinh_muc_nam = 0
        if ts.quy_tiet or any(kg.khoa not in KHONG_BI_TRU_KHI_CO_PHU_CAP for kg in ts.khoan_giam):
            kq.canh_bao.append(
                "Điều 3 khoản 3: nhiệm vụ đã được nhận thù lao hoặc phụ cấp thì không "
                "được giảm định mức nữa (trừ tổ trưởng, tổ phó chuyên môn, trưởng/phó "
                "phòng trường dự bị đại học và công tác Đảng, công đoàn, Đoàn)."
            )
        if any(kg.toi_da for kg in ts.khoan_giam):
            kq.canh_bao.append(
                "Những khoản ghi \"tối đa\" là mức trần; số tiết giảm cụ thể do hiệu "
                "trưởng quyết định, nên định mức thực tế có thể cao hơn con số trong bảng."
            )

    for ten, dieu in ts.quy_tiet:
        lon = truong_lon(ts.so_lop, ts.vung)
        quy = ("08 tiết/tuần" if lon else "04 tiết/tuần") if lon is not None else \
            "08 tiết/tuần (trường từ 28 lớp ở vùng 2, 3 hoặc từ 19 lớp ở vùng 1) hoặc 04 tiết/tuần"
        kq.canh_bao.append(
            f"{ten}: {dieu} không cho một con số giảm cố định - hiệu trưởng quyết "
            f"định, trong quỹ chung của cả trường là {quy}. Khoản này chưa được trừ "
            f"trong bảng."
        )
        kq.can_cu_da_dung.append(TT05_D11)

    if ts.so_tiet_thuc_day is not None:
        kq.tiet_vuot_tuan = ts.so_tiet_thuc_day - kq.dinh_muc_tuan
        tran = kq.dinh_muc_tuan * TRAN_VUOT_TUAN
        if kq.tiet_vuot_tuan > tran + 1e-9:
            kq.canh_bao.append(
                f"Số tiết dạy vượt {dinh_dang_so(kq.tiet_vuot_tuan)} tiết/tuần đã quá "
                f"trần {dinh_dang_ty_le(TRAN_VUOT_TUAN)} định mức tuần "
                f"({dinh_dang_so(tran)} tiết) tại Điều 3 khoản 2."
            )
            kq.can_cu_da_dung.append(TT05_NGUYEN_TAC)

    ra: list[CanCu] = []
    for cc in [d.can_cu for d in kq.dong] + [TT05_CONG_THUC, thoi_gian] \
            + kq.can_cu_da_dung + ts.can_cu_ngoai_kho:
        if cc is not None and cc not in ra:
            ra.append(cc)
    kq.can_cu_da_dung = ra
    for cc in ts.can_cu_ngoai_kho:
        kq.canh_bao.append(
            f"{cc.van_ban} chưa có trong kho tài liệu: mức giảm của nhiệm vụ này KHÔNG "
            f"được tính vào bảng trên vì chatbot không trích dẫn được nguồn."
        )
    return kq


# ============================================================
# NHẬN DIỆN CÂU HỎI
# ============================================================
# Cổng 1 - hỏi về SỐ TIẾT phải dạy, không phải về một tiết dạy cụ thể. "Tiết
# dạy" đứng một mình thì quá rộng: "soạn tiết dạy Toán THPT" là câu hỏi giáo án.
TU_KHOA_DINH_MUC = re.compile(
    r"dinh muc|tiet/tuan|tiet (?:mot|moi|1) tuan|che do lam viec|thua gio|vuot gio|"
    r"day vuot|bao nhieu tiet|may tiet|so tiet (?:phai |duoc )?day|so tiet day|"
    r"(?:duoc )?giam\s*(?:may|bao nhieu)?\s*tiet|"
    r"tiet day (?:cua|doi voi|danh cho|cho)? ?(?:gv|giao vien|hieu truong|pho hieu truong)"
)
KHONG_PHAI_DINH_MUC = re.compile(
    r"soan|giao an|ke hoach bai day|\bkhbd\b|bao nhieu phut|may phut|thoi luong|"
    r"phan phoi chuong trinh|\bppct\b|hoc sinh (?:hoc|co) (?:bao nhieu|may) tiet|"
    r"mon \w+ (?:co|hoc) (?:bao nhieu|may) tiet"
)
CAP_MAU = [
    (1, r"tieu hoc|\bcap (?:1|i)\b"),
    (2, r"trung hoc co so|\bthcs\b|\bcap (?:2|ii)\b"),
    (3, r"trung hoc pho thong|\bthpt\b|\bcap (?:3|iii)\b"),
]
LOAI_MAU = [
    ("du_bi_dai_hoc", r"du bi dai hoc"),
    ("dtnt", r"dan toc noi tru|\b(?:pt)?dtnt\b"),
    ("dtbt", r"dan toc ban tru|\b(?:pt)?dtbt\b"),
    ("khuyet_tat", r"(?:truong|lop)(?: \w+){0,3} (?:danh cho )?(?:nguoi |hoc sinh )?khuyet tat"),
]
# Cơ sở giáo dục mà Thông tư 05/2025 không điều chỉnh.
NGOAI_PHAM_VI = re.compile(
    r"(?<!du bi )dai hoc|cao dang|trung cap|mam non|mau giao|giang vien|nghe nghiep"
)


def nhan_dien(cau_hoi: str) -> ThamSo | None:
    """None nghĩa là câu này không thuộc phạm vi Thông tư 05/2025, chỉ hỏi căn
    cứ, hoặc không đủ thông tin để ra một con số - khi đó RAG trả lời."""
    if not cau_hoi:
        return None
    thap = bo_dau(cau_hoi)
    if TU_KHOA_TRA_CUU.search(thap) or KHONG_PHAI_DINH_MUC.search(thap):
        return None
    if not TU_KHOA_DINH_MUC.search(thap):
        return None
    # Giáo dục thường xuyên đã có công cụ riêng theo Thông tư 04/2026.
    if TU_KHOA_GDTX.search(thap) or NGOAI_PHAM_VI.search(thap) or "tong phu trach" in thap:
        return None

    ts = ThamSo()
    if re.search(r"pho hieu truong", thap):
        ts.vai_tro = "pho_hieu_truong"
    elif re.search(r"hieu truong", thap):
        ts.vai_tro = "hieu_truong"

    cac_cap = [cap for cap, mau in CAP_MAU if re.search(mau, thap)]
    loai = next((l for l, mau in LOAI_MAU if re.search(mau, thap)), "thuong")
    if loai == "khuyet_tat" and re.search(r"ho tro giao duc", thap):
        loai = "thuong"   # kiêm hỗ trợ giáo dục người khuyết tật, không phải trường chuyên biệt
    ts.loai = loai

    if loai == "du_bi_dai_hoc":
        ts.so_tuan = SO_TUAN_DU_BI_DAI_HOC
    elif ts.vai_tro == "giao_vien":
        # So sánh nhiều cấp học thì trả lời bằng một con số là nửa vời; thiếu
        # cấp học thì không biết lấy dòng nào của bảng.
        if len(cac_cap) != 1:
            return None
        ts.cap = cac_cap[0]
        if (loai, ts.cap) not in DINH_MUC:
            return None   # vd trường dân tộc bán trú cấp THPT: Điều 7 không quy định
    elif re.search(r"kiem nhiem|chu nhiem|bi thu|to truong|to pho", thap):
        ts.canh_bao.append(
            "Điều 8 khoản 4: hiệu trưởng, phó hiệu trưởng không được dùng chế độ "
            "giảm định mức cho nhiệm vụ kiêm nhiệm để thay cho định mức này, nên "
            "các nhiệm vụ nêu trong câu hỏi không được trừ."
        )

    m = re.search(r"(\d{1,3})\s*lop", thap)
    ts.so_lop = int(m.group(1)) if m else None
    m = re.search(r"vung\s*(1|2|3|i{1,3})\b", thap)
    if m:
        ts.vung = int(m.group(1)) if m.group(1).isdigit() else len(m.group(1))

    if ts.vai_tro == "giao_vien":
        _nhan_khoan_giam(ts, thap)

    m = re.search(r"(\d{1,2})\s*tuan\s*(?:thuc day)?", thap)
    if m and 1 <= int(m.group(1)) <= 52:
        ts.so_tuan = int(m.group(1))
    m = re.search(
        r"(?:day|phan cong|dang day|thuc day)\s*(?:la\s*)?(\d{1,2}(?:[.,]\d)?)"
        r"\s*tiet\s*(?:/|mot |moi )?\s*tuan",
        thap,
    )
    if m:
        ts.so_tiet_thuc_day = float(m.group(1).replace(",", "."))
    return ts


def _nhan_khoan_giam(ts: ThamSo, thap: str) -> None:
    if re.search(MAU_CHU_NHIEM, thap):
        if ts.loai == "du_bi_dai_hoc":
            ts.khoan_giam.append(KhoanGiam("chu_nhiem", "Chủ nhiệm lớp trường dự bị đại học", 3, TT05_D9))
        else:
            ts.khoan_giam.append(KhoanGiam("chu_nhiem", "Chủ nhiệm lớp", 4, TT05_D9))

    for kg in KHOAN_GIAM:
        if re.search(kg.mau, thap):
            ts.khoan_giam.append(kg)

    if re.search(MAU_BI_THU, thap):
        lon = truong_lon(ts.so_lop, ts.vung)
        ts.khoan_giam.append(KhoanGiam(
            "bi_thu", "Bí thư đảng bộ, bí thư chi bộ", 4 if lon else 3, TT05_D10,
        ))
        if lon is None:
            ts.canh_bao.append(
                "Bí thư chi bộ được giảm 04 tiết/tuần nếu trường có từ 28 lớp (vùng 2, "
                "vùng 3) hoặc từ 19 lớp (vùng 1); bảng đang tính mức 03 tiết của trường "
                "còn lại vì câu hỏi chưa nêu số lớp và vùng."
            )

    so_phong = re.search(r"(\d)\s*" + MAU_PHONG_BO_MON, thap)
    if re.search(MAU_PHONG_BO_MON, thap):
        so = int(so_phong.group(1)) if so_phong else 1
        ts.khoan_giam.append(KhoanGiam(
            "phong_bo_mon", f"Phụ trách phòng học bộ môn ({so} môn)", 3 * so, _cc(
                "Điều 9 khoản 6",
                "Khi nhà trường không có viên chức thiết bị, thí nghiệm, giáo viên "
                "kiêm phụ trách phòng học bộ môn (trừ phòng tin học) được giảm 03 "
                "tiết/môn/tuần, phụ trách phòng thiết bị giáo dục được giảm 03 tiết/tuần.",
            ),
        ))
    if re.search(MAU_PHONG_THIET_BI, thap):
        ts.khoan_giam.append(KhoanGiam("phong_thiet_bi", "Phụ trách phòng thiết bị giáo dục", 3, TT05_D9))
    if re.search(MAU_PHONG_BO_MON + "|" + MAU_PHONG_THIET_BI, thap):
        ts.canh_bao.append(
            "Điều 9 khoản 6 chỉ cho giảm khi nhà trường không có viên chức thiết bị, "
            "thí nghiệm."
        )

    if re.search(MAU_NUOI_CON, thap):
        ts.khoan_giam.append(KhoanGiam(
            "nuoi_con", "Nữ nuôi con dưới 12 tháng tuổi",
            4 if ts.cap == 1 and ts.loai != "du_bi_dai_hoc" else 3, TT05_D12, vao_tran=False,
        ))

    for mau, ten, dieu in MAU_QUY_TIET:
        if re.search(mau, thap):
            ts.quy_tiet.append((ten, dieu))
    for mau, cc in NGOAI_KHO:
        if re.search(mau, thap):
            ts.can_cu_ngoai_kho.append(cc)


# ============================================================
# TRÌNH BÀY
# ============================================================
def dinh_dang(kq: KetQua) -> str:
    ts = kq.tham_so
    dong = [
        f"Định mức **{dinh_dang_so(kq.dinh_muc_tuan)} tiết/tuần**, tương ứng "
        f"**{dinh_dang_so(kq.dinh_muc_nam)} tiết** trong 01 năm học "
        f"({ts.so_tuan} tuần {'thực dạy' if ts.loai != 'du_bi_dai_hoc' else 'giảng dạy'}).",
        "",
        f"**{ten_giao_vien(ts)}**",
        "",
        "| Khoản | Cách tính | Số tiết |",
        "|---|---|---:|",
    ]
    for d in kq.dong:
        dong.append(f"| {d.nhan} | {d.cong_thuc} | {dinh_dang_so(d.so_tiet)} |")
    if kq.tong_giam_tuan:
        dong.append(
            f"| **Định mức còn lại trong 01 tuần** | {dinh_dang_so(kq.dinh_muc_goc)} − "
            f"{dinh_dang_so(kq.tong_giam_tuan)} | **{dinh_dang_so(kq.dinh_muc_tuan)}** |"
        )
    dong.append(
        f"| **Định mức trong 01 năm học** | {dinh_dang_so(kq.dinh_muc_tuan)} × "
        f"{ts.so_tuan} tuần | **{dinh_dang_so(kq.dinh_muc_nam)}** |"
    )
    if ts.so_tiet_thuc_day is not None:
        nhan = "Số tiết dạy vượt" if kq.tiet_vuot_tuan >= 0 else "Còn thiếu so với định mức"
        dong.append(
            f"| **{nhan}** | {dinh_dang_so(ts.so_tiet_thuc_day)} được phân công − "
            f"{dinh_dang_so(kq.dinh_muc_tuan)} định mức | "
            f"**{dinh_dang_so(abs(kq.tiet_vuot_tuan))}** |"
        )

    dong += ["", "**Căn cứ:**"]
    for cc in kq.can_cu_da_dung:
        nhan = "" if cc.trong_kho else " *(chưa có trong kho tài liệu)*"
        dong.append(f"- {cc.mo_ta()}{nhan}")
    if kq.canh_bao:
        dong += ["", "**Lưu ý:**"] + [f"- {c}" for c in kq.canh_bao]
    dong += [
        "",
        "*Phép tính do công cụ tính định mức thực hiện, không phải mô hình ngôn ngữ "
        "sinh ra. Áp dụng cho giáo viên trường phổ thông, dự bị đại học theo Thông tư "
        "05/2025/TT-BGDĐT; chưa gồm tiết quy đổi từ hoạt động chuyên môn ở Điều 13 "
        "(dạy liên trường, bồi dưỡng học sinh giỏi, dạy lớp chuyên...) vì mức quy "
        "đổi tùy từng việc.*",
    ]
    return "\n".join(dong)


def tra_loi(cau_hoi: str) -> tuple[str, list[dict]] | None:
    ts = nhan_dien(cau_hoi)
    if ts is None:
        return None
    kq = tinh(ts)
    return dinh_dang(kq), nguon_tu_can_cu(kq.can_cu_da_dung)


def main(argv: list[str]) -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) < 2:
        print(__doc__)
        return 1
    ket_qua = tra_loi(" ".join(argv[1:]))
    if ket_qua is None:
        print("Không nhận ra đây là câu hỏi định mức tiết dạy của giáo viên phổ thông.")
        return 1
    print(ket_qua[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
