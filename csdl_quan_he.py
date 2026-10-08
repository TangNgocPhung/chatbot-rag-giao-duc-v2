"""
CƠ SỞ DỮ LIỆU QUAN HỆ VĂN BẢN (SQLite)
======================================
Nơi lưu đồ thị quan hệ mà quan_he_van_ban.SoQuanHe dựng ra: văn bản là nút,
quan hệ (thay thế, sửa đổi, hướng dẫn...) là cạnh có hướng.

  van_ban       một dòng/số hiệu - kể cả văn bản cũ đã rời kho, vì vẫn phải
                biết nó bị thay bởi gì; phụ lục tách tệp mang khóa "tep:<tên>"
  tep           tệp trong kho -> số hiệu của văn bản chứa nó
  loai_quan_he  5 loại quan hệ với tên đọc xuôi/ngược
  quan_he       cạnh (tu, loai, den), nguồn tu_dong (đọc từ nội dung) hoặc so_tay
  loai_bo       cạnh máy đọc sai mà sổ tay đã chặn (bản sao để tra cứu)
  quan_he_de_doc  view ghép nhãn văn bản và tên quan hệ cho người đọc

Đồ thị là dữ liệu SUY RA từ nội dung kho + sổ tay so_quan_he_van_ban.json, nên
mỗi lần dựng lại thì ghi đè toàn bộ trong một giao dịch: người đọc không bao giờ
thấy nửa đồ thị cũ nửa mới. Sửa quan hệ bằng tay thì sửa sổ tay JSON, không sửa
tệp .db - lần dựng sau sẽ ghi đè.

Xem nhanh:  sqlite3 quan_he_van_ban.db "SELECT * FROM quan_he_de_doc LIMIT 20"
"""

from __future__ import annotations

import os
import sqlite3

DUONG_DAN_CSDL = os.path.abspath(os.getenv(
    "RAG_QUAN_HE_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "quan_he_van_ban.db"),
))

PHIEN_BAN_LUOC_DO = "1"

LUOC_DO = """
CREATE TABLE IF NOT EXISTS loai_quan_he (
    ma        TEXT PRIMARY KEY,
    ten_xuoi  TEXT NOT NULL,
    ten_nguoc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS van_ban (
    so_hieu       TEXT PRIMARY KEY,
    nhan          TEXT NOT NULL,
    loai_van_ban  TEXT,
    ngay_ban_hanh TEXT,
    ngay_hieu_luc TEXT,
    tinh_trang    TEXT NOT NULL,
    tu_ngay       TEXT,
    trong_kho     INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tep (
    ten_file TEXT PRIMARY KEY,
    so_hieu  TEXT NOT NULL REFERENCES van_ban(so_hieu)
);
CREATE TABLE IF NOT EXISTS quan_he (
    tu     TEXT NOT NULL REFERENCES van_ban(so_hieu),
    loai   TEXT NOT NULL REFERENCES loai_quan_he(ma),
    den    TEXT NOT NULL REFERENCES van_ban(so_hieu),
    nguon  TEXT NOT NULL CHECK (nguon IN ('tu_dong', 'so_tay')),
    can_cu TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (tu, loai, den)
);
CREATE INDEX IF NOT EXISTS ix_quan_he_den ON quan_he(den);
CREATE INDEX IF NOT EXISTS ix_tep_so_hieu ON tep(so_hieu);
CREATE TABLE IF NOT EXISTS loai_bo (
    tu   TEXT NOT NULL,
    loai TEXT NOT NULL,
    den  TEXT NOT NULL,
    PRIMARY KEY (tu, loai, den)
);
CREATE TABLE IF NOT EXISTS thong_tin (
    khoa    TEXT PRIMARY KEY,
    gia_tri TEXT
);
CREATE VIEW IF NOT EXISTS quan_he_de_doc AS
    SELECT a.nhan AS van_ban, l.ten_xuoi AS quan_he, b.nhan AS van_ban_kia,
           q.nguon, q.can_cu, q.tu, q.loai, q.den
    FROM quan_he q
    JOIN van_ban a ON a.so_hieu = q.tu
    JOIN van_ban b ON b.so_hieu = q.den
    JOIN loai_quan_he l ON l.ma = q.loai;
"""


def ket_noi(duong_dan: str | None = None) -> sqlite3.Connection:
    """Mở (tạo nếu chưa có) CSDL, bật khóa ngoại - SQLite mặc định tắt."""
    conn = sqlite3.connect(duong_dan or DUONG_DAN_CSDL)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(LUOC_DO)
    return conn


def ghi(du_lieu: dict, duong_dan: str | None = None) -> None:
    """Ghi đè cả đồ thị bằng kết quả SoQuanHe.xuat()."""
    conn = ket_noi(duong_dan)
    try:
        with conn:  # một giao dịch: lỗi giữa chừng thì giữ nguyên bản cũ
            for bang in ("tep", "quan_he", "loai_bo", "van_ban", "loai_quan_he", "thong_tin"):
                conn.execute(f"DELETE FROM {bang}")
            conn.executemany(
                "INSERT INTO loai_quan_he VALUES (?, ?, ?)",
                [(ma, ten[0], ten[1]) for ma, ten in du_lieu["loai_quan_he"].items()],
            )
            conn.executemany(
                "INSERT INTO van_ban VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (so_hieu, muc["nhan"], muc.get("loai_van_ban"), muc.get("ngay_ban_hanh"),
                     muc.get("ngay_hieu_luc"), muc["tinh_trang"], muc.get("tu_ngay"),
                     1 if muc.get("tep") else 0)
                    for so_hieu, muc in du_lieu["van_ban"].items()
                ],
            )
            conn.executemany(
                "INSERT INTO tep VALUES (?, ?)",
                [(ten, so_hieu) for so_hieu, muc in du_lieu["van_ban"].items()
                 for ten in muc.get("tep") or []],
            )
            conn.executemany(
                "INSERT INTO quan_he VALUES (?, ?, ?, ?, ?)",
                [(q["tu"], q["loai"], q["den"], q["nguon"], q.get("can_cu") or "")
                 for q in du_lieu["quan_he"]],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO loai_bo VALUES (?, ?, ?)",
                [(q["tu"], q["loai"], q["den"]) for q in du_lieu.get("loai_bo") or []],
            )
            conn.executemany(
                "INSERT INTO thong_tin VALUES (?, ?)",
                [("phien_ban_luoc_do", PHIEN_BAN_LUOC_DO), ("ngay_tinh", du_lieu.get("ngay_tinh"))],
            )
    finally:
        conn.close()


def do_thi(goc: list[str] | None = None, so_buoc: int = 2,
           duong_dan: str | None = None) -> dict | None:
    """
    Nút và cạnh để vẽ: không có goc thì mọi văn bản có quan hệ (văn bản đứng
    riêng chỉ làm rối hình); có goc thì vùng đi tối đa so_buoc bước theo cạnh
    cả hai chiều - truy vấn đệ quy ngay trong SQLite. None khi chưa có CSDL.
    """
    duong_dan = duong_dan or DUONG_DAN_CSDL
    if not os.path.exists(duong_dan):
        return None
    goc = [g for g in (goc or []) if g]
    conn = ket_noi(duong_dan)
    try:
        if goc:
            tap_nut = {dong[0] for dong in conn.execute(f"""
                WITH RECURSIVE canh(a, b) AS (
                    SELECT tu, den FROM quan_he UNION SELECT den, tu FROM quan_he
                ), vung(so_hieu, buoc) AS (
                    SELECT so_hieu, 0 FROM van_ban WHERE so_hieu IN ({",".join("?" * len(goc))})
                    UNION
                    SELECT canh.b, vung.buoc + 1 FROM canh JOIN vung ON canh.a = vung.so_hieu
                    WHERE vung.buoc < ?
                )
                SELECT DISTINCT so_hieu FROM vung""", (*goc, so_buoc))}
        else:
            tap_nut = {dong[0] for dong in conn.execute(
                "SELECT tu FROM quan_he UNION SELECT den FROM quan_he"
            )}
        tep_cua: dict[str, list[str]] = {}
        for dong in conn.execute("SELECT ten_file, so_hieu FROM tep ORDER BY ten_file"):
            tep_cua.setdefault(dong["so_hieu"], []).append(dong["ten_file"])
        nut = [
            {
                "so_hieu": dong["so_hieu"],
                "nhan": dong["nhan"],
                "loai_van_ban": dong["loai_van_ban"],
                "ngay_hieu_luc": dong["ngay_hieu_luc"],
                "tinh_trang": dong["tinh_trang"],
                "tu_ngay": dong["tu_ngay"],
                "tep": tep_cua.get(dong["so_hieu"], []),
                "goc": dong["so_hieu"] in goc,
            }
            for dong in conn.execute("SELECT * FROM van_ban ORDER BY so_hieu")
            if dong["so_hieu"] in tap_nut
        ]
        canh = [
            {"tu": dong["tu"], "den": dong["den"], "loai": dong["loai"], "ten": dong["quan_he"],
             "nguon": dong["nguon"], "can_cu": dong["can_cu"]}
            for dong in conn.execute("SELECT * FROM quan_he_de_doc ORDER BY den, loai, tu")
            if dong["tu"] in tap_nut and dong["den"] in tap_nut
        ]
        # Danh sách để tìm: mọi văn bản, kể cả văn bản không có quan hệ nào.
        tat_ca = [
            {"so_hieu": dong["so_hieu"], "nhan": dong["nhan"], "tep": tep_cua.get(dong["so_hieu"], [])}
            for dong in conn.execute("SELECT so_hieu, nhan FROM van_ban ORDER BY so_hieu")
        ]
        ngay_tinh = conn.execute(
            "SELECT gia_tri FROM thong_tin WHERE khoa = 'ngay_tinh'"
        ).fetchone()
        return {
            "ngay_tinh": ngay_tinh[0] if ngay_tinh else None,
            "loai_quan_he": {
                dong["ma"]: [dong["ten_xuoi"], dong["ten_nguoc"]]
                for dong in conn.execute("SELECT * FROM loai_quan_he")
            },
            "goc": [g for g in goc if any(n["so_hieu"] == g for n in nut)],
            "nut": nut,
            "canh": canh,
            "tat_ca": tat_ca,
        }
    finally:
        conn.close()


def doc(duong_dan: str | None = None) -> dict | None:
    """
    Đồ thị đã lưu, cùng dạng SoQuanHe.xuat() (thiếu thong_ke); None khi chưa
    từng ghi. Không tạo tệp rỗng chỉ vì có người đọc.
    """
    duong_dan = duong_dan or DUONG_DAN_CSDL
    if not os.path.exists(duong_dan):
        return None
    conn = ket_noi(duong_dan)
    try:
        tep_cua: dict[str, list[str]] = {}
        for dong in conn.execute("SELECT ten_file, so_hieu FROM tep ORDER BY ten_file"):
            tep_cua.setdefault(dong["so_hieu"], []).append(dong["ten_file"])
        van_ban = {
            dong["so_hieu"]: {
                "nhan": dong["nhan"],
                "loai_van_ban": dong["loai_van_ban"],
                "ngay_ban_hanh": dong["ngay_ban_hanh"],
                "ngay_hieu_luc": dong["ngay_hieu_luc"],
                "tinh_trang": dong["tinh_trang"],
                "tu_ngay": dong["tu_ngay"],
                "tep": tep_cua.get(dong["so_hieu"], []),
            }
            for dong in conn.execute("SELECT * FROM van_ban ORDER BY so_hieu")
        }
        quan_he = [
            dict(dong) for dong in conn.execute(
                "SELECT tu, loai, den, nguon, can_cu FROM quan_he ORDER BY den, loai, tu"
            )
        ]
        loai_bo = [dict(dong) for dong in conn.execute("SELECT tu, loai, den FROM loai_bo")]
        thong_tin = dict(conn.execute("SELECT khoa, gia_tri FROM thong_tin").fetchall())
        return {
            "ngay_tinh": thong_tin.get("ngay_tinh"),
            "van_ban": van_ban,
            "quan_he": quan_he,
            "loai_bo": loai_bo,
        }
    finally:
        conn.close()
