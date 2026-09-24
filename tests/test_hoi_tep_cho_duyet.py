"""Người gửi tệp phải hỏi được về tệp của mình dù quản trị viên chưa duyệt.

Hai chỗ từng làm hỏng điều đó:
  - Duyệt tệp (hay bất cứ thay đổi nào của kho) hẹn một lượt cập nhật chỉ mục;
    lượt đó giữ khoá sinh câu trả lời nhiều phút và /api/chat/stream trả 503
    cho MỌI câu hỏi, kể cả câu về tệp đính kèm vốn không cần chỉ mục.
  - Tệp đính kèm chỉ nằm trong RAM, cả máy chủ giữ 12 tệp: quản trị viên bận
    vài ngày thì tệp đã bị tệp của người khác đẩy ra, hoặc mất khi khởi động lại.
"""

import threading
import time
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import tep_dinh_kem
from api import app
from rag_service import service

NOI_DUNG = (
    "Bài 2. Gõ bàn phím đúng cách. Khi gõ phím, em đặt hai ngón trỏ lên hai phím "
    "F và J có gạch nổi. Các ngón còn lại đặt trên hàng phím cơ sở."
).encode("utf-8")


def cho_san_sang(kho, tep_id, giay=20.0):
    het = time.monotonic() + giay
    while time.monotonic() < het:
        tep = kho.lay(tep_id)
        if tep is not None and tep.trang_thai != "dang_xu_ly":
            return tep
        time.sleep(0.05)
    return kho.lay(tep_id)


class LuuTepRaDiaTests(unittest.TestCase):
    def setUp(self):
        tep_dinh_kem.dat_hook_luu_kho(lambda *_: ("cho_duyet", "Chờ duyệt"))
        self.addCleanup(tep_dinh_kem.dat_hook_luu_kho, None)

    def test_khoi_dong_lai_van_hoi_duoc_tep_dang_cho_duyet(self):
        kho = tep_dinh_kem.KhoTepDinhKem()
        tep = cho_san_sang(kho, kho.them("ban-phim.txt", NOI_DUNG, nguoi={"id": "hs1"}).id)
        self.assertEqual(tep.trang_thai, "san_sang")
        self.assertEqual(tep.luu_kho, "cho_duyet")

        kho_moi = tep_dinh_kem.KhoTepDinhKem()  # như máy chủ vừa khởi động lại
        self.assertEqual(kho_moi.nap_lai_tu_dia(), 1)
        tep_nap = kho_moi.lay_san_sang(tep.id)
        self.assertEqual(tep_nap.luu_kho, "cho_duyet")
        self.assertEqual(tep_nap.nguoi, {"id": "hs1"})
        doan = kho_moi.truy_hoi(tep_nap, "đặt ngón trỏ lên phím nào", 2)
        self.assertTrue(doan)
        self.assertIn("F và J", doan[0].page_content)

    def test_tep_cua_nguoi_khac_khong_day_tep_cho_duyet_ra_sau_vai_luot(self):
        kho = tep_dinh_kem.KhoTepDinhKem()
        dau_tien = kho.them("dau-tien.txt", NOI_DUNG).id
        cho_san_sang(kho, dau_tien)
        for i in range(15):
            cho_san_sang(kho, kho.them(f"khac-{i}.txt", NOI_DUNG + str(i).encode()).id)
        self.assertIsNotNone(kho.lay(dau_tien))

    def test_tep_qua_han_bi_don_ca_ban_ghi(self):
        kho = tep_dinh_kem.KhoTepDinhKem()
        tep = cho_san_sang(kho, kho.them("cu.txt", NOI_DUNG).id)
        tep.tao_luc -= (tep_dinh_kem.NGAY_GIU_TEP + 1) * 86400
        kho._ghi_ra_dia(tep)

        kho_moi = tep_dinh_kem.KhoTepDinhKem()
        kho_moi.nap_lai_tu_dia()
        self.assertIsNone(kho_moi.lay(tep.id))
        self.assertFalse(tep_dinh_kem.os.path.exists(tep.duong_dan))
        self.assertFalse(tep_dinh_kem.os.path.exists(kho._duong_dan_ban_ghi(tep.id)))

    def test_bo_tep_thi_xoa_luon_ban_ghi(self):
        kho = tep_dinh_kem.KhoTepDinhKem()
        tep = cho_san_sang(kho, kho.them("bo.txt", NOI_DUNG).id)
        self.assertTrue(kho.xoa(tep.id))
        self.assertEqual(tep_dinh_kem.KhoTepDinhKem().nap_lai_tu_dia(), 0)


def tra_loi_gia(question, history, tep_ids, pham_vi, **_):
    yield {"type": "token", "content": "ok"}
    yield {"type": "done", "elapsed_seconds": 0.1}


class HoiTepKhiKhoDangCapNhatTests(unittest.TestCase):
    def setUp(self):
        self.state_cu, self.chain_cu = service.status.state, service.rag_chain
        service.status.state = "updating"
        service.rag_chain = object()  # chuỗi của lần nạp trước vẫn còn
        self.addCleanup(setattr, service, "rag_chain", self.chain_cu)
        self.addCleanup(setattr, service.status, "state", self.state_cu)
        gia = patch.object(service, "stream_answer", tra_loi_gia)
        gia.start()
        self.addCleanup(gia.stop)

    def test_cau_hoi_ve_tep_van_duoc_tra_loi(self):
        with TestClient(app) as client:
            phan_hoi = client.post(
                "/api/chat/stream", json={"question": "tệp nói gì", "tep_ids": ["abc"]}
            )
            self.assertEqual(phan_hoi.status_code, 200)
            self.assertTrue(client.get("/api/status").json()["hoi_tep_duoc"])

    def test_cau_hoi_ca_kho_van_phai_doi(self):
        with TestClient(app) as client:
            phan_hoi = client.post("/api/chat/stream", json={"question": "học phí"})
            self.assertEqual(phan_hoi.status_code, 503)

    def test_may_chu_vua_bat_chua_co_chuoi_thi_doi(self):
        service.status.state = "loading"
        service.rag_chain = None
        with TestClient(app) as client:
            phan_hoi = client.post(
                "/api/chat/stream", json={"question": "tệp nói gì", "tep_ids": ["abc"]}
            )
            self.assertEqual(phan_hoi.status_code, 503)


class LuotSinhTepTests(unittest.TestCase):
    """Khoá sinh bị lượt cập nhật giữ thì câu hỏi về tệp dùng khoá phụ."""

    def setUp(self):
        self.state_cu = service.status.state
        self.addCleanup(setattr, service.status, "state", self.state_cu)

    def test_khong_doi_luot_cap_nhat_chi_muc(self):
        service.status.state = "updating"
        with service._generation_lock:  # lượt cập nhật đang giữ
            xong = threading.Event()

            def hoi():
                with service._luot_sinh_tep():
                    xong.set()

            threading.Thread(target=hoi, daemon=True).start()
            self.assertTrue(xong.wait(5))

    def test_luc_san_sang_van_xep_hang_sau_cau_dang_tra_loi(self):
        service.status.state = "ready"
        xong = threading.Event()

        def hoi():
            with service._luot_sinh_tep():
                xong.set()

        with service._generation_lock:  # một câu khác đang sinh
            threading.Thread(target=hoi, daemon=True).start()
            self.assertFalse(xong.wait(1.5))
        self.assertTrue(xong.wait(5))


class KhongTuCapNhatBanNgayTests(unittest.TestCase):
    """VPS đặt RAG_TU_NAP_CHI_MUC=0: duyệt tệp xong không được khoá chat cả máy
    giữa ban ngày; tệp chờ lượt cập nhật ban đêm."""

    def setUp(self):
        gia = patch.dict("os.environ", {"RAG_TU_NAP_CHI_MUC": "0"})
        gia.start()
        self.addCleanup(gia.stop)
        self.cho_cu = list(service.tep_cho_nap)
        self.addCleanup(setattr, service, "tep_cho_nap", self.cho_cu)

    def test_duyet_tep_khong_hen_cap_nhat_chi_muc(self):
        with patch.object(service, "start_index_update") as cap_nhat, \
                patch("rag_service.threading.Thread") as luong:
            service.tep_cho_nap.append("de-thi.pdf")
            service._hen_cap_nhat_chi_muc()
        luong.assert_not_called()
        cap_nhat.assert_not_called()
        trang_thai = service.status_dict()
        self.assertFalse(trang_thai["tu_nap_chi_muc"])
        self.assertGreaterEqual(trang_thai["tep_cho_nap"], 1)

    def test_mac_dinh_van_tu_cap_nhat_nhu_cu(self):
        with patch.dict("os.environ", {"RAG_TU_NAP_CHI_MUC": "1"}), \
                patch("rag_service.threading.Thread") as luong:
            service._dang_hen_nap = False
            service._hen_cap_nhat_chi_muc()
        luong.assert_called_once()
        service._dang_hen_nap = False


if __name__ == "__main__":
    unittest.main()
