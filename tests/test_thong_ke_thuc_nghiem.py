"""Khóa mẫu số của các phép đo, đặc biệt lỗi hạ tầng và thiếu trích dẫn."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import tong_hop_thuc_nghiem as report


class MetricsTests(unittest.TestCase):
    def test_loi_khong_duoc_dem_la_tu_choi_dung_va_thieu_trich_dan_khong_tang_ty_le(self):
        labels = [{"cau_hoi": "ngoai", "tap": "test", "mong_doi_tu_choi": True},
                  {"cau_hoi": "loi", "tap": "test", "mong_doi_tu_choi": True},
                  {"cau_hoi": "co_dan", "tap": "test"},
                  {"cau_hoi": "thieu_dan", "tap": "test"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bo_cau_hoi_benchmark.json").write_text(json.dumps({"cau_hoi": labels}), encoding="utf-8")
            out = root / "out"
            out.mkdir()
            for i, q in enumerate(labels):
                r = {"cau_hoi": q["cau_hoi"], "thu_tu": i + 1, "done": i != 1,
                     "su_kien": [{"type": "warning"}] if i == 2 else [],
                     "ket_qua": {"loi": "timeout" if i == 1 else "", "tra_loi": "Nội dung [1]" if i == 2 else "Nội dung",
                                 "da_tu_choi": i < 2, "trich_dan_hop_le": True,
                                 "so_lieu_co_can_cu": i != 2, "giay": 1}}
                (out / f"cau_{i:03d}.json").write_text(json.dumps(r), encoding="utf-8")
            with patch.object(report, "ROOT", root):
                stats, _ = report.summarize(out)
            self.assertEqual(stats["tu_choi_dung_ngoai_pham_vi"], report.ratio(1, 1))
            self.assertEqual(stats["so_cau_loi_hoac_khong_done"], 1)
            self.assertEqual(stats["co_canh_bao_hau_kiem"], report.ratio(1, 3))
            self.assertEqual(stats["co_trich_dan_tren_cau_tra_loi_noi_dung"], report.ratio(1, 2))
            self.assertEqual(stats["trich_dan_khong_vuot_so_nguon_tren_cau_co_trich_dan"], report.ratio(1, 1))
            self.assertFalse(stats["hoan_tat_200"])

    def test_mau_so_rong_la_chua_do_khong_phai_100_phan_tram(self):
        self.assertIsNone(report.ratio(0, 0)["ty_le"])


if __name__ == "__main__":
    unittest.main()
