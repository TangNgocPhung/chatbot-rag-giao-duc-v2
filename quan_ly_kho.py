"""
QUẢN LÝ TỆP GỬI LÊN KHO TÀI LIỆU
================================
Trước đây tệp ai đính kèm trong khung chat cũng tự chép vào kho chung: một học
sinh gửi ảnh chụp bài tập là ảnh đó thành "tài liệu tra cứu" cho mọi người, và
không ai biết tệp nào do ai đưa vào.

Giờ:
  - Quản trị viên tải lên (nút "+" hay đính kèm) -> vào thẳng kho, có ghi tên.
  - Người khác đính kèm -> vẫn hỏi đáp được ngay trong cuộc trò chuyện của họ,
    nhưng bản sao gửi vào kho nằm ở hàng chờ cho tới khi quản trị viên duyệt.
  - Quản trị viên gỡ tài liệu khỏi kho -> tệp chuyển vào thùng rác của kho,
    khôi phục được; chỉ mục bỏ nội dung của tệp ở lần cập nhật kế tiếp.

Sổ ghi (ai gửi, lúc nào, ai duyệt) nằm trong SQLite riêng, tách khỏi sổ ghi
chép chỉ mục vốn do trình cập nhật chỉ mục ghi đè toàn bộ mỗi lần chạy.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import threading
import time
import uuid

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_DB = os.path.abspath(os.getenv(
    "RAG_KHO_TAI_LEN_DB", os.path.join(THU_MUC_DU_AN, "kho_tai_len.db")
))
THU_MUC_CHO_DUYET = os.path.abspath(os.getenv(
    "RAG_THU_MUC_CHO_DUYET", os.path.join(THU_MUC_DU_AN, "kho_cho_duyet")
))
THU_MUC_THUNG_RAC = os.path.abspath(os.getenv(
    "RAG_THU_MUC_THUNG_RAC_KHO", os.path.join(THU_MUC_DU_AN, "thung_rac_kho")
))

_khoa = threading.Lock()
_ket_noi: sqlite3.Connection | None = None


class LoiQuanLyKho(ValueError):
    def __init__(self, thong_bao: str, ma_http: int = 400):
        super().__init__(thong_bao)
        self.ma_http = ma_http


def _connect() -> sqlite3.Connection:
    global _ket_noi
    if _ket_noi is None:
        _ket_noi = sqlite3.connect(DUONG_DAN_DB, check_same_thread=False)
        _ket_noi.row_factory = sqlite3.Row
        _ket_noi.execute("PRAGMA journal_mode=WAL")
        _ket_noi.executescript(
            """
            CREATE TABLE IF NOT EXISTS tai_len (
                id            TEXT PRIMARY KEY,
                ten           TEXT NOT NULL,       -- tên người gửi đặt
                ten_trong_kho TEXT,                -- tên sau khi vào kho (có thể thêm " (2)")
                duong_dan_cho TEXT,                -- bản chờ duyệt, NULL khi đã xử lý
                ma_bam        TEXT NOT NULL,
                kich_thuoc    INTEGER NOT NULL,
                nguon         TEXT NOT NULL,       -- dinh_kem | kho
                trang_thai    TEXT NOT NULL,       -- cho_duyet | trong_kho | tu_choi
                nguoi_id      TEXT,
                nguoi_ten     TEXT NOT NULL,
                nguoi_email   TEXT,
                tao_luc       REAL NOT NULL,
                xu_ly_luc     REAL,
                xu_ly_boi     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_tai_len_trang_thai ON tai_len(trang_thai, tao_luc);
            CREATE TABLE IF NOT EXISTS thung_rac (
                id            TEXT PRIMARY KEY,
                ten           TEXT NOT NULL,       -- tên trong kho lúc bị gỡ
                duong_dan_rac TEXT NOT NULL,
                kich_thuoc    INTEGER NOT NULL,
                go_luc        REAL NOT NULL,
                go_boi        TEXT NOT NULL
            );
            """
        )
        _ket_noi.commit()
    return _ket_noi


def dong_ket_noi() -> None:
    global _ket_noi
    with _khoa:
        if _ket_noi is not None:
            _ket_noi.close()
            _ket_noi = None


def _nguoi(nguoi_dung: dict | None) -> tuple[str | None, str, str | None]:
    if not nguoi_dung:
        return None, "Khách", None
    return nguoi_dung.get("id"), nguoi_dung.get("ten") or nguoi_dung.get("email", ""), nguoi_dung.get("email")


# ------------------------------------------------------------
# GHI NHẬN
# ------------------------------------------------------------
def ghi_vao_kho(ten: str, ten_trong_kho: str, ma_bam: str, kich_thuoc: int,
                nguon: str, nguoi_dung: dict | None) -> None:
    """Tệp vào thẳng kho (quản trị viên tải lên): chỉ ghi lại ai đưa vào."""
    nguoi_id, nguoi_ten, nguoi_email = _nguoi(nguoi_dung)
    bay_gio = time.time()
    with _khoa:
        conn = _connect()
        conn.execute(
            "INSERT INTO tai_len (id, ten, ten_trong_kho, ma_bam, kich_thuoc, nguon,"
            " trang_thai, nguoi_id, nguoi_ten, nguoi_email, tao_luc, xu_ly_luc, xu_ly_boi)"
            " VALUES (?, ?, ?, ?, ?, ?, 'trong_kho', ?, ?, ?, ?, ?, ?)",
            (uuid.uuid4().hex, ten, ten_trong_kho, ma_bam, kich_thuoc, nguon,
             nguoi_id, nguoi_ten, nguoi_email, bay_gio, bay_gio, nguoi_ten),
        )
        conn.commit()


def gui_cho_duyet(duong_dan_nguon: str, ten: str, ma_bam: str,
                  nguon: str, nguoi_dung: dict | None) -> tuple[str, bool]:
    """Chép một bản vào hàng chờ duyệt. Trả về (id, là_mới).

    Cùng nội dung đang chờ rồi thì không xếp hàng lần hai - học sinh cả lớp
    cùng đính kèm một đề thi thì quản trị viên chỉ phải duyệt một lần.
    """
    with _khoa:
        conn = _connect()
        dong = conn.execute(
            "SELECT id FROM tai_len WHERE ma_bam = ? AND trang_thai = 'cho_duyet'", (ma_bam,)
        ).fetchone()
        if dong:
            return dong["id"], False
        ma = uuid.uuid4().hex
        os.makedirs(THU_MUC_CHO_DUYET, exist_ok=True)
        dich = os.path.join(THU_MUC_CHO_DUYET, ma + os.path.splitext(ten)[1].lower())
        shutil.copy2(duong_dan_nguon, dich)
        nguoi_id, nguoi_ten, nguoi_email = _nguoi(nguoi_dung)
        conn.execute(
            "INSERT INTO tai_len (id, ten, duong_dan_cho, ma_bam, kich_thuoc, nguon,"
            " trang_thai, nguoi_id, nguoi_ten, nguoi_email, tao_luc)"
            " VALUES (?, ?, ?, ?, ?, ?, 'cho_duyet', ?, ?, ?, ?)",
            (ma, ten, dich, ma_bam, os.path.getsize(dich), nguon,
             nguoi_id, nguoi_ten, nguoi_email, time.time()),
        )
        conn.commit()
        return ma, True


# ------------------------------------------------------------
# TRA CỨU
# ------------------------------------------------------------
def _cong_khai(dong: sqlite3.Row) -> dict:
    ban = dict(dong)
    ban.pop("duong_dan_cho", None)
    ban.pop("ma_bam", None)
    return ban


def danh_sach_tai_len(trang_thai: str | None = None, gioi_han: int = 300) -> list[dict]:
    sql = "SELECT * FROM tai_len"
    tham_so: list = []
    if trang_thai:
        sql += " WHERE trang_thai = ?"
        tham_so.append(trang_thai)
    sql += " ORDER BY tao_luc DESC LIMIT ?"
    tham_so.append(max(1, min(gioi_han, 1000)))
    return [_cong_khai(d) for d in _connect().execute(sql, tham_so).fetchall()]


def dem_cho_duyet() -> int:
    return _connect().execute(
        "SELECT COUNT(*) FROM tai_len WHERE trang_thai = 'cho_duyet'"
    ).fetchone()[0]


def nguoi_dua_vao_kho() -> dict[str, dict]:
    """ten_trong_kho -> {nguoi_ten, tao_luc} để danh sách kho ghi ai đã đưa vào."""
    ket_qua = {}
    for dong in _connect().execute(
        "SELECT ten_trong_kho, nguoi_ten, xu_ly_boi, tao_luc, xu_ly_luc, nguon"
        "  FROM tai_len WHERE trang_thai = 'trong_kho' ORDER BY tao_luc"
    ):
        ket_qua[dong["ten_trong_kho"]] = {
            "nguoi_gui": dong["nguoi_ten"],
            "nguoi_duyet": dong["xu_ly_boi"],
            "gui_luc": dong["tao_luc"],
            "nguon_gui": dong["nguon"],
        }
    return ket_qua


def lay_ban_cho(ma: str) -> tuple[dict, str]:
    dong = _connect().execute("SELECT * FROM tai_len WHERE id = ?", (ma,)).fetchone()
    if dong is None or dong["trang_thai"] != "cho_duyet" or not dong["duong_dan_cho"]:
        raise LoiQuanLyKho("Không tìm thấy tệp đang chờ duyệt.", 404)
    if not os.path.isfile(dong["duong_dan_cho"]):
        raise LoiQuanLyKho("Bản chờ duyệt không còn trên đĩa.", 410)
    return dict(dong), dong["duong_dan_cho"]


# ------------------------------------------------------------
# DUYỆT / TỪ CHỐI
# ------------------------------------------------------------
def duyet(ma: str, nguoi_duyet: dict, dua_vao_kho) -> str:
    """dua_vao_kho(duong_dan_tam, ten) -> (trang_thai, ten_trong_kho | thông báo)."""
    ban, duong_dan = lay_ban_cho(ma)
    trang_thai, ket_qua = dua_vao_kho(duong_dan, ban["ten"])
    if trang_thai not in {"da_luu", "da_co"}:
        raise LoiQuanLyKho(ket_qua)
    with _khoa:
        conn = _connect()
        conn.execute(
            "UPDATE tai_len SET trang_thai = 'trong_kho', ten_trong_kho = ?, duong_dan_cho = NULL,"
            " xu_ly_luc = ?, xu_ly_boi = ? WHERE id = ?",
            (ket_qua if trang_thai == "da_luu" else None, time.time(),
             nguoi_duyet.get("ten") or nguoi_duyet.get("email"), ma),
        )
        conn.commit()
    try:
        os.remove(duong_dan)
    except OSError:
        pass
    return ket_qua


def tu_choi(ma: str, nguoi_duyet: dict) -> None:
    _, duong_dan = lay_ban_cho(ma)
    with _khoa:
        conn = _connect()
        conn.execute(
            "UPDATE tai_len SET trang_thai = 'tu_choi', duong_dan_cho = NULL,"
            " xu_ly_luc = ?, xu_ly_boi = ? WHERE id = ?",
            (time.time(), nguoi_duyet.get("ten") or nguoi_duyet.get("email"), ma),
        )
        conn.commit()
    # Bản chờ chỉ là bản sao gửi vào kho; tệp đính kèm của người gửi vẫn còn
    # trong cuộc trò chuyện của họ, nên xoá bản này không mất gì.
    try:
        os.remove(duong_dan)
    except OSError:
        pass


# ------------------------------------------------------------
# THÙNG RÁC CỦA KHO
# ------------------------------------------------------------
def go_khoi_kho(duong_dan: str, nguoi_go: dict) -> dict:
    ten = os.path.basename(duong_dan)
    ma = uuid.uuid4().hex
    os.makedirs(THU_MUC_THUNG_RAC, exist_ok=True)
    dich = os.path.join(THU_MUC_THUNG_RAC, f"{ma}{os.path.splitext(ten)[1].lower()}")
    kich_thuoc = os.path.getsize(duong_dan)
    shutil.move(duong_dan, dich)
    with _khoa:
        conn = _connect()
        conn.execute(
            "INSERT INTO thung_rac (id, ten, duong_dan_rac, kich_thuoc, go_luc, go_boi)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (ma, ten, dich, kich_thuoc, time.time(), nguoi_go.get("ten") or nguoi_go.get("email")),
        )
        conn.commit()
    return {"id": ma, "ten": ten}


def danh_sach_thung_rac() -> list[dict]:
    return [
        {k: d[k] for k in ("id", "ten", "kich_thuoc", "go_luc", "go_boi")}
        for d in _connect().execute("SELECT * FROM thung_rac ORDER BY go_luc DESC")
    ]


def khoi_phuc(ma: str, duong_dan_dich) -> str:
    """duong_dan_dich(ten) -> đường dẫn trống trong kho (tránh trùng tên)."""
    dong = _connect().execute("SELECT * FROM thung_rac WHERE id = ?", (ma,)).fetchone()
    if dong is None:
        raise LoiQuanLyKho("Không tìm thấy tệp trong thùng rác.", 404)
    if not os.path.isfile(dong["duong_dan_rac"]):
        raise LoiQuanLyKho("Tệp trong thùng rác không còn trên đĩa.", 410)
    dich = duong_dan_dich(dong["ten"])
    os.makedirs(os.path.dirname(dich), exist_ok=True)
    shutil.move(dong["duong_dan_rac"], dich)
    with _khoa:
        conn = _connect()
        conn.execute("DELETE FROM thung_rac WHERE id = ?", (ma,))
        conn.commit()
    return os.path.basename(dich)
