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

Xác minh email: gửi mã 6 số qua thư (gui_thu.py, cần cấu hình SMTP). Chưa xác
minh vẫn dùng bình thường, chỉ là email chỉ định trong RAG_EMAIL_QUAN_TRI chưa
thành quản trị viên - kẻ lạ đăng ký trước bằng email của quản trị viên không
chiếm được quyền. Máy chủ chưa cấu hình thư thì bỏ qua điều kiện này (không có
cách nào xác minh), giữ đúng hành vi cũ.

Quản trị viên xem mọi tài khoản, khoá hoặc xoá tài khoản ngay trên giao diện
(menu tài khoản > Quản lý tài khoản). Tài khoản quản trị thì không khoá/xoá ở
đó được, phải thu quyền bằng dòng lệnh trước.

Quên mật khẩu: quản trị viên đặt lại bằng dòng lệnh
    python tai_khoan.py dat-lai-mat-khau email@truong.edu.vn
    python tai_khoan.py quan-tri email@truong.edu.vn        # cấp quyền quản trị
    python tai_khoan.py xac-minh email@truong.edu.vn        # xác minh hộ
    python tai_khoan.py danh-sach
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid

import gui_thu

DUONG_DAN_DB = os.path.abspath(os.getenv(
    "RAG_TAI_KHOAN_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tai_khoan.db"),
))
TEN_COOKIE = "rag_phien"
GIAY_PHIEN = 30 * 86400
MAT_KHAU_TOI_THIEU = 8
MAT_KHAU_TOI_DA = 200
SO_TAY_TOI_DA_BYTE = 8 * 1024 * 1024  # sổ có ảnh vùng khoanh, vài MB là cùng

# Mã xác minh email: 6 chữ số, sống 15 phút, sai 5 lần là huỷ - dò hết 10^6 mã
# thì phải xin mã mới 200.000 lần, mà mỗi giờ chỉ được xin vài lần.
PHUT_MA_XAC_MINH = 15
SO_LAN_NHAP_SAI_MA = 5
GIAY_GIUA_HAI_LAN_GUI = 60
SO_LAN_GUI_MOI_GIO = 5

# Ảnh đại diện: nhận ảnh gốc tới 8 MB, cắt vuông và nén lại còn vài chục KB.
ANH_TOI_DA_BYTE = 8 * 1024 * 1024
ANH_TOI_DA_DIEM = 40_000_000  # chặn "bom giải nén": tệp nhỏ nhưng khai 100k x 100k điểm
CANH_ANH = 256

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
_lan_gui_ma: dict[str, list[float]] = {}

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
            CREATE TABLE IF NOT EXISTS ma_xac_minh (
                nguoi_dung_id TEXT PRIMARY KEY,
                ma_bam        TEXT NOT NULL,
                het_han       REAL NOT NULL,
                so_lan_sai    INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS anh_dai_dien (
                nguoi_dung_id TEXT PRIMARY KEY,
                kieu          TEXT NOT NULL,
                du_lieu       BLOB NOT NULL
            );
            """
        )
        # Cơ sở dữ liệu tạo trước khi có xác minh email và ảnh đại diện.
        cot = {d["name"] for d in _ket_noi.execute("PRAGMA table_info(nguoi_dung)")}
        if "da_xac_minh" not in cot:
            _ket_noi.execute("ALTER TABLE nguoi_dung ADD COLUMN da_xac_minh INTEGER NOT NULL DEFAULT 0")
        if "anh_cap_nhat" not in cot:
            _ket_noi.execute("ALTER TABLE nguoi_dung ADD COLUMN anh_cap_nhat REAL")
        if "bi_cam" not in cot:
            _ket_noi.execute("ALTER TABLE nguoi_dung ADD COLUMN bi_cam INTEGER NOT NULL DEFAULT 0")
            _ket_noi.execute("ALTER TABLE nguoi_dung ADD COLUMN cam_luc REAL")
            _ket_noi.execute("ALTER TABLE nguoi_dung ADD COLUMN cam_boi TEXT")
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
        _lan_gui_ma.clear()


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
    da_xac_minh = bool(dong["da_xac_minh"])
    # Email chỉ định chỉ thành quản trị khi chủ email đã chứng minh mình giữ hộp
    # thư. Máy chủ không gửi được thư thì không ai xác minh nổi: bỏ điều kiện.
    theo_chi_dinh = dong["email"] in email_quan_tri() and (
        da_xac_minh or not gui_thu.da_cau_hinh()
    )
    return {
        "id": dong["id"],
        "email": dong["email"],
        "ten": dong["ten"],
        "quan_tri": bool(dong["quan_tri"]) or theo_chi_dinh,
        "da_xac_minh": da_xac_minh,
        "anh": (
            f"/api/tai-khoan/anh-dai-dien/{dong['id']}?v={int(dong['anh_cap_nhat'] * 1000)}"
            if dong["anh_cap_nhat"] else None
        ),
    }


def lay_nguoi_dung(nguoi_dung_id: str) -> dict | None:
    dong = _connect().execute("SELECT * FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,)).fetchone()
    return _cong_khai(dong) if dong else None


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
            # Cột quan_tri để 0: quyền theo email chỉ định tính lúc đọc, sau khi xác minh.
            quan_tri = False
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
    # Báo khoá sau khi đúng mật khẩu: người dò mật khẩu không biết tài khoản bị khoá.
    if dong["bi_cam"]:
        raise LoiTaiKhoan("Tài khoản này đã bị khoá. Hãy liên hệ quản trị viên.", 403)
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
            " WHERE p.ma_bam = ? AND p.het_han > ? AND n.bi_cam = 0",
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


def doi_thong_tin(nguoi_dung_id: str, ten: str | None = None, email: str | None = None,
                  mat_khau: str = "") -> dict:
    """Sửa tên hiển thị và/hoặc email của chính mình.

    Đổi tên thì không cần gì thêm. Đổi email phải nhập đúng mật khẩu (người
    mượn máy đang đăng nhập sẵn không chiếm được tài khoản bằng cách đổi email
    sang hộp thư của họ) và email mới phải xác minh lại từ đầu - quyền quản trị
    theo RAG_EMAIL_QUAN_TRI cũng chỉ có lại sau khi xác minh.
    """
    dong = _connect().execute("SELECT * FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,)).fetchone()
    if dong is None:
        raise LoiTaiKhoan("Tài khoản không còn tồn tại.", 404)
    ten_moi = dong["ten"]
    if ten is not None:
        ten_moi = " ".join(ten.split())[:60]
        if not ten_moi:
            raise LoiTaiKhoan("Tên hiển thị không được để trống.")
    email_moi = dong["email"]
    if email is not None and chuan_hoa_email(email) != dong["email"]:
        email_moi = chuan_hoa_email(email)
        if not dung_mat_khau(mat_khau or "", dong["mat_khau_bam"]):
            raise LoiTaiKhoan("Mật khẩu không đúng. Đổi email cần nhập mật khẩu hiện tại.", 401)
    with _khoa_ghi:
        conn = _connect()
        if email_moi != dong["email"]:
            if conn.execute("SELECT 1 FROM nguoi_dung WHERE email = ? AND id != ?",
                            (email_moi, nguoi_dung_id)).fetchone():
                raise LoiTaiKhoan("Email này đã có tài khoản khác dùng.", 409)
            conn.execute(
                "UPDATE nguoi_dung SET email = ?, da_xac_minh = 0 WHERE id = ?",
                (email_moi, nguoi_dung_id),
            )
            # Mã đã gửi tới email cũ không được dùng để xác minh email mới.
            conn.execute("DELETE FROM ma_xac_minh WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
        conn.execute("UPDATE nguoi_dung SET ten = ? WHERE id = ?", (ten_moi, nguoi_dung_id))
        conn.commit()
    # Giới hạn gửi mã theo tài khoản vẫn giữ nguyên: nếu đổi email là được gửi
    # lại ngay thì đổi qua đổi lại sẽ biến máy chủ thành công cụ gửi thư rác.
    return lay_nguoi_dung(nguoi_dung_id)


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
# XÁC MINH EMAIL
# ------------------------------------------------------------
def _bam_ma(nguoi_dung_id: str, ma: str) -> str:
    return hashlib.sha256(f"{nguoi_dung_id}:{ma}".encode("utf-8")).hexdigest()


def tao_ma_xac_minh(nguoi_dung_id: str) -> tuple[dict, str]:
    """Sinh mã mới (thay mã cũ). Trả về (người dùng, mã) để bên gọi gửi thư."""
    dong = _connect().execute("SELECT * FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,)).fetchone()
    if dong is None:
        raise LoiTaiKhoan("Tài khoản không còn tồn tại.", 404)
    if dong["da_xac_minh"]:
        raise LoiTaiKhoan("Email này đã được xác minh.", 409)
    bay_gio = time.time()
    with _khoa_dem:
        lan = _con_trong_han(_lan_gui_ma.get(nguoi_dung_id, []), 3600)
        if lan and bay_gio - lan[-1] < GIAY_GIUA_HAI_LAN_GUI:
            con = int(GIAY_GIUA_HAI_LAN_GUI - (bay_gio - lan[-1])) + 1
            raise LoiTaiKhoan(f"Hãy đợi {con} giây rồi gửi lại mã.", 429)
        if len(lan) >= SO_LAN_GUI_MOI_GIO:
            raise LoiTaiKhoan("Đã gửi mã quá nhiều lần. Hãy thử lại sau một giờ.", 429)
        _lan_gui_ma[nguoi_dung_id] = lan + [bay_gio]
    ma = f"{secrets.randbelow(1_000_000):06d}"
    with _khoa_ghi:
        conn = _connect()
        conn.execute(
            "INSERT INTO ma_xac_minh (nguoi_dung_id, ma_bam, het_han, so_lan_sai) VALUES (?, ?, ?, 0)"
            " ON CONFLICT(nguoi_dung_id) DO UPDATE SET ma_bam = excluded.ma_bam,"
            " het_han = excluded.het_han, so_lan_sai = 0",
            (nguoi_dung_id, _bam_ma(nguoi_dung_id, ma), bay_gio + PHUT_MA_XAC_MINH * 60),
        )
        conn.commit()
    return _cong_khai(dong), ma


def huy_lan_gui_ma(nguoi_dung_id: str) -> None:
    """Thư không đi được thì không tính lượt, để người dùng bấm gửi lại ngay."""
    with _khoa_dem:
        if _lan_gui_ma.get(nguoi_dung_id):
            _lan_gui_ma[nguoi_dung_id].pop()


def xac_minh(nguoi_dung_id: str, ma: str) -> dict:
    ma = "".join(ch for ch in (ma or "") if ch.isdigit())
    with _khoa_ghi:
        conn = _connect()
        dong = conn.execute(
            "SELECT * FROM ma_xac_minh WHERE nguoi_dung_id = ?", (nguoi_dung_id,)
        ).fetchone()
        if dong is None or dong["het_han"] < time.time():
            conn.execute("DELETE FROM ma_xac_minh WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
            conn.commit()
            raise LoiTaiKhoan("Mã đã hết hạn hoặc chưa được gửi. Hãy bấm gửi mã mới.", 410)
        if len(ma) != 6 or not hmac.compare_digest(_bam_ma(nguoi_dung_id, ma), dong["ma_bam"]):
            sai = dong["so_lan_sai"] + 1
            if sai >= SO_LAN_NHAP_SAI_MA:
                conn.execute("DELETE FROM ma_xac_minh WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
                conn.commit()
                raise LoiTaiKhoan("Nhập sai quá nhiều lần, mã đã bị huỷ. Hãy gửi mã mới.", 429)
            conn.execute(
                "UPDATE ma_xac_minh SET so_lan_sai = ? WHERE nguoi_dung_id = ?", (sai, nguoi_dung_id)
            )
            conn.commit()
            raise LoiTaiKhoan(f"Mã không đúng. Còn {SO_LAN_NHAP_SAI_MA - sai} lần thử.", 400)
        conn.execute("UPDATE nguoi_dung SET da_xac_minh = 1 WHERE id = ?", (nguoi_dung_id,))
        conn.execute("DELETE FROM ma_xac_minh WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
        conn.commit()
    with _khoa_dem:
        _lan_gui_ma.pop(nguoi_dung_id, None)
    return lay_nguoi_dung(nguoi_dung_id)


# ------------------------------------------------------------
# ẢNH ĐẠI DIỆN
# ------------------------------------------------------------
def _chuan_hoa_anh(du_lieu: bytes) -> bytes:
    """Mở ảnh bằng Pillow, cắt vuông giữa ảnh, thu về 256x256 WebP.

    Nén lại từ điểm ảnh chứ không lưu nguyên tệp: bỏ EXIF (toạ độ GPS của ảnh
    chụp điện thoại), và tệp giả dạng ảnh (HTML, SVG có script) không lọt qua.
    """
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(du_lieu)) as goc:
            if goc.format not in {"JPEG", "PNG", "WEBP", "GIF", "BMP"}:
                raise LoiTaiKhoan("Chỉ nhận ảnh JPG, PNG, WebP, GIF hoặc BMP.", 415)
            if goc.width * goc.height > ANH_TOI_DA_DIEM:
                raise LoiTaiKhoan("Ảnh quá lớn, hãy chọn ảnh nhỏ hơn.", 413)
            goc.seek(0)  # GIF động: lấy khung đầu
            anh = ImageOps.exif_transpose(goc)
            trong_suot = "A" in anh.getbands() or "transparency" in anh.info
            anh = anh.convert("RGBA" if trong_suot else "RGB")
            anh = ImageOps.fit(anh, (CANH_ANH, CANH_ANH), Image.Resampling.LANCZOS)
            ra = io.BytesIO()
            anh.save(ra, "WEBP", quality=86, method=4)
            return ra.getvalue()
    except LoiTaiKhoan:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError) as exc:
        raise LoiTaiKhoan("Tệp không phải ảnh hoặc ảnh bị hỏng.", 415) from exc


def luu_anh_dai_dien(nguoi_dung_id: str, du_lieu: bytes) -> dict:
    if not du_lieu:
        raise LoiTaiKhoan("Chưa có ảnh.", 400)
    if len(du_lieu) > ANH_TOI_DA_BYTE:
        raise LoiTaiKhoan("Ảnh quá lớn (tối đa 8 MB).", 413)
    anh = _chuan_hoa_anh(du_lieu)
    with _khoa_ghi:
        conn = _connect()
        conn.execute(
            "INSERT INTO anh_dai_dien (nguoi_dung_id, kieu, du_lieu) VALUES (?, 'image/webp', ?)"
            " ON CONFLICT(nguoi_dung_id) DO UPDATE SET kieu = excluded.kieu, du_lieu = excluded.du_lieu",
            (nguoi_dung_id, anh),
        )
        conn.execute("UPDATE nguoi_dung SET anh_cap_nhat = ? WHERE id = ?", (time.time(), nguoi_dung_id))
        conn.commit()
    return lay_nguoi_dung(nguoi_dung_id)


def lay_anh_dai_dien(nguoi_dung_id: str) -> tuple[bytes, str] | None:
    dong = _connect().execute(
        "SELECT kieu, du_lieu FROM anh_dai_dien WHERE nguoi_dung_id = ?", (nguoi_dung_id,)
    ).fetchone()
    return (bytes(dong["du_lieu"]), dong["kieu"]) if dong else None


def xoa_anh_dai_dien(nguoi_dung_id: str) -> dict:
    with _khoa_ghi:
        conn = _connect()
        conn.execute("DELETE FROM anh_dai_dien WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
        conn.execute("UPDATE nguoi_dung SET anh_cap_nhat = NULL WHERE id = ?", (nguoi_dung_id,))
        conn.commit()
    return lay_nguoi_dung(nguoi_dung_id)


# ------------------------------------------------------------
# QUẢN TRỊ TÀI KHOẢN (xem, khoá, xoá)
# ------------------------------------------------------------
def _cho_quan_tri(dong: sqlite3.Row) -> dict:
    nd = _cong_khai(dong)
    nd.pop("anh")  # ảnh chỉ chính chủ tải được, quản trị viên thấy chữ cái đầu
    nd.update(
        tao_luc=dong["tao_luc"],
        dang_nhap_luc=dong["dang_nhap_luc"],
        bi_cam=bool(dong["bi_cam"]),
        cam_luc=dong["cam_luc"],
        cam_boi=dong["cam_boi"],
    )
    return nd


def danh_sach_tai_khoan() -> list[dict]:
    return [
        _cho_quan_tri(dong)
        for dong in _connect().execute("SELECT * FROM nguoi_dung ORDER BY tao_luc DESC")
    ]


def _tai_khoan_de_xu_ly(nguoi_dung_id: str, nguoi_lam: dict) -> sqlite3.Row:
    """Không tự khoá/xoá mình, không đụng tới quản trị viên khác.

    Quản trị viên mà khoá được nhau thì một tài khoản quản trị bị lộ là khoá
    sạch những người còn lại; muốn gỡ thì thu quyền bằng dòng lệnh trên máy chủ.
    """
    dong = _connect().execute("SELECT * FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,)).fetchone()
    if dong is None:
        raise LoiTaiKhoan("Tài khoản không còn tồn tại.", 404)
    if dong["id"] == nguoi_lam.get("id"):
        raise LoiTaiKhoan("Không thể khoá hay xoá tài khoản của chính mình.", 409)
    if _cong_khai(dong)["quan_tri"]:
        raise LoiTaiKhoan(
            "Đây là tài khoản quản trị. Hãy thu quyền quản trị trên máy chủ trước"
            f" (python tai_khoan.py quan-tri {dong['email']} --bo).",
            409,
        )
    return dong


def dat_cam(nguoi_dung_id: str, cam: bool, nguoi_lam: dict) -> dict:
    """Khoá: đăng xuất mọi nơi và không đăng nhập lại được; dữ liệu giữ nguyên."""
    if cam:
        _tai_khoan_de_xu_ly(nguoi_dung_id, nguoi_lam)
    with _khoa_ghi:
        conn = _connect()
        cur = conn.execute(
            "UPDATE nguoi_dung SET bi_cam = ?, cam_luc = ?, cam_boi = ? WHERE id = ?",
            (int(cam), time.time() if cam else None, nguoi_lam.get("ten") if cam else None, nguoi_dung_id),
        )
        if cur.rowcount == 0:
            raise LoiTaiKhoan("Tài khoản không còn tồn tại.", 404)
        if cam:
            conn.execute("DELETE FROM phien WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
        conn.commit()
        return _cho_quan_tri(conn.execute("SELECT * FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,)).fetchone())


def xoa_tai_khoan(nguoi_dung_id: str, nguoi_lam: dict) -> str:
    """Xoá hẳn tài khoản cùng phiên, sổ tay, ảnh; trả về email vừa xoá.

    Lịch sử trò chuyện nằm ở lich_su_chat.db, bên gọi xoá tiếp theo "nd:<id>".
    Email được giải phóng nên chủ của nó đăng ký lại được - chặn hẳn thì khoá.
    """
    dong = _tai_khoan_de_xu_ly(nguoi_dung_id, nguoi_lam)
    with _khoa_ghi:
        conn = _connect()
        for bang in ("phien", "so_tay", "ma_xac_minh", "anh_dai_dien"):
            conn.execute(f"DELETE FROM {bang} WHERE nguoi_dung_id = ?", (nguoi_dung_id,))
        conn.execute("DELETE FROM nguoi_dung WHERE id = ?", (nguoi_dung_id,))
        conn.commit()
    with _khoa_dem:
        _lan_gui_ma.pop(nguoi_dung_id, None)
    return dong["email"]


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
    xm = lenh.add_parser("xac-minh", help="Đánh dấu email đã xác minh (không cần mã)")
    xm.add_argument("email")
    tham_so = parser.parse_args(argv)

    conn = _connect()
    if tham_so.lenh == "danh-sach":
        for dong in conn.execute("SELECT * FROM nguoi_dung ORDER BY tao_luc"):
            nd = _cong_khai(dong)
            nhan = (["quản trị"] * nd["quan_tri"] + ["chưa xác minh"] * (not nd["da_xac_minh"])
                    + ["bị khoá"] * bool(dong["bi_cam"]))
            print(f"{nd['email']:<40} {nd['ten']:<24} {', '.join(nhan)}")
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
    elif tham_so.lenh == "xac-minh":
        with _khoa_ghi:
            conn.execute("UPDATE nguoi_dung SET da_xac_minh = 1 WHERE id = ?", (dong["id"],))
            conn.execute("DELETE FROM ma_xac_minh WHERE nguoi_dung_id = ?", (dong["id"],))
            conn.commit()
        print(f"Đã xác minh email {email}.")
    else:
        with _khoa_ghi:
            conn.execute("UPDATE nguoi_dung SET quan_tri = ? WHERE id = ?", (int(not tham_so.bo), dong["id"]))
            conn.commit()
        print(f"{'Đã thu' if tham_so.bo else 'Đã cấp'} quyền quản trị: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
