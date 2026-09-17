"""Công cụ tính định mức tiết dạy: sai ở đây thành một bảng phân công sai cho
cả năm học của một giáo viên, mà nhìn vào thì không thấy gì bất thường.

Phần lớn test đối chiếu ngược lại đúng con số in trong Thông tư 04/2026 -
17 tiết, 35 tuần, 8%, 10%, các mức giảm ở Điều 9 và Điều 10. Nhóm cuối kiểm
phạm vi: Thông tư chỉ điều chỉnh giáo dục thường xuyên, nên câu hỏi về cấp học
khác phải bị trả None thay vì được trả lời bằng con số của giáo dục thường
xuyên.
"""

import unittest

import dinh_muc_tiet_day as dm


class HangSoTests(unittest.TestCase):
    """Những con số này có nguyên văn trong Thông tư. Test ở đây là chốt chặn
    cuối: đổi một hằng số mà quên đổi căn cứ thì phải hỏng ngay tại đây."""

    def test_dinh_muc_tuan_dung_dieu_7(self):
        self.assertEqual(dm.DINH_MUC_TUAN, 17)

    def test_so_tuan_thuc_day_dung_dieu_5(self):
        """Điều 5 ghi 37 tuần, trong đó 35 tuần thực dạy và 02 tuần dự phòng.
        Lấy nhầm 37 thì định mức năm vống lên 34 tiết."""
        self.assertEqual(dm.SO_TUAN_THUC_DAY, 35)

    def test_ty_le_cua_giam_doc_va_pho_giam_doc(self):
        self.assertEqual(dm.TY_LE_GIAM_DOC, 0.08)
        self.assertEqual(dm.TY_LE_PHO_GIAM_DOC, 0.10)

    def test_muc_giam_dung_dieu_9_va_dieu_10(self):
        muc = {kg.khoa: kg.so_tiet for kg in dm.KHOAN_GIAM}
        self.assertEqual(muc["chu_nhiem"], 4)
        self.assertEqual(muc["truong_phong"], 6)
        self.assertEqual(muc["pho_truong_phong"], 4)
        self.assertEqual(muc["tu_van"], 8)
        self.assertEqual(muc["tap_su"], 2)
        self.assertEqual(muc["nuoi_con_nho"], 3)

    def test_khoan_nao_chi_la_tran_thi_phai_duoc_danh_dau(self):
        """Điều 9 giao giám đốc quyết định mức cụ thể cho mấy khoản này. Tính
        theo trần mà không nói rõ là đưa ra một con số quá tay."""
        toi_da = {kg.khoa for kg in dm.KHOAN_GIAM if kg.toi_da}
        self.assertEqual(
            toi_da, {"truong_phong", "pho_truong_phong", "tu_van"}
        )


class TinhTests(unittest.TestCase):
    def test_giao_vien_khong_kiem_nhiem(self):
        kq = dm.tinh(dm.ThamSo())
        self.assertEqual(kq.dinh_muc_tuan, 17)
        self.assertEqual(kq.dinh_muc_nam, 595)

    def test_chu_nhiem_mot_lop_giam_bon_tiet(self):
        kq = dm.tinh(dm.ThamSo(khoan_giam=[dm.KHOAN_GIAM[0]]))
        self.assertEqual(kq.dinh_muc_tuan, 13)
        self.assertEqual(kq.dinh_muc_nam, 455)

    def test_giam_doc_tinh_theo_phan_tram_dinh_muc_nam(self):
        kq = dm.tinh(dm.ThamSo(vai_tro="giam_doc"))
        self.assertAlmostEqual(kq.dinh_muc_nam, 47.6)

    def test_pho_giam_doc_tinh_theo_phan_tram_dinh_muc_nam(self):
        kq = dm.tinh(dm.ThamSo(vai_tro="pho_giam_doc"))
        self.assertAlmostEqual(kq.dinh_muc_nam, 59.5)

    def test_quan_ly_khong_duoc_tru_tiet_kiem_nhiem(self):
        """Điều 8 khoản 3 cấm dùng tiết được giảm hoặc quy đổi để thay cho định
        mức của giám đốc - trừ vào đó là xóa mất phần dạy bắt buộc."""
        kq = dm.tinh(dm.ThamSo(vai_tro="giam_doc", khoan_giam=[dm.KHOAN_GIAM[0]]))
        self.assertAlmostEqual(kq.dinh_muc_nam, 47.6)
        self.assertTrue(
            any("Điều 8 khoản 3" in c for c in kq.canh_bao),
            "không nói rõ vì sao nhiệm vụ kiêm nhiệm không được trừ",
        )

    def test_canh_bao_khi_tong_giam_vuot_tran_nam(self):
        """Điều 4 khoản 2: tổng giảm và quy đổi cho nhiệm vụ kiêm nhiệm không
        quá 50% định mức năm."""
        kq = dm.tinh(dm.ThamSo(khoan_giam=[dm.KHOAN_GIAM[0], dm.KHOAN_GIAM[1]]))
        self.assertTrue(any("Điều 4 khoản 2" in c for c in kq.canh_bao))

    def test_tap_su_va_nuoi_con_nho_khong_tinh_vao_tran(self):
        """Hai khoản này nằm ở Điều 10, không phải nhiệm vụ kiêm nhiệm. Cộng
        chúng vào phép kiểm tra trần là cảnh báo oan người dùng."""
        tap_su = next(kg for kg in dm.KHOAN_GIAM if kg.khoa == "tap_su")
        con_nho = next(kg for kg in dm.KHOAN_GIAM if kg.khoa == "nuoi_con_nho")
        self.assertFalse(tap_su.vao_tran)
        self.assertFalse(con_nho.vao_tran)
        kq = dm.tinh(dm.ThamSo(khoan_giam=[tap_su, con_nho]))
        self.assertEqual(kq.dinh_muc_tuan, 12)
        self.assertFalse(any("Điều 4 khoản 2" in c for c in kq.canh_bao))

    def test_so_tiet_vuot_va_tran_vuot_tuan(self):
        """Điều 4 khoản 1: số tiết dạy vượt trong tuần không quá 50% định mức
        tuần."""
        kq = dm.tinh(dm.ThamSo(so_tiet_thuc_day=22))
        self.assertEqual(kq.tiet_vuot_tuan, 5)
        self.assertFalse(any("Điều 4 khoản 1" in c for c in kq.canh_bao))

        kq = dm.tinh(dm.ThamSo(so_tiet_thuc_day=26))
        self.assertEqual(kq.tiet_vuot_tuan, 9)
        self.assertTrue(any("Điều 4 khoản 1" in c for c in kq.canh_bao))

    def test_giam_qua_tay_khong_tao_ra_dinh_muc_am(self):
        kq = dm.tinh(dm.ThamSo(khoan_giam=list(dm.KHOAN_GIAM)))
        self.assertEqual(kq.dinh_muc_tuan, 0)
        self.assertTrue(any("phân công sai" in c for c in kq.canh_bao))


class CanCuTests(unittest.TestCase):
    def test_van_ban_ngoai_kho_phai_co_canh_bao(self):
        """Công đoàn và Đoàn thanh niên được Điều 9 đẩy sang hai văn bản không
        có trong kho. Tính hộ mức giảm của họ là đưa ra con số không nguồn."""
        ts = dm.nhan_dien("giáo viên GDTX kiêm nhiệm công đoàn giảm mấy tiết")
        self.assertIsNotNone(ts)
        kq = dm.tinh(ts)
        self.assertEqual(kq.dinh_muc_tuan, 17)
        self.assertTrue(
            any("08/2016" in c for c in kq.canh_bao),
            "không cảnh báo văn bản ngoài kho",
        )

    def test_moi_chip_nguon_tro_toi_mot_tep_co_that(self):
        """Chip nguồn bấm vào phải mở được tài liệu, nếu không người dùng nhận
        về một liên kết 404."""
        import os

        from main import DATA_PATH

        co_tren_dia = set()
        for _, _, cac_tep in os.walk(DATA_PATH):
            co_tren_dia.update(cac_tep)

        kq = dm.tinh(dm.ThamSo())
        chip = dm.nguon_trich_dan(kq)
        self.assertTrue(chip, "không còn chip nguồn nào")
        for nguon in chip:
            self.assertIn(nguon["name"], co_tren_dia)
            self.assertTrue(nguon["excerpt"])


class NhanDienTests(unittest.TestCase):
    def test_cau_hoi_co_neu_giao_duc_thuong_xuyen(self):
        ts = dm.nhan_dien(
            "giáo viên GDTX chủ nhiệm 1 lớp thì còn phải dạy bao nhiêu tiết/tuần"
        )
        self.assertIsNotNone(ts)
        self.assertEqual(ts.vai_tro, "giao_vien")
        self.assertEqual([kg.khoa for kg in ts.khoan_giam], ["chu_nhiem"])

    def test_doc_duoc_so_tiet_dang_duoc_phan_cong(self):
        ts = dm.nhan_dien(
            "giáo viên giáo dục thường xuyên đang dạy 22 tiết/tuần thì vượt "
            "định mức bao nhiêu"
        )
        self.assertIsNotNone(ts)
        self.assertEqual(ts.so_tiet_thuc_day, 22)

    def test_nhan_ra_chuc_vu_quan_ly(self):
        ts = dm.nhan_dien("giám đốc trung tâm GDTX dạy bao nhiêu tiết một năm")
        self.assertEqual(ts.vai_tro, "giam_doc")
        ts = dm.nhan_dien(
            "phó giám đốc trung tâm giáo dục thường xuyên định mức tiết dạy "
            "bao nhiêu"
        )
        self.assertEqual(ts.vai_tro, "pho_giam_doc")

    def test_kiem_nhiem_co_ten_khong_bi_cong_them_muc_giam_chung(self):
        """"Kiêm nhiệm tổ trưởng" mà vừa tính 6 tiết của tổ trưởng vừa cộng 4
        tiết của "vị trí việc làm khác" là trừ hai lần cho một nhiệm vụ."""
        ts = dm.nhan_dien(
            "giáo viên GDTX kiêm nhiệm tổ trưởng thì định mức tiết dạy còn bao nhiêu"
        )
        self.assertEqual([kg.khoa for kg in ts.khoan_giam], ["truong_phong"])


class PhamViTests(unittest.TestCase):
    """Thông tư 04/2026 chỉ điều chỉnh giáo dục thường xuyên. Kho chưa có văn
    bản nào quy định định mức tiết dạy cho các cấp học khác, nên đem con số 17
    tiết trả lời cho giáo viên THPT là bịa, dù có trích dẫn kèm."""

    def khong_nhan(self, cau_hoi):
        self.assertIsNone(dm.tra_loi(cau_hoi), f"nhận nhầm: {cau_hoi}")

    def test_cap_hoc_khac_thi_nhuong_cho_rag(self):
        self.khong_nhan("định mức tiết dạy giáo viên THPT là bao nhiêu")
        self.khong_nhan("giáo viên tiểu học dạy bao nhiêu tiết một tuần")
        self.khong_nhan("định mức tiết dạy của giảng viên đại học")

    def test_cau_so_sanh_hai_che_do_khong_tra_loi_nua_voi(self):
        self.khong_nhan("so sánh định mức tiết dạy giáo viên GDTX và THPT")

    def test_khong_neu_pham_vi_thi_khong_doan(self):
        self.khong_nhan("định mức tiết dạy là bao nhiêu")

    def test_cau_hoi_tra_cuu_can_cu_de_cho_rag(self):
        self.khong_nhan("chế độ làm việc của giáo viên được quy định ở đâu")
        self.khong_nhan("định mức tiết dạy giáo viên GDTX quy định tại điều nào")

    def test_cau_khong_lien_quan(self):
        self.khong_nhan("tuyển sinh lớp 10 năm 2026")
        self.khong_nhan("học viên giáo dục thường xuyên được miễn học phí không")


if __name__ == "__main__":
    unittest.main()
