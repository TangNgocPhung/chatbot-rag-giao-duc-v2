"""
Kiểm tính nhất quán của sổ quan hệ nhập tay (so_quan_he_van_ban.json).

Sổ được sửa tay thường xuyên, mỗi lần thêm vài ngày hiệu lực hoặc quan hệ. Chỉ
một lỗi gõ (đảo chiều tu/den, ngày sai định dạng, số hiệu không chuẩn) là đồ thị
hiệu lực chọn sai văn bản mà không báo lỗi gì, và nhãn của bộ câu hỏi mốc thời
gian (lấy từ sổ) cũng sai theo. Các test ở đây chỉ kiểm những điều mà quan hệ
pháp lý BẮT BUỘC phải thoả, không kiểm nội dung pháp lý.
"""

import json
import os
import re
import unittest
from collections import defaultdict
from datetime import date

import quan_he_van_ban as qh

DUONG_DAN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "so_quan_he_van_ban.json")
LOAI_HOP_LE = {"thay_the", "bai_bo_mot_phan", "sua_doi", "huong_dan", "kem_theo"}

# Luật Ban hành VBQPPL 2008 (Điều 78), 2015 (Điều 151) và 2025 (Điều 53): văn bản
# của cơ quan trung ương có hiệu lực không sớm hơn 45 ngày kể từ ngày thông qua
# hoặc ký, trừ trường hợp khẩn cấp / trình tự rút gọn / trường hợp đặc biệt.
# Văn bản ký trước 2009 theo luật cũ, không xét.
SO_NGAY_TOI_THIEU = 45
AP_DUNG_TU = date(2009, 1, 1)
# Văn bản đã biết là có hiệu lực sớm hơn, kèm lý do. Thêm vào đây chỉ khi đã
# kiểm nguyên văn; nếu không thì nhiều khả năng là gõ nhầm ngày.
HIEU_LUC_SOM = {
    "15/2020/TT-BGDĐT": "có hiệu lực kể từ ngày ký (ghi chú trong sổ)",
    "21/2025/TT-BGDĐT": "có hiệu lực kể từ ngày ký (ghi chú trong sổ)",
    "3/2026/TT-BGDĐT": "có hiệu lực kể từ ngày ký (ghi chú trong sổ)",
    "23/2026/TT-BGDĐT": "có hiệu lực kể từ ngày ký (ghi chú trong sổ)",
    "27/2026/TT-BGDĐT": "có hiệu lực kể từ ngày ký (ghi chú trong sổ)",
    "30/2026/TT-BGDĐT": "có hiệu lực kể từ ngày ký (ghi chú trong sổ)",
    "125/2014/TTLT-BTC": "44 ngày, đúng như văn bản ghi (ký 27/8/2014, hiệu lực 10/10/2014)",
    "123/2025/QH15": "Luật tự quy định hiệu lực 1/1/2026, 22 ngày sau khi thông qua",
}


def _nam_so_hieu(so_hieu: str) -> int | None:
    khop = re.search(r"/(\d{4})/", so_hieu)
    return int(khop.group(1)) if khop else None


class SoQuanHeNhapTayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DUONG_DAN, encoding="utf-8") as tep:
            so = json.load(tep)
        cls.van_ban = so["van_ban"]
        cls.quan_he = so["quan_he"]
        cls.loai_bo = so.get("loai_bo", [])

    def _ngay(self, so_hieu: str, truong: str) -> date | None:
        gia_tri = self.van_ban.get(so_hieu, {}).get(truong)
        return date.fromisoformat(gia_tri) if gia_tri else None

    def test_so_hieu_da_chuan_hoa(self):
        # Đồ thị tra theo số hiệu chuẩn; khoá lệch dạng thì quan hệ treo lơ lửng.
        for so_hieu in self.van_ban:
            self.assertEqual(qh.chuan_so_hieu(so_hieu), so_hieu)
        for q in self.quan_he:
            self.assertEqual(qh.chuan_so_hieu(q["tu"]), q["tu"], q)
            self.assertEqual(qh.chuan_so_hieu(q["den"]), q["den"], q)

    def test_quan_he_dung_loai_va_co_can_cu(self):
        for q in self.quan_he:
            self.assertIn(q["loai"], LOAI_HOP_LE, q)
            self.assertTrue(q.get("can_cu", "").strip(), q)

    def test_ngay_hop_le_va_dung_thu_tu(self):
        for so_hieu, tt in self.van_ban.items():
            ban_hanh = self._ngay(so_hieu, "ngay_ban_hanh")
            hieu_luc = self._ngay(so_hieu, "ngay_hieu_luc")
            if ban_hanh and hieu_luc:
                self.assertLessEqual(ban_hanh, hieu_luc, so_hieu)
            nam = _nam_so_hieu(so_hieu)
            if nam and ban_hanh:
                self.assertEqual(ban_hanh.year, nam, so_hieu)
            if nam and hieu_luc:
                self.assertGreaterEqual(hieu_luc.year, nam, so_hieu)
            if nam and "nam" in tt:
                self.assertEqual(tt["nam"], nam, so_hieu)

    def test_hieu_luc_khong_som_hon_luat_cho_phep(self):
        # Gõ nhầm ngày hiệu lực sớm hơn thật là lỗi nguy hiểm nhất: hệ thống coi
        # văn bản mới đã áp dụng trong khi văn bản cũ vẫn còn hiệu lực.
        for so_hieu in self.van_ban:
            ban_hanh = self._ngay(so_hieu, "ngay_ban_hanh")
            hieu_luc = self._ngay(so_hieu, "ngay_hieu_luc")
            if not (ban_hanh and hieu_luc) or ban_hanh < AP_DUNG_TU or so_hieu in HIEU_LUC_SOM:
                continue
            self.assertGreaterEqual((hieu_luc - ban_hanh).days, SO_NGAY_TOI_THIEU, (
                f"{so_hieu}: ký {ban_hanh}, hiệu lực {hieu_luc}. Kiểm lại ngày; nếu văn bản "
                "đúng là có hiệu lực sớm thì thêm vào HIEU_LUC_SOM kèm lý do."))

    def test_ngoai_le_hieu_luc_som_van_con_trong_so(self):
        # Ngoại lệ thừa che mất lỗi gõ sau này của chính văn bản đó.
        for so_hieu in HIEU_LUC_SOM:
            self.assertIn(so_hieu, self.van_ban, so_hieu)

    def test_moi_cap_mot_quan_he_mot_chieu(self):
        cap = defaultdict(list)
        for q in self.quan_he:
            self.assertNotEqual(q["tu"], q["den"], q)
            cap[(q["tu"], q["den"])].append(q["loai"])
        for (tu, den), cac_loai in cap.items():
            self.assertEqual(len(cac_loai), 1, (tu, den, cac_loai))
            self.assertNotIn((den, tu), cap, (tu, den))

    def test_moi_van_ban_bi_thay_tron_nhieu_nhat_mot_lan(self):
        # Hai văn bản cùng "thay thế toàn bộ" một văn bản gần như chắc là một
        # trong hai quan hệ phải là bãi bỏ một phần.
        bi_thay = defaultdict(list)
        for q in self.quan_he:
            if q["loai"] == "thay_the":
                bi_thay[q["den"]].append(q["tu"])
        for den, cac_tu in bi_thay.items():
            self.assertEqual(len(cac_tu), 1, (den, cac_tu))

    def test_khong_co_chu_trinh_thay_the(self):
        ke = defaultdict(list)
        for q in self.quan_he:
            if q["loai"] == "thay_the":
                ke[q["tu"]].append(q["den"])
        trang_thai = {}  # 1: đang duyệt, 2: xong

        def duyet(nut, duong):
            trang_thai[nut] = 1
            for ke_tiep in ke[nut]:
                self.assertNotEqual(trang_thai.get(ke_tiep), 1, duong + [nut, ke_tiep])
                if ke_tiep not in trang_thai:
                    duyet(ke_tiep, duong + [nut])
            trang_thai[nut] = 2

        for nut in list(ke):
            if nut not in trang_thai:
                duyet(nut, [])

    def test_van_ban_moi_khong_ra_truoc_van_ban_cu(self):
        # Chỉ xét quan hệ đè lên văn bản khác; hướng dẫn / kèm theo có thể ban
        # hành cùng ngày với văn bản gốc.
        for q in self.quan_he:
            if q["loai"] not in ("thay_the", "bai_bo_mot_phan", "sua_doi"):
                continue
            moi, cu = self._ngay(q["tu"], "ngay_ban_hanh"), self._ngay(q["den"], "ngay_ban_hanh")
            if moi and cu:
                self.assertGreaterEqual(moi, cu, q)
            else:
                nam_moi, nam_cu = _nam_so_hieu(q["tu"]), _nam_so_hieu(q["den"])
                if nam_moi and nam_cu:
                    self.assertGreaterEqual(nam_moi, nam_cu, q)
            moi_hl, cu_hl = self._ngay(q["tu"], "ngay_hieu_luc"), self._ngay(q["den"], "ngay_hieu_luc")
            if moi_hl and cu_hl:
                self.assertGreater(moi_hl, cu_hl, q)

    def test_quan_he_da_loai_bo_khong_con_trong_so(self):
        con_lai = {(q["tu"], q["loai"], q["den"]) for q in self.quan_he}
        for l in self.loai_bo:
            self.assertNotIn((l["tu"], l["loai"], l["den"]), con_lai, l)


if __name__ == "__main__":
    unittest.main()
