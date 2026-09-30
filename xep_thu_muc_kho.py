"""
XẾP TÀI LIỆU VÀO THƯ MỤC CON THEO LOẠI
======================================
Kho phẳng dễ tìm trên giao diện web nhưng nhìn trong WinSCP thì hơn một nghìn
tệp trộn lẫn: sách bài tập cạnh thông tư, video cạnh giáo án. Module này chọn
thư mục con cho một tệp theo hai tầng:

    <định dạng>/<loại nội dung>[/<loại văn bản>]

    pdf/sach_bai_tap/Vở bài tập Toán 5 - Tập một.pdf
    pdf/van_ban_quy_pham/thong_tu/27-2020-TT-BGDDT.pdf
    word/giao_an/Bai 10 Cau truc tuan tu.docx
    trinh_chieu/VoNhat_NhanVatTrang.pptx
    video/YTDown.com_YouTube_....mp4

Chỉ PDF và Word được chia tiếp theo nội dung. Trình chiếu, video, ảnh, bảng
tính dừng ở tầng định dạng: phần lớn là bài giảng hoặc học liệu, chia thêm
chỉ đẻ ra nhiều thư mục gần rỗng.

Vì sao chọn thư mục LÚC LƯU chứ không xếp lại định kỳ: sổ ghi chép, chỉ mục
FAISS và drive_state.json đều nhớ đường dẫn tệp (xem gop_kho_mot_thu_muc.py).
Tệp vào đúng chỗ ngay từ đầu thì cả ba ghi đúng luôn; chuyển tệp sau khi đã lập
chỉ mục thì phải sửa cả ba (việc của xep_kho_theo_loai.py).

Nguyên tắc giống phan_loai_giao_duc.py: không đoán bừa. Không đủ dấu hiệu thì
vào "chua_phan_loai" để quản trị viên xếp tay, còn hơn nằm sai thư mục.
Không gọi LLM: chỉ đọc lớp chữ 1-2 trang đầu (vài chục ms) rồi chạy regex.
"""

from __future__ import annotations

import logging
import os
import re
import zipfile
from html import unescape

from document_loaders import (
    DINH_DANG_AM_THANH,
    DINH_DANG_ANH,
    DINH_DANG_BANG,
    DINH_DANG_PHU_DE,
    DINH_DANG_TRINH_CHIEU,
)
from hybrid_retrieval import bo_dau
from media_transcribe import DINH_DANG_MEDIA
from phan_loai_giao_duc import (
    LOAI_NOI_DUNG_MAC_DINH,
    NHAN_LOAI_NOI_DUNG,
    PhanLoai,
    suy_phan_loai,
)
from van_ban_meta import (
    MAU_DAU_HIEU_QPPL,
    HoSoVanBan,
    cat_khoi_tieu_de,
    suy_loai_van_ban,
    suy_so_hieu_chinh,
    trich_so_hieu,
)


def dang_bat() -> bool:
    """Đặt RAG_XEP_THU_MUC_THEO_LOAI=0 để quay về lưu tệp như trước."""
    return os.getenv("RAG_XEP_THU_MUC_THEO_LOAI", "1") == "1"


# ============================================================
# TẦNG 1: ĐỊNH DẠNG
# ============================================================
DINH_DANG_PDF = {".pdf"}
DINH_DANG_WORD = {".docx", ".doc"}
# Hai định dạng này mới có trang bìa / khối tiêu đề để chia tiếp theo nội dung.
THU_MUC_CHIA_THEO_NOI_DUNG = {"pdf", "word"}


def thu_muc_dinh_dang(ten: str) -> str:
    duoi = os.path.splitext(ten)[1].lower()
    if duoi in DINH_DANG_PDF:
        return "pdf"
    if duoi in DINH_DANG_WORD:
        return "word"
    if duoi in DINH_DANG_TRINH_CHIEU:
        return "trinh_chieu"
    # Âm thanh xét trước video: DINH_DANG_MEDIA gồm cả hai.
    if duoi in DINH_DANG_AM_THANH:
        return "am_thanh"
    if duoi in DINH_DANG_MEDIA:
        return "video"
    if duoi in DINH_DANG_ANH:
        return "hinh_anh"
    if duoi in DINH_DANG_BANG:
        return "bang_tinh"
    if duoi in DINH_DANG_PHU_DE:
        return "phu_de"
    return "van_ban_khac"  # .txt, .md, .html, .epub


# ============================================================
# TẦNG 2: LOẠI NỘI DUNG (chỉ PDF, Word)
# ============================================================
THU_MUC_CHUA_PHAN_LOAI = "chua_phan_loai"
THU_MUC_VAN_BAN_QUY_PHAM = "van_ban_quy_pham"

# Loại văn bản -> tên thư mục con của van_ban_quy_pham. Khóa là nhãn mà
# van_ban_meta.suy_loai_van_ban trả về, cộng vài loại hành chính hay gặp.
THU_MUC_LOAI_VAN_BAN = {
    "Luật": "luat",
    "Nghị định": "nghi_dinh",
    "Thông tư": "thong_tu",
    "Thông tư liên tịch": "thong_tu_lien_tich",
    "Quyết định": "quyet_dinh",
    "Nghị quyết": "nghi_quyet",
    "Chỉ thị": "chi_thi",
    "Công văn": "cong_van",
    "Hướng dẫn": "huong_dan",
    "Kế hoạch": "ke_hoach",
    "Thông báo": "thong_bao",
}
THU_MUC_VAN_BAN_KHAC = "khac"

# suy_loai_van_ban chỉ biết các mã quy phạm (TT, NĐ, QĐ...). Văn bản hành
# chính của Bộ, Sở cũng có mã loại trong số hiệu: "123/KH-SGDĐT".
_LOAI_THEO_MA_PHU = {"HD": "Hướng dẫn", "KH": "Kế hoạch", "TB": "Thông báo", "CV": "Công văn"}

# Tên loại viết bỏ dấu, chữ thường -> nhãn. Xếp tên dài trước để "thong tu
# lien tich" không bị "thong tu" ăn mất.
_LOAI_THEO_CHU = sorted(
    ((bo_dau(nhan).lower(), nhan) for nhan in THU_MUC_LOAI_VAN_BAN),
    key=lambda cap: -len(cap[0]),
)
# Chỉ những loại này mới đủ để khẳng định "là văn bản quy phạm / hành chính"
# khi chỉ nhìn tên file hay một dòng tiêu đề. "Kế hoạch bài dạy", "Hướng dẫn
# giải bài tập", "Thông báo tuyển sinh" cũng mở đầu bằng tên loại mà lại là
# giáo án, học liệu - ba loại đó chỉ nhận khi có số hiệu hoặc quốc hiệu.
LOAI_CHAC_CHAN = {
    "Luật", "Nghị định", "Thông tư", "Thông tư liên tịch", "Quyết định",
    "Nghị quyết", "Chỉ thị", "Công văn",
}
_MAU_LOAI_DAU_TEN = re.compile(
    r"^(?:" + "|".join(re.escape(chu) for chu, nhan in _LOAI_THEO_CHU
                       if nhan in LOAI_CHAC_CHAN) + r")\b"
)
# "TT 27-2020", "ND24-2023": viết tắt chỉ nhận khi ngay sau là con số, kẻo
# "ct" hay "tt" trong tên bài học bị hiểu thành chỉ thị, thông tư.
_VIET_TAT_DAU_TEN = {"ttlt": "Thông tư liên tịch", "tt": "Thông tư", "nd": "Nghị định",
                     "qd": "Quyết định", "nq": "Nghị quyết", "ct": "Chỉ thị", "cv": "Công văn"}
_MAU_VIET_TAT_DAU_TEN = re.compile(r"^(ttlt|tt|nd|qd|nq|ct|cv) ?\d")
# Số hiệu viết trong tên file bằng gạch ngang: "27-2020-TT-BGDDT.pdf".
_MAU_SO_HIEU_TRONG_TEN = re.compile(r"\b\d{1,4} (?:19|20)\d\d (ttlt|tt|nd|qd|nq|ct)\b")
# Công văn không có dòng tên loại mà có trích yếu "V/v ..." ngay dưới số hiệu.
_MAU_TRICH_YEU_CONG_VAN = re.compile(r"\bV/v\b", re.IGNORECASE)


def _chu_thuong_bo_dau(van_ban: str) -> str:
    chuoi = bo_dau(van_ban).lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", chuoi).strip()


def _loai_theo_so_hieu(so_hieu: str | None) -> str | None:
    loai = suy_loai_van_ban(so_hieu)
    if loai or not so_hieu:
        return loai
    ma = so_hieu.split("/")[-1].split("-")[0].upper()
    return _LOAI_THEO_MA_PHU.get(ma)


DO_DAI_KHOI_TIEU_DE = 1200


def _loai_theo_dong_tieu_de(tieu_de: str) -> str | None:
    """Khối tiêu đề có một dòng riêng in hoa: "THÔNG TƯ", "NGHỊ ĐỊNH", "LUẬT".

    Chỉ nhận khi CẢ DÒNG là tên loại: dòng "Căn cứ Luật Giáo dục..." đã bị cắt
    bỏ ở cat_khoi_tieu_de, nhưng trong tiêu đề vẫn có thể có "Bộ trưởng ban
    hành Thông tư quy định..." và câu đó không nói văn bản này là thông tư.
    """
    # Tiêu đề văn bản nằm ở đầu trang; chỉ xét phần này để một dòng đề mục
    # "HƯỚNG DẪN" giữa giáo án không bị coi là tên loại.
    for dong in tieu_de[:DO_DAI_KHOI_TIEU_DE].splitlines():
        chuan = re.sub(r"[^a-z ]", "", _chu_thuong_bo_dau(dong)).strip()
        for chu, nhan in _LOAI_THEO_CHU:
            if chuan == chu:
                return nhan
    return None


def _loai_theo_ten_file(ten: str) -> str | None:
    goc = _chu_thuong_bo_dau(os.path.splitext(ten)[0])
    khop = _MAU_LOAI_DAU_TEN.match(goc)
    if khop:
        return dict(_LOAI_THEO_CHU)[khop.group(0)]
    khop = _MAU_VIET_TAT_DAU_TEN.match(goc) or _MAU_SO_HIEU_TRONG_TEN.search(goc)
    return _VIET_TAT_DAU_TEN[khop.group(1)] if khop else None


def suy_loai_van_ban_cua_tep(ten: str, phan_dau: str,
                             ho_so: HoSoVanBan | None = None) -> str | None:
    """Thứ tự tin cậy: hồ sơ đã lập từ toàn văn > số hiệu > dòng tiêu đề >
    đầu tên file > trích yếu "V/v". Không thấy gì thì None (thư mục "khac")."""
    if ho_so is not None and ho_so.loai:
        return ho_so.loai
    so_hieu = ho_so.so_hieu if ho_so is not None else suy_so_hieu_chinh(ten, phan_dau)[0]
    tieu_de = cat_khoi_tieu_de(phan_dau)
    if not so_hieu:
        # suy_so_hieu_chinh cố ý không đoán (số hiệu sai đẻ ra cảnh báo hiệu
        # lực sai), và hụt với văn bản của Sở: chữ "S" của "SỞ GIÁO DỤC" bị
        # nhận là dòng "Số:". Ở đây chỉ cần LOẠI văn bản nên lấy số hiệu đầu
        # tiên của khối tiêu đề là đủ - khối này đã cắt bỏ phần "Căn cứ".
        # Chỉ lấy số ĐẦU TIÊN: trích yếu công văn hay nhắc số hiệu văn bản
        # khác ("V/v triển khai Thông tư 27/2020/TT-BGDĐT").
        cac_so_hieu = trich_so_hieu(tieu_de[:DO_DAI_KHOI_TIEU_DE])
        so_hieu = cac_so_hieu[0] if cac_so_hieu else None
    return (
        _loai_theo_so_hieu(so_hieu)
        or _loai_theo_dong_tieu_de(tieu_de)
        or _loai_theo_ten_file(ten)
        or ("Công văn" if _MAU_TRICH_YEU_CONG_VAN.search(tieu_de) else None)
    )


# ============================================================
# ĐỌC PHẦN ĐẦU TÀI LIỆU
# ============================================================
# Khối tiêu đề và trang bìa nằm gọn trong 2 trang đầu; đọc cả cuốn sách 300
# trang chỉ để lấy tên loại thì phí, lại dễ dính chữ "Thông tư" ở giữa sách.
SO_TRANG_DOC = 2
DO_DAI_PHAN_DAU = 3000


def _phan_dau_pdf(duong_dan: str) -> str:
    van_ban = ""
    # PDF hỏng nhẹ (thiếu EOF, header lạ) vẫn đọc được; pypdf kêu từng dòng
    # cảnh báo, xếp cả nghìn tệp thì màn hình chỉ còn cảnh báo.
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        from pypdf import PdfReader

        doc = PdfReader(duong_dan)
        van_ban = "\n".join(
            (trang.extract_text() or "") for trang in doc.pages[:SO_TRANG_DOC]
        )
    except Exception:
        van_ban = ""
    if len(van_ban.strip()) >= 50:
        return van_ban
    # PDF scan không có lớp chữ. Nếu tệp từng được OCR (cache theo hash nội
    # dung nên đổi tên, chuyển chỗ vẫn dùng lại được) thì lấy luôn; chưa thì
    # thôi - OCR mất vài phút mỗi tệp, không làm lúc người dùng đang chờ tải lên.
    try:
        from ocr_pdf import doc_cache

        cac_trang = doc_cache(duong_dan) or []
        return "\n".join(cac_trang[:SO_TRANG_DOC]) or van_ban
    except Exception:
        return van_ban


def _phan_dau_docx(duong_dan: str) -> str:
    """Đọc thẳng word/document.xml: không cần thư viện, không đọc ảnh nhúng."""
    try:
        with zipfile.ZipFile(duong_dan) as goi:
            xml = goi.read("word/document.xml").decode("utf-8", errors="ignore")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""
    # Cắt bớt trước khi xử lý: document.xml của sách dài có thể vài chục MB.
    xml = xml[: DO_DAI_PHAN_DAU * 40]
    xml = re.sub(r"</w:p>|<w:br\s*/>|<w:cr\s*/>", "\n", xml)
    xml = re.sub(r"<w:tab\s*/>", " ", xml)
    return unescape(re.sub(r"<[^>]+>", "", xml))


def doc_phan_dau(duong_dan: str | None, ten: str) -> str:
    if not duong_dan or not os.path.isfile(duong_dan):
        return ""
    duoi = os.path.splitext(ten)[1].lower()
    if duoi == ".pdf":
        van_ban = _phan_dau_pdf(duong_dan)
    elif duoi == ".docx":
        van_ban = _phan_dau_docx(duong_dan)
    else:
        van_ban = ""  # .doc đời cũ: đọc cần Word/LibreOffice, chỉ xét tên file
    return van_ban[:DO_DAI_PHAN_DAU]


# ============================================================
# CHỌN THƯ MỤC
# ============================================================
def chon_thu_muc(
    ten: str,
    duong_dan: str | None = None,
    *,
    phan_loai: PhanLoai | None = None,
    ho_so: HoSoVanBan | None = None,
) -> str:
    """Trả về thư mục con (tương đối, dấu "/") nơi cất tệp `ten`.

    duong_dan: nơi đọc nội dung tệp (tệp tạm lúc tải lên, tệp trong thùng
    rác lúc khôi phục). Bỏ trống thì chỉ xét tên file.
    phan_loai, ho_so: kết quả đã lập từ TOÀN VĂN lúc lập chỉ mục (có cả chữ
    OCR), đáng tin hơn 2 trang đầu - dùng khi xếp lại tệp đã có trong kho.
    """
    goc = thu_muc_dinh_dang(ten)
    if goc not in THU_MUC_CHIA_THEO_NOI_DUNG:
        return goc

    # Đọc tệp chỉ khi thật cần: xếp lại cả kho mà nhãn đã có sẵn thì khỏi mở
    # hàng nghìn tệp PDF.
    _da_doc: list[str] = []

    def phan_dau_tep() -> str:
        if not _da_doc:
            _da_doc.append(doc_phan_dau(duong_dan, ten))
        return _da_doc[0]

    # "hoc_lieu_khac" của bảng chỉ nghĩa là "không thấy dấu hiệu", không phải
    # một khẳng định - vẫn cho quy tắc tên file / tiêu đề thử thêm lần nữa.
    if phan_loai is not None and phan_loai.loai_noi_dung != LOAI_NOI_DUNG_MAC_DINH:
        loai_noi_dung = phan_loai.loai_noi_dung
    else:
        phan_dau = phan_dau_tep()
        # Cùng dấu hiệu mà van_ban_meta dùng để đặt la_qppl cho hồ sơ, cộng
        # thêm tên loại tìm được ở tiêu đề / tên file ("Luat Giao duc 2019.pdf"
        # không có số hiệu trong tên nhưng rõ ràng là văn bản quy phạm).
        # Chỉ xét phần đầu: giáo án cũng có thể nhắc "Căn cứ" ở giữa bài.
        la_qppl = (
            (ho_so.la_qppl if ho_so is not None else False)
            or bool(MAU_DAU_HIEU_QPPL.search(phan_dau[:DO_DAI_KHOI_TIEU_DE]))
            or _loai_theo_ten_file(ten) is not None
            or _loai_theo_dong_tieu_de(cat_khoi_tieu_de(phan_dau)) in LOAI_CHAC_CHAN
        )
        loai_noi_dung = suy_phan_loai(
            ten, phan_dau, la_qppl=la_qppl, loai_tai_lieu="van_ban"
        ).loai_noi_dung

    if loai_noi_dung == "van_ban_quy_pham":
        if ho_so is not None and ho_so.loai:
            loai_van_ban = ho_so.loai
        else:
            loai_van_ban = suy_loai_van_ban_cua_tep(ten, phan_dau_tep(), ho_so)
        con = THU_MUC_LOAI_VAN_BAN.get(loai_van_ban or "", THU_MUC_VAN_BAN_KHAC)
        return f"{goc}/{THU_MUC_VAN_BAN_QUY_PHAM}/{con}"
    if loai_noi_dung == LOAI_NOI_DUNG_MAC_DINH:
        return f"{goc}/{THU_MUC_CHUA_PHAN_LOAI}"
    return f"{goc}/{loai_noi_dung}"


# ============================================================
# NHÃN HIỂN THỊ
# ============================================================
NHAN_THU_MUC_DINH_DANG = {
    "pdf": "PDF",
    "word": "Word",
    "trinh_chieu": "Trình chiếu",
    "am_thanh": "Âm thanh",
    "video": "Video",
    "hinh_anh": "Hình ảnh",
    "bang_tinh": "Bảng tính",
    "phu_de": "Phụ đề",
    "van_ban_khac": "Văn bản khác",
}


def nhan_thu_muc() -> dict:
    """Tên thư mục -> nhãn tiếng Việt, để Kho tài liệu trên web chia nhóm
    "Văn bản 1101" thành Sách giáo khoa, Sách giáo viên, Thông tư...

    "dinh_dang": tầng 1 - giao diện bỏ qua tầng này khi chia nhóm, vì PDF và
    Word cùng là sách giáo khoa thì nên đếm chung.
    "thu_muc": tầng 2 và 3 (loại nội dung, loại văn bản quy phạm).
    """
    nhan = {
        loai: ten.split(" (")[0]  # "Giáo án (kế hoạch bài dạy)" -> "Giáo án"
        for loai, ten in NHAN_LOAI_NOI_DUNG.items()
    }
    nhan[THU_MUC_CHUA_PHAN_LOAI] = "Chưa phân loại"
    nhan[THU_MUC_VAN_BAN_KHAC] = "Loại khác"
    nhan.update({thu_muc: loai for loai, thu_muc in THU_MUC_LOAI_VAN_BAN.items()})
    return {"dinh_dang": dict(NHAN_THU_MUC_DINH_DANG), "thu_muc": nhan}


def thu_muc_he_dieu_hanh(thu_muc_con: str) -> str:
    """"pdf/sach_bai_tap" -> "pdf\\sach_bai_tap" trên Windows."""
    return os.path.join(*thu_muc_con.split("/")) if thu_muc_con else ""
