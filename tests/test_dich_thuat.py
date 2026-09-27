"""Dịch mọi ngôn ngữ Google hỗ trợ: Google Cloud Translation, dự phòng bằng mô hình trên máy."""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import dich_thuat
from api import app


class NhanDienTests(unittest.TestCase):
    def test_bon_ngon_ngu(self):
        self.assertEqual(dich_thuat.nhan_dien("学校は生徒の安全を守ります。"), "ja")
        self.assertEqual(dich_thuat.nhan_dien("학교는 학생의 안전을 책임집니다."), "ko")
        self.assertEqual(dich_thuat.nhan_dien("Giáo viên chủ nhiệm"), "vi")
        self.assertEqual(dich_thuat.nhan_dien("giao vien chu nhiem cua lop la nguoi"), "vi")
        self.assertEqual(dich_thuat.nhan_dien("Homeroom teachers support students."), "en")

    def test_ngon_ngu_ngoai_bon_ngon_ngu_cu(self):
        self.assertEqual(dich_thuat.nhan_dien("学校负责学生的安全。"), "zh-CN")
        self.assertEqual(dich_thuat.nhan_dien("Школа отвечает за безопасность."), "ru")
        self.assertEqual(dich_thuat.nhan_dien("Школа відповідає за їхню безпеку."), "uk")
        self.assertEqual(dich_thuat.nhan_dien("โรงเรียนดูแลความปลอดภัย"), "th")
        self.assertEqual(dich_thuat.nhan_dien("المدرسة مسؤولة عن السلامة"), "ar")
        self.assertEqual(dich_thuat.nhan_dien("विद्यालय सुरक्षा के लिए जिम्मेदार है"), "hi")
        self.assertEqual(dich_thuat.nhan_dien("Bonjour, ça va ? L'école est pour les élèves."), "fr")
        self.assertEqual(dich_thuat.nhan_dien("La escuela es muy segura para los niños."), "es")
        self.assertEqual(dich_thuat.nhan_dien("Die Schule ist nicht weit von der Stadt."), "de")
        # à, é... có cả ở tiếng Pháp nên "Xin chào" phải nhận ra nhờ từ.
        self.assertEqual(dich_thuat.nhan_dien("Xin chào"), "vi")

    def test_ma_ngon_ngu_va_bi_danh_cua_google(self):
        self.assertGreater(len(dich_thuat.NGON_NGU), 130)
        self.assertEqual(dich_thuat.chuan_hoa_ma("zh-cn"), "zh-CN")
        self.assertEqual(dich_thuat.chuan_hoa_ma("iw"), "he")
        self.assertEqual(dich_thuat.chuan_hoa_ma("zh"), "zh-CN")
        self.assertEqual(dich_thuat.chuan_hoa_ma("xx"), "")
        self.assertEqual(dich_thuat.chuan_hoa_yeu_cau("Bonjour", "FR", "sw"), ("Bonjour", "fr", "sw"))

    def test_bao_truoc_khi_mo_hinh_nho_khong_thao(self):
        self.assertEqual(dich_thuat.canh_bao_mo_hinh_nho("vi", "fr"), "")
        self.assertIn("tiếng Swahili", dich_thuat.canh_bao_mo_hinh_nho("vi", "sw"))

    def test_cap_khong_co_tieng_anh_di_qua_tieng_anh(self):
        self.assertEqual(dich_thuat.cac_chang("vi", "ja"), [("vi", "en"), ("en", "ja")])
        self.assertEqual(dich_thuat.cac_chang("ko", "en"), [("ko", "en")])
        self.assertEqual(dich_thuat.cac_chang("en", "en"), [])

    def test_loc_chu_han_lot_vao_tieng_viet(self):
        self.assertEqual(dich_thuat._loc_ban_dich("Nhà trường负 có trách nhiệm", "vi"), "Nhà trường có trách nhiệm")
        self.assertEqual(dich_thuat._loc_ban_dich("学校", "ja"), "学校")
        self.assertEqual(dich_thuat._loc_ban_dich("学校", "zh-CN"), "学校")
        self.assertEqual(dich_thuat._loc_ban_dich("L'école负", "fr"), "L'école")

    def test_kiem_tra_yeu_cau(self):
        with self.assertRaises(dich_thuat.LoiDich):
            dich_thuat.chuan_hoa_yeu_cau("  ", "tu_dong", "en")
        with self.assertRaises(dich_thuat.LoiDich):
            dich_thuat.chuan_hoa_yeu_cau("xin chào", "tu_dong", "xx")
        with self.assertRaises(dich_thuat.LoiDich):
            dich_thuat.chuan_hoa_yeu_cau("a" * 5001, "tu_dong", "en")


def _su_kien(phan_hoi):
    return [json.loads(dong) for dong in phan_hoi.text.splitlines() if dong.strip()]


class ApiDichTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_google_khi_co_khoa(self):
        gia = MagicMock(status_code=200)
        gia.json.return_value = {"data": {"translations": [
            {"translatedText": "学校は安全です。", "detectedSourceLanguage": "vi"}]}}
        with patch.dict(os.environ, {"RAG_GOOGLE_TRANSLATE_KEY": "khoa-thu"}), \
             patch("dich_thuat.requests.post", return_value=gia) as goi:
            su_kien = _su_kien(self.client.post("/api/dich", json={"van_ban": "Trường học an toàn.", "dich_sang": "ja"}))
        self.assertEqual(goi.call_args.kwargs["data"]["target"], "ja")
        self.assertNotIn("source", goi.call_args.kwargs["data"])  # để Google tự nhận
        self.assertEqual(su_kien[0], {"type": "ngon_ngu", "nguon": "vi", "dich_sang": "ja", "cong_cu": "google"})
        self.assertEqual(su_kien[1]["content"], "学校は安全です。")
        self.assertEqual(su_kien[-1]["type"], "done")

    def test_google_loi_thi_dung_may_chu_va_bao_ly_do(self):
        loi = MagicMock(status_code=403)
        loi.json.return_value = {"error": {"message": "API has not been used"}}
        with patch.dict(os.environ, {"RAG_GOOGLE_TRANSLATE_KEY": "khoa-thu"}), \
             patch("dich_thuat.requests.post", return_value=loi), \
             patch("dich_thuat._goi_ollama", return_value=iter(["Hello"])), \
             patch("api._chon_mo_hinh_dich", return_value="qwen2.5:3b-instruct"):
            su_kien = _su_kien(self.client.post("/api/dich", json={"van_ban": "Xin chào", "dich_sang": "en"}))
        self.assertEqual(su_kien[0]["cong_cu"], "cuc_bo")
        canh_bao = next(s for s in su_kien if s["type"] == "warning")["message"]
        self.assertIn("Cloud Translation API", canh_bao)
        self.assertEqual("".join(s["content"] for s in su_kien if s["type"] == "token"), "Hello")

    def test_cuc_bo_hai_chang_chi_phat_chang_cuoi(self):
        def gia_ollama(van_ban, tu, sang, mo_hinh):
            return iter(["School is safe."] if sang == "en" else ["学校は", "安全です。"])
        with patch.dict(os.environ, {"RAG_GOOGLE_TRANSLATE_KEY": ""}), \
             patch("dich_thuat._goi_ollama", side_effect=gia_ollama) as goi, \
             patch("api._chon_mo_hinh_dich", return_value="qwen2.5:3b-instruct"):
            su_kien = _su_kien(self.client.post(
                "/api/dich", json={"van_ban": "Trường học an toàn.", "nguon": "tu_dong", "dich_sang": "ja"}))
        self.assertEqual(su_kien[0]["nguon"], "vi")
        self.assertEqual(goi.call_args_list[1].args[0], "School is safe.")
        self.assertEqual("".join(s["content"] for s in su_kien if s["type"] == "token"), "学校は安全です。")
        self.assertTrue(any(s["type"] == "phase" for s in su_kien))

    def test_cau_hinh_bao_van_ban_co_roi_may_chu(self):
        with patch.dict(os.environ, {"RAG_GOOGLE_TRANSLATE_KEY": ""}):
            cau_hinh = self.client.get("/api/dich/cau-hinh").json()
        self.assertEqual(cau_hinh["cong_cu"], "cuc_bo")
        self.assertIn({"ma": "fr", "ten": "Tiếng Pháp", "ten_goc": "Français"}, cau_hinh["ngon_ngu"])
        with patch.dict(os.environ, {"RAG_GOOGLE_TRANSLATE_KEY": "k"}):
            self.assertEqual(self.client.get("/api/dich/cau-hinh").json()["cong_cu"], "google")

    def test_cuc_bo_ngon_ngu_yeu_co_canh_bao(self):
        with patch.dict(os.environ, {"RAG_GOOGLE_TRANSLATE_KEY": ""}),              patch("dich_thuat._goi_ollama", return_value=iter(["Habari"])),              patch("api._chon_mo_hinh_dich", return_value="qwen2.5:3b-instruct"):
            su_kien = _su_kien(self.client.post("/api/dich", json={"van_ban": "Hello", "dich_sang": "sw"}))
        self.assertEqual(su_kien[0]["dich_sang"], "sw")
        self.assertIn("tiếng Swahili", next(s for s in su_kien if s["type"] == "warning")["message"])
        self.assertEqual("".join(s["content"] for s in su_kien if s["type"] == "token"), "Habari")

    def test_ngon_ngu_khong_ho_tro_bi_tu_choi(self):
        self.assertEqual(self.client.post("/api/dich", json={"van_ban": "Hello", "dich_sang": "xx"}).status_code, 400)
