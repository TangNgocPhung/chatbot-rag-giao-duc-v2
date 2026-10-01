"""Câu hỏi thủ tục: nhận diện, đoạn mở đầu danh sách hồ sơ, cụm thời hạn."""

import unittest

import thu_tuc as tt


class ThuTucTests(unittest.TestCase):
    def test_nhan_ra_cau_hoi_thu_tuc(self):
        for cau in (
            "Hồ sơ chuyển trường gồm những gì?",
            "Xin cấp bản sao bằng tốt nghiệp nộp ở đâu?",
            "Công nhận văn bằng nước ngoài mất bao lâu?",
            "Cần chuẩn bị giấy tờ gì để xin học lại?",
        ):
            self.assertTrue(tt.la_cau_hoi_thu_tuc(cau), cau)
        self.assertFalse(tt.la_cau_hoi_thu_tuc("Giáo viên dạy bao nhiêu tiết một tuần?"))

    def test_mo_dau_danh_sach_ho_so(self):
        self.assertTrue(tt.mo_dau_danh_sach_ho_so(
            "Điều 5. Hồ sơ chuyển trường\n1. Hồ sơ chuyển trường gồm các giấy tờ sau:\na) Đơn xin chuyển trường;"
        ))
        self.assertTrue(tt.mo_dau_danh_sach_ho_so("Hồ sơ đề nghị công nhận bao gồm:\n- Tờ khai"))
        self.assertFalse(tt.mo_dau_danh_sach_ho_so("Hồ sơ được lưu tại văn phòng nhà trường."))

    def test_trich_thoi_han_giu_moc(self):
        self.assertEqual(
            tt.trich_thoi_han(
                "Trong thời hạn 15 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ, Sở có trách nhiệm trả lời. "
                "Chậm nhất sau 3 ngày làm việc, trường phải gửi hồ sơ. Học sinh học 4 năm."
            ),
            ["Trong thời hạn 15 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ", "Chậm nhất sau 3 ngày làm việc"],
        )

    def test_ghi_chu_prompt(self):
        ghi_chu = tt.ghi_chu_prompt([(2, "trong thời hạn 15 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ")])
        self.assertIn("liệt kê ĐỦ từng giấy tờ", ghi_chu)
        self.assertIn('[2] "trong thời hạn 15 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ"', ghi_chu)
        self.assertNotIn("Thời hạn trong các khối", tt.ghi_chu_prompt([]))


if __name__ == "__main__":
    unittest.main()
