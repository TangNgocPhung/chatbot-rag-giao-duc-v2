import os
import random
import unittest
from unittest import mock

from fastapi.testclient import TestClient

import goi_y_cau_hoi
from api import app
from hieu_luc_bo_sung import TinhTrangThoiGian
from phan_loai_giao_duc import PhanLoai
from rag_service import service
from van_ban_meta import HoSoVanBan


def bo_bien_che_do():
    """Chạy test như máy chưa đặt RAG_GOI_Y_MO_DAU, dù máy thật có đặt."""
    moi_truong = {k: v for k, v in os.environ.items() if k != "RAG_GOI_Y_MO_DAU"}
    return mock.patch.dict(os.environ, moi_truong, clear=True)


class TieuDeTuTenTepTests(unittest.TestCase):
    def test_ten_tai_tu_cong_van_ban_thanh_cau_hoi(self):
        cau_hoi = goi_y_cau_hoi.goi_y_tu_kho(
            {"Thông tư quy định về dạy thêm, học thêm.pdf": None}
        )
        self.assertEqual(
            cau_hoi,
            ["Thông tư quy định về dạy thêm, học thêm có những nội dung chính nào?"],
        )

    def test_ten_ma_hoa_bi_loai(self):
        self.assertEqual(
            goi_y_cau_hoi.goi_y_tu_kho({
                "20-bgddt.pdf": None,
                "PPCT-5.docx": None,
                "5512_BGDDT-GDTrH_462988 (1).doc": None,
                "PhanPhoi-ChuongTrinh-Tin4.docx": None,
                "QUAN 10 - NOI DUNG GDKNCDS KHOI LOP 3-4-5-2.docx": None,
            }),
            [],
        )

    def test_ten_bi_cat_ngan_thi_bo_chu_cat_do_va_ma_bam(self):
        tieu_de = goi_y_cau_hoi._lam_sach_tieu_de(
            "Phê duyệt đề án Chương trình học bổng toàn phần dành cho sinh viên "
            "xuất sắc đi đào tạo về các công nghệ ch--caa14599.pdf"
        )
        self.assertTrue(tieu_de.endswith("về các công nghệ"), tieu_de)

    def test_so_hieu_trong_ten_tep_duoc_tra_lai_dau_gach_cheo(self):
        tieu_de = goi_y_cau_hoi._lam_sach_tieu_de(
            "Sửa đổi, bổ sung một số điều của Nghị định số 86_2021_NĐ-CP.pdf"
        )
        self.assertIn("86/2021/NĐ-CP", tieu_de)

    def test_ten_qua_dai_khong_dung_lam_goi_y(self):
        dai = "Thông tư quy định " + "tiêu chuẩn và quy trình biên soạn tài liệu " * 4
        self.assertEqual(goi_y_cau_hoi.goi_y_tu_kho({f"{dai}.pdf": None}), [])


KHO_MUOI_VAN_BAN = {
    f"Thông tư quy định nội dung {chu} trong trường phổ thông.pdf": None
    for chu in "ABCDEFGHIJ"
}


class GoiYMoDauTinhTests(unittest.TestCase):
    def setUp(self):
        self.moi_truong = bo_bien_che_do()
        self.moi_truong.start()
        self.addCleanup(self.moi_truong.stop)

    def test_bo_cau_tinh_du_17_cau_chia_4_nhom(self):
        self.assertEqual(
            [(nhom["chu_de"], len(nhom["cau_hoi"])) for nhom in goi_y_cau_hoi.nhom_goi_y_tinh()],
            [("Mầm non & phổ thông", 6), ("Giáo dục nghề nghiệp", 3),
             ("Giáo dục đại học", 4), ("Chính sách và đội ngũ nhà giáo", 4)],
        )
        self.assertEqual(len(set(goi_y_cau_hoi.GOI_Y_CHU_DE)), 17)

    def test_mac_dinh_la_bo_cau_tinh_khong_tron_cau_tu_kho(self):
        lan_mot = goi_y_cau_hoi.goi_y_mo_dau(KHO_MUOI_VAN_BAN, 6, random.Random(1))
        lan_hai = goi_y_cau_hoi.goi_y_mo_dau(KHO_MUOI_VAN_BAN, 6, random.Random(2))
        self.assertEqual(lan_mot, lan_hai)
        self.assertTrue(set(lan_mot) <= set(goi_y_cau_hoi.GOI_Y_CHU_DE))

    def test_lay_it_cau_van_trai_du_cac_chu_de(self):
        # Lời từ chối chỉ chừa ba chỗ gợi ý; ba câu đó không được dồn cả vào
        # nhóm mầm non & phổ thông.
        nhom_cua = {
            cau: nhom["chu_de"]
            for nhom in goi_y_cau_hoi.nhom_goi_y_tinh() for cau in nhom["cau_hoi"]
        }
        self.assertEqual(len({nhom_cua[cau] for cau in goi_y_cau_hoi.goi_y_mo_dau({}, 4)}), 4)

    def test_lay_du_bo_thi_ra_dung_17_cau(self):
        self.assertEqual(
            sorted(goi_y_cau_hoi.goi_y_mo_dau({}, 17)), sorted(goi_y_cau_hoi.GOI_Y_CHU_DE)
        )

    def test_so_luong_bi_chan_tren_va_chan_duoi(self):
        self.assertEqual(len(goi_y_cau_hoi.goi_y_mo_dau({}, 0)), 1)
        self.assertEqual(
            len(goi_y_cau_hoi.goi_y_mo_dau({}, 999)), goi_y_cau_hoi.SO_GOI_Y_TOI_DA
        )

    def test_che_do_la_quay_ve_bo_cau_tinh(self):
        self.assertEqual(goi_y_cau_hoi.che_do_goi_y_mo_dau("khong-co"), "tinh")
        with mock.patch.dict(os.environ, {"RAG_GOI_Y_MO_DAU": "Metadata"}):
            self.assertEqual(goi_y_cau_hoi.che_do_goi_y_mo_dau(), "metadata")


class GoiYTheoVaiTroTests(unittest.TestCase):
    def setUp(self):
        self.moi_truong = bo_bien_che_do()
        self.moi_truong.start()
        self.addCleanup(self.moi_truong.stop)

    def test_moi_vai_tro_co_mot_nhom_sau_cau_khong_trung(self):
        self.assertEqual(
            [ma for ma, _ in goi_y_cau_hoi.VAI_TRO],
            list(goi_y_cau_hoi.GOI_Y_THEO_VAI_TRO),
        )
        for ma, (chu_de, cac_cau) in goi_y_cau_hoi.GOI_Y_THEO_VAI_TRO.items():
            with self.subTest(ma):
                self.assertTrue(chu_de)
                self.assertEqual(len(cac_cau), 6)
                self.assertEqual(len(set(cac_cau)), 6)
                for cau in cac_cau:
                    self.assertLessEqual(len(cau), goi_y_cau_hoi._DO_DAI_CAU_HOI_TOI_DA)
                    self.assertTrue(cau.endswith("?"), cau)

    def test_cau_hoi_con_so_van_vao_dung_cong_cu_tinh(self):
        # Mấy câu này được chọn vì công cụ tính trả lời chắc chắn đúng, kho có
        # văn bản hay không cũng vậy. Công cụ đổi cách nhận câu thì gợi ý phải
        # đổi theo, không thì bấm vào lại rơi sang RAG.
        import danh_gia_hoc_sinh
        import dinh_muc_tiet_day_pho_thong
        import tinh_luong

        cong_cu_cua = {
            "Giáo viên THCS dạy bao nhiêu tiết một tuần?": dinh_muc_tiet_day_pho_thong,
            "Lương giáo viên THPT hạng III bậc 1 hiện nay là bao nhiêu?": tinh_luong,
        }
        for cac_cau in (c for _, c in goi_y_cau_hoi.GOI_Y_THEO_VAI_TRO.values()):
            for cau in cac_cau:
                if "điểm thường xuyên" in cau.casefold():
                    cong_cu_cua[cau] = danh_gia_hoc_sinh
        self.assertEqual(len(cong_cu_cua), 4)
        for cau, cong_cu in cong_cu_cua.items():
            with self.subTest(cau):
                self.assertIsNotNone(cong_cu.nhan_dien(cau))

    def test_nhom_vai_tro_dung_dau_bon_nhom_chu_de_van_con(self):
        cac_nhom = goi_y_cau_hoi.nhom_goi_y_tinh("phu_huynh")
        self.assertEqual(cac_nhom[0]["vai_tro"], "phu_huynh")
        self.assertEqual(cac_nhom[0]["chu_de"], "Dành cho phụ huynh")
        self.assertTrue(all("vai_tro" not in nhom for nhom in cac_nhom[1:]))
        self.assertEqual(len(cac_nhom), 5)
        # Không câu nào hiện hai lần, và cả 17 câu tĩnh vẫn bấm được.
        tat_ca = [cau for nhom in cac_nhom for cau in nhom["cau_hoi"]]
        self.assertEqual(len(tat_ca), len(set(tat_ca)))
        self.assertTrue(set(goi_y_cau_hoi.GOI_Y_CHU_DE) <= set(tat_ca))

    def test_vai_tro_la_hay_trong_nhu_chua_chon(self):
        khong_chon = goi_y_cau_hoi.nhom_goi_y_tinh()
        for gia_tri in (None, "", "hieu_truong", "<script>"):
            with self.subTest(gia_tri):
                self.assertIsNone(goi_y_cau_hoi.chuan_hoa_vai_tro(gia_tri))
                self.assertEqual(goi_y_cau_hoi.nhom_goi_y_tinh(gia_tri), khong_chon)
        self.assertEqual(goi_y_cau_hoi.chuan_hoa_vai_tro(" Phu_Huynh "), "phu_huynh")

    def test_it_cau_thi_lay_cau_cua_vai_tro_truoc(self):
        self.assertEqual(
            goi_y_cau_hoi.goi_y_mo_dau({}, 3, vai_tro="giao_vien"),
            list(goi_y_cau_hoi.GOI_Y_THEO_VAI_TRO["giao_vien"][1][:3]),
        )

    def test_che_do_metadata_chi_nua_me_la_cau_cua_vai_tro(self):
        goi_y = goi_y_cau_hoi.goi_y_mo_dau(
            KHO_MUOI_VAN_BAN, 6, random.Random(1), che_do="metadata", vai_tro="hoc_sinh"
        )
        cua_vai_tro = set(goi_y_cau_hoi.GOI_Y_THEO_VAI_TRO["hoc_sinh"][1])
        self.assertEqual(len(goi_y), 6)
        self.assertEqual(sum(cau in cua_vai_tro for cau in goi_y), 3)
        self.assertTrue(all(cau in cua_vai_tro for cau in goi_y[:3]))

    def test_giao_dien_giu_cung_danh_sach_ma_vai_tro(self):
        # static/vai-tro.js dựng hộp chọn vai trò; mã lệch với máy chủ thì
        # người dùng chọn xong vẫn nhận bộ gợi ý chung mà không ai hay.
        duong_dan = os.path.join(os.path.dirname(goi_y_cau_hoi.__file__), "static", "vai-tro.js")
        with open(duong_dan, encoding="utf-8") as tep:
            ma_nguon = tep.read()
        for ma, nhan in goi_y_cau_hoi.VAI_TRO:
            with self.subTest(ma):
                self.assertIn(f"ma: '{ma}', nhan: '{nhan}'", ma_nguon)


class GoiYMoDauMetadataTests(unittest.TestCase):
    def goi_y(self, ho_so, so_luong=6, tinh_trang=None, hat_giong=1):
        return goi_y_cau_hoi.goi_y_mo_dau(
            ho_so, so_luong, random.Random(hat_giong),
            che_do="metadata", tinh_trang=tinh_trang,
        )

    def test_khong_co_kho_van_ban_van_co_goi_y_chu_de(self):
        goi_y = self.goi_y({})
        self.assertEqual(len(goi_y), 6)
        self.assertEqual(len(set(goi_y)), 6)

    def test_kho_du_van_ban_thi_ca_me_lay_tu_kho(self):
        goi_y = self.goi_y(KHO_MUOI_VAN_BAN)
        self.assertEqual(len(goi_y), 6)
        self.assertTrue(all("trong trường phổ thông" in cau for cau in goi_y), goi_y)

    def test_kho_it_van_ban_thi_bu_bang_cau_tinh(self):
        goi_y = self.goi_y({"Thông tư quy định về dạy thêm, học thêm.pdf": None})
        self.assertEqual(
            goi_y[0], "Thông tư quy định về dạy thêm, học thêm có những nội dung chính nào?"
        )
        self.assertTrue(set(goi_y[1:]) <= set(goi_y_cau_hoi.GOI_Y_CHU_DE))

    def test_moi_nhanh_cua_cay_quyet_dinh_gop_mot_cau(self):
        def ho_so(ten, so, **them):
            return HoSoVanBan(ten_file=ten, so_hieu=so, loai="Thông tư", **them)

        kho = {
            "a.pdf": ho_so("a.pdf", "1/2020/TT-BGDĐT", bi_thay_the_boi=["b.pdf"]),
            "b.pdf": ho_so("b.pdf", "2/2024/TT-BGDĐT", thay_the=["1/2020/TT-BGDĐT"]),
            "c.pdf": ho_so("c.pdf", "3/2021/TT-BGDĐT", bi_sua_doi_boi=["b.pdf"]),
            "d.pdf": ho_so("d.pdf", "4/2099/TT-BGDĐT"),
            "e.pdf": ho_so("e.pdf", "5/2025/TT-BGDĐT"),
        }
        kho.update({
            f"Thông tư quy định nội dung {chu} trong trường phổ thông.pdf": None
            for chu in "ABCDEF"
        })
        tinh_trang = {
            "d.pdf": TinhTrangThoiGian(ten_file="d.pdf", ngay_hieu_luc="2999-01-01"),
            "e.pdf": TinhTrangThoiGian(ten_file="e.pdf", la_du_thao=True),
        }
        goi_y = self.goi_y(kho, 6, tinh_trang)
        self.assertEqual(goi_y[:5], [
            "Văn bản nào đã thay thế Thông tư 1/2020/TT-BGDĐT?",
            "Thông tư 3/2021/TT-BGDĐT đã được sửa đổi, bổ sung những nội dung nào?",
            "Thông tư 4/2099/TT-BGDĐT có hiệu lực từ ngày nào và áp dụng ra sao?",
            "Đã có văn bản chính thức nào ban hành thay cho bản dự thảo "
            "Thông tư 5/2025/TT-BGDĐT chưa?",
            "Thông tư 2/2024/TT-BGDĐT thay thế những văn bản nào?",
        ])
        self.assertIn("trong trường phổ thông có những nội dung chính nào?", goi_y[5])

    def test_ten_tep_ma_hoa_co_so_hieu_thi_goi_bang_so_hieu(self):
        goi_y = goi_y_cau_hoi.goi_y_tu_kho({
            "5512_BGDDT-GDTrH_462988.doc": HoSoVanBan(
                ten_file="5512_BGDDT-GDTrH_462988.doc",
                so_hieu="5512/BGDĐT-GDTrH", loai="Công văn",
            ),
            "PPCT-5.docx": HoSoVanBan(ten_file="PPCT-5.docx"),
        })
        self.assertEqual(goi_y, ["Công văn 5512/BGDĐT-GDTrH có những nội dung chính nào?"])


class GoiYTiepTheoTests(unittest.TestCase):
    def nguon(self, **ghi_de):
        nguon = {
            "name": "Thông tư quy định về dạy thêm, học thêm.pdf",
            "van_ban": {"so_hieu": "29/2024/TT-BGDĐT", "loai": "Thông tư", "thay_the": []},
            "validity": {"code": "con_hieu_luc"},
        }
        nguon.update(ghi_de)
        return nguon

    def test_van_ban_bi_thay_the_thi_goi_y_tim_van_ban_thay_the(self):
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Dạy thêm được quy định thế nào?",
            [self.nguon(validity={"code": "bi_thay_the"})],
        )
        self.assertEqual(
            goi_y[0], "Văn bản nào đã thay thế Thông tư 29/2024/TT-BGDĐT?"
        )

    def test_dieu_duoc_trich_thanh_goi_y_hoi_sau(self):
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Dạy thêm được quy định thế nào?",
            [self.nguon(article="Điều 4. Các trường hợp không được dạy thêm")],
        )
        self.assertIn(
            "Điều 4 của Thông tư 29/2024/TT-BGDĐT quy định chi tiết những gì?", goi_y
        )

    def test_ban_du_thao_thi_goi_y_tim_ban_chinh_thuc(self):
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Chế độ dạy thêm giờ thế nào?",
            [self.nguon(validity={"code": "du_thao"})],
        )
        self.assertEqual(
            goi_y[0],
            "Đã có văn bản chính thức nào ban hành thay cho bản dự thảo "
            "Thông tư 29/2024/TT-BGDĐT chưa?",
        )

    def test_moi_van_ban_chi_gop_mot_cau_goi_y(self):
        # Một câu trả lời hay trích hai ba Điều của cùng một thông tư; cả ba chỗ
        # gợi ý đều hỏi về văn bản đó thì mất hướng nhìn sang nguồn khác.
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Dạy thêm được quy định thế nào?",
            [
                self.nguon(article="Điều 2. Giải thích từ ngữ"),
                self.nguon(article="Điều 5. Dạy thêm trong nhà trường"),
                self.nguon(
                    name="Thông tư quy định chế độ làm việc của giáo viên.pdf",
                    van_ban={"so_hieu": "5/2025/TT-BGDĐT", "loai": "Thông tư", "thay_the": []},
                    validity={"code": "du_thao"},
                ),
            ],
        )
        self.assertEqual(
            goi_y[:2],
            [
                "Điều 2 của Thông tư 29/2024/TT-BGDĐT quy định chi tiết những gì?",
                "Đã có văn bản chính thức nào ban hành thay cho bản dự thảo "
                "Thông tư 5/2025/TT-BGDĐT chưa?",
            ],
        )

    def test_khong_goi_y_lai_dung_cau_vua_hoi(self):
        cau_hoi = "Tóm tắt những nội dung chính của Thông tư 29/2024/TT-BGDĐT"
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(cau_hoi, [self.nguon()])
        self.assertNotIn(cau_hoi, goi_y)
        self.assertEqual(len(goi_y), goi_y_cau_hoi.SO_GOI_Y_TIEP)

    def test_khong_co_nguon_van_tra_goi_y_chung(self):
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo("Câu hỏi gì đó", [])
        self.assertEqual(len(goi_y), goi_y_cau_hoi.SO_GOI_Y_TIEP)
        self.assertNotIn("", goi_y)

    def test_goi_y_theo_tep_dinh_kem_uu_tien_tom_tat(self):
        goi_y = goi_y_cau_hoi.goi_y_theo_tep("Tệp này nói gì?", ["bao-cao.pdf"])
        self.assertEqual(goi_y[0], "Tóm tắt tệp bao-cao.pdf")

    def test_nhieu_tep_thi_goi_y_so_sanh(self):
        goi_y = goi_y_cau_hoi.goi_y_theo_tep(
            "Hai tệp này nói gì?", ["bao-cao.pdf", "ke-hoach.docx"]
        )
        self.assertIn("So sánh nội dung giữa các tệp đã đính kèm", goi_y)


class GoiYTheoNoiDungTraLoiTests(unittest.TestCase):
    TRA_LOI_TRUYEN = (
        "Truyện kể về cuộc giao tranh giữa Sơn Tinh và Thủy Tinh để cầu hôn "
        "Mị Nương [1].\n"
        "- **Sính lễ**: vua đòi voi chín ngà, gà chín cựa [2].\n"
        "- Thủy Tinh đến sau, nổi giận dâng nước đánh Sơn Tinh [3]."
    )

    def test_tep_truyen_thi_goi_y_bam_nhan_vat_chu_khong_hoi_moc_thoi_gian(self):
        goi_y = goi_y_cau_hoi.goi_y_theo_tep(
            "Truyện nói về gì?", ["SƠN TINH - THỦY TINH.docx"],
            cau_tra_loi=self.TRA_LOI_TRUYEN,
        )
        self.assertEqual(goi_y[0], "Sơn Tinh và Thủy Tinh có quan hệ với nhau thế nào?")
        self.assertIn("Nói rõ hơn về sính lễ", goi_y)
        self.assertFalse(any("mốc thời gian" in cau for cau in goi_y))

    def test_nguon_khong_duoc_trich_thi_khong_goi_y_hoi_ve_no(self):
        nguon = [
            {
                "name": "thong-tu-37.doc",
                "van_ban": {"so_hieu": "37/2021/TT-BGDĐT", "loai": "Thông tư"},
                "article": "Điều 1. Ban hành kèm theo",
            },
            {"name": "11-sgk-tin-hoc-11-dinh-huong-tin-hoc-ung-dung.pdf"},
        ]
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Môn tin học là môn như thế nào",
            nguon,
            cau_tra_loi="Môn Tin học có định hướng **Tin học ứng dụng** [2].",
        )
        self.assertEqual(goi_y[0], "Nói rõ hơn về tin học ứng dụng")
        self.assertFalse(any("37/2021" in cau for cau in goi_y))
        self.assertFalse(any("sgk-tin-hoc" in cau for cau in goi_y))

    def test_hoi_mon_tin_hoc_khong_goi_y_thong_tu_thiet_bi_lac_de(self):
        # Câu trả lời thật: trích cả Thông tư 37 về thiết bị dạy học tiểu học,
        # nhắc "Nhà xuất bản Giáo dục Việt Nam" và giải nghĩa ICT/CS trong ngoặc.
        tra_loi = (
            "Dựa trên **cấu trúc và định hướng** của môn Tin học tại bậc THPT "
            "(từ lớp 10 trở lên):\n"
            "- Nội dung được tổ chức thành ICT (Tin học ứng dụng) và CS "
            "(Khoa học máy tính). [4]\n"
            "- Sách giáo khoa thuộc bộ của Nhà xuất bản Giáo dục Việt Nam. [4]\n"
            "- Danh mục thiết bị dạy học tối thiểu cấp Tiểu học không liệt kê "
            "chi tiết nội dung Tin học. [1]"
        )
        nguon = [
            {
                "name": "thong-tu-37-2021-tt-bgddt-bo-giao-duc-va-dao-tao.doc",
                "van_ban": {"so_hieu": "37/2021/TT-BGDĐT", "loai": "Thông tư"},
                "article": "Điều 1. Ban hành kèm theo Thông tư này Danh mục thiết bị",
            },
            {"name": "11-sgk-tin-hoc-11-dinh-huong-tin-hoc-ung-dung.pdf"},
            {"name": "12-sgk-tin-hoc-12-dinh-huong-tin-hoc-ung-dung.pdf"},
            {"name": "11-sgk-tin-hoc-11-dinh-huong-khoa-hoc-may-tinh.pdf"},
        ]
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Môn tin học là môn như thế nào", nguon, cau_tra_loi=tra_loi
        )
        self.assertEqual(
            goi_y[:2],
            # "Tin học ứng dụng" đã chạm chủ thể "môn tin học" nên không gắn thêm.
            ["Nói rõ hơn về tin học ứng dụng",
             "Khoa học máy tính trong môn tin học gồm những gì?"],
        )
        self.assertFalse(any("37/2021" in cau or "Việt Nam" in cau for cau in goi_y))
        self.assertFalse(any("lớp 10" in cau for cau in goi_y))

    def test_dau_cau_viet_hoa_khong_bi_coi_la_ten_rieng(self):
        y_chinh = goi_y_cau_hoi.rut_y_chinh("Học sinh được học hai buổi. Giáo viên dạy.")
        self.assertEqual(y_chinh, [])


CAU_HOI_CT_2018 = (
    "Chương trình giáo dục phổ thông 2018 đặt ra những yêu cầu nào về phẩm chất và năng lực?"
)
# Rút gọn từ một câu trả lời thật: ý chính in đậm, rồi bảng so sánh từng môn.
TRA_LOI_CT_2018 = (
    "Chương trình Giáo dục phổ thông 2018 đặt ra các yêu cầu sau:\n\n"
    "*   Góp phần hình thành ở học sinh các **phẩm chất chủ yếu** và **năng lực chung**. [4]\n"
    "*   Yêu cầu này được quy định cụ thể trong **Chương trình tổng thể**. [2]\n\n"
    "| Môn học | Yêu cầu | Nguồn |\n|---|---|---|\n"
    "| Giáo dục thể chất lớp 12 | Phẩm chất chủ yếu; **năng lực thể chất** (đặc thù). | [2] |\n"
    "| Tin học lớp 12 | Phát triển **năng lực tin học**. | [4] |\n"
)
NGUON_SGV = [
    {"name": "11-sgv-cong-nghe-11.pdf"},
    {"name": "12-sgv-giao-duc-the-chat-12-bong-chuyen.pdf"},
    {"name": "10-sgv-cong-nghe-10.pdf"},
    {"name": "12-sgv-tin-hoc-12.pdf"},
]


class TachChuDeTests(unittest.TestCase):
    def test_chu_the_dung_truoc_dong_tu_chinh(self):
        self.assertEqual(
            goi_y_cau_hoi.tach_chu_de(CAU_HOI_CT_2018),
            ("Chương trình giáo dục phổ thông 2018", "phẩm chất và năng lực"),
        )
        self.assertEqual(
            goi_y_cau_hoi.tach_chu_de("Kế hoạch bài dạy theo Công văn 5512 gồm những phần nào?")[0],
            "Kế hoạch bài dạy theo Công văn 5512",
        )

    def test_khong_co_dong_tu_chinh_thi_khong_doan(self):
        self.assertIsNone(goi_y_cau_hoi.tach_chu_de("Tiếng trung dạy từ lớp mấy")[0])

    def test_chu_the_la_nguoi_thi_bo(self):
        self.assertIsNone(goi_y_cau_hoi.tach_chu_de(
            "Học sinh phổ thông được miễn học phí trong những trường hợp nào?"
        )[0])

    def test_lay_lai_chu_the_tu_goi_y_cua_chinh_minh(self):
        for cau in (
            "Nói rõ hơn về phẩm chất chủ yếu trong Chương trình giáo dục phổ thông 2018",
            "Năng lực chung trong Chương trình giáo dục phổ thông 2018 gồm những gì?",
        ):
            self.assertEqual(
                goi_y_cau_hoi.tach_chu_de(cau)[0], "Chương trình giáo dục phổ thông 2018"
            )

    def test_ten_loai_van_ban_tro_troi_khong_phai_chu_the(self):
        # "ban hành" nằm trong tên văn bản: cắt ở đó thì chỉ còn mỗi "Thông tư".
        self.assertEqual(
            goi_y_cau_hoi.tach_chu_de(
                "Thông tư ban hành quy chế tuyển sinh có những nội dung chính nào?"
            )[0],
            "Thông tư ban hành quy chế tuyển sinh",
        )
        self.assertIsNone(goi_y_cau_hoi.tach_chu_de("Quyết định có hiệu lực từ ngày nào?")[0])

    def test_pham_vi_khong_dinh_duoi_cau_hoi(self):
        self.assertEqual(
            goi_y_cau_hoi.tach_chu_de("Luật Nhà giáo có quy định gì về phụ cấp là gì?")[1],
            "phụ cấp",
        )

    def test_trong_chi_tach_khi_phan_sau_la_ten_rieng(self):
        self.assertEqual(
            goi_y_cau_hoi.tach_chu_de(
                "Việc ứng dụng công nghệ trong giáo dục đại học được quy định thế nào?"
            )[0],
            "Việc ứng dụng công nghệ trong giáo dục đại học",
        )


class TenGoiNguonTests(unittest.TestCase):
    def test_nguon_ten_tep_ma_hoa_khong_thanh_cau_goi_y(self):
        """VPS 30/9: "Đã có văn bản chính thức nào ban hành thay cho bản dự
        thảo 222-cp.signed.pdf chưa?" - nguồn không có số hiệu trong hồ sơ."""
        nguon = [
            {"name": "08-sgv-tieng-trung-quoc-8.pdf"},
            {"name": "222-cp.signed.pdf", "validity": {"code": "du_thao"}},
        ]
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Tiếng trung dạy từ lớp mấy", nguon,
            cau_tra_loi="Sách dành cho **lớp 8** [1]. Đối tượng chuyển lớp theo Điều 5 [2].",
        )
        self.assertFalse([cau for cau in goi_y if ".pdf" in cau or "dự thảo" in cau], goi_y)
        self.assertEqual(len(goi_y), goi_y_cau_hoi.SO_GOI_Y_TIEP)

    def test_co_so_hieu_thi_van_hoi_ve_du_thao(self):
        nguon = [{
            "name": "du-thao-222.pdf",
            "van_ban": {"so_hieu": "222/2025/NĐ-CP", "loai": "Nghị định"},
            "validity": {"code": "du_thao"},
        }]
        self.assertEqual(
            goi_y_cau_hoi.goi_y_tiep_theo("Học phí được miễn khi nào?", nguon)[0],
            "Đã có văn bản chính thức nào ban hành thay cho bản dự thảo Nghị định 222/2025/NĐ-CP chưa?",
        )


class GoiYBamChuDeCauHoiTests(unittest.TestCase):
    def test_goi_y_gan_chu_the_va_bo_y_chi_co_trong_o_bang(self):
        self.assertEqual(
            goi_y_cau_hoi.goi_y_tiep_theo(
                CAU_HOI_CT_2018, NGUON_SGV, cau_tra_loi=TRA_LOI_CT_2018
            ),
            [
                "Nói rõ hơn về phẩm chất chủ yếu trong Chương trình giáo dục phổ thông 2018",
                "Năng lực chung trong Chương trình giáo dục phổ thông 2018 gồm những gì?",
                "Còn tài liệu nào khác trong kho nói về phẩm chất và năng lực?",
            ],
        )

    def test_y_trong_o_bang_van_dung_khi_ngoai_bang_khong_du_y(self):
        tra_loi = (
            "Các môn đều hướng tới phẩm chất chủ yếu. [1]\n\n"
            "| Môn | Năng lực |\n|---|---|\n"
            "| Thể dục | **năng lực thể chất** |\n| Mọi môn | **năng lực tự học** |\n"
        )
        y_chinh = [cum for cum, _ in goi_y_cau_hoi.rut_y_chinh(tra_loi, CAU_HOI_CT_2018)]
        self.assertEqual(y_chinh, ["năng lực thể chất", "năng lực tự học"])

    def test_y_neu_ten_mon_khong_duoc_hoi_thi_bo(self):
        """Câu trả lời thật trên VPS 30/9: điểm qua từng môn bằng gạch đầu dòng."""
        tra_loi = (
            "- **Phẩm chất và Năng lực chung**: mọi bài học đều góp phần hình thành [1].\n"
            "- **Giáo dục Tin học (Năng lực tin học)**: phát triển năng lực tin học [4].\n"
        )
        self.assertEqual(
            goi_y_cau_hoi.rut_y_chinh(tra_loi, CAU_HOI_CT_2018),
            [("Phẩm chất và Năng lực chung", False)],
        )
        # Hỏi đúng môn đó thì giữ, và bỏ phần chú thích trong ngoặc.
        self.assertIn(
            ("Giáo dục Tin học", False),
            goi_y_cau_hoi.rut_y_chinh(tra_loi, "Môn Tin học đặt ra yêu cầu nào về năng lực?"),
        )

    def test_ha_chu_hoa_le_nhung_giu_ten_rieng(self):
        self.assertEqual(
            goi_y_cau_hoi.goi_y_tiep_theo(
                CAU_HOI_CT_2018, NGUON_SGV,
                cau_tra_loi="- **Phẩm chất và Năng lực chung**: hình thành dần [1].",
            )[0],
            "Nói rõ hơn về phẩm chất và năng lực chung trong Chương trình giáo dục phổ thông 2018",
        )
        self.assertEqual(goi_y_cau_hoi._ha_chu_hoa_le("Luật Giáo dục sửa đổi"), "Luật Giáo dục sửa đổi")
        self.assertEqual(
            goi_y_cau_hoi._ha_chu_hoa_le("Rational Agent for Generating"),
            "Rational Agent for Generating",
        )
        self.assertEqual(
            goi_y_cau_hoi._ha_chu_hoa_le("Khung trình độ quốc gia Việt Nam"),
            "khung trình độ quốc gia Việt Nam",
        )

    def test_cau_noi_tiep_muon_chu_the_cua_cau_truoc(self):
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Còn năng lực đặc thù thì sao?", NGUON_SGV,
            cau_tra_loi=TRA_LOI_CT_2018, cau_hoi_truoc=CAU_HOI_CT_2018,
        )
        self.assertTrue(
            all("Chương trình giáo dục phổ thông 2018" in cau for cau in goi_y[:2]), goi_y
        )

    TRA_LOI_TIENG_TRUNG = (
        "Việc giảng dạy Tiếng Trung Quốc bắt đầu từ **lớp 8**. SGK Tiếng Trung Quốc 8 "
        "phục vụ Chương trình môn Tiếng Trung Quốc [1]. Người học có thể chuyển sang "
        "học bằng Tiếng Trung Quốc [1]."
    )
    NGUON_TIENG_TRUNG = [{"name": "08-sgv-tieng-trung-quoc-8.pdf"}]

    def test_khong_co_dong_tu_nhung_nhac_mon_thi_goi_y_sach_cung_mon(self):
        """VPS 30/9 "Tiếng trung dạy từ lớp mấy": trước ra "...về lớp 8?" và
        "...về nội dung này?"."""
        self.assertEqual(
            goi_y_cau_hoi.goi_y_tiep_theo(
                "Tiếng trung dạy từ lớp mấy", self.NGUON_TIENG_TRUNG,
                cau_tra_loi=self.TRA_LOI_TIENG_TRUNG, phan_loai=KHO_NGOAI_NGU,
            ),
            # "Tiếng Trung Quốc" là chính môn làm chủ thể nên không thành gợi ý.
            [
                "Sách giáo khoa Tiếng Trung Quốc lớp 3 gồm những bài học nào?",
                "Sách giáo khoa Tiếng Trung Quốc lớp 6 gồm những bài học nào?",
                "Sách giáo khoa Tiếng Trung Quốc lớp 10 gồm những bài học nào?",
            ],
        )

    def test_khong_co_bang_phan_loai_thi_cau_chung_gan_ten_mon(self):
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Tiếng trung dạy từ lớp mấy", self.NGUON_TIENG_TRUNG,
            cau_tra_loi=self.TRA_LOI_TIENG_TRUNG,
        )
        self.assertIn("Còn tài liệu nào khác trong kho nói về môn Tiếng Trung Quốc?", goi_y)
        self.assertFalse([cau for cau in goi_y if "lớp 8" in cau or "nội dung này" in cau], goi_y)

    def test_nhan_kem_so_khong_phai_y_chinh(self):
        self.assertEqual(
            goi_y_cau_hoi.rut_y_chinh(
                "Bắt đầu từ **lớp 8**, ôn tập vào **học kì 2**, áp dụng cho "
                "**học sinh lớp 8 và lớp 9**, **lớp 3, 4, 5**. **Học sinh khuyết tật** được miễn.",
                "",
            ),
            [("Học sinh khuyết tật", False)],
        )

    def test_chu_the_la_mon_thi_khong_hoi_lai_ten_mon_va_sach_chen_som(self):
        """VPS 30/9 lần hai: "Học sinh lớp 8 và lớp 9 trong môn Tiếng Trung Quốc
        gồm những gì?", "Nói rõ hơn về Tiếng Trung Quốc", sách thì bị đẩy ra ngoài."""
        tra_loi = (
            "Việc dạy **Tiếng Trung Quốc** áp dụng cho **học sinh lớp 8 và lớp 9** [1].\n"
            "- **Trình độ yêu cầu**: giao tiếp đơn giản [1].\n"
            "- **Tính chất giai đoạn**: phát triển và nâng cao [2].\n"
            "- **Kĩ năng viết**: viết chữ Hán [2].\n"
        )
        self.assertEqual(
            goi_y_cau_hoi.goi_y_tiep_theo(
                "Tiếng trung dạy từ lớp mấy", self.NGUON_TIENG_TRUNG,
                cau_tra_loi=tra_loi, phan_loai=KHO_NGOAI_NGU,
            ),
            [
                "Nói rõ hơn về trình độ yêu cầu trong môn Tiếng Trung Quốc",
                "Tính chất giai đoạn trong môn Tiếng Trung Quốc gồm những gì?",
                "Sách giáo khoa Tiếng Trung Quốc lớp 3 gồm những bài học nào?",
            ],
        )

    def test_khong_tach_duoc_chu_the_thi_giu_khuon_cu(self):
        # Không động từ chính, không nhắc môn nào: không có gì để gắn.
        goi_y = goi_y_cau_hoi.goi_y_tiep_theo(
            "Tóm tắt giúp tôi", NGUON_SGV, cau_tra_loi=TRA_LOI_CT_2018
        )
        self.assertEqual(goi_y[0], "Nói rõ hơn về phẩm chất chủ yếu")


def _sach(ten, mon, lop, loai="sach_giao_khoa"):
    return ten, PhanLoai(ten_file=ten, mon_hoc=[mon], lop=[lop], loai_noi_dung=loai)


KHO_NGOAI_NGU = dict([
    _sach("03-sgk-tieng-trung-quoc-3-tap-mot.pdf", "Tiếng Trung Quốc", 3),
    _sach("03-sgk-tieng-trung-quoc-3-tap-hai.pdf", "Tiếng Trung Quốc", 3),
    _sach("04-sgk-tieng-trung-quoc-4-tap-mot.pdf", "Tiếng Trung Quốc", 4),
    _sach("06-sgk-tieng-trung-quoc-6.pdf", "Tiếng Trung Quốc", 6),
    _sach("10-sgk-tieng-trung-quoc-10.pdf", "Tiếng Trung Quốc", 10),
    _sach("07-sgk-tieng-nhat-7.pdf", "Tiếng Nhật", 7),
    _sach("DeKiemTra-HK2-Lop3.docx", "Tin học", 3, "de_kiem_tra"),
    _sach("03-sgk-tin-hoc-3.pdf", "Tin học", 3),
    _sach("04-sgk-tin-hoc-4.pdf", "Tin học", 4),
])
DU_PHONG = ["Câu mẫu A?", "Câu mẫu B?", "Câu mẫu C?"]


class GoiYKhiTuChoiTests(unittest.TestCase):
    def test_nhac_toi_mon_thi_goi_y_sach_cung_mon_trai_qua_cac_cap(self):
        self.assertEqual(
            goi_y_cau_hoi.goi_y_khi_tu_choi(
                "Tiếng trung dạy từ lớp mấy", KHO_NGOAI_NGU, du_phong=DU_PHONG
            ),
            [
                "Sách giáo khoa Tiếng Trung Quốc lớp 3 gồm những bài học nào?",
                "Sách giáo khoa Tiếng Trung Quốc lớp 6 gồm những bài học nào?",
                "Sách giáo khoa Tiếng Trung Quốc lớp 10 gồm những bài học nào?",
            ],
        )

    def test_dung_lop_da_hoi_len_truoc(self):
        goi_y = goi_y_cau_hoi.goi_y_khi_tu_choi(
            "Tin học lớp 4 bài 20 nói gì", KHO_NGOAI_NGU, du_phong=DU_PHONG
        )
        self.assertEqual(goi_y[0], "Sách giáo khoa Tin học lớp 4 gồm những bài học nào?")
        # Đề kiểm tra không có khuôn hỏi: cổng chặn từ chối câu hỏi kiểu đó.
        self.assertFalse(any("Đề kiểm tra" in cau for cau in goi_y))

    def test_khong_nhan_ra_chu_de_thi_dung_cau_du_phong(self):
        self.assertEqual(
            goi_y_cau_hoi.goi_y_khi_tu_choi(
                "Cách nấu phở bò", KHO_NGOAI_NGU, du_phong=DU_PHONG
            ),
            DU_PHONG,
        )

    def test_ten_mon_chung_phai_kem_dau_hieu_truong_lop(self):
        kho = dict([_sach("04-sgk-khoa-hoc-4.pdf", "Khoa học", 4)])
        self.assertEqual(
            goi_y_cau_hoi.goi_y_khi_tu_choi(
                "Nghiên cứu khoa học của giảng viên tính giờ thế nào",
                kho, du_phong=DU_PHONG,
            ),
            DU_PHONG,
        )

    def test_dang_loc_pham_vi_thi_khong_goi_y_tai_lieu_ngoai_pham_vi(self):
        goi_y = goi_y_cau_hoi.goi_y_khi_tu_choi(
            "Tiếng trung dạy từ lớp mấy", KHO_NGOAI_NGU,
            pham_vi={"mon_hoc": ["Tiếng Nhật"]}, du_phong=DU_PHONG,
        )
        self.assertEqual(goi_y, DU_PHONG)

    def test_ten_van_ban_cham_chu_de_thi_goi_y_van_ban_do(self):
        goi_y = goi_y_cau_hoi.goi_y_khi_tu_choi(
            "Quy định về dạy thêm học thêm ở Hà Nội năm 2030",
            ho_so={
                "Thông tư quy định về dạy thêm, học thêm.pdf": None,
                "Thông tư quy định về chế độ làm việc của giáo viên.pdf": None,
            },
            du_phong=DU_PHONG,
        )
        self.assertEqual(goi_y, [
            "Thông tư quy định về dạy thêm, học thêm có những nội dung chính nào?",
            "Câu mẫu A?", "Câu mẫu B?",
        ])


class GoiYApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.ho_so_goc = service.ho_so_van_ban
        service.ho_so_van_ban = {
            "Thông tư quy định về dạy thêm, học thêm.pdf": HoSoVanBan(
                ten_file="Thông tư quy định về dạy thêm, học thêm.pdf",
                so_hieu="29/2024/TT-BGDĐT",
            )
        }

    def tearDown(self):
        service.ho_so_van_ban = self.ho_so_goc

    def test_tra_ve_dung_so_luong_goi_y(self):
        with bo_bien_che_do():
            response = self.client.get("/api/goi-y?so_luong=4")
        self.assertEqual(response.status_code, 200)
        goi_y = response.json()["goi_y"]
        self.assertEqual(len(goi_y), 4)
        self.assertEqual(len(set(goi_y)), 4)

    def test_mac_dinh_tra_ca_bo_cau_tinh_theo_nhom(self):
        with bo_bien_che_do():
            payload = self.client.get("/api/goi-y").json()
        self.assertEqual(payload["che_do"], "tinh")
        self.assertEqual(len(payload["nhom"]), 4)
        self.assertEqual(sum(len(nhom["cau_hoi"]) for nhom in payload["nhom"]), 17)

    def test_che_do_metadata_dung_ho_so_van_ban_trong_kho(self):
        payload = self.client.get("/api/goi-y?so_luong=3&che_do=metadata").json()
        self.assertEqual(payload["che_do"], "metadata")
        self.assertEqual(payload["nhom"], [])
        self.assertEqual(
            payload["goi_y"][0],
            "Thông tư quy định về dạy thêm, học thêm có những nội dung chính nào?",
        )

    def test_vai_tro_dua_nhom_cua_vai_tro_len_dau(self):
        with bo_bien_che_do():
            payload = self.client.get("/api/goi-y?so_luong=2&vai_tro=sinh_vien").json()
        self.assertEqual(payload["vai_tro"], "sinh_vien")
        self.assertEqual(payload["nhom"][0]["vai_tro"], "sinh_vien")
        self.assertEqual(
            payload["goi_y"], list(goi_y_cau_hoi.GOI_Y_THEO_VAI_TRO["sinh_vien"][1][:2])
        )

    def test_vai_tro_la_khong_lam_hong_request(self):
        with bo_bien_che_do():
            response = self.client.get("/api/goi-y?vai_tro=khong-co")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["vai_tro"])
        self.assertEqual(len(response.json()["nhom"]), 4)

    def test_goi_y_co_san_khi_kho_tri_thuc_chua_nap(self):
        # Giao diện lấy gợi ý ngay lúc mở trang, trước cả khi Ollama trả lời
        # được, nên endpoint không được phụ thuộc vào trạng thái "ready".
        trang_thai_goc = service.status.state
        service.status.state = "loading"
        try:
            response = self.client.get("/api/goi-y")
        finally:
            service.status.state = trang_thai_goc
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["goi_y"])


if __name__ == "__main__":
    unittest.main()
