"""Hết hiệu lực dây chuyền: văn bản hướng dẫn một văn bản đã bị thay."""

import unittest
from datetime import date

import chuyen_tiep as ct
import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import van_ban_meta as vm


def van_ban(so_hieu_dong: str, than: str, ngay: str) -> str:
    return (
        f"CHÍNH PHỦ\nSố: {so_hieu_dong} Hà Nội, {ngay}\nNGHỊ ĐỊNH\n"
        f"Căn cứ Luật Tổ chức Chính phủ;\nĐiều 1. Phạm vi điều chỉnh\n{than}"
    )


CAU_GIU = (
    "Các văn bản quy định chi tiết thi hành Luật Giáo dục số 38/2005/QH11 tiếp tục có "
    "hiệu lực nếu không trái với quy định của Luật này."
)


def kho_mau(co_cau_giu: bool = False, so_tay_them: dict | None = None):
    """
    Luật GDĐH 8/2012 bị Luật 125/2025 thay từ 1/1/2026:
      nd99 (99/2019) quy định chi tiết Luật GDĐH            -> nghi hết theo
      tt12 (12/2021) hướng dẫn Nghị định 99/2019             -> nghi hết, qua chuỗi
      tt20 (20/2020) hướng dẫn 99/2019 nhưng được tt05 sửa năm 2026 -> còn sống
      tt40 (40/2026) ban hành sau ngày đó, "hướng dẫn" 99/2019 -> trích nhầm, bỏ qua
    Luật Giáo dục 38/2005 bị 43/2019 thay:
      nd75 (75/2006) quy định chi tiết Luật Giáo dục 2005   -> nghi hết, trừ khi Luật
                     2019 có câu giữ lại (co_cau_giu)
      nd84 (84/2020) quy định chi tiết Luật Giáo dục 2019   -> Luật còn hiệu lực
    """
    noi_dung = {
        "nd99.pdf": van_ban(
            "99/2019/NĐ-CP",
            "Quy định chi tiết và hướng dẫn thi hành một số điều của Luật Giáo dục đại học",
            "ngày 30 tháng 12 năm 2019",
        ),
        "tt12.pdf": van_ban(
            "12/2021/TT-BGDĐT",
            "Thông tư này hướng dẫn thi hành Nghị định số 99/2019/NĐ-CP.",
            "ngày 5 tháng 4 năm 2021",
        ),
        "tt20.pdf": van_ban(
            "20/2020/TT-BGDĐT",
            "Thông tư này hướng dẫn thi hành Nghị định số 99/2019/NĐ-CP.",
            "ngày 2 tháng 7 năm 2020",
        ),
        "tt05.pdf": van_ban(
            "5/2026/TT-BGDĐT",
            "Sửa đổi, bổ sung một số điều của Thông tư số 20/2020/TT-BGDĐT.\n"
            "Thông tư này có hiệu lực thi hành từ ngày 01 tháng 3 năm 2026.",
            "ngày 10 tháng 1 năm 2026",
        ),
        "tt40.pdf": van_ban(
            "40/2026/TT-BGDĐT",
            "Thông tư này hướng dẫn thi hành Nghị định số 99/2019/NĐ-CP.",
            "ngày 20 tháng 5 năm 2026",
        ),
        "nd75.pdf": van_ban(
            "75/2006/NĐ-CP", "Quy định chi tiết một số điều của Luật Giáo dục", "ngày 2 tháng 8 năm 2006",
        ),
        "nd84.pdf": van_ban(
            "84/2020/NĐ-CP", "Quy định chi tiết một số điều của Luật Giáo dục", "ngày 17 tháng 7 năm 2020",
        ),
    }
    if co_cau_giu:
        noi_dung["luat43.pdf"] = van_ban(
            "43/2019/QH14", "LUẬT GIÁO DỤC\n" + CAU_GIU, "ngày 14 tháng 6 năm 2019",
        )
    ho_so = vm.xay_dung_ho_so(noi_dung)
    tinh_trang = hl.xay_dung(noi_dung, ho_so)
    so_tay = {
        "van_ban": {
            "8/2012/QH13": {"ten_goi": ["Luật Giáo dục đại học"], "ngay_ban_hanh": "2012-06-18"},
            "125/2025/QH15": {"ten_goi": ["Luật Giáo dục đại học"], "nam": 2025, "ngay_hieu_luc": "2026-01-01"},
            "38/2005/QH11": {"ten_goi": ["Luật Giáo dục"], "ngay_ban_hanh": "2005-06-14"},
            "43/2019/QH14": {"ten_goi": ["Luật Giáo dục"], "ngay_ban_hanh": "2019-06-14", "ngay_hieu_luc": "2020-07-01"},
        },
        "quan_he": [
            {"tu": "125/2025/QH15", "loai": "thay_the", "den": "8/2012/QH13"},
            {"tu": "43/2019/QH14", "loai": "thay_the", "den": "38/2005/QH11"},
        ],
    }
    for khoa, gia_tri in (so_tay_them or {}).items():
        if isinstance(gia_tri, dict):
            for so_hieu, muc in gia_tri.items():
                so_tay[khoa].setdefault(so_hieu, {}).update(muc)
        else:
            so_tay.setdefault(khoa, []).extend(gia_tri)
    return qh.SoQuanHe(ho_so, tinh_trang, so_tay), tinh_trang


HOM_NAY = date(2026, 10, 1)


class TrichCauGiuTests(unittest.TestCase):
    def test_nhan_ra_cau_giu_van_ban_quy_dinh_chi_tiet(self):
        self.assertEqual(ct.trich_giu_van_ban_huong_dan("2. " + CAU_GIU), CAU_GIU.rstrip("."))

    def test_cau_tiep_tuc_thong_thuong_khong_tinh(self):
        for cau in (
            "Nhà trường tiếp tục thực hiện theo hướng dẫn của Sở Giáo dục và Đào tạo.",
            "Các văn bản quy định chi tiết thi hành Luật số 38/2005/QH11 hết hiệu lực.",
        ):
            self.assertIsNone(ct.trich_giu_van_ban_huong_dan(cau), cau)


class HetTheoGocTests(unittest.TestCase):
    def setUp(self):
        self.so, self.tinh_trang = kho_mau()

    def test_huong_dan_truc_tiep_luat_da_bi_thay(self):
        ket_qua = self.so.het_theo_goc("99/2019/NĐ-CP", HOM_NAY)
        self.assertEqual(ket_qua["goc"], "8/2012/QH13")
        self.assertEqual(ket_qua["thay_goc"], ["125/2025/QH15"])
        self.assertEqual(ket_qua["tu_ngay"], "2026-01-01")
        self.assertFalse(ket_qua["sap"])
        self.assertEqual(ket_qua["chuoi"], ["8/2012/QH13"])

    def test_lan_qua_chuoi_luat_nghi_dinh_thong_tu(self):
        ket_qua = self.so.het_theo_goc("12/2021/TT-BGDĐT", HOM_NAY)
        self.assertEqual(ket_qua["chuoi"], ["99/2019/NĐ-CP", "8/2012/QH13"])
        self.assertIn("(văn bản này lại hướng dẫn Luật 8/2012/QH13)", self.so.mo_ta_het_theo_goc(ket_qua))

    def test_con_duoc_sua_sau_ngay_do_thi_con_song(self):
        self.assertIsNone(self.so.het_theo_goc("20/2020/TT-BGDĐT", HOM_NAY))

    def test_ban_hanh_sau_ngay_do_la_trich_nham(self):
        self.assertIsNone(self.so.het_theo_goc("40/2026/TT-BGDĐT", HOM_NAY))

    def test_van_ban_duoc_huong_dan_con_hieu_luc(self):
        self.assertIsNone(self.so.het_theo_goc("84/2020/NĐ-CP", HOM_NAY))

    def test_truoc_ngay_luat_moi_co_hieu_luc_la_sap(self):
        ket_qua = self.so.het_theo_goc("99/2019/NĐ-CP", date(2025, 12, 20))
        self.assertTrue(ket_qua["sap"])
        nhan = self.so.nhan_hieu_luc("nd99.pdf", hom_nay=date(2025, 12, 20))
        self.assertEqual(nhan["label"], "Sắp cần kiểm tra hiệu lực")
        self.assertIn("sẽ bị thay bởi Luật 125/2025/QH15 từ 1/1/2026", nhan["note"])

    def test_chi_canh_bao_khong_loc_khoi_truy_hoi(self):
        self.assertFalse(self.so.het_hieu_luc("nd99.pdf", HOM_NAY))
        self.assertEqual(self.so.tinh_trang_nut("99/2019/NĐ-CP", HOM_NAY)["code"], "con_hieu_luc")

    def test_nhan_hieu_luc(self):
        nhan = self.so.nhan_hieu_luc("nd99.pdf", hom_nay=HOM_NAY)
        self.assertEqual(nhan["code"], "het_theo_goc")
        self.assertEqual(nhan["level"], "vua")
        self.assertEqual(nhan["label"], "Cần kiểm tra hiệu lực")
        self.assertIn("đã bị thay bởi Luật 125/2025/QH15 từ 1/1/2026", nhan["note"])
        # Văn bản hướng dẫn Luật còn hiệu lực giữ nhãn cũ.
        self.assertEqual(self.so.nhan_hieu_luc("nd84.pdf", hom_nay=HOM_NAY)["code"], "con_hieu_luc")

    def test_canh_bao_va_ghi_chu_cau_hoi(self):
        canh_bao = self.so.canh_bao([{"name": "tt12.pdf", "evidence": 3}], HOM_NAY)
        self.assertEqual(canh_bao[0]["loai"], "het_theo_goc")
        self.assertTrue(canh_bao[0]["thong_bao"].startswith("Nguồn [3] Thông tư 12/2021/TT-BGDĐT hướng dẫn"))
        ghi_chu, can_keo = self.so.ghi_chu_cau_hoi("Nghị định 99/2019 quy định gì?", HOM_NAY)
        self.assertIn("cần kiểm tra", ghi_chu[0])
        self.assertEqual(can_keo, [])

    def test_xuat_ghi_nghi_van_ma_khong_doi_tinh_trang(self):
        muc = self.so.xuat(HOM_NAY)["van_ban"]["99/2019/NĐ-CP"]
        self.assertEqual(muc["tinh_trang"], "con_hieu_luc")
        self.assertEqual(muc["het_theo_goc"]["goc"], "8/2012/QH13")
        self.assertIsNone(self.so.xuat(HOM_NAY)["van_ban"]["84/2020/NĐ-CP"]["het_theo_goc"])


class NgoaiLeTests(unittest.TestCase):
    def test_luat_cu_khong_co_cau_giu_thi_canh_bao(self):
        so, _ = kho_mau()
        self.assertEqual(so.het_theo_goc("75/2006/NĐ-CP", HOM_NAY)["goc"], "38/2005/QH11")

    def test_luat_moi_cho_giu_van_ban_huong_dan(self):
        so, tinh_trang = kho_mau(co_cau_giu=True)
        self.assertTrue(tinh_trang["luat43.pdf"].giu_van_ban_huong_dan)
        self.assertIn("43/2019/QH14", so.giu_huong_dan)
        self.assertIsNone(so.het_theo_goc("75/2006/NĐ-CP", HOM_NAY))

    def test_so_tay_giu_cau_va_giu_hieu_luc(self):
        so, _ = kho_mau(so_tay_them={"van_ban": {
            "43/2019/QH14": {"giu_van_ban_huong_dan": "Điều 115 khoản 3 (đối chiếu tay)"},
            "99/2019/NĐ-CP": {"giu_hieu_luc": "Đã đối chiếu: vẫn áp dụng"},
        }})
        self.assertIsNone(so.het_theo_goc("75/2006/NĐ-CP", HOM_NAY))
        self.assertIsNone(so.het_theo_goc("99/2019/NĐ-CP", HOM_NAY))
        # Cấp trên được xác nhận còn hiệu lực thì cấp dưới cũng không bị nghi.
        self.assertIsNone(so.het_theo_goc("12/2021/TT-BGDĐT", HOM_NAY))

    def test_chu_trinh_huong_dan_khong_lap_vo_han(self):
        so, _ = kho_mau(so_tay_them={"quan_he": [
            {"tu": "1/2020/TT-BGDĐT", "loai": "huong_dan", "den": "2/2020/TT-BGDĐT"},
            {"tu": "2/2020/TT-BGDĐT", "loai": "huong_dan", "den": "1/2020/TT-BGDĐT"},
        ]})
        self.assertIsNone(so.het_theo_goc("1/2020/TT-BGDĐT", HOM_NAY))


if __name__ == "__main__":
    unittest.main()
