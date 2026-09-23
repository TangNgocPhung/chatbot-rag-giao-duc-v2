"""Hỏi về đoạn vừa khoanh trong trình đọc tài liệu.

Người dùng khoanh "Căn cứ Luật Giáo dục số 43/2019/QH14..." rồi bấm Giải thích.
Ba chỗ nối dễ hỏng lặng lẽ:
  - Đoạn khoanh phải là bằng chứng số 1, nếu không mô hình chỉ thấy các đoạn
    truy hồi được và đáp "không tìm thấy" cho chữ người dùng đang nhìn thấy.
  - Câu có "43/2019" không được rẽ sang công cụ tính như một phép chia.
  - Bộ chặn lạc đề không được chặn đoạn người dùng tự chỉ ra.
"""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api import app
from rag_service import RAGService, doan_khoanh_thanh_bang_chung, service

DOAN = {
    "van_ban": "Căn cứ Luật Giáo dục số 43/2019/QH14 được sửa đổi, bổ sung bởi Luật số 123/2025/QH15;",
    "ten": "159-ndcp.signed.pdf",
    "trang": 1,
}


class BangChungTests(unittest.TestCase):
    def test_doan_nguon_trong_kho(self):
        doc = doan_khoanh_thanh_bang_chung(DOAN)
        self.assertEqual(doc.page_content, DOAN["van_ban"])
        self.assertEqual(doc.metadata["source_file"], "159-ndcp.signed.pdf")
        self.assertEqual(doc.metadata["so_trang"], 1)
        self.assertNotIn("source_url", doc.metadata)

    def test_doan_tep_dinh_kem_tro_ve_tep(self):
        doc = doan_khoanh_thanh_bang_chung({**DOAN, "tep": "abc123"})
        self.assertEqual(doc.metadata["source_url"], "/api/tep/abc123/noi-dung")
        self.assertEqual(doc.metadata["tep_dinh_kem"], "abc123")

    def test_doan_rong_bo_qua(self):
        self.assertIsNone(doan_khoanh_thanh_bang_chung(None))
        self.assertIsNone(doan_khoanh_thanh_bang_chung({"van_ban": "  "}))


class TraLoiDoanKhoanhTests(unittest.TestCase):
    def setUp(self):
        self.service = RAGService()
        self.service.status.state = "ready"
        self.service.format_docs = lambda docs: "\n".join(d.page_content for d in docs)
        self.service.rag_chain = MagicMock()
        self.service.rag_chain.stream.return_value = iter(["Tôi không tìm thấy."])
        # Prompt tra cứu cấm kiến thức ngoài nên hay đáp "không tìm thấy" cho
        # yêu cầu giải thích; hỏi về đoạn khoanh phải đi prompt giải thích.
        self.service.chain_giai_thich = MagicMock()
        self.service.chain_giai_thich.stream.return_value = iter(["Đoạn này nêu căn cứ [1]."])
        self.lac_de = Document(page_content="Quy chế tuyển sinh.", metadata={"source_file": "khac.pdf"})

    def test_doan_khoanh_la_bang_chung_so_mot_va_khong_bi_chan(self):
        cau_hoi = f'Giải thích đoạn sau: "{DOAN["van_ban"]}"'
        with patch.object(self.service, "_retrieve", return_value=[self.lac_de]), \
             patch("kiem_tra_tra_loi.ly_do_bo_qua", return_value="lac_de") as chan:
            su_kien = list(self.service._sinh_cau_tra_loi(cau_hoi, doan_trich=DOAN))
        chan.assert_not_called()
        nguon = next(s for s in su_kien if s["type"] == "sources")["sources"]
        self.assertEqual(nguon[0]["name"], "159-ndcp.signed.pdf")
        self.assertEqual(nguon[1]["name"], "khac.pdf")
        self.service.rag_chain.stream.assert_not_called()
        ngu_canh = self.service.chain_giai_thich.stream.call_args[0][0]["context"]
        self.assertTrue(ngu_canh.startswith(DOAN["van_ban"]))
        self.assertNotIn("cong_cu", su_kien[-1])

    def test_so_hieu_van_ban_khong_thanh_phep_chia(self):
        with patch.object(self.service, "_retrieve", return_value=[]):
            su_kien = list(self.service._sinh_cau_tra_loi("43/2019", doan_trich=DOAN))
        self.assertNotIn("cong_cu", su_kien[-1])
        self.assertTrue(self.service.chain_giai_thich.stream.called)


class ApiDoanKhoanhTests(unittest.TestCase):
    def setUp(self):
        self.trang_thai_cu = service.status.state
        service.status.state = "ready"
        self.client = TestClient(app)

    def tearDown(self):
        service.status.state = self.trang_thai_cu

    def test_chuyen_doan_trich_toi_dich_vu(self):
        su_kien = iter([{"type": "done", "elapsed_seconds": 0.1}])
        with patch.object(service, "stream_answer", return_value=su_kien) as stream:
            phan_hoi = self.client.post(
                "/api/chat/stream", json={"question": "Giải thích đoạn này", "doan_trich": DOAN},
            )
        self.assertEqual(phan_hoi.status_code, 200)
        stream.assert_called_once_with(
            "Giải thích đoạn này", [], [], {}, doan_trich={**DOAN, "tep": None},
        )

    def test_doan_trich_rong_bi_tu_choi(self):
        phan_hoi = self.client.post(
            "/api/chat/stream",
            json={"question": "Giải thích đoạn này", "doan_trich": {"van_ban": ""}},
        )
        self.assertEqual(phan_hoi.status_code, 422)


class ChainThuongTests(unittest.TestCase):
    def test_cau_hoi_thuong_van_dung_prompt_tra_cuu(self):
        dich_vu = RAGService()
        dich_vu.rag_chain, dich_vu.chain_giai_thich = object(), object()
        self.assertIs(dich_vu._chain_tra_loi(None), dich_vu.rag_chain)
        self.assertIs(dich_vu._chain_tra_loi(doan_khoanh_thanh_bang_chung(DOAN)), dich_vu.chain_giai_thich)


if __name__ == "__main__":
    unittest.main()
