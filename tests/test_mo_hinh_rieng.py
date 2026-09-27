"""Mỗi người tự chọn mô hình trả lời, không đổi mô hình của người khác."""

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from rag_service import RAGService, service

CO_SAN = {"models": [{"name": "llama3.2:3b"}, {"name": "qwen2.5:3b-instruct"}, {"name": "qwen3.5:9b"}]}


class ChonMoHinhTests(unittest.TestCase):
    def setUp(self):
        self.dich_vu = RAGService()
        self.dich_vu.llm_model = "llama3.2:3b"
        gia = patch.object(self.dich_vu, "danh_sach_model", return_value=CO_SAN)
        gia.start()
        self.addCleanup(gia.stop)

    def test_bo_trong_hoac_la_thi_dung_mac_dinh(self):
        self.assertEqual(self.dich_vu.chon_mo_hinh(None), "llama3.2:3b")
        self.assertEqual(self.dich_vu.chon_mo_hinh("khong-co:1b"), "llama3.2:3b")
        self.assertEqual(self.dich_vu.chon_mo_hinh("qwen2.5:3b-instruct"), "qwen2.5:3b-instruct")

    def test_quan_tri_gioi_han_duoc_mo_hinh_cho_chon(self):
        with patch.dict(os.environ, {"RAG_MO_HINH_CHO_PHEP": "qwen2.5:3b-instruct"}):
            self.assertEqual(self.dich_vu.chon_mo_hinh("qwen3.5:9b"), "llama3.2:3b")
            self.assertEqual(self.dich_vu.chon_mo_hinh("qwen2.5:3b-instruct"), "qwen2.5:3b-instruct")

    def test_chuoi_rieng_dung_dung_mo_hinh_va_duoc_nho(self):
        self.dich_vu.rag_chain = "chuoi-mac-dinh"
        with patch("rag_service.tao_llm", side_effect=lambda ten, **_: f"llm:{ten}") as tao, \
             patch("rag_service.tao_rag_chain", side_effect=lambda vs, llm: (f"rag:{llm}", None)), \
             patch("rag_service.tao_chain_giai_thich", side_effect=lambda llm: f"giai-thich:{llm}"), \
             patch("rag_service.tao_chain_tom_tat", side_effect=lambda llm: f"tom-tat:{llm}"):
            self.assertEqual(self.dich_vu._chain_tra_loi(None, "qwen2.5:3b-instruct"), "rag:llm:qwen2.5:3b-instruct")
            self.assertEqual(self.dich_vu._chain_tra_loi(None, "qwen2.5:3b-instruct"), "rag:llm:qwen2.5:3b-instruct")
            self.assertEqual(self.dich_vu._chain_tra_loi(None, "llama3.2:3b"), "chuoi-mac-dinh")
            self.assertEqual(self.dich_vu._chain_tra_loi(None, None), "chuoi-mac-dinh")
        # Lần thứ hai lấy từ nhớ đệm: chỉ dựng LLM hỏi đáp + LLM tóm tắt một lần.
        self.assertEqual(tao.call_count, 2)

    def test_danh_sach_an_mo_hinh_bi_chan(self):
        with patch.dict(os.environ, {"RAG_MO_HINH_CHO_PHEP": "qwen2.5:3b-instruct"}), \
             patch("rag_service.requests.get") as goi:
            goi.return_value.json.return_value = CO_SAN
            dich_vu = RAGService()
            dich_vu.llm_model = "llama3.2:3b"
            ten = [m["name"] for m in dich_vu.danh_sach_model()["models"]]
        self.assertEqual(ten, ["llama3.2:3b", "qwen2.5:3b-instruct"])


class ApiMoHinhTests(unittest.TestCase):
    def setUp(self):
        self.trang_thai = service.status.state
        service.status.state = "ready"
        self.client = TestClient(app)

    def tearDown(self):
        service.status.state = self.trang_thai

    def test_chuyen_mo_hinh_nguoi_dung_chon(self):
        su_kien = iter([{"type": "done", "elapsed_seconds": 0.1}])
        with patch.object(service, "stream_answer", return_value=su_kien) as stream:
            self.client.post("/api/chat/stream", json={"question": "Câu hỏi", "model": "qwen2.5:3b-instruct"}).read()
        stream.assert_called_once_with("Câu hỏi", [], [], {}, model="qwen2.5:3b-instruct")

    def test_nguoi_thuong_khong_doi_duoc_mac_dinh_cua_may_chu(self):
        with patch.dict(os.environ, {"RAG_KHOA_QUAN_TRI": "1"}):
            phan_hoi = self.client.post(
                "/api/model", json={"model": "qwen2.5:3b-instruct"}, headers={"X-RAG-Action": "switch-model"}
            )
        self.assertEqual(phan_hoi.status_code, 401)
