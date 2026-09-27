"""
Trình đọc tài liệu ngay trong khung chat.

ChatGPT, Gemini chỉ cho đẩy tệp lên rồi hỏi: muốn đọc thì phải mở tệp ở chỗ
khác, gặp đoạn khó lại chép tay sang khung chat. Ở đây người dùng đọc thẳng
PDF (hay ảnh chụp trang sách) bên cạnh cuộc trò chuyện, khoanh vào chỗ chưa
hiểu, và máy chủ trả lại đúng chữ nằm trong vùng khoanh để hỏi tiếp.

Render trang ở máy chủ bằng pypdfium2 (đã có sẵn cho OCR) thay vì nhúng PDF.js
vào giao diện: không thêm thư viện vài MB, và quan trọng hơn là gần 80% PDF
trong kho là bản scan - không có lớp chữ nào để trình duyệt chọn. Với những
trang đó, vùng khoanh được render lại ở 300 DPI rồi OCR bằng Tesseract, giống
hệt cách kho tài liệu được OCR lúc lập chỉ mục.
"""

from __future__ import annotations

import ctypes
import difflib
import io
import json
import os
import re
import subprocess
import tempfile
import threading
import unicodedata
from collections import OrderedDict

DUOI_PDF = {".pdf"}
DUOI_ANH = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
DUOI_DOC_DUOC = DUOI_PDF | DUOI_ANH

RONG_TOI_THIEU = 200
RONG_TOI_DA = 2000
# Làm tròn bề rộng xin render lên bội số này: giao diện đổi cỡ khung vài pixel
# thì vẫn trúng bản đã render, không phải render lại cả tệp.
BUOC_RONG = 200
DPI_OCR = 300
SO_ANH_NHO = 48          # ~100 KB mỗi trang webp -> vài MB bộ nhớ là cùng
KY_TU_TOI_THIEU = 3      # vùng có ít chữ hơn thế coi như không có lớp chữ
KY_TU_TOI_DA = 4000

# pdfium không an toàn đa luồng; FastAPI chạy các route đồng bộ trong nhiều
# luồng cùng lúc nên mọi lần chạm vào pdfium phải đi qua khoá này. OCR thì
# chạy ngoài khoá vì Tesseract là tiến trình riêng.
_khoa_pdfium = threading.Lock()
_anh_da_render: OrderedDict = OrderedDict()
_khoa_anh = threading.Lock()


class LoiDocTaiLieu(ValueError):
    """Lỗi người dùng hiểu được: sai định dạng, trang không tồn tại..."""


def doc_duoc(duong_dan: str) -> bool:
    return os.path.splitext(duong_dan)[1].lower() in DUOI_DOC_DUOC


def _la_pdf(duong_dan: str) -> bool:
    return os.path.splitext(duong_dan)[1].lower() in DUOI_PDF


def _mo_anh(duong_dan: str):
    from PIL import Image, ImageOps

    anh = Image.open(duong_dan)
    # Ảnh chụp điện thoại lưu hướng xoay trong EXIF; không xoay theo thì trang
    # sách nằm ngang và vùng khoanh lệch hẳn chỗ.
    anh = ImageOps.exif_transpose(anh)
    return anh.convert("RGB")


def _kiem_trang(so_trang: int, tong: int) -> None:
    if not 1 <= so_trang <= tong:
        raise LoiDocTaiLieu(f"Tài liệu chỉ có {tong} trang.")


def thong_tin(duong_dan: str) -> dict:
    """Số trang và kích thước từng trang (đã tính hướng xoay) để dựng khung."""
    if not doc_duoc(duong_dan):
        raise LoiDocTaiLieu("Chỉ đọc trực tiếp được tệp PDF và ảnh.")
    if not _la_pdf(duong_dan):
        with _mo_anh(duong_dan) as anh:
            return {"so_trang": 1, "trang": [list(anh.size)]}

    import pypdfium2

    with _khoa_pdfium:
        tai_lieu = pypdfium2.PdfDocument(duong_dan)
        try:
            kich_thuoc = []
            for chi_so in range(len(tai_lieu)):
                trang = tai_lieu[chi_so]
                rong, cao = trang.get_size()
                kich_thuoc.append([round(rong, 2), round(cao, 2)])
                trang.close()
        finally:
            tai_lieu.close()
    return {"so_trang": len(kich_thuoc), "trang": kich_thuoc}


def chuan_hoa_rong(rong: int) -> int:
    rong = max(RONG_TOI_THIEU, min(RONG_TOI_DA, int(rong or 0)))
    return -(-rong // BUOC_RONG) * BUOC_RONG


def _ma_hoa_anh(anh) -> tuple[bytes, str]:
    dem = io.BytesIO()
    try:
        # WebP nhẹ bằng một phần ba PNG mà chữ vẫn sắc; trang 1200px còn ~100 KB.
        anh.save(dem, format="WEBP", quality=86, method=4)
        return dem.getvalue(), "image/webp"
    except (OSError, KeyError, ValueError):
        dem = io.BytesIO()
        anh.save(dem, format="PNG", optimize=True)
        return dem.getvalue(), "image/png"


def render_trang(duong_dan: str, so_trang: int, rong: int) -> tuple[bytes, str]:
    """Ảnh một trang ở bề rộng gần nhất với yêu cầu, có nhớ đệm."""
    if not doc_duoc(duong_dan):
        raise LoiDocTaiLieu("Chỉ đọc trực tiếp được tệp PDF và ảnh.")
    rong = chuan_hoa_rong(rong)
    try:
        moc = os.stat(duong_dan).st_mtime_ns
    except OSError as exc:
        raise LoiDocTaiLieu("Tệp không còn trên máy chủ.") from exc
    khoa = (duong_dan, moc, so_trang, rong)
    with _khoa_anh:
        if khoa in _anh_da_render:
            _anh_da_render.move_to_end(khoa)
            return _anh_da_render[khoa]

    if _la_pdf(duong_dan):
        import pypdfium2

        with _khoa_pdfium:
            tai_lieu = pypdfium2.PdfDocument(duong_dan)
            try:
                _kiem_trang(so_trang, len(tai_lieu))
                trang = tai_lieu[so_trang - 1]
                anh = trang.render(scale=rong / trang.get_width()).to_pil()
                trang.close()
            finally:
                tai_lieu.close()
    else:
        _kiem_trang(so_trang, 1)
        anh = _mo_anh(duong_dan)
        if anh.width > rong:
            anh = anh.resize((rong, max(1, round(anh.height * rong / anh.width))))

    ket_qua = _ma_hoa_anh(anh.convert("RGB"))
    with _khoa_anh:
        _anh_da_render[khoa] = ket_qua
        while len(_anh_da_render) > SO_ANH_NHO:
            _anh_da_render.popitem(last=False)
    return ket_qua


def _lam_gon(van_ban: str) -> str:
    """Nối các dòng bị ngắt giữa câu, giữ lại chỗ xuống đoạn thật."""
    van_ban = (van_ban or "").replace("\r", "\n").replace("\x02", "")
    van_ban = re.sub(r"[ \t ]+", " ", van_ban)
    van_ban = re.sub(r"\n{3,}", "\n\n", van_ban)
    van_ban = "\n".join(dong.strip() for dong in van_ban.split("\n")).strip()
    # Dòng trước chưa hết câu mà dòng sau mở đầu bằng chữ thường là một câu
    # bị ngắt dòng theo khổ giấy ("bổ sung bởi Luật\nsố 123/2025/QH15").
    return re.sub(r"(?<![.;:!?])\n(?=[a-zà-ỹđ(])", " ", van_ban)


def _chu_trong_vung_pdf(trang, vung: tuple[float, float, float, float]) -> str:
    """Lấy chữ từ lớp văn bản của PDF trong vùng (toạ độ 0..1, gốc trên-trái).

    Toạ độ giao diện là toạ độ trên ảnh đã xoay; lớp chữ của PDF lại dùng hệ
    toạ độ gốc của trang (gốc dưới-trái, chưa xoay, có thể lệch gốc). Nhờ
    pdfium tự đổi qua FPDF_DeviceToPage nên trang xoay 90° hay hộp trang lệch
    gốc vẫn ra đúng chỗ.
    """
    import pypdfium2.raw as pdfium_c

    rong, cao = trang.get_size()
    thiet_bi_x, thiet_bi_y = 10000, max(1, round(10000 * cao / rong))

    def doi(x: float, y: float) -> tuple[float, float]:
        px, py = ctypes.c_double(), ctypes.c_double()
        pdfium_c.FPDF_DeviceToPage(
            trang.raw, 0, 0, thiet_bi_x, thiet_bi_y, 0,
            round(x * thiet_bi_x), round(y * thiet_bi_y),
            ctypes.byref(px), ctypes.byref(py),
        )
        return px.value, py.value

    x0, y0, x1, y1 = vung
    diem = [doi(x0, y0), doi(x1, y1)]
    trai, phai = sorted(d[0] for d in diem)
    duoi, tren = sorted(d[1] for d in diem)
    lop_chu = trang.get_textpage()
    try:
        return lop_chu.get_text_bounded(left=trai, bottom=duoi, right=phai, top=tren)
    finally:
        lop_chu.close()


def _ocr_anh(anh) -> str:
    import ocr_pdf

    san_sang, thong_bao = ocr_pdf.san_sang()
    if not san_sang:
        raise LoiDocTaiLieu(thong_bao)
    # Tesseract đọc kém chữ nhỏ; vùng khoanh trên ảnh chụp thường chỉ vài
    # chục pixel chiều cao nên phóng lên trước khi đọc.
    if anh.height < 400:
        he_so = min(4.0, 400 / max(1, anh.height))
        anh = anh.resize((round(anh.width * he_so), round(anh.height * he_so)))
    tep = tempfile.NamedTemporaryFile(prefix="rag-vung-", suffix=".png", delete=False)
    tep.close()
    try:
        anh.save(tep.name)
        return ocr_pdf._ocr_mot_anh(ocr_pdf.tim_tesseract(), tep.name)
    finally:
        try:
            os.remove(tep.name)
        except OSError:
            pass


def chu_trong_vung(duong_dan: str, so_trang: int, vung: tuple[float, float, float, float]) -> dict:
    """Chữ trong vùng khoanh: ưu tiên lớp chữ của PDF, không có thì OCR."""
    if not doc_duoc(duong_dan):
        raise LoiDocTaiLieu("Chỉ đọc trực tiếp được tệp PDF và ảnh.")
    x0, y0, x1, y1 = (max(0.0, min(1.0, float(v))) for v in vung)
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    if x1 - x0 < 0.005 or y1 - y0 < 0.003:
        raise LoiDocTaiLieu("Vùng khoanh quá nhỏ.")

    if _la_pdf(duong_dan):
        import pypdfium2

        with _khoa_pdfium:
            tai_lieu = pypdfium2.PdfDocument(duong_dan)
            try:
                _kiem_trang(so_trang, len(tai_lieu))
                trang = tai_lieu[so_trang - 1]
                van_ban = _lam_gon(_chu_trong_vung_pdf(trang, (x0, y0, x1, y1)))
                anh = None
                if len(van_ban) < KY_TU_TOI_THIEU:
                    rong, cao = trang.get_size()
                    # crop tính bằng điểm PDF cắt từ bốn mép, áp dụng SAU khi
                    # xoay - tức là đúng hệ toạ độ của ảnh người dùng nhìn thấy.
                    anh = trang.render(
                        scale=DPI_OCR / 72,
                        crop=(x0 * rong, (1 - y1) * cao, (1 - x1) * rong, y0 * cao),
                    ).to_pil()
                trang.close()
            finally:
                tai_lieu.close()
        if anh is None:
            return {"van_ban": van_ban[:KY_TU_TOI_DA], "cach": "lop_chu"}
    else:
        _kiem_trang(so_trang, 1)
        anh_goc = _mo_anh(duong_dan)
        rong, cao = anh_goc.size
        anh = anh_goc.crop((
            round(x0 * rong), round(y0 * cao), round(x1 * rong), round(y1 * cao),
        ))

    van_ban = _lam_gon(_ocr_anh(anh))
    return {"van_ban": van_ban[:KY_TU_TOI_DA], "cach": "ocr" if van_ban else "trong"}


# ------------------------------------------------------------
# TẢI VỀ BẢN ĐÃ ĐÁNH DẤU
# ------------------------------------------------------------
# Nét vẽ của sổ tay ({c, m, d, h, p} - xem veNet trong static/so-tay.js) được
# vẽ thành đường véc-tơ ngay trên trang PDF gốc: chữ của tài liệu vẫn chọn và
# tìm được, phóng to không vỡ, tệp chỉ nặng hơn bản gốc vài KB. Ảnh chụp thì
# chuyển thành PDF một trang rồi vẽ y như vậy.
MAU_KHOANH = (214, 69, 52)
MAU_TO_SANG = (255, 212, 59)
_MAU_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _mau(hex_: str | None, mac_dinh: tuple[int, int, int]) -> str:
    r, g, b = (
        (int(hex_[1:3], 16), int(hex_[3:5], 16), int(hex_[5:7], 16))
        if hex_ and _MAU_HEX.match(hex_) else mac_dinh
    )
    return f"{r / 255:.3f} {g / 255:.3f} {b / 255:.3f}"


def _phep_doi(trang) -> tuple:
    """(hàm đổi toạ độ 0..1 trên trang đang nhìn -> điểm PDF, bề rộng trang đang nhìn).

    Giao diện vẽ trên ảnh đã xoay theo /Rotate và cắt theo CropBox (giống
    pdfium render); nội dung PDF thì nằm trong hệ toạ độ gốc chưa xoay.
    """
    hop = trang.cropbox
    x0, x1 = sorted((float(hop.left), float(hop.right)))
    y0, y1 = sorted((float(hop.bottom), float(hop.top)))
    rong, cao = x1 - x0, y1 - y0
    xoay = (trang.get("/Rotate", 0) or 0) % 360
    doi = {
        0: lambda u, v: (x0 + u * rong, y1 - v * cao),
        90: lambda u, v: (x0 + v * rong, y0 + u * cao),
        180: lambda u, v: (x1 - u * rong, y0 + v * cao),
        270: lambda u, v: (x1 - v * rong, y1 - u * cao),
    }[xoay if xoay in (0, 90, 180, 270) else 0]
    return doi, (rong if xoay in (0, 180) else cao)


def _duong_net(p: list[float], doi) -> list[str]:
    """Đường đi qua các điểm, làm mượt y như veNet: cong bậc hai qua trung điểm."""
    diem = [(p[i], p[i + 1]) for i in range(0, len(p) - 1, 2)]
    ra = lambda u, v: "{:.2f} {:.2f}".format(*doi(u, v))  # noqa: E731
    lenh = [f"{ra(*diem[0])} m"]
    if len(diem) == 1:
        # Chấm một điểm: nét dài bằng 0 với đầu tròn vẽ ra một chấm tròn.
        lenh.append(f"{ra(*diem[0])} l")
        return lenh
    hien_tai = diem[0]
    for i in range(1, len(diem) - 1):
        dk, sau = diem[i], diem[i + 1]
        giua = ((dk[0] + sau[0]) / 2, (dk[1] + sau[1]) / 2)
        # Bậc hai -> bậc ba: hai điểm điều khiển nằm 2/3 đường về phía điểm điều khiển cũ.
        c1 = (hien_tai[0] + 2 / 3 * (dk[0] - hien_tai[0]), hien_tai[1] + 2 / 3 * (dk[1] - hien_tai[1]))
        c2 = (giua[0] + 2 / 3 * (dk[0] - giua[0]), giua[1] + 2 / 3 * (dk[1] - giua[1]))
        lenh.append(f"{ra(*c1)} {ra(*c2)} {ra(*giua)} c")
        hien_tai = giua
    lenh.append(f"{ra(*diem[-1])} l")
    return lenh


def _lenh_ve_trang(cac_net: list[dict], doi, rong_nhin: float) -> str:
    lenh = []
    for net in cac_net:
        p = [min(1.0, max(0.0, float(x))) for x in (net.get("p") or [])]
        if len(p) < 2:
            continue
        loai = net.get("c")
        lenh.append("q 1 J 1 j")
        if loai == "khoanh":
            lenh.append(f"{_mau(None, MAU_KHOANH)} RG {_mau(None, MAU_KHOANH)} rg /RagNen gs")
            lenh.append(f"{rong_nhin * 0.003:.2f} w [{rong_nhin * 0.012:.2f} {rong_nhin * 0.008:.2f}] 0 d")
            if net.get("h") == "cn" and len(p) >= 4:
                u0, u1 = sorted((p[0], p[2]))
                v0, v1 = sorted((p[1], p[3]))
                goc = [doi(u0, v0), doi(u1, v0), doi(u1, v1), doi(u0, v1)]
                lenh.append("{:.2f} {:.2f} m".format(*goc[0]))
                lenh += ["{:.2f} {:.2f} l".format(*g) for g in goc[1:]]
            else:
                lenh += _duong_net(p, doi)
            lenh.append("h B Q")  # tô nền mờ rồi viền nét đứt
            continue
        to_sang = loai == "to-sang"
        do_day = max(0.5, float(net.get("d") or 0.0035) * rong_nhin)
        mau = _mau(net.get("m"), MAU_TO_SANG if to_sang else (31, 42, 68))
        lenh.append(f"{mau} RG {do_day:.2f} w" + (" /RagToSang gs" if to_sang else ""))
        lenh += _duong_net(p, doi)
        lenh.append("S Q")
    return "\n".join(lenh)


def xuat_pdf_danh_dau(duong_dan: str, net_theo_trang: dict[int, list[dict]]) -> bytes:
    """PDF của tài liệu với các nét đánh dấu vẽ đè lên từng trang."""
    if not doc_duoc(duong_dan):
        raise LoiDocTaiLieu("Chỉ tải được bản đánh dấu của tệp PDF và ảnh.")
    from pypdf import PdfReader, PdfWriter
    from pypdf.errors import PdfReadError
    from pypdf.generic import DecodedStreamObject, DictionaryObject, FloatObject, NameObject

    if _la_pdf(duong_dan):
        nguon = duong_dan
    else:
        nguon = io.BytesIO()
        _mo_anh(duong_dan).save(nguon, format="PDF", resolution=72)
        nguon.seek(0)
    try:
        doc = PdfReader(nguon)
        if doc.is_encrypted and not doc.decrypt(""):
            raise LoiDocTaiLieu("Tài liệu có mật khẩu nên không ghép đánh dấu vào được.")
        ghi = PdfWriter(clone_from=doc)
    except PdfReadError as exc:
        raise LoiDocTaiLieu(f"Không đọc được tệp PDF: {exc}") from exc

    tong = len(ghi.pages)
    for so_trang, cac_net in net_theo_trang.items():
        if not cac_net:
            continue
        _kiem_trang(so_trang, tong)
        trang = ghi.pages[so_trang - 1]
        doi, rong_nhin = _phep_doi(trang)
        noi_dung = _lenh_ve_trang(cac_net, doi, rong_nhin)
        if not noi_dung:
            continue
        # Độ trong của bút tô sáng / nền vùng khoanh khai báo trong tài nguyên
        # của trang (pypdf đã chép tài nguyên thừa kế từ cây trang xuống từng trang).
        tai_nguyen = trang.get("/Resources")
        tai_nguyen = tai_nguyen.get_object() if tai_nguyen is not None else DictionaryObject()
        trang[NameObject("/Resources")] = tai_nguyen
        trang_thai = tai_nguyen.get("/ExtGState")
        trang_thai = trang_thai.get_object() if trang_thai is not None else DictionaryObject()
        tai_nguyen[NameObject("/ExtGState")] = trang_thai
        for ten, khoa, gia_tri in (("/RagToSang", "/CA", 0.38), ("/RagNen", "/ca", 0.08)):
            trang_thai[NameObject(ten)] = DictionaryObject({
                NameObject("/Type"): NameObject("/ExtGState"),
                NameObject(khoa): FloatObject(gia_tri),
            })
        # Bọc nội dung cũ trong q/Q: trạng thái đồ hoạ trang để lại (phép biến
        # đổi, màu...) không được làm lệch nét vẽ nối phía sau.
        cu = trang.get_contents()
        dong = DecodedStreamObject()
        dong.set_data(b"q\n" + (cu.get_data() if cu is not None else b"") + b"\nQ\n" + noi_dung.encode("ascii"))
        trang.replace_contents(dong)
    ra = io.BytesIO()
    ghi.write(ra)
    return ra.getvalue()


# ------------------------------------------------------------
# ĐỊNH VỊ ĐOẠN TRÍCH TRÊN TRANG
# ------------------------------------------------------------
# Số trang thôi chưa đủ: một trang văn bản hành chính có vài chục dòng, người
# đọc vẫn phải dò xem câu được trích nằm đâu. Ở đây dò lại chính đoạn văn bản
# đã đưa cho mô hình trên trang gốc và trả về các hình chữ nhật (toạ độ 0..1,
# gốc trên-trái, đúng hệ toạ độ của ảnh trang) để giao diện tô sáng.
#
# Nhiều chunk được lập chỉ mục trước khi có metadata "so_trang", nên trang
# cũng được dò lại bằng chữ: lớp chữ PDF, hoặc bản OCR đã lưu cache cho PDF scan.
# Hộp của từng chữ trên trang scan thì phải OCR lại riêng trang đó (Tesseract
# xuất TSV có toạ độ) - chỉ làm khi cần và lưu cache ra đĩa.
_TU = re.compile(r"\w+", re.UNICODE)
KHOP_TOI_THIEU = 3          # ít hơn chừng này chữ khớp thì coi là không thấy
SO_TAI_LIEU_NHO = 8
SO_TRANG_NHO = 48
_khoa_nho = threading.Lock()
_chu_theo_trang: OrderedDict = OrderedDict()   # (đường dẫn, mốc) -> [văn bản từng trang]
_tu_theo_trang: OrderedDict = OrderedDict()    # (đường dẫn, mốc, trang) -> [chữ có hộp]
_hash_tep: dict = {}
# Mỗi lần OCR một trang 300 DPI tốn vài giây CPU; bốn nguồn cùng lúc thì chạy
# lần lượt từng đôi một thay vì dồn cả bốn tiến trình Tesseract lên máy.
_luot_ocr = threading.Semaphore(2)


def _chuan_tu(van_ban: str) -> list[str]:
    return _TU.findall(unicodedata.normalize("NFC", van_ban or "").lower())


def _nho(bo_nho: OrderedDict, khoa, gia_tri, toi_da: int):
    with _khoa_nho:
        bo_nho[khoa] = gia_tri
        bo_nho.move_to_end(khoa)
        while len(bo_nho) > toi_da:
            bo_nho.popitem(last=False)
    return gia_tri


def _lay_nho(bo_nho: OrderedDict, khoa):
    with _khoa_nho:
        if khoa in bo_nho:
            bo_nho.move_to_end(khoa)
            return bo_nho[khoa]
    return None


def _moc(duong_dan: str) -> tuple[int, int]:
    try:
        tt = os.stat(duong_dan)
    except OSError as exc:
        raise LoiDocTaiLieu("Tệp không còn trên máy chủ.") from exc
    return tt.st_mtime_ns, tt.st_size


def _hash_cua(duong_dan: str) -> str:
    """Hash nội dung tệp (khoá cache OCR); băm tệp vài chục MB mỗi lần hỏi thì chậm."""
    khoa = (duong_dan, _moc(duong_dan))
    if khoa not in _hash_tep:
        from chunking_utils import tinh_hash_file

        _hash_tep[khoa] = tinh_hash_file(duong_dan)[:16]
    return _hash_tep[khoa]


def _van_ban_cac_trang(duong_dan: str) -> list[str]:
    """Chữ của từng trang để dò xem đoạn trích nằm trang nào."""
    khoa = (duong_dan, _moc(duong_dan))
    da_co = _lay_nho(_chu_theo_trang, khoa)
    if da_co is not None:
        return da_co
    import ocr_pdf

    if not _la_pdf(duong_dan):
        cache = ocr_pdf.doc_cache(duong_dan)
        return _nho(_chu_theo_trang, khoa, [cache[0] if cache else ""], SO_TAI_LIEU_NHO)

    import pypdfium2

    cac_trang = []
    with _khoa_pdfium:
        tai_lieu = pypdfium2.PdfDocument(duong_dan)
        try:
            for chi_so in range(len(tai_lieu)):
                trang = tai_lieu[chi_so]
                lop_chu = trang.get_textpage()
                cac_trang.append(lop_chu.get_text_range())
                lop_chu.close()
                trang.close()
        finally:
            tai_lieu.close()
    # PDF scan: lớp chữ gần như trống (hoặc mất dấu), chữ thật nằm trong bản
    # OCR lúc lập chỉ mục.
    if (
        sum(len(t.strip()) for t in cac_trang) < ocr_pdf.KY_TU_TOI_THIEU_MOI_TRANG * max(1, len(cac_trang))
        or ocr_pdf.lop_chu_mat_dau(" ".join(cac_trang))
    ):
        cache = ocr_pdf.doc_cache(duong_dan)
        if not cache or len(cache) != len(cac_trang):
            # Chưa OCR thì đừng nhớ: tệp được OCR sau đó (lượt cập nhật ban
            # đêm, cache chép từ máy khác) phải dò được ngay, không đợi khởi động lại.
            return cac_trang
        cac_trang = cache
    return _nho(_chu_theo_trang, khoa, cac_trang, SO_TAI_LIEU_NHO)


def _tu_lop_chu_pdf(trang) -> list[tuple]:
    """Chữ kèm hộp (0..1 trên trang đang nhìn) từ lớp văn bản của PDF."""
    import pypdfium2.raw as pdfium_c

    rong, cao = trang.get_size()
    thiet_bi_x, thiet_bi_y = 10000, max(1, round(10000 * cao / rong))

    def doi(x: float, y: float) -> tuple[float, float]:
        dx, dy = ctypes.c_int(), ctypes.c_int()
        pdfium_c.FPDF_PageToDevice(
            trang.raw, 0, 0, thiet_bi_x, thiet_bi_y, 0, x, y,
            ctypes.byref(dx), ctypes.byref(dy),
        )
        return dx.value / thiet_bi_x, dy.value / thiet_bi_y

    lop_chu = trang.get_textpage()
    cac_tu, chu, hop, dong = [], [], None, None

    def chot():
        nonlocal chu, hop
        if chu and hop:
            cac_tu.extend((tu, *hop) for tu in _chuan_tu("".join(chu))[:1])
        chu, hop = [], None

    try:
        for i in range(lop_chu.count_chars()):
            ma = pdfium_c.FPDFText_GetUnicode(lop_chu.raw, i)
            ky_tu = chr(ma) if 0 < ma < 0x110000 else " "
            if not (ky_tu.isalnum() or unicodedata.category(ky_tu).startswith("M")):
                chot()
                continue
            trai, duoi, phai, tren = lop_chu.get_charbox(i)
            # Hai ký tự liền nhau không có dấu cách mà khác dòng: tách từ. So
            # trong hệ toạ độ gốc của trang - trên trang xoay 90° thì theo ảnh
            # đang nhìn, mỗi ký tự của cùng một dòng lại nằm cao thấp khác nhau.
            if hop and dong and (duoi > dong[1] or tren < dong[0]):
                chot()
            dong = (duoi, tren)
            (x0, y0), (x1, y1) = doi(trai, tren), doi(phai, duoi)
            x0, x1 = sorted((x0, x1))
            y0, y1 = sorted((y0, y1))
            chu.append(ky_tu)
            hop = (x0, y0, x1, y1) if hop is None else (
                min(hop[0], x0), min(hop[1], y0), max(hop[2], x1), max(hop[3], y1))
        chot()
    finally:
        lop_chu.close()
    return cac_tu


def _tu_ocr(anh) -> list[tuple]:
    """OCR ra từng chữ kèm hộp (Tesseract TSV), toạ độ 0..1 theo ảnh."""
    import ocr_pdf

    tesseract = ocr_pdf.tim_tesseract()
    if tesseract is None or not ocr_pdf.san_sang()[0]:
        return []
    rong, cao = anh.size
    tep = tempfile.NamedTemporaryFile(prefix="rag-dinh-vi-", suffix=".png", delete=False)
    tep.close()
    try:
        anh.save(tep.name)
        with _luot_ocr:
            ket_qua = subprocess.run(
                [
                    tesseract, tep.name, "stdout",
                    "--tessdata-dir", ocr_pdf.THU_MUC_TESSDATA,
                    "-l", ocr_pdf.NGON_NGU, "--psm", "3", "--oem", "1",
                    # Không dùng tên cấu hình "tsv": thư mục tessdata riêng của
                    # dự án không có configs/, Tesseract lặng lẽ xuất chữ trơn.
                    "-c", "tessedit_create_tsv=1",
                ],
                capture_output=True, timeout=300,
            )
    finally:
        try:
            os.remove(tep.name)
        except OSError:
            pass
    if ket_qua.returncode != 0:
        return []
    cac_tu = []
    for dong in ket_qua.stdout.decode("utf-8", errors="replace").splitlines()[1:]:
        cot = dong.split("\t")
        if len(cot) < 12 or cot[0] != "5" or not cot[11].strip():
            continue
        trai, tren, w, h = (int(c) for c in cot[6:10])
        for tu in _chuan_tu(cot[11])[:1]:
            cac_tu.append((tu, trai / rong, tren / cao, (trai + w) / rong, (tren + h) / cao))
    return cac_tu


def _tep_nho_ocr(duong_dan: str, so_trang: int) -> str:
    import ocr_pdf

    os.makedirs(ocr_pdf.THU_MUC_CACHE, exist_ok=True)
    return os.path.join(
        ocr_pdf.THU_MUC_CACHE,
        f"{_hash_cua(duong_dan)}--{ocr_pdf.NGON_NGU}--hop-{so_trang}.json",
    )


def _tu_cua_trang(duong_dan: str, so_trang: int, cho_phep_ocr: bool = True) -> list[tuple] | None:
    """Các chữ trên trang theo thứ tự đọc: [(chữ, x0, y0, x1, y1)].

    None nghĩa là trang scan chưa có hộp chữ trong cache mà lúc này không được
    OCR (máy đang sinh câu trả lời) - hỏi lại sau.
    """
    khoa = (duong_dan, _moc(duong_dan), so_trang)
    da_co = _lay_nho(_tu_theo_trang, khoa)
    if da_co is not None:
        return da_co

    import ocr_pdf

    cac_tu, anh, tep_nho, hoan = [], None, None, False
    if _la_pdf(duong_dan):
        import pypdfium2

        with _khoa_pdfium:
            tai_lieu = pypdfium2.PdfDocument(duong_dan)
            try:
                _kiem_trang(so_trang, len(tai_lieu))
                trang = tai_lieu[so_trang - 1]
                cac_tu = _tu_lop_chu_pdf(trang)
                # Trang scan: lớp chữ trống, vài chữ rác của máy scan, hoặc
                # chữ tiếng Việt mất dấu không khớp được với bản OCR đã lập chỉ mục.
                if len(cac_tu) < 10 or ocr_pdf.lop_chu_mat_dau(" ".join(t[0] for t in cac_tu)):
                    cac_tu = []
                    tep_nho = _tep_nho_ocr(duong_dan, so_trang)
                    if os.path.exists(tep_nho):
                        pass
                    elif cho_phep_ocr:
                        anh = trang.render(scale=ocr_pdf.DPI / 72).to_pil()
                    else:
                        hoan = True
                trang.close()
            finally:
                tai_lieu.close()
    else:
        _kiem_trang(so_trang, 1)
        tep_nho = _tep_nho_ocr(duong_dan, so_trang)
        if os.path.exists(tep_nho):
            pass
        elif cho_phep_ocr:
            anh = _mo_anh(duong_dan)
        else:
            hoan = True

    if hoan:
        return None
    if anh is not None:
        cac_tu = _tu_ocr(anh)
        if cac_tu:
            try:
                with open(tep_nho, "w", encoding="utf-8") as f:
                    json.dump([[t, *(round(v, 5) for v in h)] for t, *h in cac_tu], f, ensure_ascii=False)
            except OSError:
                pass
    elif tep_nho is not None:
        try:
            with open(tep_nho, encoding="utf-8") as f:
                cac_tu = [tuple(tu) for tu in json.load(f)]
        except (OSError, ValueError):
            cac_tu = []
    return _nho(_tu_theo_trang, khoa, cac_tu, SO_TRANG_NHO)


def _cum_khop(tu_trang: list[str], tu_doan: list[str]) -> tuple[int, int, int] | None:
    """(đầu, cuối, số chữ khớp) của cụm chữ trên trang giống đoạn trích nhất.

    Chữ OCR lệch vài ký tự, lớp chữ PDF tách/ghép từ khác bộ đọc lúc lập chỉ
    mục, nên không tìm nguyên chuỗi mà gióng hai dãy chữ (difflib) rồi lấy cụm
    các khối khớp nằm sát nhau - khối khớp lẻ loi ở chỗ khác thì bỏ.
    """
    if not tu_trang or not tu_doan:
        return None
    khop = difflib.SequenceMatcher(None, tu_trang, tu_doan, autojunk=False)
    toi_thieu = 1 if len(tu_doan) <= 4 else 2
    khoi = [k for k in khop.get_matching_blocks() if k.size >= toi_thieu]
    if not khoi:
        return None
    cac_cum, cum = [], [khoi[0]]
    for truoc, sau in zip(khoi, khoi[1:]):
        # Khoảng hở trên trang lớn hơn hẳn khoảng hở trong đoạn trích: đã sang chỗ khác.
        if (sau.a - truoc.a - truoc.size) > (sau.b - truoc.b - truoc.size) + 12:
            cac_cum.append(cum)
            cum = []
        cum.append(sau)
    cac_cum.append(cum)
    tot = max(cac_cum, key=lambda c: sum(k.size for k in c))
    so_khop = sum(k.size for k in tot)
    if so_khop < min(KHOP_TOI_THIEU, len(tu_doan)):
        return None
    return tot[0].a, tot[-1].a + tot[-1].size, so_khop


def _hop_theo_dong(cac_tu: list[tuple]) -> list[list[float]]:
    """Gộp hộp các chữ liền nhau thành một hình chữ nhật cho mỗi dòng."""
    # Trang xoay 90°: dòng chữ chạy dọc trên ảnh. Nhận ra nhờ hình dạng chữ
    # (cao hơn rộng) rồi đổi trục, gộp như dòng ngang, xong đổi lại.
    dai = [(x1 - x0) < (y1 - y0) for t, x0, y0, x1, y1 in cac_tu if len(t) >= 3]
    doc = bool(dai) and sum(dai) * 2 > len(dai)
    cac_hop: list[list[float]] = []
    for _, x0, y0, x1, y1 in cac_tu:
        if doc:
            x0, y0, x1, y1 = y0, x0, y1, x1
        if cac_hop:
            hop = cac_hop[-1]
            # Cùng dòng và sát nhau: chữ ở cột bên kia của bảng hai cột, dù
            # cùng độ cao, vẫn là một hình chữ nhật riêng.
            if hop[1] <= (y0 + y1) / 2 <= hop[3] and x0 <= hop[2] + 0.08 and x1 >= hop[0] - 0.08:
                hop[0], hop[1] = min(hop[0], x0), min(hop[1], y0)
                hop[2], hop[3] = max(hop[2], x1), max(hop[3], y1)
                continue
        cac_hop.append([x0, y0, x1, y1])
    if doc:
        cac_hop = [[b, a, d, c] for a, b, c, d in cac_hop]
    le = 0.004
    return [
        [round(max(0.0, a - le), 4), round(max(0.0, b - le), 4),
         round(min(1.0, c + le), 4), round(min(1.0, d + le), 4)]
        for a, b, c, d in cac_hop
    ]


def _shingle(tu: list[str], n: int = 3) -> set:
    return {tuple(tu[i:i + n]) for i in range(max(1, len(tu) - n + 1))} if tu else set()


def dinh_vi_doan(
    duong_dan: str, doan: str, trong_tam: str = "", trang_goi_y: int | None = None,
    cho_phep_ocr: bool = True,
) -> dict:
    """Trang chứa đoạn trích và các hình chữ nhật cần tô sáng trên đó.

    Trả về {"trang": n | None, "danh_dau": {n: {"vung": [...], "chinh": [...]}}}.
    "vung" phủ cả đoạn đã đưa cho mô hình, "chinh" là câu trọng tâm trong đó
    (câu sát câu hỏi nhất) để mắt người đọc rơi đúng chỗ.

    cho_phep_ocr=False: trang scan chưa có hộp chữ thì không OCR ngay mà trả
    thêm "cho_ocr": True để giao diện hỏi lại sau. Trên VPS, OCR chạy cùng lúc
    với mô hình đang sinh câu trả lời làm câu trả lời chậm đi hàng chục lần.
    """
    if not doc_duoc(duong_dan):
        raise LoiDocTaiLieu("Chỉ định vị được trong tệp PDF và ảnh.")
    tu_doan, tu_tam = _chuan_tu(doan), _chuan_tu(trong_tam)
    cac_trang = _van_ban_cac_trang(duong_dan)
    trang_goi_y = trang_goi_y if trang_goi_y and 1 <= trang_goi_y <= len(cac_trang) else None
    if not tu_doan:
        return {"trang": trang_goi_y, "danh_dau": {}}

    mau_doan, mau_tam = _shingle(tu_doan), _shingle(tu_tam)
    diem = []
    for so, van_ban in enumerate(cac_trang, 1):
        mau_trang = _shingle(_chuan_tu(van_ban))
        diem.append((len(mau_doan & mau_trang), len(mau_tam & mau_trang), so))
    if not diem or max(d[0] for d in diem) == 0:
        # Không có chữ để dò (PDF scan chưa OCR...): giữ trang theo metadata.
        return {"trang": trang_goi_y, "danh_dau": {}}

    # Trang chính: trang có câu trọng tâm, không thì trang khớp nhiều nhất;
    # metadata trang chỉ phân xử khi hai trang ngang điểm.
    co_tam = max(d[1] for d in diem) > 0
    so_chinh = max(diem, key=lambda d: (d[1] if co_tam else 0, d[0], d[2] == trang_goi_y))[2]
    # Đoạn trích vắt sang trang kề bên thì tô cả phần nằm ở trang đó.
    cac_so = [so_chinh] + [
        d[2] for d in diem
        if abs(d[2] - so_chinh) == 1 and d[0] >= max(2, 0.2 * len(mau_doan))
    ]

    danh_dau, cho_ocr = {}, False
    for so in cac_so:
        cac_tu = _tu_cua_trang(duong_dan, so, cho_phep_ocr)
        if cac_tu is None:
            cho_ocr = True
            continue
        tu_trang = [t[0] for t in cac_tu]
        cum = _cum_khop(tu_trang, tu_doan)
        if not cum:
            continue
        dau, cuoi, _ = cum
        muc = {"vung": _hop_theo_dong(cac_tu[dau:cuoi]), "chinh": []}
        if tu_tam:
            cum_tam = _cum_khop(tu_trang[dau:cuoi], tu_tam)
            if cum_tam and cum_tam[2] >= min(len(tu_tam), max(KHOP_TOI_THIEU, len(tu_tam) // 3)):
                muc["chinh"] = _hop_theo_dong(cac_tu[dau + cum_tam[0]:dau + cum_tam[1]])
        danh_dau[so] = muc
    ket_qua = {"trang": so_chinh, "danh_dau": danh_dau}
    if cho_ocr:
        ket_qua["cho_ocr"] = True
    return ket_qua
