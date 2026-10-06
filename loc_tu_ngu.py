"""
LỌC TỪ NGỮ KHÔNG PHÙ HỢP TRONG CÂU HỎI
=====================================

Chặn câu hỏi có từ chửi thề, tục tĩu hoặc nội dung 18+ trước khi nó đi vào
truy hồi và mô hình ngôn ngữ. Trợ lý dùng trong môi trường học đường: trả lời
một câu chửi thề thì vừa phí một lượt sinh trên CPU, vừa có nguy cơ mô hình
lặp lại đúng những chữ đó trong câu trả lời.

Khó nhất ở tiếng Việt là BỎ DẤU. Rất nhiều từ tục khi bỏ dấu trùng với chữ
thường gặp nhất trong kho giáo dục:

    lồn  -> lon   (lon nước, bù lon)        cặc  -> cac   (các)
    buồi -> buoi  (buổi học)                đéo  -> deo   (đeo khẩu trang)
    đụ   -> du    (du lịch, dự án)          chịch -> chich (chích ngừa)
    đụ má -> du ma (tiền dư mà ...)         chó đẻ -> cho de (cho dễ hiểu)

Nên KHÔNG được bỏ dấu cả câu rồi so như can_cu_van_ban.bo_dau vẫn làm cho các
công cụ tính. Ở đây có hai danh sách:

  - TU_CO_DAU: so trên câu giữ nguyên dấu. Chỉ khớp khi người dùng gõ đúng dấu.
  - TU_KHONG_DAU: so trên "góc nhìn không dấu" - chỉ gồm những chữ người dùng
    VỐN gõ không dấu; chữ nào có dấu bị thay bằng ô trống. Nhờ vậy "tiền dư mà"
    không bao giờ biến thành "du ma". Danh sách này chỉ nhận những cụm mà ở
    dạng không dấu cũng không thể đọc thành nghĩa khác ("dcm", "vcl", "dit me").

Ngược lại, KHÔNG chặn thuật ngữ khoa học và pháp lý: "tình dục", "giáo dục
giới tính", "sức khỏe sinh sản", "khiêu dâm", "mại dâm", "dương vật" đều có
trong SGK Sinh học, Giáo dục công dân và văn bản luật trong kho. Bộ lọc nhắm
vào cách NÓI tục, không nhắm vào CHỦ ĐỀ.

Lọc theo danh sách thì luôn có hai giới hạn, nên ghi rõ ở đây:
  - Bỏ sót: cách viết lách luật mới, gõ nửa dấu nửa không ("dit mẹ"), tiếng
    lóng địa phương. Thêm từ vào danh sách khi gặp, kèm test.
  - Chặn nhầm (lỗi "Scunthorpe"): mỗi từ thêm vào phải tự hỏi "bỏ dấu đi / ghép
    với chữ bên cạnh thì nó có nghĩa gì khác không?". Test TU_HOP_LE trong
    tests/test_loc_tu_ngu.py là chốt chặn cho kiểu hỏng này.

Giao diện (static/loc-tu-ngu.js) chạy đúng thuật toán này, với danh sách lấy
từ /api/loc-tu-ngu, để báo người dùng sửa câu trước khi gửi. Sửa thuật toán ở
đây thì sửa cả bên đó: tests/test_loc_tu_ngu.py chạy cùng bộ câu qua hai bản.

Tắt bộ lọc bằng RAG_LOC_TU_NGU=0 (tắt luôn phía giao diện).
"""

from __future__ import annotations

import os
import re
import sqlite3
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass

from can_cu_van_ban import bo_dau

# ============================================================
# DANH SÁCH TỪ
# ============================================================
# Viết chữ thường. Khoảng trắng trong cụm khớp với một hay nhiều khoảng trắng.
# Dấu * khớp đúng dấu * (kiểu viết che "đ*t", "f*ck").
# Mỗi nhóm có mã riêng để thống kê biết người dùng vấp loại nào nhiều.

TU_CO_DAU: dict[str, tuple[str, ...]] = {
    "chui_the": (
        # Không có "đm" đứng riêng: giáo viên viết tắt "đm" cho "định mức".
        "địt", "đụ", "đéo", "đù má", "đù mé", "đụ má", "đụ mẹ",
        "đm mày", "đmm", "đcm", "đcmm", "đkm", "đkmm",
        "con mẹ mày", "tổ cha mày", "tiên sư bố", "tiên sư cha",
        "vãi lồn", "vãi cặc", "đ*t", "đ**", "đ*m",
    ),
    "tuc_tiu": (
        "lồn", "lìn", "cặc", "kặc", "cặk", "buồi", "đĩ", "con điếm", "đĩ điếm",
        "bú cu", "bú cặc", "bú lồn", "liếm lồn", "mặt lồn",
        "như cứt", "đồ cứt", "ăn cứt",
        "l*n", "l**", "c*c", "c**",
    ),
    # Không có "ảnh nóng", "gái gọi": giáo viên hỏi thật về xử lý học sinh
    # phát tán ảnh nóng. Cũng không có "phim cấp ba" vì "cấp ba" là THPT.
    "tinh_duc": (
        "chịch", "nứng", "phim người lớn", "ảnh sex", "truyện sex",
    ),
    # Không có "óc lợn" (món ăn), "con chó" (con vật).
    "xuc_pham": (
        "óc chó", "đồ chó", "thằng chó", "chó đẻ", "thằng ngu", "con ngu",
        "đồ ngu", "thằng khốn", "đồ khốn",
    ),
}

# Mỗi mục ở đây đã được thử: gõ lại mọi cách thêm dấu vẫn không ra câu bình
# thường. Những mục bị loại vì ra câu bình thường: "con cac" (còn các), "an cac"
# (ăn các), "bu cac" (bù các), "du me" (dù mẹ), "cho de" (cho dễ), "oc lon"
# (ốc lớn), "con me may" (con, mẹ may áo), "lon"/"cac"/"buoi"/"deo"/"du".
TU_KHONG_DAU: dict[str, tuple[str, ...]] = {
    "chui_the": (
        "dcm", "dcmm", "dkm", "dkmm", "dmm", "djt", "dit me", "dit con me",
        "dit me may", "du ma may", "deo biet", "deo hieu", "vcl", "vkl", "clgt",
        "cmnr", "cmm",
        # Tiếng Anh.
        "fuck", "fucking", "fucked", "fucker", "motherfucker", "f*ck", "f**k",
        "shit", "bullshit", "sh*t", "bitch", "b*tch", "asshole", "cunt",
    ),
    "tuc_tiu": (
        "loz", "lozz", "dickhead", "pussy", "blowjob",
    ),
    "tinh_duc": (
        "phim sex", "clip sex", "xem sex", "anh sex", "truyen sex", "web sex",
        "sex video", "phim heo", "phim nguoi lon", "phim jav", "xem jav",
        "porn", "porno", "pornhub", "xvideos", "xnxx", "hentai", "nudes",
    ),
    "xuc_pham": (
        "oc cho", "thang ngu",
    ),
}

# Cụm hợp lệ có chứa một mục ở trên: xoá trước khi so. Viết cả dạng có dấu
# lẫn không dấu vì mỗi dạng được so trên một góc nhìn riêng.
CUM_HOP_LE: tuple[str, ...] = (
    "hạt óc chó", "quả óc chó", "dầu óc chó", "sữa óc chó", "bánh óc chó",
    "hat oc cho", "qua oc cho", "dau oc cho", "sua oc cho", "banh oc cho",
)

LOI_NHAC = (
    "Câu hỏi có từ ngữ không phù hợp với môi trường học đường nên tôi không "
    "trả lời. Bạn vui lòng diễn đạt lại một cách lịch sự, tôi sẵn sàng hỗ trợ."
)


# ============================================================
# CHUẨN HOÁ
# ============================================================
# Chữ cái (không tính số và gạch dưới, vốn cũng nằm trong \w).
_CHU = r"[^\W\d_]"
# Ký tự "leet" chỉ đổi khi kẹp giữa hai chữ cái: "l0n", "sh!t", "đ1t". Số đứng
# riêng ("lớp 10", "12%") giữ nguyên.
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "@": "a", "!": "i", "$": "s"})
_RE_LEET = re.compile(rf"(?<={_CHU})[0134@!$]+(?={_CHU})")
# Mọi thứ không phải chữ, số hay dấu * thành khoảng trắng: "đ.m", "địt-mẹ".
_RE_PHAN_CACH = re.compile(r"[^\w*]+|_+")
# Chuỗi chữ cái đứng lẻ bị tách cố ý: "đ ị t", "d i t m e" (sau khi "." đã
# thành khoảng trắng). Cần ít nhất hai chữ lẻ liền nhau.
_RE_CHU_LE = re.compile(rf"(?<!\S){_CHU}(?: {_CHU}(?!\S))+")
_RE_LAP = re.compile(r"(\w)\1+")
_RE_LAP_3 = re.compile(r"(\w)\1{2,}")


def _chuan_hoa(van_ban: str) -> str:
    """Hạ chữ thường, gộp dạng Unicode, bỏ ký tự vô hình, đổi ký tự leet,
    thay dấu câu bằng khoảng trắng."""
    van_ban = unicodedata.normalize("NFC", van_ban or "").lower()
    # Ký tự định dạng vô hình (U+200B...) chèn giữa chữ để lách bộ lọc.
    van_ban = "".join(c for c in van_ban if unicodedata.category(c) != "Cf")
    van_ban = _RE_LEET.sub(lambda m: m.group().translate(_LEET), van_ban)
    return " ".join(_RE_PHAN_CACH.sub(" ", van_ban).split())


def _cac_dang_go_lach(van_ban: str) -> tuple[str, ...]:
    """Các dạng gỡ cách viết lách: ghép chữ lẻ ("đ ị t" -> "địt"), rồi gộp
    chữ lặp ("địttttt" -> "địt", "vcllll" -> "vcl").

    Gộp còn một chữ làm hỏng những mục vốn có chữ đôi ("đmm", "dcmm"), nên
    giữ thêm dạng chưa gộp ("đ.m.m" -> "đmm") và dạng gộp còn hai chữ
    ("đmmmm" -> "đmm")."""
    ghep = _RE_CHU_LE.sub(lambda m: m.group().replace(" ", ""), van_ban)
    return ghep, _RE_LAP_3.sub(r"\1\1", ghep), _RE_LAP.sub(r"\1", ghep)


def _goc_khong_dau(van_ban: str) -> str:
    """Chỉ giữ chữ người dùng gõ không dấu; chữ có dấu thành ô trống "#" để
    không ghép được với chữ bên cạnh thành một cụm trong TU_KHONG_DAU."""
    return " ".join(
        tu if bo_dau(tu) == tu else "#" for tu in van_ban.split()
    )


def _bien_dich(danh_sach: dict[str, tuple[str, ...]]) -> dict[str, re.Pattern]:
    """Một biểu thức chính quy cho mỗi nhóm, khớp nguyên từ."""
    ket_qua = {}
    for nhom, cac_tu in danh_sach.items():
        # Mục dài đi trước để "đụ má" thắng "đụ" khi báo từ khớp.
        mau = "|".join(
            r"\s+".join(re.escape(chu) for chu in tu.split())
            for tu in sorted(set(cac_tu), key=len, reverse=True)
        )
        ket_qua[nhom] = re.compile(rf"(?<![\w*])(?:{mau})(?![\w*])")
    return ket_qua


def _tu_don(danh_sach: dict[str, tuple[str, ...]]) -> list[tuple[str, str]]:
    """(nhóm, từ) của các mục một chữ, đủ dài để tìm như chuỗi con."""
    return [
        (nhom, tu) for nhom, cac_tu in danh_sach.items() for tu in cac_tu
        if " " not in tu and "*" not in tu and len(tu) >= 3
    ]


_RE_HOP_LE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(c) for c in CUM_HOP_LE) + r")(?!\w)"
)


# ============================================================
# KIỂM TRA
# ============================================================
@dataclass(frozen=True)
class KetQuaLoc:
    vi_pham: bool
    # Mã nhóm vi phạm, theo thứ tự trong NHOM: "chui_the", "tuc_tiu",
    # "tinh_duc", "xuc_pham". Dùng cho log và thống kê.
    nhom: tuple[str, ...] = ()
    # Từ đã khớp (dạng sau chuẩn hoá). Chỉ để ghi log, viết test và cho quản
    # trị viên thử câu; KHÔNG đưa ngược lên giao diện người hỏi.
    tu_khop: tuple[str, ...] = ()


@dataclass(frozen=True)
class _BoLoc:
    """Các mẫu đã biên dịch từ một bộ danh sách. Dựng lại cả bộ khi quản trị
    viên thêm hay xoá từ, rồi thay một lần: luồng đang kiểm tra dở vẫn dùng
    trọn bộ cũ, không bao giờ thấy bộ dựng nửa chừng."""

    co_dau: dict[str, tuple[str, ...]]
    khong_dau: dict[str, tuple[str, ...]]
    mau_co_dau: dict[str, re.Pattern]
    mau_khong_dau: dict[str, re.Pattern]
    tu_don_co_dau: list[tuple[str, str]]
    tu_don_khong_dau: list[tuple[str, str]]

    @classmethod
    def dung(cls, co_dau: dict, khong_dau: dict) -> "_BoLoc":
        # Nhóm không còn từ nào thì bỏ hẳn: mẫu rỗng "(?:)" khớp mọi chỗ.
        co_dau = {n: tuple(t) for n, t in co_dau.items() if t}
        khong_dau = {n: tuple(t) for n, t in khong_dau.items() if t}
        return cls(
            co_dau, khong_dau, _bien_dich(co_dau), _bien_dich(khong_dau),
            _tu_don(co_dau), _tu_don(khong_dau),
        )


def kiem_tra(van_ban: str, bo_loc: _BoLoc | None = None) -> KetQuaLoc:
    """Tìm từ ngữ không phù hợp trong văn bản người dùng gõ.

    bo_loc: bỏ trống là bộ đang dùng (có sẵn + quản trị viên thêm); truyền vào
    để thử riêng một từ (xem thu_tu_moi).

    Chi phí O(độ dài câu): mỗi góc nhìn chỉ qua một biểu thức chính quy cho
    mỗi nhóm, không có vòng lặp theo từng từ trong danh sách.
    """
    bo_loc = bo_loc or _bo_loc_hien_tai()
    chuan = _RE_HOP_LE.sub(" ", _chuan_hoa(van_ban))
    if not chuan:
        return KetQuaLoc(False)
    cac_dang = (chuan, *_cac_dang_go_lach(chuan))
    goc_nhin = (
        (bo_loc.mau_co_dau, cac_dang),
        (bo_loc.mau_khong_dau, tuple(_goc_khong_dau(d) for d in cac_dang)),
    )
    nhom_vi_pham: list[str] = []
    tu_khop: list[str] = []
    for bo_mau, cac_dang in goc_nhin:
        for nhom, mau in bo_mau.items():
            for dang in cac_dang:
                for khop in mau.finditer(dang):
                    if nhom not in nhom_vi_pham:
                        nhom_vi_pham.append(nhom)
                    if khop.group() not in tu_khop:
                        tu_khop.append(khop.group())
    # Chữ lẻ đã ghép ("đ ị t m ẹ" -> "địtmẹ") không còn ranh giới từ, nên tìm
    # từ đơn như chuỗi con. Chỉ làm trên phần ghép, không trên cả câu: tìm
    # chuỗi con trên cả câu thì "lồn" khớp luôn "lồng".
    for khoi in _RE_CHU_LE.findall(chuan):
        khoi = khoi.replace(" ", "")
        cac_khoi = (khoi, _RE_LAP.sub(r"\1", khoi))
        tu_don = bo_loc.tu_don_khong_dau if bo_dau(khoi) == khoi else bo_loc.tu_don_co_dau
        for nhom, tu in tu_don:
            if any(tu in k for k in cac_khoi):
                if nhom not in nhom_vi_pham:
                    nhom_vi_pham.append(nhom)
                if tu not in tu_khop:
                    tu_khop.append(tu)
    if not nhom_vi_pham:
        return KetQuaLoc(False)
    return KetQuaLoc(
        True,
        tuple(sorted(nhom_vi_pham, key=list(NHOM).index)),
        tuple(tu_khop),
    )


def co_tu_ngu_khong_phu_hop(van_ban: str) -> bool:
    return kiem_tra(van_ban).vi_pham


def dang_bat() -> bool:
    return os.getenv("RAG_LOC_TU_NGU", "1") == "1"


def du_lieu_cho_giao_dien() -> dict:
    """Danh sách từ cho static/loc-tu-ngu.js kiểm tra trước khi gửi.

    Giao diện lấy danh sách từ đây chứ không tự chép một bản: hai bản chép tay
    sớm muộn sẽ lệch nhau. Giao diện chỉ để báo sớm cho người dùng sửa câu;
    chốt chặn thật vẫn là kiem_tra() trong stream_answer, vì ai cũng gọi thẳng
    được /api/chat/stream mà không qua giao diện."""
    bo_loc = _bo_loc_hien_tai()
    return {
        "bat": dang_bat(),
        "co_dau": {nhom: list(cac_tu) for nhom, cac_tu in bo_loc.co_dau.items()},
        "khong_dau": {nhom: list(cac_tu) for nhom, cac_tu in bo_loc.khong_dau.items()},
        "hop_le": list(CUM_HOP_LE),
    }


# ============================================================
# TỪ QUẢN TRỊ VIÊN THÊM
# ============================================================
# Danh sách có sẵn ở trên nằm trong mã nguồn, có test chốt chặn. Từ mới gặp
# trong thực tế (tiếng lóng mới, cách viết lách mới) thì quản trị viên thêm qua
# giao diện, không phải sửa mã: lưu trong SQLite, bộ lọc dựng lại ngay.
#
# Từ thêm vào đi đúng một trong hai danh sách theo chính cách nó được gõ: có
# dấu thì vào danh sách có dấu, không dấu thì vào danh sách không dấu - cùng
# quy tắc với danh sách có sẵn. Từ không dấu là thứ dễ chặn nhầm nhất ("cac" là
# "các"), nên giao diện bắt xem trước nó chặn những câu hỏi cũ nào (thu_tu_moi)
# rồi mới cho thêm.

NHOM: dict[str, str] = {
    "chui_the": "Chửi thề",
    "tuc_tiu": "Tục tĩu",
    "tinh_duc": "Tình dục, 18+",
    "xuc_pham": "Xúc phạm",
}

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_DB = os.path.abspath(os.getenv(
    "RAG_TU_NGU_CAM_DB", os.path.join(THU_MUC_DU_AN, "tu_ngu_cam.db")
))
DO_DAI_TOI_DA = 60

_khoa = threading.Lock()
_ket_noi: sqlite3.Connection | None = None
_bo_loc: _BoLoc | None = None


class LoiTuNgu(ValueError):
    def __init__(self, thong_bao: str, ma_http: int = 400):
        super().__init__(thong_bao)
        self.ma_http = ma_http


def _connect() -> sqlite3.Connection:
    global _ket_noi
    if _ket_noi is None:
        _ket_noi = sqlite3.connect(DUONG_DAN_DB, check_same_thread=False)
        _ket_noi.row_factory = sqlite3.Row
        _ket_noi.executescript(
            """
            CREATE TABLE IF NOT EXISTS tu_them (
                id        TEXT PRIMARY KEY,
                tu        TEXT NOT NULL UNIQUE,   -- dạng đã chuẩn hoá
                nhom      TEXT NOT NULL,
                tao_luc   REAL NOT NULL,
                tao_boi   TEXT NOT NULL
            );
            """
        )
        _ket_noi.commit()
    return _ket_noi


def dong_ket_noi() -> None:
    """Đóng sổ và quên bộ lọc đã dựng (test đổi DUONG_DAN_DB rồi gọi hàm này)."""
    global _ket_noi, _bo_loc
    with _khoa:
        if _ket_noi is not None:
            _ket_noi.close()
            _ket_noi = None
        _bo_loc = None


def _dung_bo_loc() -> _BoLoc:
    co_dau = {nhom: list(TU_CO_DAU.get(nhom, ())) for nhom in NHOM}
    khong_dau = {nhom: list(TU_KHONG_DAU.get(nhom, ())) for nhom in NHOM}
    for muc in danh_sach_tu_them():
        dich = khong_dau if muc["khong_dau"] else co_dau
        dich[muc["nhom"]].append(muc["tu"])
    return _BoLoc.dung(co_dau, khong_dau)


def _bo_loc_hien_tai() -> _BoLoc:
    global _bo_loc
    bo_loc = _bo_loc
    if bo_loc is None:
        try:
            bo_loc = _dung_bo_loc()
        except sqlite3.Error:
            # Sổ hỏng hay không mở được: vẫn lọc bằng danh sách có sẵn, không
            # để lỗi lưu trữ làm hỏng mọi câu hỏi.
            bo_loc = _BoLoc.dung(TU_CO_DAU, TU_KHONG_DAU)
        _bo_loc = bo_loc
    return bo_loc


def _lam_moi() -> None:
    global _bo_loc
    _bo_loc = _dung_bo_loc()


def chuan_hoa_tu_moi(tu: str) -> str:
    """Kiểm tra và đưa từ quản trị viên gõ về dạng lưu.

    Từ phải sống sót qua đúng bước chuẩn hoá mà câu hỏi phải qua: "đ.m" thành
    "đ m", "l0n" thành "lon" - lưu nguyên dạng gõ thì không bao giờ khớp, lưu
    dạng đã đổi thì "l0n" âm thầm thành "lon" (lon nước). Nên báo lỗi để người
    thêm gõ lại, thay vì tự đổi hộ."""
    goc = " ".join(unicodedata.normalize("NFC", tu or "").lower().split())
    if len(goc) < 2:
        raise LoiTuNgu("Từ cần ít nhất 2 ký tự.")
    if len(goc) > DO_DAI_TOI_DA:
        raise LoiTuNgu(f"Từ dài quá {DO_DAI_TOI_DA} ký tự.")
    if not re.search(_CHU, goc):
        raise LoiTuNgu("Từ phải có ít nhất một chữ cái.")
    if _chuan_hoa(goc) != goc:
        raise LoiTuNgu(
            "Chỉ gõ chữ, số, khoảng trắng và dấu *. Không cần thêm các cách viết "
            "lách như \"đ.m\", \"l0n\": bộ lọc tự gỡ dấu chấm và số thay chữ."
        )
    if goc in CUM_HOP_LE:
        raise LoiTuNgu("Cụm này đang nằm trong danh sách cụm hợp lệ.")
    return goc


def _la_khong_dau(tu: str) -> bool:
    return bo_dau(tu) == tu


def thu_tu_moi(tu: str, nhom: str, cac_cau: list[str], so_vi_du: int = 5) -> dict:
    """Xem trước một từ sắp thêm: dạng sẽ lưu, thuộc danh sách nào, và trong
    các câu hỏi cũ thì nó chặn những câu nào.

    Chỉ dựng bộ lọc từ riêng từ đó, nên câu bị đếm là câu từ này chặn THÊM chứ
    không lẫn câu vốn đã bị danh sách hiện có chặn."""
    if nhom not in NHOM:
        raise LoiTuNgu("Nhóm không hợp lệ.")
    tu = chuan_hoa_tu_moi(tu)
    khong_dau = _la_khong_dau(tu)
    bo_loc = _BoLoc.dung({} if khong_dau else {nhom: [tu]}, {nhom: [tu]} if khong_dau else {})
    bi_chan = [cau for cau in cac_cau if kiem_tra(cau, bo_loc).vi_pham]
    return {
        "tu": tu,
        "nhom": nhom,
        "khong_dau": khong_dau,
        "da_co": _da_co(tu),
        "so_cau_xet": len(cac_cau),
        "so_cau_bi_chan": len(bi_chan),
        "vi_du": [cau[:160] for cau in bi_chan[:so_vi_du]],
    }


def _da_co(tu: str) -> bool:
    """Từ đã nằm trong danh sách đang dùng, ở bất kỳ nhóm nào."""
    hien_tai = _bo_loc_hien_tai()
    return any(
        tu in cac_tu
        for bo in (hien_tai.co_dau, hien_tai.khong_dau) for cac_tu in bo.values()
    )


def danh_sach_tu_them() -> list[dict]:
    with _khoa:
        dong = _connect().execute(
            "SELECT id, tu, nhom, tao_luc, tao_boi FROM tu_them ORDER BY tao_luc DESC"
        ).fetchall()
    return [
        {**dict(d), "khong_dau": _la_khong_dau(d["tu"])}
        for d in dong if d["nhom"] in NHOM
    ]


def them_tu(tu: str, nhom: str, nguoi_lam: dict | None = None) -> dict:
    if nhom not in NHOM:
        raise LoiTuNgu("Nhóm không hợp lệ.")
    tu = chuan_hoa_tu_moi(tu)
    if _da_co(tu):
        raise LoiTuNgu(f"\"{tu}\" đã có trong danh sách.", 409)
    muc = {
        "id": uuid.uuid4().hex,
        "tu": tu,
        "nhom": nhom,
        "tao_luc": time.time(),
        "tao_boi": ((nguoi_lam or {}).get("ten") or (nguoi_lam or {}).get("email")
                    or "Quản trị viên"),
    }
    with _khoa:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO tu_them (id, tu, nhom, tao_luc, tao_boi) VALUES (?, ?, ?, ?, ?)",
                tuple(muc.values()),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise LoiTuNgu(f"\"{tu}\" đã có trong danh sách.", 409) from exc
    _lam_moi()
    return {**muc, "khong_dau": _la_khong_dau(tu)}


def xoa_tu(ma: str) -> dict:
    with _khoa:
        conn = _connect()
        dong = conn.execute("SELECT id, tu, nhom FROM tu_them WHERE id = ?", (ma,)).fetchone()
        if dong is None:
            raise LoiTuNgu("Không tìm thấy từ này (có thể đã bị xoá).", 404)
        conn.execute("DELETE FROM tu_them WHERE id = ?", (ma,))
        conn.commit()
    _lam_moi()
    return dict(dong)


__all__ = [
    "CUM_HOP_LE",
    "KetQuaLoc",
    "LOI_NHAC",
    "LoiTuNgu",
    "NHOM",
    "TU_CO_DAU",
    "TU_KHONG_DAU",
    "chuan_hoa_tu_moi",
    "co_tu_ngu_khong_phu_hop",
    "dang_bat",
    "danh_sach_tu_them",
    "du_lieu_cho_giao_dien",
    "kiem_tra",
    "them_tu",
    "thu_tu_moi",
    "xoa_tu",
]
