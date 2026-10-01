"""
Test phần benchmark nối với bộ chỉ số IR: chấm thứ hạng và tính lại chỉ số từ
tệp kết quả cũ. Không đụng tới FAISS/Ollama.
"""

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

import benchmark_chatbot


class ChamThuHangTests(unittest.TestCase):
    def _cham(self, nguon, mong_doi):
        kq = benchmark_chatbot.KetQuaMotCau(cau_hoi="c", nhom="n")
        kq.nguon = nguon
        benchmark_chatbot._cham_diem(kq, {"cau_hoi": "c", "nguon_mong_doi": mong_doi})
        return kq

    def test_hai_chunk_cung_file_khong_day_tai_lieu_sau_xuong_hai_bac(self):
        # Nguồn đúng đứng ngay sau hai chunk của cùng một file khác: ở mức tài
        # liệu nó là hạng 2, dù ở mức chunk là hạng 3.
        kq = self._cham(["a.pdf", "a.pdf", "Luật Giáo Dục.pdf"], ["Luật Giáo Dục"])
        self.assertEqual(kq.thu_hang_nguon_dung, [2])
        self.assertEqual(kq.thu_hang_chunk_dung, [3])
        self.assertTrue(kq.truy_hoi_dung_nguon)

    def test_truot_thi_khong_co_thu_hang_va_khong_tinh_la_dung(self):
        kq = self._cham(["a.pdf", "b.pdf"], ["Luật Giáo Dục"])
        self.assertEqual(kq.thu_hang_nguon_dung, [])
        self.assertFalse(kq.truy_hoi_dung_nguon)

    def test_khong_co_nhan_thi_khong_cham_truy_hoi(self):
        kq = benchmark_chatbot.KetQuaMotCau(cau_hoi="c")
        kq.nguon = ["a.pdf"]
        benchmark_chatbot._cham_diem(kq, {"cau_hoi": "c"})
        self.assertIsNone(kq.truy_hoi_dung_nguon)
        self.assertEqual(kq.so_nguon_mong_doi, 0)

    def test_cau_loi_ha_tang_bi_loai_chu_khong_tinh_la_truot(self):
        # Ollama nghẽn giữa chừng từng làm MRR tụt 0.01 giữa hai lần chạy cùng
        # một cấu hình - đó là nhiễu máy móc, không phải chất lượng xếp hạng.
        tot = self._cham(["Luật Giáo Dục.pdf"], ["Luật Giáo Dục"])
        hong = self._cham([], ["Luật Giáo Dục"])
        hong.loi = "ResponseError: read blob ..."
        hong.loi_ha_tang = True
        luot = benchmark_chatbot._luot_truy_hoi([tot, hong])
        self.assertEqual(len(luot), 1)

    def test_cum_la_nhan_dau_tien_khong_phan_biet_hoa_thuong(self):
        kq = self._cham(["Luật Giáo Dục.pdf"], ["Luật Giáo Dục", "Khung"])
        self.assertEqual(benchmark_chatbot._luot_truy_hoi([kq])[0].cum, "luật giáo dục")

    def test_in_rieng_so_lieu_cau_them_sau_chia(self):
        cu = self._cham(["a.pdf", "Luật Giáo Dục.pdf"], ["Luật Giáo Dục"])
        moi = self._cham(["Luật Viên Chức.pdf"], ["Luật Viên Chức"])
        moi.cau_hoi = "câu mới"
        with mock.patch.object(benchmark_chatbot, "_cau_them_sau_chia",
                               return_value={"câu mới"}), redirect_stdout(io.StringIO()) as ra:
            tom_tat = benchmark_chatbot.in_bang_chi_so_ir([cu, moi], so_chunk=4)
        self.assertEqual(tom_tat["cau_them_sau_chia"]["so_cau"], 1)
        self.assertAlmostEqual(tom_tat["cau_them_sau_chia"]["mrr"], 1.0)
        self.assertIn("Riêng 1 câu thêm sau khi chia tập", ra.getvalue())

    def test_khong_co_cau_them_sau_chia_thi_khong_in(self):
        kq = self._cham(["Luật Giáo Dục.pdf"], ["Luật Giáo Dục"])
        with mock.patch.object(benchmark_chatbot, "_cau_them_sau_chia",
                               return_value=set()), redirect_stdout(io.StringIO()):
            tom_tat = benchmark_chatbot.in_bang_chi_so_ir([kq], so_chunk=4)
        self.assertIsNone(tom_tat["cau_them_sau_chia"])

    def test_pdf_chua_ocr_van_tinh_la_truot(self):
        # Ngược lại: PDF chưa OCR là giới hạn thật, người dùng thật cũng không
        # có câu trả lời, nên phải nằm trong mẫu.
        hong = self._cham([], ["Luật Giáo Dục"])
        hong.loi = "ValueError: PDF chưa có lớp văn bản"
        hong.ly_do_chan = "khong_truy_hoi_duoc"
        luot = benchmark_chatbot._luot_truy_hoi([hong])
        self.assertEqual(len(luot), 1)
        self.assertEqual(luot[0].thu_hang, [])

    def test_cau_khong_co_nhan_bi_loai_khoi_phep_do_ir(self):
        co_nhan = self._cham(["Luật Giáo Dục.pdf"], ["Luật Giáo Dục"])
        khong_nhan = benchmark_chatbot.KetQuaMotCau(cau_hoi="lạc đề", nhom="ngoai_pham_vi")
        luot = benchmark_chatbot._luot_truy_hoi([co_nhan, khong_nhan])
        self.assertEqual(len(luot), 1)
        self.assertEqual(luot[0].thu_hang, [1])


class DuongDanKetQuaIrTests(unittest.TestCase):
    """Lần chạy một nhóm từng ghi đè mất bảng 97 câu dùng cho báo cáo. Khóa lại
    hành vi tách tệp để lỗi đó không quay lại."""

    def test_chay_ca_bo_ghi_vao_tep_chinh(self):
        self.assertEqual(
            benchmark_chatbot._duong_dan_ir(None, None),
            (benchmark_chatbot.DUONG_DAN_KET_QUA_IR, benchmark_chatbot.DUONG_DAN_BANG_IR),
        )

    def test_loc_nhom_hoac_lay_mau_ghi_ra_tep_rieng(self):
        for nhom, so in (("video", None), (None, 20), ("video", 20)):
            duong_dan = benchmark_chatbot._duong_dan_ir(nhom, so)
            self.assertNotIn(benchmark_chatbot.DUONG_DAN_KET_QUA_IR, duong_dan)
            self.assertNotIn(benchmark_chatbot.DUONG_DAN_BANG_IR, duong_dan)
        self.assertTrue(
            benchmark_chatbot._duong_dan_ir("video", None)[1].endswith("_video.md"))


class DoIrTuTepTests(unittest.TestCase):
    """Tính lại chỉ số từ tệp kết quả cũ - đường đi so sánh hai cấu hình mà
    không phải chạy lại cả bộ, nên phải chắc nó đọc đúng nhãn."""

    def _tep_ket_qua(self, thu_muc, cac_luot):
        duong_dan = os.path.join(thu_muc, "ket_qua.json")
        with open(duong_dan, "w", encoding="utf-8") as f:
            json.dump({"chay_luc": "2026-01-01 00:00:00", "che_do": "nhanh",
                       "model": "test", "ket_qua": cac_luot}, f, ensure_ascii=False)
        return duong_dan

    def test_doc_nhan_kem_trong_tep_va_in_ra_chi_so(self):
        with tempfile.TemporaryDirectory() as thu_muc:
            duong_dan = self._tep_ket_qua(thu_muc, [
                {"cau_hoi": "c1", "nhom": "a", "nguon": ["x.pdf", "Luật Giáo Dục.pdf"],
                 "nguon_mong_doi": ["Luật Giáo Dục"]},
                {"cau_hoi": "c2", "nhom": "a", "nguon": ["Điều lệ trường.pdf"],
                 "nguon_mong_doi": ["Điều lệ"]},
            ])
            man_hinh = io.StringIO()
            with redirect_stdout(man_hinh):
                ma_thoat = benchmark_chatbot.do_ir_tu_tep(duong_dan)
            ket_qua = man_hinh.getvalue()
        self.assertEqual(ma_thoat, 0)
        # MRR = (1/2 + 1/1) / 2 = 0.75
        self.assertIn("MRR@10 = 0.750", ket_qua)

    def test_tep_khong_co_luot_nao_khop_nhan_thi_bao_loi_chu_khong_no(self):
        with tempfile.TemporaryDirectory() as thu_muc:
            duong_dan = self._tep_ket_qua(thu_muc, [
                {"cau_hoi": "câu lạc đề không có trong bộ đề", "nguon": ["x.pdf"]},
            ])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(benchmark_chatbot.do_ir_tu_tep(duong_dan), 1)


if __name__ == "__main__":
    unittest.main()
