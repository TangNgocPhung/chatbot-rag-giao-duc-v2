"""CÔNG CỤ SỐ HỌC - PHÉP TÍNH DO PYTHON LÀM, KHÔNG ĐỂ MÔ HÌNH LÀM TOÁN
=====================================================================
Cùng một lý lẽ với tinh_luong.py, nhưng cho những câu số học trần trụi:
"12% của 2.340.000 là bao nhiêu", "35 × 17", "5 triệu tăng 8%". Người dùng gõ
những câu này khá thường xuyên ngay giữa lúc tra cứu văn bản, và hiện tại
chúng đi trọn đường RAG: truy hồi vài đoạn thông tư chẳng liên quan gì, rồi để
một model 3B trên CPU làm phép nhân trong 150 giây. Vừa chậm, vừa không có gì
bảo đảm con số đúng - mà hậu kiểm (kiem_tra_tra_loi.py) thì lại gắn cờ chính
con số đó, vì kết quả tính ra không có nguyên văn trong đoạn trích nào.

CỔNG NHẬN CÂU RẤT HẸP. Câu hỏi chỉ được nhận khi phần còn lại - sau khi bỏ mấy
chữ dẫn như "tính", "là bao nhiêu" - là một biểu thức số học thuần túy. Hẹp như
vậy vì công cụ này đứng TRƯỚC cả RAG: nhận nhầm một câu tra cứu thì người dùng
mất hẳn câu trả lời, còn bỏ sót một câu số học thì họ chỉ phải chờ lâu như cũ.
Hai loại lỗi không cân nhau, nên cổng nghiêng hẳn về phía bỏ sót.

KHÔNG DÙNG eval(). Chuỗi đi vào đây là chuỗi người dùng gõ. Biểu thức được tách
token rồi hạ xuống bằng bộ phân tích đệ quy viết tay ở dưới - nó chỉ biết đúng
sáu phép toán, không có tên hàm, không có thuộc tính, không có đường nào chạy
ra ngoài phép tính.

    python tinh_toan.py "12% của 2.340.000"
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from can_cu_van_ban import bo_dau


# Chặn trên cho mọi thứ có thể phình ra. Người dùng gõ một dòng trong ô chat,
# không ai gõ biểu thức 200 token - còn 2^999999 thì treo cả tiến trình.
DAI_TOI_DA = 200
SO_TOKEN_TOI_DA = 60
MU_TOI_DA = 64
KET_QUA_TOI_DA = 1e15


class LoiTinh(Exception):
    """Biểu thức đọc được nhưng không tính ra số (chia cho 0, mũ quá lớn...).

    Khác hẳn với "không nhận ra câu này": ở đây người dùng RÕ RÀNG muốn một
    phép tính, nên phải nói thẳng vì sao không tính được, thay vì lặng lẽ đẩy
    câu sang RAG để nhận về một câu trả lời lạc đề.
    """


# ============================================================
# ĐỌC SỐ KIỂU VIỆT
# ============================================================
# Văn bản quy phạm viết "2.340.000 đồng" và "hệ số 2,34" - dấu chấm phân nhóm
# nghìn, dấu phẩy ngăn phần thập phân. Người dùng chép thẳng con số từ Thông tư
# vào ô chat, nên phải đọc đúng quy ước đó chứ không phải quy ước của Python.
#
# Chỗ duy nhất còn nhập nhằng là một dấu chấm với đúng ba chữ số sau nó:
# "2.340" hiểu là hai nghìn ba trăm bốn mươi (quy ước Việt), không phải 2,34.
# "2.34" - hai chữ số - thì hiểu là số thập phân.
MAU_NGHIN = re.compile(r"^\d{1,3}(?:\.\d{3})+$")
MAU_THAP_PHAN_CHAM = re.compile(r"^\d+\.\d+$")

DON_VI = {
    "nghin": 1_000, "ngan": 1_000,
    "trieu": 1_000_000,
    "ty": 1_000_000_000, "ti": 1_000_000_000,
}


def doc_so(chuoi: str) -> float:
    """Chuỗi chữ số kiểu Việt thành số. Ném ValueError nếu không đọc nổi."""
    chuoi = chuoi.strip().rstrip(".,")
    if not chuoi:
        raise ValueError("chuỗi rỗng")

    if "," in chuoi:
        if chuoi.count(",") > 1:
            raise ValueError(f"nhiều dấu phẩy thập phân: {chuoi}")
        nguyen, le = chuoi.split(",")
        nguyen = nguyen.replace(".", "")
        if not nguyen.isdigit() or not le.isdigit():
            raise ValueError(f"không đọc được số: {chuoi}")
        return float(f"{nguyen}.{le}")

    if "." in chuoi:
        if MAU_NGHIN.match(chuoi):
            return float(chuoi.replace(".", ""))
        if MAU_THAP_PHAN_CHAM.match(chuoi):
            return float(chuoi)
        raise ValueError(f"không đọc được số: {chuoi}")

    if not chuoi.isdigit():
        raise ValueError(f"không đọc được số: {chuoi}")
    return float(chuoi)


def dinh_dang_so(x: float) -> str:
    """Số ra dạng người Việt đọc được: 2.340.000 và 12,5.

    Phần thập phân cắt ở 6 chữ số rồi bỏ số 0 thừa - đủ cho mọi phép tính người
    ta gõ trong ô chat, mà không phơi ra cái đuôi 0,30000000000000004 của số
    dấu phẩy động.
    """
    if x != x or x in (float("inf"), float("-inf")):
        raise LoiTinh("Kết quả không phải là một số hữu hạn.")
    am = x < 0
    x = abs(x)
    nguyen = int(x)
    le = x - nguyen
    chuoi = f"{nguyen:,}".replace(",", ".")
    if le:
        duoi = f"{le:.6f}".split(".")[1].rstrip("0")
        if duoi:
            chuoi = f"{chuoi},{duoi}"
    return ("-" + chuoi) if am else chuoi


# ============================================================
# TÁCH TOKEN
# ============================================================
# Ký hiệu phép toán gõ tay mỗi người một kiểu: dấu nhân có thể là ×, x hoặc *;
# dấu chia có thể là ÷, : hoặc /. Quy hết về một dạng ngay từ đây để bộ phân
# tích bên dưới chỉ phải biết một ký hiệu cho mỗi phép.
DONG_NGHIA = {"×": "*", "·": "*", "÷": "/", ":": "/", "−": "-", "–": "-", "—": "-"}

# Chữ nối thay cho dấu phép toán. "trên" là dấu chia trong "32 trên 40", và
# "của" là dấu nhân nhưng CHỈ sau dấu phần trăm - "12% của 40" là phép nhân,
# còn "điểm của lớp 3" thì không phải phép tính nào cả.
CHU_PHEP = [
    (r"\bcong\b", "+"),
    (r"\btru di\b|\btru\b", "-"),
    (r"\bnhan voi\b|\bnhan\b", "*"),
    (r"\bchia cho\b|\bchia\b", "/"),
    (r"\btren\b", "/"),
    (r"\bmu\b", "^"),
]

MAU_TOKEN = re.compile(r"""
    (?P<so>\d[\d.,]*)
  | (?P<toan_tu>[-+*/^()%])
  | (?P<khoang>\s+)
  | (?P<chu>[^\s\d\-+*/^()%]+)
""", re.VERBOSE)


@dataclass(frozen=True)
class Token:
    loai: str   # "so" | "toan_tu"
    gia_tri: str


def tach_token(bieu_thuc: str) -> list[Token]:
    """Chuỗi thành danh sách token, hoặc ném ValueError nếu có chữ lạ.

    Bất cứ chữ cái nào còn sót lại đều là lý do để từ chối cả câu: một token
    không hiểu nghĩa là đây không phải biểu thức số học, mà là câu tra cứu bị
    lọt vào nhầm chỗ.
    """
    bieu_thuc = bo_dau(bieu_thuc)
    for ky_tu, thay in DONG_NGHIA.items():
        bieu_thuc = bieu_thuc.replace(ky_tu, thay)

    token: list[Token] = []
    vi_tri = 0
    while vi_tri < len(bieu_thuc):
        khop = MAU_TOKEN.match(bieu_thuc, vi_tri)
        if khop is None:
            raise ValueError(f"ký tự lạ tại vị trí {vi_tri}")
        vi_tri = khop.end()
        if khop.lastgroup == "khoang":
            continue
        if khop.lastgroup == "chu":
            chu = khop.group().lower()
            # "5 triệu" - đơn vị đi sau một con số thì nhân con số đó lên.
            if chu in DON_VI and token and token[-1].loai == "so":
                goc = doc_so(token[-1].gia_tri) * DON_VI[chu]
                token[-1] = Token("so", repr(goc))
                continue
            # Chữ "x" đi sau một giá trị đã hoàn chỉnh - con số, dấu phần trăm
            # hay ngoặc đóng - là dấu nhân: "35 x 17", "15% x 4.980.000".
            # Chữ "x" đứng đầu hay đứng một mình thì không phải phép toán nào.
            if chu == "x" and token and (
                token[-1].loai == "so" or token[-1].gia_tri in ("%", ")")
            ):
                token.append(Token("toan_tu", "*"))
                continue
            raise ValueError(f"không hiểu chữ {chu!r}")
        if khop.lastgroup == "so":
            doc_so(khop.group())  # đọc thử ngay để lỗi nổ ở đây, không nổ sau
            token.append(Token("so", khop.group()))
        else:
            token.append(Token("toan_tu", khop.group()))

    if len(token) > SO_TOKEN_TOI_DA:
        raise ValueError("biểu thức quá dài")
    return token


# ============================================================
# PHÂN TÍCH VÀ TÍNH
# ============================================================
# Văn phạm, ưu tiên từ thấp đến cao:
#     bieu_thuc := hang (('+' | '-') hang)*
#     hang      := luy_thua (('*' | '/') luy_thua)*
#     luy_thua  := don ('^' luy_thua)?          - kết hợp phải
#     don       := ('-' | '+')* nguyen_to
#     nguyen_to := SO '%'? | '(' bieu_thuc ')' '%'?
class BoPhanTich:
    """Bộ phân tích đệ quy đi xuống. Tự viết thay vì gọi eval hay ast: ở đây
    phải đọc số kiểu Việt, phải hiểu hậu tố %, và quan trọng nhất là phải
    KHÔNG hiểu bất cứ thứ gì khác."""

    def __init__(self, token: list[Token]):
        self.token = token
        self.vi_tri = 0

    def _nhin(self) -> Token | None:
        return self.token[self.vi_tri] if self.vi_tri < len(self.token) else None

    def _an(self, gia_tri: str) -> bool:
        t = self._nhin()
        if t is not None and t.loai == "toan_tu" and t.gia_tri == gia_tri:
            self.vi_tri += 1
            return True
        return False

    def phan_tich(self) -> float:
        gia_tri = self.bieu_thuc()
        if self.vi_tri != len(self.token):
            raise ValueError("còn token thừa sau biểu thức")
        return gia_tri

    def bieu_thuc(self) -> float:
        gia_tri = self.hang()
        while True:
            if self._an("+"):
                gia_tri += self.hang()
            elif self._an("-"):
                gia_tri -= self.hang()
            else:
                return gia_tri

    def hang(self) -> float:
        gia_tri = self.luy_thua()
        while True:
            if self._an("*"):
                gia_tri *= self.luy_thua()
            elif self._an("/"):
                chia = self.luy_thua()
                if chia == 0:
                    raise LoiTinh("Không chia được cho 0.")
                gia_tri /= chia
            else:
                return gia_tri

    def luy_thua(self) -> float:
        co_so = self.don()
        if not self._an("^"):
            return co_so
        so_mu = self.luy_thua()
        if abs(so_mu) > MU_TOI_DA or so_mu != int(so_mu):
            raise LoiTinh(
                f"Chỉ tính được lũy thừa với số mũ nguyên không quá {MU_TOI_DA}."
            )
        try:
            return float(co_so) ** int(so_mu)
        except (OverflowError, ZeroDivisionError) as loi:
            raise LoiTinh("Lũy thừa này vượt quá khả năng tính.") from loi

    def don(self) -> float:
        if self._an("-"):
            return -self.don()
        if self._an("+"):
            return self.don()
        return self.nguyen_to()

    def nguyen_to(self) -> float:
        t = self._nhin()
        if t is None:
            raise ValueError("biểu thức kết thúc giữa chừng")
        if t.loai == "so":
            self.vi_tri += 1
            gia_tri = doc_so(t.gia_tri)
        elif t.gia_tri == "(":
            self.vi_tri += 1
            gia_tri = self.bieu_thuc()
            if not self._an(")"):
                raise ValueError("thiếu dấu đóng ngoặc")
        else:
            raise ValueError(f"không mở đầu biểu thức bằng {t.gia_tri!r} được")
        if self._an("%"):
            gia_tri /= 100
        return gia_tri


def tinh_bieu_thuc(bieu_thuc: str) -> float:
    gia_tri = BoPhanTich(tach_token(bieu_thuc)).phan_tich()
    if abs(gia_tri) > KET_QUA_TOI_DA:
        raise LoiTinh("Kết quả quá lớn để trình bày cho có nghĩa.")
    return gia_tri


# ============================================================
# NHẬN DIỆN CÂU HỎI
# ============================================================
# Chữ dẫn bao quanh phép tính, bỏ đi thì còn lại đúng biểu thức. Xếp cụm dài
# trước cụm ngắn: bỏ "là bao nhiêu" trước khi bỏ "là", nếu không thì "là" bị
# bốc đi trước và để lại chữ "bao nhiêu" chỏng chơ.
# Viết KHÔNG DẤU: câu hỏi đã đi qua bo_dau() trước khi bóc chữ dẫn.
CHU_DAN = [
    r"lam on", r"cho (?:minh|toi|em|anh|chi) hoi", r"cho (?:minh|toi|em) biet",
    r"giup (?:minh|toi|em) tinh",
    r"tinh giup(?: (?:minh|toi|em))?", r"tinh ho(?: (?:minh|toi|em))?",
    r"tinh gium(?: (?:minh|toi|em))?", r"tinh xem", r"tinh",
    r"ket qua (?:cua|phep tinh)?",
    r"la bao nhieu", r"bang bao nhieu", r"ra bao nhieu", r"bao nhieu",
    r"bang may", r"ra may", r"thi bang", r"bang", r"la", r"may",
    r"nhe", r"nhi", r"a", r"vay", r"the", r"voi", r"di",
]

# Kẹp \b hai đầu là BẮT BUỘC, không phải cho gọn. Sau khi bỏ dấu, "ạ" thành
# một chữ "a" trơ trọi và "là" thành "la" - không chốt biên từ thì chúng ăn mất
# chữ a giữa "cua", cắt "tang" thành "t ng", và cả câu vỡ vụn trước khi tới
# được bộ phân tích.
MAU_CHU_DAN = re.compile(r"\b(?:" + "|".join(CHU_DAN) + r")\b")

# Có mấy chữ này thì đây là câu tra cứu văn bản, không phải phép tính - nhường
# đường cho RAG kể cả khi phần còn lại trông giống biểu thức. "Thông tư 22/2021
# quy định gì" mà lọt vào đây thì sẽ thành phép chia 22 cho 2021.
MAU_TRA_CUU = re.compile(
    r"dieu\s*\d|khoan|thong tu|nghi dinh|quyet dinh|luat|van ban|quy dinh|"
    r"theo\s|can cu|hieu luc|tai lieu|o dau|the nao|nhu the nao|vi sao|tai sao|"
    r"la gi|gom nhung|hang\s*i|bac\s*\d|he so|nam hoc|lop\s*\d"
)

MAU_TANG_GIAM = re.compile(
    r"^(?P<goc>.+?)\s*(?P<huong>tang|giam)\s*(?P<ty_le>\d[\d.,]*)\s*%$"
)
MAU_TY_LE = re.compile(
    r"^(?P<phan>.+?)\s*(?:tren|/|so voi|trong)\s*(?P<tong>.+?)"
    r"\s*(?:ra|bang|=)?\s*(?:bao nhieu|may)?\s*(?:%|phan tram)$"
)
MAU_PHAN_TRAM_CUA = re.compile(r"%\s*(?:cua|of|trong so)\b")


@dataclass
class KetQua:
    """Một phép tính đã ra kết quả, kèm đúng dòng công thức đã thay số."""

    cau_goc: str
    bieu_thuc: str       # biểu thức đã chuẩn hóa, để người đọc soi lại
    gia_tri: float
    dien_giai: list[str] = field(default_factory=list)
    # Đuôi in kèm con số. Câu hỏi "32 trên 40 là bao nhiêu phần trăm" mà trả về
    # trơ một số 80 thì người đọc không biết đó là 80% hay 80 học sinh.
    hau_to: str = ""

    def so_ket_qua(self) -> str:
        return dinh_dang_so(self.gia_tri) + self.hau_to


def _bo_chu_dan(cau_hoi: str) -> str:
    """Bỏ chữ dẫn và dấu câu, còn lại phần ruột của câu hỏi.

    Dấu "=" cũng bị bỏ, vì trong ô chat nó không phải một phép toán mà là cách
    hỏi ngắn nhất: "5+3=", "5+3=?", "5+3=mấy". Bộ phân tích bên dưới không biết
    dấu "=", nên để nguyên thì cả ba câu đó rơi ra ngoài - mà đây lại đúng là
    cách người ta gõ một phép tính nhanh nhất.

    Bỏ luôn cả "=" ở giữa câu: "5+3=8 đúng không" thành "5+3 8", hai con số
    đứng cạnh nhau không thành biểu thức, câu tự rơi sang RAG. Đó là kết cục
    đúng - công cụ này tính chứ không kiểm tra đáp án hộ ai.
    """
    con = MAU_CHU_DAN.sub(" ", bo_dau(cau_hoi))
    for dau in "?!;=":
        con = con.replace(dau, " ")
    return re.sub(r"\s+", " ", con).strip(" ,.")


def _thay_chu_phep(chuoi: str) -> str:
    """Chữ nối thành dấu phép toán. "của" chỉ thành dấu nhân khi đứng ngay sau
    dấu phần trăm - ngoài ngữ cảnh đó nó là chữ của tiếng Việt, không phải
    phép toán."""
    chuoi = MAU_PHAN_TRAM_CUA.sub("% * ", chuoi)
    for mau, dau in CHU_PHEP:
        chuoi = re.sub(mau, dau, chuoi, flags=re.IGNORECASE)
    return chuoi


def _co_phep_tinh(chuoi: str) -> bool:
    """Một con số trơ trọi không phải là câu hỏi tính toán. Phải có ít nhất một
    dấu phép toán hoặc một dấu phần trăm thì mới đáng chen ngang RAG.

    Quy các ký hiệu đồng nghĩa (× ÷ :) về dạng chuẩn ngay ở đây, nếu không thì
    "2,34 × 2.340.000" bị coi là không có phép toán nào và rơi hết sang RAG.
    """
    for ky_tu, thay in DONG_NGHIA.items():
        chuoi = chuoi.replace(ky_tu, thay)
    if re.search(r"[-+*/^%]", chuoi):
        return True
    # "35 x 17" - chữ x kẹp giữa hai con số cũng là dấu nhân, đúng như cách
    # tach_token đọc nó.
    return bool(re.search(r"\d\s*[xX]\s*\d", chuoi))


def nhan_dien(cau_hoi: str) -> KetQua | None:
    """Đọc câu hỏi thành một phép tính; None nghĩa là câu này không phải số học
    thuần - để nó đi tiếp đường RAG bình thường."""
    if not cau_hoi or len(cau_hoi) > DAI_TOI_DA:
        return None
    if MAU_TRA_CUU.search(bo_dau(cau_hoi)):
        return None

    con = _bo_chu_dan(cau_hoi)
    if not con:
        return None

    for doc_hieu in (_tang_giam, _ty_le_phan_tram, _bieu_thuc_thuan):
        try:
            ket_qua = doc_hieu(cau_hoi, con)
        except ValueError:
            continue
        if ket_qua is not None:
            return ket_qua
    return None


def _tang_giam(cau_goc: str, con: str) -> KetQua | None:
    """"5 triệu tăng 8%" - tăng giảm theo tỉ lệ phải tách riêng, vì đọc thẳng
    dấu % thành phép chia 100 sẽ ra "5.000.000 + 0,08"."""
    khop = MAU_TANG_GIAM.match(con)
    if khop is None:
        return None
    goc = tinh_bieu_thuc(_thay_chu_phep(khop.group("goc")))
    ty_le = doc_so(khop.group("ty_le")) / 100
    len_xuong = khop.group("huong").lower().startswith("t")
    he_so = 1 + ty_le if len_xuong else 1 - ty_le
    dau = "+" if len_xuong else "−"
    return KetQua(
        cau_goc=cau_goc,
        bieu_thuc=f"{dinh_dang_so(goc)} × (1 {dau} {dinh_dang_so(ty_le * 100)}%)",
        gia_tri=goc * he_so,
        dien_giai=[
            f"{dinh_dang_so(goc)} × {dinh_dang_so(he_so)} = "
            f"{dinh_dang_so(goc * he_so)}",
            f"Phần {'tăng' if len_xuong else 'giảm'}: "
            f"{dinh_dang_so(abs(goc * ty_le))}",
        ],
    )


def _ty_le_phan_tram(cau_goc: str, con: str) -> KetQua | None:
    """"32 trên 40 là bao nhiêu phần trăm" - câu hỏi ngược, ra tỉ lệ chứ không
    ra một con số tuyệt đối."""
    khop = MAU_TY_LE.match(con)
    if khop is None:
        return None
    phan = tinh_bieu_thuc(_thay_chu_phep(khop.group("phan")))
    tong = tinh_bieu_thuc(_thay_chu_phep(khop.group("tong")))
    if tong == 0:
        raise LoiTinh("Không tính được tỉ lệ khi tổng bằng 0.")
    ty_le = phan / tong * 100
    return KetQua(
        cau_goc=cau_goc,
        bieu_thuc=f"{dinh_dang_so(phan)} ÷ {dinh_dang_so(tong)} × 100",
        gia_tri=ty_le,
        dien_giai=[f"{dinh_dang_so(phan)} là {dinh_dang_so(ty_le)}% của "
                   f"{dinh_dang_so(tong)}"],
        hau_to="%",
    )


def _bieu_thuc_thuan(cau_goc: str, con: str) -> KetQua | None:
    chuoi = _thay_chu_phep(con)
    if not _co_phep_tinh(chuoi):
        return None
    gia_tri = tinh_bieu_thuc(chuoi)
    return KetQua(
        cau_goc=cau_goc,
        bieu_thuc=_trinh_bay_bieu_thuc(chuoi),
        gia_tri=gia_tri,
    )


def _trinh_bay_bieu_thuc(chuoi: str) -> str:
    """Biểu thức in ra cho người đọc: dấu nhân chia dùng ký hiệu toán học, và
    mọi con số về đúng dạng nghìn kiểu Việt để đối chiếu lại với câu đã gõ."""
    ra = []
    for t in tach_token(chuoi):
        if t.loai == "so":
            ra.append(dinh_dang_so(doc_so(t.gia_tri)))
        elif t.gia_tri == "*":
            ra.append("×")
        elif t.gia_tri == "/":
            ra.append("÷")
        else:
            ra.append(t.gia_tri)
    chuoi = " ".join(ra)
    return chuoi.replace("( ", "(").replace(" )", ")").replace(" %", "%")


# ============================================================
# TRÌNH BÀY
# ============================================================
def dinh_dang(kq: KetQua) -> str:
    dong = [
        f"**{kq.so_ket_qua()}**",
        "",
        f"`{kq.bieu_thuc}` = **{kq.so_ket_qua()}**",
    ]
    for d in kq.dien_giai:
        dong.append("")
        dong.append(d)
    dong.append("")
    dong.append(
        "*Phép tính do công cụ số học của ứng dụng thực hiện, không phải mô "
        "hình ngôn ngữ sinh ra. Công cụ chỉ làm đúng phép tính trong câu hỏi, "
        "không tra cứu tài liệu nào - nếu con số cần lấy từ văn bản thì hãy "
        "hỏi riêng về văn bản đó trước.*"
    )
    return "\n".join(dong)


def dinh_dang_loi(loi: LoiTinh) -> str:
    return (
        f"**Không tính được.** {loi}\n\n"
        "*Công cụ số học của ứng dụng đã đọc câu hỏi này là một phép tính "
        "nhưng không cho ra số. Hãy kiểm tra lại biểu thức.*"
    )


def tra_loi(cau_hoi: str) -> tuple[str, list[dict]] | None:
    """Đường tắt cho chỗ gọi: câu hỏi vào, (câu trả lời, nguồn) ra, None nếu
    không phải câu số học.

    Danh sách nguồn luôn rỗng, và đó là điều đúng: phép tính này không dựa vào
    văn bản nào trong kho, nên gắn một chip nguồn vào là nói dối.
    """
    try:
        kq = nhan_dien(cau_hoi)
    except LoiTinh as loi:
        return dinh_dang_loi(loi), []
    if kq is None:
        return None
    return dinh_dang(kq), []


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    ket_qua = tra_loi(" ".join(argv[1:]))
    if ket_qua is None:
        print("Không nhận ra đây là một phép tính số học.")
        return 1
    print(ket_qua[0])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
