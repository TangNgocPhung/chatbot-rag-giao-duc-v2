"""Script chạy đo một lệnh: kiểm tra điều kiện, chạy từng bước, gom báo cáo."""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import requests

import chay_do_luong as cd


def _phan_hoi_ollama(*ten_model):
    phan_hoi = MagicMock()
    phan_hoi.json.return_value = {"models": [{"name": ten} for ten in ten_model]}
    return phan_hoi


class KiemTraDieuKienTests(unittest.TestCase):
    def test_thieu_chi_muc_thi_khong_dat(self):
        with tempfile.TemporaryDirectory() as tam:
            kq = cd.kiem_tra_chi_muc(tam)
            self.assertFalse(kq.dat)
            self.assertIn("index.faiss", kq.chi_tiet)
            for ten in ("index.faiss", "index.pkl"):
                with open(os.path.join(tam, ten), "wb") as tep:
                    tep.write(b"x")
            self.assertTrue(cd.kiem_tra_chi_muc(tam).dat)

    def test_ollama_khong_chay(self):
        with patch.object(cd.requests, "get", side_effect=requests.ConnectionError("tu choi")):
            kq = cd.kiem_tra_ollama("llama3.2:3b")
        self.assertFalse(kq.dat)
        self.assertIn("Mở Ollama", kq.chi_tiet)

    def test_ollama_thieu_model_thi_chi_lenh_pull(self):
        with patch.dict(os.environ, {"RAG_EMBEDDING_MODEL": "bge-m3"}), \
                patch.object(cd.requests, "get", return_value=_phan_hoi_ollama("bge-m3:latest")):
            kq = cd.kiem_tra_ollama("llama3.2:3b")
        self.assertFalse(kq.dat)
        self.assertIn("ollama pull llama3.2:3b", kq.chi_tiet)
        self.assertNotIn("bge-m3", kq.chi_tiet)

    def test_ollama_du_model(self):
        with patch.dict(os.environ, {"RAG_EMBEDDING_MODEL": "bge-m3"}), \
                patch.object(cd.requests, "get", return_value=_phan_hoi_ollama("bge-m3:latest", "llama3.2:3b")):
            self.assertTrue(cd.kiem_tra_ollama("llama3.2:3b").dat)

    def test_model_tra_loi_cung_thu_tu_uu_tien_voi_dich_vu(self):
        with tempfile.TemporaryDirectory() as tam:
            cai_dat = os.path.join(tam, "cai_dat.json")
            with open(cai_dat, "w", encoding="utf-8") as tep:
                json.dump({"llm_model": "qwen3:8b"}, tep)
            with patch.dict(os.environ, {"RAG_CAI_DAT": cai_dat}):
                os.environ.pop("RAG_LLM_MODEL", None)
                self.assertEqual(cd._model_tra_loi(), "qwen3:8b")
                with patch.dict(os.environ, {"RAG_LLM_MODEL": "gemma3:4b"}):
                    self.assertEqual(cd._model_tra_loi(), "gemma3:4b")

    def test_bo_cau_hoi_cua_du_an_co_du(self):
        self.assertTrue(cd.kiem_tra_bo_cau_hoi().dat)


class ChayBuocTests(unittest.TestCase):
    def test_giu_dau_ra_tieng_viet_va_ma_thoat(self):
        da_in = []
        kq = cd.chay_buoc("thử", [sys.executable, "-c", "print('Định mức tiết dạy'); raise SystemExit(3)"],
                          ghi=da_in.append)
        self.assertEqual(kq.ma_thoat, 3)
        self.assertEqual(kq.dau_ra, "Định mức tiết dạy")
        self.assertIn("Định mức tiết dạy", da_in)

    def test_lenh_khong_ton_tai(self):
        kq = cd.chay_buoc("hỏng", ["khong-co-lenh-nay-xyz"], ghi=lambda *_: None)
        self.assertEqual(kq.ma_thoat, -1)


class MainTests(unittest.TestCase):
    DAT = [cd.KetQuaKiemTra("Chỉ mục FAISS", True, "ok")]

    def setUp(self):
        self._tam = tempfile.TemporaryDirectory()
        self.bao_cao = os.path.join(self._tam.name, "bao_cao.md")

    def tearDown(self):
        self._tam.cleanup()

    def _chay(self, kiem_tra, cac_buoc, *tham_so):
        with patch.object(cd, "kiem_tra_tat_ca", return_value=kiem_tra), \
                patch.object(cd, "cac_buoc_mac_dinh", return_value=cac_buoc), \
                patch("builtins.print"):
            return cd.main(["--ra", self.bao_cao, *tham_so])

    def test_chua_du_dieu_kien_thi_dung_truoc_khi_do(self):
        buoc = [("không được chạy", ["khong-co-lenh-nay-xyz"])]
        ma = self._chay([cd.KetQuaKiemTra("Ollama", False, "tắt")], buoc)
        self.assertEqual(ma, 2)
        self.assertFalse(os.path.exists(self.bao_cao))

    def test_chi_kiem_tra(self):
        self.assertEqual(self._chay(self.DAT, [("x", ["khong-co-lenh-nay-xyz"])], "--chi-kiem-tra"), 0)
        self.assertFalse(os.path.exists(self.bao_cao))

    def test_buoc_loi_van_giu_so_cua_buoc_khac(self):
        cac_buoc = [
            ("Bước tốt", [sys.executable, "-c", "print('Hit@1 0.80')"]),
            ("Bước hỏng", [sys.executable, "-c", "print('LỖI KHỞI TẠO'); raise SystemExit(1)"]),
        ]
        self.assertEqual(self._chay(self.DAT, cac_buoc), 1)
        with open(self.bao_cao, encoding="utf-8") as tep:
            noi_dung = tep.read()
        self.assertIn("## Bước tốt: xong", noi_dung)
        self.assertIn("Hit@1 0.80", noi_dung)
        self.assertIn("## Bước hỏng: LỖI (mã thoát 1)", noi_dung)
        self.assertIn("đạt · Chỉ mục FAISS", noi_dung)


class BaoCaoTests(unittest.TestCase):
    def test_do_ir_tren_tap_dev_va_doc_dung_bang_cua_tap_do(self):
        # Quyết định bật tuỳ chọn là chọn tham số: phải đo trên dev, không nhìn test.
        lenh_ir = dict(cd.cac_buoc_mac_dinh(False, True))["Đo IR (tập dev)"]
        self.assertEqual(lenh_ir[-2:], ["--tap", "dev"])
        self.assertTrue(cd.DUONG_DAN_BANG_IR.endswith("bang_chi_so_ir_dev.md"))

    def test_bang_ir_chi_kem_khi_buoc_ir_vua_chay_xong(self):
        ir = cd.KetQuaBuoc("Đo IR", ["python", "benchmark_chatbot.py", "--ir"], 0, 60.0, "...")
        moc = cd.KetQuaBuoc("Đo mốc", ["python", "benchmark_moc_thoi_gian.py"], 0, 60.0, "...")
        luc = datetime(2026, 10, 1, 9, 0)
        self.assertIn("## Bảng chỉ số IR (tập dev)", cd.viet_bao_cao([], [ir, moc], luc, "| MRR |"))
        # Bỏ qua bước IR thì bảng trên đĩa là của lần chạy cũ, không được trộn vào.
        self.assertNotIn("## Bảng chỉ số IR (tập dev)", cd.viet_bao_cao([], [moc], luc, "| MRR |"))
        ir_loi = cd.KetQuaBuoc("Đo IR", ir.lenh, 1, 5.0, "lỗi")
        self.assertNotIn("## Bảng chỉ số IR (tập dev)", cd.viet_bao_cao([], [ir_loi], luc, "| MRR |"))


if __name__ == "__main__":
    unittest.main()
