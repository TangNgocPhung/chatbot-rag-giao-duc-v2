"""Gõ có dấu và gõ không dấu phải ra cùng một câu trả lời.

Người dùng gõ "tinh luong giao vien THPT hang III bac 1" nhiều không kém gõ đủ
dấu - trên điện thoại, trên máy chưa cài bộ gõ, hoặc chỉ vì gõ nhanh. Trước đây
mỗi công cụ tự liệt kê hai biến thể cho từng cụm từ, và cụm nào quên thì cả câu
rơi khỏi cổng nhận mà không ai biết: công cụ trả None, câu đi tiếp sang RAG,
người dùng chỉ thấy câu trả lời chậm hơn chứ không thấy lỗi.

Nay cả bốn công cụ bỏ dấu câu hỏi một lần rồi mới so mẫu. Đổi lại, mọi mẫu phải
viết KHÔNG DẤU - một mẫu còn sót dấu sẽ không bao giờ khớp nữa, và cũng hỏng
lặng lẽ y như vậy. Test ở đây là chốt chặn cho cả hai kiểu hỏng đó.
"""

import unittest

import danh_gia_hoc_sinh
import dinh_muc_tiet_day
import tinh_luong
import tinh_toan
from can_cu_van_ban import bo_dau

# (công cụ, câu gõ đủ dấu, đúng câu đó gõ không dấu)
CAC_CAP = [
    (tinh_luong,
     "tính lương giáo viên THPT hạng III bậc 1",
     "tinh luong giao vien THPT hang III bac 1"),
    (tinh_luong,
     "tính lương giáo viên mầm non hạng II bậc 3 vùng đặc biệt khó khăn",
     "tinh luong giao vien mam non hang II bac 3 vung dac biet kho khan"),
    (dinh_muc_tiet_day,
     "giáo viên GDTX chủ nhiệm 1 lớp dạy bao nhiêu tiết/tuần",
     "giao vien GDTX chu nhiem 1 lop day bao nhieu tiet/tuan"),
    (dinh_muc_tiet_day,
     "giám đốc trung tâm GDTX dạy bao nhiêu tiết một năm",
     "giam doc trung tam GDTX day bao nhieu tiet mot nam"),
    (danh_gia_hoc_sinh,
     "điểm thường xuyên 8, 9, giữa kì 7, cuối kì 8 thì ĐTB bao nhiêu",
     "diem thuong xuyen 8, 9, giua ki 7, cuoi ki 8 thi DTB bao nhieu"),
    (danh_gia_hoc_sinh,
     "học kì I 7,9 học kì II 8,5 thì ĐTB cả năm bao nhiêu",
     "hoc ki I 7,9 hoc ki II 8,5 thi DTB ca nam bao nhieu"),
    (danh_gia_hoc_sinh,
     "điểm các môn 9 9 9 9 9 8 rèn luyện tốt thì danh hiệu gì",
     "diem cac mon 9 9 9 9 9 8 ren luyen tot thi danh hieu gi"),
    (tinh_toan, "tính 12% của 2.340.000", "tinh 12% cua 2.340.000"),
    (tinh_toan, "5 triệu tăng 8%", "5 trieu tang 8%"),
    (tinh_toan, "32 trên 40 là bao nhiêu phần trăm",
     "32 tren 40 la bao nhieu phan tram"),
]


class BoDauTests(unittest.TestCase):
    def test_bo_dau_giu_nguyen_chu_so_va_dau_cau(self):
        """Con số là thứ duy nhất không được phép đổi: mọi phép tính đọc số từ
        chính chuỗi đã bỏ dấu."""
        self.assertEqual(bo_dau("2.340.000 đồng"), "2.340.000 dong")
        self.assertEqual(bo_dau("hệ số 2,34"), "he so 2,34")
        self.assertEqual(bo_dau("12% × 40"), "12% × 40")

    def test_chu_d_gach_ngang(self):
        """NFD không phân rã được chữ đ, phải thay tay - mà đây lại là chữ hay
        gặp nhất trong kho: "điều", "đánh giá", "định mức"."""
        self.assertEqual(bo_dau("Điều 9 định mức"), "dieu 9 dinh muc")

    def test_ha_chu_thuong(self):
        self.assertEqual(bo_dau("ĐTBmhk"), "dtbmhk")


class HaiKieuGoTests(unittest.TestCase):
    def test_cung_cau_hoi_cung_ket_qua(self):
        for cong_cu, co_dau, khong_dau in CAC_CAP:
            ten = cong_cu.__name__
            with self.subTest(cong_cu=ten, cau=khong_dau):
                a = cong_cu.tra_loi(co_dau)
                b = cong_cu.tra_loi(khong_dau)
                self.assertIsNotNone(a, f"{ten} bỏ sót câu gõ có dấu")
                self.assertIsNotNone(b, f"{ten} bỏ sót câu gõ không dấu")
                self.assertEqual(
                    a[0], b[0], f"{ten} trả hai kết quả khác nhau cho cùng câu"
                )


class MauPhaiVietKhongDauTests(unittest.TestCase):
    """Chuỗi đem so đã sạch dấu, nên một mẫu còn sót dấu là mẫu chết - không
    bao giờ khớp, và không có gì báo cho ai biết."""

    def kiem(self, cac_mau, nguon):
        # So với mau.lower() chứ không so với chính mau: bo_dau() vừa bỏ dấu vừa
        # hạ chữ thường, mà mẫu thì có chữ hoa hợp lệ - tên nhóm (?P<...>) và
        # các lớp ký tự của regex. Ở đây chỉ cần khẳng định BỎ DẤU không làm đổi
        # gì, tức là mẫu vốn đã sạch dấu.
        for mau in cac_mau:
            self.assertEqual(
                bo_dau(mau), mau.lower(),
                f"{nguon} còn mẫu có dấu: {mau!r} - sẽ không bao giờ khớp",
            )

    def test_tinh_luong(self):
        self.kiem(
            [tinh_luong.TU_KHOA_TINH.pattern,
             tinh_luong.TU_KHOA_LUONG.pattern,
             tinh_luong.TU_KHOA_TRA_CUU.pattern]
            + [mau for _, mau in tinh_luong.CAP_HOC_MAU]
            + [mau for _, mau in tinh_luong.HANG_MAU],
            "tinh_luong",
        )

    def test_dinh_muc_tiet_day(self):
        self.kiem(
            [dinh_muc_tiet_day.TU_KHOA_DINH_MUC.pattern,
             dinh_muc_tiet_day.TU_KHOA_GDTX.pattern,
             dinh_muc_tiet_day.CAP_HOC_KHAC.pattern,
             dinh_muc_tiet_day.TU_KHOA_TRA_CUU.pattern,
             dinh_muc_tiet_day.KIEM_NHIEM_KHAC.mau]
            + [kg.mau for kg in dinh_muc_tiet_day.KHOAN_GIAM]
            + [mau for mau, _ in dinh_muc_tiet_day.NGOAI_KHO]
            + [mau for _, mau in dinh_muc_tiet_day.VAI_TRO_MAU],
            "dinh_muc_tiet_day",
        )

    def test_danh_gia_hoc_sinh(self):
        self.kiem(
            [danh_gia_hoc_sinh.TU_KHOA_DIEM.pattern,
             danh_gia_hoc_sinh.TU_KHOA_TRA_CUU.pattern,
             danh_gia_hoc_sinh.MAU_THUONG_XUYEN.pattern,
             danh_gia_hoc_sinh.MAU_GIUA_KI.pattern,
             danh_gia_hoc_sinh.MAU_CUOI_KI.pattern,
             danh_gia_hoc_sinh.MAU_HOC_KI_1.pattern,
             danh_gia_hoc_sinh.MAU_HOC_KI_2.pattern,
             danh_gia_hoc_sinh.MAU_CAC_MON.pattern],
            "danh_gia_hoc_sinh",
        )

    def test_tinh_toan(self):
        self.kiem(
            list(tinh_toan.CHU_DAN)
            + [tinh_toan.MAU_TRA_CUU.pattern,
               tinh_toan.MAU_TANG_GIAM.pattern,
               tinh_toan.MAU_TY_LE.pattern,
               tinh_toan.MAU_PHAN_TRAM_CUA.pattern]
            + [mau for mau, _ in tinh_toan.CHU_PHEP]
            + list(tinh_toan.DON_VI),
            "tinh_toan",
        )


class ChuDanPhaiChotBienTuTests(unittest.TestCase):
    """Bỏ dấu xong, "ạ" thành một chữ "a" trơ trọi và "là" thành "la". Không
    chốt biên từ thì chúng ăn mất chữ a giữa "cua", cắt "tang" thành "t ng", và
    cả câu vỡ vụn trước khi tới được bộ phân tích."""

    def test_khong_an_chu_giua_tu(self):
        self.assertEqual(
            tinh_toan._bo_chu_dan("12% của 2.340.000 là bao nhiêu"),
            "12% cua 2.340.000",
        )
        self.assertEqual(tinh_toan._bo_chu_dan("5 triệu tăng 8%"), "5 trieu tang 8%")


if __name__ == "__main__":
    unittest.main()
