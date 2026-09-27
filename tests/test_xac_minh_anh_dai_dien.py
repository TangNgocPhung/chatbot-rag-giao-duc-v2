"""Xác minh email bằng mã gửi qua thư, và ảnh đại diện của tài khoản."""

import io
import sqlite3
import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import gui_thu
import tai_khoan
from api import app

MAT_KHAU = "matkhau-rat-dai-1"


@pytest.fixture(autouse=True)
def co_so_du_lieu_moi(tmp_path, monkeypatch):
    monkeypatch.setattr(tai_khoan, "DUONG_DAN_DB", str(tmp_path / "tai_khoan.db"))
    for bien in ("RAG_EMAIL_QUAN_TRI", "RAG_SMTP_TAI_KHOAN", "RAG_SMTP_MAT_KHAU"):
        monkeypatch.delenv(bien, raising=False)
    tai_khoan.dong_ket_noi()
    yield
    tai_khoan.dong_ket_noi()


CO_THU = {"RAG_SMTP_TAI_KHOAN": "hopthu@gmail.com", "RAG_SMTP_MAT_KHAU": "abcd efgh ijkl mnop"}


def anh_mau(kieu="PNG", co=(640, 480)) -> bytes:
    ra = io.BytesIO()
    Image.new("RGB", co, (40, 90, 160)).save(ra, kieu)
    return ra.getvalue()


class XacMinhTests(unittest.TestCase):
    def setUp(self):
        self.nd = tai_khoan.dang_ky("a@x.vn", MAT_KHAU, "Cô A")

    def test_ma_dung_thi_xac_minh(self):
        self.assertFalse(self.nd["da_xac_minh"])
        _, ma = tai_khoan.tao_ma_xac_minh(self.nd["id"])
        self.assertRegex(ma, r"^\d{6}$")
        nd = tai_khoan.xac_minh(self.nd["id"], ma[:3] + " " + ma[3:])  # dán kèm dấu cách vẫn nhận
        self.assertTrue(nd["da_xac_minh"])
        # Mã chỉ dùng được một lần, và đã xác minh thì không xin mã nữa.
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.xac_minh(self.nd["id"], ma)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.tao_ma_xac_minh(self.nd["id"])
        self.assertEqual(loi.exception.ma_http, 409)

    def test_sai_nhieu_lan_thi_huy_ma(self):
        _, ma = tai_khoan.tao_ma_xac_minh(self.nd["id"])
        sai = "000000" if ma != "000000" else "111111"
        for _ in range(tai_khoan.SO_LAN_NHAP_SAI_MA - 1):
            with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
                tai_khoan.xac_minh(self.nd["id"], sai)
            self.assertEqual(loi.exception.ma_http, 400)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.xac_minh(self.nd["id"], sai)
        self.assertEqual(loi.exception.ma_http, 429)
        # Mã đúng cũng hết giá trị sau khi bị huỷ.
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.xac_minh(self.nd["id"], ma)

    def test_ma_het_han(self):
        _, ma = tai_khoan.tao_ma_xac_minh(self.nd["id"])
        with patch("tai_khoan.time.time", return_value=tai_khoan.time.time() + 16 * 60):
            with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
                tai_khoan.xac_minh(self.nd["id"], ma)
        self.assertEqual(loi.exception.ma_http, 410)

    def test_gioi_han_gui_ma(self):
        tai_khoan.tao_ma_xac_minh(self.nd["id"])
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.tao_ma_xac_minh(self.nd["id"])
        self.assertEqual(loi.exception.ma_http, 429)
        self.assertIn("giây", str(loi.exception))
        # Thư không đi được thì trả lại lượt: gửi lại ngay được.
        tai_khoan.huy_lan_gui_ma(self.nd["id"])
        tai_khoan.huy_lan_gui_ma(self.nd["id"])
        tai_khoan.tao_ma_xac_minh(self.nd["id"])

    def test_email_chi_dinh_chi_la_quan_tri_sau_khi_xac_minh(self):
        with patch.dict("os.environ", {"RAG_EMAIL_QUAN_TRI": "admin@x.vn", **CO_THU}):
            # Kẻ lạ đăng ký trước bằng email của quản trị viên: chưa có quyền gì.
            nd = tai_khoan.dang_ky("admin@x.vn", MAT_KHAU)
            self.assertFalse(nd["quan_tri"])
            _, ma = tai_khoan.tao_ma_xac_minh(nd["id"])
            self.assertTrue(tai_khoan.xac_minh(nd["id"], ma)["quan_tri"])
        # Máy chủ không gửi được thư: không ai xác minh nổi, giữ hành vi cũ.
        khac = tai_khoan.dang_ky("b@x.vn", MAT_KHAU)
        with patch.dict("os.environ", {"RAG_EMAIL_QUAN_TRI": "b@x.vn"}):
            self.assertTrue(tai_khoan.lay_nguoi_dung(khac["id"])["quan_tri"])

    def test_nang_cap_co_so_du_lieu_cu(self):
        tai_khoan.dong_ket_noi()
        conn = sqlite3.connect(tai_khoan.DUONG_DAN_DB)
        conn.executescript(
            "DROP TABLE nguoi_dung;"
            "CREATE TABLE nguoi_dung (id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, ten TEXT NOT NULL,"
            " mat_khau_bam TEXT NOT NULL, quan_tri INTEGER NOT NULL DEFAULT 0, tao_luc REAL NOT NULL,"
            " dang_nhap_luc REAL);"
        )
        conn.execute(
            "INSERT INTO nguoi_dung (id, email, ten, mat_khau_bam, quan_tri, tao_luc) VALUES (?, ?, ?, ?, 1, 0)",
            ("cu", "cu@x.vn", "Cũ", tai_khoan.bam_mat_khau(MAT_KHAU)),
        )
        conn.commit()
        conn.close()
        nd = tai_khoan.dang_nhap("cu@x.vn", MAT_KHAU)
        self.assertFalse(nd["da_xac_minh"])
        self.assertIsNone(nd["anh"])
        self.assertTrue(nd["quan_tri"])

    def test_dong_lenh_xac_minh_ho(self):
        self.assertEqual(tai_khoan.main(["xac-minh", "a@x.vn"]), 0)
        self.assertTrue(tai_khoan.lay_nguoi_dung(self.nd["id"])["da_xac_minh"])


class AnhDaiDienTests(unittest.TestCase):
    def setUp(self):
        self.nd = tai_khoan.dang_ky("a@x.vn", MAT_KHAU)

    def test_cat_vuong_va_nen_webp(self):
        nd = tai_khoan.luu_anh_dai_dien(self.nd["id"], anh_mau("JPEG", (1200, 800)))
        self.assertTrue(nd["anh"].startswith(f"/api/tai-khoan/anh-dai-dien/{self.nd['id']}?v="))
        du_lieu, kieu = tai_khoan.lay_anh_dai_dien(self.nd["id"])
        self.assertEqual(kieu, "image/webp")
        with Image.open(io.BytesIO(du_lieu)) as anh:
            self.assertEqual((anh.format, anh.size), ("WEBP", (256, 256)))
        self.assertIsNone(tai_khoan.xoa_anh_dai_dien(self.nd["id"])["anh"])
        self.assertIsNone(tai_khoan.lay_anh_dai_dien(self.nd["id"]))

    def test_tu_choi_tep_khong_phai_anh(self):
        for du_lieu in (b"<svg onload=alert(1)></svg>", b"<html>xin chao</html>", b""):
            with self.assertRaises(tai_khoan.LoiTaiKhoan):
                tai_khoan.luu_anh_dai_dien(self.nd["id"], du_lieu)
        self.assertIsNone(tai_khoan.lay_nguoi_dung(self.nd["id"])["anh"])

    def test_bo_exif(self):
        ra = io.BytesIO()
        exif = Image.Exif()
        exif[0x010F] = "Hang may anh"
        Image.new("RGB", (300, 300), "red").save(ra, "JPEG", exif=exif)
        tai_khoan.luu_anh_dai_dien(self.nd["id"], ra.getvalue())
        du_lieu, _ = tai_khoan.lay_anh_dai_dien(self.nd["id"])
        with Image.open(io.BytesIO(du_lieu)) as anh:
            self.assertEqual(dict(anh.getexif()), {})


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.client.post("/api/tai-khoan/dang-ky", json={"email": "a@x.vn", "mat_khau": MAT_KHAU})

    def test_gui_ma_va_xac_minh_qua_api(self):
        self.assertFalse(self.client.get("/api/tai-khoan/toi").json()["gui_thu"])
        self.assertEqual(self.client.post("/api/tai-khoan/gui-ma-xac-minh").status_code, 503)
        da_gui = {}
        with patch.dict("os.environ", CO_THU), patch.object(
            gui_thu, "gui_ma_xac_minh", side_effect=lambda den, ten, ma, phut: da_gui.update(den=den, ma=ma)
        ):
            self.assertTrue(self.client.get("/api/tai-khoan/toi").json()["gui_thu"])
            phan_hoi = self.client.post("/api/tai-khoan/gui-ma-xac-minh")
            self.assertEqual(phan_hoi.status_code, 200)
            self.assertEqual(da_gui["den"], "a@x.vn")
            self.assertNotIn(da_gui["ma"], phan_hoi.text)  # mã chỉ nằm trong thư
            sai = self.client.post("/api/tai-khoan/xac-minh", json={"ma": "12345"})
            self.assertEqual(sai.status_code, 400)
            dung = self.client.post("/api/tai-khoan/xac-minh", json={"ma": da_gui["ma"]})
            self.assertEqual(dung.status_code, 200)
            self.assertTrue(dung.json()["nguoi_dung"]["da_xac_minh"])

    def test_thu_loi_thi_tra_lai_luot_gui(self):
        with patch.dict("os.environ", CO_THU), patch.object(
            gui_thu, "gui_ma_xac_minh", side_effect=gui_thu.LoiGuiThu("hỏng")
        ):
            self.assertEqual(self.client.post("/api/tai-khoan/gui-ma-xac-minh").status_code, 502)
            self.assertEqual(self.client.post("/api/tai-khoan/gui-ma-xac-minh").status_code, 502)

    def test_khach_khong_xac_minh_duoc(self):
        khach = TestClient(app)
        self.assertEqual(khach.post("/api/tai-khoan/gui-ma-xac-minh").status_code, 401)
        self.assertEqual(khach.post("/api/tai-khoan/xac-minh", json={"ma": "123456"}).status_code, 401)

    def test_doi_anh_qua_api_chi_chu_xem_duoc(self):
        khong_header = self.client.put("/api/tai-khoan/anh-dai-dien", content=anh_mau())
        self.assertEqual(khong_header.status_code, 403)
        phan_hoi = self.client.put(
            "/api/tai-khoan/anh-dai-dien", content=anh_mau(),
            headers={"Content-Type": "image/png", "X-RAG-Action": "avatar"},
        )
        self.assertEqual(phan_hoi.status_code, 200)
        duong_dan = phan_hoi.json()["nguoi_dung"]["anh"]
        anh = self.client.get(duong_dan)
        self.assertEqual(anh.status_code, 200)
        self.assertEqual(anh.headers["content-type"], "image/webp")
        self.assertIn("nosniff", anh.headers["x-content-type-options"])
        self.assertEqual(TestClient(app).get(duong_dan).status_code, 404)
        self.assertEqual(self.client.get("/api/tai-khoan/toi").json()["nguoi_dung"]["anh"], duong_dan)
        xoa = self.client.delete("/api/tai-khoan/anh-dai-dien")
        self.assertIsNone(xoa.json()["nguoi_dung"]["anh"])
        self.assertEqual(self.client.get(duong_dan).status_code, 404)

    def test_tep_la_bi_tu_choi(self):
        phan_hoi = self.client.put(
            "/api/tai-khoan/anh-dai-dien", content=b"<svg onload=alert(1)/>",
            headers={"Content-Type": "image/svg+xml", "X-RAG-Action": "avatar"},
        )
        self.assertEqual(phan_hoi.status_code, 415)
