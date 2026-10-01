"""Thứ bậc hiệu lực pháp lý: suy từ số hiệu, kiểm tra đồ thị, prompt, xếp hạng."""

import json
import os
import unittest

from langchain_core.documents import Document

import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import thu_bac as tb
import van_ban_meta as vm


class SuyCapTests(unittest.TestCase):
    def test_cap_theo_so_hieu(self):
        for so_hieu, cap in (
            ("123/2025/QH15", 1),
            ("1/2016/NQ-UBTVQH14", 2),
            ("81/2021/NĐ-CP", 3),
            ("5/2013/QĐ-TTg", 4),
            ("22/2021/TT-BGDĐT", 5),
            ("58/2012/TTLT-BGDĐT", 5),
            # Quyết định quy phạm của Bộ trưởng theo luật cũ (số hiệu có năm).
            ("43/2007/QĐ-BGDĐT", 5),
            ("12/2019/NQ-HĐND", 6),
            ("15/2020/QĐ-UBND", 6),
            # Không có năm: công văn, quyết định cá biệt, chỉ thị.
            ("5512/BGDĐT-GDTrH", 9),
            ("527/QĐ-TTg", 9),
            ("20/CT-TTg", 9),
        ):
            self.assertEqual(tb.thu_bac(so_hieu).cap, cap, so_hieu)

    def test_khong_suy_duoc_thi_khong_doan(self):
        for so_hieu in (None, "", "abc", "12/2020/XYZ-ABC"):
            self.assertIsNone(tb.thu_bac(so_hieu), so_hieu)
        self.assertFalse(tb.thap_hon("abc", "81/2021/NĐ-CP"))

    def test_thap_hon(self):
        self.assertTrue(tb.thap_hon("5512/BGDĐT-GDTrH", "22/2021/TT-BGDĐT"))
        self.assertTrue(tb.thap_hon("22/2021/TT-BGDĐT", "81/2021/NĐ-CP"))
        self.assertFalse(tb.thap_hon("81/2021/NĐ-CP", "22/2021/TT-BGDĐT"))
        self.assertFalse(tb.thap_hon("22/2021/TT-BGDĐT", "10/2022/TT-BGDĐT"))

    def test_mo_ta_cho_prompt(self):
        self.assertEqual(
            tb.mo_ta("Nghị định", "81/2021/NĐ-CP"), "Nghị định - văn bản quy phạm pháp luật"
        )
        self.assertEqual(
            tb.mo_ta(None, "5512/BGDĐT-GDTrH"),
            "Công văn - văn bản hành chính, không phải văn bản quy phạm pháp luật",
        )
        self.assertTrue(tb.mo_ta(None, "123/KH-SGDĐT").startswith("Kế hoạch - văn bản hành chính"))
        self.assertIsNone(tb.mo_ta(None, None))

    def test_so_tay_doi_chieu_tay_khong_trai_thu_bac(self):
        """Mọi quan hệ đã đối chiếu tay đều hợp thứ bậc: bảng cấp sai, hay ai
        đó nhập ngược chiều, thì test này báo."""
        duong_dan = os.path.join(os.path.dirname(os.path.dirname(__file__)), "so_quan_he_van_ban.json")
        with open(duong_dan, encoding="utf-8") as tep:
            so_tay = json.load(tep)
        trai = [
            q for q in so_tay["quan_he"]
            if (q["loai"] in qh.QUAN_HE_CO_MOC and tb.thap_hon(q["tu"], q["den"]))
            or (q["loai"] == "huong_dan" and tb.thap_hon(q["den"], q["tu"]))
        ]
        self.assertEqual(trai, [])
        khong_ro = sorted({
            x for q in so_tay["quan_he"] for x in (q["tu"], q["den"]) if tb.thu_bac(x) is None
        })
        self.assertEqual(khong_ro, [])


def van_ban(so_hieu: str, than: str, co_quan: str = "BỘ GIÁO DỤC VÀ ĐÀO TẠO") -> str:
    return f"{co_quan}\nSố: {so_hieu} Hà Nội, ngày 3 tháng 3 năm 2026\nCăn cứ Luật;\nĐiều 1. Phạm vi\n{than}"


def kho_mau():
    noi_dung = {
        "tt22.pdf": van_ban("22/2021/TT-BGDĐT", "Đánh giá học sinh trung học."),
        "nd81.pdf": van_ban("81/2021/NĐ-CP", "Học phí.", "CHÍNH PHỦ"),
        # Công văn kể lại việc sửa Thông tư - không tự nó sửa được Thông tư.
        "cv.pdf": van_ban(
            "1234/BGDĐT-GDTrH", "Đề nghị các Sở chuẩn bị sửa đổi, bổ sung Thông tư số 22/2021/TT-BGDĐT."
        ),
        # Thông tư không thay được Nghị định; Nghị định không "hướng dẫn" Thông tư.
        "tt30.pdf": van_ban("30/2026/TT-BGDĐT", "Thông tư này thay thế Nghị định số 81/2021/NĐ-CP."),
        "nd99.pdf": van_ban(
            "99/2026/NĐ-CP", "Nghị định này hướng dẫn thi hành Thông tư số 22/2021/TT-BGDĐT.", "CHÍNH PHỦ"
        ),
        # Cùng cấp: hợp lệ.
        "tt31.pdf": van_ban("31/2026/TT-BGDĐT", "Thông tư này thay thế Thông tư số 22/2021/TT-BGDĐT."),
        "PL31.docx": "PHỤ LỤC\n(Kèm theo Thông tư số 31/2026/TT-BGDĐT ngày 3/3/2026)\nMẫu 01",
    }
    ho_so = vm.xay_dung_ho_so(noi_dung)
    return qh.SoQuanHe(ho_so, hl.xay_dung(noi_dung, ho_so), so_tay={})


class DoThiTests(unittest.TestCase):
    def setUp(self):
        self.so = kho_mau()

    def test_loai_quan_he_trai_thu_bac(self):
        trai = {(q.tu, q.loai, q.den) for q in self.so.quan_he_trai_thu_bac}
        self.assertEqual(trai, {
            ("1234/BGDĐT-GDTrH", "sua_doi", "22/2021/TT-BGDĐT"),
            ("30/2026/TT-BGDĐT", "thay_the", "81/2021/NĐ-CP"),
            ("99/2026/NĐ-CP", "huong_dan", "22/2021/TT-BGDĐT"),
        })
        dang_dung = {(q.tu, q.loai, q.den) for q in self.so.quan_he}
        self.assertIn(("31/2026/TT-BGDĐT", "thay_the", "22/2021/TT-BGDĐT"), dang_dung)
        self.assertFalse(trai & dang_dung)
        # Nghị định không bị gắn nhãn "đã bị thay" vì một câu trích nhầm.
        self.assertEqual(self.so.tinh_trang_nut("81/2021/NĐ-CP")["code"], "con_hieu_luc")

    def test_so_tay_van_duoc_ghi_de(self):
        # Quan hệ nhập tay đã đối chiếu thì giữ, kể cả khi bảng cấp nói khác.
        noi_dung = {"cv.pdf": van_ban("1234/BGDĐT-GDTrH", "Nội dung.")}
        ho_so = vm.xay_dung_ho_so(noi_dung)
        so = qh.SoQuanHe(ho_so, hl.xay_dung(noi_dung, ho_so), so_tay={"quan_he": [
            {"tu": "1234/BGDĐT-GDTrH", "loai": "thay_the", "den": "1000/BGDĐT-GDTrH"},
        ]})
        self.assertEqual(len(so.quan_he), 1)

    def test_mo_ta_va_cap_theo_tep(self):
        self.assertEqual(self.so.mo_ta_thu_bac("nd81.pdf"), "Nghị định - văn bản quy phạm pháp luật")
        self.assertTrue(self.so.mo_ta_thu_bac("cv.pdf").startswith("Công văn - văn bản hành chính"))
        self.assertEqual(self.so.cap_cua_tep("cv.pdf"), 9)
        # Phụ lục tách tệp theo văn bản chính của nó.
        self.assertEqual(self.so.cap_cua_tep("PL31.docx"), 5)
        self.assertIsNone(self.so.mo_ta_thu_bac("khong_co.pdf"))

    def test_xuat_va_thong_ke(self):
        bang = self.so.xuat()
        self.assertEqual(bang["van_ban"]["81/2021/NĐ-CP"]["thu_bac"], 3)
        self.assertEqual(len(bang["quan_he_trai_thu_bac"]), 3)
        self.assertEqual(self.so.thong_ke()["quan_he_trai_thu_bac_da_loai"], 3)


class XepHangTests(unittest.TestCase):
    NOI_DUNG = "Hội đồng xét công nhận tốt nghiệp trung học cơ sở do Chủ tịch Ủy ban nhân dân thành lập gồm"

    def _hai_ban(self, cap_cu, cap_moi):
        cu = Document(page_content=self.NOI_DUNG + " trưởng phòng giáo dục.", metadata={
            "source_file": "cu.pdf", "_ngay_van_ban": "2020-12-20", "_rrf_score": 0.02, "_thu_bac": cap_cu,
        })
        moi = Document(page_content=self.NOI_DUNG + " chủ tịch xã.", metadata={
            "source_file": "moi.pdf", "_ngay_van_ban": "2026-02-25", "_rrf_score": 0.02, "_thu_bac": cap_moi,
        })
        return cu, moi

    def _diem(self, cap_cu, cap_moi):
        from hybrid_retrieval import xep_hang_theo_lien_quan

        cu, moi = self._hai_ban(cap_cu, cap_moi)
        xep_hang_theo_lien_quan("hội đồng xét tốt nghiệp gồm ai", [cu, moi], 2)
        return cu.metadata["_retrieval_score"], moi.metadata["_retrieval_score"]

    def test_cong_van_moi_hon_khong_vuot_thong_tu(self):
        cu, moi = self._diem(5, 9)
        self.assertEqual(cu, moi)

    def test_giua_van_ban_quy_pham_van_uu_tien_ban_moi(self):
        cu, moi = self._diem(5, 5)
        self.assertGreater(moi, cu)
        cu, moi = self._diem(9, 5)
        self.assertGreater(moi, cu)

    def test_khong_biet_cap_thi_giu_nhu_cu(self):
        cu, moi = self._diem(None, None)
        self.assertGreater(moi, cu)


class PromptTests(unittest.TestCase):
    def test_dong_loai_trong_khoi_bang_chung(self):
        from main import tao_rag_chain
        from rag_service import RAGService

        service = RAGService.__new__(RAGService)
        service.so_quan_he = kho_mau()
        service._doan_theo_tep = {}
        doc = Document(page_content="Đề nghị chuẩn bị.", metadata={"source_file": "cv.pdf"})
        docs, _ = service._them_van_ban_di_kem([doc], "chuẩn bị gì")
        _, format_docs = tao_rag_chain(None, lambda _: "")
        self.assertIn(
            "Loại: Công văn - văn bản hành chính, không phải văn bản quy phạm pháp luật",
            format_docs(docs),
        )
        self.assertNotIn("_loai_van_ban", doc.metadata)

    def test_quy_tac_thu_bac_chi_khi_nhieu_cap(self):
        from rag_service import RAGService

        service = RAGService.__new__(RAGService)
        service.so_quan_he = kho_mau()
        doc = lambda ten: Document(page_content="x", metadata={"source_file": ten})  # noqa: E731
        self.assertIn("THỨ BẬC VĂN BẢN", service._ghi_chu_thu_bac([doc("cv.pdf"), doc("tt22.pdf")]))
        self.assertIsNone(service._ghi_chu_thu_bac([doc("tt22.pdf"), doc("tt31.pdf")]))
        self.assertIsNone(service._ghi_chu_thu_bac([doc("tt22.pdf"), doc("sgk.pdf")]))


if __name__ == "__main__":
    unittest.main()
