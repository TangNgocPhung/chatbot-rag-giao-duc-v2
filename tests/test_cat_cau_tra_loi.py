"""Câu trả lời bị Ollama cắt vì hết num_predict (lỗi 6/10: dừng ở "Cuốn sách
cung"): phải rút về ý trọn vẹn cuối cùng và báo là đã rút gọn."""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

import lich_su_chat
from api import app
from kiem_tra_tra_loi import GHI_CHU_BI_CAT, cat_ve_y_tron_ven
from rag_service import service

CLIENT = {"X-RAG-Client": "trinh-duyet-test"}

CAU_BI_CAT = (
    "Sách hướng dẫn giảng dạy chuyên đề Tin học 10 [1].\n\n"
    "**Chi tiết:**\n\n"
    "- **Cơ sở pháp lý:** Theo Thông tư 32/2018/TT-BGDĐT [2].\n"
    "- **Đối tượng:** Học sinh định hướng Khoa học máy tính [3]\n"
    "- **Mục đích sử dụng sách:** Cuốn sách cung"
)


class CatVeYTronVenTests(unittest.TestCase):
    def test_bo_y_dang_do_giu_cac_y_truoc(self):
        ket_qua = cat_ve_y_tron_ven(CAU_BI_CAT)
        self.assertNotIn("Cuốn sách cung", ket_qua)
        self.assertNotIn("Mục đích sử dụng sách", ket_qua)
        self.assertIn("Khoa học máy tính [3]", ket_qua)
        self.assertTrue(ket_qua.endswith(GHI_CHU_BI_CAT))

    def test_giu_cau_tron_ven_trong_y_dang_do(self):
        ket_qua = cat_ve_y_tron_ven("- **Hạn:** Nộp trước 30/6 [1]. Sau đó thì")
        self.assertTrue(ket_qua.startswith("- **Hạn:** Nộp trước 30/6 [1]." + GHI_CHU_BI_CAT[:2]))

    def test_bo_tieu_de_va_so_thu_tu_treo(self):
        ket_qua = cat_ve_y_tron_ven("Kết luận [1].\n\n**Các bước:**\n\n1. Bước một [1].\n2. Bước hai đang")
        self.assertEqual(ket_qua, "Kết luận [1].\n\n**Các bước:**\n\n1. Bước một [1]." + GHI_CHU_BI_CAT)
        ket_qua = cat_ve_y_tron_ven("Kết luận [1].\n\n**Các bước:**\n\n1. Bước")
        self.assertEqual(ket_qua, "Kết luận [1]." + GHI_CHU_BI_CAT)

    def test_giu_cau_dung_truoc_loi_dan_treo(self):
        ket_qua = cat_ve_y_tron_ven("Có ba mức [1]. Cụ thể như sau:\n\n1")
        self.assertEqual(ket_qua, "Có ba mức [1]." + GHI_CHU_BI_CAT)

    def test_dau_cham_trong_so_tien_khong_phai_het_cau(self):
        ket_qua = cat_ve_y_tron_ven("Mức lương 2.340.000 đồng theo Nghị định 73/2024 và còn")
        self.assertTrue(ket_qua.startswith("Mức lương 2.340.000 đồng theo Nghị định 73/2024 và còn…"))

    def test_dong_in_dam_bi_cat_ngang(self):
        ket_qua = cat_ve_y_tron_ven("**Giáo viên được nghỉ hè 8 tuần [1]. Ngoài ra còn")
        self.assertTrue(ket_qua.startswith("**Giáo viên được nghỉ hè 8 tuần [1].**"))


class DocDoneReasonTests(unittest.TestCase):
    def setUp(self):
        service.huy_sinh.clear()

    def test_bo_str_output_parser_de_doc_metadata(self):
        chuoi = (
            ChatPromptTemplate.from_template("{question}")
            | RunnableLambda(lambda x: x)
            | StrOutputParser()
        )
        da_bo = service._bo_bo_doc_chuoi(chuoi)
        self.assertNotIsInstance(da_bo.steps[-1], StrOutputParser)
        self.assertEqual(len(da_bo.steps), 2)

    def test_phat_chu_va_ghi_done_reason(self):
        class ChuoiBiCat:
            def astream(self, _dau_vao):
                async def phat():
                    for manh in (
                        AIMessageChunk(content="Cuốn sách"),
                        AIMessageChunk(content=" cung"),
                        AIMessageChunk(content="", response_metadata={"done_reason": "length"}),
                    ):
                        await asyncio.sleep(0)
                        yield manh
                return phat()

        ket_thuc: dict = {}
        chu = "".join(service._phat_token(ChuoiBiCat(), {}, ket_thuc))
        self.assertEqual(chu, "Cuốn sách cung")
        self.assertEqual(ket_thuc, {"done_reason": "length"})


class LichSuGhiBanRutGonTests(unittest.TestCase):
    def setUp(self):
        self.thu_muc = tempfile.TemporaryDirectory()
        self.patcher = patch.object(
            lich_su_chat, "DUONG_DAN_DB", os.path.join(self.thu_muc.name, "api.db")
        )
        self.patcher.start()
        lich_su_chat.dong_ket_noi()
        self.client = TestClient(app)
        service.status.state = "ready"

    def tearDown(self):
        lich_su_chat.dong_ket_noi()
        self.patcher.stop()
        self.thu_muc.cleanup()

    def test_lich_su_luu_ban_da_cat(self):
        rut_gon = cat_ve_y_tron_ven(CAU_BI_CAT)

        def su_kien():
            yield {"type": "sources", "sources": []}
            yield {"type": "token", "content": CAU_BI_CAT}
            yield {"type": "thay_cau_tra_loi", "content": rut_gon}
            yield {"type": "done", "elapsed_seconds": 1.0, "citations_ok": True, "figures_ok": True}

        with patch.object(service, "stream_answer", return_value=su_kien()):
            self.client.post("/api/chat/stream", json={"question": "Sách Tin 10?"}, headers=CLIENT)
        ma = self.client.get("/api/hoi-thoai", headers=CLIENT).json()["hoi_thoai"][0]["id"]
        luot = self.client.get(f"/api/hoi-thoai/{ma}", headers=CLIENT).json()["luot"][0]
        self.assertEqual(luot["tra_loi"], rut_gon)


if __name__ == "__main__":
    unittest.main()
