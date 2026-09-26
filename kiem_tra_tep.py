"""
Kiểm tra an toàn tệp người dùng tải lên, TRƯỚC khi lưu và đọc nội dung.

Máy chủ không bao giờ chạy tệp người dùng gửi, chỉ đọc nó bằng pypdf,
openpyxl, python-docx, faster-whisper... Nên nguy cơ thật là:

1. Tệp độc lọt vào kho chung rồi được phát cho người khác tải về mở trên máy
   họ - chatbot thành kênh phát tán mã độc.
2. Tệp dị dạng làm chính trình đọc tệp treo hoặc ăn hết RAM (zip bomb).

Ba lớp chặn, chạy theo thứ tự rẻ tới đắt:

- Lớp 3 - chặn macro: không nhận .xlsm; .docx/.xlsx/.pptx có vbaProject.bin
  hoặc mẫu tải từ ngoài (template injection); .doc/.xls có dự án VBA.
- Lớp 2 - nội dung phải khớp đuôi (magic bytes): một .exe đổi tên thành .pdf
  không qua được. Tệp ZIP (docx, xlsx, pptx, epub) còn bị kiểm tra zip bomb.
- Lớp 1 - quét ClamAV qua clamdscan (daemon clamd giữ sẵn cơ sở mẫu trong RAM,
  quét vài trăm ms thay vì 20-30 giây nạp lại mẫu như clamscan).

Không lớp nào bắt được 100%: ClamAV chỉ nhận ra mẫu đã biết, còn lớp 2-3 là
luật tự viết. Cả ba cộng lại để giảm rủi ro, không phải để loại bỏ nó.

Biến môi trường:
  RAG_QUET_VIRUS            tat | tu_dong (mặc định) | bat_buoc
      tu_dong  : có clamdscan thì quét, máy không cài thì bỏ qua (máy dev).
      bat_buoc : không có clamdscan cũng từ chối tệp - dùng trên máy chủ thật,
                 để lỡ gỡ ClamAV thì việc tải lên dừng chứ không lặng lẽ bỏ quét.
      Khi đã quét mà clamd lỗi / quá giờ thì LUÔN từ chối (fail-closed).
  RAG_LENH_CLAMDSCAN        đường dẫn tới clamdscan (mặc định tìm trong PATH)
  RAG_GIOI_HAN_GIAI_NEN_MB  tổng dung lượng giải nén tối đa của một tệp ZIP (500)
"""

from __future__ import annotations

import io
import logging
import os
import re
import shutil
import subprocess
import zipfile

logger = logging.getLogger(__name__)


class TepKhongAnToan(ValueError):
    """Tệp bị từ chối vì lý do an toàn. Thông báo hiển thị thẳng cho người dùng."""


# ------------------------------------------------------------
# LỚP 3: định dạng không nhận khi tải lên
# ------------------------------------------------------------
# .xlsm là Excel CÓ macro. Chatbot chỉ cần dữ liệu trong bảng, không cần macro,
# nên không có lý do nhận nó. Chỉ chặn ở cửa tải lên: trình đọc vẫn đọc được
# .xlsm có sẵn trong kho do quản trị viên chép vào trên máy chủ.
DUOI_CAM_TAI_LEN = {".xlsm"}


# ------------------------------------------------------------
# LỚP 2: nội dung phải khớp đuôi
# ------------------------------------------------------------
CHU_KY_ZIP = b"PK\x03\x04"
CHU_KY_OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # Word/Excel 97-2003
CHU_KY_RTF = b"{\\rtf"

_DUOI_ZIP = {".docx", ".xlsx", ".pptx", ".epub"}
_CHU_KY_ANH = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".bmp": (b"BM",),
    ".tif": (b"II*\x00", b"MM\x00*"),
    ".tiff": (b"II*\x00", b"MM\x00*"),
}

# Tệp thực thi thì không đuôi nào hợp lệ cả, kể cả .txt.
_CHU_KY_THUC_THI = (
    b"\x7fELF",              # Linux
    b"\xca\xfe\xba\xbe",     # Mach-O fat (macOS)
    b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf",
    b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe",
)

# Giới hạn chống zip bomb. Tệp Office nén XML khoảng 10-20 lần, tệp có ảnh hay
# video bên trong gần như không nén thêm được, nên 40 MB tải lên hiếm khi giải
# nén quá vài trăm MB. DEFLATE nén tối đa ~1032:1 nên zip bomb một lớp lộ ra
# qua tỉ lệ nén của từng mục.
GIOI_HAN_GIAI_NEN = max(1, int(os.getenv("RAG_GIOI_HAN_GIAI_NEN_MB", "500"))) * 1024 * 1024
SO_MUC_ZIP_TOI_DA = 20_000
TI_LE_NEN_TOI_DA = 200
_CO_MUC_DANG_XET_TI_LE = 10 * 1024 * 1024  # mục nhỏ hơn thì tỉ lệ cao cũng vô hại
_CO_TEP_RELS_TOI_DA = 1024 * 1024

# Quan hệ trỏ ra ngoài mà Word/Excel tự tải khi mở tệp: attachedTemplate là
# kỹ thuật "template injection" kéo tài liệu có macro từ máy chủ kẻ tấn công về.
# Liên kết (hyperlink) cũng là quan hệ ngoài nhưng chỉ mở khi người đọc bấm.
_QUAN_HE_NGOAI_NGUY_HIEM = re.compile(
    rb"<Relationship\b"
    rb"(?=[^>]*\bTargetMode=\"External\")"
    rb"(?=[^>]*\bType=\"[^\"]*/(?:attachedTemplate|oleObject|frame|subDocument)\")",
    re.IGNORECASE,
)

# Dự án VBA trong tệp OLE (Word/Excel 97-2003) nằm ở luồng _VBA_PROJECT
# (Excel: _VBA_PROJECT_CUR). Tên luồng OLE lưu dạng UTF-16LE nên tìm thẳng
# trong byte. Đây là heuristic: một tài liệu mà NỘI DUNG chữ có đúng chuỗi
# "_VBA_PROJECT" cũng bị chặn nhầm - chấp nhận được với tài liệu giáo dục.
_DAU_HIEU_VBA_OLE = "_VBA_PROJECT".encode("utf-16-le")


def _la_tep_thuc_thi_windows(du_lieu: bytes) -> bool:
    """MZ ở đầu và "PE\\0\\0" ở vị trí header trỏ tới: một .exe/.dll thật.

    Không chặn chỉ vì 2 byte "MZ" - một tệp .txt bắt đầu bằng "MZ" là hợp lệ.
    """
    if not du_lieu.startswith(b"MZ") or len(du_lieu) < 0x40:
        return False
    vi_tri_pe = int.from_bytes(du_lieu[0x3C:0x40], "little")
    return du_lieu[vi_tri_pe:vi_tri_pe + 4] == b"PE\x00\x00"


def _kiem_tra_chu_ky(duoi: str, du_lieu: bytes) -> None:
    if _la_tep_thuc_thi_windows(du_lieu) or du_lieu.startswith(_CHU_KY_THUC_THI):
        raise TepKhongAnToan("Tệp là chương trình chạy được (không phải tài liệu) nên bị từ chối.")

    sai_dinh_dang = TepKhongAnToan(
        f"Nội dung tệp không phải định dạng {duoi} như tên tệp. "
        "Hãy mở tệp bằng ứng dụng gốc và lưu lại đúng định dạng."
    )
    if duoi == ".pdf":
        # Chuẩn PDF cho phép vài byte rác trước "%PDF-", trình đọc bỏ qua được.
        if b"%PDF-" not in du_lieu[:1024]:
            raise sai_dinh_dang
    elif duoi in _DUOI_ZIP:
        if not du_lieu.startswith(CHU_KY_ZIP):
            raise sai_dinh_dang
    elif duoi == ".doc":
        # Nhiều tệp .doc thật ra là RTF hoặc .docx đặt nhầm đuôi - Word và
        # LibreOffice đều mở được, nên vẫn nhận.
        if not du_lieu.startswith((CHU_KY_OLE, CHU_KY_RTF, CHU_KY_ZIP)):
            raise sai_dinh_dang
    elif duoi == ".xls":
        # pandas nhìn nội dung để chọn trình đọc: OLE -> xlrd, ZIP -> openpyxl.
        if not du_lieu.startswith((CHU_KY_OLE, CHU_KY_ZIP)):
            raise sai_dinh_dang
    elif duoi in _CHU_KY_ANH:
        if not du_lieu.startswith(_CHU_KY_ANH[duoi]):
            raise sai_dinh_dang
    elif duoi == ".webp":
        if not (du_lieu.startswith(b"RIFF") and du_lieu[8:12] == b"WEBP"):
            raise sai_dinh_dang
    # Văn bản thuần (.txt, .csv, .md, .html, .srt...) không có chữ ký cố định.
    # Âm thanh/video cũng không kiểm ở đây: .mp3 không có thẻ ID3, .aac thô...
    # có nhiều dạng đầu tệp hợp lệ, đoán sai là chặn nhầm bài giảng của giáo
    # viên. Lọc tệp thực thi ở trên đã áp cho cả hai nhóm này.


def _kiem_tra_zip(du_lieu: bytes) -> None:
    """Zip bomb và macro trong các định dạng Office mới (đều là tệp ZIP)."""
    try:
        tep_zip = zipfile.ZipFile(io.BytesIO(du_lieu))
        cac_muc = tep_zip.infolist()
    except (zipfile.BadZipFile, ValueError, OSError) as exc:
        raise TepKhongAnToan("Tệp bị hỏng, không mở được cấu trúc bên trong.") from exc

    if len(cac_muc) > SO_MUC_ZIP_TOI_DA:
        raise TepKhongAnToan("Tệp chứa quá nhiều thành phần bên trong, có dấu hiệu tệp nén độc hại.")
    # Kích thước lấy từ header của từng mục. Header nói dối cũng không sao:
    # zipfile của Python (openpyxl, python-docx, python-pptx đều dùng nó) chỉ
    # giải nén tới đúng kích thước khai báo rồi báo lỗi CRC.
    tong = sum(muc.file_size for muc in cac_muc)
    if tong > GIOI_HAN_GIAI_NEN:
        raise TepKhongAnToan(
            f"Tệp giải nén ra hơn {GIOI_HAN_GIAI_NEN // 1048576} MB, có dấu hiệu tệp nén độc hại (zip bomb)."
        )
    for muc in cac_muc:
        if (
            muc.file_size > _CO_MUC_DANG_XET_TI_LE
            and muc.file_size > TI_LE_NEN_TOI_DA * max(muc.compress_size, 1)
        ):
            raise TepKhongAnToan("Tệp có thành phần bị nén bất thường, có dấu hiệu tệp nén độc hại (zip bomb).")

    for muc in cac_muc:
        ten = muc.filename.lower()
        if ten.endswith("vbaproject.bin"):
            raise TepKhongAnToan(
                "Tệp có chứa macro nên bị từ chối. Hãy lưu lại dạng không có macro "
                "(.docx, .xlsx, .pptx) rồi tải lên."
            )
        if ten.endswith(".rels") and muc.file_size <= _CO_TEP_RELS_TOI_DA:
            try:
                noi_dung = tep_zip.read(muc)
            except (zipfile.BadZipFile, ValueError, OSError, NotImplementedError) as exc:
                raise TepKhongAnToan("Tệp bị hỏng, không mở được cấu trúc bên trong.") from exc
            if _QUAN_HE_NGOAI_NGUY_HIEM.search(noi_dung):
                raise TepKhongAnToan(
                    "Tệp tự tải nội dung từ máy chủ bên ngoài khi mở (mẫu hoặc đối tượng nhúng) nên bị từ chối."
                )


def _kiem_tra_ole(du_lieu: bytes) -> None:
    if _DAU_HIEU_VBA_OLE in du_lieu:
        raise TepKhongAnToan(
            "Tệp có chứa macro nên bị từ chối. Hãy lưu lại dạng .docx hoặc .xlsx "
            "(không có macro) rồi tải lên."
        )


# ------------------------------------------------------------
# LỚP 1: ClamAV
# ------------------------------------------------------------
THOI_GIAN_QUET_TOI_DA = 120  # giây; tệp 40 MB trên clamd thường chỉ vài giây


def _che_do_quet() -> str:
    che_do = os.getenv("RAG_QUET_VIRUS", "tu_dong").strip().lower()
    return che_do if che_do in {"tat", "tu_dong", "bat_buoc"} else "tu_dong"


def _tim_clamdscan() -> str | None:
    lenh = os.getenv("RAG_LENH_CLAMDSCAN", "").strip()
    return lenh or shutil.which("clamdscan")


def quet_virus(du_lieu: bytes) -> None:
    """Quét bằng clamdscan, gửi byte qua stdin (clamd nhận bằng lệnh INSTREAM).

    Gửi byte thay vì đường dẫn để clamd (chạy bằng user clamav) không cần quyền
    đọc thư mục của ứng dụng.

    QUAN TRỌNG: clamd.conf phải có StreamMaxLength và MaxFileSize lớn hơn giới
    hạn tải lên (RAG_GIOI_HAN_TEP_MB). Mặc định của Debian/Ubuntu là 25M, và
    khi vượt, clamd KHÔNG báo lỗi: nó chỉ quét 25 MB đầu rồi trả "OK" (đã thử
    với ClamAV 1.5: mã độc đặt sau 30 MB lọt qua). 01_cai_dat_vps.sh đặt 64M.
    """
    che_do = _che_do_quet()
    if che_do == "tat":
        return
    clamdscan = _tim_clamdscan()
    if clamdscan is None:
        if che_do == "bat_buoc":
            logger.error("RAG_QUET_VIRUS=bat_buoc nhưng không tìm thấy clamdscan.")
            raise TepKhongAnToan("Máy chủ chưa kiểm tra được an toàn của tệp, hãy thử lại sau.")
        return

    try:
        ket_qua = subprocess.run(
            [clamdscan, "--no-summary", "-"],
            input=du_lieu, capture_output=True, timeout=THOI_GIAN_QUET_TOI_DA, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("Không chạy được clamdscan: %s", exc)
        raise TepKhongAnToan("Máy chủ chưa kiểm tra được an toàn của tệp, hãy thử lại sau.") from exc

    # Mã thoát của clamdscan: 0 = sạch, 1 = có mã độc, 2 = lỗi.
    if ket_qua.returncode == 0:
        return
    dau_ra = ket_qua.stdout.decode("utf-8", "replace").strip()
    if ket_qua.returncode == 1:
        # Dạng "stream: Eicar-Test-Signature FOUND"
        ten_ma_doc = dau_ra.split(":", 1)[-1].removesuffix("FOUND").strip() or "không rõ tên"
        logger.warning("ClamAV chặn một tệp tải lên: %s", ten_ma_doc)
        raise TepKhongAnToan(f"Tệp bị phát hiện chứa mã độc ({ten_ma_doc}) nên đã bị từ chối.")
    logger.error(
        "clamdscan lỗi (mã %s): %s %s", ket_qua.returncode, dau_ra,
        ket_qua.stderr.decode("utf-8", "replace").strip(),
    )
    raise TepKhongAnToan("Máy chủ chưa kiểm tra được an toàn của tệp, hãy thử lại sau.")


# ------------------------------------------------------------
# ĐIỂM VÀO
# ------------------------------------------------------------
def kiem_tra_tai_len(ten: str, du_lieu: bytes) -> None:
    """Chạy cả ba lớp. Ném TepKhongAnToan nếu tệp không được nhận.

    Gọi SAU khi đã kiểm tra đuôi nằm trong danh sách hỗ trợ và giới hạn dung lượng.
    """
    duoi = os.path.splitext(ten)[1].lower()
    if duoi in DUOI_CAM_TAI_LEN:
        raise TepKhongAnToan(
            f"Không nhận tệp {duoi} vì định dạng này chứa được macro. "
            "Hãy lưu lại dạng .xlsx rồi tải lên."
        )
    _kiem_tra_chu_ky(duoi, du_lieu)
    if du_lieu.startswith(CHU_KY_ZIP) and duoi in _DUOI_ZIP | {".doc", ".xls"}:
        _kiem_tra_zip(du_lieu)
    elif du_lieu.startswith(CHU_KY_OLE):
        _kiem_tra_ole(du_lieu)
    quet_virus(du_lieu)


def kiem_tra_tep_tren_dia(duong_dan: str, ten: str) -> None:
    """Như kiem_tra_tai_len, cho tệp đã nằm trên đĩa (tệp chờ duyệt)."""
    with open(duong_dan, "rb") as tep:
        kiem_tra_tai_len(ten, tep.read())
