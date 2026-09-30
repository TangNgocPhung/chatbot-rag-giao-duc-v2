"""Bộ câu hỏi và cách chấm của benchmark_moc_thoi_gian (không cần chỉ mục)."""

import json
import os
import unittest
from datetime import date

from langchain_core.documents import Document

import benchmark_moc_thoi_gian as bm
import hieu_luc_bo_sung as hl
import quan_he_van_ban as qh
import van_ban_meta as vm

HOM_NAY = date(2026, 9, 30)


def nap_bo():
    with open(bm.DUONG_DAN_BO, encoding="utf-8") as tep:
        return json.load(tep)


class KhoaSoHieuTests(unittest.TestCase):
    def test_bo_so_0_dau_va_phan_co_quan(self):
        self.assertEqual(bm.khoa_so_hieu("05/2025/TT-BGDĐT"), "5/2025/tt")
        self.assertEqual(bm.khoa_so_hieu("5/2025/TT-BGDDT"), "5/2025/tt")
        self.assertEqual(bm.khoa_so_hieu("23/2015/TTLT-BGDĐT-BNV"), "23/2015/ttlt")
        self.assertEqual(bm.khoa_so_hieu("43/2019/QH14"), "43/2019/qh14")
        self.assertEqual(bm.khoa_so_hieu("527/QĐ-TTg"), "527/qđ")

    def test_khac_loai_van_ban_thi_khac_khoa(self):
        self.assertNotEqual(bm.khoa_so_hieu("28/2009/TT-BGDĐT"), bm.khoa_so_hieu("28/2009/NĐ-CP"))

    def test_tim_file_theo_so_hieu(self):
        ho_so = {
            "a.pdf": vm.HoSoVanBan("a.pdf", so_hieu="5/2025/TT-BGDĐT"),
            "b.pdf": vm.HoSoVanBan("b.pdf", so_hieu="5/2025/NĐ-CP"),
            "c.docx": vm.HoSoVanBan("c.docx"),
        }
        self.assertEqual(bm.tep_theo_so_hieu(ho_so, "05/2025/TT-BGDĐT"), ["a.pdf"])
        self.assertEqual(bm.tep_theo_so_hieu(ho_so, "9/2025/TT-BGDĐT"), [])

    def test_tim_file_qua_do_thi_quan_he(self):
        # Số hiệu chỉ có trong tên tệp vẫn tra được nhờ đồ thị của quan_he_van_ban.
        ho_so = {"Thông-tư-05-2025-TT-BGDĐT.pdf": vm.HoSoVanBan(
            "Thông-tư-05-2025-TT-BGDĐT.pdf", so_hieu="5/2025/TT-BGDĐT")}
        so = qh.SoQuanHe(ho_so, {}, so_tay={})
        self.assertEqual(
            bm.tep_theo_so_hieu({}, "05/2025/TT-BGDĐT", so), ["Thông-tư-05-2025-TT-BGDĐT.pdf"]
        )


class ChamTests(unittest.TestCase):
    DUNG = {"28/2009/TT-BGDĐT": ["cu.pdf"]}
    SAI = {"5/2025/TT-BGDĐT": ["moi.pdf"]}

    def test_ban_dung_xep_truoc(self):
        r = bm.cham(["cu.pdf", "cu.pdf", "moi.pdf", "x.pdf"], self.DUNG, self.SAI, 2)
        self.assertEqual((r.hang_dung, r.hang_sai, r.dung_phien_ban), (1, 2, True))
        self.assertTrue(r.dung_trong_cua_so)
        self.assertFalse(r.sai_trong_cua_so)

    def test_ban_sai_xep_truoc(self):
        r = bm.cham(["moi.pdf", "cu.pdf"], self.DUNG, self.SAI, 4)
        self.assertFalse(r.dung_phien_ban)
        self.assertTrue(r.sai_trong_cua_so)

    def test_chi_mot_ban_duoc_truy_hoi(self):
        self.assertTrue(bm.cham(["x.pdf", "cu.pdf"], self.DUNG, self.SAI).dung_phien_ban)
        self.assertFalse(bm.cham(["moi.pdf"], self.DUNG, self.SAI).dung_phien_ban)
        self.assertIsNone(bm.cham(["x.pdf"], self.DUNG, self.SAI).dung_phien_ban)

    def test_cau_so_sanh_can_du_hai_ban_trong_cua_so(self):
        hai_ban = {"a": ["cu.pdf"], "b": ["moi.pdf"]}
        self.assertTrue(bm.cham(["moi.pdf", "cu.pdf"], hai_ban, {}, 4).dung_trong_cua_so)
        self.assertFalse(bm.cham(["moi.pdf", "x.pdf", "cu.pdf"], hai_ban, {}, 2).dung_trong_cua_so)

    def test_mcnemar_chinh_xac(self):
        self.assertEqual(bm.mcnemar_chinh_xac(0, 0), 1.0)
        self.assertAlmostEqual(bm.mcnemar_chinh_xac(5, 0), 0.0625)
        self.assertAlmostEqual(bm.mcnemar_chinh_xac(6, 0), 0.03125)
        self.assertEqual(bm.mcnemar_chinh_xac(3, 3), 1.0)


class DichVuGia:
    """
    Chỉ mục giả, chọn chế độ đúng cách rag_service._retrieve của thật: gọi
    quan_he_van_ban.che_do_thoi_gian và đọc RAG_HA_BAC_NGOAI_MOC. Hiện hành thì
    văn bản cũ bị lọc bỏ; lịch sử thì văn bản mới vẫn đứng đầu (không phạt gì),
    trừ khi bật hạ bậc ngoài mốc.
    """

    def __init__(self):
        self.ho_so_van_ban = {
            "cu.pdf": vm.HoSoVanBan("cu.pdf", so_hieu="28/2009/TT-BGDĐT",
                                    ngay_ban_hanh="2009-10-21"),
            "moi.pdf": vm.HoSoVanBan("moi.pdf", so_hieu="5/2025/TT-BGDĐT",
                                     ngay_ban_hanh="2025-02-07", thay_the=["28/2009/TT-BGDĐT"]),
        }
        self.tinh_trang_hieu_luc = {
            "moi.pdf": hl.TinhTrangThoiGian("moi.pdf", ngay_hieu_luc="2025-03-24"),
        }
        self.so_quan_he = qh.SoQuanHe(self.ho_so_van_ban, self.tinh_trang_hieu_luc, so_tay={})

    def _retrieve(self, cau_hoi, so_ket_qua=None):
        che_do, _ = qh.che_do_thoi_gian(cau_hoi)
        if che_do != "lich_su":
            thu_tu = ["moi.pdf"]
        elif os.environ.get("RAG_HA_BAC_NGOAI_MOC") == "1":
            thu_tu = ["cu.pdf", "moi.pdf"]
        else:
            thu_tu = ["moi.pdf", "cu.pdf"]
        return [Document(page_content="x", metadata={"source_file": t}) for t in thu_tu]


class ChayMotCauTests(unittest.TestCase):
    def test_do_a_b_tren_cung_cau(self):
        kq = bm.chay_mot_cau(DichVuGia(), {
            "cau_hoi": "Năm 2020 giáo viên THCS dạy mấy tiết?", "cap": "dinh_muc",
            "loai": "truoc_thay_the", "che_do_mong_doi": "lich_su",
            "so_hieu_dung": ["28/2009/TT-BGDĐT"], "so_hieu_sai": ["5/2025/TT-BGDĐT"],
        }, 24)
        self.assertTrue(kq.nhan_moc_dung)
        # Tắt mốc: văn bản cũ bị lọc; bật mốc: vào rổ nhưng xếp sau; hạ bậc: lên đầu.
        self.assertFalse(kq.ket_qua["tat_moc"].dung_phien_ban)
        self.assertEqual(kq.ket_qua["bat_moc"].hang_dung, 2)
        self.assertTrue(kq.ket_qua["ha_bac"].dung_phien_ban)
        tong = bm.tong_hop([kq])
        self.assertEqual(tong["so_sanh"]["bat_moc->ha_bac"]["tot_len"], 1)
        self.assertEqual(tong["ha_bac"]["hit@1"], 1)
        self.assertEqual(tong["bat_moc"]["mrr@10"], 0.5)
        # Biến môi trường được trả lại sau lượt đo.
        self.assertNotEqual(os.environ.get("RAG_HA_BAC_NGOAI_MOC"), "1")
        # Lượt tắt mốc xong thì che_do_thoi_gian thật được trả lại.
        self.assertEqual(qh.che_do_thoi_gian("Năm 2020 thì sao?")[0], "lich_su")

    def test_chan_doan_cap(self):
        cd = bm.chan_doan_cap(DichVuGia(), {"dinh_muc": {
            "cu": "28/2009/TT-BGDĐT", "moi": "5/2025/TT-BGDĐT", "moi_co_hieu_luc": "2025-03-24",
        }})[0]
        self.assertEqual(cd["quan_he_nhan_ra"], ["thay_the"])
        self.assertEqual((cd["tep_cu"], cd["tep_moi"]), (["cu.pdf"], ["moi.pdf"]))
        self.assertEqual(cd["moi_bat_dau"], "2025-03-24")
        self.assertFalse(cd["da_doi_chieu"])

    def test_cap_da_doi_chieu_khop_so_quan_he_nhap_tay(self):
        # Cặp gắn da_doi_chieu phải thật sự có trong sổ nhập tay, đúng chiều
        # "mới thay thế cũ" - không thì cờ này chỉ là lời tự nhận.
        so_tay = qh.tai_so_tay()
        canh = {(q["tu"], q["loai"], q["den"]) for q in so_tay.get("quan_he", [])}
        for ten, cap in nap_bo()["cap_van_ban"].items():
            if cap.get("da_doi_chieu"):
                with self.subTest(cap=ten):
                    self.assertIn((cap["moi"], "thay_the", cap["cu"]), canh)
                    ngay = so_tay["van_ban"].get(cap["moi"], {}).get("ngay_hieu_luc")
                    # Ngày ghi trong bộ câu hỏi phải lấy từ sổ, không tự đặt.
                    self.assertEqual(ngay, cap["moi_co_hieu_luc"])

    def test_van_ban_chua_co_trong_kho_thi_bo_qua(self):
        kq = bm.chay_mot_cau(DichVuGia(), {
            "cau_hoi": "Năm 2020 dạy thêm thế nào?", "cap": "day_them",
            "loai": "truoc_thay_the", "so_hieu_dung": ["17/2012/TT-BGDĐT"],
        }, 24)
        self.assertIn("17/2012/TT-BGDĐT", kq.bo_qua)
        self.assertEqual(bm.tong_hop([kq])["so_cau"], 0)

    def test_luot_loi_khong_lam_lech_cap(self):
        dung = bm.KetQuaMoc("a", "c", "l", "lich_su", nhan_moc_dung=True,
                            tep_dung={"x": ["cu.pdf"]}, tep_sai={"y": ["moi.pdf"]})
        dung.ket_qua = {
            "tat_moc": bm.DoMotCheDo(loi="Lỗi"),
            "bat_moc": bm.cham(["cu.pdf"], dung.tep_dung, dung.tep_sai),
            "ha_bac": bm.cham(["cu.pdf"], dung.tep_dung, dung.tep_sai),
        }
        sai = bm.KetQuaMoc("b", "c", "l", "lich_su", nhan_moc_dung=True,
                           tep_dung={"x": ["cu.pdf"]}, tep_sai={})
        sai.ket_qua = {
            che_do: bm.cham(["moi.pdf"], sai.tep_dung, sai.tep_sai) for che_do in bm.CHE_DO
        }
        tong = bm.tong_hop([dung, sai])
        # Câu thứ hai không có bản sai trong kho nên không tính "đúng phiên bản".
        self.assertEqual(tong["bat_moc"]["so_cau_co_cap"], 1)
        self.assertEqual(tong["tat_moc"]["so_cau_co_cap"], 0)


class BoCauHoiTests(unittest.TestCase):
    """Bộ câu hỏi phải tự nhất quán: sửa quan_he_van_ban mà làm lệch nhãn thì
    test này hỏng trước khi số liệu sai lọt vào báo cáo."""

    def setUp(self):
        self.bo = nap_bo()
        self.cap = self.bo["cap_van_ban"]

    def test_nhan_thuoc_dung_cap(self):
        for muc in self.bo["cau_hoi"]:
            with self.subTest(cau_hoi=muc["cau_hoi"]):
                cap = self.cap[muc["cap"]]
                nhan = set(muc["so_hieu_dung"]) | set(muc["so_hieu_sai"])
                self.assertLessEqual(nhan, {cap["cu"], cap["moi"]})
                self.assertFalse(set(muc["so_hieu_dung"]) & set(muc["so_hieu_sai"]))

    def test_nhan_dung_dang_so_hieu_cua_he_thong(self):
        # Nhãn phải viết đúng dạng chuẩn hoá mà van_ban_meta sinh ra.
        for cap in self.cap.values():
            for so_hieu in (cap["cu"], cap["moi"]):
                with self.subTest(so_hieu=so_hieu):
                    self.assertEqual(qh.chuan_so_hieu(so_hieu), so_hieu)

    def test_moc_nam_dung_phia_ngay_chuyen_giao(self):
        for muc in self.bo["cau_hoi"]:
            with self.subTest(cau_hoi=muc["cau_hoi"]):
                che_do, thoi_diem = qh.che_do_thoi_gian(muc["cau_hoi"], HOM_NAY)
                self.assertEqual(che_do, muc["che_do_mong_doi"])
                cap = self.cap[muc["cap"]]
                if cap["moi_co_hieu_luc"]:
                    som_nhat = muon_nhat = date.fromisoformat(cap["moi_co_hieu_luc"])
                else:
                    # Sổ chưa ghi ngày: văn bản không thể có hiệu lực trước năm
                    # ban hành, và thực tế luôn có hiệu lực trong năm đó hoặc
                    # đầu năm sau - nên mốc phải tránh xa cả khoảng này.
                    nam = int(cap["moi"].split("/")[1])
                    som_nhat, muon_nhat = date(nam, 1, 1), date(nam + 1, 1, 1)
                if muc["loai"] in ("truoc_thay_the", "so_sanh"):
                    self.assertLess(thoi_diem, som_nhat)
                elif muc["loai"] == "sau_thay_the" and thoi_diem:
                    self.assertGreaterEqual(thoi_diem, muon_nhat)
                # Văn bản đúng phải là văn bản đang hiệu lực tại mốc đó.
                if muc["loai"] in ("truoc_thay_the", "truoc_khi_co"):
                    self.assertEqual(muc["so_hieu_dung"], [cap["cu"]])
                elif muc["loai"] in ("sau_thay_the", "nam_trong_ten"):
                    self.assertEqual(muc["so_hieu_dung"], [cap["moi"]])


if __name__ == "__main__":
    unittest.main()
