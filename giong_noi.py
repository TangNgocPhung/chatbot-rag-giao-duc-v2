"""
NHẬP CÂU HỎI BẰNG GIỌNG NÓI
===========================
Trình duyệt ghi âm (MediaRecorder, thường là webm/opus) rồi gửi byte về đây;
faster-whisper - cùng mô hình đang dùng phiên âm video - chuyển thành chữ và
tự nhận ra người dùng nói tiếng gì. Âm thanh không rời máy chủ, khác với
Web Speech API của Chrome/Edge (gửi lên máy chủ Google/Microsoft và bắt chọn
trước ngôn ngữ).
"""

from __future__ import annotations

import io
import os
import threading
import time

import dich_thuat
import media_transcribe

BYTE_TOI_DA = 10 * 1024 * 1024  # 60 giây webm/opus chỉ vài trăm KB
GIAY_TOI_DA = 120

# Mô hình Whisper chạy CPU; hai người nói cùng lúc thì lần lượt, tránh hết RAM.
_khoa = threading.Lock()


class LoiGiongNoi(ValueError):
    pass


def ten_ngon_ngu(ma_whisper: str) -> str:
    # Whisper chỉ báo "zh" và hay viết chữ phồn thể, nên không ghi "Giản thể".
    if ma_whisper == "zh":
        return "Tiếng Trung"
    ma = dich_thuat.chuan_hoa_ma(ma_whisper)
    if ma:
        ten = dich_thuat.TEN_VIET[ma]
        return ten[0].upper() + ten[1:]
    return ma_whisper


def nhan_dien_giong_noi(du_lieu: bytes) -> dict:
    """Trả về chữ nghe được, mã ngôn ngữ Whisper nhận ra và tên tiếng Việt."""
    if not du_lieu:
        raise LoiGiongNoi("Chưa ghi được âm thanh nào.")
    if len(du_lieu) > BYTE_TOI_DA:
        raise LoiGiongNoi("Đoạn ghi âm quá dài, hãy nói ngắn hơn.")
    bat_dau = time.perf_counter()
    with _khoa:
        model = media_transcribe._tai_model(media_transcribe.MODEL_MAC_DINH)
        try:
            cac_doan, thong_tin = model.transcribe(
                io.BytesIO(du_lieu),
                language=None,                    # để Whisper tự nhận ngôn ngữ
                vad_filter=True,                  # bỏ khoảng lặng, đỡ bịa chữ khi im
                vad_parameters={"min_silence_duration_ms": 500},
                beam_size=int(os.getenv("RAG_WHISPER_BEAM_GIONG_NOI", "5")),
                condition_on_previous_text=False,
                without_timestamps=True,
            )
            if float(getattr(thong_tin, "duration", 0) or 0) > GIAY_TOI_DA:
                raise LoiGiongNoi(f"Đoạn ghi âm dài quá {GIAY_TOI_DA} giây, hãy nói ngắn hơn.")
            van_ban = " ".join((d.text or "").strip() for d in cac_doan).strip()
        except LoiGiongNoi:
            raise
        except Exception as exc:  # PyAV không giải mã được: tệp hỏng, định dạng lạ
            raise LoiGiongNoi(f"Không đọc được đoạn ghi âm: {exc}") from exc
    if not van_ban:
        raise LoiGiongNoi("Không nghe rõ lời nói, hãy nói gần micro hơn và thử lại.")
    ma = getattr(thong_tin, "language", "") or ""
    return {
        "van_ban": van_ban,
        "ngon_ngu": ma,
        "ten_ngon_ngu": ten_ngon_ngu(ma),
        "do_tin_cay": round(float(getattr(thong_tin, "language_probability", 0) or 0), 2),
        "giay": round(time.perf_counter() - bat_dau, 1),
    }
