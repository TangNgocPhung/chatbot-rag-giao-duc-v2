"""
ĐIỀU KHOẢN CHUYỂN TIẾP - KHI VĂN BẢN ĐÃ BỊ THAY VẪN LÀ CĂN CỨ ĐÚNG
=================================================================
quan_he_van_ban coi "B thay thế A" là A hết hiệu lực với MỌI người kể từ ngày
B có hiệu lực, và tầng truy hồi bỏ hẳn A khỏi câu hỏi về quy định hiện hành.
Đúng với đa số trường hợp, nhưng văn bản mới thường kèm một câu kiểu:

    "Các khóa tuyển sinh trước ngày Thông tư này có hiệu lực thi hành tiếp tục
     thực hiện theo Quy chế ban hành kèm theo Quyết định số 43/2007/QĐ-BGDĐT."

Với sinh viên khóa cũ, câu trả lời đúng nằm ở chính văn bản đã bị thay. Bỏ A
khỏi truy hồi lúc đó không chỉ là thiếu sót mà là SAI MỘT CÁCH TỰ TIN: mô hình
trích B, gắn nhãn "Đang hiệu lực", trong khi B không áp dụng cho người hỏi.

Module này làm ba việc, đều bằng đối chiếu chuỗi như cả tầng hiệu lực:
  1. trich_chuyen_tiep(): đọc trong nội dung B các câu chuyển tiếp - áp dụng
     cho ai, mốc nào, tiếp tục theo văn bản nào.
  2. dau_hieu_trong_cau_hoi(): câu hỏi có cho biết người hỏi thuộc khóa nào
     không ("khóa tuyển sinh 2019", "nhập học năm 2020", "khóa cũ").
  3. so_voi_moc(): khóa đó đứng trước hay sau mốc chuyển tiếp.
quan_he_van_ban.SoQuanHe gắn kết quả vào đồ thị, rag_service dùng nó để mở lại A
khi câu hỏi thuộc đúng đối tượng và báo cho mô hình biết điều kiện chuyển tiếp.

Một câu chỉ được nhận là chuyển tiếp khi có ĐỦ:
  - động từ tiếp tục ("tiếp tục thực hiện/áp dụng/giải quyết...") - hoặc
    "thực hiện theo" nhưng phải chỉ ra văn bản cũ;
  - một mốc ("trước ngày ...", "đã trúng tuyển", "từ năm 2020 trở về trước");
  - và điều gì đó ràng nó vào việc chuyển tiếp: nằm trong điều "Quy định
    chuyển tiếp", nêu văn bản/quy định cũ, hoặc lấy mốc là ngày chính văn bản
    này có hiệu lực.
Thiếu một trong ba thì "học sinh đã nhập học tiếp tục học tập tại trường" ở
thân bài cũng thành điều khoản chuyển tiếp.

CHƯA XỬ LÝ (có chủ đích): lộ trình theo lớp ("từ năm học 2021-2022 đối với lớp
6, ...") là dạng điều kiện khác - theo lớp và năm học chứ không theo khóa.
So mốc chỉ theo NĂM: "khóa 2021" với mốc 3/5/2021 thì chưa biết trước hay sau,
nên trả "co_the" để mô hình trả lời có điều kiện thay vì tự quyết.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

import van_ban_meta
from hieu_luc_bo_sung import nen

# ============================================================
# 1. TRÍCH TỪ NỘI DUNG VĂN BẢN
# ============================================================
# Dò ứng viên trên chữ GỐC (regex chạy ở tốc độ C) rồi mới nén từng câu ứng
# viên: nén cả kho mỗi lần khởi động tốn ~0,6 giây/MB chỉ để tìm vài chục câu.
# \s* giữa các chữ cái vì OCR chèn khoảng trắng tùy tiện ("ti ếp t ục"); vài
# biến thể nguyên âm vì OCR hay đọc sai dấu.
_TIEP_TUC = r"t\s*i\s*[eếêềểễệé]\s*p\s*t\s*[uụúùủũư]\s*c"
_THUC_HIEN = r"t\s*h\s*[ựưuứừ]\s*c\s*h\s*i\s*[ệêeếề]\s*n"
_AP_DUNG = r"[áàảãạa]\s*p\s*d\s*[ụuúùủũ]\s*n\s*g"
MAU_UNG_VIEN = re.compile(
    rf"{_TIEP_TUC}|(?:{_THUC_HIEN}|{_AP_DUNG})\s*theo", re.IGNORECASE
)
MAU_UNG_VIEN_DIEU = re.compile(r"chuy\s*[ểeêế]\s*n\s*ti\s*[ếeêể]\s*p", re.IGNORECASE)
# Đầu một Điều mới: "\nĐiều 46." - để biết điều "Quy định chuyển tiếp" kết thúc ở đâu.
MAU_DAU_DIEU = re.compile(r"\n\s*Đi\s*[ềeêế]\s*u\s*\d+\s*[.:]", re.IGNORECASE)

# Các mẫu dưới đây chạy trên câu ĐÃ NÉN (nen(): bỏ dấu, bỏ khoảng trắng, chữ thường).
MAU_TIEU_DE_DIEU = re.compile(r"dieu\d+[.:]?(?:cac)?(?:quydinh|dieukhoan)?chuyentiep$")
MAU_DONG_TU = re.compile(
    r"tieptuc(?:duoc)?(?:thuchien|apdung|giaiquyet|xemxet|sudung|huong|daotao|hoc|tochuc|conhieuluc|cogiatri)"
)
MAU_DONG_TU_THEO = re.compile(r"(?:thuchien|apdung|giaiquyet)theo")
# Động từ không kèm văn bản nào vẫn ngầm nói "theo quy định trước đó":
# "Các khóa đã tuyển sinh trước ngày ... tiếp tục thực hiện cho đến khi kết thúc."
MAU_DONG_TU_NGAM_CU = re.compile(r"tieptuc(?:duoc)?(?:thuchien|apdung|daotao|hoc|giaiquyet|xemxet)")
MAU_MOC = re.compile(
    r"truoc(?:ngay|thoidiem|khi|namhoc)|trovetruoc"
    r"|da(?:duoc)?(?:trungtuyen|nhaphoc|tuyensinh|tuyen|nophoso|tiepnhan|khaigiang)"
    r"|dang(?:hoc|theohoc|daotao|giaiquyet|xemxet)"
)
MAU_QUY_DINH_CU = re.compile(
    r"quydinh(?:cu|truocday|cuatruoc|hienhanhtaithoidiem|taithoidiem)|vanbancu|quychecu"
    r"|chuongtrinhcu|quychetaithoidiem|(?:quydinh|vanban)(?:hienhanh)?truockhi"
)
_LOAI_NAY = r"(?:thongtu|nghidinh|luat|quyetdinh|nghiquyet|vanban|quyche)(?:lientich)?nay"
MAU_MOC_HIEU_LUC = re.compile(
    rf"truoc(?:ngay|thoidiem|khi){_LOAI_NAY}(?:batdau)?(?:co)?hieuluc"
    rf"|truoc(?:ngay|thoidiem|khi)(?:co)?hieuluc(?:thihanh)?cua{_LOAI_NAY}"
)
MAU_NAY_CO_HIEU_LUC = re.compile(rf"{_LOAI_NAY}(?:batdau)?cohieuluc")
MAU_MOC_NGAY = re.compile(r"truocngay(\d{1,2})(?:thang|/|-)(\d{1,2})(?:nam|/|-)(\d{4})")
MAU_MOC_NAM_HOC = re.compile(r"truocnamhoc(\d{4})[-–](\d{4})")
MAU_MOC_NAM_HOC_TRO_VE = re.compile(r"namhoc(\d{4})[-–](\d{4})trovetruoc")
MAU_MOC_NAM_TRO_VE = re.compile(r"nam(\d{4})trovetruoc")
# Ai được chuyển tiếp. "khoahoc" cố tình không có: bỏ dấu thì "khóa học" trùng
# "khoa học" (nhiệm vụ khoa học, hội đồng khoa học...).
MAU_DOI_TUONG_KHOA = re.compile(
    r"khoa(?:tuyensinh|daotao)|tuyensinh|nhaphoc|trungtuyen|nguoihoc|sinhvien|hocvien"
    r"|hocsinh|nghiencuusinh|thisinh"
)
MAU_DOI_TUONG_HO_SO = re.compile(r"hoso|thutuc|denghi|dexuat")

# Câu dài nhất còn coi là một câu; quá thì cắt (OCR mất dấu chấm thì "câu" dài vô tận).
DO_DAI_CAU_TOI_DA = 600
DO_DAI_TRICH = 360
DO_DAI_DIEU_KIEN = 220


@dataclass
class QuyDinhChuyenTiep:
    """Một câu chuyển tiếp của văn bản mới.

    ap_dung_theo: số hiệu văn bản được tiếp tục áp dụng, đọc thẳng từ câu.
    theo_quy_dinh_cu: câu chỉ nói "quy định cũ"/"quy định tại thời điểm tuyển
        sinh", hoặc không nói theo gì - SoQuanHe hiểu là các văn bản mà văn
        bản mới đã thay.
    moc: ngày ISO của mốc; None khi mốc là "ngày văn bản này có hiệu lực"
        (moc_la_ngay_hieu_luc=True, SoQuanHe điền) hoặc không đọc ra mốc.
    doi_tuong: "khoa" (khóa tuyển sinh, người học) | "ho_so" | "khac".
    """

    dieu_kien: str
    trich: str
    ap_dung_theo: list[str] = field(default_factory=list)
    theo_quy_dinh_cu: bool = False
    moc: str | None = None
    moc_la_ngay_hieu_luc: bool = False
    doi_tuong: str = "khac"


def _vung_dieu_chuyen_tiep(van_ban: str) -> list[tuple[int, int]]:
    """Khoảng [đầu, cuối) của các Điều có tiêu đề "Quy định chuyển tiếp"."""
    vung = []
    for khop in MAU_UNG_VIEN_DIEU.finditer(van_ban):
        if not MAU_TIEU_DE_DIEU.search(nen(van_ban[max(0, khop.start() - 60): khop.end()])):
            continue
        het = MAU_DAU_DIEU.search(van_ban, khop.end())
        vung.append((khop.start(), het.start() if het else min(len(van_ban), khop.end() + 5000)))
    return vung


def _cat_cau(van_ban: str, vi_tri: int) -> tuple[int, int]:
    """Câu chứa vị trí này: từ sau dấu . ; : gần nhất phía trước tới dấu . ;
    gần nhất phía sau. Không cắt ở xuống dòng - OCR ngắt dòng giữa câu."""
    dau = max(van_ban.rfind(dau_cau, max(0, vi_tri - DO_DAI_CAU_TOI_DA), vi_tri) for dau_cau in ".;:")
    dau = dau + 1 if dau >= 0 else max(0, vi_tri - DO_DAI_CAU_TOI_DA)
    cac_cuoi = [
        c for c in (van_ban.find(dau_cau, vi_tri, vi_tri + DO_DAI_CAU_TOI_DA) for dau_cau in ".;")
        if c >= 0
    ]
    cuoi = min(cac_cuoi) if cac_cuoi else min(len(van_ban), vi_tri + DO_DAI_CAU_TOI_DA)
    return dau, cuoi


def _gon(chuoi: str) -> str:
    return " ".join((chuoi or "").split())


# Số thứ tự "2. ", "a) ", "- " đầu câu; điều kiện bỏ thêm "Đối với"/"Trường hợp".
MAU_SO_THU_TU = re.compile(r"^(?:\d{1,2}\s*[.)]\s*|[a-zđ]\s*\)\s*|[-–+]\s*)*", re.IGNORECASE)
MAU_DAU_DIEU_KIEN = re.compile(
    r"^(?:\d{1,2}\s*[.)]\s*|[a-zđ]\s*\)\s*|[-–+]\s*)*(?:đối với|trường hợp)?\s*", re.IGNORECASE
)
MAU_DUOI_DIEU_KIEN = re.compile(r"[\s,]*(?:thì|được|vẫn|sẽ)?[\s,]*$", re.IGNORECASE)


def _dieu_kien(cau: str, vi_tri_dong_tu: int) -> str:
    """Phần đứng trước động từ - chính là "ai, từ khi nào" của câu chuyển tiếp.
    Động từ đứng đầu câu ("Tiếp tục thực hiện ... đối với các khóa ...") thì
    lấy cả câu."""
    truoc = MAU_DAU_DIEU_KIEN.sub("", _gon(cau[:vi_tri_dong_tu]), count=1)
    truoc = MAU_DUOI_DIEU_KIEN.sub("", truoc)
    if len(truoc) < 15:
        truoc = MAU_DAU_DIEU_KIEN.sub("", _gon(cau), count=1)
    if len(truoc) > DO_DAI_DIEU_KIEN:
        truoc = truoc[:DO_DAI_DIEU_KIEN].rsplit(" ", 1)[0] + "…"
    return truoc[:1].upper() + truoc[1:] if truoc else truoc


def _moc(cau_nen: str) -> tuple[str | None, bool]:
    """(ngày ISO, mốc là ngày văn bản này có hiệu lực). Năm học tính từ 1/9:
    chỉ dùng để so theo năm nên lệch vài ngày khai giảng không đổi kết quả."""
    if khop := MAU_MOC_NGAY.search(cau_nen):
        ngay, thang, nam = (int(x) for x in khop.groups())
        if 1 <= ngay <= 31 and 1 <= thang <= 12 and 1990 <= nam <= 2100:
            return f"{nam:04d}-{thang:02d}-{ngay:02d}", False
    if MAU_MOC_HIEU_LUC.search(cau_nen):
        return None, True
    if khop := MAU_MOC_NAM_HOC.search(cau_nen):
        return f"{int(khop.group(1)):04d}-09-01", False
    if khop := MAU_MOC_NAM_HOC_TRO_VE.search(cau_nen):
        return f"{int(khop.group(2)):04d}-09-01", False
    if khop := MAU_MOC_NAM_TRO_VE.search(cau_nen):
        return f"{int(khop.group(1)) + 1:04d}-01-01", False
    return None, False


def _phan_tich_cau(cau: str, so_hieu: str | None, trong_dieu_chuyen_tiep: bool) -> QuyDinhChuyenTiep | None:
    cau_nen = nen(cau)
    dong_tu = MAU_DONG_TU.search(cau_nen)
    dong_tu_theo = MAU_DONG_TU_THEO.search(cau_nen)
    if not (dong_tu or dong_tu_theo) or not MAU_MOC.search(cau_nen):
        return None
    so_hieu_cu = [s for s in van_ban_meta.trich_so_hieu(cau) if s != so_hieu]
    noi_quy_dinh_cu = bool(MAU_QUY_DINH_CU.search(cau_nen))
    ngam_cu = bool(MAU_DONG_TU_NGAM_CU.search(cau_nen)) and not so_hieu_cu and not noi_quy_dinh_cu
    if dong_tu:
        rang_buoc = (
            trong_dieu_chuyen_tiep or so_hieu_cu or noi_quy_dinh_cu
            or MAU_NAY_CO_HIEU_LUC.search(cau_nen)
        )
    else:
        # "thực hiện theo" là cụm rất phổ biến: chỉ nhận khi nói rõ theo văn bản cũ.
        rang_buoc = so_hieu_cu or noi_quy_dinh_cu
    if not rang_buoc:
        return None
    moc, moc_la_ngay_hieu_luc = _moc(cau_nen)
    if MAU_DOI_TUONG_KHOA.search(cau_nen):
        doi_tuong = "khoa"
    elif MAU_DOI_TUONG_HO_SO.search(cau_nen):
        doi_tuong = "ho_so"
    else:
        doi_tuong = "khac"
    # Vị trí động từ trên câu gốc: dò lại bằng regex chữ gốc (câu ngắn, rẻ).
    khop_goc = MAU_UNG_VIEN.search(cau)
    trich = _gon(cau)
    if len(trich) > DO_DAI_TRICH:
        trich = trich[:DO_DAI_TRICH].rsplit(" ", 1)[0] + "…"
    return QuyDinhChuyenTiep(
        dieu_kien=_dieu_kien(cau, khop_goc.start() if khop_goc else len(cau)),
        trich=MAU_SO_THU_TU.sub("", trich, count=1),
        ap_dung_theo=list(dict.fromkeys(so_hieu_cu)),
        theo_quy_dinh_cu=noi_quy_dinh_cu or (ngam_cu and bool(dong_tu)),
        moc=moc,
        moc_la_ngay_hieu_luc=moc_la_ngay_hieu_luc,
        doi_tuong=doi_tuong,
    )


def trich_chuyen_tiep(van_ban: str, so_hieu: str | None = None) -> list[dict]:
    """
    Các câu chuyển tiếp trong văn bản (dạng dict để lưu thẳng ra JSON).

    so_hieu: số hiệu của chính văn bản, để không coi "Thông tư số <chính nó>"
    trong câu là văn bản cũ được tiếp tục áp dụng.
    """
    van_ban = van_ban or ""
    vung = _vung_dieu_chuyen_tiep(van_ban)
    ket_qua: list[dict] = []
    da_xet: set[tuple[int, int]] = set()
    da_co: set[str] = set()
    for khop in MAU_UNG_VIEN.finditer(van_ban):
        dau, cuoi = _cat_cau(van_ban, khop.start())
        if (dau, cuoi) in da_xet:
            continue
        da_xet.add((dau, cuoi))
        trong_dieu = any(a <= khop.start() < b for a, b in vung)
        quy_dinh = _phan_tich_cau(van_ban[dau:cuoi], so_hieu, trong_dieu)
        # Chunk gối đầu nhau nên cùng một câu xuất hiện hai lần trong text gộp.
        khoa = nen(quy_dinh.trich) if quy_dinh else ""
        if quy_dinh and khoa not in da_co:
            da_co.add(khoa)
            ket_qua.append(asdict(quy_dinh))
    return ket_qua


# ============================================================
# 2. DẤU HIỆU TRONG CÂU HỎI
# ============================================================
@dataclass(frozen=True)
class DauHieuDoiTuong:
    """Câu hỏi có nói người hỏi thuộc khóa/đợt nào không.

    co: có dấu hiệu (kể cả không rõ năm: "khóa cũ", "khóa 35").
    nam: năm bắt đầu khóa/nhập học/nộp hồ sơ, nếu đọc được.
    """

    co: bool = False
    nam: int | None = None
    cum: str = ""


_NAM = r"((?:19|20)\d{2})"
# Viết không dấu vì so trên câu đã bỏ dấu (van_ban_meta._bo_dau_thuong).
MAU_HOI_KHOA_NAM = re.compile(
    rf"\b(?:khoa|k)\s*(?:hoc\s*|tuyen sinh\s*|dao tao\s*)?(?:nam\s*(?:hoc\s*)?)?{_NAM}\b"
)
_VAO = r"(?:tuyen sinh|nhap hoc|trung tuyen|vao truong|vao hoc|bat dau hoc|xet tuyen|nop ho so)"
MAU_HOI_VAO_NAM = re.compile(
    rf"\b{_VAO}\s*(?:(?:tu|vao|nam hoc|nam|dot)\s+|thang\s+\d{{1,2}}\s*(?:/|nam)?\s*)*{_NAM}\b"
)
MAU_HOI_VAO_TRUOC_NAM = re.compile(rf"\b{_VAO}\s+truoc\s+(?:nam\s+(?:hoc\s+)?)?{_NAM}\b")
MAU_HOI_VAO_TRUOC_NGAY = re.compile(rf"\b{_VAO}\s+truoc\s+ngay\s+[\d/\s-]*?{_NAM}\b")
MAU_HOI_KHOA_KHONG_NAM = re.compile(
    r"\b(?:khoa cu|khoa truoc|cac khoa truoc|khoa tuyen sinh truoc|da nhap hoc|da trung tuyen"
    r"|da tuyen sinh|tuyen sinh truoc|nhap hoc truoc|trung tuyen truoc|ho so da nop|da nop ho so"
    r"|khoa\s+\d{1,3})\b"
)


def dau_hieu_trong_cau_hoi(cau_hoi: str) -> DauHieuDoiTuong:
    """'Sinh viên khóa tuyển sinh 2019...' -> DauHieuDoiTuong(True, 2019)."""
    chuoi = van_ban_meta._bo_dau_thuong(cau_hoi or "")
    if khop := MAU_HOI_VAO_TRUOC_NAM.search(chuoi):
        # Trước năm 2021 = muộn nhất là năm 2020.
        return DauHieuDoiTuong(True, int(khop.group(1)) - 1, khop.group(0))
    if khop := MAU_HOI_VAO_TRUOC_NGAY.search(chuoi):
        return DauHieuDoiTuong(True, int(khop.group(1)), khop.group(0))
    for mau in (MAU_HOI_KHOA_NAM, MAU_HOI_VAO_NAM):
        if khop := mau.search(chuoi):
            return DauHieuDoiTuong(True, int(khop.group(1)), khop.group(0))
    if khop := MAU_HOI_KHOA_KHONG_NAM.search(chuoi):
        return DauHieuDoiTuong(True, None, khop.group(0))
    return DauHieuDoiTuong()


# ============================================================
# 3. SO VỚI MỐC
# ============================================================
def so_voi_moc(moc: str | None, nam: int | None) -> str:
    """
    "khop": khóa bắt đầu trước mốc -> thuộc diện chuyển tiếp.
    "khong": bắt đầu từ mốc trở đi -> áp dụng văn bản mới.
    "co_the": không đủ thông tin (thiếu năm, thiếu mốc, hay cùng năm với mốc
    mà mốc không phải 1/1) - phải trả lời có điều kiện.
    """
    if not moc or nam is None:
        return "co_the"
    nam_moc = int(moc[:4])
    if nam < nam_moc:
        return "khop"
    if nam > nam_moc or moc[5:] == "01-01":
        return "khong"
    return "co_the"


# ============================================================
# 4. GIỮ LẠI VĂN BẢN QUY ĐỊNH CHI TIẾT CỦA VĂN BẢN CŨ
# ============================================================
# Luật mới thay Luật cũ thì văn bản quy định chi tiết Luật cũ thường hết hiệu
# lực theo (quan_he_van_ban.SoQuanHe.het_theo_goc) - TRỪ khi chính Luật mới
# cho giữ lại: "Các văn bản quy định chi tiết thi hành Luật ... tiếp tục có
# hiệu lực/được áp dụng nếu không trái với Luật này". Câu này nằm ở văn bản
# MỚI, nên phải đọc nó thì mới biết không được cảnh báo.
MAU_VAN_BAN_HUONG_DAN = re.compile(r"vanban(?:quydinhchitiet|huongdan)")
MAU_GIU_HIEU_LUC = re.compile(r"tieptuc(?:duoc)?(?:co)?(?:hieuluc|apdung|thuchien)")


def trich_giu_van_ban_huong_dan(van_ban: str) -> str | None:
    """Câu (gọn khoảng trắng) mà văn bản này cho văn bản quy định chi tiết
    của văn bản cũ tiếp tục áp dụng; None nếu không có."""
    van_ban = van_ban or ""
    da_xet: set[tuple[int, int]] = set()
    for khop in MAU_UNG_VIEN.finditer(van_ban):
        dau, cuoi = _cat_cau(van_ban, khop.start())
        if (dau, cuoi) in da_xet:
            continue
        da_xet.add((dau, cuoi))
        cau_nen = nen(van_ban[dau:cuoi])
        if MAU_VAN_BAN_HUONG_DAN.search(cau_nen) and MAU_GIU_HIEU_LUC.search(cau_nen):
            trich = MAU_SO_THU_TU.sub("", _gon(van_ban[dau:cuoi]), count=1)
            return trich[:DO_DAI_TRICH].rsplit(" ", 1)[0] + "…" if len(trich) > DO_DAI_TRICH else trich
    return None
