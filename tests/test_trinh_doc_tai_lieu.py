"""Trình đọc tài liệu trong khung chat: render trang và lấy chữ trong vùng khoanh."""

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

import api
import trinh_doc_tai_lieu as tdtl
from api import app


def _pdf_co_chu(duong_dan: str, xoay: int = 0) -> None:
    """PDF một trang 600x800 điểm: dòng "TREN DAU" gần mép trên, "CUOI TRANG"
    gần mép dưới. Viết tay cho khỏi phụ thuộc thư viện tạo PDF."""
    noi_dung = (
        b"BT /F1 24 Tf 60 740 Td (TREN DAU) Tj ET\n"
        b"BT /F1 24 Tf 60 60 Td (CUOI TRANG) Tj ET\n"
    )
    cac_doi_tuong = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Rotate %d "
         b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>") % xoay,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n" % len(noi_dung) + noi_dung + b"endstream",
    ]
    du_lieu = b"%PDF-1.4\n"
    vi_tri = []
    for so, doi_tuong in enumerate(cac_doi_tuong, 1):
        vi_tri.append(len(du_lieu))
        du_lieu += b"%d 0 obj\n" % so + doi_tuong + b"\nendobj\n"
    bat_dau_xref = len(du_lieu)
    du_lieu += b"xref\n0 %d\n0000000000 65535 f \n" % (len(cac_doi_tuong) + 1)
    for moc in vi_tri:
        du_lieu += b"%010d 00000 n \n" % moc
    du_lieu += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                % (len(cac_doi_tuong) + 1, bat_dau_xref))
    with open(duong_dan, "wb") as f:
        f.write(du_lieu)


class DocTaiLieuTests(unittest.TestCase):
    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.thu_muc.name, "bai-hoc.pdf")
        _pdf_co_chu(self.pdf)

    def tearDown(self):
        self.thu_muc.cleanup()

    def test_thong_tin_tra_so_trang_va_kich_thuoc(self):
        self.assertEqual(tdtl.thong_tin(self.pdf), {"so_trang": 1, "trang": [[600.0, 800.0]]})

    def test_trang_xoay_doi_chieu_kich_thuoc(self):
        xoay = os.path.join(self.thu_muc.name, "xoay.pdf")
        _pdf_co_chu(xoay, xoay=90)
        self.assertEqual(tdtl.thong_tin(xoay)["trang"], [[800.0, 600.0]])

    def test_render_lam_tron_be_rong(self):
        du_lieu, kieu = tdtl.render_trang(self.pdf, 1, 530)
        self.assertIn(kieu, {"image/webp", "image/png"})
        with Image.open(__import__("io").BytesIO(du_lieu)) as anh:
            self.assertEqual(anh.width, 600)

    def test_trang_khong_ton_tai(self):
        with self.assertRaises(tdtl.LoiDocTaiLieu):
            tdtl.render_trang(self.pdf, 3, 800)

    def test_chi_lay_chu_trong_vung_khoanh(self):
        # "TREN DAU" nằm ở y ~ 740/800 tính từ đáy, tức ~7% từ mép trên.
        tren = tdtl.chu_trong_vung(self.pdf, 1, (0.0, 0.0, 1.0, 0.2))
        self.assertEqual(tren["cach"], "lop_chu")
        self.assertIn("TREN DAU", tren["van_ban"])
        self.assertNotIn("CUOI", tren["van_ban"])
        duoi = tdtl.chu_trong_vung(self.pdf, 1, (0.0, 0.8, 1.0, 1.0))
        self.assertIn("CUOI TRANG", duoi["van_ban"])

    def test_vung_tren_trang_xoay_van_dung_cho(self):
        # Xoay 90° theo chiều kim đồng hồ: mép trên của trang gốc thành mép
        # phải của ảnh người dùng nhìn thấy.
        xoay = os.path.join(self.thu_muc.name, "xoay.pdf")
        _pdf_co_chu(xoay, xoay=90)
        phai = tdtl.chu_trong_vung(xoay, 1, (0.8, 0.0, 1.0, 1.0))
        self.assertIn("TREN DAU", phai["van_ban"])
        self.assertNotIn("CUOI", phai["van_ban"])

    def test_vung_qua_nho_bi_tu_choi(self):
        with self.assertRaises(tdtl.LoiDocTaiLieu):
            tdtl.chu_trong_vung(self.pdf, 1, (0.5, 0.5, 0.501, 0.5005))

    def test_vung_khong_co_lop_chu_thi_ocr(self):
        # Vùng trống ở giữa trang: không có lớp chữ nên phải chuyển sang OCR.
        with patch.object(tdtl, "_ocr_anh", return_value="chữ nhận dạng") as ocr:
            ket_qua = tdtl.chu_trong_vung(self.pdf, 1, (0.1, 0.4, 0.9, 0.6))
        ocr.assert_called_once()
        self.assertEqual(ket_qua, {"van_ban": "chữ nhận dạng", "cach": "ocr"})

    def test_anh_la_mot_trang_va_cat_dung_vung(self):
        anh = os.path.join(self.thu_muc.name, "trang-sach.png")
        Image.new("RGB", (400, 300), "white").save(anh)
        self.assertEqual(tdtl.thong_tin(anh), {"so_trang": 1, "trang": [[400, 300]]})
        with patch.object(tdtl, "_ocr_anh", return_value="") as ocr:
            ket_qua = tdtl.chu_trong_vung(anh, 1, (0.25, 0.5, 0.75, 1.0))
        self.assertEqual(ocr.call_args[0][0].size, (200, 150))
        self.assertEqual(ket_qua["cach"], "trong")

    def test_noi_dong_bi_ngat_giua_cau(self):
        self.assertEqual(
            tdtl._lam_gon("được sửa đổi, bổ sung bởi Luật\nsố 123/2025/QH15;\nCăn cứ Luật Nhà giáo;"),
            "được sửa đổi, bổ sung bởi Luật số 123/2025/QH15;\nCăn cứ Luật Nhà giáo;",
        )

    def test_tu_choi_dinh_dang_khong_doc_duoc(self):
        docx = os.path.join(self.thu_muc.name, "a.docx")
        open(docx, "wb").close()
        with self.assertRaises(tdtl.LoiDocTaiLieu):
            tdtl.thong_tin(docx)


class DocTaiLieuApiTests(unittest.TestCase):
    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.thu_muc.name, "bai-hoc.pdf")
        _pdf_co_chu(self.pdf)
        self.client = TestClient(app)
        api._nguon_da_tim.clear()

    def tearDown(self):
        api._nguon_da_tim.clear()
        self.thu_muc.cleanup()

    def _tim_nguon(self, ten):
        return self.pdf if ten == "bai-hoc.pdf" else None

    def test_doc_nguon_trong_kho(self):
        with patch.object(api.service, "resolve_source_file", side_effect=self._tim_nguon):
            thong_tin = self.client.get("/api/doc/thong-tin", params={"nguon": "bai-hoc.pdf"})
            trang = self.client.get("/api/doc/trang", params={"nguon": "bai-hoc.pdf", "so": 1, "rong": 400})
            vung = self.client.post("/api/doc/vung", json={
                "nguon": "bai-hoc.pdf", "so": 1, "x0": 0, "y0": 0, "x1": 1, "y1": 0.2,
            })
        self.assertEqual(thong_tin.json()["so_trang"], 1)
        self.assertEqual(trang.status_code, 200)
        self.assertTrue(trang.headers["content-type"].startswith("image/"))
        self.assertIn("TREN DAU", vung.json()["van_ban"])

    def test_thieu_nguon_va_nguon_la(self):
        self.assertEqual(self.client.get("/api/doc/thong-tin").status_code, 400)
        with patch.object(api.service, "resolve_source_file", return_value=None):
            self.assertEqual(
                self.client.get("/api/doc/thong-tin", params={"nguon": "khong-co.pdf"}).status_code, 404,
            )
        self.assertEqual(
            self.client.get("/api/doc/thong-tin", params={"tep": "khong-co"}).status_code, 404,
        )

    def test_tep_khong_phai_pdf_hay_anh(self):
        docx = os.path.join(self.thu_muc.name, "a.docx")
        open(docx, "wb").close()
        with patch.object(api.service, "resolve_source_file", return_value=docx):
            phan_hoi = self.client.get("/api/doc/thong-tin", params={"nguon": "a.docx"})
        self.assertEqual(phan_hoi.status_code, 415)

    def test_vung_ngoai_khoang_bi_tu_choi(self):
        phan_hoi = self.client.post("/api/doc/vung", json={
            "nguon": "bai-hoc.pdf", "so": 1, "x0": -1, "y0": 0, "x1": 1, "y1": 2,
        })
        self.assertEqual(phan_hoi.status_code, 422)


if __name__ == "__main__":
    unittest.main()
