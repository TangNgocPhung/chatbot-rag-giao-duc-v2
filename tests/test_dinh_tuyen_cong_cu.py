"""Định tuyến câu hỏi sang các công cụ tính bằng Python.

Bốn công cụ (tinh_luong, dinh_muc_tiet_day, danh_gia_hoc_sinh, tinh_toan) đều
chen vào TRƯỚC cache ngữ nghĩa và trước cả khâu truy hồi. Hai thứ dễ hỏng ở chỗ nối này, và cả hai
đều hỏng lặng lẽ:

  - Sai thứ tự thử: tinh_toan nhận cả những biểu thức trần trụi, đứng trước thì
    nó sẽ nuốt mất phần của ba công cụ có căn cứ pháp lý.
  - Sai chuỗi sự kiện: giao diện dựng câu trả lời theo đúng thứ tự sources →
    token → goi_y → done. Thiếu một sự kiện thì khung chat đứng im, không báo
    lỗi gì.
"""

import importlib
import unittest
from contextlib import ExitStack
from datetime import date
from unittest.mock import patch

from rag_service import RAGService


class DinhTuyenTests(unittest.TestCase):
    def setUp(self):
        self.service = RAGService()
        # Nhánh công cụ tính trả lời xong là thoát, không đụng tới chỉ mục -
        # nên chỉ cần qua được cổng kiểm tra trạng thái ở đầu hàm.
        self.service.status.state = "ready"

    def su_kien(self, cau_hoi):
        return list(self.service._sinh_cau_tra_loi(cau_hoi))

    def test_cau_so_hoc_di_sang_tinh_toan(self):
        su_kien = self.su_kien("12% của 2.340.000 là bao nhiêu")
        xong = su_kien[-1]
        self.assertEqual(xong["cong_cu"], "tinh_toan")
        self.assertIn("280.800", su_kien[1]["content"])

    def test_cau_tinh_luong_di_sang_tinh_luong(self):
        """Câu này vừa nói về tiền vừa có con số, nhưng phải về tay công cụ
        tính lương chứ không phải công cụ số học."""
        su_kien = self.su_kien("tính lương giáo viên THPT hạng III bậc 1")
        self.assertEqual(su_kien[-1]["cong_cu"], "tinh_luong")
        self.assertTrue(su_kien[-1]["tinh_luong"])

    def test_cau_dinh_muc_di_sang_dinh_muc_tiet_day(self):
        su_kien = self.su_kien(
            "giáo viên GDTX chủ nhiệm 1 lớp còn phải dạy bao nhiêu tiết/tuần"
        )
        self.assertEqual(su_kien[-1]["cong_cu"], "dinh_muc_tiet_day")
        self.assertFalse(su_kien[-1]["tinh_luong"])

    def test_cau_dinh_muc_pho_thong_di_sang_cong_cu_thong_tu_05(self):
        """Câu thật 24/9/2026 - trước đó ra "không tìm thấy", rồi "19 tiết"."""
        su_kien = self.su_kien("tiết dạy của GV THPT cấp 3")
        self.assertEqual(su_kien[-1]["cong_cu"], "dinh_muc_tiet_day_pho_thong")
        self.assertIn("17 tiết/tuần", su_kien[1]["content"])

    def test_cau_tinh_diem_di_sang_danh_gia_hoc_sinh(self):
        su_kien = self.su_kien(
            "điểm thường xuyên 8, 9, giữa kì 7, cuối kì 8 thì ĐTB bao nhiêu"
        )
        self.assertEqual(su_kien[-1]["cong_cu"], "danh_gia_hoc_sinh")
        self.assertIn("7,9", su_kien[1]["content"])

    def test_du_chuoi_su_kien_giao_dien_can(self):
        su_kien = self.su_kien("35 x 17")
        self.assertEqual(
            [s["type"] for s in su_kien],
            ["sources", "token", "goi_y", "done"],
        )

    def test_khong_goi_y_khi_khong_co_nguon(self):
        """Một phép tính số học thuần không dẫn tới văn bản nào trong kho, nên
        gợi ý kiểu "còn văn bản nào khác quy định nội dung này" là lạc đề."""
        su_kien = self.su_kien("35 x 17")
        self.assertEqual(su_kien[0]["sources"], [])
        self.assertEqual(su_kien[2]["goi_y"], [])

    def test_van_goi_y_khi_cau_tra_loi_co_nguon(self):
        su_kien = self.su_kien("tính lương giáo viên THPT hạng III bậc 1")
        self.assertTrue(su_kien[0]["sources"])
        self.assertTrue(su_kien[2]["goi_y"])

    def test_bo_qua_hau_kiem_vi_con_so_do_python_tinh(self):
        """Hậu kiểm đối chiếu từng con số với đoạn trích - đúng cho câu do mô
        hình sinh, vô nghĩa với kết quả tính ra vì không văn bản nào chứa sẵn
        con số đó."""
        xong = self.su_kien("35 x 17")[-1]
        self.assertTrue(xong["citations_ok"])
        self.assertTrue(xong["figures_ok"])


class MocThoiGianTests(unittest.TestCase):
    """Bốn công cụ có căn cứ pháp lý chỉ biết quy định hiện hành. Hỏi "năm
    2020" mà nhận phiếu lương tính theo lương cơ sở 2.340.000 (NĐ 73/2024) là
    sai lặng lẽ - câu đó phải đi qua RAG ở chế độ lich_su."""

    CONG_CU_PHAP_LY = (
        "tinh_luong", "dinh_muc_tiet_day",
        "dinh_muc_tiet_day_pho_thong", "danh_gia_hoc_sinh",
    )

    def setUp(self):
        self.service = RAGService()
        self.service.status.state = "ready"

    def su_kien(self, cau_hoi):
        """Chạy câu hỏi với truy hồi rỗng; trả về (chuỗi sự kiện, mock tra_loi
        của từng công cụ pháp lý). Mock bọc hàm thật nên vẫn định tuyến đúng."""
        vo_boc = {}
        with ExitStack() as ngan_xep:
            ngan_xep.enter_context(
                patch.object(self.service, "_retrieve", return_value=[])
            )
            for ten in self.CONG_CU_PHAP_LY:
                mo_dun = importlib.import_module(ten)
                vo_boc[ten] = ngan_xep.enter_context(
                    patch.object(mo_dun, "tra_loi", wraps=mo_dun.tra_loi)
                )
            return list(self.service._sinh_cau_tra_loi(cau_hoi)), vo_boc

    def test_hoi_luong_nam_da_qua_khong_dung_cong_cu(self):
        su_kien, vo_boc = self.su_kien("tính lương giáo viên THPT hạng III bậc 1 năm 2020")
        for mock in vo_boc.values():
            mock.assert_not_called()
        self.assertNotIn("cong_cu", su_kien[-1])

    def test_hoi_dinh_muc_ngay_da_qua_khong_dung_cong_cu(self):
        su_kien, vo_boc = self.su_kien("tiết dạy của GV THPT cấp 3 ngày 15/3/2019")
        for mock in vo_boc.values():
            mock.assert_not_called()
        self.assertNotIn("cong_cu", su_kien[-1])

    def test_hoi_luong_nam_sau_van_dung_cong_cu(self):
        """Mốc tương lai không phải lich_su: quy định hiện hành là thứ tốt nhất
        đang có, nên vẫn tính bằng công cụ."""
        su_kien, vo_boc = self.su_kien(
            f"tính lương giáo viên THPT hạng III bậc 1 năm {date.today().year + 1}"
        )
        vo_boc["tinh_luong"].assert_called_once()
        self.assertEqual(su_kien[-1]["cong_cu"], "tinh_luong")

    def test_nam_da_qua_van_thu_tinh_toan(self):
        """Số học thuần không phụ thuộc thời điểm nên tinh_toan vẫn được thử.
        (Tự nó hiện từ chối câu có mốc ngày - con số của mốc lẫn vào phép tính.)"""
        with patch("tinh_toan.tra_loi", return_value=None) as thu:
            self.su_kien("năm 2020: 12% của 2.340.000 là bao nhiêu")
        thu.assert_called_once()


if __name__ == "__main__":
    unittest.main()
