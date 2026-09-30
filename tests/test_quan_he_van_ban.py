"""Hiệu lực và văn bản đi kèm: trích quan hệ, đồ thị trên số hiệu, kéo văn bản
đi kèm vào ngữ cảnh."""

import unittest
from datetime import date

from langchain_core.documents import Document

import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import van_ban_meta as vm


def van_ban(so_hieu_dong: str, than: str, ngay: str = "ngày 10 tháng 1 năm 2026") -> str:
    return (
        f"BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: {so_hieu_dong} Hà Nội, {ngay}\nTHÔNG TƯ\n"
        f"Căn cứ Luật Giáo dục;\nĐiều 1. Phạm vi\n{than}"
    )


class TrichQuanHeTests(unittest.TestCase):
    def test_bai_bo_vai_dieu_chi_la_mot_phan(self):
        # Trước đây câu này bị tính như thay thế toàn bộ Nghị định 61/2006.
        quan_he = vm.trich_quan_he_day_du(
            "6. Bãi bỏ quy định tại Điều 5 Nghị định số 61/2006/NĐ-CP ngày 20 tháng 6"
        )
        self.assertEqual(quan_he["bai_bo_mot_phan"], ["61/2006/NĐ-CP"])
        self.assertEqual(quan_he["thay_the"], [])

    def test_thay_the_ca_van_ban_van_la_toan_bo(self):
        quan_he = vm.trich_quan_he_day_du(
            "Thông tư này thay thế Thông tư số 17/2012/TT-BGDĐT ngày 16 tháng 5 năm 2012."
        )
        self.assertEqual(quan_he["thay_the"], ["17/2012/TT-BGDĐT"])
        self.assertEqual(quan_he["bai_bo_mot_phan"], [])

    def test_thay_hay_bo_cum_tu_la_sua_doi(self):
        # Văn bản kia vẫn áp dụng, chỉ khác chữ - không phải mất hiệu lực.
        for cau in (
            "3. Thay thế cụm từ “dạy trẻ” thành cụm từ “giảng dạy” tại điểm b khoản 2 "
            "Điều 4 Thông tư số 21/2025/TT-BGDĐT",
            "4. Bãi bỏ cụm từ “hoặc dạy trẻ” tại điểm a khoản 1 Điều 5 Thông tư số 21/2025/TT-BGDĐT",
        ):
            quan_he = vm.trich_quan_he_day_du(cau)
            self.assertEqual(quan_he["sua_doi"], ["21/2025/TT-BGDĐT"], cau)
            self.assertEqual(quan_he["bai_bo_mot_phan"], [], cau)

    def test_huong_dan_co_so_hieu(self):
        so, ten = vm.trich_huong_dan(van_ban(
            "5/2026/TT-BGDĐT",
            "Thông tư này hướng dẫn thi hành Nghị định số 71/2020/NĐ-CP về nâng chuẩn.",
        ))
        self.assertEqual(so, ["71/2020/NĐ-CP"])
        self.assertEqual(ten, [])

    def test_huong_dan_chi_co_ten_luat(self):
        so, ten = vm.trich_huong_dan(
            "CHÍNH PHỦ\nSố: 84/2020/NĐ-CP\nNGHỊ ĐỊNH\nQuy định chi tiết một số điều "
            "của Luật Giáo dục\nCăn cứ Luật Tổ chức Chính phủ;\nĐiều 1. ..."
        )
        self.assertEqual(so, [])
        self.assertEqual(ten, ["Luật Giáo dục"])

    def test_phu_luc_tach_tep_la_kem_theo(self):
        self.assertEqual(
            vm.trich_kem_theo("PHỤ LỤC\nBiểu mẫu (Kèm theo Thông tư số 44/2026/TT-BGDĐT ngày 9/6/2026)"),
            "44/2026/TT-BGDĐT",
        )

    def test_trich_yeu_sua_doi_quy_che_khong_phai_kem_theo(self):
        self.assertIsNone(vm.trich_kem_theo(
            "THÔNG TƯ SỬA ĐỔI, BỔ SUNG MỘT SỐ ĐIỀU CỦA QUY CHẾ THI TỐT NGHIỆP "
            "BAN HÀNH KÈM THEO THÔNG TƯ SỐ 24/2024/TT-BGDĐT"
        ))


class SoHieuTests(unittest.TestCase):
    def test_so_hieu_tu_ten_file(self):
        self.assertEqual(vm.so_hieu_tu_ten_file("Nghị-định-125-2026-NĐ-CP.pdf"), "125/2026/NĐ-CP")
        self.assertEqual(vm.so_hieu_tu_ten_file("07_2026_TT-BGDDT_696111.doc"), "7/2026/TT-BGDĐT")
        self.assertEqual(vm.so_hieu_tu_ten_file("thong-tu-27-2020-tt-bgddt.doc"), "27/2020/TT-BGDĐT")
        self.assertEqual(vm.so_hieu_tu_ten_file("Luật-123-2025-QH15.pdf"), "123/2025/QH15")

    def test_ten_file_nhac_so_hieu_giua_chung_khong_tinh(self):
        # Công văn hướng dẫn Thông tư 32 không phải chính Thông tư 32.
        self.assertIsNone(vm.so_hieu_tu_ten_file("huong-dan-thuc-hien-32-2020-tt-bgddt.pdf"))
        # Số đầu tên tệp của cổng Chính phủ là ID tải về, không có năm.
        self.assertIsNone(vm.so_hieu_tu_ten_file("281-cp.signed.pdf"))

    def test_ban_da_ky_ocr_hong_o_so(self):
        dau = (
            "BỘ GIÁO DỤC VÀ ĐÀO TẠO. CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM Sá:v4ố /2023/TT-BGDĐT "
            "Hà Nội, ngày z2 thángÉØ năm 2023\nTHÔNG TƯ\nCăn cứ ..."
        )
        self.assertFalse(hl.phat_hien_du_thao(dau, "26-bgd.signed.pdf"))
        self.assertTrue(hl.phat_hien_du_thao(dau, "26-bgd.pdf"))
        self.assertEqual(vm.suy_so_hieu_chinh("26-bgd.signed.pdf", dau), ("26/2023/TT-BGDĐT", True))
        # Bản chưa ký có ô số trống là dự thảo: không điền số vào.
        self.assertEqual(vm.suy_so_hieu_chinh("26-bgd.pdf", dau), (None, False))


def kho_mau():
    """Kho nhỏ: 7/2026 thay 29/2023, 51/2026 sửa 52/2020, 11/2026 bãi bỏ vài điều
    của 21/2025, phụ lục kèm theo 44/2026, và một dự thảo đòi sửa 52/2020."""
    noi_dung = {
        "moi.pdf": van_ban("7/2026/TT-BGDĐT", "Thông tư này thay thế Thông tư số 29/2023/TT-BGDĐT."),
        "cu.pdf": van_ban("29/2023/TT-BGDĐT", "Quy định dạy thêm, học thêm.", "ngày 30 tháng 12 năm 2023"),
        "goc.pdf": van_ban("52/2020/TT-BGDĐT", "Điều lệ trường mầm non. Điều 5. Nhóm trẻ.", "ngày 31 tháng 12 năm 2020"),
        "sua.pdf": van_ban(
            "51/2026/TT-BGDĐT",
            "Sửa đổi, bổ sung một số điều của Thông tư số 52/2020/TT-BGDĐT.\n"
            "Khoản 2 Điều 5 Thông tư số 52/2020/TT-BGDĐT được sửa đổi như sau: nhóm trẻ tối đa 20 trẻ.",
        ),
        "gv.pdf": van_ban("21/2025/TT-BGDĐT", "Chế độ làm việc giáo viên mầm non.", "ngày 23 tháng 9 năm 2025"),
        "bai_bo.pdf": van_ban(
            "11/2026/TT-BGDĐT",
            "4. Bãi bỏ điểm a khoản 1 Điều 5 Thông tư số 21/2025/TT-BGDĐT.",
        ),
        "tt44.docx": van_ban("44/2026/TT-BGDĐT", "Quản lý chương trình khoa học."),
        "PHỤ LỤC TT 44.docx": "PHỤ LỤC\nBiểu mẫu (Kèm theo Thông tư số 44/2026/TT-BGDĐT ngày 9/6/2026)\nMẫu 01",
        "du_thao.docx": (
            "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: /2026/TT-BGDĐT Hà Nội, ngày tháng năm 2026\nTHÔNG TƯ\n"
            "Căn cứ ...\nĐiều 1. Sửa đổi, bổ sung một số điều của Thông tư số 52/2020/TT-BGDĐT."
        ),
    }
    ho_so = vm.xay_dung_ho_so(noi_dung)
    tinh_trang = hl.xay_dung(noi_dung, ho_so)
    so_tay = {
        "van_ban": {
            "38/2005/QH11": {"ten_goi": ["Luật Giáo dục"], "ngay_ban_hanh": "2005-06-14"},
            "43/2019/QH14": {"ten_goi": ["Luật Giáo dục"], "ngay_ban_hanh": "2019-06-14"},
        },
        "quan_he": [
            {"tu": "279/2026/NĐ-CP", "loai": "thay_the", "den": "37/2025/NĐ-CP"},
            {"tu": "7/2026/TT-BGDĐT", "loai": "thay_the", "den": "12/2020/TT-BGDĐT"},
        ],
        "loai_bo": [],
    }
    return qh.SoQuanHe(ho_so, tinh_trang, so_tay), noi_dung


class DoThiTests(unittest.TestCase):
    HOM_NAY = date(2026, 9, 30)

    def setUp(self):
        self.so, self.noi_dung = kho_mau()

    def test_tinh_trang_tung_van_ban(self):
        tt = lambda nut: self.so.tinh_trang_nut(nut, self.HOM_NAY)["code"]
        self.assertEqual(tt("29/2023/TT-BGDĐT"), "het_hieu_luc")
        self.assertEqual(tt("52/2020/TT-BGDĐT"), "da_sua_doi")
        self.assertEqual(tt("21/2025/TT-BGDĐT"), "het_mot_phan")
        self.assertEqual(tt("7/2026/TT-BGDĐT"), "con_hieu_luc")
        # Quan hệ trong sổ tay, văn bản cũ không có trong kho.
        self.assertEqual(tt("37/2025/NĐ-CP"), "het_hieu_luc")

    def test_du_thao_khong_sua_doi_duoc_gi(self):
        boi = self.so.tinh_trang_nut("52/2020/TT-BGDĐT", self.HOM_NAY)["boi"]
        self.assertEqual(boi, ["51/2026/TT-BGDĐT"])

    def test_van_ban_thay_the_chua_hieu_luc_thi_cu_van_ap_dung(self):
        self.so.thong_tin["7/2026/TT-BGDĐT"] = {"ngay_hieu_luc": "2026-11-15"}
        tt = self.so.tinh_trang_nut("29/2023/TT-BGDĐT", self.HOM_NAY)
        self.assertEqual(tt["code"], "sap_het_hieu_luc")
        self.assertEqual(tt["tu_ngay"], "2026-11-15")
        self.assertFalse(self.so.het_hieu_luc("cu.pdf", self.HOM_NAY))

    def test_phu_luc_chung_so_phan_voi_van_ban_chinh(self):
        self.assertEqual(self.so.nut_cua_tep["PHỤ LỤC TT 44.docx"], "tep:PHỤ LỤC TT 44.docx")
        self.so.thong_tin["44/2026/TT-BGDĐT"] = {}
        self.so.vao.setdefault("44/2026/TT-BGDĐT", []).append(
            qh.QuanHe("99/2026/TT-BGDĐT", "thay_the", "44/2026/TT-BGDĐT")
        )
        self.assertTrue(self.so.het_hieu_luc("PHỤ LỤC TT 44.docx", self.HOM_NAY))

    def test_nhan_hieu_luc_giu_ma_cu(self):
        self.assertEqual(self.so.nhan_hieu_luc("cu.pdf", hom_nay=self.HOM_NAY)["code"], "bi_thay_the")
        self.assertIn("7/2026", self.so.nhan_hieu_luc("cu.pdf", hom_nay=self.HOM_NAY)["note"])
        self.assertEqual(self.so.nhan_hieu_luc("goc.pdf", hom_nay=self.HOM_NAY)["code"], "bi_sua_doi")
        self.assertEqual(self.so.nhan_hieu_luc("gv.pdf", hom_nay=self.HOM_NAY)["code"], "het_mot_phan")
        self.assertEqual(self.so.nhan_hieu_luc("du_thao.docx", hom_nay=self.HOM_NAY)["code"], "du_thao")

    def test_di_kem_theo_thu_tu_uu_tien(self):
        cac_tep = [m["tep"] for m in self.so.di_kem("goc.pdf", self.HOM_NAY)]
        self.assertEqual(cac_tep, ["sua.pdf"])
        # Đang trích văn bản sửa đổi thì kéo văn bản gốc.
        muc = self.so.di_kem("sua.pdf", self.HOM_NAY)[0]
        self.assertEqual((muc["tep"], muc["vai_tro"]), ("goc.pdf", "Văn bản gốc được sửa đổi"))
        # Phụ lục <-> văn bản chính.
        self.assertEqual([m["tep"] for m in self.so.di_kem("tt44.docx")], ["PHỤ LỤC TT 44.docx"])
        self.assertEqual([m["tep"] for m in self.so.di_kem("PHỤ LỤC TT 44.docx")], ["tt44.docx"])

    def test_di_kem_khong_keo_van_ban_het_hieu_luc(self):
        # Trích văn bản mới: văn bản cũ nó thay không được kéo vào.
        self.assertEqual(self.so.di_kem("moi.pdf", self.HOM_NAY), [])
        # Trích văn bản cũ: kéo văn bản mới.
        self.assertEqual([m["tep"] for m in self.so.di_kem("cu.pdf", self.HOM_NAY)], ["moi.pdf"])

    def test_lien_quan_ke_ca_van_ban_ngoai_kho(self):
        muc = self.so.lien_quan("moi.pdf")
        self.assertEqual({m["nhan"] for m in muc}, {"Thông tư 29/2023/TT-BGDĐT", "Thông tư 12/2020/TT-BGDĐT"})
        ngoai_kho = [m for m in muc if m["so_hieu"] == "12/2020/TT-BGDĐT"][0]
        self.assertEqual(ngoai_kho["tep"], [])

    def test_cau_hoi_nhac_van_ban_cu_rut_gon(self):
        self.assertEqual(self.so.van_ban_trong_cau_hoi("Nghị định 37/2025 quy định gì?"), ["37/2025/NĐ-CP"])
        ghi_chu, keo = self.so.ghi_chu_cau_hoi("thông tư 29/2023 về dạy thêm", self.HOM_NAY)
        self.assertIn("đã hết hiệu lực", ghi_chu[0])
        self.assertEqual([m["tep"] for m in keo], ["moi.pdf"])
        # Văn bản còn nguyên hiệu lực thì không có gì để nói.
        self.assertEqual(self.so.ghi_chu_cau_hoi("Thông tư 7/2026 quy định gì", self.HOM_NAY), ([], []))

    def test_ten_luat_chon_ban_truoc_van_ban_dang_xet(self):
        self.assertEqual(self.so._tra_ten_luat("Luật Giáo dục", "2020-06-30"), "43/2019/QH14")
        self.assertEqual(self.so._tra_ten_luat("Luật Giáo dục", "2010-01-01"), "38/2005/QH11")
        self.assertIsNone(self.so._tra_ten_luat("Luật Đất đai", "2020-01-01"))

    def test_canh_bao_chi_ra_nguon_thay_the(self):
        canh_bao = self.so.canh_bao([
            {"evidence": 1, "name": "cu.pdf"},
            {"evidence": 2, "name": "moi.pdf"},
        ], self.HOM_NAY)
        self.assertEqual(len(canh_bao), 1)
        self.assertEqual(canh_bao[0]["loai"], "thay_the")
        self.assertIn("nguồn [2]", canh_bao[0]["thong_bao"])

    def test_so_tay_loai_bo_quan_he_sai(self):
        so = qh.SoQuanHe(self.so.ho_so, self.so.tinh_trang, {
            "loai_bo": [{"tu": "7/2026/TT-BGDĐT", "loai": "thay_the", "den": "29/2023/TT-BGDĐT"}],
        })
        self.assertEqual(so.tinh_trang_nut("29/2023/TT-BGDĐT", self.HOM_NAY)["code"], "con_hieu_luc")


class ThoiDiemTests(unittest.TestCase):
    """Hiện hành hay lịch sử, và hiệu lực tính tại mốc quá khứ."""

    HOM_NAY = date(2026, 9, 30)

    def test_nhan_ra_moc_thoi_gian(self):
        tim = lambda cau: qh.thoi_diem_trong_cau_hoi(cau, self.HOM_NAY)
        self.assertEqual(tim("Năm 2023 quy định dạy thêm thế nào?"), date(2023, 12, 31))
        self.assertEqual(tim("tại ngày 15/3/2024 thì sao"), date(2024, 3, 15))
        self.assertEqual(tim("ngày 15 tháng 3 năm 2024"), date(2024, 3, 15))
        self.assertEqual(tim("tháng 2/2024 áp dụng gì"), date(2024, 2, 29))
        # Số hiệu không phải mốc thời gian; năm nay là hỏi hiện tại.
        self.assertIsNone(tim("Thông tư 29/2023 quy định gì?"))
        self.assertIsNone(tim("năm 2026 áp dụng gì"))

    def test_che_do_lich_su(self):
        che_do = lambda cau: qh.che_do_thoi_gian(cau, self.HOM_NAY)[0]
        self.assertEqual(che_do("Trước đây theo văn bản 124 quy định thế nào?"), "lich_su")
        self.assertEqual(che_do("Quy định cũ về dạy thêm"), "lich_su")
        self.assertEqual(che_do("Năm 2023 giáo viên dạy bao nhiêu tiết?"), "lich_su")
        self.assertEqual(che_do("Giáo viên dạy bao nhiêu tiết một tuần?"), "hien_hanh")
        self.assertEqual(che_do("Nghị định 124/2024 quy định gì?"), "hien_hanh")

    def test_hieu_luc_tai_moc_qua_khu(self):
        so, _ = kho_mau()
        # 7/2026 thay 29/2023; năm 2024 thì 29/2023 vẫn đang áp dụng.
        self.assertEqual(so.tinh_trang_nut("29/2023/TT-BGDĐT", date(2024, 12, 31))["code"], "sap_het_hieu_luc")
        self.assertEqual(so.tinh_trang_nut("29/2023/TT-BGDĐT", date(2026, 9, 30))["code"], "het_hieu_luc")
        self.assertEqual(so.nhan_hieu_luc("cu.pdf", hom_nay=date(2024, 12, 31))["level"], "vua")

    def test_bang_trang_thai_ke_ca_van_ban_ngoai_kho(self):
        so, _ = kho_mau()
        bang = so.xuat(self.HOM_NAY)["van_ban"]
        self.assertEqual(bang["37/2025/NĐ-CP"]["tinh_trang"], "het_hieu_luc")
        self.assertEqual(bang["37/2025/NĐ-CP"]["boi"], ["279/2026/NĐ-CP"])
        self.assertEqual(bang["37/2025/NĐ-CP"]["tep"], [])
        self.assertEqual(bang["7/2026/TT-BGDĐT"]["tinh_trang"], "con_hieu_luc")


class XepHangTheoHieuLucTests(unittest.TestCase):
    """Lọc văn bản hết hiệu lực và ưu tiên văn bản mới hơn khi cùng phạm vi."""

    NOI_DUNG = "Hội đồng xét công nhận tốt nghiệp trung học cơ sở do Chủ tịch Ủy ban nhân dân thành lập gồm"

    def _hai_ban(self):
        cu = Document(page_content=self.NOI_DUNG + " trưởng phòng giáo dục.",
                      metadata={"source_file": "cu.pdf", "_ngay_van_ban": "2023-12-20", "_rrf_score": 0.02})
        moi = Document(page_content=self.NOI_DUNG + " chủ tịch xã.",
                       metadata={"source_file": "moi.pdf", "_ngay_van_ban": "2025-12-25", "_rrf_score": 0.02})
        return cu, moi

    def test_ban_moi_hon_thang_khi_cung_pham_vi(self):
        from hybrid_retrieval import xep_hang_theo_lien_quan

        cu, moi = self._hai_ban()
        ket_qua = xep_hang_theo_lien_quan("hội đồng xét tốt nghiệp gồm ai", [cu, moi], 2)
        self.assertEqual(ket_qua[0].metadata["source_file"], "moi.pdf")

    def test_hoi_lich_su_khong_uu_tien_ban_moi(self):
        from hybrid_retrieval import xep_hang_theo_lien_quan

        cu, moi = self._hai_ban()
        xep_hang_theo_lien_quan("hội đồng xét tốt nghiệp gồm ai", [cu, moi], 2, lich_su=True)
        self.assertEqual(cu.metadata["_retrieval_score"], moi.metadata["_retrieval_score"])

    def test_khong_uu_tien_khi_khac_pham_vi(self):
        from hybrid_retrieval import xep_hang_theo_lien_quan

        cu = Document(page_content="Điều lệ trường mầm non quy định nhóm trẻ.",
                      metadata={"source_file": "a.pdf", "_ngay_van_ban": "2020-01-01", "_rrf_score": 0.02})
        moi = Document(page_content="Học bạ số được ký bằng chữ ký điện tử.",
                       metadata={"source_file": "b.pdf", "_ngay_van_ban": "2026-01-01", "_rrf_score": 0.02})
        xep_hang_theo_lien_quan("x", [cu, moi], 2)
        self.assertEqual(cu.metadata["_retrieval_score"], moi.metadata["_retrieval_score"])

    def test_loc_hieu_luc_bo_ung_vien_het_hieu_luc(self):
        from unittest import mock

        import hybrid_retrieval as hr

        cu, moi = self._hai_ban()
        vector_store = mock.Mock()
        vector_store.similarity_search_with_score.return_value = [(cu, 0.1), (moi, 0.2)]
        with mock.patch.object(hr, "_ket_qua_bm25_co_diem", return_value=[]):
            ket_qua = hr.truy_hoi_hybrid(
                "hội đồng", vector_store, None,
                loc_hieu_luc=lambda doc: doc.metadata["source_file"] != "cu.pdf",
            )
        self.assertEqual([d.metadata["source_file"] for d in ket_qua], ["moi.pdf"])
        # Không nới rổ ứng viên như bộ lọc phạm vi.
        self.assertEqual(vector_store.similarity_search_with_score.call_args.kwargs["k"], hr.SO_UNG_VIEN_MOI_RETRIEVER)


class ChonDoanTests(unittest.TestCase):
    def test_uu_tien_doan_nhac_so_hieu_nguon(self):
        cac_doan = [
            Document(page_content="Điều 1. Phạm vi điều chỉnh về nhóm trẻ.", metadata={}),
            Document(page_content="Khoản 2 Điều 5 Thông tư số 52/2020/TT-BGDĐT được sửa đổi.", metadata={}),
        ]
        doan = qh.chon_doan_tot_nhat(cac_doan, "nhóm trẻ tối đa bao nhiêu", "52/2020/TT-BGDĐT")
        self.assertIs(doan, cac_doan[1])


class TangDichVuTests(unittest.TestCase):
    """_them_van_ban_di_kem trên một RAGService dựng tay (không nạp mô hình)."""

    def setUp(self):
        from rag_service import RAGService

        self.so, self.noi_dung = kho_mau()
        self.service = RAGService.__new__(RAGService)
        self.service.so_quan_he = self.so
        self.service._doan_theo_tep = {
            ten: [Document(page_content=noi, metadata={"source_file": ten})]
            for ten, noi in self.noi_dung.items()
        }

    def test_keo_van_ban_sua_doi_va_khong_dong_vao_doan_goc(self):
        goc = Document(page_content="Điều 5. Nhóm trẻ.", metadata={"source_file": "goc.pdf"})
        docs, ghi_chu = self.service._them_van_ban_di_kem([goc], "nhóm trẻ tối đa bao nhiêu trẻ")
        self.assertEqual([d.metadata["source_file"] for d in docs], ["goc.pdf", "sua.pdf"])
        self.assertEqual(docs[1].metadata["_di_kem"]["evidence"], 1)
        self.assertEqual(docs[1].metadata["_di_kem"]["vai_tro"], "Văn bản sửa đổi, bổ sung")
        self.assertIn("Đã được sửa đổi", docs[0].metadata["_hieu_luc"])
        self.assertNotIn("_hieu_luc", goc.metadata)
        self.assertEqual(ghi_chu, [])

    def test_cau_hoi_ve_van_ban_da_bi_thay(self):
        khac = Document(page_content="Điều lệ trường.", metadata={"source_file": "goc.pdf"})
        docs, ghi_chu = self.service._them_van_ban_di_kem([khac], "Thông tư 29/2023 quy định gì?")
        self.assertIn("moi.pdf", [d.metadata["source_file"] for d in docs])
        self.assertTrue(ghi_chu)

    def test_prompt_co_dong_hieu_luc_va_di_kem(self):
        from main import tao_rag_chain

        _, format_docs = tao_rag_chain(None, lambda _: "")
        goc = Document(page_content="Điều 5. Nhóm trẻ.", metadata={"source_file": "goc.pdf"})
        docs, _ = self.service._them_van_ban_di_kem([goc], "nhóm trẻ")
        ngu_canh = format_docs(docs)
        self.assertIn("Hiệu lực: Đã được sửa đổi", ngu_canh)
        self.assertIn("Đi kèm: Văn bản sửa đổi, bổ sung của EVIDENCE 1", ngu_canh)

    def test_nguon_co_van_ban_lien_quan(self):
        from rag_service import RAGService

        goc = Document(page_content="Điều 5.", metadata={"source_file": "goc.pdf"})
        docs, _ = self.service._them_van_ban_di_kem([goc], "nhóm trẻ")
        nguon = RAGService._sources(docs, so_quan_he=self.so)
        self.assertEqual(nguon[0]["lien_quan"][0]["mo_ta"], "Được sửa đổi, bổ sung bởi")
        self.assertEqual(nguon[0]["lien_quan"][0]["tep"], "sua.pdf")
        self.assertEqual(nguon[1]["di_kem"]["evidence"], 1)


if __name__ == "__main__":
    unittest.main()
