"""Phân cấp cho địa phương và cơ sở: câu giao quyền trong đoạn được trích."""

import unittest

import phan_cap as pc

DIEU_HOC_PHI = """Điều 9. Khung học phí
1. Khung học phí đối với cơ sở giáo dục công lập từ 100 nghìn đồng đến 540 nghìn đồng một tháng.
2. Căn cứ khung học phí quy định tại khoản 1 Điều này, mức thu học phí cụ thể do Hội đồng nhân dân cấp tỉnh quyết định.
3. Ủy ban nhân dân cấp tỉnh có trách nhiệm hướng dẫn thực hiện.
4. Thủ tục miễn giảm thực hiện theo quy định của Ủy ban nhân dân cấp tỉnh.
5. Số lớp mỗi khối do Hiệu trưởng quyết định.
6. Hồ sơ do Sở Giáo dục và Đào tạo tiếp nhận."""


class TrichTests(unittest.TestCase):
    def test_cac_dang_giao_quyen(self):
        ket_qua = pc.trich_phan_cap(DIEU_HOC_PHI)
        self.assertEqual(
            [(m.co_quan, m.co_khung) for m in ket_qua],
            [
                ("Hội đồng nhân dân cấp tỉnh", True),
                ("Ủy ban nhân dân cấp tỉnh", False),
                ("người đứng đầu cơ sở giáo dục", False),
            ],
        )
        self.assertTrue(ket_qua[0].trich.endswith("do Hội đồng nhân dân cấp tỉnh quyết định."))

    def test_trach_nhiem_va_tiep_nhan_khong_phai_giao_quyen(self):
        for cau in (
            "Ủy ban nhân dân cấp tỉnh có trách nhiệm hướng dẫn thực hiện.",
            "Hồ sơ do Sở Giáo dục và Đào tạo tiếp nhận.",
            "Do Bộ trưởng Bộ Giáo dục và Đào tạo quy định.",
        ):
            self.assertEqual(pc.trich_phan_cap(cau), [], cau)

    def test_cac_co_quan(self):
        for cau, co_quan in (
            ("Mức chi do UBND tỉnh quyết định.", "Ủy ban nhân dân cấp tỉnh"),
            ("Giao Giám đốc Sở Giáo dục và Đào tạo phê duyệt kế hoạch.", "Sở Giáo dục và Đào tạo"),
            ("Học phí do Hội đồng trường quyết định.", "Hội đồng trường"),
            ("Định mức do thủ trưởng cơ sở giáo dục quy định trong quy chế chi tiêu nội bộ.",
             "người đứng đầu cơ sở giáo dục"),
            ("Mức hỗ trợ do Ủy ban nhân dân cấp xã quyết định.", "Ủy ban nhân dân cấp xã/huyện"),
        ):
            self.assertEqual([m.co_quan for m in pc.trich_phan_cap(cau)], [co_quan], cau)

    def test_khung(self):
        self.assertTrue(pc.trich_phan_cap("Mức thu không vượt quá 300 nghìn đồng, do HĐND tỉnh quyết định.")[0].co_khung)
        self.assertFalse(pc.trich_phan_cap("Số lớp do Hiệu trưởng quyết định.")[0].co_khung)


class LienQuanTests(unittest.TestCase):
    def setUp(self):
        self.cac = pc.trich_phan_cap(DIEU_HOC_PHI)

    def _co_quan(self, cau_hoi):
        return [m.co_quan for m in self.cac if pc.lien_quan(cau_hoi, m)]

    def test_chi_cau_giao_quyen_cung_chu_de(self):
        self.assertEqual(self._co_quan("Học phí trường công lập ở TP.HCM bao nhiêu?"), ["Hội đồng nhân dân cấp tỉnh"])
        self.assertEqual(self._co_quan("Mỗi khối có bao nhiêu lớp?"), ["người đứng đầu cơ sở giáo dục"])

    def test_cap_tu_chung_khong_tinh(self):
        # "quy định", "bao nhiêu"... có ở mọi câu: không đủ để coi là cùng chủ đề.
        self.assertEqual(self._co_quan("Quy định bao nhiêu?"), [])


class DauRaTests(unittest.TestCase):
    def test_ghi_chu_prompt(self):
        self.assertIsNone(pc.ghi_chu_prompt([]))
        muc = pc.trich_phan_cap(DIEU_HOC_PHI)
        ghi_chu = pc.ghi_chu_prompt([(2, muc[0])])
        self.assertIn('Khối [2]: "Căn cứ khung học phí', ghi_chu)
        self.assertIn("nêu khung (tối đa/tối thiểu)", ghi_chu)
        self.assertNotIn("nêu khung", pc.ghi_chu_prompt([(1, muc[2])]))

    def test_canh_bao_moi_nguon_moi_co_quan_mot_lan(self):
        muc = pc.trich_phan_cap(DIEU_HOC_PHI + "\nMức thu do Hội đồng nhân dân cấp tỉnh quyết định.")
        hdnd = [m for m in muc if m.co_quan.startswith("Hội đồng nhân dân")]
        canh_bao = pc.canh_bao([(1, m) for m in hdnd])
        self.assertEqual(len(canh_bao), 1)
        self.assertEqual(canh_bao[0]["loai"], "phan_cap")
        self.assertIn("Nguồn [1] giao cho Hội đồng nhân dân cấp tỉnh quyết định trong khung", canh_bao[0]["thong_bao"])


if __name__ == "__main__":
    unittest.main()
