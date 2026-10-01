"""Điều khoản chuyển tiếp: văn bản đã bị thay vẫn là căn cứ cho khóa cũ."""

import unicodedata
import unittest
from datetime import date

from langchain_core.documents import Document

import chuyen_tiep as ct
import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import van_ban_meta as vm


def van_ban(so_hieu_dong: str, than: str, ngay: str = "ngày 18 tháng 3 năm 2021") -> str:
    return (
        f"BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: {so_hieu_dong} Hà Nội, {ngay}\nTHÔNG TƯ\n"
        f"Căn cứ Luật Giáo dục đại học;\nĐiều 1. Phạm vi\n{than}"
    )


class TrichTests(unittest.TestCase):
    def test_khoa_tuyen_sinh_truoc_ngay_hieu_luc_theo_so_hieu(self):
        ket_qua = ct.trich_chuyen_tiep(
            "Điều 2. Hiệu lực thi hành\n1. Thông tư này có hiệu lực thi hành từ ngày 03 tháng 5 "
            "năm 2021 và thay thế Quyết định số 43/2007/QĐ-BGDĐT.\n2. Các khóa tuyển sinh trước "
            "ngày Thông tư này có hiệu lực thi hành tiếp tục thực hiện theo Quy chế ban hành kèm "
            "theo Quyết định số 43/2007/QĐ-BGDĐT.",
            "8/2021/TT-BGDĐT",
        )
        self.assertEqual(len(ket_qua), 1)
        quy_dinh = ket_qua[0]
        self.assertEqual(quy_dinh["ap_dung_theo"], ["43/2007/QĐ-BGDĐT"])
        self.assertTrue(quy_dinh["moc_la_ngay_hieu_luc"])
        self.assertIsNone(quy_dinh["moc"])
        self.assertEqual(quy_dinh["doi_tuong"], "khoa")
        self.assertEqual(
            quy_dinh["dieu_kien"], "Các khóa tuyển sinh trước ngày Thông tư này có hiệu lực thi hành"
        )

    def test_quy_dinh_cu_khong_neu_so_hieu(self):
        # Không nêu văn bản nào: SoQuanHe hiểu là các văn bản mà văn bản này thay.
        ket_qua = ct.trich_chuyen_tiep(
            "3. Đối với các khóa đã tuyển sinh trước ngày Thông tư này có hiệu lực thi hành "
            "thì tiếp tục thực hiện theo quy định hiện hành tại thời điểm tuyển sinh."
        )
        self.assertEqual(ket_qua[0]["ap_dung_theo"], [])
        self.assertTrue(ket_qua[0]["theo_quy_dinh_cu"])
        # Điều kiện bỏ "Đối với ... thì"; trích dẫn giữ nguyên văn.
        self.assertTrue(ket_qua[0]["dieu_kien"].startswith("Các khóa đã tuyển sinh"))
        self.assertFalse(ket_qua[0]["dieu_kien"].endswith("thì"))
        self.assertTrue(ket_qua[0]["trich"].startswith("Đối với"))

    def test_dieu_quy_dinh_chuyen_tiep_va_moc_ngay_cu_the(self):
        ket_qua = ct.trich_chuyen_tiep(
            "Điều 45. Quy định chuyển tiếp\n1. Người học đã trúng tuyển trước ngày 01 tháng 01 "
            "năm 2026 được tiếp tục học theo chương trình đào tạo đã công bố.\nĐiều 46. Hiệu lực"
        )
        self.assertEqual(ket_qua[0]["moc"], "2026-01-01")
        self.assertFalse(ket_qua[0]["moc_la_ngay_hieu_luc"])
        self.assertEqual(ket_qua[0]["doi_tuong"], "khoa")

    def test_ho_so_dang_giai_quyet(self):
        ket_qua = ct.trich_chuyen_tiep(
            "Hồ sơ đề nghị đã nộp trước ngày Nghị định này có hiệu lực tiếp tục được xem xét, "
            "giải quyết theo quy định tại Nghị định số 46/2017/NĐ-CP."
        )
        self.assertEqual(ket_qua[0]["doi_tuong"], "ho_so")
        self.assertEqual(ket_qua[0]["ap_dung_theo"], ["46/2017/NĐ-CP"])

    def test_moc_nam_tro_ve_truoc(self):
        ket_qua = ct.trich_chuyen_tiep(
            "Các khóa tuyển sinh từ năm 2020 trở về trước thực hiện theo Thông tư số 15/2014/TT-BGDĐT."
        )
        # "2020 trở về trước" = khóa nào bắt đầu trước 1/1/2021.
        self.assertEqual(ket_qua[0]["moc"], "2021-01-01")
        self.assertEqual(ket_qua[0]["ap_dung_theo"], ["15/2014/TT-BGDĐT"])

    def test_ocr_chen_khoang_trang(self):
        ket_qua = ct.trich_chuyen_tiep(
            "Cá c khó a tuyể n sinh trướ c ngà y Thông tư nà y có hiệ u lự c tiế p tụ c "
            "thự c hiệ n theo Thông tư số 15/2014/TT-BGDĐT"
        )
        self.assertEqual(ket_qua[0]["ap_dung_theo"], ["15/2014/TT-BGDĐT"])
        self.assertTrue(ket_qua[0]["moc_la_ngay_hieu_luc"])

    def test_than_bai_khong_phai_chuyen_tiep(self):
        for cau in (
            # Có mốc ("đã nhập học") và "tiếp tục" nhưng không ràng vào chuyển tiếp.
            "Học sinh đã nhập học tiếp tục học tập tại trường cho đến hết năm học.",
            # "thực hiện theo" mà không chỉ ra văn bản cũ.
            "Giáo viên thực hiện theo quy định tại Điều 5 Thông tư này.",
            "Các khóa tuyển sinh trước ngày Thông tư này có hiệu lực thực hiện theo Thông tư này.",
            # Có văn bản nhưng không có mốc.
            "Nhà trường tiếp tục thực hiện theo Thông tư số 15/2014/TT-BGDĐT.",
        ):
            self.assertEqual(ct.trich_chuyen_tiep(cau), [], cau)

    def test_khong_lay_chinh_so_hieu_van_ban(self):
        ket_qua = ct.trich_chuyen_tiep(
            "Các khóa tuyển sinh trước ngày Thông tư số 8/2021/TT-BGDĐT có hiệu lực tiếp tục "
            "thực hiện theo quy định cũ.",
            "8/2021/TT-BGDĐT",
        )
        self.assertEqual(ket_qua[0]["ap_dung_theo"], [])
        self.assertTrue(ket_qua[0]["theo_quy_dinh_cu"])

    def test_cau_lap_lai_do_chunk_goi_dau(self):
        cau = (
            "2. Các khóa tuyển sinh trước ngày Thông tư này có hiệu lực tiếp tục thực hiện theo "
            "Thông tư số 15/2014/TT-BGDĐT."
        )
        self.assertEqual(len(ct.trich_chuyen_tiep(cau + "\n" + cau)), 1)


class DauHieuCauHoiTests(unittest.TestCase):
    def test_nhan_ra_nam_khoa(self):
        for cau, nam in (
            ("Sinh viên khóa tuyển sinh 2019 được đăng ký tối đa bao nhiêu tín chỉ?", 2019),
            ("Tôi nhập học năm 2020 thì xét tốt nghiệp thế nào?", 2020),
            ("K2019 học bao nhiêu tín chỉ", 2019),
            ("trúng tuyển tháng 9/2018 thì sao", 2018),
            ("Sinh viên nhập học trước năm 2021", 2020),
        ):
            dau_hieu = ct.dau_hieu_trong_cau_hoi(cau)
            self.assertTrue(dau_hieu.co, cau)
            self.assertEqual(dau_hieu.nam, nam, cau)

    def test_khoa_khong_ro_nam(self):
        for cau in ("Sinh viên khóa cũ đăng ký học phần thế nào?", "Lịch học cao học khóa 35"):
            dau_hieu = ct.dau_hieu_trong_cau_hoi(cau)
            self.assertTrue(dau_hieu.co, cau)
            self.assertIsNone(dau_hieu.nam, cau)

    def test_khong_phai_dau_hieu_khoa(self):
        for cau in (
            "Khoa CNTT có bao nhiêu giảng viên năm 2020?",
            "Thông tư 08/2021 quy định gì?",
            "Sinh viên được đăng ký tối đa bao nhiêu tín chỉ?",
            "Học sinh lớp 10 năm học 2024-2025 học những môn nào?",
        ):
            self.assertFalse(ct.dau_hieu_trong_cau_hoi(cau).co, cau)

    def test_so_voi_moc(self):
        self.assertEqual(ct.so_voi_moc("2021-05-03", 2019), "khop")
        self.assertEqual(ct.so_voi_moc("2021-05-03", 2023), "khong")
        # Cùng năm mốc: tuyển sinh tháng 9/2021 là SAU mốc 3/5 - không đoán.
        self.assertEqual(ct.so_voi_moc("2021-05-03", 2021), "co_the")
        self.assertEqual(ct.so_voi_moc("2021-01-01", 2021), "khong")
        self.assertEqual(ct.so_voi_moc(None, 2019), "co_the")
        self.assertEqual(ct.so_voi_moc("2021-05-03", None), "co_the")


class NenCoBanDoTests(unittest.TestCase):
    def test_vi_tri_tro_ve_chuoi_goc_dang_nfc(self):
        # Lỗi cũ: vị trí trỏ vào chuỗi đã tách dấu nên câu nhiều dấu bị cắt
        # quá cả số hiệu, và chú thích sửa đổi tại chỗ bị bỏ sót.
        cau = unicodedata.normalize(
            "NFC",
            "Đoạn văn dài có rất nhiều dấu tiếng Việt ở phía trước, được sửa đổi, bổ sung "
            "theo quy định tại Thông tư số 45/2026/TT-BGDĐT",
        )
        self.assertEqual(hl.van_ban_sua_doan(cau), ["45/2026/TT-BGDĐT"])
        chuoi, ban_do = hl.nen_co_ban_do("Điều ạ")
        self.assertEqual(chuoi, "dieua")
        self.assertEqual(ban_do, [0, 1, 2, 3, 5])


def kho_mau():
    """8/2021 thay QĐ 43/2007 từ 3/5/2021, giữ QĐ 43/2007 cho khóa tuyển sinh
    trước ngày đó; 15/2026 thay 28/2020 nhưng không có câu chuyển tiếp."""
    noi_dung = {
        "tt08.pdf": van_ban(
            "08/2021/TT-BGDĐT",
            "Quy chế đào tạo trình độ đại học. Sinh viên đăng ký tối đa 25 tín chỉ mỗi học kỳ.\n"
            "Điều 2. Hiệu lực thi hành\n1. Thông tư này có hiệu lực thi hành từ ngày 03 tháng 5 năm "
            "2021 và thay thế Quyết định số 43/2007/QĐ-BGDĐT.\n2. Các khóa tuyển sinh trước ngày "
            "Thông tư này có hiệu lực thi hành tiếp tục thực hiện theo quy định cũ.",
        ),
        "qd43.pdf": van_ban(
            "43/2007/QĐ-BGDĐT",
            "Quy chế đào tạo đại học theo hệ thống tín chỉ. Sinh viên đăng ký tối đa 30 tín chỉ.",
            "ngày 15 tháng 8 năm 2007",
        ),
        "tt15.pdf": van_ban(
            "15/2026/TT-BGDĐT", "Điều lệ trường tiểu học. Thông tư này thay thế Thông tư số 28/2020/TT-BGDĐT.",
            "ngày 24 tháng 3 năm 2026",
        ),
        "tt28.pdf": van_ban("28/2020/TT-BGDĐT", "Điều lệ trường tiểu học cũ.", "ngày 4 tháng 9 năm 2020"),
        # Câu có dạng chuyển tiếp nhưng văn bản được nhắc vẫn còn hiệu lực.
        "tt30.pdf": van_ban(
            "30/2026/TT-BGDĐT",
            "Học bạ số. Các trường đã triển khai trước ngày Thông tư này có hiệu lực tiếp tục "
            "thực hiện theo Thông tư số 22/2021/TT-BGDĐT.",
            "ngày 14 tháng 4 năm 2026",
        ),
        "tt22.pdf": van_ban("22/2021/TT-BGDĐT", "Đánh giá học sinh trung học.", "ngày 20 tháng 7 năm 2021"),
        "du_thao.docx": (
            "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: /2026/TT-BGDĐT Hà Nội, ngày tháng năm 2026\nTHÔNG TƯ\n"
            "Căn cứ ...\nĐiều 1. Thông tư này thay thế Thông tư số 28/2020/TT-BGDĐT. Các khóa "
            "tuyển sinh trước ngày Thông tư này có hiệu lực tiếp tục thực hiện theo quy định cũ."
        ),
    }
    ho_so = vm.xay_dung_ho_so(noi_dung)
    tinh_trang = hl.xay_dung(noi_dung, ho_so)
    return qh.SoQuanHe(ho_so, tinh_trang, so_tay={}), noi_dung, ho_so, tinh_trang


HOI_KHOA_CU = "Sinh viên khóa tuyển sinh 2019 được đăng ký tối đa bao nhiêu tín chỉ?"
HOI_KHOA_MOI = "Sinh viên khóa tuyển sinh 2023 được đăng ký tối đa bao nhiêu tín chỉ?"
HOI_CHUNG = "Sinh viên được đăng ký tối đa bao nhiêu tín chỉ?"


class DoThiChuyenTiepTests(unittest.TestCase):
    HOM_NAY = date(2026, 10, 1)

    def setUp(self):
        self.so, self.noi_dung, self.ho_so, self.tinh_trang = kho_mau()

    def test_luu_trong_tinh_trang_thoi_gian(self):
        self.assertEqual(len(self.tinh_trang["tt08.pdf"].chuyen_tiep), 1)
        self.assertEqual(self.tinh_trang["qd43.pdf"].chuyen_tiep, [])

    def test_quy_dinh_cu_la_van_ban_bi_thay_va_moc_la_ngay_hieu_luc(self):
        quy_dinh = self.so.chuyen_tiep["8/2021/TT-BGDĐT"][0]
        self.assertEqual(quy_dinh["cu"], ["43/2007/QĐ-BGDĐT"])
        self.assertEqual(quy_dinh["moc"], "2021-05-03")
        self.assertIs(self.so.giu_lai["43/2007/QĐ-BGDĐT"][0], quy_dinh)

    def test_van_ban_cu_van_het_hieu_luc_nhung_mang_chuyen_tiep(self):
        tt = self.so.tinh_trang_nut("43/2007/QĐ-BGDĐT", self.HOM_NAY)
        self.assertEqual(tt["code"], "het_hieu_luc")
        self.assertTrue(tt["chuyen_tiep"])
        # Hỏi quy định hiện hành mà không nêu khóa: vẫn lọc bỏ như trước.
        self.assertTrue(self.so.het_hieu_luc("qd43.pdf", self.HOM_NAY))

    def test_nhan_hieu_luc_noi_ro_doi_tuong(self):
        nhan = self.so.nhan_hieu_luc("qd43.pdf", hom_nay=self.HOM_NAY)
        self.assertEqual(nhan["code"], "bi_thay_the")
        self.assertTrue(nhan["chuyen_tiep"])
        self.assertEqual(nhan["level"], "vua")
        self.assertIn("còn áp dụng chuyển tiếp", nhan["label"])
        # "Thông tư này" đặt cạnh văn bản cũ thì phải ghi rõ là Thông tư nào,
        # kèm ngày hiệu lực đọc được.
        self.assertIn("trước ngày Thông tư 8/2021/TT-BGDĐT (3/5/2021) có hiệu lực", nhan["note"])
        self.assertNotIn("Thông tư này", nhan["note"])

    def test_van_ban_bi_thay_khong_co_chuyen_tiep_giu_nhan_cu(self):
        nhan = self.so.nhan_hieu_luc("tt28.pdf", hom_nay=self.HOM_NAY)
        self.assertEqual(nhan["label"], "Hết hiệu lực")
        self.assertEqual(nhan["level"], "cao")

    def test_du_thao_khong_tao_chuyen_tiep(self):
        self.assertNotIn("28/2020/TT-BGDĐT", self.so.giu_lai)

    def test_mo_van_ban_cu_theo_khoa_trong_cau_hoi(self):
        self.assertIn("43/2007/QĐ-BGDĐT", self.so.mo_theo_chuyen_tiep(HOI_KHOA_CU))
        self.assertIn("43/2007/QĐ-BGDĐT", self.so.mo_theo_chuyen_tiep("Sinh viên khóa cũ đăng ký mấy tín chỉ?"))
        # Cùng năm mốc: chưa biết trước hay sau 3/5 nên vẫn mở, để trả lời có điều kiện.
        self.assertIn("43/2007/QĐ-BGDĐT", self.so.mo_theo_chuyen_tiep("khóa tuyển sinh 2021"))
        self.assertEqual(self.so.mo_theo_chuyen_tiep(HOI_KHOA_MOI), {})
        self.assertEqual(self.so.mo_theo_chuyen_tiep(HOI_CHUNG), {})
        mo = self.so.mo_theo_chuyen_tiep(HOI_KHOA_CU)
        self.assertTrue(self.so.mo_cho_tep("qd43.pdf", mo))
        self.assertFalse(self.so.mo_cho_tep("tt28.pdf", mo))

    def test_canh_bao_nguon_cu_la_chuyen_tiep(self):
        canh_bao = self.so.canh_bao([{"name": "qd43.pdf", "evidence": 2}], self.HOM_NAY)
        self.assertEqual(canh_bao[0]["loai"], "chuyen_tiep")
        self.assertIn("vẫn áp dụng cho các khóa tuyển sinh", canh_bao[0]["thong_bao"])

    def test_canh_bao_nguon_moi_co_dieu_khoan_chuyen_tiep(self):
        nguon = [{"name": "tt08.pdf", "evidence": 1}]
        canh_bao = self.so.canh_bao_chuyen_tiep(nguon, HOI_CHUNG, self.HOM_NAY)
        self.assertEqual(len(canh_bao), 1)
        self.assertEqual(canh_bao[0]["evidence"], 1)
        self.assertIn("Quyết định 43/2007/QĐ-BGDĐT", canh_bao[0]["thong_bao"])
        self.assertIn("hỏi kèm khóa", canh_bao[0]["thong_bao"])
        # Khóa người hỏi nêu đã ở sau mốc: không còn liên quan.
        self.assertEqual(self.so.canh_bao_chuyen_tiep(nguon, HOI_KHOA_MOI, self.HOM_NAY), [])
        # Văn bản cũ cũng là nguồn: canh_bao() đã báo, không lặp lại.
        self.assertEqual(self.so.canh_bao_chuyen_tiep(
            nguon + [{"name": "qd43.pdf", "evidence": 2}], HOI_KHOA_CU, self.HOM_NAY
        ), [])
        # Mốc quá cũ so với hôm nay (khóa tuyển sinh 2021 đã ra trường từ lâu).
        self.assertEqual(self.so.canh_bao_chuyen_tiep(nguon, HOI_CHUNG, date(2035, 1, 1)), [])
        # Nhưng nêu đúng khóa cũ thì vẫn báo, dù mốc đã lâu.
        self.assertTrue(self.so.canh_bao_chuyen_tiep(nguon, HOI_KHOA_CU, date(2035, 1, 1)))

    def test_ghi_chu_prompt_la_nguyen_van(self):
        ghi_chu = self.so.ghi_chu_chuyen_tiep([{"name": "tt08.pdf", "evidence": 1}], HOI_KHOA_CU, self.HOM_NAY)
        self.assertEqual(len(ghi_chu), 1)
        self.assertIn('"Các khóa tuyển sinh trước ngày Thông tư này có hiệu lực thi hành', ghi_chu[0])
        self.assertIn("văn bản cũ: Quyết định 43/2007/QĐ-BGDĐT", ghi_chu[0])

    def test_hoi_dich_danh_van_ban_cu(self):
        ghi_chu, _ = self.so.ghi_chu_cau_hoi("Quyết định 43/2007 quy định gì?", self.HOM_NAY)
        self.assertIn("Riêng các khóa tuyển sinh trước ngày Thông tư 8/2021/TT-BGDĐT (3/5/2021)", ghi_chu[0])

    def test_so_tay_them_va_loai_bo(self):
        so = qh.SoQuanHe(self.ho_so, self.tinh_trang, {
            "chuyen_tiep": [{
                "van_ban": "15/2026/TT-BGDĐT", "ap_dung_theo": ["28/2020/TT-BGDĐT"],
                "dieu_kien": "Học sinh đã nhập học trước năm học 2026-2027",
                "moc": "2026-09-01", "doi_tuong": "khoa", "can_cu": "đối chiếu tay",
            }],
            "loai_bo": [{"tu": "8/2021/TT-BGDĐT", "loai": "chuyen_tiep", "den": "43/2007/QĐ-BGDĐT"}],
        })
        self.assertNotIn("43/2007/QĐ-BGDĐT", so.giu_lai)
        self.assertEqual(so.giu_lai["28/2020/TT-BGDĐT"][0]["nguon"], "so_tay")
        self.assertTrue(so.tinh_trang_nut("28/2020/TT-BGDĐT", self.HOM_NAY)["chuyen_tiep"])

    def test_van_ban_duoc_nhac_con_hieu_luc_thi_khong_bao(self):
        self.assertIn("22/2021/TT-BGDĐT", self.so.giu_lai)
        nguon = [{"name": "tt30.pdf", "evidence": 1}]
        self.assertEqual(self.so.canh_bao_chuyen_tiep(nguon, HOI_CHUNG, self.HOM_NAY), [])
        self.assertNotIn("22/2021/TT-BGDĐT", self.so.mo_theo_chuyen_tiep("khóa cũ"))
        self.assertEqual(self.so.nhan_hieu_luc("tt22.pdf", hom_nay=self.HOM_NAY)["code"], "con_hieu_luc")

    def test_xuat_va_thong_ke(self):
        bang = self.so.xuat(self.HOM_NAY)
        self.assertIn("8/2021/TT-BGDĐT", [m["van_ban"] for m in bang["chuyen_tiep"]])
        self.assertEqual(self.so.thong_ke()["chuyen_tiep"], 2)

    def test_doc_tinh_trang_cu_khong_co_truong_chuyen_tiep(self):
        muc = hl.TinhTrangThoiGian(ten_file="a.pdf", la_du_thao=False, ngay_hieu_luc=None)
        self.assertEqual(muc.chuyen_tiep, [])


class TangDichVuChuyenTiepTests(unittest.TestCase):
    def setUp(self):
        from rag_service import RAGService

        self.so, self.noi_dung, _, _ = kho_mau()
        self.service = RAGService.__new__(RAGService)
        self.service.so_quan_he = self.so
        self.service._doan_theo_tep = {
            ten: [Document(page_content=noi, metadata={"source_file": ten})]
            for ten, noi in self.noi_dung.items()
        }
        self.moi = Document(page_content="Sinh viên đăng ký tối đa 25 tín chỉ.", metadata={"source_file": "tt08.pdf"})

    def test_keo_van_ban_cu_khi_hoi_dung_khoa(self):
        docs, _ = self.service._them_van_ban_di_kem([self.moi], HOI_KHOA_CU)
        self.assertEqual([d.metadata["source_file"] for d in docs], ["tt08.pdf", "qd43.pdf"])
        self.assertEqual(docs[1].metadata["_di_kem"]["vai_tro"], "Văn bản cũ còn áp dụng chuyển tiếp")
        self.assertIn("còn áp dụng chuyển tiếp", docs[1].metadata["_hieu_luc"])

    def test_khong_keo_khi_khong_neu_khoa_hoac_khoa_moi(self):
        for cau in (HOI_CHUNG, HOI_KHOA_MOI):
            docs, _ = self.service._them_van_ban_di_kem([self.moi], cau)
            self.assertEqual([d.metadata["source_file"] for d in docs], ["tt08.pdf"], cau)

    def test_bo_loc_truy_hoi_mo_van_ban_cu_cho_dung_khoa(self):
        cu = Document(page_content="Tối đa 30 tín chỉ.", metadata={"source_file": "qd43.pdf"})
        khac = Document(page_content="Điều lệ cũ.", metadata={"source_file": "tt28.pdf"})
        loc = self.service._loc_hieu_luc(HOI_KHOA_CU)
        self.assertTrue(loc(cu))
        self.assertFalse(loc(khac))
        self.assertFalse(self.service._loc_hieu_luc(HOI_CHUNG)(cu))

    def test_khong_cache_cau_hoi_neu_khoa(self):
        from rag_service import RAGService

        self.assertFalse(RAGService._cache_duoc(HOI_KHOA_CU, None))
        self.assertTrue(RAGService._cache_duoc(HOI_CHUNG, None))


if __name__ == "__main__":
    unittest.main()
