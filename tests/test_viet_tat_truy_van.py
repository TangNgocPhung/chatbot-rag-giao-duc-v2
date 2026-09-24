"""Viết tắt trong câu hỏi phải được bung ra cho cả hai nhánh truy hồi.

Câu thật 24/9/2026: "tiết dạy của GV THPT cấp 3" ra "không tìm thấy" dù
Thông tư 05/2025 nằm trong kho. Vector của câu gốc trôi về sách giáo viên
("GV", "HS") và "Bài 3"; không đoạn nào lọt từ nhánh vector nên bộ chặn lạc đề
từ chối luôn.
"""

import unittest

from hybrid_retrieval import mo_rong_truy_van, tach_tu_tieng_viet, viet_day_du


class VietDayDuTests(unittest.TestCase):
    def test_cau_that(self):
        self.assertEqual(
            viet_day_du("tiết dạy của GV THPT cấp 3"),
            "tiết dạy của giáo viên trung học phổ thông",
        )

    def test_cap_hoc_khong_co_ten_thi_thay_bang_ten(self):
        self.assertEqual(viet_day_du("giáo viên cấp 2"), "giáo viên trung học cơ sở")
        self.assertEqual(viet_day_du("học sinh cấp I"), "học sinh tiểu học")

    def test_khong_dung_vao_chu_thuong_va_hang(self):
        self.assertEqual(viet_day_du("Thông tư 05 quy định gì"), "Thông tư 05 quy định gì")
        self.assertEqual(viet_day_du("hạng III bậc 5"), "hạng III bậc 5")
        self.assertEqual(viet_day_du("cấp độ 3"), "cấp độ 3")


class MoRongBm25Tests(unittest.TestCase):
    def test_thpt_va_cap_3(self):
        q = "tiết dạy của GV THPT cấp 3"
        tokens = mo_rong_truy_van(tach_tu_tieng_viet(q), q)
        for tu in ("giáo", "viên", "trung", "phổ", "thông", "thpt"):
            self.assertIn(tu, tokens)

    def test_cap_3_khong_nhan_doi_tu(self):
        q = "giáo viên trung học phổ thông cấp 3"
        tokens = mo_rong_truy_van(tach_tu_tieng_viet(q), q)
        self.assertEqual(tokens.count("phổ"), 1)


class DoPhuIdfTests(unittest.TestCase):
    def test_cau_viet_tat_khong_bi_chan_oan(self):
        from langchain_core.documents import Document

        from tu_vung_kho import xay_dung_tu_vung

        doan = Document(
            page_content="Định mức tiết dạy trung bình trong 01 tuần: giáo viên trường "
                         "trung học phổ thông là 17 tiết.",
            metadata={"source_file": "05-bgddt.pdf"},
        )
        kho = [doan] + [
            Document(page_content=f"GV yêu cầu HS đọc bài {i}. Học sinh làm bài tập cấp độ {i}.")
            for i in range(50)
        ]
        tu_vung = xay_dung_tu_vung(kho)
        self.assertGreater(tu_vung.do_phu_idf("tiết dạy của GV THPT cấp 3", [doan]), 0.9)


if __name__ == "__main__":
    unittest.main()
