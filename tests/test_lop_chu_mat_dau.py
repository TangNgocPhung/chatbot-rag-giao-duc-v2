"""PDF có lớp chữ tiếng Việt mất dấu phải được OCR lại.

Máy scan HP tự OCR bằng bộ nhận dạng tiếng Anh rồi nhúng lớp chữ vào PDF. Lớp
chữ đủ dài nên trước đây được tin dùng thẳng, và Thông tư 05/2025 về định mức
tiết dạy nằm trong kho mà hỏi "tiết dạy của GV THPT" vẫn ra "không tìm thấy".
"""

import unittest

from ocr_pdf import lop_chu_mat_dau

# Nguyên văn lớp chữ của 05-bgddt.pdf trong chỉ mục VPS (24/9/2026).
MAT_DAU = (
    "a) Gido vien truing tieu hgc la 23 ti&, gido vien truing trung hgc co so. la "
    "19 ti6t, giao vien truing trung hoc pho thong la 17 ti6t; "
    "b) Gido vien truing pho thong dan tOc ban tria lieu hoc la 21 tie't, gido vien "
    "truang phO thong dan tOc ban tru trung hoc ca ser la 17 ti6t, giao vien truing pho "
    "th8ng dan tOc nOi frit trung hgc co so la 17 ti6t, gido vien truing phO thong dan "
    "tOc nOi tru trung hgc phO thong la 15 fiat; Dinh mut tiet day trong 01 nam hoc "
    "dugc xac dinh nhu sau, hieu truang phan cong giao vien giang day theo dinh mire "
    "tiet day trung binh trong 01 tuan va cac nhiem vu khac cua nha truong."
)

CO_DAU = (
    "a) Giáo viên trường tiểu học là 23 tiết, giáo viên trường trung học cơ sở là "
    "19 tiết, giáo viên trường trung học phổ thông là 17 tiết; b) Giáo viên trường "
    "phổ thông dân tộc bán trú tiểu học là 21 tiết, giáo viên trường phổ thông dân "
    "tộc bán trú trung học cơ sở là 17 tiết, giáo viên trường phổ thông dân tộc nội "
    "trú trung học phổ thông là 15 tiết; hiệu trưởng phân công giáo viên giảng dạy "
    "theo định mức tiết dạy trung bình trong 01 tuần và các nhiệm vụ khác."
)

TIENG_ANH = (
    "Digital competence framework for teachers. This document describes the six "
    "areas of competence that teachers need in order to use digital technologies "
    "effectively in the classroom, including professional engagement, digital "
    "resources, teaching and learning, assessment, empowering learners and "
    "facilitating learners' digital competence. Each area contains several "
    "competences with progression levels from newcomer to pioneer."
)


class LopChuMatDauTests(unittest.TestCase):
    def test_tieng_viet_mat_dau_phai_ocr_lai(self):
        self.assertTrue(lop_chu_mat_dau(MAT_DAU))

    def test_tieng_viet_co_dau_giu_nguyen(self):
        self.assertFalse(lop_chu_mat_dau(CO_DAU))

    def test_tieng_anh_khong_bi_nham(self):
        self.assertFalse(lop_chu_mat_dau(TIENG_ANH))

    def test_qua_it_chu_khong_ket_luan(self):
        self.assertFalse(lop_chu_mat_dau("giao vien truong trung hoc pho thong la 17 tiet"))


if __name__ == "__main__":
    unittest.main()
