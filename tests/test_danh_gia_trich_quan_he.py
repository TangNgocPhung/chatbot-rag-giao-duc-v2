"""Công cụ đo precision/recall của bộ trích quan hệ (không cần chỉ mục)."""

import os
import tempfile
import textwrap
import unittest

import danh_gia_trich_quan_he as dg
import van_ban_meta as vm


def dong(cau, thay_the="", sua_doi="", ngu_canh="", ghi_chu="", ma="q001",
         bai_bo_mot_phan=""):
    return {"ma": ma, "tep": "a.pdf", "ngu_canh_truoc": ngu_canh, "cau": cau,
            "thay_the": thay_the, "bai_bo_mot_phan": bai_bo_mot_phan,
            "sua_doi": sua_doi, "ghi_chu": ghi_chu}


class LayMauTests(unittest.TestCase):
    def test_tach_cau_giu_xuong_dong_trong_cau(self):
        cau = [c for _, c in dg.tach_cau("Điều 1\nThông tư số 1/2020/TT-BGDĐT\nhết hiệu lực. Câu hai")]
        self.assertEqual(len(cau), 2)
        self.assertIn("hết hiệu lực", cau[0])

    def test_ung_vien_can_ca_dong_tu_lan_so_hieu(self):
        self.assertTrue(dg.la_ung_vien("Bãi bỏ Thông tư số 1/2020/TT-BGDĐT"))
        self.assertFalse(dg.la_ung_vien("Căn cứ Thông tư số 1/2020/TT-BGDĐT"))
        self.assertFalse(dg.la_ung_vien("Việc thay thế thành viên hội đồng"))

    def test_ung_vien_khong_phu_thuoc_ket_qua_he_thong(self):
        # Câu hệ thống KHÔNG trích ra quan hệ vẫn phải vào tập ứng viên, nếu
        # không recall đo được sẽ đẹp giả tạo.
        cau = "Nghị định số 71/2020/NĐ-CP hết hiệu lực theo quy định tại Nghị định này."
        self.assertEqual(vm.trich_quan_he(cau), ([], []))
        self.assertEqual(len(dg.cau_ung_vien({"a.pdf": cau})), 1)

    def test_lay_mau_co_dinh_va_khu_trung(self):
        ung_vien = [{"tep": f"{i}.pdf", "ngu_canh_truoc": "", "cau": f"câu {i % 5}"}
                    for i in range(20)]
        mau = dg.lay_mau(ung_vien, 10)
        self.assertEqual(len(mau), 5)
        self.assertEqual(mau, dg.lay_mau(ung_vien, 10))
        self.assertEqual(mau[0]["ma"], "q001")
        self.assertNotIn("du_doan", mau[0])

    def test_csv_ghi_doc_lai_duoc(self):
        with tempfile.TemporaryDirectory() as thu_muc:
            duong_dan = os.path.join(thu_muc, "nhan.csv")
            dg.ghi_csv(duong_dan, [dong("Bãi bỏ Thông tư số 1/2020/TT-BGDĐT.")])
            self.assertEqual(dg.doc_csv(duong_dan)[0]["cau"], "Bãi bỏ Thông tư số 1/2020/TT-BGDĐT.")


class ChamTests(unittest.TestCase):
    def test_wilson(self):
        thap, cao = dg.wilson(10, 10)
        self.assertLess(thap, 1.0)
        self.assertEqual(cao, 1.0)
        self.assertEqual(dg.wilson(0, 0), (0.0, 1.0))
        thap, cao = dg.wilson(5, 10)
        self.assertAlmostEqual(thap + cao, 1.0, places=6)

    def test_nhan_khong_can_chuan_hoa(self):
        self.assertEqual(
            dg.nhan_vang(dong("x", thay_the="05/2025/TT-BGDDT; 43/2019/QH14"))["thay_the"],
            {"5/2025/tt", "43/2019/qh14"},
        )

    def test_cham_dem_dung_tp_fp_fn_va_nham_loai(self):
        cac_dong = [
            # Đúng: thay thế toàn bộ.
            dong("Thông tư này thay thế Thông tư số 17/2012/TT-BGDĐT.",
                 thay_the="17/2012/TT-BGDĐT", ma="q1"),
            # Nhãn nói sửa một phần, giả sử hệ thống nói thay thế -> nhầm loại.
            dong("Thông tư này thay thế Thông tư số 1/2020/TT-BGDĐT.",
                 sua_doi="1/2020/TT-BGDĐT", ma="q2"),
            # Không có quan hệ, hệ thống cũng không trích.
            dong("Nghị định số 71/2020/NĐ-CP thay thế Nghị định số 1/2015/NĐ-CP.", ma="q3"),
            dong("Câu OCR hỏng 5/2020/TT-BGDĐT thay", ghi_chu="bo qua", ma="q4"),
        ]
        kq = dg.cham(cac_dong, vm.trich_quan_he_day_du)
        self.assertEqual((kq.so_cau, kq.so_cau_bo_qua), (3, 1))
        tt = kq.theo_loai["thay_the"]
        self.assertEqual((tt.tp, tt.fp, tt.fn), (1, 1, 0))
        self.assertEqual(kq.theo_loai["sua_doi"].fn, 1)
        self.assertEqual(kq.nham_lan[("sua_doi", "thay_the")], 1)
        self.assertEqual([loi["ma"] for loi in kq.loi], ["q2"])

    def test_chi_tinh_so_hieu_nam_trong_cau(self):
        # Quan hệ rút ra từ phần ngữ cảnh thuộc về câu khác, không tính ở đây.
        kq = dg.cham([dong(
            "Điều 2. Hiệu lực.", ngu_canh="Thông tư này thay thế Thông tư số 9/2010/TT-BGDĐT."
        )], vm.trich_quan_he_day_du)
        self.assertEqual(kq.theo_loai["thay_the"].fp, 0)

    def test_bai_bo_mot_phan_la_loai_rieng(self):
        kq = dg.cham([dong(
            "Bãi bỏ khoản 2 Điều 5 của Thông tư số 12/2020/TT-BGDĐT.",
            bai_bo_mot_phan="12/2020/TT-BGDĐT",
        )], vm.trich_quan_he_day_du)
        self.assertEqual(kq.theo_loai["bai_bo_mot_phan"].tp, 1)
        self.assertEqual(kq.loi, [])

    def test_cham_bang_ma_nguon_khac(self):
        with tempfile.TemporaryDirectory() as thu_muc:
            with open(os.path.join(thu_muc, "van_ban_meta.py"), "w", encoding="utf-8") as tep:
                # Có dataclass như van_ban_meta thật: nạp module ngoài mà quên
                # đăng ký vào sys.modules thì @dataclass hỏng ngay ở đây.
                tep.write(textwrap.dedent('''
                    from dataclasses import dataclass

                    @dataclass
                    class HoSoVanBan:
                        ten_file: str

                    def trich_quan_he(van_ban):
                        return [], []
                '''))
            trich_cu = dg.nap_trich_quan_he(thu_muc)
        kq = dg.cham([dong("Thông tư này thay thế Thông tư số 17/2012/TT-BGDĐT.",
                           thay_the="17/2012/TT-BGDĐT")], trich_cu)
        self.assertEqual(kq.theo_loai["thay_the"].fn, 1)
        # Bộ trích của tiến trình hiện tại không bị thay.
        self.assertIs(dg.nap_trich_quan_he(None), vm.trich_quan_he_day_du)

    def test_ban_cu_hai_loai_lo_ra_o_nham_lan(self):
        # Bộ trích cũ gộp "bãi bỏ khoản 2 Điều 5" vào thay thế toàn bộ: công cụ
        # phải cho thấy đúng ô nhầm lẫn đó khi so trên cùng bộ nhãn.
        class BanCu:
            @staticmethod
            def trich_quan_he(van_ban):
                return vm.trich_so_hieu(van_ban), []

        kq = dg.cham([dong(
            "Bãi bỏ khoản 2 Điều 5 của Thông tư số 12/2020/TT-BGDĐT.",
            bai_bo_mot_phan="12/2020/TT-BGDĐT",
        )], dg._ba_loai(BanCu))
        self.assertEqual(kq.nham_lan[("bai_bo_mot_phan", "thay_the")], 1)


if __name__ == "__main__":
    unittest.main()
