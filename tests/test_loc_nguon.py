from datetime import date
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from langchain_core.documents import Document

import hieu_luc_bo_sung as hl
import loc_nguon as loc
import van_ban_meta as vm


def doc(name, text="Nội dung", **meta):
    return Document(page_content=text, metadata={"source_file": name, **meta})


class LocNguonTests(unittest.TestCase):
    def test_ten_file_khong_xac_nhan_duoc_o_so_hieu_trong(self):
        text = "Số: /2026/TT-BGDĐT Hà Nội, ngày tháng năm 2026\nTHÔNG TƯ\nCăn cứ Luật Giáo dục"
        self.assertEqual(vm.suy_so_hieu_chinh("Thông-tư-50-2026-TT-BGDĐT.pdf", text), (None, False))
        self.assertEqual(loc.trang_thai_phan_dau("Thông-tư-50-2026-TT-BGDĐT.pdf", text)[0], "du_thao")

    def test_mot_dau_hieu_thieu_chi_danh_dau_can_xac_minh(self):
        text = "Số: /2026/TT-BGDĐT Hà Nội, ngày 1 tháng 1 năm 2026\nTHÔNG TƯ"
        self.assertEqual(loc.trang_thai_phan_dau("x.pdf", text)[0], "can_xac_minh")

    def test_sach_co_vien_dan_thong_tu_va_mau_khong_bi_cach_ly(self):
        text = "SÁCH BÀI TẬP TIN HỌC 6\nBiên soạn theo Thông tư 32/2018/TT-BGDĐT.\nPHIẾU ĐĂNG KÝ\nNgày tháng năm sinh:"
        self.assertEqual(loc.trang_thai_phan_dau("SBT Tin học 6.pdf", text)[0], "su_dung")
        self.assertFalse(hl.phat_hien_du_thao(text, "SBT Tin học 6.pdf"))

    def test_dau_du_thao_ro_rang_khong_bi_ten_signed_che_di(self):
        text = "Số: /2026/TT-BGDĐT\nTHÔNG TƯ\nDỰ THẢO"
        self.assertTrue(hl.phat_hien_du_thao(text, "x.signed.pdf"))

    def test_bieu_mau_trong_than_khong_lam_mat_so_hieu_that(self):
        text = "Số: 12/2026/TT-BGDĐT Hà Nội, ngày 1 tháng 1 năm 2026\nCăn cứ Luật Giáo dục\nMẫu: Số: /2026/TT-BGDĐT ngày tháng năm"
        self.assertEqual(loc.trang_thai_phan_dau("x.pdf", text)[0], "su_dung")
        self.assertEqual(vm.suy_so_hieu_chinh("x.pdf", text)[0], "12/2026/TT-BGDĐT")

    def test_cach_ly_khong_xoa_noi_dung_va_cho_phep_hoi_du_thao(self):
        d = doc("x.pdf", "Số: /2026/TT-BGDĐT ngày tháng năm 2026\nTHÔNG TƯ")
        catalog = loc.xay_dung({"x.pdf": [d]})
        self.assertEqual(loc.ly_do_loai(d, "Quy định hiện hành?", catalog, {}), "du_thao")
        self.assertEqual(loc.ly_do_loai(d, "Dự thảo đề xuất điều gì?", catalog, {}), "")
        self.assertTrue(d.page_content)

    def test_ban_trung_chi_giu_mot_ban_chinh(self):
        catalog = loc.xay_dung({"b.pdf": [doc("b.pdf","Cùng nội dung")],
                               "a.pdf": [doc("a.pdf","Cùng  nội dung")]})
        self.assertEqual(catalog["b.pdf"]["trang_thai"], "ban_trung")
        self.assertEqual(catalog["b.pdf"]["ban_chinh"], "a.pdf")

    def test_chua_hieu_luc_duoc_tinh_theo_moc_cau_hoi(self):
        d = doc("x.pdf")
        dates = {"x.pdf": hl.TinhTrangThoiGian("x.pdf", ngay_hieu_luc="2027-01-01")}
        self.assertEqual(loc.ly_do_loai(d,"Quy định",{},dates,date(2026,1,1)), "chua_hieu_luc")
        self.assertEqual(loc.ly_do_loai(d,"Quy định",{},dates,date(2027,1,1)), "")

    def test_khong_tron_tieu_hoc_va_dai_hoc(self):
        self.assertTrue(loc.mau_thuan_pham_vi(doc("Quy định thư viện trường tiểu học.pdf"), "Thư viện đại học cần gì?"))
        self.assertFalse(loc.mau_thuan_pham_vi(doc("Luật Giáo dục.pdf"), "Thư viện đại học cần gì?"))
        self.assertFalse(loc.mau_thuan_pham_vi(doc("Quy định trường tiểu học và đại học.pdf"), "Thư viện đại học cần gì?"))

    def test_lop_khac_duoc_loc_ke_ca_thieu_mon(self):
        self.assertTrue(loc.mau_thuan_pham_vi(doc("Giáo dục địa phương lớp 10.xlsx", lop=[10]), "Chương trình Tin học lớp 4?"))
        self.assertFalse(loc.mau_thuan_pham_vi(doc("Hướng dẫn chung.pdf"), "Chương trình Tin học lớp 4?"))

    def test_ten_so_hieu_van_duoc_loc_theo_trich_yeu_noi_dung(self):
        d = doc("16-2022.pdf", "Số: 16/2022/TT-BGDĐT\nTHÔNG TƯ\nQuy định thư viện cơ sở giáo dục mầm non và giáo dục phổ thông\nCăn cứ Luật Giáo dục")
        catalog = loc.xay_dung({"16-2022.pdf":[d]})
        self.assertEqual(loc.ly_do_loai(d, "Thư viện đại học cần gì?", catalog, {}), "mau_thuan_pham_vi")
        self.assertEqual(loc.ly_do_loai(d, "Thư viện tiểu học cần gì?", catalog, {}), "")

    def test_huong_dan_khong_lien_quan_khong_duoc_keo_theo_luat_chung(self):
        d = doc("Quỹ Học bổng Quốc gia.pdf")
        self.assertFalse(loc.di_kem_dung_chu_de({"quan_he":"huong_dan"}, d, "Khung trình độ quốc gia gồm những bậc nào?"))
        self.assertTrue(loc.di_kem_dung_chu_de({"quan_he":"sua_doi"}, d, "Khung trình độ quốc gia?"))
        self.assertTrue(loc.di_kem_dung_chu_de({"quan_he":"huong_dan"}, doc("Nghị định về học bổng.pdf"), "Điều kiện học bổng?"))


class TichHopDichVuTests(unittest.TestCase):
    def test_cach_ly_ung_vien_truoc_khi_cat_top_k(self):
        from rag_service import RAGService
        s = RAGService.__new__(RAGService)
        s._matching_no_text_source = lambda _: None
        s.vector_store = s.bm25_retriever = object()
        s.tu_vung = None
        s.so_quan_he = SimpleNamespace(het_hieu_luc=lambda _: False)
        s.tinh_trang_hieu_luc = {}
        s.danh_muc_nguon = {"draft.pdf":{"trang_thai":"du_thao"}}
        candidates = [doc("draft.pdf"), doc("official.pdf")]
        def retrieve(*args):
            return [d for d in candidates if (args[4] is None or args[4](d))
                    and (args[6] is None or args[6](d))]
        with patch("rag_service.truy_hoi", side_effect=retrieve), patch.dict("os.environ", {"RAG_LOC_NGUON":"1"}):
            self.assertEqual([d.metadata["source_file"] for d in s._retrieve("Quy định hiện hành?")], ["official.pdf"])

    def test_nguon_di_kem_khong_di_vong_qua_cach_ly(self):
        from rag_service import RAGService
        s = RAGService.__new__(RAGService)
        s.so_quan_he = SimpleNamespace(
            ghi_chu_cau_hoi=lambda *a: ("", []), nhan_hieu_luc=lambda *a: None,
            di_kem=lambda *a: [{"tep":"draft.pdf", "vai_tro":"Văn bản sửa đổi", "quan_he":"sua_doi"}],
            nhan_nut=lambda *a: "", nut_cua_tep={})
        s._doan_theo_tep = {"draft.pdf":[doc("draft.pdf","Sửa đổi quy định")]}
        s.danh_muc_nguon = {"draft.pdf":{"trang_thai":"du_thao"}}
        s.tinh_trang_hieu_luc = {}
        with patch.dict("os.environ", {"RAG_LOC_NGUON":"1"}):
            docs, _ = s._them_van_ban_di_kem([doc("official.pdf")], "Quy định hiện hành?")
        self.assertEqual([d.metadata["source_file"] for d in docs], ["official.pdf"])

    def test_huong_dan_cung_chu_de_nhung_sai_cap_hoc_van_bi_loai(self):
        from rag_service import RAGService
        s = RAGService.__new__(RAGService)
        s.so_quan_he = SimpleNamespace(
            ghi_chu_cau_hoi=lambda *a: ("", []), nhan_hieu_luc=lambda *a: None,
            di_kem=lambda *a: [{"tep":"Thư viện tiểu học.pdf", "vai_tro":"Văn bản hướng dẫn", "quan_he":"huong_dan"}],
            nhan_nut=lambda *a: "", nut_cua_tep={})
        s._doan_theo_tep = {"Thư viện tiểu học.pdf":[doc("Thư viện tiểu học.pdf","Quy định thư viện")]}
        s.danh_muc_nguon = {}
        s.tinh_trang_hieu_luc = {}
        with patch.dict("os.environ", {"RAG_LOC_NGUON":"1"}):
            docs, _ = s._them_van_ban_di_kem([doc("Luật chung.pdf")], "Thư viện đại học cần gì?")
        self.assertEqual([d.metadata["source_file"] for d in docs], ["Luật chung.pdf"])
