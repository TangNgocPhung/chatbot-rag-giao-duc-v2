"""
Test việc chia bộ câu hỏi benchmark thành tập dev / test và việc benchmark lọc
đúng theo tập. Không đụng tới FAISS/Ollama.
"""

import io
import json
import os
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stdout
from unittest import mock

import benchmark_chatbot
import chia_tap_benchmark as ct


def _bo_gia(so_cau_theo_nhom):
    return [
        {"cau_hoi": f"{nhom} {i}", "nhom": nhom}
        for nhom, so_cau in so_cau_theo_nhom.items()
        for i in range(so_cau)
    ]


class SoCauTestMucTieuTests(unittest.TestCase):
    def test_lam_tron_nua_len_khong_phai_ve_so_chan(self):
        # 5 * 0.4 = 2.0, 6 * 0.4 = 2.4, 14 * 0.4 = 5.6 -> 6, 30 * 0.4 = 12.
        self.assertEqual(ct.so_cau_test_muc_tieu(5, 0.4), 2)
        self.assertEqual(ct.so_cau_test_muc_tieu(6, 0.4), 2)
        self.assertEqual(ct.so_cau_test_muc_tieu(14, 0.4), 6)
        # round(2.5) == 2 trong Python; ở đây phải ra 3.
        self.assertEqual(ct.so_cau_test_muc_tieu(5, 0.5), 3)

    def test_nhom_nho_van_co_mat_o_ca_hai_tap(self):
        self.assertEqual(ct.so_cau_test_muc_tieu(2, 0.1), 1)
        self.assertEqual(ct.so_cau_test_muc_tieu(2, 0.9), 1)

    def test_nhom_mot_cau_thi_vao_dev(self):
        self.assertEqual(ct.so_cau_test_muc_tieu(1), 0)
        self.assertEqual(ct.gan_tap(_bo_gia({"le": 1}))[0]["tap"], ct.TAP_DEV)


class GanTapTests(unittest.TestCase):
    def test_phan_tang_dung_so_cau_moi_nhom(self):
        ket_qua = ct.gan_tap(_bo_gia({"lon": 50, "video": 5, "doc": 6}))
        bang = ct.thong_ke(ket_qua)
        self.assertEqual(bang["lon"], Counter(dev=30, test=20))
        self.assertEqual(bang["video"], Counter(dev=3, test=2))
        self.assertEqual(bang["doc"], Counter(dev=4, test=2))

    def test_tat_dinh_qua_cac_lan_chay(self):
        bo = _bo_gia({"a": 20, "b": 9})
        self.assertEqual(ct.gan_tap(bo), ct.gan_tap(bo))

    def test_khong_sua_danh_sach_dau_vao(self):
        bo = _bo_gia({"a": 5})
        ct.gan_tap(bo)
        self.assertTrue(all("tap" not in muc for muc in bo))

    def test_cau_da_gan_khong_bao_gio_bi_doi_tap(self):
        # Đổi một câu từ test sang dev sau khi đã thấy kết quả test là rò rỉ;
        # gán tay "toàn bộ là test" cũng phải được tôn trọng nguyên vẹn.
        bo = [{"cau_hoi": f"q{i}", "nhom": "a", "tap": "test"} for i in range(5)]
        self.assertEqual([m["tap"] for m in ct.gan_tap(bo)], ["test"] * 5)

    def test_them_cau_moi_giu_cau_cu_va_keo_ty_le_ve_muc_tieu(self):
        cu = ct.gan_tap(_bo_gia({"a": 10}))
        moi = [{"cau_hoi": f"moi {i}", "nhom": "a"} for i in range(5)]
        ket_qua = ct.gan_tap(cu + moi)
        self.assertEqual(ket_qua[:10], cu)
        # Mục tiêu cho 15 câu là 6 test; 10 câu cũ đã có 4 nên thêm đúng 2.
        self.assertEqual(Counter(m["tap"] for m in ket_qua[10:]), Counter(dev=3, test=2))

    def test_gia_tri_tap_la_bi_tu_choi(self):
        with self.assertRaises(ValueError):
            ct.gan_tap([{"cau_hoi": "q", "nhom": "a", "tap": "validation"}])


class BoCauHoiThatTests(unittest.TestCase):
    """Khóa trạng thái của tệp bo_cau_hoi_benchmark.json đang theo dõi trong Git."""

    @classmethod
    def setUpClass(cls):
        with open(ct.DUONG_DAN_BO_CAU_HOI, encoding="utf-8") as f:
            cls.bo = json.load(f)["cau_hoi"]

    def test_moi_cau_deu_co_tap_hop_le(self):
        self.assertTrue(all(muc.get("tap") in ct.CAC_TAP for muc in self.bo))

    def test_moi_nhom_deu_co_ca_dev_lan_test(self):
        for nhom, dem in ct.thong_ke(self.bo).items():
            with self.subTest(nhom=nhom):
                self.assertGreater(dem[ct.TAP_DEV], 0)
                self.assertGreater(dem[ct.TAP_TEST], 0)

    def test_khong_co_cau_trung_lap(self):
        # Hai câu y hệt ở hai tập là rò rỉ thẳng từ dev sang test.
        cac_cau = [muc["cau_hoi"].casefold().strip() for muc in self.bo]
        self.assertEqual(len(cac_cau), len(set(cac_cau)))

    def test_cau_nao_cung_co_nhan_hoac_la_cau_phai_tu_choi(self):
        for muc in self.bo:
            with self.subTest(cau=muc["cau_hoi"][:60]):
                self.assertNotEqual(bool(muc.get("nguon_mong_doi")), bool(muc.get("mong_doi_tu_choi")))
                self.assertEqual(muc["nhom"] == "ngoai_pham_vi", bool(muc.get("mong_doi_tu_choi")))

    def test_danh_dau_them_sau_chia_chi_mang_gia_tri_true(self):
        # Ghi `false` cho câu cũ là thừa và dễ gõ nhầm; thiếu trường nghĩa là câu
        # có từ trước khi chia tập.
        for muc in self.bo:
            if "them_sau_chia" in muc:
                self.assertIs(muc["them_sau_chia"], True)

    def test_chay_lai_script_khong_doi_gi(self):
        self.assertEqual(ct.gan_tap(self.bo), self.bo)

    def test_ghi_lai_giu_nguyen_tung_byte(self):
        # Định dạng một-câu-một-dòng là để diff Git đọc được; ghi lại tệp đã
        # chia xong không được sinh ra diff nào.
        with open(ct.DUONG_DAN_BO_CAU_HOI, encoding="utf-8") as f:
            goc = f.read()
        with tempfile.TemporaryDirectory() as thu_muc:
            duong_dan = os.path.join(thu_muc, "bo.json")
            ct.ghi_bo_cau_hoi(json.loads(goc), duong_dan)
            with open(duong_dan, encoding="utf-8") as f:
                self.assertEqual(f.read(), goc)


class BenchmarkLocTheoTapTests(unittest.TestCase):
    def _voi_bo(self, cac_cau):
        thu_muc = tempfile.TemporaryDirectory()
        self.addCleanup(thu_muc.cleanup)
        duong_dan = os.path.join(thu_muc.name, "bo.json")
        with open(duong_dan, "w", encoding="utf-8") as f:
            json.dump({"cau_hoi": cac_cau}, f, ensure_ascii=False)
        va_duong_dan = mock.patch.object(benchmark_chatbot, "DUONG_DAN_BO_CAU_HOI", duong_dan)
        va_duong_dan.start()
        self.addCleanup(va_duong_dan.stop)

    def test_chi_lay_cau_thuoc_tap_duoc_chon(self):
        self._voi_bo([
            {"cau_hoi": "d", "nhom": "a", "tap": "dev"},
            {"cau_hoi": "t", "nhom": "a", "tap": "test"},
        ])
        nap = benchmark_chatbot._nap_danh_sach
        self.assertEqual([m["cau_hoi"] for m in nap(None, None, "dev")], ["d"])
        self.assertEqual([m["cau_hoi"] for m in nap(None, None, "test")], ["t"])
        self.assertEqual(len(nap(None, None, "tat_ca")), 2)

    def test_cau_chua_gan_tap_thi_bao_loi_chu_khong_lang_le_bo(self):
        self._voi_bo([
            {"cau_hoi": "d", "nhom": "a", "tap": "dev"},
            {"cau_hoi": "câu mới thêm", "nhom": "a"},
        ])
        with self.assertRaises(ValueError):
            benchmark_chatbot._nap_danh_sach(None, None, "dev")
        # Chạy cả bộ thì không cần trường tap.
        self.assertEqual(len(benchmark_chatbot._nap_danh_sach(None, None, "tat_ca")), 2)

    def test_tinh_lai_tu_tep_chi_dem_cau_cua_tap(self):
        self._voi_bo([
            {"cau_hoi": "c1", "nhom": "a", "nguon_mong_doi": ["Luật"], "tap": "dev"},
            {"cau_hoi": "c2", "nhom": "a", "nguon_mong_doi": ["Điều lệ"], "tap": "test"},
        ])
        with tempfile.TemporaryDirectory() as thu_muc:
            duong_dan = os.path.join(thu_muc, "kq.json")
            with open(duong_dan, "w", encoding="utf-8") as f:
                json.dump({"ket_qua": [
                    {"cau_hoi": "c1", "nhom": "a", "nguon": ["Luật.pdf"]},
                    {"cau_hoi": "c2", "nhom": "a", "nguon": ["x.pdf", "Điều lệ.pdf"]},
                ]}, f, ensure_ascii=False)
            for tap, mrr in (("dev", "1.000"), ("test", "0.500"), ("tat_ca", "0.750")):
                man_hinh = io.StringIO()
                with redirect_stdout(man_hinh):
                    self.assertEqual(benchmark_chatbot.do_ir_tu_tep(duong_dan, tap), 0)
                with self.subTest(tap=tap):
                    self.assertIn(f"MRR@10 = {mrr}", man_hinh.getvalue())


class DuongDanTheoTapTests(unittest.TestCase):
    """Một lượt dev chạy thử không được ghi đè số liệu test của báo cáo."""

    def test_moi_tap_mot_tep_rieng(self):
        cac_tep = {benchmark_chatbot._duong_dan_ir(None, None, tap)[1]
                   for tap in benchmark_chatbot.CAC_LUA_CHON_TAP}
        self.assertEqual(len(cac_tep), 3)
        self.assertTrue(
            benchmark_chatbot._duong_dan_ir(None, None, "test")[1].endswith("bang_chi_so_ir_test.md"))
        self.assertNotEqual(benchmark_chatbot._duong_dan_ket_qua(True, "dev"),
                            benchmark_chatbot._duong_dan_ket_qua(True, "test"))

    def test_tat_ca_giu_ten_tep_cu(self):
        self.assertEqual(benchmark_chatbot._duong_dan_ir(None, None, "tat_ca"),
                         benchmark_chatbot._duong_dan_ir(None, None))


class DongLenhTests(unittest.TestCase):
    def test_quet_nguong_tren_tap_test_bi_chan(self):
        with mock.patch("sys.argv", ["benchmark_chatbot.py", "--nhanh", "--do-nguong",
                                     "--tap", "test"]), \
                mock.patch.object(benchmark_chatbot, "RAGService") as dich_vu, \
                redirect_stdout(io.StringIO()), \
                mock.patch("sys.stderr", io.StringIO()):
            with self.assertRaises(SystemExit) as loi:
                benchmark_chatbot.main()
        self.assertEqual(loi.exception.code, 2)
        dich_vu.assert_not_called()


if __name__ == "__main__":
    unittest.main()
