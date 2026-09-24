"""Tài liệu riêng: tệp người dùng tải lên chỉ chính họ thấy và dùng được."""

import time
import unittest
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import quan_ly_kho
import tai_khoan
from api import app
from rag_service import service
from tep_dinh_kem import kho_tep

MAT_KHAU = "matkhau-rat-dai-1"
NOI_DUNG = (
    "Bài tập lớn môn Học máy nâng cao: so sánh rừng ngẫu nhiên và mạng nơ-ron "
    "trên bộ dữ liệu điểm thi, kèm nhận xét của giảng viên."
).encode("utf-8")


@pytest.fixture(autouse=True)
def co_so_du_lieu_moi(tmp_path, monkeypatch):
    monkeypatch.setattr(tai_khoan, "DUONG_DAN_DB", str(tmp_path / "tai_khoan.db"))
    monkeypatch.delenv("RAG_EMAIL_QUAN_TRI", raising=False)
    monkeypatch.setenv("RAG_KHOA_QUAN_TRI", "1")
    tai_khoan.dong_ket_noi()
    yield
    tai_khoan.dong_ket_noi()


def cho_doc_xong(tep_id, giay=20.0):
    het = time.monotonic() + giay
    while kho_tep.lay(tep_id).trang_thai == "dang_xu_ly" and time.monotonic() < het:
        time.sleep(0.05)


def dang_ky(email):
    client = TestClient(app)
    nd = client.post("/api/tai-khoan/dang-ky", json={"email": email, "mat_khau": MAT_KHAU}).json()
    return client, nd["nguoi_dung"]


def tai_len(client, ten="bai-tap-lon.txt", noi_dung=NOI_DUNG, khach=None):
    headers = {"X-RAG-Action": "upload-file"}
    if khach:
        headers["X-RAG-Client"] = khach
    tep = client.post(f"/api/tep?ten={ten}", content=noi_dung, headers=headers).json()
    cho_doc_xong(tep["id"])
    return tep


class TaiLieuRiengTests(unittest.TestCase):
    def setUp(self):
        self.quan_tri, _ = dang_ky("qt@x.vn")  # tài khoản đầu tiên là quản trị
        self.a, self.nd_a = dang_ky("a@x.vn")
        self.b, _ = dang_ky("b@x.vn")
        self.tep = tai_len(self.a)
        self.addCleanup(kho_tep.xoa_het_cua, f"nd:{self.nd_a['id']}")

    def test_dinh_kem_khong_tu_vao_hang_cho(self):
        self.assertEqual(self.tep["luu_kho"], "rieng")
        self.assertEqual(quan_ly_kho.dem_cho_duyet(), 0)

    def test_chi_chu_tep_liet_ke_va_doc_duoc(self):
        self.assertEqual([t["id"] for t in self.a.get("/api/tep").json()["tep"]], [self.tep["id"]])
        for nguoi_khac in (self.b, self.quan_tri, TestClient(app)):
            self.assertEqual(nguoi_khac.get("/api/tep").json()["tep"], [])
            for duong_dan in (f"/api/tep/{self.tep['id']}", f"/api/tep/{self.tep['id']}/noi-dung",
                              f"/api/doc/thong-tin?tep={self.tep['id']}"):
                self.assertEqual(nguoi_khac.get(duong_dan).status_code, 404, duong_dan)
            self.assertEqual(nguoi_khac.delete(f"/api/tep/{self.tep['id']}").status_code, 404)
        self.assertIsNotNone(kho_tep.lay(self.tep["id"]))  # người khác không xoá được

    def test_nguoi_khac_khong_hoi_duoc_ve_tep(self):
        service.status.state, cu = "ready", service.status.state
        self.addCleanup(setattr, service.status, "state", cu)
        with patch.object(service, "stream_answer", return_value=iter([{"type": "done"}])) as hoi:
            phan_hoi = self.b.post("/api/chat/stream", json={"question": "tệp nói gì", "tep_ids": [self.tep["id"]]})
            self.assertEqual(phan_hoi.status_code, 404)
            hoi.assert_not_called()
            self.assertEqual(
                self.a.post("/api/chat/stream", json={"question": "tệp nói gì", "tep_ids": [self.tep["id"]]}).status_code,
                200,
            )

    def test_xoa_tai_khoan_thi_xoa_tai_lieu_rieng(self):
        phan_hoi = self.quan_tri.delete(
            f"/api/quan-ly/tai-khoan/{self.nd_a['id']}", headers={"X-RAG-Action": "xoa-tai-khoan"}
        )
        self.assertEqual(phan_hoi.json()["so_tai_lieu"], 1)
        self.assertIsNone(kho_tep.lay(self.tep["id"]))

    def test_han_muc_moi_nguoi(self):
        with patch("tep_dinh_kem.SO_TEP_MOI_NGUOI", 1):
            phan_hoi = self.a.post("/api/tep?ten=them.txt", content=NOI_DUNG,
                                   headers={"X-RAG-Action": "upload-file"})
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertIn("tối đa 1", phan_hoi.json()["detail"])


class KhachTests(unittest.TestCase):
    def test_khach_dang_ky_thi_tep_di_theo_sang_tai_khoan(self):
        khach = TestClient(app)
        tep = tai_len(khach, khach="trinh-duyet-1")
        self.addCleanup(kho_tep.xoa, tep["id"], kiem_chu=False)
        # Khách mở lại tệp của mình bằng mã tệp (ảnh trang không gửi được mã trình duyệt).
        self.assertEqual(khach.get(f"/api/tep/{tep['id']}").status_code, 200)
        self.assertEqual(khach.get("/api/tep").json()["tep"], [])  # khách không có "Của tôi"

        nd = khach.post("/api/tai-khoan/dang-ky", json={"email": "moi@x.vn", "mat_khau": MAT_KHAU},
                        headers={"X-RAG-Client": "trinh-duyet-1"}).json()["nguoi_dung"]
        self.assertEqual([t["id"] for t in khach.get("/api/tep").json()["tep"]], [tep["id"]])
        self.assertEqual(kho_tep.lay(tep["id"]).chu, f"nd:{nd['id']}")
        self.assertEqual(TestClient(app).get(f"/api/tep/{tep['id']}").status_code, 404)


class CachLyHtmlTests(unittest.TestCase):
    """Tệp HTML người dùng tải lên không được chạy script trên tên miền chatbot."""

    def test_html_mo_trong_hop_cach_ly(self):
        client, nd = dang_ky("html@x.vn")
        self.addCleanup(kho_tep.xoa_het_cua, f"nd:{nd['id']}")
        html = b"<html><body><h1>Bai giang</h1><script>fetch('/api/quan-ly/tai-khoan')</script>" + NOI_DUNG + b"</body></html>"
        tep = tai_len(client, ten="trang.html", noi_dung=html)
        phan_hoi = client.get(f"/api/tep/{tep['id']}/noi-dung")
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.headers.get("content-security-policy"), "sandbox")
        txt = tai_len(client, ten="ghi-chu.txt")
        self.assertNotIn("content-security-policy", client.get(f"/api/tep/{txt['id']}/noi-dung").headers)
