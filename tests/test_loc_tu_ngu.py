"""Chặn câu hỏi chửi thề, tục tĩu, 18+ mà không chặn nhầm câu hỏi học tập.

Hai kiểu hỏng cần chốt chặn, và kiểu thứ hai nguy hiểm hơn:
  - Bỏ sót: viết lách luật ("đ.ị.t", "l0z", "vcllll") lọt qua bộ lọc.
  - Chặn nhầm: bỏ dấu đi thì "lồn" thành "lon", "cặc" thành "các", "buồi"
    thành "buổi", "đéo" thành "đeo". Một bộ lọc chặn "Các môn học lớp 10" hay
    "Lịch buổi học" thì làm hỏng chính việc trợ lý sinh ra để làm, mà người
    dùng chỉ thấy bị mắng vô cớ chứ không biết vì sao.
"""

import unittest
from unittest.mock import patch

import loc_tu_ngu

# (câu, nhóm phải báo)
CAU_VI_PHAM = [
    ("Địt mẹ mày", "chui_the"),
    ("ĐỤ MÁ cái hệ thống này", "chui_the"),
    ("đéo hiểu gì cả", "chui_the"),
    ("deo hieu gi het", "chui_the"),
    ("dcm trả lời sai rồi", "chui_the"),
    ("vcl thật", "chui_the"),
    ("clgt", "chui_the"),
    ("fuck this bot", "chui_the"),
    ("cái lồn gì vậy", "tuc_tiu"),
    ("cho xem phim sex", "tinh_duc"),
    ("phim heo ở đâu", "tinh_duc"),
    ("thằng ngu này", "xuc_pham"),
    ("đồ óc chó", "xuc_pham"),
]

# Viết lách: dấu câu, khoảng trắng chen giữa, lặp chữ, số thay chữ, ký tự
# vô hình, che bằng dấu *, chữ hoa, tổ hợp Unicode dạng tách (NFD, máy Mac).
CAU_VIET_LACH = [
    "đ.ị.t",
    "đ ị t m ẹ",
    "địttttt",
    "VCLLLLL",
    "cái l0z gì",
    "sh!t",
    "f*ck",
    "đ*t",
    "l​ồn",
    "v c l",
    "đmmmm",
    "đ.m.m",
]

# Câu học tập bình thường có chứa từ trùng với từ tục khi bỏ dấu, ghép chữ
# hoặc chữ hoa - mỗi câu từng là ứng viên chặn nhầm khi viết danh sách.
CAU_HOP_LE = [
    "Lịch buổi học tuần này",
    "Các môn học lớp 10",
    "con cac mon khac thi sao",          # còn các môn khác
    "an cac loai rau",                   # ăn các loại rau
    "đeo khẩu trang khi đến trường",
    "du lịch hè cho học sinh",
    "chích ngừa cho học sinh",
    "giải thích cho dễ hiểu",
    "giai thich cho de hieu",
    "tiền dư mà không dùng",
    "dù mẹ không cho phép",
    "du me khong cho phep",
    "lon nuoc ngot",
    "bù lon và đai ốc",
    "cái lồng chim",
    "đm tiết dạy giáo viên THPT",        # đm = định mức
    "1 dm bằng bao nhiêu cm",
    "VL 10 bài 3",
    "hạt óc chó có tốt không",
    "ốc lớn",
    "con chó của tôi",
    "đồ ngủ",
    "giáo dục giới tính lớp 8",
    "quan hệ tình dục an toàn",
    "sức khỏe sinh sản vị thành niên",
    "xử lý học sinh phát tán ảnh nóng",
    "Luật Trẻ em cấm văn hóa phẩm khiêu dâm",
    "chương trình cấp ba",
    "C++ là gì",
    "lớp 10a1",
    "classic assessment",
    "Cocktail party",
]


class LocTuNguTests(unittest.TestCase):
    def test_chan_tu_vi_pham_va_bao_dung_nhom(self):
        for cau, nhom in CAU_VI_PHAM:
            with self.subTest(cau=cau):
                ket_qua = loc_tu_ngu.kiem_tra(cau)
                self.assertTrue(ket_qua.vi_pham)
                self.assertIn(nhom, ket_qua.nhom)

    def test_chan_cach_viet_lach(self):
        for cau in CAU_VIET_LACH:
            with self.subTest(cau=cau):
                self.assertTrue(loc_tu_ngu.co_tu_ngu_khong_phu_hop(cau))

    def test_khong_chan_nham_cau_hoc_tap(self):
        for cau in CAU_HOP_LE:
            with self.subTest(cau=cau):
                ket_qua = loc_tu_ngu.kiem_tra(cau)
                self.assertFalse(ket_qua.vi_pham, ket_qua.tu_khop)

    def test_nfd_cung_bi_chan(self):
        import unicodedata
        self.assertTrue(loc_tu_ngu.co_tu_ngu_khong_phu_hop(
            unicodedata.normalize("NFD", "địt mẹ")
        ))

    def test_cau_rong(self):
        self.assertFalse(loc_tu_ngu.kiem_tra("").vi_pham)
        self.assertFalse(loc_tu_ngu.kiem_tra("   ...  ").vi_pham)

    def test_danh_sach_khong_dau_that_su_khong_dau(self):
        """Mục có dấu lọt vào TU_KHONG_DAU sẽ không bao giờ khớp, vì góc nhìn
        không dấu đã thay mọi chữ có dấu bằng ô trống - hỏng lặng lẽ."""
        from can_cu_van_ban import bo_dau
        for nhom, cac_tu in loc_tu_ngu.TU_KHONG_DAU.items():
            for tu in cac_tu:
                with self.subTest(nhom=nhom, tu=tu):
                    self.assertEqual(bo_dau(tu), tu)

    def test_tat_bang_bien_moi_truong(self):
        with patch.dict("os.environ", {"RAG_LOC_TU_NGU": "0"}):
            self.assertFalse(loc_tu_ngu.dang_bat())
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("RAG_LOC_TU_NGU", None)
            self.assertTrue(loc_tu_ngu.dang_bat())


class TuChoiTrongLuotHoiTests(unittest.TestCase):
    """Câu vi phạm không được đi tới truy hồi hay mô hình."""

    def test_stream_answer_tu_choi_truoc_khi_sinh(self):
        from rag_service import service

        with patch.object(service, "_sinh_cau_tra_loi") as sinh, \
                patch.dict("os.environ", {"RAG_LOC_TU_NGU": "1"}):
            su_kien = list(service.stream_answer("đ.m.m trả lời đi"))
        sinh.assert_not_called()
        self.assertEqual(
            [e["type"] for e in su_kien], ["sources", "token", "goi_y", "done"]
        )
        self.assertEqual(su_kien[1]["content"], loc_tu_ngu.LOI_NHAC)
        self.assertTrue(su_kien[-1]["abstained"])
        self.assertTrue(su_kien[-1]["ly_do_chan"].startswith("tu_ngu_khong_phu_hop"))

    def test_tat_loc_thi_cau_di_tiep(self):
        from rag_service import service

        with patch.object(service, "_sinh_cau_tra_loi", return_value=iter([])) as sinh, \
                patch.dict("os.environ", {"RAG_LOC_TU_NGU": "0"}):
            list(service.stream_answer("vcl"))
        sinh.assert_called_once()


if __name__ == "__main__":
    unittest.main()
