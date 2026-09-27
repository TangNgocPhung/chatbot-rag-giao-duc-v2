"""Định mức tiết dạy giáo viên phổ thông theo Thông tư 05/2025/TT-BGDĐT.

Câu thật 24/9/2026 "tiết dạy của GV THPT cấp 3": truy hồi đã đưa đúng Điều 7
vào bằng chứng số 1 mà qwen3.5:4b vẫn kết luận "19 tiết". Con số trong bảng
9 dòng phải do Python tra, mọi con số dưới đây đối chiếu nguyên văn Thông tư.
"""

import unittest

import dinh_muc_tiet_day_pho_thong as pt


def tinh(cau_hoi):
    ts = pt.nhan_dien(cau_hoi)
    assert ts is not None, f"không nhận: {cau_hoi}"
    return pt.tinh(ts)


class DinhMucTheoCapHocTests(unittest.TestCase):
    def test_cau_that_gv_thpt_cap_3(self):
        kq = tinh("tiết dạy của GV THPT cấp 3")
        self.assertEqual((kq.dinh_muc_tuan, kq.dinh_muc_nam), (17, 595))

    def test_ba_cap_hoc_thuong(self):
        self.assertEqual(tinh("giáo viên tiểu học dạy bao nhiêu tiết một tuần").dinh_muc_tuan, 23)
        self.assertEqual(tinh("định mức tiết dạy giáo viên THCS").dinh_muc_tuan, 19)
        self.assertEqual(tinh("dinh muc tiet day giao vien trung hoc pho thong").dinh_muc_tuan, 17)

    def test_truong_dac_thu(self):
        self.assertEqual(tinh("định mức tiết dạy GV trường dân tộc nội trú THPT").dinh_muc_tuan, 15)
        self.assertEqual(tinh("định mức tiết dạy GV trường dân tộc bán trú tiểu học").dinh_muc_tuan, 21)
        self.assertEqual(tinh("định mức tiết dạy giáo viên trường khuyết tật cấp THCS").dinh_muc_tuan, 17)

    def test_du_bi_dai_hoc_12_tiet_28_tuan(self):
        kq = tinh("giáo viên trường dự bị đại học dạy bao nhiêu tiết")
        self.assertEqual((kq.dinh_muc_tuan, kq.dinh_muc_nam), (12, 336))

    def test_hieu_truong_pho_hieu_truong(self):
        self.assertEqual(tinh("hiệu trưởng trường THPT dạy mấy tiết một tuần").dinh_muc_tuan, 2)
        self.assertEqual(tinh("phó hiệu trưởng THCS dạy bao nhiêu tiết").dinh_muc_tuan, 4)

    def test_hieu_truong_kiem_nhiem_khong_duoc_tru(self):
        kq = tinh("hiệu trưởng kiêm bí thư chi bộ dạy bao nhiêu tiết")
        self.assertEqual(kq.dinh_muc_tuan, 2)
        self.assertTrue(any("Điều 8 khoản 4" in c for c in kq.canh_bao))


class KhoanGiamTests(unittest.TestCase):
    def test_chu_nhiem_va_to_truong(self):
        kq = tinh("giáo viên THCS chủ nhiệm kiêm tổ trưởng dạy bao nhiêu tiết")
        self.assertEqual(kq.dinh_muc_tuan, 19 - 4 - 3)

    def test_nuoi_con_tieu_hoc_4_tiet_cap_khac_3_tiet(self):
        self.assertEqual(tinh("định mức tiết dạy giáo viên tiểu học nuôi con dưới 12 tháng").dinh_muc_tuan, 19)
        self.assertEqual(tinh("định mức tiết dạy giáo viên THPT nuôi con dưới 12 tháng").dinh_muc_tuan, 14)

    def test_bi_thu_chi_bo_theo_quy_mo_truong(self):
        self.assertEqual(tinh("GV THPT kiêm bí thư chi bộ trường 30 lớp vùng 2 dạy bao nhiêu tiết").dinh_muc_tuan, 13)
        self.assertEqual(tinh("GV THPT kiêm bí thư chi bộ trường 20 lớp vùng 1 dạy bao nhiêu tiết").dinh_muc_tuan, 13)
        kq = tinh("GV THPT kiêm bí thư chi bộ dạy bao nhiêu tiết")
        self.assertEqual(kq.dinh_muc_tuan, 14)
        self.assertTrue(any("28 lớp" in c for c in kq.canh_bao))

    def test_to_truong_quan_ly_hoc_sinh_khong_tinh_hai_lan(self):
        kq = tinh("giáo viên trường dân tộc nội trú THPT làm tổ trưởng tổ quản lý học sinh định mức bao nhiêu")
        self.assertEqual([kg.khoa for kg in kq.tham_so.khoan_giam], ["to_truong_qlhs"])

    def test_giao_vu_khong_tru_ma_canh_bao(self):
        kq = tinh("giáo viên THPT kiêm giáo vụ định mức bao nhiêu tiết")
        self.assertEqual(kq.dinh_muc_tuan, 17)
        self.assertTrue(any("hiệu trưởng quyết định" in c for c in kq.canh_bao))

    def test_cong_doan_ngoai_kho(self):
        kq = tinh("giáo viên THPT chủ nhiệm kiêm công đoàn định mức bao nhiêu")
        self.assertEqual(kq.dinh_muc_tuan, 13)
        self.assertTrue(any("08/2016" in c for c in kq.canh_bao))

    def test_qua_hai_nhiem_vu_kiem_nhiem(self):
        kq = tinh("giáo viên THPT chủ nhiệm kiêm tổ trưởng, văn thư định mức bao nhiêu")
        self.assertTrue(any("tối đa 2 nhiệm vụ" in c for c in kq.canh_bao))

    def test_day_vuot_qua_50_phan_tram(self):
        kq = tinh("GV THPT đang dạy 26 tiết/tuần thì vượt định mức bao nhiêu")
        self.assertEqual(kq.tiet_vuot_tuan, 9)
        self.assertTrue(any("Điều 3 khoản 2" in c for c in kq.canh_bao))


class PhamViTests(unittest.TestCase):
    def khong_nhan(self, cau_hoi):
        self.assertIsNone(pt.nhan_dien(cau_hoi), f"nhận nhầm: {cau_hoi}")

    def test_cau_hoi_ve_mot_tiet_day_cu_the(self):
        self.khong_nhan("soạn tiết dạy Toán THPT theo công văn 5512")
        self.khong_nhan("một tiết dạy THPT bao nhiêu phút")
        self.khong_nhan("môn Toán lớp 10 học bao nhiêu tiết")

    def test_ngoai_thong_tu_05(self):
        self.khong_nhan("định mức tiết dạy giáo viên GDTX")
        self.khong_nhan("giảng viên đại học dạy bao nhiêu tiết")
        self.khong_nhan("giáo viên mầm non dạy bao nhiêu tiết")
        self.khong_nhan("giáo viên tổng phụ trách Đội THCS dạy bao nhiêu tiết")

    def test_so_sanh_hoac_thieu_cap_hoc_de_cho_rag(self):
        self.khong_nhan("giáo viên THCS và THPT dạy bao nhiêu tiết")
        self.khong_nhan("định mức tiết dạy là bao nhiêu")
        # Điều 7 không có dòng cho trường dân tộc bán trú cấp THPT.
        self.khong_nhan("định mức tiết dạy GV trường dân tộc bán trú THPT")

    def test_hoi_can_cu_de_cho_rag(self):
        self.khong_nhan("định mức tiết dạy giáo viên THPT quy định ở văn bản nào")


if __name__ == "__main__":
    unittest.main()
