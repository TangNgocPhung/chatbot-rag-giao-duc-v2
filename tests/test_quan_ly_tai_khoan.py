"""Quản trị viên xem, khoá / mở khoá và xoá tài khoản."""

import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import lich_su_chat
import tai_khoan
from api import app

MAT_KHAU = "matkhau-rat-dai-1"
QUAN_TRI = {"id": "qt", "ten": "Cô Quản Trị"}


@pytest.fixture(autouse=True)
def co_so_du_lieu_moi(tmp_path, monkeypatch):
    monkeypatch.setattr(tai_khoan, "DUONG_DAN_DB", str(tmp_path / "tai_khoan.db"))
    for bien in ("RAG_EMAIL_QUAN_TRI", "RAG_SMTP_TAI_KHOAN", "RAG_SMTP_MAT_KHAU"):
        monkeypatch.delenv(bien, raising=False)
    tai_khoan.dong_ket_noi()
    yield
    tai_khoan.dong_ket_noi()


class KhoaXoaTests(unittest.TestCase):
    def setUp(self):
        self.qt = tai_khoan.dang_ky("qt@x.vn", MAT_KHAU, "Quản trị")  # tài khoản đầu tiên
        self.nd = tai_khoan.dang_ky("a@x.vn", MAT_KHAU, "Cô A")

    def test_danh_sach_co_trang_thai(self):
        ds = {tk["email"]: tk for tk in tai_khoan.danh_sach_tai_khoan()}
        self.assertEqual(set(ds), {"qt@x.vn", "a@x.vn"})
        self.assertTrue(ds["qt@x.vn"]["quan_tri"])
        self.assertFalse(ds["a@x.vn"]["da_xac_minh"])
        self.assertFalse(ds["a@x.vn"]["bi_cam"])
        self.assertNotIn("mat_khau_bam", ds["a@x.vn"])

    def test_khoa_thi_dang_xuat_va_khong_dang_nhap_duoc(self):
        phien = tai_khoan.tao_phien(self.nd["id"])
        tk = tai_khoan.dat_cam(self.nd["id"], True, self.qt)
        self.assertTrue(tk["bi_cam"])
        self.assertEqual(tk["cam_boi"], "Quản trị")
        self.assertIsNone(tai_khoan.nguoi_dung_theo_phien(phien))
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.dang_nhap("a@x.vn", MAT_KHAU)
        self.assertEqual(loi.exception.ma_http, 403)
        # Sai mật khẩu thì vẫn báo sai mật khẩu, không lộ chuyện bị khoá.
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.dang_nhap("a@x.vn", "sai-mat-khau-roi")
        self.assertEqual(loi.exception.ma_http, 401)
        # Email vẫn bị giữ: không đăng ký lại được.
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.dang_ky("a@x.vn", MAT_KHAU)

        tai_khoan.dat_cam(self.nd["id"], False, self.qt)
        self.assertEqual(tai_khoan.dang_nhap("a@x.vn", MAT_KHAU)["id"], self.nd["id"])

    def test_xoa_sach_du_lieu_va_giai_phong_email(self):
        tai_khoan.tao_phien(self.nd["id"])
        tai_khoan.ghi_so_tay(self.nd["id"], "h1", {"ghi": "x"})
        self.assertEqual(tai_khoan.xoa_tai_khoan(self.nd["id"], self.qt), "a@x.vn")
        self.assertIsNone(tai_khoan.lay_nguoi_dung(self.nd["id"]))
        self.assertIsNone(tai_khoan.lay_so_tay(self.nd["id"], "h1"))
        self.assertEqual(
            tai_khoan._connect().execute(
                "SELECT COUNT(*) FROM phien WHERE nguoi_dung_id = ?", (self.nd["id"],)
            ).fetchone()[0],
            0,
        )
        tai_khoan.dang_ky("a@x.vn", MAT_KHAU)  # đăng ký lại được

    def test_khong_tu_khoa_minh_va_khong_dung_quan_tri_khac(self):
        for lam in (lambda: tai_khoan.dat_cam(self.qt["id"], True, self.qt),
                    lambda: tai_khoan.xoa_tai_khoan(self.qt["id"], self.qt)):
            with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
                lam()
            self.assertEqual(loi.exception.ma_http, 409)
        # Quản trị viên khác (theo email chỉ định) cũng không khoá được.
        with patch.dict("os.environ", {"RAG_EMAIL_QUAN_TRI": "a@x.vn"}):
            with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
                tai_khoan.dat_cam(self.nd["id"], True, QUAN_TRI)
        self.assertEqual(loi.exception.ma_http, 409)

    def test_tai_khoan_khong_ton_tai(self):
        for lam in (lambda: tai_khoan.dat_cam("khong-co", True, self.qt),
                    lambda: tai_khoan.dat_cam("khong-co", False, self.qt),
                    lambda: tai_khoan.xoa_tai_khoan("khong-co", self.qt)):
            with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
                lam()
            self.assertEqual(loi.exception.ma_http, 404)


class ApiQuanLyTaiKhoanTests(unittest.TestCase):
    def setUp(self):
        self.quan_tri = TestClient(app)
        self.quan_tri.post("/api/tai-khoan/dang-ky", json={"email": "qt@x.vn", "mat_khau": MAT_KHAU})
        self.nguoi = TestClient(app)
        self.nd = self.nguoi.post(
            "/api/tai-khoan/dang-ky", json={"email": "a@x.vn", "mat_khau": MAT_KHAU}
        ).json()["nguoi_dung"]
        self.bat_khoa = patch.dict("os.environ", {"RAG_KHOA_QUAN_TRI": "1"})
        self.bat_khoa.start()
        self.addCleanup(self.bat_khoa.stop)

    def test_chi_quan_tri_moi_xem_duoc(self):
        self.assertEqual(TestClient(app).get("/api/quan-ly/tai-khoan").status_code, 401)
        self.assertEqual(self.nguoi.get("/api/quan-ly/tai-khoan").status_code, 403)
        ds = self.quan_tri.get("/api/quan-ly/tai-khoan").json()["tai_khoan"]
        toi = {tk["email"]: tk["la_toi"] for tk in ds}
        self.assertEqual(toi, {"qt@x.vn": True, "a@x.vn": False})

    def test_khoa_qua_api_la_nguoi_do_bi_dang_xuat(self):
        duong_dan = f"/api/quan-ly/tai-khoan/{self.nd['id']}/khoa"
        self.assertEqual(self.nguoi.post(duong_dan, json={"khoa": True},
                                         headers={"X-RAG-Action": "khoa-tai-khoan"}).status_code, 403)
        # Thiếu header hành động (vd. form giả mạo từ trang khác) thì từ chối.
        self.assertEqual(self.quan_tri.post(duong_dan, json={"khoa": True}).status_code, 403)
        phan_hoi = self.quan_tri.post(duong_dan, json={"khoa": True}, headers={"X-RAG-Action": "khoa-tai-khoan"})
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertTrue(phan_hoi.json()["tai_khoan"]["bi_cam"])
        self.assertIsNone(self.nguoi.get("/api/tai-khoan/toi").json()["nguoi_dung"])
        dang_nhap = self.nguoi.post("/api/tai-khoan/dang-nhap", json={"email": "a@x.vn", "mat_khau": MAT_KHAU})
        self.assertEqual(dang_nhap.status_code, 403)

    def test_xoa_qua_api_xoa_ca_lich_su(self):
        with patch.object(lich_su_chat, "xoa_theo_client", return_value=3) as xoa_lich_su:
            phan_hoi = self.quan_tri.delete(
                f"/api/quan-ly/tai-khoan/{self.nd['id']}", headers={"X-RAG-Action": "xoa-tai-khoan"}
            )
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.json(), {"email": "a@x.vn", "so_hoi_thoai": 3, "so_tai_lieu": 0})
        xoa_lich_su.assert_called_once_with(f"nd:{self.nd['id']}")
        self.assertIsNone(self.nguoi.get("/api/tai-khoan/toi").json()["nguoi_dung"])

    def test_quan_tri_khong_tu_xoa_minh(self):
        ma = next(tk["id"] for tk in self.quan_tri.get("/api/quan-ly/tai-khoan").json()["tai_khoan"]
                  if tk["la_toi"])
        phan_hoi = self.quan_tri.delete(f"/api/quan-ly/tai-khoan/{ma}", headers={"X-RAG-Action": "xoa-tai-khoan"})
        self.assertEqual(phan_hoi.status_code, 409)
