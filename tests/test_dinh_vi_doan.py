"""Trích dẫn chỉ đúng dòng trên trang gốc, không chỉ số trang.

Ba chỗ dễ hỏng lặng lẽ:
  - Chunk lập chỉ mục trước khi có "so_trang" không mang trang nào: phải dò
    ra trang bằng chính chữ của đoạn trích.
  - Hộp tô sáng phải nằm trong hệ toạ độ của ảnh trang người dùng nhìn thấy
    (kể cả trang xoay), nếu không vệt vàng lệch sang dòng khác.
  - PDF scan không có lớp chữ: hộp chữ lấy từ OCR, và chỉ OCR một lần.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

import ocr_pdf
import trinh_doc_tai_lieu as tdtl
from api import app
from rag_service import RAGService, cau_trong_tam, service

TRANG_1 = [
    "Dieu 1. Pham vi dieu chinh cua nghi dinh nay",
    "Nghi dinh nay quy dinh chi tiet mot so dieu",
]
TRANG_2 = [
    "Dieu 9. Tuyen dung nha giao",
    "Co so giao duc ngoai cong lap thuc hien tuyen dung",
    "nha giao theo trinh tu thu tuc cua co so giao duc",
    "Dieu 10. Tiep nhan nha giao vao co so cong lap",
    "Thanh lap hoi dong kiem tra sat hach ung vien",
]


def _pdf(duong_dan: str, cac_trang: list[list[str]], xoay: int = 0, co_chu: bool = True) -> None:
    """PDF 600x800 điểm, mỗi dòng cách nhau 40 điểm từ y=740 xuống."""
    cac_doi_tuong = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    con = []
    for dong in cac_trang:
        noi_dung = b"".join(
            b"BT /F1 16 Tf 40 %d Td (%s) Tj ET\n" % (740 - 40 * i, d.encode("ascii"))
            for i, d in enumerate(dong)
        ) if co_chu else b"0 0 1 rg 40 700 100 20 re f\n"
        so_trang = len(cac_doi_tuong) + 1
        con.append(b"%d 0 R" % so_trang)
        cac_doi_tuong.append(
            (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 800] /Rotate %d "
             b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>")
            % (xoay, so_trang + 1, so_trang + 2)
        )
        cac_doi_tuong.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        cac_doi_tuong.append(b"<< /Length %d >>\nstream\n" % len(noi_dung) + noi_dung + b"endstream")
    cac_doi_tuong[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(con), len(con))
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


def _dong_cua(hop: list[float]) -> int:
    """Dòng thứ mấy (từ 0) mà hộp tô sáng nằm trên, theo bố cục của _pdf."""
    giua_diem_pdf = 800 - (hop[1] + hop[3]) / 2 * 800
    return round((740 + 5 - giua_diem_pdf) / 40)


class DinhViPdfCoLopChuTests(unittest.TestCase):
    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.thu_muc.name, "nd.pdf")
        _pdf(self.pdf, [TRANG_1, TRANG_2])

    def tearDown(self):
        self.thu_muc.cleanup()

    def test_do_ra_trang_khi_chunk_khong_co_so_trang(self):
        doan = " ".join(TRANG_2[1:3])
        kq = tdtl.dinh_vi_doan(self.pdf, doan)
        self.assertEqual(kq["trang"], 2)
        dong = sorted({_dong_cua(h) for h in kq["danh_dau"][2]["vung"]})
        self.assertEqual(dong, [1, 2])

    def test_cau_trong_tam_chi_to_dong_cua_no(self):
        doan = " ".join(TRANG_2)
        kq = tdtl.dinh_vi_doan(self.pdf, doan, trong_tam=TRANG_2[4])
        muc = kq["danh_dau"][2]
        self.assertEqual({_dong_cua(h) for h in muc["vung"]}, {0, 1, 2, 3, 4})
        self.assertEqual({_dong_cua(h) for h in muc["chinh"]}, {4})

    def test_chu_that_thang_metadata_trang_sai(self):
        """Chunk cũ mang "page" của trang đầu tệp; chữ nằm ở trang 2 thì tô trang 2."""
        kq = tdtl.dinh_vi_doan(self.pdf, TRANG_2[4], trang_goi_y=1)
        self.assertEqual(kq["trang"], 2)

    def test_khong_thay_thi_giu_trang_goi_y(self):
        kq = tdtl.dinh_vi_doan(self.pdf, "hoan toan khong lien quan gi ca", trang_goi_y=2)
        self.assertEqual(kq, {"trang": 2, "danh_dau": {}})

    def test_hop_tren_trang_xoay_khop_vung_khoanh(self):
        """Hộp trả về phải cùng hệ toạ độ với ảnh trang: khoanh lại đúng hộp đó
        thì lấy ra được đúng chữ vừa tô."""
        xoay = os.path.join(self.thu_muc.name, "xoay.pdf")
        _pdf(xoay, [TRANG_2], xoay=90)
        kq = tdtl.dinh_vi_doan(xoay, TRANG_2[3])
        hop = kq["danh_dau"][1]["vung"]
        self.assertEqual(len(hop), 1)
        chu = tdtl.chu_trong_vung(xoay, 1, tuple(hop[0]))["van_ban"]
        self.assertIn("Tiep nhan nha giao", chu)


class DinhViPdfScanTests(unittest.TestCase):
    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.thu_muc.name, "scan.pdf")
        _pdf(self.pdf, [TRANG_1, TRANG_2], co_chu=False)
        self.cache = patch.object(ocr_pdf, "THU_MUC_CACHE", self.thu_muc.name)
        self.cache.start()
        tdtl._tu_theo_trang.clear()
        tdtl._chu_theo_trang.clear()

    def tearDown(self):
        self.cache.stop()
        self.thu_muc.cleanup()

    def test_dung_ban_ocr_de_do_trang_va_ocr_trang_do_mot_lan(self):
        hop_ocr = [
            (tu, 0.1, 0.1 + 0.05 * i, 0.2, 0.14 + 0.05 * i)
            for i, dong in enumerate(TRANG_2) for tu in dong.lower().split()
        ]
        with patch.object(ocr_pdf, "doc_cache", return_value=["\n".join(TRANG_1), "\n".join(TRANG_2)]), \
                patch.object(tdtl, "_tu_ocr", return_value=hop_ocr) as ocr:
            kq = tdtl.dinh_vi_doan(self.pdf, TRANG_2[1])
            self.assertEqual(kq["trang"], 2)
            self.assertEqual(len(kq["danh_dau"][2]["vung"]), 1)
            # Lần sau (kể cả sau khi máy chủ khởi động lại) đọc hộp chữ từ đĩa.
            tdtl._tu_theo_trang.clear()
            tdtl.dinh_vi_doan(self.pdf, TRANG_2[2])
        self.assertEqual(ocr.call_count, 1)

    def test_chua_ocr_thi_khong_do_duoc_nhung_khong_loi(self):
        with patch.object(ocr_pdf, "doc_cache", return_value=None):
            kq = tdtl.dinh_vi_doan(self.pdf, TRANG_2[1], trang_goi_y=2)
        self.assertEqual(kq, {"trang": 2, "danh_dau": {}})


class CumKhopTests(unittest.TestCase):
    def test_bo_khoi_khop_le_loi_o_xa(self):
        trang = "nha giao".split() + ["x"] * 60 + "co so giao duc tuyen dung nha giao dung han".split()
        doan = "co so giao duc tuyen dung nha giao".split()
        dau, cuoi, so_khop = tdtl._cum_khop(trang, doan)
        self.assertEqual((dau, cuoi, so_khop), (62, 70, 8))

    def test_chiu_duoc_loi_ocr_vai_chu(self):
        trang = "luat nha giao sô 73 2025 qh15 co quan quan ly".split()
        doan = "luat nha giao số 73 2025 qh15 co quan quan ly".split()
        dau, cuoi, _ = tdtl._cum_khop(trang, doan)
        self.assertEqual((dau, cuoi), (0, len(trang)))


class CauTrongTamTests(unittest.TestCase):
    def test_chon_cau_sat_cau_hoi(self):
        doan = (
            "Điều 9. Tuyển dụng nhà giáo. Cơ sở giáo dục công lập tổ chức thi tuyển. "
            "Cơ sở giáo dục ngoài công lập thực hiện tuyển dụng nhà giáo theo quy chế của cơ sở. "
            "Việc ra đề thi phải bảo mật."
        )
        cau = cau_trong_tam(doan, "Cơ sở giáo dục ngoài công lập tuyển dụng nhà giáo thế nào?")
        self.assertTrue(cau.startswith("Cơ sở giáo dục ngoài công lập"))

    def test_cau_hoi_khong_lien_quan_thi_bo_trong(self):
        self.assertEqual(cau_trong_tam("Điều 1. Phạm vi điều chỉnh.", "thời tiết hôm nay"), "")


class NguonMangDoanTests(unittest.TestCase):
    def test_pdf_trong_kho_kem_doan_de_dinh_vi(self):
        nguon = RAGService._sources([Document(
            page_content="Cơ sở giáo dục ngoài công lập\ntuyển dụng nhà giáo.",
            metadata={"source_file": "nd.pdf"},
        )], cau_hoi="ngoài công lập tuyển dụng nhà giáo")[0]
        self.assertEqual(nguon["doan"], "Cơ sở giáo dục ngoài công lập tuyển dụng nhà giáo.")
        self.assertTrue(nguon["trong_tam"])

    def test_trang_web_va_word_khong_kem(self):
        web, word = RAGService._sources([
            Document(page_content="x", metadata={"source_file": "a.pdf", "source_url": "https://vb.gov.vn/a.pdf"}),
            Document(page_content="x", metadata={"source_file": "b.docx"}),
        ])
        self.assertNotIn("doan", web)
        self.assertNotIn("doan", word)


class DinhViApiTests(unittest.TestCase):
    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.pdf = os.path.join(self.thu_muc.name, "nd.pdf")
        _pdf(self.pdf, [TRANG_1, TRANG_2])
        self.client = TestClient(app)

    def tearDown(self):
        self.thu_muc.cleanup()

    def test_tra_trang_va_hop(self):
        with patch.object(service, "resolve_source_file", return_value=self.pdf):
            phan_hoi = self.client.post("/api/doc/dinh-vi", json={
                "nguon": "nd-dinh-vi.pdf", "doan": TRANG_2[3], "trang": 1,
            })
        self.assertEqual(phan_hoi.status_code, 200, phan_hoi.text)
        du_lieu = phan_hoi.json()
        self.assertEqual(du_lieu["trang"], 2)
        self.assertEqual(len(du_lieu["danh_dau"]["2"]["vung"]), 1)

    def test_thieu_doan_bi_tu_choi(self):
        phan_hoi = self.client.post("/api/doc/dinh-vi", json={"nguon": "nd.pdf", "doan": ""})
        self.assertEqual(phan_hoi.status_code, 422)


if __name__ == "__main__":
    unittest.main()
