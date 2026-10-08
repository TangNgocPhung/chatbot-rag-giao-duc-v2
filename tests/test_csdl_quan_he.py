"""Lưu đồ thị quan hệ văn bản vào SQLite và nạp lại."""

import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest import mock

import csdl_quan_he
import quan_he_van_ban as qh
from tests.test_quan_he_van_ban import kho_mau


class CsdlQuanHeTests(unittest.TestCase):
    HOM_NAY = date(2026, 9, 30)

    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.thu_muc.name, "quan_he.db")
        # tu_csdl() đọc tên gọi Luật từ sổ tay: không để sổ tay thật lọt vào test.
        self.vo_so_tay = mock.patch.object(
            qh, "DUONG_DAN_SO_TAY", os.path.join(self.thu_muc.name, "khong_co.json")
        )
        self.vo_so_tay.start()
        self.so, _ = kho_mau()

    def tearDown(self):
        self.vo_so_tay.stop()
        self.thu_muc.cleanup()

    def truy_van(self, cau: str, *tham_so):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(cau, tham_so).fetchall()
        finally:
            conn.close()

    def test_ghi_du_bang_va_khoa_ngoai_hop_le(self):
        self.so.luu(self.db)
        self.assertEqual(self.truy_van("PRAGMA foreign_key_check"), [])
        self.assertEqual(
            self.truy_van("SELECT COUNT(*) FROM quan_he")[0][0], len(self.so.quan_he)
        )
        self.assertEqual(self.truy_van("SELECT COUNT(*) FROM loai_quan_he")[0][0], 5)
        # Cạnh đọc từ nội dung và tệp nằm trong kho.
        self.assertEqual(
            self.truy_van("SELECT nguon FROM quan_he WHERE tu=? AND loai='thay_the' AND den=?",
                          "7/2026/TT-BGDĐT", "29/2023/TT-BGDĐT"),
            [("tu_dong",)],
        )
        self.assertEqual(
            self.truy_van("SELECT so_hieu FROM tep WHERE ten_file='cu.pdf'"),
            [("29/2023/TT-BGDĐT",)],
        )
        # Cạnh sổ tay giữa hai văn bản không có trong kho: vẫn có nút, trong_kho = 0.
        self.assertEqual(
            self.truy_van("SELECT nguon FROM quan_he WHERE tu='279/2026/NĐ-CP'"), [("so_tay",)]
        )
        self.assertEqual(
            self.truy_van("SELECT trong_kho, loai_van_ban FROM van_ban WHERE so_hieu='37/2025/NĐ-CP'"),
            [(0, "Nghị định")],
        )
        # Phụ lục tách tệp là nút riêng nối vào văn bản chính.
        self.assertEqual(
            self.truy_van("SELECT den FROM quan_he WHERE tu='tep:PHỤ LỤC TT 44.docx' AND loai='kem_theo'"),
            [("44/2026/TT-BGDĐT",)],
        )

    def test_view_de_doc_ghep_nhan(self):
        self.so.luu(self.db)
        dong = self.truy_van(
            "SELECT van_ban, quan_he, van_ban_kia FROM quan_he_de_doc WHERE tu=? AND den=?",
            "7/2026/TT-BGDĐT", "29/2023/TT-BGDĐT",
        )
        self.assertEqual(dong, [("Thông tư 7/2026/TT-BGDĐT", "Thay thế", "Thông tư 29/2023/TT-BGDĐT")])

    def test_ghi_lai_thay_ca_do_thi(self):
        self.so.luu(self.db)
        so_moi = qh.SoQuanHe(self.so.ho_so, self.so.tinh_trang, {
            "loai_bo": [{"tu": "7/2026/TT-BGDĐT", "loai": "thay_the", "den": "29/2023/TT-BGDĐT"}],
        })
        so_moi.luu(self.db)
        self.assertEqual(
            self.truy_van("SELECT COUNT(*) FROM quan_he")[0][0], len(so_moi.quan_he)
        )
        self.assertEqual(
            self.truy_van("SELECT COUNT(*) FROM quan_he WHERE tu='7/2026/TT-BGDĐT' AND den='29/2023/TT-BGDĐT'")[0][0],
            0,
        )
        self.assertEqual(self.truy_van("SELECT COUNT(*) FROM loai_bo")[0][0], 1)
        # Cạnh sổ tay của lần trước không còn (sổ tay mới không có nó).
        self.assertEqual(self.truy_van("SELECT COUNT(*) FROM quan_he WHERE nguon='so_tay'")[0][0], 0)

    def test_nap_lai_tu_csdl_giu_nguyen_do_thi(self):
        self.so.luu(self.db)
        nap = qh.SoQuanHe.tu_csdl(self.db)
        canh = lambda so: {(q.tu, q.loai, q.den, q.nguon) for q in so.quan_he}
        self.assertEqual(canh(nap), canh(self.so))
        self.assertEqual(nap.nut_cua_tep["cu.pdf"], "29/2023/TT-BGDĐT")
        self.assertEqual(nap.nut_cua_tep["PHỤ LỤC TT 44.docx"], "tep:PHỤ LỤC TT 44.docx")
        for nut in ("29/2023/TT-BGDĐT", "52/2020/TT-BGDĐT", "21/2025/TT-BGDĐT", "7/2026/TT-BGDĐT"):
            self.assertEqual(
                nap.tinh_trang_nut(nut, self.HOM_NAY)["code"],
                self.so.tinh_trang_nut(nut, self.HOM_NAY)["code"],
                nut,
            )
        self.assertTrue(nap.het_hieu_luc("cu.pdf", self.HOM_NAY))

    def test_chua_co_csdl_thi_do_thi_rong_va_khong_tao_tep(self):
        nap = qh.SoQuanHe.tu_csdl(self.db)
        self.assertEqual(nap.quan_he, [])
        self.assertFalse(os.path.exists(self.db))

    def test_duong_dan_mac_dinh_da_cach_ly(self):
        # conftest chuyển CSDL sang thư mục tạm; test nào gọi luu() không đối số
        # cũng không chạm tệp thật của dự án.
        thu_muc_du_an = os.path.dirname(os.path.abspath(qh.__file__))
        self.assertNotEqual(os.path.dirname(csdl_quan_he.DUONG_DAN_CSDL), thu_muc_du_an)


if __name__ == "__main__":
    unittest.main()
