"""Đối tượng áp dụng: ô câu hỏi để trống mà bằng chứng trải nhiều trường hợp."""

import unittest

import doi_tuong_ap_dung as dt
import phan_loai_giao_duc as plgd

TIEU_HOC = (1, "Định mức tiết dạy của giáo viên tiểu học là 23 tiết một tuần.", None)
THCS = (2, "Định mức tiết dạy của giáo viên trung học cơ sở là 19 tiết một tuần.", None)
HOI = "Giáo viên dạy bao nhiêu tiết một tuần?"


class NhacToiTests(unittest.TestCase):
    def test_cap_hoc_ke_ca_suy_tu_lop(self):
        self.assertEqual(plgd.cap_hoc_nhac_toi("giáo viên lớp 3 dạy mấy tiết"), ["Tiểu học"])
        self.assertEqual(
            plgd.cap_hoc_nhac_toi("trung học cơ sở và tiểu học"), ["Tiểu học", "THCS"]
        )
        self.assertEqual(plgd.cap_hoc_nhac_toi(HOI), [])

    def test_dau_hieu_ngam_khong_tinh_la_da_chon_cap(self):
        # "tín chỉ", "sinh viên" cũng có ở cao đẳng: người hỏi chưa chọn cấp học.
        self.assertEqual(plgd.cap_hoc_nhac_toi("Sinh viên đăng ký tối đa bao nhiêu tín chỉ?"), [])
        self.assertEqual(plgd.cap_hoc_nhac_toi("sinh viên cao đẳng"), ["Giáo dục nghề nghiệp"])

    def test_cong_lap_khac_ngoai_cong_lap(self):
        self.assertEqual(dt.nhac_toi("trường ngoài công lập"), {"loai_hinh": {"ngoài công lập"}})
        self.assertEqual(dt.nhac_toi("trường công lập"), {"loai_hinh": {"công lập"}})
        self.assertEqual(dt.nhac_toi("trường tư thục và công lập")["loai_hinh"], {"công lập", "ngoài công lập"})

    def test_vung_dac_thu(self):
        self.assertEqual(dt.nhac_toi("xã đặc biệt khó khăn")["vung"], {"vùng đặc biệt khó khăn"})
        self.assertEqual(dt.nhac_toi("Học phí năm học 2026"), {})


class PhanTichTests(unittest.TestCase):
    def test_hai_khoi_hai_cap_hoc(self):
        mo_ho = dt.phan_tich(HOI, [TIEU_HOC, THCS])
        self.assertEqual(len(mo_ho), 1)
        self.assertEqual(mo_ho[0].chieu, "cap_hoc")
        self.assertEqual(mo_ho[0].gia_tri, {"Tiểu học": [1], "THCS": [2]})
        self.assertTrue(mo_ho[0].khac_nguon)

    def test_cau_hoi_da_dien_o_thi_khong_mo_ho(self):
        self.assertEqual(dt.phan_tich("Giáo viên tiểu học dạy bao nhiêu tiết?", [TIEU_HOC, THCS]), [])
        self.assertEqual(dt.phan_tich("Giáo viên lớp 7 dạy bao nhiêu tiết?", [TIEU_HOC, THCS]), [])

    def test_mot_khoi_liet_ke_nhieu_cap_chi_la_mo_ho_yeu(self):
        mo_ho = dt.phan_tich(HOI, [(1, "Áp dụng đối với trường tiểu học, trường trung học cơ sở.", None)])
        self.assertEqual(len(mo_ho), 1)
        self.assertFalse(mo_ho[0].khac_nguon)

    def test_cap_hoc_cua_tep_chi_dung_khi_dung_mot_cap(self):
        mo_ho = dt.phan_tich(HOI, [
            (1, "Giáo viên dạy 23 tiết.", ["Tiểu học"]),
            (2, "Giáo viên dạy 19 tiết.", ["THCS"]),
        ])
        self.assertEqual(mo_ho[0].gia_tri, {"Tiểu học": [1], "THCS": [2]})
        # Tệp gắn nhiều cấp (Thông tư chung cho phổ thông) không nói được đoạn thuộc cấp nào.
        self.assertEqual(dt.phan_tich(HOI, [
            (1, "Giáo viên dạy 23 tiết.", ["Tiểu học", "THCS"]),
            (2, "Giáo viên dạy 19 tiết.", ["THCS"]),
        ]), [])

    def test_mot_gia_tri_khong_phai_mo_ho_tru_vung(self):
        self.assertEqual(dt.phan_tich(HOI, [TIEU_HOC]), [])
        mo_ho = dt.phan_tich(HOI, [(1, "Giáo viên ở vùng đặc biệt khó khăn được giảm 2 tiết.", None)])
        self.assertEqual([m.chieu for m in mo_ho], ["vung"])


class DauRaTests(unittest.TestCase):
    def test_ghi_chu_prompt(self):
        self.assertIsNone(dt.ghi_chu_prompt([]))
        ghi_chu = dt.ghi_chu_prompt(dt.phan_tich(HOI, [TIEU_HOC, THCS]))
        self.assertIn("Câu hỏi chưa nói rõ cấp học; các khối nói về: Tiểu học [1]; THCS [2].", ghi_chu)
        self.assertIn("không gộp", ghi_chu)

    def test_cau_hoi_lam_ro_chi_khi_khac_nguon(self):
        self.assertEqual(
            dt.cau_hoi_lam_ro(HOI, dt.phan_tich(HOI, [TIEU_HOC, THCS])),
            ["Giáo viên dạy bao nhiêu tiết một tuần (Tiểu học)?", "Giáo viên dạy bao nhiêu tiết một tuần (THCS)?"],
        )
        mot_khoi = dt.phan_tich(HOI, [(1, "Áp dụng cho trường tiểu học, trung học cơ sở.", None)])
        self.assertEqual(dt.cau_hoi_lam_ro(HOI, mot_khoi), [])
        self.assertEqual(dt.cau_hoi_lam_ro("", dt.phan_tich(HOI, [TIEU_HOC, THCS])), [])

    def test_cau_hoi_lam_ro_dien_xong_o(self):
        # Câu gợi ý bấm vào phải tự giải được mơ hồ, không lặp lại vòng hỏi.
        for cau in dt.cau_hoi_lam_ro(HOI, dt.phan_tich(HOI, [TIEU_HOC, THCS])):
            self.assertEqual(dt.phan_tich(cau, [TIEU_HOC, THCS]), [], cau)

    def test_ghep_goi_y(self):
        self.assertEqual(dt.ghep_goi_y([], ["a", "b"], 3), ["a", "b"])
        self.assertEqual(dt.ghep_goi_y(["x", "y"], ["a", "x", "b"], 3), ["x", "y", "a"])
        self.assertEqual(dt.ghep_goi_y(["x", "y", "z"], ["a"], 3), ["x", "y", "z"])


if __name__ == "__main__":
    unittest.main()
