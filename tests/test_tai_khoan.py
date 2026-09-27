"""Tài khoản đăng nhập: đăng ký, phiên, quyền quản trị, lịch sử và sổ tay theo tài khoản."""

import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import lich_su_chat
import tai_khoan
from api import app
from rag_service import service

MAT_KHAU = "matkhau-rat-dai-1"


@pytest.fixture(autouse=True)
def co_so_du_lieu_moi(tmp_path, monkeypatch):
    """Mỗi test một cơ sở dữ liệu tài khoản riêng để thứ tự chạy không ảnh hưởng."""
    monkeypatch.setattr(tai_khoan, "DUONG_DAN_DB", str(tmp_path / "tai_khoan.db"))
    monkeypatch.delenv("RAG_EMAIL_QUAN_TRI", raising=False)
    tai_khoan.dong_ket_noi()
    yield
    tai_khoan.dong_ket_noi()


class MatKhauTests(unittest.TestCase):
    def test_bam_va_kiem_tra(self):
        da_bam = tai_khoan.bam_mat_khau("abc12345")
        self.assertTrue(da_bam.startswith("scrypt$"))
        self.assertNotIn("abc12345", da_bam)
        self.assertTrue(tai_khoan.dung_mat_khau("abc12345", da_bam))
        self.assertFalse(tai_khoan.dung_mat_khau("abc12346", da_bam))
        self.assertFalse(tai_khoan.dung_mat_khau("abc12345", "hong"))

    def test_hai_lan_bam_khac_nhau_nho_muoi(self):
        self.assertNotEqual(tai_khoan.bam_mat_khau("abc12345"), tai_khoan.bam_mat_khau("abc12345"))


class DangKyDangNhapTests(unittest.TestCase):
    def test_tai_khoan_dau_tien_la_quan_tri(self):
        dau = tai_khoan.dang_ky("A@Truong.edu.vn", MAT_KHAU, "Cô A")
        sau = tai_khoan.dang_ky("b@truong.edu.vn", MAT_KHAU)
        self.assertEqual(dau["email"], "a@truong.edu.vn")
        self.assertTrue(dau["quan_tri"])
        self.assertFalse(sau["quan_tri"])
        self.assertEqual(sau["ten"], "b")

    def test_email_chi_dinh_quyet_dinh_quan_tri(self):
        with patch.dict("os.environ", {"RAG_EMAIL_QUAN_TRI": "admin@truong.edu.vn"}):
            nguoi_la = tai_khoan.dang_ky("nguoila@x.vn", MAT_KHAU)
            quan_tri = tai_khoan.dang_ky("admin@truong.edu.vn", MAT_KHAU)
        self.assertFalse(nguoi_la["quan_tri"])
        self.assertTrue(quan_tri["quan_tri"])

    def test_email_trung_va_mat_khau_ngan(self):
        tai_khoan.dang_ky("a@x.vn", MAT_KHAU)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.dang_ky("A@x.vn", MAT_KHAU)
        self.assertEqual(loi.exception.ma_http, 409)
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.dang_ky("c@x.vn", "ngan")
        with self.assertRaises(tai_khoan.LoiTaiKhoan):
            tai_khoan.dang_ky("khong-phai-email", MAT_KHAU)

    def test_dang_nhap_sai_bi_khoa_tam(self):
        tai_khoan.dang_ky("a@x.vn", MAT_KHAU)
        for _ in range(tai_khoan.SO_LAN_SAI_TOI_DA):
            with self.assertRaises(tai_khoan.LoiTaiKhoan):
                tai_khoan.dang_nhap("a@x.vn", "sai-mat-khau", ip="1.2.3.4")
        # Đã khoá thì mật khẩu đúng cũng phải chờ.
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as loi:
            tai_khoan.dang_nhap("a@x.vn", MAT_KHAU, ip="5.6.7.8")
        self.assertEqual(loi.exception.ma_http, 429)

    def test_email_khong_ton_tai_bao_loi_giong_sai_mat_khau(self):
        tai_khoan.dang_ky("a@x.vn", MAT_KHAU)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as khong_co:
            tai_khoan.dang_nhap("khongco@x.vn", MAT_KHAU)
        with self.assertRaises(tai_khoan.LoiTaiKhoan) as sai:
            tai_khoan.dang_nhap("a@x.vn", "sai-mat-khau")
        self.assertEqual(str(khong_co.exception), str(sai.exception))

    def test_phien_va_doi_mat_khau_dang_xuat_noi_khac(self):
        nd = tai_khoan.dang_ky("a@x.vn", MAT_KHAU)
        phien_nay = tai_khoan.tao_phien(nd["id"])
        phien_khac = tai_khoan.tao_phien(nd["id"])
        self.assertEqual(tai_khoan.nguoi_dung_theo_phien(phien_nay)["id"], nd["id"])
        tai_khoan.doi_mat_khau(nd["id"], MAT_KHAU, "mat-khau-moi-123", giu_phien=phien_nay)
        self.assertIsNotNone(tai_khoan.nguoi_dung_theo_phien(phien_nay))
        self.assertIsNone(tai_khoan.nguoi_dung_theo_phien(phien_khac))
        self.assertIsNotNone(tai_khoan.dang_nhap("a@x.vn", "mat-khau-moi-123"))
        tai_khoan.xoa_phien(phien_nay)
        self.assertIsNone(tai_khoan.nguoi_dung_theo_phien(phien_nay))


class ApiTaiKhoanTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def dang_ky(self, email="a@x.vn", client=None, **them):
        return (client or self.client).post(
            "/api/tai-khoan/dang-ky",
            json={"email": email, "mat_khau": MAT_KHAU, **them},
            headers={"X-RAG-Client": "trinh-duyet-khach-1"},
        )

    def test_dang_ky_dat_cookie_httponly_va_nhan_ra_nguoi_dung(self):
        phan_hoi = self.dang_ky(ten="Cô A")
        self.assertEqual(phan_hoi.status_code, 200)
        cookie = phan_hoi.headers["set-cookie"]
        self.assertIn("rag_phien=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("samesite=lax", cookie.lower())
        toi = self.client.get("/api/tai-khoan/toi").json()["nguoi_dung"]
        self.assertEqual(toi["ten"], "Cô A")
        self.client.post("/api/tai-khoan/dang-xuat")
        self.assertIsNone(self.client.get("/api/tai-khoan/toi").json()["nguoi_dung"])

    def test_sai_mat_khau_tra_401(self):
        self.dang_ky()
        self.client.post("/api/tai-khoan/dang-xuat")
        phan_hoi = self.client.post(
            "/api/tai-khoan/dang-nhap", json={"email": "a@x.vn", "mat_khau": "sai-mat-khau"},
        )
        self.assertEqual(phan_hoi.status_code, 401)

    def test_khoa_quan_tri(self):
        with patch.dict("os.environ", {"RAG_KHOA_QUAN_TRI": "1"}):
            khach = self.client.delete("/api/cache", headers={"X-RAG-Action": "clear-cache"})
            self.assertEqual(khach.status_code, 401)
            self.dang_ky("admin@x.vn")  # tài khoản đầu tiên là quản trị
            quan_tri = self.client.delete("/api/cache", headers={"X-RAG-Action": "clear-cache"})
            self.assertEqual(quan_tri.status_code, 200)
            nguoi_thuong = TestClient(app)
            self.dang_ky("hs@x.vn", client=nguoi_thuong)
            bi_chan = nguoi_thuong.get("/api/thong-ke")
            self.assertEqual(bi_chan.status_code, 403)

    def test_lich_su_theo_tai_khoan_va_chuyen_tu_khach(self):
        lich_su_chat.ghi_luot("trinh-duyet-khach-1", "Câu hỏi lúc còn là khách", "Trả lời",
                              hoi_thoai_id="hoi-thoai-khach-01")
        self.dang_ky()
        # Máy khác, đăng nhập cùng tài khoản: vẫn thấy hội thoại vừa chuyển sang.
        may_khac = TestClient(app)
        may_khac.post("/api/tai-khoan/dang-nhap", json={"email": "a@x.vn", "mat_khau": MAT_KHAU})
        ds = may_khac.get("/api/hoi-thoai", headers={"X-RAG-Client": "trinh-duyet-khac"}).json()
        self.assertEqual([h["id"] for h in ds["hoi_thoai"]], ["hoi-thoai-khach-01"])
        # Khách giả mã "nd:..." không đọc được lịch sử của tài khoản.
        khach = TestClient(app)
        nd_id = self.client.get("/api/tai-khoan/toi").json()["nguoi_dung"]["id"]
        gia = khach.get("/api/hoi-thoai", headers={"X-RAG-Client": f"nd:{nd_id}"}).json()
        self.assertEqual(gia["hoi_thoai"], [])

    def test_chat_luu_chi_tiet_nguon_theo_tai_khoan(self):
        self.dang_ky()
        su_kien = iter([
            {"type": "sources", "sources": [{"name": "a.pdf", "page": 3, "url": "/api/source?name=a.pdf"}]},
            {"type": "token", "content": "Trả lời [1]"},
            {"type": "goi_y", "goi_y": ["Hỏi tiếp?"]},
            {"type": "done", "elapsed_seconds": 1.5},
        ])
        trang_thai = service.status.state
        service.status.state = "ready"
        try:
            with patch.object(service, "stream_answer", return_value=su_kien):
                self.client.post(
                    "/api/chat/stream",
                    json={"question": "Câu hỏi", "hoi_thoai_id": "hoi-thoai-tk-0001"},
                    headers={"X-RAG-Client": "trinh-duyet-khach-1"},
                ).read()
        finally:
            service.status.state = trang_thai
        chi_tiet = self.client.get("/api/hoi-thoai/hoi-thoai-tk-0001").json()
        luot = chi_tiet["luot"][0]["chi_tiet"]
        self.assertEqual(luot["sources"][0]["page"], 3)
        self.assertEqual(luot["goiY"], ["Hỏi tiếp?"])
        self.assertFalse(luot["interrupted"])

    def test_so_tay_chi_chu_tai_khoan_doc_duoc(self):
        self.assertEqual(self.client.get("/api/so-tay/hoi-thoai-0001").status_code, 401)
        self.dang_ky()
        ban = {"id": "hoi-thoai-0001", "ghiChu": "<p>Ghi chú</p>", "bang": []}
        self.assertEqual(self.client.put("/api/so-tay/hoi-thoai-0001", json=ban).status_code, 200)
        self.assertEqual(self.client.get("/api/so-tay/hoi-thoai-0001").json()["so_tay"], ban)
        nguoi_khac = TestClient(app)
        self.dang_ky("b@x.vn", client=nguoi_khac)
        self.assertIsNone(nguoi_khac.get("/api/so-tay/hoi-thoai-0001").json()["so_tay"])
        self.client.delete("/api/so-tay/hoi-thoai-0001")
        self.assertIsNone(self.client.get("/api/so-tay/hoi-thoai-0001").json()["so_tay"])
