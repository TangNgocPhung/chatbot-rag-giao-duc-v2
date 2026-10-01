"""Bộ câu hỏi và trình chạy benchmark_van_ban.py: tệp hợp lệ, logic chấm, và
mọi câu "tinh_toan" (không phụ thuộc kho) đạt trên đường trả lời thật."""

import contextlib
import json
import unittest
from collections import defaultdict
from unittest import mock


import benchmark_van_ban as bvb


def _bo():
    with open(bvb.DUONG_DAN_BO, encoding="utf-8") as tep:
        return json.load(tep)


class BoCauHoiTests(unittest.TestCase):
    def test_tep_hop_le(self):
        self.assertEqual(bvb.kiem_tra_bo(_bo()), [])

    def test_moi_use_case_co_ca_duong_tinh_va_doi_chung(self):
        loai = defaultdict(set)
        for muc in _bo()["cau_hoi"]:
            loai[muc["use_case"]].add(muc["loai"])
        for use_case in bvb.CAC_USE_CASE:
            self.assertEqual(loai[use_case], {"duong_tinh", "doi_chung"}, use_case)

    def test_cau_gia_dinh_chua_tinh_la_da_doi_chieu(self):
        for muc in _bo()["cau_hoi"]:
            self.assertEqual(muc["da_doi_chieu"], muc["do_tin_cay"] != "gia_dinh", muc["cau_hoi"])

    def test_moi_nhom_co_cau_o_ca_hai_tap(self):
        tap = defaultdict(list)
        for muc in _bo()["cau_hoi"]:
            tap[muc["nhom"]].append(muc["tap"])
        for nhom, cac_tap in tap.items():
            if len(cac_tap) >= 2:
                self.assertEqual(set(cac_tap), {"dev", "test"}, nhom)

    def test_bat_loi_tep_hong(self):
        loi = bvb.kiem_tra_bo({"cau_hoi": [
            {"cau_hoi": "a", "use_case": "x", "loai": "duong_tinh", "do_tin_cay": "tinh_toan",
             "tap": "dev", "da_doi_chieu": True, "kiem_tra": [{"loai": "la", "gia_tri": 1}]},
        ]})
        self.assertTrue(any("use_case" in l for l in loi))
        self.assertTrue(any("loại kiểm tra lạ" in l for l in loi))


class ChamTests(unittest.TestCase):
    def _cham(self, kiem_tra, **qs):
        return bvb.cham({"kiem_tra": kiem_tra}, bvb.QuanSat(**qs))

    def test_cac_loai_kiem_tra(self):
        qs = dict(
            tra_loi="Hạn 16/10/2026", ngu_canh="THỦ TỤC: ...", cong_cu="tinh_han",
            canh_bao=["phan_cap"], goi_y=["Hỏi (Tiểu học)?"],
            nguon=[{"name": "Thông tư tiêu chuẩn người dạy nghề.pdf", "validity": {"code": "het_theo_goc"}}],
        )
        ket_qua = self._cham([
            {"loai": "cong_cu", "gia_tri": "tinh_han"},
            {"loai": "khong_cong_cu", "gia_tri": "so_sanh_phien_ban"},
            {"loai": "tra_loi_chua", "gia_tri": "16/10/2026"},
            {"loai": "ngu_canh_chua", "gia_tri": "THỦ TỤC:"},
            {"loai": "ngu_canh_khong_chua", "gia_tri": "PHÂN CẤP"},
            {"loai": "ngu_canh_chua_mot_trong", "gia_tri": ["x", "THỦ TỤC"]},
            {"loai": "canh_bao", "gia_tri": "phan_cap"},
            {"loai": "khong_canh_bao", "gia_tri": "chuyen_tiep"},
            {"loai": "nguon_chua", "gia_tri": "người dạy nghề"},
            {"loai": "nhan_nguon_khac", "gia_tri": {"nguon": "người dạy nghề", "ma": "con_hieu_luc"}},
            {"loai": "goi_y_chua", "gia_tri": "("},
        ], **qs)
        self.assertEqual([k["ket_qua"] for k in ket_qua], ["dat"] * 11)
        self.assertEqual(bvb.ket_luan(ket_qua), "dat")

    def test_tra_loi_duong_rag_chi_cham_khi_co_llm(self):
        kt = [{"loai": "tra_loi_chua", "gia_tri": "x"}]
        self.assertEqual(self._cham(kt)[0]["ket_qua"], "bo_qua")
        self.assertEqual(bvb.ket_luan(self._cham(kt)), "bo_qua")
        self.assertEqual(self._cham(kt, co_llm=True)[0]["ket_qua"], "truot")

    def test_nhan_nguon_khi_khong_truy_hoi_duoc_la_truot(self):
        ket_qua = self._cham([{"loai": "nhan_nguon_khac", "gia_tri": {"nguon": "abc", "ma": "con_hieu_luc"}}])
        self.assertEqual(ket_qua[0]["ket_qua"], "truot")
        self.assertIn("không truy hồi được", ket_qua[0]["ghi_chu"])

    def test_loi_ha_tang_la_truot(self):
        ket_qua = self._cham([{"loai": "khong_canh_bao", "gia_tri": "x"}], loi="RuntimeError: chưa sẵn sàng")
        self.assertEqual(ket_qua[0]["ket_qua"], "truot")

    def test_tong_ket_tach_cau_chua_doi_chieu(self):
        bang = bvb.tong_ket([
            {"use_case": "thu_tuc", "loai": "duong_tinh", "da_doi_chieu": True, "ket_luan": "dat"},
            {"use_case": "thu_tuc", "loai": "duong_tinh", "da_doi_chieu": False, "ket_luan": "truot"},
            {"use_case": "thu_tuc", "loai": "doi_chung", "da_doi_chieu": True, "ket_luan": "bo_qua"},
        ])
        self.assertEqual(bang["thu_tuc"]["duong_tinh"], [1, 2])
        self.assertEqual(bang["thu_tuc"]["duong_tinh:chua_doi_chieu"], [0, 1])
        self.assertNotIn("doi_chung", bang["thu_tuc"])
        self.assertEqual(bang["TONG"]["duong_tinh"], [1, 2])


class CauTinhToanTests(unittest.TestCase):
    """Câu "tinh_toan" không phụ thuộc kho: chạy qua đường trả lời thật (dịch vụ
    dựng tay, truy hồi giả) thì phải đạt. Sai ngày hạn mong đợi, hay một lớp xử
    lý kích hoạt nhầm ở câu đối chứng, đều làm test này hỏng."""

    def test_moi_cau_tinh_toan_dat(self):
        from tests.test_luong_tra_loi_van_ban import CHUNK, dich_vu

        service = dich_vu()
        # Truy hồi giả trả về đoạn có cả điều khoản chuyển tiếp, viện dẫn và
        # văn bản hai cấp - đủ để một lớp kích hoạt nhầm thì lộ ra.
        tai_lieu = [CHUNK["tt08.pdf"][1], CHUNK["cv.pdf"][0]]
        with contextlib.ExitStack() as ngan:
            for ten, gia_tri in (
                ("hoi_kho_duoc", True), ("_retrieve", tai_lieu), ("_chain_tra_loi", None),
            ):
                ngan.enter_context(mock.patch.object(type(service), ten, return_value=gia_tri))
            ngan.enter_context(mock.patch.object(type(service), "_luot_sinh_tep", contextlib.nullcontext))
            ngan.enter_context(mock.patch("kiem_tra_tra_loi.ly_do_bo_qua", return_value=None))
            cac_muc = [m for m in _bo()["cau_hoi"] if m["do_tin_cay"] == "tinh_toan"]
            self.assertGreaterEqual(len(cac_muc), 10)
            for muc in cac_muc:
                ket_qua = bvb.cham(muc, bvb.quan_sat(service, muc["cau_hoi"]))
                self.assertEqual(
                    bvb.ket_luan(ket_qua), "dat",
                    f"{muc['cau_hoi']}: {[k for k in ket_qua if k['ket_qua'] != 'dat']}",
                )

    def test_quan_sat_bat_duoc_prompt_va_su_kien(self):
        from tests.test_luong_tra_loi_van_ban import CHUNK, dich_vu

        service = dich_vu()
        with contextlib.ExitStack() as ngan:
            for ten, gia_tri in (
                ("hoi_kho_duoc", True), ("_retrieve", [CHUNK["tt08.pdf"][1]]), ("_chain_tra_loi", None),
            ):
                ngan.enter_context(mock.patch.object(type(service), ten, return_value=gia_tri))
            ngan.enter_context(mock.patch.object(type(service), "_luot_sinh_tep", contextlib.nullcontext))
            ngan.enter_context(mock.patch("kiem_tra_tra_loi.ly_do_bo_qua", return_value=None))
            qs = bvb.quan_sat(service, "Sinh viên được đăng ký tối đa bao nhiêu tín chỉ?")
        self.assertEqual(qs.loi, "")
        self.assertIn("QUY ĐỊNH CHUYỂN TIẾP", qs.ngu_canh)
        self.assertIn("chuyen_tiep", qs.canh_bao)
        self.assertEqual(qs.nguon[0]["name"], "tt08.pdf")
        self.assertIsNone(qs.cong_cu)


if __name__ == "__main__":
    unittest.main()
