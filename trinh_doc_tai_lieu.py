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
import io
import os
import re
import tempfile
import threading
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
