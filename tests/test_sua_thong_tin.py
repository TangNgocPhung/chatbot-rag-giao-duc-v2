"""Người dùng tự sửa tên hiển thị và email (vd. lỡ nhập sai email lúc đăng ký)."""

import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import tai_khoan
from api import app

MAT_KHAU = "matkhau-rat-dai-1"
CO_THU = {"RAG_SMTP_TAI_KHOAN": "hopthu@gmail.com", "RAG_SMTP_MAT_KHAU": "abcd efgh ijkl mnop"}


@pytest.fixture(autouse=True)
def co_so_du_lieu_moi(tmp_path, monkeypatch):
    monkeypatch.setattr(tai_khoan, "DUONG_DAN_DB", str(tmp_path / "tai_khoan.db"))
    for bien in ("RAG_EMAIL_QUAN_TRI", "RAG_SMTP_TAI_KHOAN", "RAG_SMTP_MAT_KHAU"):
        monkeypatch.delenv(bien, raising=False)
    tai_khoan.dong_ket_noi()
    yield
    tai_khoan.dong_ket_noi()


class SuaThongTinTests(unittest.TestCase):
    def setUp(self):
        self.nd = tai_khoan.dang_ky("sai@gmail.com", MAT_KHAU, "Ngọc Phụng")

    def test_doi_ten_khong_can_mat_khau(self):
        nd = tai_khoan.doi_thong_tin(self.nd["id"], ten="  Tăng   Ngọc Phụng ")
        self.assertEqual(nd["ten"], "Tăng Ngọc Phụng")
        self.assertEqual(nd["email"], "sai@gmail.com")
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.doi_thong_tin(self.nd["id"], ten="   ")

    def test_doi_email_can_mat_khau_va_phai_xac_minh_lai(self):
        _, ma = tai_khoan.tao_ma_xac_minh(self.nd["id"])
        tai_khoan.xac_minh(self.nd["id"], ma)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.doi_thong_tin(self.nd["id"], email="dung@gmail.com", mat_khau="sai-mat-khau")
        self.assertEqual(loi.exception.ma_http, 401)

        nd = tai_khoan.doi_thong_tin(self.nd["id"], email=" Dung@Gmail.com ", mat_khau=MAT_KHAU)
        self.assertEqual(nd["email"], "dung@gmail.com")
        self.assertFalse(nd["da_xac_minh"])
        self.assertEqual(tai_khoan.dang_nhap("dung@gmail.com", MAT_KHAU)["id"], self.nd["id"])
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.dang_nhap("sai@gmail.com", MAT_KHAU)

    def test_giu_nguyen_email_thi_khong_can_mat_khau(self):
        nd = tai_khoan.doi_thong_tin(self.nd["id"], ten="Mới", email="SAI@gmail.com")
        self.assertEqual((nd["ten"], nd["email"]), ("Mới", "sai@gmail.com"))

    def test_email_da_co_nguoi_dung(self):
        tai_khoan.dang_ky("khac@gmail.com", MAT_KHAU)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.doi_thong_tin(self.nd["id"], email="khac@gmail.com", mat_khau=MAT_KHAU)
        self.assertEqual(loi.exception.ma_http, 409)

    def test_ma_gui_toi_email_cu_mat_hieu_luc(self):
        _, ma = tai_khoan.tao_ma_xac_minh(self.nd["id"])
        tai_khoan.doi_thong_tin(self.nd["id"], email="dung@gmail.com", mat_khau=MAT_KHAU)
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.xac_minh(self.nd["id"], ma)

    def test_doi_sang_email_quan_tri_chua_xac_minh_thi_chua_co_quyen(self):
        # self.nd là tài khoản đầu tiên nên vốn đã là quản trị; dùng một người thường.
        with patch.dict("os.environ", {"RAG_EMAIL_QUAN_TRI": "admin@x.vn", **CO_THU}):
            thuong = tai_khoan.dang_ky("nguoi-thuong@x.vn", MAT_KHAU)
            nd = tai_khoan.doi_thong_tin(thuong["id"], email="admin@x.vn", mat_khau=MAT_KHAU)
            self.assertFalse(nd["quan_tri"])
            _, ma = tai_khoan.tao_ma_xac_minh(thuong["id"])
            self.assertTrue(tai_khoan.xac_minh(thuong["id"], ma)["quan_tri"])


class ApiSuaThongTinTests(unittest.TestCase):
    def test_qua_api(self):
        client = TestClient(app)
        self.assertEqual(client.post("/api/tai-khoan/thong-tin", json={"ten": "A"}).status_code, 401)
        client.post("/api/tai-khoan/dang-ky", json={"email": "sai@gmail.com", "mat_khau": MAT_KHAU, "ten": "Cũ"})
        phan_hoi = client.post("/api/tai-khoan/thong-tin", json={
            "ten": "Ngọc Phụng 4", "email": "dung@gmail.com", "mat_khau": MAT_KHAU,
        })
        self.assertEqual(phan_hoi.status_code, 200)
        nd = phan_hoi.json()["nguoi_dung"]
        self.assertEqual((nd["ten"], nd["email"], nd["da_xac_minh"]), ("Ngọc Phụng 4", "dung@gmail.com", False))
        # Phiên đăng nhập vẫn giữ nguyên sau khi đổi.
        self.assertEqual(client.get("/api/tai-khoan/toi").json()["nguoi_dung"]["email"], "dung@gmail.com")
        sai = client.post("/api/tai-khoan/thong-tin", json={"email": "x@gmail.com", "mat_khau": "sai"})
        self.assertEqual(sai.status_code, 401)
