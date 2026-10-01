"""Tham chiếu chéo giữa các Điều và định nghĩa thuật ngữ."""

import os
import unittest
from unittest import mock

from langchain_core.documents import Document

import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import tham_chieu as tc
import van_ban_meta as vm

DIEU_8 = (
    "Điều 8. Đăng ký học phần\n"
    "1. Sinh viên được đăng ký tối đa 25 tín chỉ, trừ trường hợp quy định tại khoản 2 Điều 9 "
    "Quy chế này.\n"
    "2. Việc miễn học phí thực hiện theo Điều 10 Nghị định số 115/2020/NĐ-CP.\n"
    "3. Theo khoản 1 Điều này, giáo viên cốt cán hướng dẫn sinh viên."
)


class TrichThamChieuTests(unittest.TestCase):
    def test_cac_dang_vien_dan(self):
        ket_qua = tc.trich_tham_chieu(
            DIEU_8 + "\n4. Xem điểm a khoản 3 Điều 12 và Điều 5 Luật Giáo dục đại học.", 8
        )
        self.assertEqual(
            [(t.dieu, t.khoan, t.diem, t.so_hieu, t.tran) for t in ket_qua],
            [
                (9, 2, None, None, False),
                (10, None, None, "115/2020/NĐ-CP", False),
                (12, 3, "a", None, True),
            ],
        )
        self.assertEqual(ket_qua[0].cum, "khoản 2 Điều 9")

    def test_bo_tieu_de_dieu_va_chinh_dieu_dang_doc(self):
        self.assertEqual(tc.trich_tham_chieu("Điều 8. Đăng ký\nNội dung theo Điều 8.", 8), [])
        # "Điều 9." đầu dòng là tiêu đề Điều 9 dính vào chunk, không phải viện dẫn.
        self.assertEqual(tc.trich_tham_chieu("Hết Điều 8.\nĐiều 9. Ngoại lệ", 8), [])

    def test_van_ban_chi_goi_ten_bi_bo(self):
        self.assertEqual(tc.trich_tham_chieu("theo Điều 5 Luật Giáo dục đại học", 1), [])

    def test_khong_lap(self):
        self.assertEqual(len(tc.trich_tham_chieu("Điều 9 Quy chế này; lại Điều 9 Quy chế này", 1)), 1)

    def test_so_dieu(self):
        self.assertEqual(tc.so_dieu("Điều 12. Đăng ký học phần"), 12)
        self.assertIsNone(tc.so_dieu("Chương II"))
        self.assertIsNone(tc.so_dieu(None))


class TrichKhoanTests(unittest.TestCase):
    DIEU_9 = (
        "Điều 9. Ngoại lệ\n1. Học kỳ phụ tối đa 12 tín chỉ, hạn chót ngày\n15. tháng sau.\n"
        "2. Sinh viên năm cuối được đăng ký tối đa 30 tín chỉ.\n3. Trường hợp khác."
    )

    def test_cat_dung_khoan(self):
        self.assertEqual(
            tc.trich_khoan(self.DIEU_9, 2), "2. Sinh viên năm cuối được đăng ký tối đa 30 tín chỉ."
        )
        # "15." lạc dòng không phải khoản 15 cũng không cắt ngang khoản 1.
        self.assertTrue(tc.trich_khoan(self.DIEU_9, 1).endswith("15. tháng sau."))

    def test_khong_co_khoan_thi_lay_dau_dieu(self):
        self.assertTrue(tc.trich_khoan(self.DIEU_9, 7).startswith("Điều 9. Ngoại lệ"))
        self.assertTrue(tc.trich_khoan(self.DIEU_9, None).startswith("Điều 9. Ngoại lệ"))

    def test_gioi_han_do_dai(self):
        self.assertLessEqual(len(tc.trich_khoan("Điều 1. " + "chữ " * 500, None)), tc.DO_DAI_TOI_DA + 2)


DIEU_2 = (
    "Điều 2. Giải thích từ ngữ\nTrong Quy chế này, các từ ngữ dưới đây được hiểu như sau:\n"
    "1. Giáo viên cốt cán là giáo viên có năng lực chuyên môn tốt, được chọn để hỗ trợ đồng nghiệp.\n"
    "2. “Học bạ số” là học bạ được lập dưới dạng điện tử.\n"
    "3. Học sinh: là người đang học tại trường.\n"
    "4. Chương trình đào tạo liên thông là chương trình dành cho người đã có văn bằng khác."
)


class DinhNghiaTests(unittest.TestCase):
    def test_trich_thuat_ngu(self):
        self.assertEqual(
            [t for t, _ in tc.trich_dinh_nghia(DIEU_2)],
            ["Giáo viên cốt cán", "Học bạ số", "Học sinh", "Chương trình đào tạo liên thông"],
        )
        self.assertTrue(tc.la_dieu_giai_thich("Điều 2. Giải thích từ ngữ"))
        self.assertFalse(tc.la_dieu_giai_thich("Điều 3. Đối tượng áp dụng"))

    def test_uu_tien_thuat_ngu_trong_cau_hoi(self):
        dinh_nghia = tc.trich_dinh_nghia(DIEU_2)
        ket_qua = tc.dinh_nghia_lien_quan(
            dinh_nghia, "Học bạ số lưu ở đâu?", ["chương trình đào tạo liên thông kéo dài 2 năm"]
        )
        self.assertEqual([(t, co) for t, _, co in ket_qua], [
            ("Học bạ số", True), ("Chương trình đào tạo liên thông", False),
        ])

    def test_thuat_ngu_ngan_chi_keo_khi_cau_hoi_nhac(self):
        dinh_nghia = tc.trich_dinh_nghia(DIEU_2)
        # "Học sinh" có ở mọi đoạn: chỉ đoạn nhắc thì không kéo.
        self.assertEqual(tc.dinh_nghia_lien_quan(dinh_nghia, "Mấy giờ vào lớp?", ["học sinh vào lớp"]), [])
        self.assertEqual(
            [t for t, _, _ in tc.dinh_nghia_lien_quan(dinh_nghia, "Học sinh là ai?", [])], ["Học sinh"]
        )


def chunk(ten: str, noi_dung: str, trang: int = 1) -> Document:
    return Document(page_content=noi_dung, metadata={
        "source_file": ten, "article": noi_dung.split("\n", 1)[0][:80], "so_trang": trang,
    })


def dich_vu():
    """Quy chế 8/2021 (Điều 2, 8, 9 - Điều 9 dài, chia hai chunk), Nghị định
    115/2020 (Điều 10) và Thông tư 5/2026 sửa đổi Quy chế."""
    from rag_service import RAGService

    dau = "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: {} Hà Nội, ngày 3 tháng 3 năm {}\nTHÔNG TƯ\nCăn cứ Luật;\n"
    cac_chunk = {
        "qc.pdf": [
            chunk("qc.pdf", DIEU_2, 1),
            chunk("qc.pdf", DIEU_8, 3),
            chunk("qc.pdf", "Điều 9. Ngoại lệ\n1. Học kỳ phụ tối đa 12 tín chỉ.", 4),
            chunk("qc.pdf", "Điều 9. Ngoại lệ\n2. Sinh viên năm cuối được đăng ký tối đa 30 tín chỉ.", 5),
        ],
        "nd115.pdf": [chunk("nd115.pdf", "Điều 10. Miễn học phí\nMiễn cho sinh viên khuyết tật.", 7)],
        "sua.pdf": [chunk(
            "sua.pdf",
            "Điều 1. Sửa đổi, bổ sung một số điều của Thông tư số 8/2021/TT-BGDĐT\n"
            "1. Khoản 2 Điều 9 được sửa đổi như sau: tối đa 28 tín chỉ.",
        )],
    }
    noi_dung = {
        "qc.pdf": dau.format("8/2021/TT-BGDĐT", 2021) + "Điều 1. Phạm vi\nQuy chế đào tạo.",
        "nd115.pdf": dau.format("115/2020/NĐ-CP", 2020) + "Điều 1. Phạm vi\nHọc phí.",
        "sua.pdf": dau.format("5/2026/TT-BGDĐT", 2026)
        + "Điều 1. Phạm vi\nSửa đổi, bổ sung một số điều của Thông tư số 8/2021/TT-BGDĐT.",
    }
    ho_so = vm.xay_dung_ho_so(noi_dung)
    service = RAGService.__new__(RAGService)
    service.so_quan_he = qh.SoQuanHe(ho_so, hl.xay_dung(noi_dung, ho_so), so_tay={})
    service._doan_theo_tep = cac_chunk
    return service, cac_chunk


@mock.patch.dict(os.environ, {"RAG_SO_DOAN_THAM_CHIEU": "2"})
class TangDichVuTests(unittest.TestCase):
    def setUp(self):
        self.service, self.chunk = dich_vu()
        self.dieu_8 = self.chunk["qc.pdf"][1]

    def test_keo_khoan_duoc_vien_dan_va_dieu_cua_van_ban_khac(self):
        docs = self.service._them_tham_chieu([self.dieu_8], "Sinh viên đăng ký tối đa bao nhiêu tín chỉ?")
        self.assertEqual(len(docs), 3)
        khoan_2 = docs[1]
        self.assertEqual(khoan_2.page_content, "2. Sinh viên năm cuối được đăng ký tối đa 30 tín chỉ.")
        # Trang của chunk thật sự chứa khoản 2, không phải chunk đầu Điều 9.
        self.assertEqual(khoan_2.metadata["so_trang"], 5)
        self.assertEqual(khoan_2.metadata["_di_kem"]["evidence"], 1)
        self.assertEqual(khoan_2.metadata["_di_kem"]["vai_tro"], "Điều khoản được viện dẫn (khoản 2 Điều 9)")
        self.assertEqual(docs[2].metadata["source_file"], "nd115.pdf")
        # Đoạn trong docstore dùng chung, không bị gắn thông tin của lượt này.
        self.assertNotIn("_di_kem", self.chunk["qc.pdf"][3].metadata)

    def test_dinh_nghia_thuat_ngu_trong_cau_hoi_dung_truoc(self):
        with mock.patch.dict(os.environ, {"RAG_SO_DOAN_THAM_CHIEU": "1"}):
            docs = self.service._them_tham_chieu([self.dieu_8], "Giáo viên cốt cán hướng dẫn mấy sinh viên?")
        self.assertEqual(len(docs), 2)
        self.assertTrue(docs[1].page_content.startswith("1. Giáo viên cốt cán là"))
        self.assertEqual(docs[1].metadata["_di_kem"]["vai_tro"], "Định nghĩa thuật ngữ (Giáo viên cốt cán)")

    def test_khong_keo_lai_dieu_da_co(self):
        docs = self.service._them_tham_chieu(
            [self.dieu_8, self.chunk["qc.pdf"][3], self.chunk["nd115.pdf"][0]], "tín chỉ"
        )
        # Điều 9 và Điều 10 đã có trong ngữ cảnh: chỉ còn định nghĩa thuật ngữ
        # đặc thù mà Điều 8 nhắc tới ("giáo viên cốt cán").
        them = [d.metadata["_di_kem"]["vai_tro"] for d in docs[3:]]
        self.assertEqual(them, ["Định nghĩa thuật ngữ (Giáo viên cốt cán)"])

    def test_van_ban_sua_doi_bo_vien_dan_tran(self):
        docs = self.service._them_tham_chieu([self.chunk["sua.pdf"][0]], "tối đa bao nhiêu tín chỉ")
        self.assertEqual(len(docs), 1)

    def test_tat_bang_bien_moi_truong(self):
        with mock.patch.dict(os.environ, {"RAG_SO_DOAN_THAM_CHIEU": "0"}):
            self.assertEqual(len(self.service._them_tham_chieu([self.dieu_8], "tín chỉ")), 1)

    def test_prompt_noi_ro_vi_sao_khoi_co_mat(self):
        from main import tao_rag_chain

        _, format_docs = tao_rag_chain(None, lambda _: "")
        ngu_canh = format_docs(self.service._them_tham_chieu([self.dieu_8], "tín chỉ"))
        self.assertIn("Đi kèm: Điều khoản được viện dẫn (khoản 2 Điều 9) của EVIDENCE 1", ngu_canh)


if __name__ == "__main__":
    unittest.main()
