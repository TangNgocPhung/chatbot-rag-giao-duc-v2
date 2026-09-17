"""Công cụ tính điểm và xếp loại theo Thông tư 22/2021.

Ba chỗ dễ sai nhất, và cả ba đều ra một kết quả trông hợp lý:

  - ĐTBmhk KHÔNG phải trung bình cộng. Giữa kì nhân 2, cuối kì nhân 3, mẫu số
    là số điểm thường xuyên cộng 5. Cộng chia bình thường vẫn ra một con số rất
    gần đáp án đúng - gần tới mức không ai kiểm lại.
  - Làm tròn. Điểm rơi đúng ngưỡng 6,5 hay 8,0 thì lệch một phần mười là lệch
    cả mức xếp loại.
  - Khoản 3 Điều 9 cho nâng lên mức liền kề khi học sinh tụt hai mức chỉ vì
    đúng một môn. Bỏ sót quy tắc này là xếp sai loại cho đúng nhóm học sinh
    dễ bị thiệt nhất.

Con số trong test lấy từ nguyên văn Thông tư, và mỗi ĐTB đều đối chiếu với
phép tính tay ghi ngay trong test.
"""

import unittest

import danh_gia_hoc_sinh as dg


class LamTronTests(unittest.TestCase):
    """Điều 5 khoản 3 điểm b: lấy đến chữ số thập phân thứ nhất sau khi làm
    tròn số."""

    def test_lam_tron_nua_len(self):
        """round() của Python cho 8.2 vì số dấu phẩy động, còn sổ điểm ghi 8,3."""
        self.assertEqual(dg.lam_tron(8.25), 8.3)
        self.assertEqual(dg.lam_tron(6.45), 6.5)

    def test_lam_tron_xuong(self):
        self.assertEqual(dg.lam_tron(7.84), 7.8)
        self.assertEqual(dg.lam_tron(4.999), 5.0)


class DiemTrungBinhTests(unittest.TestCase):
    def test_dtb_mon_hoc_ki_dung_trong_so(self):
        """(8 + 9 + 2×7 + 3×8) ÷ (2 + 5) = 55 ÷ 7 = 7,857 → 7,9"""
        self.assertEqual(dg.dtb_mon_hoc_ki([8, 9], 7, 8), 7.9)

    def test_mau_so_theo_so_diem_thuong_xuyen(self):
        """Bốn điểm thường xuyên thì mẫu số là 9, không phải 7. Đây là chỗ mà
        một công thức ghim cứng mẫu số sẽ sai lặng lẽ."""
        # (8+8+8+8 + 2×8 + 3×8) ÷ (4+5) = 72 ÷ 9 = 8,0
        self.assertEqual(dg.dtb_mon_hoc_ki([8, 8, 8, 8], 8, 8), 8.0)

    def test_khong_co_diem_thuong_xuyen_thi_bao_loi(self):
        """Thà hỏng to còn hơn chia cho 5 rồi trả về một con số vô nghĩa."""
        with self.assertRaises(ValueError):
            dg.dtb_mon_hoc_ki([], 8, 8)

    def test_dtb_mon_ca_nam_hoc_ki_hai_nhan_doi(self):
        """(7,9 + 2×8,5) ÷ 3 = 24,9 ÷ 3 = 8,3 - không phải trung bình cộng
        hai học kì, vốn sẽ ra 8,2."""
        self.assertEqual(dg.dtb_mon_ca_nam(7.9, 8.5), 8.3)
        self.assertNotEqual(dg.dtb_mon_ca_nam(7.9, 8.5), dg.lam_tron((7.9 + 8.5) / 2))


class SoDiemThuongXuyenTests(unittest.TestCase):
    """Điều 6 khoản 2 điểm b - ba bậc theo số tiết/năm học."""

    def test_ba_bac_theo_so_tiet(self):
        self.assertEqual(dg.so_diem_thuong_xuyen(35), 2)
        self.assertEqual(dg.so_diem_thuong_xuyen(36), 3)
        self.assertEqual(dg.so_diem_thuong_xuyen(70), 3)
        self.assertEqual(dg.so_diem_thuong_xuyen(71), 4)
        self.assertEqual(dg.so_diem_thuong_xuyen(105), 4)


class XepLoaiTests(unittest.TestCase):
    def muc(self, diem, **kw):
        return dg.xep_loai_hoc_tap(diem, **kw).muc

    def test_muc_tot(self):
        """Mọi môn từ 6,5 và ít nhất 06 môn từ 8,0."""
        self.assertEqual(self.muc([8.5] * 8), "Tốt")
        self.assertEqual(self.muc([8.0] * 6 + [6.5, 7.0]), "Tốt")

    def test_thieu_mot_mon_tam_diem_thi_khong_con_la_tot(self):
        """Đúng 05 môn từ 8,0 là chưa đủ - văn bản đòi ít nhất 06."""
        self.assertEqual(self.muc([8.0] * 5 + [7.0, 7.0, 7.0]), "Khá")

    def test_muc_kha(self):
        self.assertEqual(self.muc([7.0] * 6 + [5.5, 5.5]), "Khá")

    def test_muc_dat(self):
        self.assertEqual(self.muc([6.0] * 8), "Đạt")

    def test_mot_mon_duoi_3_5_thi_khong_con_la_dat(self):
        """Mức Đạt đòi "không có môn học nào có ĐTBmhk, ĐTBmcn dưới 3,5 điểm"."""
        kq = dg.xep_loai_hoc_tap([6.0] * 7 + [3.4])
        self.assertEqual(kq.muc_truoc_khi_nang or kq.muc, "Chưa đạt")

    def test_mon_nhan_xet_chua_dat(self):
        """Mức Tốt và Khá đòi TẤT CẢ môn nhận xét mức Đạt; mức Đạt cho nhiều
        nhất 01 môn Chưa đạt."""
        self.assertEqual(self.muc([8.5] * 8, mon_nhan_xet_chua_dat=1), "Đạt")
        self.assertEqual(self.muc([8.5] * 8, mon_nhan_xet_chua_dat=2), "Chưa đạt")


class NangMucTests(unittest.TestCase):
    """Khoản 3 Điều 9 - tụt từ 02 mức trở lên chỉ vì duy nhất 01 môn thì được
    điều chỉnh lên mức liền kề."""

    def test_nang_tu_dat_len_kha(self):
        """Bảy môn 8,5 mà một môn 4,0: theo ngưỡng là Đạt, tụt hai mức so với
        Tốt chỉ vì một môn, nên lên Khá."""
        kq = dg.xep_loai_hoc_tap([8.5] * 7 + [4.0])
        self.assertEqual(kq.muc_truoc_khi_nang, "Đạt")
        self.assertEqual(kq.muc, "Khá")

    def test_chi_nang_mot_muc_khong_nang_thang_len_dinh(self):
        """Văn bản nói "mức liền kề", không nói trả lại mức đáng lẽ đạt được."""
        kq = dg.xep_loai_hoc_tap([8.5] * 7 + [3.0])
        self.assertEqual(kq.muc_truoc_khi_nang, "Chưa đạt")
        self.assertEqual(kq.muc, "Đạt")

    def test_tut_chi_mot_muc_thi_khong_nang(self):
        kq = dg.xep_loai_hoc_tap([8.5] * 7 + [6.0])
        self.assertIsNone(kq.muc_truoc_khi_nang)
        self.assertEqual(kq.muc, "Khá")

    def test_hai_mon_keo_xuong_thi_khong_nang(self):
        """"Duy nhất 01 môn học" - hai môn cùng kéo xuống thì không thuộc diện
        được điều chỉnh."""
        kq = dg.xep_loai_hoc_tap([8.5] * 6 + [4.0, 4.0])
        self.assertIsNone(kq.muc_truoc_khi_nang)


class KhenThuongTests(unittest.TestCase):
    """Điều 15 khoản 1 điểm a."""

    def test_xuat_sac_doi_them_sau_mon_tu_9_0(self):
        self.assertEqual(
            dg.danh_hieu_khen_thuong("Tốt", "Tốt", [9.0] * 6 + [8.0, 8.0]),
            "Học sinh Xuất sắc",
        )

    def test_nam_mon_tu_9_0_thi_chi_la_hoc_sinh_gioi(self):
        self.assertEqual(
            dg.danh_hieu_khen_thuong("Tốt", "Tốt", [9.0] * 5 + [8.0] * 3),
            "Học sinh Giỏi",
        )

    def test_ren_luyen_chua_tot_thi_khong_co_danh_hieu(self):
        self.assertIsNone(dg.danh_hieu_khen_thuong("Khá", "Tốt", [9.0] * 8))
        self.assertIsNone(dg.danh_hieu_khen_thuong("Tốt", "Khá", [9.0] * 8))


class CanCuTests(unittest.TestCase):
    def test_moi_chip_nguon_tro_toi_mot_tep_co_that(self):
        import os

        from main import DATA_PATH

        co_tren_dia = set()
        for _, _, cac_tep in os.walk(DATA_PATH):
            co_tren_dia.update(cac_tep)

        _, nguon = dg.tra_loi(
            "điểm thường xuyên 8, 9, giữa kì 7, cuối kì 8 thì ĐTB bao nhiêu"
        )
        self.assertTrue(nguon, "không còn chip nguồn nào")
        for n in nguon:
            self.assertIn(n["name"], co_tren_dia)
            self.assertTrue(n["excerpt"])


class NhanDienTests(unittest.TestCase):
    def test_doc_duoc_diem_thanh_phan(self):
        ts = dg.nhan_dien(
            "điểm thường xuyên 8, 9, giữa kì 7, cuối kì 8 thì ĐTB môn bao nhiêu"
        )
        self.assertEqual(ts.dang, "mon_hoc_ki")
        self.assertEqual(ts.diem_thuong_xuyen, [8.0, 9.0])
        self.assertEqual(ts.diem_giua_ki, 7.0)
        self.assertEqual(ts.diem_cuoi_ki, 8.0)

    def test_doc_duoc_hai_hoc_ki(self):
        ts = dg.nhan_dien(
            "học kì I 7,9 học kì II 8,5 thì điểm trung bình môn cả năm bao nhiêu"
        )
        self.assertEqual(ts.dang, "mon_ca_nam")
        self.assertEqual(ts.dtb_hoc_ki_1, 7.9)
        self.assertEqual(ts.dtb_hoc_ki_2, 8.5)

    def test_doc_duoc_day_diem_cac_mon(self):
        ts = dg.nhan_dien(
            "điểm các môn 8,5 8,5 8,5 8,5 8,5 8,5 8,5 4,0 thì xếp loại gì"
        )
        self.assertEqual(ts.dang, "xep_loai")
        self.assertEqual(len(ts.diem_cac_mon), 8)


class TuChoiTests(unittest.TestCase):
    """Công cụ đứng trước RAG, nên nhận nhầm một câu tra cứu nghĩa là người
    dùng mất hẳn câu trả lời từ kho tài liệu."""

    def khong_nhan(self, cau_hoi):
        self.assertIsNone(dg.tra_loi(cau_hoi), f"nhận nhầm: {cau_hoi}")

    def test_cau_hoi_tra_cuu_quy_dinh(self):
        self.khong_nhan("Thông tư 22/2021 quy định xếp loại học sinh như thế nào")
        self.khong_nhan("điều kiện được lên lớp là gì")
        self.khong_nhan("trách nhiệm của giáo viên chủ nhiệm")
        self.khong_nhan("điểm trung bình môn tính ra sao")

    def test_thieu_so_lieu_thi_nhuong_cho_rag(self):
        self.khong_nhan("xếp loại học lực của tôi")
        self.khong_nhan("điểm thường xuyên 8, 9 thì ĐTB bao nhiêu")

    def test_duoi_sau_mon_thi_khong_xep_loai(self):
        """Mọi ngưỡng ở khoản 2 đều đếm "ít nhất 06 môn học". Dưới mức đó thì
        mọi mức đều rơi về Chưa đạt - một kết luận sai, không phải một kết luận
        nghiêm khắc."""
        self.khong_nhan("điểm các môn 8, 9, 7 thì xếp loại gì")


if __name__ == "__main__":
    unittest.main()
