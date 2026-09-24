"""Quản trị viên quản lý tệp gửi lên kho: hàng chờ duyệt, gỡ và khôi phục."""

import os
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import quan_ly_kho
import tai_khoan
from api import app
from rag_service import THU_MUC_TEP_TRONG_KHO, service
from tep_dinh_kem import kho_tep

MAT_KHAU = "matkhau-rat-dai-1"
HOC_SINH = {"id": "hs1", "ten": "Học sinh A", "email": "hs@x.vn", "quan_tri": False}
QUAN_TRI = {"id": "qt1", "ten": "Cô Lan", "email": "lan@x.vn", "quan_tri": True}


class KhoTamTests(unittest.TestCase):
    """Kho tài liệu, sổ ghi chép và cơ sở dữ liệu tài khoản đều là bản tạm."""

    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.addCleanup(self.thu_muc.cleanup)
        self.kho = os.path.join(self.thu_muc.name, "data_giao_duc")
        os.makedirs(self.kho)
        self.tep = os.path.join(self.thu_muc.name, "de-thi.txt")
        with open(self.tep, "w", encoding="utf-8") as f:
            f.write("Đề thi thử môn Toán lớp 10.")
        duong_dan = patch.multiple(
            "rag_service",
            DATA_PATH=self.kho,
            DUONG_DAN_SO_GHI_CHEP=os.path.join(self.thu_muc.name, "so.json"),
        )
        duong_dan.start()
        self.addCleanup(duong_dan.stop)
        hen = patch.object(service, "_hen_cap_nhat_chi_muc")
        hen.start()
        self.addCleanup(hen.stop)
        service.tep_cho_nap.clear()
        self.addCleanup(service.tep_cho_nap.clear)
        khoa = patch.dict(os.environ, {"RAG_KHOA_QUAN_TRI": "1"})
        khoa.start()
        self.addCleanup(khoa.stop)

    def trong_kho(self, ten):
        return os.path.join(self.kho, THU_MUC_TEP_TRONG_KHO, ten)


class ChoDuyetTests(KhoTamTests):
    def test_hoc_sinh_dinh_kem_thi_cho_duyet_khong_vao_kho(self):
        trang_thai, thong_bao = service.luu_tep_vao_kho(self.tep, "de-thi.txt", HOC_SINH)
        self.assertEqual(trang_thai, "cho_duyet")
        self.assertIn("duyệt", thong_bao)
        self.assertFalse(os.path.exists(self.trong_kho("de-thi.txt")))
        self.assertEqual(service.tep_cho_nap, [])
        cho = quan_ly_kho.danh_sach_tai_len("cho_duyet")
        self.assertEqual([(c["ten"], c["nguoi_ten"]) for c in cho], [("de-thi.txt", "Học sinh A")])

    def test_cung_noi_dung_chi_xep_hang_mot_lan(self):
        service.luu_tep_vao_kho(self.tep, "de-thi.txt", HOC_SINH)
        service.luu_tep_vao_kho(self.tep, "ten-khac.txt", None)
        self.assertEqual(quan_ly_kho.dem_cho_duyet(), 1)

    def test_quan_tri_dinh_kem_thi_vao_thang_va_ghi_ten(self):
        trang_thai, _ = service.luu_tep_vao_kho(self.tep, "de-thi.txt", QUAN_TRI)
        self.assertEqual(trang_thai, "da_luu")
        self.assertTrue(os.path.isfile(self.trong_kho("de-thi.txt")))
        self.assertEqual(quan_ly_kho.nguoi_dua_vao_kho()["de-thi.txt"]["nguoi_gui"], "Cô Lan")

    def test_thu_muc_nong_khong_can_duyet(self):
        trang_thai, _ = service.luu_tep_vao_kho(self.tep, "de-thi.txt", tu_he_thong=True)
        self.assertEqual(trang_thai, "da_luu")


class ApiQuanLyKhoTests(KhoTamTests):
    def setUp(self):
        super().setUp()
        self.db_cu = tai_khoan.DUONG_DAN_DB
        tai_khoan.DUONG_DAN_DB = os.path.join(self.thu_muc.name, "tai_khoan.db")
        tai_khoan.dong_ket_noi()
        self.addCleanup(self._tra_db)
        self.quan_tri = TestClient(app)
        self.quan_tri.post("/api/tai-khoan/dang-ky", json={"email": "lan@x.vn", "mat_khau": MAT_KHAU})
        self.hoc_sinh = TestClient(app)
        self.hoc_sinh.post("/api/tai-khoan/dang-ky", json={"email": "hs@x.vn", "mat_khau": MAT_KHAU})

    def _tra_db(self):
        tai_khoan.dong_ket_noi()
        tai_khoan.DUONG_DAN_DB = self.db_cu

    def test_nguoi_thuong_khong_vao_duoc_trang_quan_ly(self):
        self.assertEqual(self.hoc_sinh.get("/api/quan-ly/tai-len").status_code, 403)
        self.assertEqual(TestClient(app).get("/api/quan-ly/thung-rac").status_code, 401)

    def _gui_vao_kho(self, client, ten="de-thi.txt", noi_dung="Đề thi thử môn Toán lớp 10."):
        return client.post(f"/api/kho/tep?ten={ten}", content=noi_dung.encode("utf-8"),
                           headers={"X-RAG-Action": "upload-library"})

    def test_nguoi_dung_tai_len_kho_thi_thanh_tai_lieu_rieng(self):
        phan_hoi = self._gui_vao_kho(self.hoc_sinh)
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.json()["trang_thai"], "rieng")
        tep_id = phan_hoi.json()["tep"]["id"]
        self.addCleanup(kho_tep.xoa, tep_id, kiem_chu=False)
        # Không vào kho chung, không tự vào hàng chờ duyệt.
        self.assertFalse(os.path.exists(self.trong_kho("de-thi.txt")))
        self.assertEqual(quan_ly_kho.dem_cho_duyet(), 0)
        # Chỉ chủ tệp thấy - quản trị viên cũng không.
        self.assertEqual([t["id"] for t in self.hoc_sinh.get("/api/tep").json()["tep"]], [tep_id])
        self.assertEqual(self.quan_tri.get("/api/tep").json()["tep"], [])
        self.assertEqual(self.quan_tri.get(f"/api/tep/{tep_id}").status_code, 404)
        self.assertEqual(self.quan_tri.get(f"/api/tep/{tep_id}/noi-dung").status_code, 404)

    def test_de_xuat_thi_vao_hang_cho_va_ghi_ai_de_xuat(self):
        noi_dung = "Đề thi thử môn Toán lớp 10, gồm 5 câu tự luận về hàm số và hình học."
        tep_id = self._gui_vao_kho(self.hoc_sinh, noi_dung=noi_dung).json()["tep"]["id"]
        self.addCleanup(kho_tep.xoa, tep_id, kiem_chu=False)
        het = time.monotonic() + 20
        while kho_tep.lay(tep_id).trang_thai == "dang_xu_ly" and time.monotonic() < het:
            time.sleep(0.05)
        duong_dan = f"/api/tep/{tep_id}/de-xuat"
        self.assertEqual(self.hoc_sinh.post(duong_dan).status_code, 403)  # thiếu X-RAG-Action
        self.assertEqual(
            self.quan_tri.post(duong_dan, headers={"X-RAG-Action": "de-xuat-kho"}).status_code, 404
        )
        phan_hoi = self.hoc_sinh.post(duong_dan, headers={"X-RAG-Action": "de-xuat-kho"})
        self.assertEqual(phan_hoi.json()["luu_kho"], "cho_duyet")
        cho = quan_ly_kho.danh_sach_tai_len("cho_duyet")
        self.assertEqual([(c["ten"], c["nguon"], c["nguoi_ten"]) for c in cho],
                         [("de-thi.txt", "de_xuat", "hs")])
        # Đề xuất lại cùng nội dung thì không xếp hàng lần hai.
        self.hoc_sinh.post(duong_dan, headers={"X-RAG-Action": "de-xuat-kho"})
        self.assertEqual(quan_ly_kho.dem_cho_duyet(), 1)
        # Quản trị viên từ chối: chủ tệp thấy đúng tình trạng.
        self.quan_tri.post(f"/api/quan-ly/tai-len/{cho[0]['id']}/tu-choi", headers={"X-RAG-Action": "tu-choi-tep"})
        self.assertEqual(self.hoc_sinh.get(f"/api/tep/{tep_id}").json()["luu_kho"], "tu_choi")

    def test_khach_phai_dang_nhap_moi_tai_len_kho(self):
        self.assertEqual(self._gui_vao_kho(TestClient(app)).status_code, 401)
        self.assertEqual(quan_ly_kho.dem_cho_duyet(), 0)

    def test_quan_tri_tai_len_kho_thi_vao_thang(self):
        phan_hoi = self._gui_vao_kho(self.quan_tri)
        self.assertEqual(phan_hoi.json()["trang_thai"], "da_luu")
        self.assertTrue(os.path.isfile(self.trong_kho("de-thi.txt")))
        self.assertEqual(quan_ly_kho.dem_cho_duyet(), 0)

    def test_duyet_dua_tep_vao_kho(self):
        service.luu_tep_vao_kho(self.tep, "de-thi.txt", HOC_SINH)
        ma = quan_ly_kho.danh_sach_tai_len("cho_duyet")[0]["id"]
        xem = self.quan_tri.get(f"/api/quan-ly/tai-len/{ma}/tep")
        self.assertIn("Đề thi thử", xem.content.decode("utf-8"))
        phan_hoi = self.quan_tri.post(
            f"/api/quan-ly/tai-len/{ma}/duyet", headers={"X-RAG-Action": "duyet-tep"}
        )
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.json()["so_cho_duyet"], 0)
        self.assertTrue(os.path.isfile(self.trong_kho("de-thi.txt")))
        self.assertEqual(service.tep_cho_nap, ["de-thi.txt"])
        ban = quan_ly_kho.danh_sach_tai_len("trong_kho")[0]
        self.assertEqual((ban["nguoi_ten"], ban["xu_ly_boi"]), ("Học sinh A", "lan"))

    def test_tu_choi_chuyen_vao_thung_rac(self):
        service.luu_tep_vao_kho(self.tep, "de-thi.txt", HOC_SINH)
        ma = quan_ly_kho.danh_sach_tai_len("cho_duyet")[0]["id"]
        self.quan_tri.post(f"/api/quan-ly/tai-len/{ma}/tu-choi", headers={"X-RAG-Action": "tu-choi-tep"})
        self.assertEqual(os.listdir(quan_ly_kho.THU_MUC_CHO_DUYET), [])
        self.assertEqual(quan_ly_kho.danh_sach_tai_len("tu_choi")[0]["ten"], "de-thi.txt")
        self.assertFalse(os.path.exists(self.trong_kho("de-thi.txt")))
        rac = self.quan_tri.get("/api/quan-ly/thung-rac").json()["thung_rac"]
        self.assertEqual([(r["ten"], r["loai"], r["go_boi"], r["nguoi_gui"]) for r in rac],
                         [("de-thi.txt", "tu_choi", "lan", "Học sinh A")])

    def test_khoi_phuc_tep_bi_tu_choi_thi_ve_hang_cho(self):
        service.luu_tep_vao_kho(self.tep, "de-thi.txt", HOC_SINH)
        ma = quan_ly_kho.danh_sach_tai_len("cho_duyet")[0]["id"]
        self.quan_tri.post(f"/api/quan-ly/tai-len/{ma}/tu-choi", headers={"X-RAG-Action": "tu-choi-tep"})
        ma_rac = self.quan_tri.get("/api/quan-ly/thung-rac").json()["thung_rac"][0]["id"]
        kq = self.quan_tri.post(f"/api/quan-ly/thung-rac/{ma_rac}/khoi-phuc",
                                headers={"X-RAG-Action": "khoi-phuc"}).json()
        self.assertEqual(kq, {"ten": "de-thi.txt", "ve_cho_duyet": True})
        self.assertEqual(self.quan_tri.get("/api/quan-ly/thung-rac").json()["thung_rac"], [])
        self.assertFalse(os.path.exists(self.trong_kho("de-thi.txt")))
        self.assertEqual(service.tep_cho_nap, [])
        cho = quan_ly_kho.danh_sach_tai_len("cho_duyet")
        self.assertEqual([c["id"] for c in cho], [ma])
        # Về hàng chờ rồi thì duyệt được như thường.
        self.quan_tri.post(f"/api/quan-ly/tai-len/{ma}/duyet", headers={"X-RAG-Action": "duyet-tep"})
        self.assertTrue(os.path.isfile(self.trong_kho("de-thi.txt")))

    def test_go_vao_thung_rac_roi_khoi_phuc(self):
        with open(self.trong_kho("luat.pdf"), "wb") as f:
            f.write(b"%PDF noi dung")
        go = self.quan_tri.post(
            "/api/quan-ly/kho/go", json={"ten": "luat.pdf"}, headers={"X-RAG-Action": "go-tai-lieu"}
        )
        self.assertEqual(go.status_code, 200)
        self.assertFalse(os.path.exists(self.trong_kho("luat.pdf")))
        rac = self.quan_tri.get("/api/quan-ly/thung-rac").json()["thung_rac"]
        self.assertEqual([(r["ten"], r["go_boi"]) for r in rac], [("luat.pdf", "lan")])
        khoi_phuc = self.quan_tri.post(
            f"/api/quan-ly/thung-rac/{rac[0]['id']}/khoi-phuc", headers={"X-RAG-Action": "khoi-phuc"}
        )
        self.assertEqual(khoi_phuc.json()["ten"], "luat.pdf")
        self.assertTrue(os.path.isfile(self.trong_kho("luat.pdf")))
        self.assertEqual(self.quan_tri.get("/api/quan-ly/thung-rac").json()["thung_rac"], [])

    def test_go_tai_lieu_khong_ton_tai(self):
        phan_hoi = self.quan_tri.post(
            "/api/quan-ly/kho/go", json={"ten": "khong-co.pdf"}, headers={"X-RAG-Action": "go-tai-lieu"}
        )
        self.assertEqual(phan_hoi.status_code, 404)
