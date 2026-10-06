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

Tắt bộ lọc bằng RAG_LOC_TU_NGU=0.
"""

from __future__ import annotations

import os
import re
import unicodedata
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


_MAU_CO_DAU = _bien_dich(TU_CO_DAU)
_MAU_KHONG_DAU = _bien_dich(TU_KHONG_DAU)


def _tu_don(danh_sach: dict[str, tuple[str, ...]]) -> list[tuple[str, str]]:
    """(nhóm, từ) của các mục một chữ, đủ dài để tìm như chuỗi con."""
    return [
        (nhom, tu) for nhom, cac_tu in danh_sach.items() for tu in cac_tu
        if " " not in tu and "*" not in tu and len(tu) >= 3
    ]


_TU_DON_CO_DAU = _tu_don(TU_CO_DAU)
_TU_DON_KHONG_DAU = _tu_don(TU_KHONG_DAU)
_RE_HOP_LE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(c) for c in CUM_HOP_LE) + r")(?!\w)"
)


# ============================================================
# KIỂM TRA
# ============================================================
@dataclass(frozen=True)
class KetQuaLoc:
    vi_pham: bool
    # Mã nhóm vi phạm, theo thứ tự khai báo: "chui_the", "tuc_tiu",
    # "tinh_duc", "xuc_pham". Dùng cho log và thống kê.
    nhom: tuple[str, ...] = ()
    # Từ đã khớp (dạng sau chuẩn hoá). Chỉ để ghi log và viết test, KHÔNG
    # đưa ngược lên giao diện.
    tu_khop: tuple[str, ...] = ()


def kiem_tra(van_ban: str) -> KetQuaLoc:
    """Tìm từ ngữ không phù hợp trong văn bản người dùng gõ.

    Chi phí O(độ dài câu): mỗi góc nhìn chỉ qua một biểu thức chính quy cho
    mỗi nhóm, không có vòng lặp theo từng từ trong danh sách.
    """
    chuan = _RE_HOP_LE.sub(" ", _chuan_hoa(van_ban))
    if not chuan:
        return KetQuaLoc(False)
    cac_dang = (chuan, *_cac_dang_go_lach(chuan))
    goc_nhin = (
        (_MAU_CO_DAU, cac_dang),
        (_MAU_KHONG_DAU, tuple(_goc_khong_dau(d) for d in cac_dang)),
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
        tu_don = _TU_DON_KHONG_DAU if bo_dau(khoi) == khoi else _TU_DON_CO_DAU
        for nhom, tu in tu_don:
            if any(tu in k for k in cac_khoi):
                if nhom not in nhom_vi_pham:
                    nhom_vi_pham.append(nhom)
                if tu not in tu_khop:
                    tu_khop.append(tu)
    if not nhom_vi_pham:
        return KetQuaLoc(False)
    thu_tu = list(TU_CO_DAU)
    return KetQuaLoc(
        True,
        tuple(sorted(nhom_vi_pham, key=thu_tu.index)),
        tuple(tu_khop),
    )


def co_tu_ngu_khong_phu_hop(van_ban: str) -> bool:
    return kiem_tra(van_ban).vi_pham


def dang_bat() -> bool:
    return os.getenv("RAG_LOC_TU_NGU", "1") == "1"


__all__ = [
    "CUM_HOP_LE",
    "KetQuaLoc",
    "LOI_NHAC",
    "TU_CO_DAU",
    "TU_KHONG_DAU",
    "co_tu_ngu_khong_phu_hop",
    "dang_bat",
    "kiem_tra",
]
