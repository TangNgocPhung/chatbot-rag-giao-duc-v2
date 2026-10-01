"""Công cụ tính hạn: ngày làm việc, ngày lịch, tháng, ngày lễ và lịch nghỉ nhập tay."""

import json
import os
import tempfile
import unittest
from datetime import date

import tinh_han as th

KHONG_LICH = th.LichNghi()


class TinhTests(unittest.TestCase):
    def test_ngay_lam_viec_bo_cuoi_tuan(self):
        # Thứ Sáu 25/9/2026: đếm từ thứ Hai 28/9, 15 ngày làm việc -> thứ Sáu 16/10.
        kq = th.tinh(date(2026, 9, 25), 15, "ngày làm việc", KHONG_LICH)
        self.assertEqual(kq.ket_thuc, date(2026, 10, 16))
        self.assertEqual(len(kq.bo_qua), 6)

    def test_ngay_lam_viec_tru_le_co_dinh(self):
        # 28/8/2026 (thứ Sáu) + 10 ngày làm việc, trừ Quốc khánh 2/9 -> 14/9.
        kq = th.tinh(date(2026, 8, 28), 10, "ngày làm việc", KHONG_LICH)
        self.assertEqual(kq.ket_thuc, date(2026, 9, 14))
        self.assertIn((date(2026, 9, 2), "Quốc khánh"), kq.bo_qua)

    def test_ngay_lich_ngay_cuoi_la_ngay_nghi_thi_lui(self):
        # 1/10/2026 + 30 ngày = thứ Bảy 31/10 -> thứ Hai 2/11 (Điều 148 BLDS).
        kq = th.tinh(date(2026, 10, 1), 30, "ngày", KHONG_LICH)
        self.assertEqual(kq.ket_thuc, date(2026, 11, 2))
        self.assertEqual(kq.lui_ngay_cuoi, date(2026, 10, 31))
        self.assertIn(th.BLDS_KET_THUC, kq.can_cu)

    def test_thang_cuoi_thang(self):
        # 31/1 + 1 tháng: tháng 2 không có ngày 31 -> ngày cuối tháng 2.
        self.assertEqual(th.tinh(date(2026, 1, 31), 1, "tháng", KHONG_LICH).ket_thuc, date(2026, 3, 2))
        # 28/2/2026 là thứ Bảy -> lùi sang thứ Hai 2/3.
        self.assertEqual(th._cong_thang(date(2026, 1, 31), 1), date(2026, 2, 28))

    def test_lich_nghi_nhap_tay_va_ngay_lam_bu(self):
        lich = th.LichNghi(
            ngay_nghi={"2027-02-08": "Tết Nguyên đán", "2027-02-09": "Tết Nguyên đán"},
            ngay_lam_bu={"2027-02-13"},
            nam_da_nhap={2027},
        )
        # Thứ Sáu 5/2/2027 + 3 ngày làm việc: thứ Hai 8, thứ Ba 9 nghỉ Tết -> 10, 11, 12.
        kq = th.tinh(date(2027, 2, 5), 3, "ngày làm việc", lich)
        self.assertEqual(kq.ket_thuc, date(2027, 2, 12))
        # Thứ Bảy 13/2 đi làm bù thì được đếm.
        self.assertEqual(th.tinh(date(2027, 2, 12), 1, "ngày làm việc", lich).ket_thuc, date(2027, 2, 13))
        self.assertEqual(kq.canh_bao, [])

    def test_canh_bao_chi_khi_di_qua_dip_nghi_chua_nhap(self):
        self.assertEqual(th.tinh(date(2026, 9, 25), 15, "ngày làm việc", KHONG_LICH).canh_bao, [])
        kq = th.tinh(date(2026, 8, 28), 10, "ngày làm việc", KHONG_LICH)
        self.assertEqual(len(kq.canh_bao), 1)
        self.assertIn("Quốc khánh 2026", kq.canh_bao[0])
        self.assertIn("Tết Nguyên đán 2027", th.tinh(date(2027, 1, 20), 20, "ngày làm việc", KHONG_LICH).canh_bao[0])

    def test_tai_lich_tu_tep(self):
        with tempfile.TemporaryDirectory() as thu_muc:
            duong_dan = os.path.join(thu_muc, "nghi.json")
            with open(duong_dan, "w", encoding="utf-8") as tep:
                json.dump({"theo_nam": {"2027": {"ngay_nghi": {"2027-02-08": "Tết"}, "ngay_lam_bu": ["2027-02-13"]}}}, tep)
            lich = th.tai_lich_nghi(duong_dan)
        self.assertEqual(lich.nam_da_nhap, {2027})
        self.assertEqual(th.ly_do_nghi(date(2027, 2, 8), lich), "Tết")
        self.assertIsNone(th.ly_do_nghi(date(2027, 2, 13), lich))
        self.assertEqual(th.tai_lich_nghi("/khong/co/tep.json").nam_da_nhap, set())

    def test_bang_lich_trong_kho_doc_duoc(self):
        duong_dan = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ngay_nghi_le.json")
        self.assertIsInstance(th.tai_lich_nghi(duong_dan), th.LichNghi)


class NhanDienTests(unittest.TestCase):
    HOM_NAY = date(2026, 10, 1)

    def test_cau_hoi_tinh_han(self):
        for cau, mong_doi in (
            ("Nộp hồ sơ ngày 25/9/2026, 15 ngày làm việc thì đến ngày nào?", (date(2026, 9, 25), 15, "ngày làm việc")),
            ("nộp hôm nay, 30 ngày thì hạn cuối là khi nào", (self.HOM_NAY, 30, "ngày")),
            ("Nộp ngày 5 tháng 10, sau 2 tháng thì bao giờ hết hạn?", (date(2026, 10, 5), 2, "tháng")),
        ):
            ts = th.nhan_dien(cau, self.HOM_NAY)
            self.assertEqual((ts.bat_dau, ts.so, ts.don_vi), mong_doi, cau)

    def test_khong_phai_cau_tinh_han(self):
        for cau in (
            "Thông tư 15/2026/TT-BGDĐT có hiệu lực từ ngày nào?",
            "Hồ sơ chuyển trường gồm những gì?",
            "Từ 1/9/2026 đến 15/9/2026 là bao nhiêu ngày?",   # hai mốc ngày
            "Nộp ngày 25/9/2026 thì khi nào có kết quả?",       # không có thời hạn
            "Giải quyết trong 15 ngày làm việc thì khi nào xong?",  # không có mốc
        ):
            self.assertIsNone(th.nhan_dien(cau, self.HOM_NAY), cau)

    def test_tra_loi_co_can_cu_ngoai_kho(self):
        van_ban, nguon = th.tra_loi("Nộp hồ sơ ngày 25/9/2026, 15 ngày làm việc thì đến ngày nào?", self.HOM_NAY)
        self.assertIn("**Hạn: Thứ Sáu, 16/10/2026**", van_ban)
        self.assertIn("Bộ luật Dân sự 2015, Điều 147", van_ban)
        self.assertIn("(chưa có trong kho tài liệu)", van_ban)
        # Văn bản ngoài kho không thành chip nguồn bấm được.
        self.assertEqual(nguon, [])


if __name__ == "__main__":
    unittest.main()
