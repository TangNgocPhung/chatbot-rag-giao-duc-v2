"""CÔNG CỤ TÍNH ĐỊNH MỨC TIẾT DẠY - PYTHON TÍNH, MÔ HÌNH KHÔNG LÀM TOÁN
========================================================================
Cùng khuôn với tinh_luong.py, cho nhóm câu hỏi thứ hai mà kho tài liệu có đủ
căn cứ để tính: chế độ làm việc của giáo viên cơ sở giáo dục thường xuyên theo
Thông tư 04/2026/TT-BGDĐT.

Vì sao là phép tính chứ không phải câu tra cứu: Thông tư chỉ in ra công thức
("Định mức tiết dạy trong 01 năm học = định mức tuần × số tuần thực dạy") và
từng khoản giảm rời rạc ở Điều 9, Điều 10. Con số cuối cùng - còn phải dạy bao
nhiêu tiết một tuần sau khi trừ chủ nhiệm và kiêm nhiệm - không nằm sẵn trong
văn bản nào. Để mô hình tự cộng trừ thì vướng đúng ba lớp bảo vệ đã nói trong
tinh_luong.py: prompt cấm ghép số liệu giữa các đoạn trích, hậu kiểm gắn cờ mọi
con số không có nguyên văn trong đoạn trích, và model 3B trên CPU thì không
đáng tin ở số học nhiều bước.

PHẠM VI HẸP ĐÚNG BẰNG PHẠM VI CỦA VĂN BẢN. Thông tư 04/2026 chỉ điều chỉnh
giáo viên cơ sở giáo dục thường xuyên (Điều 1). Kho hiện KHÔNG có văn bản nào
quy định định mức tiết dạy cho giáo viên phổ thông hay mầm non, nên câu hỏi về
các cấp học đó bị trả None để đi tiếp đường RAG - đem con số 17 tiết của giáo
dục thường xuyên trả lời cho giáo viên THPT là bịa, dù có trích dẫn kèm.

    python dinh_muc_tiet_day.py "giáo viên GDTX chủ nhiệm một lớp dạy bao nhiêu tiết"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from can_cu_van_ban import CanCu, bo_dau, nguon_tu_can_cu


# ============================================================
# CĂN CỨ
# ============================================================
TEP_TT04 = "04_2026_TT-BGDDT_694692.doc"

TT04_DINH_MUC = CanCu(
    van_ban="Thông tư 04/2026/TT-BGDĐT",
    dieu_khoan="Điều 7",
    ten_tep=TEP_TT04,
    trich="Định mức tiết dạy trung bình trong 01 tuần đối với giáo viên giảng "
          "dạy chương trình giáo dục thường xuyên là 17 tiết.",
)

TT04_THOI_GIAN = CanCu(
    van_ban="Thông tư 04/2026/TT-BGDĐT",
    dieu_khoan="Điều 5 khoản 1 điểm a",
    ten_tep=TEP_TT04,
    trich="37 tuần giảng dạy các nội dung trong chương trình giáo dục thường "
          "xuyên (bao gồm 35 tuần thực dạy và 02 tuần dự phòng).",
)

TT04_QUAN_LY = CanCu(
    van_ban="Thông tư 04/2026/TT-BGDĐT",
    dieu_khoan="Điều 8 khoản 1",
    ten_tep=TEP_TT04,
    trich="Định mức tiết dạy trong 01 năm học của giám đốc là 8% định mức tiết "
          "dạy trong 01 năm học của giáo viên [...]. Định mức tiết dạy trong "
          "01 năm học của phó giám đốc là 10%.",
)

TT04_GIAM = CanCu(
    van_ban="Thông tư 04/2026/TT-BGDĐT",
    dieu_khoan="Điều 9",
    ten_tep=TEP_TT04,
    trich="Giáo viên chủ nhiệm lớp học chương trình giáo dục thường xuyên được "
          "giảm 04 tiết/tuần.",
)

TT04_GIAM_KHAC = CanCu(
    van_ban="Thông tư 04/2026/TT-BGDĐT",
    dieu_khoan="Điều 10",
    ten_tep=TEP_TT04,
    trich="Giáo viên trong thời gian tập sự (nếu có) được giảm 02 tiết/tuần. "
          "Giáo viên nữ nuôi con dưới 12 tháng tuổi được giảm 03 tiết/tuần.",
)

TT04_NGUYEN_TAC = CanCu(
    van_ban="Thông tư 04/2026/TT-BGDĐT",
    dieu_khoan="Điều 4",
    ten_tep=TEP_TT04,
    trich="Tổng số tiết được giảm và quy đổi đối với các nhiệm vụ kiêm nhiệm "
          "trong 01 năm học của giáo viên không quá 50% định mức tiết dạy "
          "trong 01 năm học.",
)

# Hai văn bản được Điều 9 dẫn chiếu sang nhưng KHÔNG nằm trong kho. Không tính
# hộ mức giảm của hai nhóm này: con số sẽ không đối chiếu được với nguồn nào.
TT_CONG_DOAN = CanCu(
    van_ban="Thông tư 08/2016/TT-BGDĐT",
    dieu_khoan="chế độ giảm định mức giờ dạy cho giáo viên làm công tác công đoàn",
    trong_kho=False,
)
QD_DOAN = CanCu(
    van_ban="Quyết định 13/2013/QĐ-TTg",
    dieu_khoan="chế độ đối với cán bộ Đoàn trong các cơ sở giáo dục",
    trong_kho=False,
)


DINH_MUC_TUAN = 17
SO_TUAN_THUC_DAY = 35
TY_LE_GIAM_DOC = 0.08
TY_LE_PHO_GIAM_DOC = 0.10
TRAN_GIAM_NAM = 0.50      # Điều 4 khoản 2
TRAN_VUOT_TUAN = 0.50     # Điều 4 khoản 1


# ============================================================
# CÁC KHOẢN GIẢM ĐỊNH MỨC
# ============================================================
@dataclass(frozen=True)
class KhoanGiam:
    """Một nhiệm vụ kiêm nhiệm kèm số tiết được giảm mỗi tuần.

    `toi_da` đánh dấu những khoản mà Thông tư chỉ đặt trần rồi giao giám đốc
    quyết định mức cụ thể. Với những khoản đó, công cụ tính theo mức trần NHƯNG
    phải nói rõ đây là trần chứ không phải mức đương nhiên được hưởng - lấy
    trần làm mức chắc chắn là chỗ dễ đưa ra một con số quá tay nhất ở đây.
    """

    khoa: str
    ten: str
    so_tiet: float
    can_cu: CanCu
    toi_da: bool = False
    mau: str = ""
    # Trần 50% ở Điều 4 khoản 2 chỉ tính trên "các nhiệm vụ kiêm nhiệm". Tập sự
    # và nuôi con dưới 12 tháng nằm ở Điều 10, không phải nhiệm vụ kiêm nhiệm,
    # nên cộng chúng vào phép kiểm tra trần là dựng ra một giới hạn không có
    # trong văn bản rồi cảnh báo oan người dùng.
    vao_tran: bool = True


KHOAN_GIAM: list[KhoanGiam] = [
    KhoanGiam(
        "chu_nhiem", "Chủ nhiệm lớp học chương trình giáo dục thường xuyên",
        4, TT04_GIAM,
        mau=r"chu nhiem|gvcn",
    ),
    KhoanGiam(
        "truong_phong", "Trưởng phòng hoặc tổ trưởng", 6, TT04_GIAM,
        toi_da=True,
        mau=r"truong phong|to truong",
    ),
    KhoanGiam(
        "pho_truong_phong", "Phó trưởng phòng hoặc tổ phó", 4, TT04_GIAM,
        toi_da=True,
        mau=r"pho truong phong|to pho",
    ),
    KhoanGiam(
        "tu_van", "Kiêm nhiệm công tác tư vấn học viên", 8, TT04_GIAM,
        toi_da=True,
        mau=r"tu van hoc vien|tu van hoc sinh|tu van tam ly",
    ),
    KhoanGiam(
        "tap_su", "Trong thời gian tập sự", 2, TT04_GIAM_KHAC,
        vao_tran=False,
        mau=r"tap su",
    ),
    KhoanGiam(
        "nuoi_con_nho", "Nữ nuôi con dưới 12 tháng tuổi", 3, TT04_GIAM_KHAC,
        vao_tran=False,
        mau=r"nuoi con duoi 12 thang|con nho duoi 12 thang",
    ),
]

# Kiêm nhiệm nói chung - Điều 9 khoản 2 điểm c cho dải 2 đến 4 tiết/tuần, mức
# cụ thể do giám đốc quyết định. Tách riêng khỏi danh sách trên vì nó chỉ được
# nhận khi câu hỏi KHÔNG nêu một nhiệm vụ cụ thể nào, nếu không thì một câu
# "kiêm nhiệm tổ trưởng" sẽ bị cộng hai lần.
KIEM_NHIEM_KHAC = KhoanGiam(
    "kiem_nhiem_khac", "Kiêm nhiệm vị trí việc làm khác", 4, TT04_GIAM,
    toi_da=True,
    mau=r"kiem nhiem",
)

# Nhiệm vụ mà Thông tư đẩy sang văn bản khác - nhận diện được để cảnh báo, chứ
# không tính thành tiết.
NGOAI_KHO = [
    (r"cong doan", TT_CONG_DOAN),
    (r"bi thu doan|tro ly thanh nien|pho bi thu doan|co van doan",
     QD_DOAN),
]


# ============================================================
# THAM SỐ VÀ KẾT QUẢ
# ============================================================
@dataclass
class ThamSo:
    vai_tro: str = "giao_vien"          # giao_vien | giam_doc | pho_giam_doc
    khoan_giam: list[KhoanGiam] = field(default_factory=list)
    so_tuan: int = SO_TUAN_THUC_DAY
    so_tiet_thuc_day: float | None = None   # tiết/tuần đang được phân công
    can_cu_ngoai_kho: list[CanCu] = field(default_factory=list)


@dataclass
class Dong:
    nhan: str
    cong_thuc: str
    so_tiet: float
    can_cu: CanCu | None = None


@dataclass
class KetQua:
    tham_so: ThamSo
    dong: list[Dong] = field(default_factory=list)
    dinh_muc_tuan: float = 0.0
    dinh_muc_nam: float = 0.0
    tong_giam_tuan: float = 0.0
    tiet_vuot_tuan: float = 0.0
    canh_bao: list[str] = field(default_factory=list)
    can_cu_da_dung: list[CanCu] = field(default_factory=list)


def dinh_dang_so(x: float) -> str:
    """Số tiết kiểu Việt: 17, 47,6. Giữ phần lẻ chứ không làm tròn - 8% của 595
    ra 47,6 tiết, và Thông tư không quy định làm tròn về đâu, nên tự làm tròn
    hộ là thêm vào văn bản một quy tắc không có ở đó."""
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}".replace(",", ".")
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def dinh_dang_ty_le(x: float) -> str:
    return f"{x * 100:g}%".replace(".", ",")


# ============================================================
# PHÉP TÍNH
# ============================================================
def tinh(ts: ThamSo) -> KetQua:
    """Tính định mức tiết dạy. Mỗi bước là một dòng kèm công thức đã thay số,
    để người dùng kiểm lại được bằng máy tính bỏ túi."""
    kq = KetQua(tham_so=ts)

    dinh_muc_nam_gv = DINH_MUC_TUAN * ts.so_tuan
    if ts.vai_tro in ("giam_doc", "pho_giam_doc"):
        return _tinh_quan_ly(kq, dinh_muc_nam_gv)

    kq.dong.append(Dong(
        "Định mức tiết dạy trung bình trong 01 tuần",
        f"{DINH_MUC_TUAN} tiết/tuần theo Điều 7",
        DINH_MUC_TUAN,
        TT04_DINH_MUC,
    ))

    for kg in ts.khoan_giam:
        kq.dong.append(Dong(
            f"Giảm: {kg.ten}",
            (f"tối đa {dinh_dang_so(kg.so_tiet)} tiết/tuần"
             if kg.toi_da else f"{dinh_dang_so(kg.so_tiet)} tiết/tuần"),
            -kg.so_tiet,
            kg.can_cu,
        ))
        kq.tong_giam_tuan += kg.so_tiet

    kq.dinh_muc_tuan = DINH_MUC_TUAN - kq.tong_giam_tuan
    kq.dinh_muc_nam = kq.dinh_muc_tuan * ts.so_tuan

    if any(kg.toi_da for kg in ts.khoan_giam):
        kq.canh_bao.append(
            "Những khoản ghi \"tối đa\" là mức TRẦN Thông tư cho phép; mức giảm "
            "cụ thể do giám đốc quyết định, nên số tiết còn phải dạy thực tế có "
            "thể cao hơn con số trong bảng."
        )

    # Điều 4 khoản 2 - trần tổng số tiết được giảm và quy đổi trong một năm học,
    # chỉ tính phần giảm do nhiệm vụ kiêm nhiệm.
    giam_kiem_nhiem_tuan = sum(kg.so_tiet for kg in ts.khoan_giam if kg.vao_tran)
    tong_giam_nam = giam_kiem_nhiem_tuan * ts.so_tuan
    tran_nam = dinh_muc_nam_gv * TRAN_GIAM_NAM
    if tong_giam_nam > tran_nam + 1e-9:
        kq.canh_bao.append(
            f"Tổng số tiết được giảm trong năm là {dinh_dang_so(tong_giam_nam)} "
            f"tiết, vượt trần {dinh_dang_ty_le(TRAN_GIAM_NAM)} định mức năm "
            f"({dinh_dang_so(tran_nam)} tiết) tại Điều 4 khoản 2. Phải cắt bớt "
            f"mức giảm cho về trong trần, trừ phần kiêm nhiệm công tác Đoàn mà "
            f"Điều 4 khoản 2 loại trừ."
        )
        kq.can_cu_da_dung.append(TT04_NGUYEN_TAC)

    if kq.dinh_muc_tuan < 0:
        kq.canh_bao.append(
            "Các khoản giảm cộng lại đã vượt quá cả định mức 17 tiết/tuần. Đây "
            "là dấu hiệu phân công sai, không phải một định mức âm."
        )
        kq.dinh_muc_tuan = 0
        kq.dinh_muc_nam = 0

    if ts.so_tiet_thuc_day is not None:
        _tinh_vuot_dinh_muc(kq)

    _gom_can_cu(kq)
    return kq


def _tinh_quan_ly(kq: KetQua, dinh_muc_nam_gv: float) -> KetQua:
    """Giám đốc và phó giám đốc tính theo tỉ lệ phần trăm định mức năm của giáo
    viên, KHÔNG đi qua đường trừ dần theo tuần: Điều 8 khoản 3 cấm dùng tiết
    được giảm hay quy đổi để thay cho định mức này."""
    ts = kq.tham_so
    la_giam_doc = ts.vai_tro == "giam_doc"
    ty_le = TY_LE_GIAM_DOC if la_giam_doc else TY_LE_PHO_GIAM_DOC
    chuc = "giám đốc" if la_giam_doc else "phó giám đốc"

    kq.dong.append(Dong(
        "Định mức tiết dạy 01 năm học của giáo viên",
        f"{DINH_MUC_TUAN} tiết/tuần × {ts.so_tuan} tuần thực dạy",
        dinh_muc_nam_gv,
        TT04_DINH_MUC,
    ))
    kq.dinh_muc_nam = dinh_muc_nam_gv * ty_le
    kq.dong.append(Dong(
        f"Định mức tiết dạy 01 năm học của {chuc}",
        f"{dinh_dang_ty_le(ty_le)} × {dinh_dang_so(dinh_muc_nam_gv)}",
        kq.dinh_muc_nam,
        TT04_QUAN_LY,
    ))
    kq.dinh_muc_tuan = kq.dinh_muc_nam / ts.so_tuan

    kq.canh_bao.append(
        f"Điều 8 khoản 3: {chuc} không được dùng tiết dạy được giảm hoặc quy "
        f"đổi để thay cho định mức này."
    )
    if ts.khoan_giam:
        kq.canh_bao.append(
            "Các nhiệm vụ kiêm nhiệm nêu trong câu hỏi không được trừ vào định "
            "mức trên, đúng theo Điều 8 khoản 3."
        )
    kq.canh_bao.append(
        "Thông tư không quy định cách làm tròn số tiết, nên con số để nguyên "
        "phần lẻ."
    )
    _gom_can_cu(kq)
    return kq


def _tinh_vuot_dinh_muc(kq: KetQua) -> None:
    """Số tiết dạy vượt trong tuần, kèm trần 50% ở Điều 4 khoản 1."""
    ts = kq.tham_so
    thuc = ts.so_tiet_thuc_day or 0
    kq.tiet_vuot_tuan = thuc - kq.dinh_muc_tuan
    tran_vuot = kq.dinh_muc_tuan * TRAN_VUOT_TUAN
    if kq.tiet_vuot_tuan > tran_vuot + 1e-9:
        kq.canh_bao.append(
            f"Số tiết dạy vượt {dinh_dang_so(kq.tiet_vuot_tuan)} tiết/tuần đã "
            f"quá trần {dinh_dang_ty_le(TRAN_VUOT_TUAN)} định mức tuần "
            f"({dinh_dang_so(tran_vuot)} tiết) tại Điều 4 khoản 1."
        )
        kq.can_cu_da_dung.append(TT04_NGUYEN_TAC)


def _gom_can_cu(kq: KetQua) -> None:
    ra: list[CanCu] = []
    for d in kq.dong:
        if d.can_cu is not None and d.can_cu not in ra:
            ra.append(d.can_cu)
    if kq.tham_so.so_tuan == SO_TUAN_THUC_DAY and TT04_THOI_GIAN not in ra:
        ra.append(TT04_THOI_GIAN)
    for cc in kq.can_cu_da_dung + kq.tham_so.can_cu_ngoai_kho:
        if cc not in ra:
            ra.append(cc)
    kq.can_cu_da_dung = ra
    for cc in ra:
        if not cc.trong_kho:
            kq.canh_bao.append(
                f"{cc.van_ban} chưa có trong kho tài liệu: mức giảm của nhiệm "
                f"vụ này KHÔNG được tính vào bảng trên vì chatbot không trích "
                f"dẫn được nguồn."
            )


# ============================================================
# NHẬN DIỆN CÂU HỎI
# ============================================================
# Cổng 1 - câu này có thuộc chuyện định mức tiết dạy không.
# Mọi mẫu ở đây viết KHÔNG DẤU - câu hỏi đã đi qua bo_dau() trước khi so.
TU_KHOA_DINH_MUC = re.compile(
    r"dinh muc|tiet day|tiet/tuan|tiet mot tuan|che do lam viec|thua gio|"
    r"vuot dinh muc|day bao nhieu tiet|so tiet phai day|"
    r"giam\s*(?:may|bao nhieu)?\s*tiet"
)

# Cổng 2 - Thông tư 04/2026 chỉ điều chỉnh giáo dục thường xuyên. Câu hỏi phải
# tự nêu phạm vi đó ra thì mới nhận; nêu một cấp học khác thì nhường cho RAG.
TU_KHOA_GDTX = re.compile(
    r"giao duc thuong xuyen|\bgdtx\b|\bgdnn\b|"
    r"trung tam giao duc nghe nghiep|hoc vien|bo tuc"
)
CAP_HOC_KHAC = re.compile(
    r"tieu hoc|trung hoc co so|\bthcs\b|trung hoc pho thong|\bthpt\b|"
    r"mam non|mau giao|pho thong|dai hoc|cao dang|giang vien|trung cap|"
    r"du bi dai hoc"
)

# Câu hỏi về THỦ TỤC hoặc CĂN CỨ, không phải về một con số.
TU_KHOA_TRA_CUU = re.compile(
    r"quy dinh (?:o dau|tai dau)|can cu nao|van ban nao|dieu nao|"
    r"thu tuc|ho so|trinh tu|ai quyet dinh|tham quyen|co hieu luc"
)

VAI_TRO_MAU = [
    ("pho_giam_doc", r"pho giam doc|pho hieu truong"),
    ("giam_doc", r"giam doc|hieu truong"),
]


def nhan_dien(cau_hoi: str) -> ThamSo | None:
    """Đọc câu hỏi thành tham số tính định mức; None nghĩa là câu này không
    thuộc phạm vi Thông tư 04/2026, hoặc chỉ hỏi căn cứ chứ không hỏi con số."""
    if not cau_hoi:
        return None
    thap = bo_dau(cau_hoi)
    if TU_KHOA_TRA_CUU.search(thap):
        return None
    if not TU_KHOA_DINH_MUC.search(thap):
        return None

    if not TU_KHOA_GDTX.search(thap):
        return None
    # Câu nhắc cả giáo dục thường xuyên lẫn một cấp học khác thì đang so sánh
    # hai chế độ - trả lời bằng con số của riêng một bên là trả lời nửa vời.
    if CAP_HOC_KHAC.search(thap):
        return None

    ts = ThamSo()
    ts.vai_tro = next(
        (v for v, mau in VAI_TRO_MAU if re.search(mau, thap)), "giao_vien"
    )

    for kg in KHOAN_GIAM:
        if kg.mau and re.search(kg.mau, thap):
            ts.khoan_giam.append(kg)

    for mau, cc in NGOAI_KHO:
        if re.search(mau, thap):
            ts.can_cu_ngoai_kho.append(cc)

    # Mức giảm chung chỉ áp dụng khi câu hỏi không nêu nhiệm vụ nào cụ thể.
    # "Kiêm nhiệm công đoàn" đã là một nhiệm vụ có tên, và Điều 9 khoản 3 đẩy
    # nó sang Thông tư 08/2016 - cộng thêm 4 tiết của "vị trí việc làm khác"
    # vào đó là vừa cảnh báo không có căn cứ vừa lặng lẽ tính một con số.
    if not ts.khoan_giam and not ts.can_cu_ngoai_kho:
        if re.search(KIEM_NHIEM_KHAC.mau, thap):
            ts.khoan_giam.append(KIEM_NHIEM_KHAC)

    m = re.search(r"(\d{1,2})\s*tuan\s*(?:thuc day)?", thap)
    if m:
        so = int(m.group(1))
        if 1 <= so <= 52:
            ts.so_tuan = so

    # "đang dạy 22 tiết/tuần" - số tiết đang được phân công, để tính phần vượt.
    m = re.search(
        r"(?:day|phan cong|dang day|thuc day)\s*(?:la\s*)?(\d{1,2}(?:[.,]\d)?)"
        r"\s*tiet\s*(?:/|mot |moi )?\s*tuan",
        thap,
    )
    if m:
        ts.so_tiet_thuc_day = float(m.group(1).replace(",", "."))

    return ts


# ============================================================
# TRÌNH BÀY
# ============================================================
def dinh_dang(kq: KetQua) -> str:
    """Bảng định mức dạng Markdown: kết luận trước, rồi từng dòng kèm căn cứ."""
    ts = kq.tham_so
    if ts.vai_tro == "giam_doc":
        chuc = "Giám đốc cơ sở giáo dục thường xuyên"
    elif ts.vai_tro == "pho_giam_doc":
        chuc = "Phó giám đốc cơ sở giáo dục thường xuyên"
    else:
        chuc = "Giáo viên giảng dạy chương trình giáo dục thường xuyên"

    # Điều 8 chỉ quy định định mức NĂM cho giám đốc và phó giám đốc. Chia ra
    # tiết/tuần rồi đưa lên đầu thì thành một con số không có trong văn bản,
    # nên với hai chức vụ này kết luận chỉ nêu con số năm.
    if ts.vai_tro == "giao_vien":
        ket_luan = (
            f"Định mức **{dinh_dang_so(kq.dinh_muc_tuan)} tiết/tuần**, tương "
            f"ứng **{dinh_dang_so(kq.dinh_muc_nam)} tiết** trong 01 năm học "
            f"({ts.so_tuan} tuần thực dạy)."
        )
    else:
        ket_luan = (
            f"Định mức **{dinh_dang_so(kq.dinh_muc_nam)} tiết** trong 01 năm "
            f"học."
        )

    dong = [
        ket_luan,
        "",
        f"**{chuc}**",
        "",
        "| Khoản | Cách tính | Số tiết |",
        "|---|---|---:|",
    ]
    for d in kq.dong:
        dong.append(
            f"| {d.nhan} | {d.cong_thuc} | {dinh_dang_so(d.so_tiet)} |"
        )
    if ts.vai_tro == "giao_vien" and kq.tong_giam_tuan:
        dong.append(
            f"| **Định mức còn lại trong 01 tuần** | "
            f"{DINH_MUC_TUAN} − {dinh_dang_so(kq.tong_giam_tuan)} | "
            f"**{dinh_dang_so(kq.dinh_muc_tuan)}** |"
        )
    if ts.vai_tro == "giao_vien":
        dong.append(
            f"| **Định mức trong 01 năm học** | "
            f"{dinh_dang_so(kq.dinh_muc_tuan)} × {ts.so_tuan} tuần | "
            f"**{dinh_dang_so(kq.dinh_muc_nam)}** |"
        )

    if ts.so_tiet_thuc_day is not None:
        nhan = "Số tiết dạy vượt" if kq.tiet_vuot_tuan >= 0 else "Còn thiếu so với định mức"
        dong.append(
            f"| **{nhan}** | {dinh_dang_so(ts.so_tiet_thuc_day)} được phân công "
            f"− {dinh_dang_so(kq.dinh_muc_tuan)} định mức | "
            f"**{dinh_dang_so(abs(kq.tiet_vuot_tuan))}** |"
        )

    dong.append("")
    dong.append("**Căn cứ:**")
    for cc in kq.can_cu_da_dung:
        nhan = "" if cc.trong_kho else " *(chưa có trong kho tài liệu)*"
        dong.append(f"- {cc.mo_ta()}{nhan}")

    if kq.canh_bao:
        dong.append("")
        dong.append("**Lưu ý:**")
        for c in kq.canh_bao:
            dong.append(f"- {c}")

    dong.append("")
    dong.append(
        "*Phép tính do công cụ tính định mức thực hiện, không phải mô hình ngôn "
        "ngữ sinh ra. Kết quả chỉ áp dụng cho giáo viên cơ sở giáo dục thường "
        "xuyên theo Thông tư 04/2026/TT-BGDĐT, và chưa gồm tiết quy đổi từ các "
        "hoạt động chuyên môn ở Điều 11 vì số tiết quy đổi do giám đốc quyết "
        "định theo từng việc.*"
    )
    return "\n".join(dong)


def nguon_trich_dan(kq: KetQua) -> list[dict]:
    return nguon_tu_can_cu(kq.can_cu_da_dung)


def tra_loi(cau_hoi: str) -> tuple[str, list[dict]] | None:
    """Đường tắt cho chỗ gọi: câu hỏi vào, (bảng định mức, nguồn) ra, None nếu
    không phải câu hỏi định mức tiết dạy trong phạm vi Thông tư 04/2026."""
    ts = nhan_dien(cau_hoi)
    if ts is None:
        return None
    kq = tinh(ts)
    return dinh_dang(kq), nguon_trich_dan(kq)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    ket_qua = tra_loi(" ".join(argv[1:]))
    if ket_qua is None:
        print("Không nhận ra đây là câu hỏi định mức tiết dạy của giáo viên "
              "cơ sở giáo dục thường xuyên.")
        return 1
    print(ket_qua[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
