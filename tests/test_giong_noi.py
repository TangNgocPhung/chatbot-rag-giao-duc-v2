"""Nói thay vì gõ: ghi âm -> chữ bằng faster-whisper, tự nhận ngôn ngữ."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import giong_noi
from api import app


def _mo_hinh_gia(chu, ngon_ngu="vi", thoi_luong=4.0):
    mo_hinh = MagicMock()
    mo_hinh.transcribe.return_value = (
        iter([SimpleNamespace(text=f" {c} ") for c in chu]),
        SimpleNamespace(language=ngon_ngu, language_probability=0.987, duration=thoi_luong),
    )
    return mo_hinh


class NhanDienGiongNoiTests(unittest.TestCase):
    def test_tu_nhan_ngon_ngu_va_ghep_cac_doan(self):
        mo_hinh = _mo_hinh_gia(["Quy định về", "an toàn trường học?"], "vi")
        with patch("media_transcribe._tai_model", return_value=mo_hinh):
            ket_qua = giong_noi.nhan_dien_giong_noi(b"webm" * 500)
        self.assertEqual(ket_qua["van_ban"], "Quy định về an toàn trường học?")
        self.assertEqual((ket_qua["ngon_ngu"], ket_qua["ten_ngon_ngu"]), ("vi", "Tiếng Việt"))
        self.assertEqual(ket_qua["do_tin_cay"], 0.99)
        self.assertIsNone(mo_hinh.transcribe.call_args.kwargs["language"])

    def test_ten_ngon_ngu(self):
        self.assertEqual(giong_noi.ten_ngon_ngu("ja"), "Tiếng Nhật")
        self.assertEqual(giong_noi.ten_ngon_ngu("zh"), "Tiếng Trung")
        self.assertEqual(giong_noi.ten_ngon_ngu("yue"), "yue")  # Whisper có, Google không

    def test_im_lang_thi_bao_khong_nghe_ro(self):
        with patch("media_transcribe._tai_model", return_value=_mo_hinh_gia([])):
            with self.assertRaisesRegex(giong_noi.LoiGiongNoi, "Không nghe rõ"):
                giong_noi.nhan_dien_giong_noi(b"webm" * 500)

    def test_qua_dai_bi_tu_choi(self):
        with patch("media_transcribe._tai_model", return_value=_mo_hinh_gia(["a"], thoi_luong=500)):
            with self.assertRaisesRegex(giong_noi.LoiGiongNoi, "dài quá"):
                giong_noi.nhan_dien_giong_noi(b"webm" * 500)
        with self.assertRaises(giong_noi.LoiGiongNoi):
            giong_noi.nhan_dien_giong_noi(b"")


class ApiGiongNoiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_can_tieu_de_chong_gui_gia(self):
        self.assertEqual(self.client.post("/api/giong-noi", content=b"abc").status_code, 403)

    def test_tra_ve_chu_va_ngon_ngu(self):
        with patch("media_transcribe._tai_model", return_value=_mo_hinh_gia(["Hello school"], "en")):
            phan_hoi = self.client.post(
                "/api/giong-noi", content=b"webm" * 500,
                headers={"X-RAG-Action": "voice-input", "Content-Type": "audio/webm"},
            )
        self.assertEqual(phan_hoi.status_code, 200)
        self.assertEqual(phan_hoi.json()["van_ban"], "Hello school")
        self.assertEqual(phan_hoi.json()["ten_ngon_ngu"], "Tiếng Anh")

    def test_loi_nhan_dien_thanh_400(self):
        with patch("media_transcribe._tai_model", return_value=_mo_hinh_gia([])):
            phan_hoi = self.client.post(
                "/api/giong-noi", content=b"webm" * 500, headers={"X-RAG-Action": "voice-input"},
            )
        self.assertEqual(phan_hoi.status_code, 400)
        self.assertIn("Không nghe rõ", phan_hoi.json()["detail"])
