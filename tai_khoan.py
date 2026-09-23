"""
TÀI KHOẢN NGƯỜI DÙNG
====================
Trước đây mỗi trình duyệt tự sinh một mã ngẫu nhiên (X-RAG-Client) để máy chủ
gom lịch sử - không phải đăng nhập thật: đổi máy là mất lịch sử, ai gửi mã của
người khác là đọc được hội thoại của họ, và mọi người đều bấm được "cập nhật
kho", "đổi mô hình".

Giống ChatGPT: không bắt buộc đăng nhập - khách vẫn hỏi được như cũ. Đăng nhập
thì lịch sử và sổ tay nằm trên máy chủ theo tài khoản, mở máy khác vẫn thấy;
tài khoản quản trị mới được làm các thao tác đụng tới cả hệ thống.

Chỉ dùng thư viện chuẩn: mật khẩu băm bằng scrypt (hashlib), phiên đăng nhập là
chuỗi ngẫu nhiên 256 bit trong cookie HttpOnly, máy chủ chỉ giữ bản băm SHA-256
của nó - lộ tệp cơ sở dữ liệu cũng không dùng lại được phiên của ai.

Quên mật khẩu: chưa có máy chủ gửi thư nên quản trị viên đặt lại bằng dòng lệnh
    python tai_khoan.py dat-lai-mat-khau email@truong.edu.vn
    python tai_khoan.py quan-tri email@truong.edu.vn        # cấp quyền quản trị
    python tai_khoan.py danh-sach
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid

DUONG_DAN_DB = os.path.abspath(os.getenv(
    "RAG_TAI_KHOAN_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tai_khoan.db"),
))
TEN_COOKIE = "rag_phien"
GIAY_PHIEN = 30 * 86400
MAT_KHAU_TOI_THIEU = 8
MAT_KHAU_TOI_DA = 200
SO_TAY_TOI_DA_BYTE = 8 * 1024 * 1024  # sổ có ảnh vùng khoanh, vài MB là cùng

# scrypt: n=2^14, r=8 tốn ~16 MB RAM và ~50 ms mỗi lần - đủ chậm để dò mật khẩu
# hàng loạt không bõ, đủ nhanh để máy chủ CPU không khựng khi có người đăng nhập.
_SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}

# Đăng nhập sai liên tục: khoá tạm theo địa chỉ IP và theo email.
SO_LAN_SAI_TOI_DA = 10
GIAY_KHOA = 15 * 60
SO_DANG_KY_MOI_GIO = 5

_khoa_ghi = threading.Lock()
_ket_noi: sqlite3.Connection | None = None
_khoa_dem = threading.Lock()
_lan_sai: dict[str, list[float]] = {}
_lan_dang_ky: dict[str, list[float]] = {}

_MAU_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


class LoiTaiKhoan(ValueError):
    """Lỗi người dùng hiểu và tự sửa được: sai mật khẩu, email đã dùng..."""

    def __init__(self, thong_bao: str, ma_http: int = 400):
        super().__init__(thong_bao)
        self.ma_http = ma_http


def bat_khoa_quan_tri() -> bool:
    """Tắt được (RAG_KHOA_QUAN_TRI=0) cho bộ test và máy cá nhân chỉ một người dùng."""
    return os.getenv("RAG_KHOA_QUAN_TRI", "1") == "1"


def email_quan_tri() -> set[str]:
    """Email được chỉ định là quản trị viên. Để trống thì tài khoản đầu tiên là quản trị.

    Chạy công khai (VPS) nên đặt biến này: nếu không, người lạ nào đăng ký
    trước quản trị viên thật sẽ thành quản trị viên.
    """
    return {
        e.strip().lower()
        for e in os.getenv("RAG_EMAIL_QUAN_TRI", "").split(",")
        if e.strip()
    }


# ------------------------------------------------------------
# CƠ SỞ DỮ LIỆU
# ------------------------------------------------------------
def _connect() -> sqlite3.Connection:
    global _ket_noi
    if _ket_noi is None:
        _ket_noi = sqlite3.connect(DUONG_DAN_DB, check_same_thread=False)
        _ket_noi.row_factory = sqlite3.Row
        _ket_noi.execute("PRAGMA journal_mode=WAL")
        _ket_noi.executescript(
            """
            CREATE TABLE IF NOT EXISTS nguoi_dung (
                id            TEXT PRIMARY KEY,
                email         TEXT NOT NULL UNIQUE,
                ten           TEXT NOT NULL,
                mat_khau_bam  TEXT NOT NULL,
                quan_tri      INTEGER NOT NULL DEFAULT 0,
                tao_luc       REAL NOT NULL,
                dang_nhap_luc REAL
            );
            CREATE TABLE IF NOT EXISTS phien (
                ma_bam        TEXT PRIMARY KEY,
                nguoi_dung_id TEXT NOT NULL,
                tao_luc       REAL NOT NULL,
                het_han       REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_phien_nguoi_dung ON phien(nguoi_dung_id);
            CREATE TABLE IF NOT EXISTS so_tay (
                nguoi_dung_id TEXT NOT NULL,
                hoi_thoai_id  TEXT NOT NULL,
                du_lieu       TEXT NOT NULL,
                cap_nhat_luc  REAL NOT NULL,
                PRIMARY KEY (nguoi_dung_id, hoi_thoai_id)
            );
            """
        )
        _ket_noi.commit()
    return _ket_noi


def dong_ket_noi() -> None:
    """Dùng trong test để chuyển sang cơ sở dữ liệu tạm."""
    global _ket_noi
    with _khoa_ghi:
        if _ket_noi is not None:
            _ket_noi.close()
            _ket_noi = None
    with _khoa_dem:
        _lan_sai.clear()
        _lan_dang_ky.clear()


# ------------------------------------------------------------
# MẬT KHẨU
# ------------------------------------------------------------
def bam_mat_khau(mat_khau: str) -> str:
    muoi = secrets.token_bytes(16)
    bam = hashlib.scrypt(mat_khau.encode("utf-8"), salt=muoi, dklen=32, **_SCRYPT)
    b64 = lambda b: base64.b64encode(b).decode("ascii")  # noqa: E731
    return f"scrypt${_SCRYPT['n']}${_SCRYPT['r']}${_SCRYPT['p']}${b64(muoi)}${b64(bam)}"


def dung_mat_khau(mat_khau: str, da_bam: str) -> bool:
    try:
        kieu, n, r, p, muoi, bam = da_bam.split("$")
        if kieu != "scrypt":
            return False
        thu = hashlib.scrypt(
            mat_khau.encode("utf-8"), salt=base64.b64decode(muoi), dklen=32,
            n=int(n), r=int(r), p=int(p),
        )
        return hmac.compare_digest(thu, base64.b64decode(bam))
    except (ValueError, TypeError):
        return False


# Băm sẵn một mật khẩu giả: email không tồn tại vẫn tốn đúng thời gian như sai
# mật khẩu, để thời gian trả lời không tiết lộ email nào đã có tài khoản.
_BAM_GIA = bam_mat_khau(secrets.token_urlsafe(16))


def _kiem_tra_mat_khau_moi(mat_khau: str) -> None:
    if len(mat_khau) < MAT_KHAU_TOI_THIEU:
        raise LoiTaiKhoan(f"Mật khẩu cần ít nhất {MAT_KHAU_TOI_THIEU} ký tự.")
    if len(mat_khau) > MAT_KHAU_TOI_DA:
        raise LoiTaiKhoan("Mật khẩu quá dài.")
    if mat_khau.strip() != mat_khau or not mat_khau.strip():
        raise LoiTaiKhoan("Mật khẩu không được bắt đầu hay kết thúc bằng khoảng trắng.")


def chuan_hoa_email(email: str) -> str:
    email = (email or "").strip().lower()
    if len(email) > 254 or not _MAU_EMAIL.match(email):
        raise LoiTaiKhoan("Email không hợp lệ.")
    return email


# ------------------------------------------------------------
# GIỚI HẠN SỐ LẦN THỬ
# ------------------------------------------------------------
def _con_trong_han(danh_sach: list[float], giay: float) -> list[float]:
    moc = time.time() - giay
    return [t for t in danh_sach if t > moc]


def _kiem_tra_bi_khoa(*khoa: str) -> None:
    with _khoa_dem:
        for k in khoa:
            _lan_sai[k] = _con_trong_han(_lan_sai.get(k, []), GIAY_KHOA)
            if len(_lan_sai[k]) >= SO_LAN_SAI_TOI_DA:
                raise LoiTaiKhoan(
                    "Đăng nhập sai quá nhiều lần. Hãy thử lại sau 15 phút.", 429
                )


def _ghi_lan_sai(*khoa: str) -> None:
    with _khoa_dem:
        for k in khoa:
            _lan_sai.setdefault(k, []).append(time.time())


# ------------------------------------------------------------
# TÀI KHOẢN
# ------------------------------------------------------------
def _cong_khai(dong: sqlite3.Row) -> dict:
    return {
        "id": dong["id"],
        "email": dong["email"],
        "ten": dong["ten"],
        "quan_tri": bool(dong["quan_tri"]) or dong["email"] in email_quan_tri(),
    }


def dang_ky(email: str, mat_khau: str, ten: str = "", ip: str = "") -> dict:
    email = chuan_hoa_email(email)
    _kiem_tra_mat_khau_moi(mat_khau)
    ten = " ".join((ten or "").split())[:60] or email.split("@")[0]
    if ip:
        with _khoa_dem:
            lan = _con_trong_han(_lan_dang_ky.get(ip, []), 3600)
            if len(lan) >= SO_DANG_KY_MOI_GIO:
                raise LoiTaiKhoan("Đăng ký quá nhiều tài khoản từ một máy. Thử lại sau.", 429)
            _lan_dang_ky[ip] = lan + [time.time()]
    da_bam = bam_mat_khau(mat_khau)
    with _khoa_ghi:
        conn = _connect()
        if conn.execute("SELECT 1 FROM nguoi_dung WHERE email = ?", (email,)).fetchone():
            raise LoiTaiKhoan("Email này đã có tài khoản. Hãy đăng nhập.", 409)
        chi_dinh = email_quan_tri()
        if chi_dinh:
            quan_tri = email in chi_dinh
        else:
            quan_tri = conn.execute("SELECT COUNT(*) FROM nguoi_dung").fetchone()[0] == 0
        ma = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO nguoi_dung (id, email, ten, mat_khau_bam, quan_tri, tao_luc)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (ma, email, ten, da_bam, int(quan_tri), time.time()),
        )
        conn.commit()
        return _cong_khai(conn.execute("SELECT * FROM nguoi_dung WHERE id = ?", (ma,)).fetchone())


def dang_nhap(email: str, mat_khau: str, ip: str = "") -> dict:
    email_goc = (email or "").strip().lower()
    khoa = [f"email:{email_goc}"] + ([f"ip:{ip}"] if ip else [])
    _kiem_tra_bi_khoa(*khoa)
    dong = _connect().execute(
        "SELECT * FROM nguoi_dung WHERE email = ?", (email_goc,)
    ).fetchone()
    if not dung_mat_khau(mat_khau or "", dong["mat_khau_bam"] if dong else _BAM_GIA) or not dong:
        _ghi_lan_sai(*khoa)
        raise LoiTaiKhoan("Email hoặc mật khẩu không đúng.", 401)
    with _khoa_ghi:
        conn = _connect()
        conn.execute("UPDATE nguoi_dung SET dang_nhap_luc = ? WHERE id = ?", (time.time(), dong["id"]))
        conn.commit()
    return _cong_khai(dong)


def _bam_phien(ma_phien: str) -> str:
    return hashlib.sha256(ma_phien.encode("utf-8")).hexdigest()


def tao_phien(nguoi_dung_id: str) -> str:
    ma_phien = secrets.token_urlsafe(32)
    bay_gio = time.time()
    with _khoa_ghi:
        conn = _connect()
        # Dọn phiên hết hạn nhân tiện, khỏi cần tiến trình dọn riêng.
        conn.execute("DELETE FROM phien WHERE het_han < ?", (bay_gio,))
        conn.execute(
            "INSERT INTO phien (ma_bam, nguoi_dung_id, tao_luc, het_han) VALUES (?, ?, ?, ?)",
            (_bam_phien(ma_phien), nguoi_dung_id, bay_gio, bay_gio + GIAY_PHIEN),
        )
        conn.commit()
    return ma_phien


def nguoi_dung_theo_phien(ma_phien: str | None) -> dict | None:
    if not ma_phien or len(ma_phien) > 200:
        return None
    try:
        dong = _connect().execute(
            "SELECT n.* FROM phien p JOIN nguoi_dung n ON n.id = p.nguoi_dung_id"
            " WHERE p.ma_bam = ? AND p.het_han > ?",
            (_bam_phien(ma_phien), time.time()),
        ).fetchone()
    except sqlite3.Error:
        return None
    return _cong_khai(dong) if dong else None


def xoa_phien(ma_phien: str | None) -> None:
    if not ma_phien:
        return
    with _khoa_ghi:
        conn = _connect()
        conn.execute("DELETE FROM phien WHERE ma_bam = ?", (_bam_phien(ma_phien),))
        conn.commit()


def doi_mat_khau(nguoi_dung_id: str, mat_khau_cu: str, mat_khau_moi: str, giu_phien: str | None = None) -> None:
    dong = _connect().execute("SELECT * FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,)).fetchone()
    if dong is None:
        raise LoiTaiKhoan("Tài khoản không còn tồn tại.", 404)
    if not dung_mat_khau(mat_khau_cu or "", dong["mat_khau_bam"]):
        raise LoiTaiKhoan("Mật khẩu hiện tại không đúng.", 401)
    _kiem_tra_mat_khau_moi(mat_khau_moi)
    _dat_mat_khau(nguoi_dung_id, mat_khau_moi, giu_phien)


def _dat_mat_khau(nguoi_dung_id: str, mat_khau_moi: str, giu_phien: str | None = None) -> None:
    """Đổi mật khẩu thì đăng xuất mọi nơi khác: lộ mật khẩu cũ mới là lý do đổi."""
    with _khoa_ghi:
        conn = _connect()
        conn.execute(
            "UPDATE nguoi_dung SET mat_khau_bam = ? WHERE id = ?",
            (bam_mat_khau(mat_khau_moi), nguoi_dung_id),
        )
        conn.execute(
            "DELETE FROM phien WHERE nguoi_dung_id = ? AND ma_bam != ?",
            (nguoi_dung_id, _bam_phien(giu_phien) if giu_phien else ""),
        )
        conn.commit()


# ------------------------------------------------------------
# SỔ TAY THEO TÀI KHOẢN
# ------------------------------------------------------------
def lay_so_tay(nguoi_dung_id: str, hoi_thoai_id: str) -> dict | None:
    dong = _connect().execute(
        "SELECT du_lieu FROM so_tay WHERE nguoi_dung_id = ? AND hoi_thoai_id = ?",
        (nguoi_dung_id, hoi_thoai_id),
    ).fetchone()
    if dong is None:
        return None
    try:
        return json.loads(dong["du_lieu"])
    except ValueError:
        return None


def ghi_so_tay(nguoi_dung_id: str, hoi_thoai_id: str, ban: dict) -> None:
    du_lieu = json.dumps(ban, ensure_ascii=False)
    if len(du_lieu.encode("utf-8")) > SO_TAY_TOI_DA_BYTE:
        raise LoiTaiKhoan("Sổ tay quá lớn (nhiều ảnh). Hãy tải về rồi xoá bớt ảnh.", 413)
    with _khoa_ghi:
        conn = _connect()
        conn.execute(
            "INSERT INTO so_tay (nguoi_dung_id, hoi_thoai_id, du_lieu, cap_nhat_luc)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(nguoi_dung_id, hoi_thoai_id)"
            " DO UPDATE SET du_lieu = excluded.du_lieu, cap_nhat_luc = excluded.cap_nhat_luc",
            (nguoi_dung_id, hoi_thoai_id, du_lieu, time.time()),
        )
        conn.commit()


def xoa_so_tay(nguoi_dung_id: str, hoi_thoai_id: str | None = None) -> int:
    with _khoa_ghi:
        conn = _connect()
        if hoi_thoai_id is None:
            cur = conn.execute("DELETE FROM so_tay WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
        else:
            cur = conn.execute(
                "DELETE FROM so_tay WHERE nguoi_dung_id = ? AND hoi_thoai_id = ?",
                (nguoi_dung_id, hoi_thoai_id),
            )
        conn.commit()
        return cur.rowcount


# ------------------------------------------------------------
# DÒNG LỆNH CHO QUẢN TRỊ VIÊN
# ------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quản lý tài khoản chatbot.")
    lenh = parser.add_subparsers(dest="lenh", required=True)
    lenh.add_parser("danh-sach", help="Liệt kê tài khoản")
    dat_lai = lenh.add_parser("dat-lai-mat-khau", help="Đặt mật khẩu mới cho người quên mật khẩu")
    dat_lai.add_argument("email")
    cap = lenh.add_parser("quan-tri", help="Cấp (hoặc --bo để thu) quyền quản trị")
    cap.add_argument("email")
    cap.add_argument("--bo", action="store_true")
    tham_so = parser.parse_args(argv)

    conn = _connect()
    if tham_so.lenh == "danh-sach":
        for dong in conn.execute("SELECT * FROM nguoi_dung ORDER BY tao_luc"):
            nd = _cong_khai(dong)
            print(f"{nd['email']:<40} {nd['ten']:<24} {'quản trị' if nd['quan_tri'] else ''}")
        return 0

    email = chuan_hoa_email(tham_so.email)
    dong = conn.execute("SELECT * FROM nguoi_dung WHERE email = ?", (email,)).fetchone()
    if dong is None:
        print(f"Không có tài khoản {email}.")
        return 1
    if tham_so.lenh == "dat-lai-mat-khau":
        moi = getpass.getpass("Mật khẩu mới: ")
        _kiem_tra_mat_khau_moi(moi)
        if getpass.getpass("Nhập lại: ") != moi:
            print("Hai lần nhập không khớp.")
            return 1
        _dat_mat_khau(dong["id"], moi)
        print(f"Đã đặt lại mật khẩu cho {email} và đăng xuất mọi phiên cũ.")
    else:
        with _khoa_ghi:
            conn.execute("UPDATE nguoi_dung SET quan_tri = ? WHERE id = ?", (int(not tham_so.bo), dong["id"]))
            conn.commit()
        print(f"{'Đã thu' if tham_so.bo else 'Đã cấp'} quyền quản trị: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
