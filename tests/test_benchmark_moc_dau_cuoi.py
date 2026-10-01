"""
Chạy benchmark_moc_thoi_gian ĐẦU CUỐI trên một kho tổng hợp nhỏ.

Các test khác của benchmark dùng dịch vụ giả; ở đây là RAGService thật với
chỉ mục FAISS thật, BM25 thật, và hồ sơ / đồ thị quan hệ dựng bằng đúng các
hàm khởi tạo của dịch vụ (_lap_ho_so_van_ban, _lap_phan_loai). Chỉ thay mô hình
nhúng bằng embedding giả tất định vì máy chạy test không có Ollama - nên thứ
hạng theo ngữ nghĩa ở đây vô nghĩa, test chỉ kiểm chỗ NỐI giữa các khâu, không
kiểm chất lượng xếp hạng.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

import benchmark_moc_thoi_gian as bm
import hieu_luc_bo_sung
import phan_loai_giao_duc
import quan_he_van_ban
import tu_vung_kho
import van_ban_meta
from hybrid_retrieval import xay_dung_bm25
from rag_service import RAGService

DAU = "BỘ GIÁO DỤC VÀ ĐÀO TẠO\nSố: {so} Hà Nội, {ngay}\nTHÔNG TƯ\nCăn cứ Luật Giáo dục;\n"
KHO = {
    "tt28-2009.pdf": [
        DAU.format(so="28/2009/TT-BGDĐT", ngay="ngày 21 tháng 10 năm 2009")
        + "Quy định chế độ làm việc đối với giáo viên phổ thông.",
        "Điều 6. Định mức tiết dạy. Định mức tiết dạy của giáo viên trung học cơ sở "
        "là 19 tiết mỗi tuần, giáo viên trung học phổ thông là 17 tiết mỗi tuần.",
    ],
    "tt05-2025.pdf": [
        DAU.format(so="05/2025/TT-BGDĐT", ngay="ngày 07 tháng 02 năm 2025")
        + "Quy định chế độ làm việc đối với giáo viên phổ thông, dự bị đại học.",
        "Điều 5. Định mức tiết dạy. Định mức tiết dạy của giáo viên trung học cơ sở "
        "là 19 tiết mỗi tuần, giáo viên trung học phổ thông là 17 tiết mỗi tuần.",
        "Điều 13. Hiệu lực thi hành\n1. Thông tư này có hiệu lực thi hành kể từ ngày "
        "24 tháng 3 năm 2025.\n2. Thông tư số 28/2009/TT-BGDĐT ngày 21 tháng 10 năm 2009 "
        "hết hiệu lực kể từ ngày Thông tư này có hiệu lực thi hành.",
    ],
}
CAP = {"dinh_muc": {
    "cu": "28/2009/TT-BGDĐT", "moi": "5/2025/TT-BGDĐT",
    "moi_co_hieu_luc": "2025-03-24", "da_doi_chieu": False,
}}


class BenchmarkDauCuoiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tam = tempfile.TemporaryDirectory(prefix="rag-moc-")
        tam = cls._tam.name
        # Dựng hồ sơ ghi ra mấy tệp JSON cạnh mã nguồn; chuyển hết sang thư mục
        # tạm để test không ghi đè dữ liệu thật của kho.
        cls._cac_patch = [
            patch.object(van_ban_meta, "DUONG_DAN_HO_SO", os.path.join(tam, "ho_so.json")),
            patch.object(van_ban_meta, "DUONG_DAN_META_LLM", os.path.join(tam, "khong_co.json")),
            patch.object(hieu_luc_bo_sung, "DUONG_DAN_TINH_TRANG", os.path.join(tam, "tt.json")),
            patch.object(phan_loai_giao_duc, "DUONG_DAN_PHAN_LOAI", os.path.join(tam, "pl.json")),
            patch.object(quan_he_van_ban.SoQuanHe, "luu", lambda self, *a, **k: None),
        ]
        for p in cls._cac_patch:
            p.start()

        cac_doan = [
            Document(page_content=noi_dung, metadata={"source_file": ten_file, "_chunk_key": f"{ten_file}#{i}"})
            for ten_file, cac_phan in KHO.items() for i, noi_dung in enumerate(cac_phan)
        ]
        service = RAGService()
        service.vector_store = FAISS.from_documents(cac_doan, DeterministicFakeEmbedding(size=64))
        service._lap_ho_so_van_ban()
        service._lap_phan_loai()
        service.bm25_retriever = xay_dung_bm25(service.vector_store)
        service.tu_vung = tu_vung_kho.xay_dung_tu_vung(service.bm25_retriever.docs)
        cls.service = service

    @classmethod
    def tearDownClass(cls):
        for p in cls._cac_patch:
            p.stop()
        cls._tam.cleanup()

    def test_do_thi_nhan_ra_dieu_khoan_thi_hanh(self):
        cd = bm.chan_doan_cap(self.service, CAP)[0]
        self.assertEqual(cd["tep_cu"], ["tt28-2009.pdf"])
        self.assertEqual(cd["tep_moi"], ["tt05-2025.pdf"])
        self.assertEqual(cd["quan_he_nhan_ra"], ["thay_the"])
        self.assertEqual(cd["moi_bat_dau"], "2025-03-24")

    def test_ba_nhanh_chay_tren_dich_vu_that(self):
        kq = bm.chay_mot_cau(self.service, {
            "cau_hoi": "Năm 2020, định mức tiết dạy của giáo viên trung học cơ sở là bao nhiêu tiết?",
            "cap": "dinh_muc", "loai": "truoc_thay_the", "che_do_mong_doi": "lich_su",
            "so_hieu_dung": ["28/2009/TT-BGDĐT"], "so_hieu_sai": ["5/2025/TT-BGDĐT"],
        }, 24)
        self.assertEqual(kq.bo_qua, "")
        self.assertTrue(kq.nhan_moc_dung, kq.che_do_nhan_ra)
        for che_do in bm.CHE_DO:
            self.assertEqual(kq.ket_qua[che_do].loi, "", che_do)
        # Ép hiện hành: Thông tư 28/2009 đã hết hiệu lực nên bị lọc khỏi rổ.
        self.assertNotIn("tt28-2009.pdf", kq.ket_qua["tat_moc"].tai_lieu_xep_hang)
        # Chế độ lịch sử mở lại văn bản cũ.
        self.assertIn("tt28-2009.pdf", kq.ket_qua["bat_moc"].tai_lieu_xep_hang)
        # Hạ bậc chỉ trừ điểm văn bản ngoài mốc, nên văn bản đúng mốc không thể
        # tụt hạng so với nhánh không hạ bậc.
        self.assertLessEqual(kq.ket_qua["ha_bac"].hang_dung, kq.ket_qua["bat_moc"].hang_dung)
        self.assertTrue(kq.ket_qua["ha_bac"].dung_phien_ban)
        # Biến môi trường của nhánh hạ bậc không rò ra ngoài lượt đo.
        self.assertNotEqual(os.environ.get("RAG_HA_BAC_NGOAI_MOC"), "1")
        self.assertNotEqual(os.environ.get("RAG_NOI_RO_KHI_LOC_HIEU_LUC"), "1")
        # Kho nhỏ, bộ lọc không bỏ ứng viên dense nào: nới rổ phải ra y hệt bật mốc.
        self.assertEqual(kq.ket_qua["noi_ro"].tai_lieu_xep_hang, kq.ket_qua["bat_moc"].tai_lieu_xep_hang)

    def test_cau_hien_hanh_ra_van_ban_moi(self):
        kq = bm.chay_mot_cau(self.service, {
            "cau_hoi": "Định mức tiết dạy của giáo viên trung học cơ sở là bao nhiêu tiết?",
            "cap": "dinh_muc", "loai": "sau_thay_the", "che_do_mong_doi": "hien_hanh",
            "so_hieu_dung": ["5/2025/TT-BGDĐT"], "so_hieu_sai": ["28/2009/TT-BGDĐT"],
        }, 24)
        self.assertTrue(kq.nhan_moc_dung)
        for che_do in bm.CHE_DO:
            self.assertTrue(kq.ket_qua[che_do].dung_phien_ban, che_do)
        # Câu hiện hành nên bộ lọc hiệu lực chạy thật; kho chỉ 5 đoạn, ít hơn rổ
        # 15 ứng viên, nên nới rổ không có gì để lấp: phải ra y hệt bật mốc.
        self.assertNotIn("tt28-2009.pdf", kq.ket_qua["noi_ro"].tai_lieu_xep_hang)
        self.assertEqual(kq.ket_qua["noi_ro"].tai_lieu_xep_hang, kq.ket_qua["bat_moc"].tai_lieu_xep_hang)

    def test_du_lieu_that_khong_bi_ghi_de(self):
        self.assertTrue(van_ban_meta.DUONG_DAN_HO_SO.startswith(self._tam.name))


if __name__ == "__main__":
    unittest.main()
