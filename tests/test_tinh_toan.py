"""Công cụ số học: hai thứ phải đúng, và chúng hỏng theo hai kiểu khác nhau.

Con số sai thì hiện ra như một đáp án trông rất hợp lý - nên phần lớn test tính
toán ở đây đối chiếu với kết quả tính tay. Còn CỔNG NHẬN CÂU sai thì hỏng lặng
lẽ hơn nhiều: công cụ này chen trước cả RAG, nên một câu tra cứu bị nhận nhầm
sẽ không bao giờ tới được kho tài liệu, và người dùng chỉ thấy một phép chia vô
nghĩa thay cho câu trả lời. Vì vậy nửa sau của tệp toàn là những câu PHẢI bị từ
chối.
"""

import unittest

import tinh_toan


class DocSoTests(unittest.TestCase):
    """Văn bản quy phạm viết "2.340.000 đồng" và "hệ số 2,34". Đọc nhầm quy ước
    dấu chấm/dấu phẩy là sai ngay từ con số đầu vào, trước cả phép tính."""

    def test_dau_cham_la_phan_nhom_nghin(self):
        self.assertEqual(tinh_toan.doc_so("2.340.000"), 2340000)
        self.assertEqual(tinh_toan.doc_so("4.980.000"), 4980000)

    def test_dau_phay_la_phan_thap_phan(self):
        self.assertEqual(tinh_toan.doc_so("2,34"), 2.34)
        self.assertEqual(tinh_toan.doc_so("1.234,5"), 1234.5)

    def test_mot_dau_cham_ba_chu_so_hieu_theo_quy_uoc_viet(self):
        """"2.340" là hai nghìn ba trăm bốn mươi, không phải 2,34 - đây là chỗ
        nhập nhằng duy nhất còn lại và nó phải nghiêng về quy ước Việt."""
        self.assertEqual(tinh_toan.doc_so("2.340"), 2340)

    def test_mot_dau_cham_hai_chu_so_van_la_thap_phan(self):
        self.assertEqual(tinh_toan.doc_so("2.34"), 2.34)

    def test_so_khong_doc_duoc_thi_bao_loi(self):
        for xau in ("1,2,3", "1.23.4", ""):
            with self.assertRaises(ValueError):
                tinh_toan.doc_so(xau)


class TinhTests(unittest.TestCase):
    def tinh(self, bieu_thuc):
        return tinh_toan.tinh_bieu_thuc(bieu_thuc)

    def test_uu_tien_nhan_chia_truoc_cong_tru(self):
        self.assertEqual(self.tinh("2 + 3 * 4"), 14)
        self.assertEqual(self.tinh("(2 + 3) * 4"), 20)

    def test_luy_thua_ket_hop_phai(self):
        self.assertEqual(self.tinh("2 ^ 3 ^ 2"), 512)

    def test_dau_am_dung_truoc_so(self):
        self.assertEqual(self.tinh("-5 + 3"), -2)

    def test_phan_tram_la_chia_cho_100(self):
        self.assertAlmostEqual(self.tinh("12% * 2.340.000"), 280800)

    def test_don_vi_trieu_va_ty(self):
        self.assertEqual(self.tinh("5 triệu + 1"), 5000001)
        self.assertEqual(self.tinh("2 tỷ / 2"), 1000000000)

    def test_chia_cho_khong_thi_noi_ro(self):
        with self.assertRaises(tinh_toan.LoiTinh):
            self.tinh("1 / 0")

    def test_mu_qua_lon_bi_chan(self):
        """2^999999 không phải phép tính, đó là một cách treo tiến trình."""
        with self.assertRaises(tinh_toan.LoiTinh):
            self.tinh("2 ^ 999999")

    def test_khong_chay_duoc_ma_python(self):
        """Chuỗi vào đây là chuỗi người dùng gõ. Bộ phân tích chỉ biết sáu phép
        toán - mọi thứ khác phải chết ngay ở khâu tách token."""
        for doc in ("__import__('os')", "1 if 1 else 2", "open('x')", "1;2"):
            with self.assertRaises((ValueError, tinh_toan.LoiTinh)):
                self.tinh(doc)


class DinhDangSoTests(unittest.TestCase):
    def test_so_nguyen_phan_nhom_nghin(self):
        self.assertEqual(tinh_toan.dinh_dang_so(2340000), "2.340.000")

    def test_phan_thap_phan_dung_dau_phay(self):
        self.assertEqual(tinh_toan.dinh_dang_so(12.5), "12,5")

    def test_khong_phoi_ra_duoi_dau_phay_dong(self):
        """0,1 + 0,2 trong số dấu phẩy động ra 0.30000000000000004. Đáp số hiện
        ra như vậy thì người đọc mất niềm tin vào cả những con số đúng."""
        self.assertEqual(tinh_toan.dinh_dang_so(0.1 + 0.2), "0,3")


class NhanDienTests(unittest.TestCase):
    """Những câu PHẢI được nhận, viết theo đúng cách người dùng gõ."""

    def gia_tri(self, cau_hoi):
        kq = tinh_toan.nhan_dien(cau_hoi)
        self.assertIsNotNone(kq, f"không nhận ra: {cau_hoi}")
        return kq.gia_tri

    def test_phan_tram_cua_mot_so(self):
        self.assertAlmostEqual(
            self.gia_tri("12% của 2.340.000 là bao nhiêu"), 280800
        )

    def test_dau_nhan_go_bang_chu_x(self):
        self.assertEqual(self.gia_tri("tính 35 x 17"), 595)

    def test_dau_nhan_go_bang_ky_hieu_toan_hoc(self):
        self.assertAlmostEqual(self.gia_tri("2,34 × 2.340.000"), 5475600)

    def test_phan_tram_nhan_voi_mot_so(self):
        self.assertAlmostEqual(self.gia_tri("15% x 4.980.000"), 747000)

    def test_tang_theo_ty_le(self):
        """"5 triệu tăng 8%" mà đọc dấu % thành phép chia 100 sẽ ra
        5.000.000 + 0,08 - đúng cú pháp, sai hoàn toàn ý người hỏi."""
        self.assertAlmostEqual(self.gia_tri("5 triệu tăng 8%"), 5400000)

    def test_giam_theo_ty_le(self):
        self.assertAlmostEqual(self.gia_tri("10 triệu giảm 15%"), 8500000)

    def test_hoi_nguoc_ra_ty_le_phan_tram(self):
        self.assertAlmostEqual(
            self.gia_tri("32 trên 40 là bao nhiêu phần trăm"), 80
        )

    def test_ty_le_hien_kem_dau_phan_tram(self):
        """Trả về trơ một số 80 thì người đọc không biết đó là 80% hay 80 học
        sinh."""
        van_ban, _ = tinh_toan.tra_loi("32 trên 40 là bao nhiêu phần trăm")
        self.assertIn("80%", van_ban)

    def test_dau_bang_la_cach_hoi_ngan_nhat(self):
        """"5+3=mấy" là cách gõ một phép tính nhanh nhất trong ô chat, nhưng bộ
        phân tích không biết dấu "=" - để nguyên thì cả nhóm câu này rơi ra
        ngoài. Đây chính là câu đầu tiên người dùng thật gõ vào bản đã chạy."""
        self.assertEqual(self.gia_tri("5+3=mấy"), 8)
        self.assertEqual(self.gia_tri("5+3="), 8)
        self.assertEqual(self.gia_tri("5+3=?"), 8)
        self.assertEqual(self.gia_tri("2+3=MẤY?"), 5)
        self.assertAlmostEqual(self.gia_tri("35x17=bao nhiêu"), 595)

    def test_chu_phep_bang_tieng_viet(self):
        """Bộ phân tích có sẵn cả sáu phép, nên mỗi phép phải có đủ chữ tiếng
        Việt dẫn tới nó - thiếu một chữ là thiếu lặng lẽ."""
        self.assertEqual(self.gia_tri("5 cộng 3"), 8)
        self.assertEqual(self.gia_tri("10 trừ 4"), 6)
        self.assertEqual(self.gia_tri("6 nhân 7"), 42)
        self.assertEqual(self.gia_tri("20 chia 4"), 5)
        self.assertEqual(self.gia_tri("3 mũ 4"), 81)

    def test_dau_bang_giua_cau_khong_bien_thanh_phep_kiem_dap_an(self):
        """"5+3=8 đúng không" thành "5+3 8" - hai con số đứng cạnh nhau không
        thành biểu thức. Công cụ này tính chứ không chấm bài hộ ai."""
        self.assertIsNone(tinh_toan.tra_loi("5+3=8 đúng không"))

    def test_chia_cho_khong_thi_tra_ve_loi_chu_khong_tra_ve_none(self):
        """None nghĩa là "đẩy sang RAG". Người dùng gõ 1/0 thì rõ ràng muốn một
        phép tính, đẩy sang RAG chỉ tổ nhận về một câu trả lời lạc đề."""
        ket_qua = tinh_toan.tra_loi("1000000 / 0 bằng bao nhiêu")
        self.assertIsNotNone(ket_qua)
        self.assertIn("Không tính được", ket_qua[0])

    def test_khong_gan_chip_nguon_nao(self):
        """Phép tính này không dựa vào văn bản nào trong kho, gắn chip nguồn vào
        là nói dối."""
        _, nguon = tinh_toan.tra_loi("35 x 17")
        self.assertEqual(nguon, [])


class TuChoiTests(unittest.TestCase):
    """Những câu PHẢI bị từ chối. Công cụ đứng trước RAG, nên nhận nhầm ở đây
    nghĩa là người dùng mất hẳn câu trả lời từ kho tài liệu."""

    def khong_nhan(self, cau_hoi):
        self.assertIsNone(
            tinh_toan.tra_loi(cau_hoi), f"nhận nhầm câu tra cứu: {cau_hoi}"
        )

    def test_so_hieu_van_ban_khong_phai_phep_chia(self):
        """"Thông tư 22/2021" mà lọt vào đây sẽ thành phép chia 22 cho 2021."""
        self.khong_nhan("Thông tư 22/2021 quy định gì")
        self.khong_nhan("Nghị định 73/2024/NĐ-CP có hiệu lực từ khi nào")

    def test_cau_hoi_tra_cuu_dieu_khoan(self):
        self.khong_nhan("Điều 3 khoản 2 nói gì")
        self.khong_nhan("giáo viên hạng II hệ số lương bao nhiêu")

    def test_cau_tinh_luong_de_cho_cong_cu_tinh_luong(self):
        self.khong_nhan("tính lương giáo viên THPT hạng III bậc 1")

    def test_mot_con_so_tro_troi_khong_phai_phep_tinh(self):
        self.khong_nhan("2340000")
        self.khong_nhan("lương cơ sở")

    def test_chu_may_khong_nuot_chu_may_tinh(self):
        """"mấy" là chữ dẫn, mà bỏ dấu xong "máy" cũng thành "may". Chỉ cần
        phần còn lại không phải biểu thức là câu tự rơi sang RAG."""
        self.khong_nhan("máy tính của tôi")

    def test_cau_hoi_thuong_ngay_khong_co_phep_tinh(self):
        self.khong_nhan("Khung cơ cấu hệ thống giáo dục quốc dân gồm những cấp học nào?")
        self.khong_nhan("chế độ phụ cấp ưu đãi đối với nhà giáo")
        self.khong_nhan("năm học 2026-2027 bắt đầu khi nào")

    def test_cau_qua_dai_thi_bo_qua(self):
        self.khong_nhan("tính " + "1 + " * 100 + "1")


if __name__ == "__main__":
    unittest.main()
