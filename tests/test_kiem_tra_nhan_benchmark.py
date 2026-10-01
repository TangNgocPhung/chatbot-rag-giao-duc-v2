"""
Test việc đối chiếu nhãn nguồn của bộ câu hỏi benchmark với tên tệp trong kho.
Không cần kho thật: danh sách tên tệp được truyền thẳng vào.
"""

import unittest

import kiem_tra_nhan_benchmark as kt


def _cau(*nhan, cau_hoi="q", nhom="a", tap="dev"):
    return {"cau_hoi": cau_hoi, "nguon_mong_doi": list(nhan), "nhom": nhom, "tap": tap}


class DoiChieuTests(unittest.TestCase):
    CHI_MUC = ["05-bgddt.pdf", "a-dạy thêm.pdf", "b-dạy thêm.pdf"]

    def test_nhan_khop_tep_da_lap_chi_muc_thi_khong_co_van_de(self):
        self.assertEqual(kt.doi_chieu([_cau("05-BGDDT")], self.CHI_MUC, self.CHI_MUC), [])

    def test_nhan_khong_khop_tep_nao_la_loi(self):
        van_de = kt.doi_chieu([_cau("go-sai")], self.CHI_MUC, self.CHI_MUC)
        self.assertEqual([(v.nhan, v.loai) for v in van_de], [("go-sai", kt.KHONG_CO)])

    def test_tep_chi_co_tren_dia_la_chua_lap_chi_muc(self):
        van_de = kt.doi_chieu([_cau("sgk")], self.CHI_MUC, self.CHI_MUC + ["01-sgk-toan-1.pdf"])
        self.assertEqual(van_de[0].loai, kt.CHUA_LAP_CHI_MUC)
        self.assertEqual(van_de[0].tep_khop, ["01-sgk-toan-1.pdf"])

    def test_nhan_qua_rong_chi_la_canh_bao(self):
        van_de = kt.doi_chieu([_cau("dạy thêm")], self.CHI_MUC, self.CHI_MUC, nguong_mo_ho=1)
        self.assertEqual(van_de[0].loai, kt.MO_HO)
        self.assertNotIn(kt.MO_HO, kt.LA_LOI)

    def test_xet_tung_nhan_cua_cau_nhieu_nhan(self):
        van_de = kt.doi_chieu([_cau("05-bgddt", "khong-co")], self.CHI_MUC, self.CHI_MUC)
        self.assertEqual([v.nhan for v in van_de], ["khong-co"])

    def test_cau_ngoai_pham_vi_khong_co_nhan_thi_bo_qua(self):
        cau = {"cau_hoi": "q", "mong_doi_tu_choi": True, "nhom": "ngoai_pham_vi", "tap": "dev"}
        self.assertEqual(kt.doi_chieu([cau], self.CHI_MUC, self.CHI_MUC), [])


if __name__ == "__main__":
    unittest.main()
