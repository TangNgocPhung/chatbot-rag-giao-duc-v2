"""So sánh hai phiên bản văn bản: ghép Điều, khác biệt khoản và số liệu."""

import unittest
from unittest import mock

from langchain_core.documents import Document

import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import so_sanh_phien_ban as ss
import van_ban_meta as vm


def chunk(tep: str, tieu_de: str | None, than: str, trang: int = 1) -> Document:
    metadata = {"source_file": tep, "so_trang": trang}
    if tieu_de:
        metadata["article"] = tieu_de
    return Document(page_content=(tieu_de + "\n" if tieu_de else "") + than, metadata=metadata)


def ban_cu(tep="cu.pdf"):
    return [
        chunk(tep, None, "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nCăn cứ Luật Giáo dục;"),
        chunk(tep, "Điều 1. Phạm vi điều chỉnh", "Quy chế này quy định về đào tạo trình độ đại học."),
        chunk(tep, "Điều 7. Đăng ký học phần",
              "1. Sinh viên được đăng ký tối đa 25 tín chỉ mỗi học kỳ.\n2. Học kỳ phụ tối đa 12 tín chỉ."),
        chunk(tep, "Điều 9. Xét tốt nghiệp", "Sinh viên được xét tốt nghiệp khi tích lũy đủ số tín chỉ."),
        chunk(tep, "Điều 10. Học phí", "Học phí đóng theo từng học kỳ tại phòng tài vụ."),
    ]


def ban_moi(tep="moi.pdf"):
    return [
        chunk(tep, "Điều 1. Phạm vi điều chỉnh", "Quy chế này quy định về đào tạo trình độ đại học."),
        chunk(tep, "Điều 8. Đăng ký học phần",
              "1. Sinh viên được đăng ký tối đa 30 tín chỉ mỗi học kỳ.\n2. Học kỳ phụ tối đa 12 tín chỉ.\n"
              "3. Sinh viên năm cuối được đăng ký vượt mức nếu đủ điều kiện."),
        chunk(tep, "Điều 9. Xét tốt nghiệp", "Sinh viên được xét tốt nghiệp khi tích lũy đủ số tín chỉ."),
        chunk(tep, "Điều 11. Học bạ số", "Học bạ số được ký bằng chữ ký điện tử."),
    ]


class YDinhTests(unittest.TestCase):
    def test_nhan_ra_cau_hoi_so_sanh(self):
        for cau in (
            "Thông tư 15/2026 khác gì Thông tư 28/2020?",
            "Thông tư 15/2026 có điểm mới gì?",
            "Điều lệ trường tiểu học mới có gì khác điều lệ cũ",
            "So sánh quy chế đào tạo mới và cũ",
        ):
            self.assertTrue(ss.la_cau_hoi_so_sanh(cau), cau)
        for cau in ("Sinh viên đăng ký tối đa bao nhiêu tín chỉ?", "Thông tư 15/2026 quy định gì?"):
            self.assertFalse(ss.la_cau_hoi_so_sanh(cau), cau)
        self.assertEqual(ss.muc_y_dinh("Thông tư 15/2026 có điểm mới gì?"), "moi")
        self.assertEqual(ss.muc_y_dinh("Thông tư 15/2026 khác gì Thông tư 28/2020?"), "so_sanh")

    def test_khong_so_hieu_phai_noi_ro_hai_phien_ban(self):
        self.assertTrue(ss.noi_hai_phien_ban("Điều lệ mới có gì khác điều lệ cũ"))
        self.assertFalse(ss.noi_hai_phien_ban("So sánh học phí công lập và tư thục"))


class TachDieuTests(unittest.TestCase):
    def test_gom_chunk_lien_nhau_va_bo_phan_mo_dau(self):
        cac_dieu = ss.tach_dieu(ban_cu())
        self.assertEqual([d.tieu_de for d in cac_dieu], [
            "Điều 1. Phạm vi điều chỉnh", "Điều 7. Đăng ký học phần", "Điều 9. Xét tốt nghiệp", "Điều 10. Học phí",
        ])

    def test_dieu_dai_nhieu_chunk_va_chunk_lap(self):
        cac_dieu = ss.tach_dieu([
            chunk("a.pdf", "Điều 2. Dài", "Phần đầu.", 1),
            chunk("a.pdf", "Điều 2. Dài", "Phần sau.", 2),
            chunk("a.pdf", "Điều 2. Dài", "Phần sau.", 2),
        ])
        self.assertEqual(len(cac_dieu), 1)
        self.assertEqual(cac_dieu[0].noi_dung.count("Phần sau."), 1)
        self.assertEqual(cac_dieu[0].so_trang, 1)

    def test_so_dieu_trung_trong_cung_tep_van_tach_rieng(self):
        # Thông tư (Điều 1-2) và Quy chế kèm theo (Điều 1-2) chung một tệp.
        cac_dieu = ss.tach_dieu([
            chunk("a.pdf", "Điều 1. Ban hành kèm theo Thông tư này Quy chế", "x"),
            chunk("a.pdf", "Điều 2. Hiệu lực thi hành", "y"),
            chunk("a.pdf", "Điều 1. Phạm vi điều chỉnh", "z"),
            chunk("a.pdf", "Điều 2. Đối tượng áp dụng", "w"),
        ])
        self.assertEqual(len(cac_dieu), 4)


class GhepDieuTests(unittest.TestCase):
    def test_ghep_theo_noi_dung_du_so_dieu_doi(self):
        cap = ss.ghep_dieu(ss.tach_dieu(ban_cu()), ss.tach_dieu(ban_moi()))
        ten = [(a.tieu_de if a else None, b.tieu_de if b else None) for a, b, _ in cap]
        self.assertIn(("Điều 7. Đăng ký học phần", "Điều 8. Đăng ký học phần"), ten)
        self.assertIn((None, "Điều 11. Học bạ số"), ten)
        self.assertIn(("Điều 10. Học phí", None), ten)
        # Điều bị bỏ xếp cuối.
        self.assertEqual(ten[-1], ("Điều 10. Học phí", None))


class SoLieuTests(unittest.TestCase):
    def test_cum_so_lieu_bo_so_thu_tu_ngay_va_so_hieu(self):
        self.assertEqual(
            [c for c, _ in ss.cum_so_lieu(
                "tối đa 25 tín chỉ theo Điều 5, khoản 2, ngày 01/9/2021, lớp 10, Thông tư 22/2021, "
                "đạt 12,5% và 3 năm"
            )],
            ["25 tín chỉ", "12,5%", "3 năm"],
        )

    def test_ghep_so_cung_don_vi(self):
        self.assertEqual(
            ss.thay_doi_so_lieu("tối đa 25 tín chỉ, học 4 năm", "tối đa 30 tín chỉ, học 4 năm, phí 10%"),
            ["25 tín chỉ → 30 tín chỉ", "thêm 10%"],
        )
        self.assertEqual(ss.thay_doi_so_lieu("25 tín chỉ", "25 tín chỉ"), [])

    def test_khoan_chen_dau_khong_lam_lech_ghep(self):
        cu = "1. Đăng ký tối đa 25 tín chỉ mỗi kỳ.\n2. Học kỳ phụ tối đa 12 tín chỉ."
        moi = "1. Sinh viên phải có cố vấn học tập.\n2. Đăng ký tối đa 25 tín chỉ mỗi kỳ.\n3. Học kỳ phụ tối đa 12 tín chỉ."
        ket_qua = ss.so_sanh_khoan(cu, moi)
        self.assertEqual(ket_qua.them, ["1. Sinh viên phải có cố vấn học tập."])
        self.assertEqual(ket_qua.bo, [])
        self.assertEqual(ket_qua.so_lieu, [])


class SoSanhTests(unittest.TestCase):
    def test_ket_qua_va_dinh_dang(self):
        ket_qua = ss.so_sanh(ss.tach_dieu(ban_cu()), ss.tach_dieu(ban_moi()))
        self.assertEqual(len(ket_qua.giu_nguyen), 2)
        self.assertEqual([d.tieu_de for d in ket_qua.moi], ["Điều 11. Học bạ số"])
        self.assertEqual([d.tieu_de for d in ket_qua.bo], ["Điều 10. Học phí"])
        a, b, _, khoan = ket_qua.sua[0]
        self.assertEqual(khoan.so_lieu, ["25 tín chỉ → 30 tín chỉ"])
        self.assertEqual(len(khoan.them), 1)
        van_ban = ss.dinh_dang("Thông tư 15/2026", "Thông tư 28/2020", ket_qua, "Mở đầu.")
        self.assertIn("**1** Điều có thay đổi, **1** Điều mới, **1** Điều không còn", van_ban)
        self.assertIn("| Điều 8. Đăng ký học phần | Điều 7. Đăng ký học phần | số liệu: 25 tín chỉ → 30 tín chỉ; thêm 1 khoản |", van_ban)
        self.assertIn("không phải đánh giá pháp lý", van_ban)


def dich_vu(co_ban_cu: bool = True):
    from rag_service import RAGService

    dau = "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: {} Hà Nội, ngày {}\nTHÔNG TƯ\nCăn cứ Luật;\nĐiều 1. Phạm vi\n{}"
    noi_dung = {
        "moi.pdf": dau.format(
            "15/2026/TT-BGDĐT", "24 tháng 3 năm 2026",
            "Thông tư này thay thế Thông tư số 28/2020/TT-BGDĐT.\n"
            "Thông tư này có hiệu lực thi hành từ ngày 10 tháng 5 năm 2026.",
        ),
        "cu.pdf": dau.format("28/2020/TT-BGDĐT", "4 tháng 9 năm 2020", "Điều lệ trường."),
    }
    if not co_ban_cu:
        noi_dung.pop("cu.pdf")
    ho_so = vm.xay_dung_ho_so(noi_dung)
    service = RAGService.__new__(RAGService)
    service.so_quan_he = qh.SoQuanHe(ho_so, hl.xay_dung(noi_dung, ho_so), so_tay={})
    service._doan_theo_tep = {"moi.pdf": ban_moi()}
    if co_ban_cu:
        service._doan_theo_tep["cu.pdf"] = ban_cu()
    return service


class DoThiTests(unittest.TestCase):
    def test_cap_phien_ban(self):
        so = dich_vu().so_quan_he
        self.assertEqual(so.cap_phien_ban("Thông tư 15/2026 có gì mới?"), ("15/2026/TT-BGDĐT", "28/2020/TT-BGDĐT"))
        self.assertEqual(so.cap_phien_ban("Thông tư 28/2020 khác gì bản mới?"), ("15/2026/TT-BGDĐT", "28/2020/TT-BGDĐT"))
        # Nêu hai số hiệu theo thứ tự nào thì văn bản mới hơn vẫn là "mới".
        self.assertEqual(
            so.cap_phien_ban("So sánh Thông tư 28/2020 và Thông tư 15/2026"),
            ("15/2026/TT-BGDĐT", "28/2020/TT-BGDĐT"),
        )
        self.assertIsNone(so.cap_phien_ban("Thông tư 99/2019 khác gì?"))


class TangDichVuTests(unittest.TestCase):
    def test_tra_loi_so_sanh_co_nguon_hai_ben(self):
        van_ban, nguon = dich_vu()._so_sanh_phien_ban("Thông tư 15/2026 khác gì Thông tư 28/2020?")
        self.assertIn("Thông tư 15/2026/TT-BGDĐT thay thế Thông tư 28/2020/TT-BGDĐT từ ngày 10/5/2026.", van_ban)
        self.assertIn("25 tín chỉ → 30 tín chỉ", van_ban)
        self.assertEqual([(n["evidence"], n["name"]) for n in nguon], [(1, "moi.pdf"), (2, "cu.pdf")])

    def test_khong_phai_cau_so_sanh(self):
        self.assertIsNone(dich_vu()._so_sanh_phien_ban("Thông tư 15/2026 quy định gì?"))

    def test_so_sanh_chung_mot_van_ban_khong_phai_hai_phien_ban(self):
        service = dich_vu()
        for cau in (
            "So sánh Điều 5 và Điều 6 của Thông tư 15/2026",
            "Học bạ số theo Thông tư 15/2026 khác gì học bạ giấy?",
        ):
            self.assertIsNone(service._so_sanh_phien_ban(cau), cau)
        # Nói rõ mới/cũ thì vẫn là hỏi hai phiên bản.
        self.assertIsNotNone(service._so_sanh_phien_ban("Thông tư 15/2026 khác gì bản cũ?"))

    def test_kho_thieu_ban_cu_thi_noi_thang(self):
        van_ban, nguon = dich_vu(co_ban_cu=False)._so_sanh_phien_ban("Thông tư 15/2026 có gì mới?")
        self.assertIn("Kho tài liệu không có Thông tư 28/2020/TT-BGDĐT", van_ban)
        self.assertEqual([n["name"] for n in nguon], ["moi.pdf"])

    def test_khong_so_hieu_thi_dua_vao_truy_hoi(self):
        service = dich_vu()
        with mock.patch.object(type(service), "_retrieve", return_value=[ban_moi()[1]], create=True):
            ket_qua = service._so_sanh_phien_ban("Quy chế đào tạo mới có gì khác quy chế cũ?")
        self.assertIn("25 tín chỉ → 30 tín chỉ", ket_qua[0])
        # Có "so sánh" nhưng không nói về hai phiên bản: không truy hồi, không so.
        with mock.patch.object(type(service), "_retrieve", side_effect=AssertionError, create=True):
            self.assertIsNone(service._so_sanh_phien_ban("So sánh học phí công lập và tư thục"))


if __name__ == "__main__":
    unittest.main()
