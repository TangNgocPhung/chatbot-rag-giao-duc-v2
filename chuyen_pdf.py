"""
Chuyển Word / Excel / PowerPoint / HTML sang PDF để trình đọc trong sổ tay mở được.

Trình đọc (trinh_doc_tai_lieu.py) chỉ vẽ trang PDF và ảnh. Thay vì viết thêm
một bộ hiển thị cho mỗi định dạng, các tệp này được LibreOffice chuyển một
lần sang PDF rồi đi tiếp đúng con đường của PDF: xem trang, khoanh để hỏi, vẽ
đánh dấu, tải bản đã đánh dấu - tất cả dùng chung.

Bản PDF được nhớ trên đĩa theo (đường dẫn, cỡ, giờ sửa) của tệp gốc: mở lại,
lật trang, khoanh vùng không phải chuyển lại (LibreOffice mất vài giây mỗi lần).

An toàn: tệp do người dùng tải lên có thể trỏ tới ảnh trên mạng hay trên chính
máy chủ (<img src="http://127.0.0.1:...">, ảnh liên kết trong .docx). Để
LibreOffice không đi tải những thứ đó hộ kẻ xấu, trên Linux nó chạy trong một
vùng mạng riêng không có mạng (unshare -rn); HTML còn được gỡ mọi đường dẫn
ngoài, script, iframe trước khi chuyển.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

DUOI_WORD = {".docx", ".doc", ".odt", ".rtf"}
DUOI_HTML = {".html", ".htm"}
# Bảng tính giữ nguyên thiết lập trang của từng trang tính (khổ giấy, hướng
# ngang, vùng in) như khi bấm In trong Excel.
DUOI_BANG = {".xlsx", ".xlsm", ".xls", ".ods", ".csv", ".tsv"}
DUOI_TRINH_CHIEU = {".pptx", ".ppt", ".ppsx", ".pps", ".odp"}
DUOI_CHUYEN = DUOI_WORD | DUOI_HTML | DUOI_BANG | DUOI_TRINH_CHIEU
# CSV/TSV không tự khai bảng mã: đọc là UTF-8 (76), tách cột bằng dấu phẩy (44)
# hay tab (9), chuỗi đặt trong nháy kép (34).
_BO_LOC_VAN_BAN = {".csv": "--infilter=CSV:44,34,76", ".tsv": "--infilter=CSV:9,34,76"}

THU_MUC = os.path.abspath(os.getenv(
    "RAG_THU_MUC_BAN_PDF",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ban_pdf_tam"),
))
SO_BAN_TOI_DA = max(10, int(os.getenv("RAG_SO_BAN_PDF_TOI_DA", "300")))
GIAY_TOI_DA = 180

# LibreOffice ngốn CPU; chuyển lần lượt từng tệp thay vì chạy song song.
_khoa = threading.Lock()


class LoiChuyenPdf(ValueError):
    """Lỗi người dùng hiểu được: thiếu LibreOffice, tệp hỏng..."""


def chuyen_duoc(duong_dan: str) -> bool:
    return Path(duong_dan).suffix.lower() in DUOI_CHUYEN


def tim_soffice() -> str | None:
    soffice = shutil.which("soffice") or shutil.which("soffice.exe")
    if soffice:
        return soffice
    for ung_vien in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if os.path.exists(ung_vien):
            return ung_vien
    return None


def _cach_ly_mang() -> list[str]:
    """Tiền tố lệnh chạy LibreOffice không có mạng (Linux), rỗng nếu không làm được."""
    unshare = shutil.which("unshare") if os.name == "posix" else None
    if not unshare:
        return []
    try:
        ok = subprocess.run([unshare, "-rn", "true"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    return [unshare, "-rn"] if ok else []


_THE_NGUY_HIEM = re.compile(
    r"(?is)<(script|iframe|object|embed|frameset|frame|applet|noscript)\b.*?</\1\s*>"
    r"|<(script|iframe|object|embed|frame|applet|link|meta|base)\b[^>]*>"
)
_THUOC_TINH_DUONG_DAN = re.compile(
    r"""(?i)\b(src|href|background|srcset|data|poster|lowsrc|dynsrc|action|xlink:href)\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)"""
)
_URL_CSS = re.compile(r"""(?i)url\(\s*(?!['"]?data:)[^)]*\)""")
_IMPORT_CSS = re.compile(r"(?i)@import[^;]*;")


def lam_sach_html(noi_dung: bytes) -> bytes:
    """Bỏ script/iframe... và mọi đường dẫn không phải data: / #neo.

    Xử lý trên latin-1 để giữ nguyên từng byte, không phải đoán bảng mã.
    """
    chu = noi_dung.decode("latin-1")
    chu = _THE_NGUY_HIEM.sub("", chu)

    def giu_hay_bo(khop: re.Match) -> str:
        gia_tri = khop.group(2).strip("\"'").strip().lower()
        return khop.group(0) if gia_tri.startswith(("data:", "#")) else f'{khop.group(1)}="#"'

    chu = _THUOC_TINH_DUONG_DAN.sub(giu_hay_bo, chu)
    chu = _IMPORT_CSS.sub("", chu)
    chu = _URL_CSS.sub("none", chu)
    # Thêm khai báo UTF-8 nếu tệp không tự khai (thẻ meta cũ vừa bị gỡ cùng các
    # meta khác) - thiếu nó LibreOffice đọc tiếng Việt thành ký tự rác.
    if not chu.lstrip().lower().startswith("<?xml"):
        chu = '<meta charset="utf-8">' + chu if _la_utf8(noi_dung) else chu
    return chu.encode("latin-1")


def _la_utf8(noi_dung: bytes) -> bool:
    try:
        noi_dung.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def _khoa_ban(duong_dan: str) -> str:
    st = os.stat(duong_dan)
    goc = f"{os.path.abspath(duong_dan)}|{st.st_size}|{st.st_mtime_ns}"
    return hashlib.sha256(goc.encode("utf-8")).hexdigest()[:32]


def _don_bot() -> None:
    """Giữ SO_BAN_TOI_DA bản dùng gần nhất (mở lại là "chạm" vào tệp)."""
    try:
        cac_ban = sorted(Path(THU_MUC).glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    except OSError:
        return
    for ban in cac_ban[: max(0, len(cac_ban) - SO_BAN_TOI_DA)]:
        try:
            ban.unlink()
        except OSError:
            pass


def ban_pdf(duong_dan: str) -> str:
    """Đường dẫn bản PDF của tệp Word/Excel/PowerPoint/HTML (chuyển nếu chưa có)."""
    duoi = Path(duong_dan).suffix.lower()
    if duoi not in DUOI_CHUYEN:
        raise LoiChuyenPdf("Định dạng này chưa mở được trong sổ tay.")
    try:
        dich = os.path.join(THU_MUC, _khoa_ban(duong_dan) + ".pdf")
    except OSError as exc:
        raise LoiChuyenPdf("Tệp không còn trên máy chủ.") from exc
    if os.path.isfile(dich):
        try:
            os.utime(dich)
        except OSError:
            pass
        return dich

    with _khoa:
        if os.path.isfile(dich):
            return dich
        soffice = tim_soffice()
        if not soffice:
            raise LoiChuyenPdf(
                "Máy chủ chưa cài LibreOffice nên chưa mở được tệp Word, Excel, "
                "PowerPoint hay HTML trong sổ tay."
            )
        tam = tempfile.mkdtemp(prefix="rag-ban-pdf-")
        try:
            nguon = os.path.join(tam, "tai-lieu" + duoi)
            with open(duong_dan, "rb") as f:
                du_lieu = f.read()
            if duoi in DUOI_HTML:
                du_lieu = lam_sach_html(du_lieu)
            with open(nguon, "wb") as f:
                f.write(du_lieu)
            lenh = _cach_ly_mang() + [
                soffice,
                # Hồ sơ riêng cho mỗi lượt: không vướng khoá hồ sơ của phiên
                # LibreOffice khác, không để lại cấu hình nào.
                f"-env:UserInstallation={Path(tam, 'ho-so').as_uri()}",
                "--headless", "--norestore",
            ]
            if duoi in DUOI_HTML:
                # Bộ lọc Writer thường cho một trang liền mạch như văn bản; bộ lọc
                # "writer_web" đẩy tiêu đề sang một trang trắng riêng.
                lenh += ["--infilter=HTML (StarWriter)", "--convert-to", "pdf:writer_pdf_Export"]
            elif duoi in _BO_LOC_VAN_BAN:
                lenh += [_BO_LOC_VAN_BAN[duoi], "--convert-to", "pdf"]
            else:
                lenh += ["--convert-to", "pdf"]
            lenh += ["--outdir", tam, nguon]
            try:
                subprocess.run(lenh, capture_output=True, timeout=GIAY_TOI_DA, check=False)
            except subprocess.TimeoutExpired as exc:
                raise LoiChuyenPdf("Tệp quá lớn, chuyển sang dạng đọc được mất quá lâu.") from exc
            ra = os.path.join(tam, "tai-lieu.pdf")
            if not os.path.isfile(ra) or os.path.getsize(ra) == 0:
                raise LoiChuyenPdf("Không chuyển được tệp này sang dạng đọc được (có thể tệp bị hỏng).")
            os.makedirs(THU_MUC, exist_ok=True)
            tam_dich = dich + ".tmp"
            shutil.move(ra, tam_dich)
            os.replace(tam_dich, dich)
        finally:
            shutil.rmtree(tam, ignore_errors=True)
        _don_bot()
    return dich
