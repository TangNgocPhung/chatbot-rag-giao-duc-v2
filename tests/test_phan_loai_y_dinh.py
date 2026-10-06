"""Bộ phân loại ý định câu hỏi (KNN) và chỗ nối của nó vào luồng trả lời.

Hai thứ phải chốt:
  - Thuật toán: bỏ phiếu theo độ tương đồng, độ tin cậy là tỉ lệ phiếu, kiểm
    định chéo bỏ-một không cho câu mẫu tự bầu cho chính nó.
  - Chỗ nối: chỉ chặn sớm khi đủ chắc, không chặn câu nối tiếp hay câu đang
    lọc phạm vi, và công cụ tính vẫn đi trước. Chặn nhầm là lỗi nặng nhất -
    người hỏi đúng chỗ mà bị bảo "ngoài phạm vi".
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import phan_loai_y_dinh as pl
from rag_service import RAGService


def _cum(tam, so_cau, nhieu=0.05, seed=0):
    rng = np.random.default_rng(seed)
    return np.array(tam, dtype=np.float32) + rng.normal(0, nhieu, (so_cau, len(tam))).astype(np.float32)


class KNNTests(unittest.TestCase):
    def setUp(self):
        X = np.vstack([_cum([1, 0, 0], 5, seed=1), _cum([0, 1, 0], 5, seed=2), _cum([0, 0, 1], 5, seed=3)])
        nhan = ["a"] * 5 + ["b"] * 5 + ["c"] * 5
        self.bo = pl.BoPhanLoaiKNN(X, nhan, [f"câu {i}" for i in range(15)], k=5)

    def test_doan_dung_cum_gan_nhat(self):
        kq = self.bo.du_doan([0.9, 0.1, 0.0], {"a": "Loại A"})
        self.assertEqual(kq["nhan"], "a")
        self.assertEqual(kq["ten_nhan"], "Loại A")
        self.assertEqual(kq["do_tin_cay"], 1.0)
        self.assertEqual(len(kq["lang_gieng"]), 3)
        self.assertTrue(all(lg["nhan"] == "a" for lg in kq["lang_gieng"]))

    def test_cau_lung_chung_thi_tin_cay_thap(self):
        """Câu nằm giữa hai cụm: vẫn đoán một nhãn nhưng tỉ lệ phiếu thấp -
        chính con số này giữ cho dịch vụ không tự chặn câu đó."""
        self.bo.k = 10  # đủ rộng để chạm cả hai cụm
        kq = self.bo.du_doan([1.0, 1.0, 0.0])
        self.assertIn(kq["nhan"], ("a", "b"))
        self.assertLess(kq["do_tin_cay"], 0.6)

    def test_phieu_theo_do_tuong_dong(self):
        """Hai láng giềng rất giống thắng ba láng giềng chỉ hơi giống."""
        X = np.array([[1, 0], [1, 0.02], [0.2, 1], [0.25, 1], [0.3, 1]], dtype=np.float32)
        bo = pl.BoPhanLoaiKNN(X, ["x", "x", "y", "y", "y"], list("abcde"), k=5)
        self.assertEqual(bo.du_doan([1, 0.1])["nhan"], "x")

    def test_bo_mot_khong_tu_bau(self):
        S = self.bo.X @ self.bo.X.T
        _, _, idx = self.bo.bo_phieu(S, k=3, bo_chinh_no=True)
        for i, hang in enumerate(idx):
            self.assertNotIn(i, hang)

    def test_luu_va_nap_lai(self):
        self.bo.van_tay = "abc"
        with tempfile.TemporaryDirectory() as thu_muc:
            duong = os.path.join(thu_muc, "mh.npz")
            self.bo.luu(duong)
            bo2 = pl.BoPhanLoaiKNN.nap(duong)
        self.assertEqual((bo2.k, bo2.van_tay, bo2.cau), (5, "abc", self.bo.cau))
        self.assertEqual(bo2.du_doan([0, 0, 1])["nhan"], "c")

    def test_do_luong(self):
        m = pl._do_luong(["a", "a", "b", "b"], ["a", "b", "b", "b"], ["a", "b"])
        self.assertEqual(m["accuracy"], 0.75)
        self.assertEqual(m["tung_lop"]["a"]["recall"], 0.5)
        self.assertEqual(m["tung_lop"]["b"]["precision"], round(2 / 3, 4))
        self.assertEqual(m["ma_tran_nham_lan"]["a"]["b"], 1)


class DuLieuTests(unittest.TestCase):
    def test_nhan_hop_le_va_du_cau(self):
        ten_nhan, train, test = pl.nap_du_lieu()
        dem = {n: sum(1 for _, x in train if x == n) for n in ten_nhan}
        for n, so in dem.items():
            self.assertGreaterEqual(so, 30, n)
        self.assertGreater(len(test), 150)

    def test_train_khong_trung_test(self):
        """Câu trong test (kể cả bộ benchmark) mà lọt vào train thì số đo vô nghĩa."""
        _, train, test = pl.nap_du_lieu()
        chuan = lambda c: " ".join(c.lower().split())
        cau_train = {chuan(c) for c, _ in train}
        self.assertEqual([m["cau_hoi"] for m in test if chuan(m["cau_hoi"]) in cau_train], [])

    def test_van_tay_doi_khi_cau_mau_doi(self):
        a = pl.van_tay([("xin chào", "chao_hoi")], "bge-m3")
        self.assertNotEqual(a, pl.van_tay([("xin chào", "chao_hoi"), ("hi", "chao_hoi")], "bge-m3"))
        self.assertNotEqual(a, pl.van_tay([("xin chào", "chao_hoi")], "nomic-embed-text"))

    def test_nguong_hanh_dong(self):
        self.assertEqual(pl.du_chac_de_hanh_dong({"nhan": "ngoai_pham_vi", "do_tin_cay": 0.9}, 0.7), "ngoai_pham_vi")
        self.assertIsNone(pl.du_chac_de_hanh_dong({"nhan": "ngoai_pham_vi", "do_tin_cay": 0.6}, 0.7))
        self.assertIsNone(pl.du_chac_de_hanh_dong({"nhan": "tra_cuu", "do_tin_cay": 1.0}, 0.7))
        self.assertIsNone(pl.du_chac_de_hanh_dong(None))

    def test_loi_chao_doi_nguong_cao_hon(self):
        """"Ai là tổng thống Mỹ?" từng được 0,7 phiếu chào hỏi: đủ để chặn câu
        ngoài phạm vi, nhưng chưa đủ để đáp "Xin chào!" thay câu trả lời."""
        with patch.dict(pl.NGUONG, {"ngoai_pham_vi": 0.7, "chao_hoi": 0.9}):
            self.assertIsNone(pl.du_chac_de_hanh_dong({"nhan": "chao_hoi", "do_tin_cay": 0.7}))
            self.assertEqual(pl.du_chac_de_hanh_dong({"nhan": "ngoai_pham_vi", "do_tin_cay": 0.7}), "ngoai_pham_vi")
            self.assertEqual(pl.du_chac_de_hanh_dong({"nhan": "chao_hoi", "do_tin_cay": 0.95}), "chao_hoi")


class _PhanLoaiGia:
    """Thay bộ phân loại thật: test không cần Ollama, chỉ cần một nhãn cố định."""

    def __init__(self, nhan, do_tin_cay=1.0):
        self.bo = object()
        self.y_dinh = {"nhan": nhan, "ten_nhan": nhan, "do_tin_cay": do_tin_cay, "k": 7, "lang_gieng": []}

    def du_doan(self, vector):
        return dict(self.y_dinh)


class _DaTruyHoi(Exception):
    pass


class ChoNoiTests(unittest.TestCase):
    def setUp(self):
        self.service = RAGService()
        self.service.status.state = "ready"
        self.service.goi_y_mo_dau = lambda *a, **k: []
        self.service._vector_cau_hoi = lambda cau: [0.1, 0.2]

    def chay(self, cau, nhan, do_tin_cay=1.0, **them):
        self.service.phan_loai_y_dinh = _PhanLoaiGia(nhan, do_tin_cay)

        def truy_hoi(*a, **k):
            raise _DaTruyHoi()

        with patch.object(self.service, "_retrieve", truy_hoi), \
             patch("cache_ngu_nghia.bat_cache", return_value=False):
            return list(self.service._sinh_cau_tra_loi(cau, **them))

    def test_chac_chan_ngoai_pham_vi_thi_tu_choi_ngay(self):
        su_kien = self.chay("giá vàng hôm nay", "ngoai_pham_vi")
        self.assertEqual([s["type"] for s in su_kien], ["y_dinh", "sources", "token", "goi_y", "done"])
        self.assertTrue(su_kien[-1]["abstained"])
        self.assertEqual(su_kien[-1]["ly_do_chan"], "y_dinh_ngoai_pham_vi")
        self.assertIn("ngoài phạm vi", su_kien[2]["content"])

    def test_chua_du_chac_thi_van_truy_hoi(self):
        with self.assertRaises(_DaTruyHoi):
            self.chay("giá vàng hôm nay", "ngoai_pham_vi", do_tin_cay=0.5)

    def test_cau_noi_tiep_khong_bi_chan(self):
        with self.assertRaises(_DaTruyHoi):
            self.chay("còn giáo viên thì sao", "ngoai_pham_vi",
                      history=[{"role": "user", "content": "học phí đại học"}])

    def test_dang_loc_pham_vi_khong_bi_chan(self):
        with self.assertRaises(_DaTruyHoi):
            self.chay("giá vàng hôm nay", "ngoai_pham_vi", pham_vi={"cap_hoc": ["Tiểu học"]})

    def test_loai_tra_cuu_di_duong_thuong(self):
        with self.assertRaises(_DaTruyHoi):
            self.chay("Luật Giáo dục quy định gì", "tra_cuu")

    def test_cong_cu_tinh_van_di_truoc(self):
        """KNN nhầm một phép tính thành ngoài phạm vi thì công cụ tính vẫn trả lời."""
        su_kien = self.chay("12% của 2.340.000 là bao nhiêu", "ngoai_pham_vi")
        self.assertEqual(su_kien[0]["type"], "y_dinh")
        self.assertEqual(su_kien[-1]["cong_cu"], "tinh_toan")

    def test_giua_hoi_thoai_van_dap_loi_chao_that(self):
        """Lỗi gặp khi chạy thử 6/10/2026: "Chào bạn" ở lượt thứ hai đi qua
        truy hồi rồi nhận "không tìm thấy" chỉ vì đã có lịch sử."""
        su_kien = self.chay("Chào bạn", "chao_hoi",
                            history=[{"role": "user", "content": "giá vàng"}])
        self.assertIn("Xin chào", su_kien[2]["content"])

    def test_cau_noi_tiep_giong_loi_chao_van_truy_hoi(self):
        """KNN đọc "nói rõ hơn", "tại sao vậy" thành chào hỏi với ~0,9 phiếu;
        giữa hội thoại thì chúng là câu hỏi tiếp, phải đi đường thường."""
        for cau in ("nói rõ hơn", "tại sao vậy", "cảm ơn, còn giáo viên THCS hạng II bậc 3 thì sao"):
            with self.subTest(cau=cau), self.assertRaises(_DaTruyHoi):
                self.chay(cau, "chao_hoi", history=[{"role": "user", "content": "học phí"}])

    def test_cam_on_thi_dap_lai(self):
        su_kien = self.chay("cảm ơn bạn nhiều", "chao_hoi")
        self.assertIn("Rất vui", su_kien[2]["content"])
        self.assertFalse(su_kien[-1]["abstained"])

    def test_chao_thi_gioi_thieu(self):
        su_kien = self.chay("xin chào", "chao_hoi")
        self.assertIn("Xin chào", su_kien[2]["content"])

    def test_chua_san_sang_thi_khong_nhung_som(self):
        """Bộ phân loại chưa train xong: không phát sự kiện y_dinh, đường cũ giữ nguyên."""
        self.service.phan_loai_y_dinh = pl.PhanLoaiYDinh()
        su_kien = list(self.service._sinh_cau_tra_loi("12% của 2.340.000 là bao nhiêu"))
        self.assertNotIn("y_dinh", [s["type"] for s in su_kien])


if __name__ == "__main__":
    unittest.main()
