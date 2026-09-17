"""FastAPI phục vụ giao diện web và API streaming cho Chatbot RAG Giáo dục."""

from __future__ import annotations

import json
import queue
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import bao_ve_truy_cap
import cache_ngu_nghia
import lich_su_chat
import phan_loai_giao_duc
from rag_service import service
from tep_dinh_kem import GIOI_HAN_BYTE, LoiTepDinhKem, kho_tep


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    history: list["ChatMessage"] = Field(default_factory=list, max_length=8)
    # Có tệp đính kèm thì trả lời trong phạm vi các tệp đó thay vì cả kho.
    tep_ids: list[str] = Field(default_factory=list, max_length=4)
    # Hội thoại đang tiếp tục; bỏ trống thì máy chủ tạo hội thoại mới.
    hoi_thoai_id: str | None = Field(default=None, max_length=64)
    # Giới hạn truy xuất theo môn/cấp học/lớp/loại nội dung. Bỏ trống = cả kho.
    # Giá trị lạ bị chuan_hoa_pham_vi loại bỏ chứ không làm hỏng request.
    pham_vi: dict = Field(default_factory=dict)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 2:
            raise ValueError("Câu hỏi quá ngắn.")
        return value


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Nội dung hội thoại không được để trống.")
        return value


ChatRequest.model_rebuild()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Kiểm ngay lúc khởi động: bật chế độ công khai mà thiếu mật khẩu thì dừng
    # hẳn, đừng để đường hầm mở ra rồi mới phát hiện cửa không khóa.
    bao_ve_truy_cap.kiem_tra_cau_hinh()
    threading.Thread(
        target=service.initialize, daemon=True, name="rag-initialize"
    ).start()
    yield


app = FastAPI(
    title="Chatbot RAG Giáo dục",
    version="1.4.0",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)

# Gắn trước mọi route, kể cả StaticFiles cuối tệp: đặt mật khẩu là chặn tất.
bao_ve_truy_cap.gan_vao(app)


@app.get("/api/status")
def get_status():
    return service.status_dict()


@app.get("/api/documents")
def get_documents():
    return service.document_inventory()


@app.get("/api/bo-loc")
def bo_loc_pham_vi():
    """Các lựa chọn phạm vi kèm số tài liệu, để giao diện dựng hộp chọn."""
    return service.bo_loc_phan_loai()


@app.get("/api/goi-y")
def goi_y_mo_dau(so_luong: int = 6):
    """Câu hỏi gợi ý cho màn hình chào; mỗi lần gọi trả một mẻ khác nhau."""
    return {"goi_y": service.goi_y_mo_dau(so_luong)}


@app.post("/api/reinitialize")
def reinitialize():
    if service.status.state == "loading":
        return service.status_dict()
    threading.Thread(
        target=lambda: service.initialize(force=True),
        daemon=True,
        name="rag-reinitialize",
    ).start()
    return {"state": "loading", "message": "Đang thử kết nối lại..."}


@app.post("/api/index/update")
def update_index(x_rag_action: str | None = Header(default=None)):
    if x_rag_action != "update-index":
        raise HTTPException(status_code=403, detail="Yêu cầu cập nhật không hợp lệ.")
    started, message = service.start_index_update()
    if not started:
        raise HTTPException(status_code=409, detail=message)
    return service.status_dict()


class ModelRequest(BaseModel):
    model: str = Field(min_length=1, max_length=120)


@app.get("/api/models")
def danh_sach_model():
    """Danh sách model Ollama có trên máy để giao diện cho người dùng chọn."""
    return service.danh_sach_model()


@app.post("/api/model")
def doi_model(request: ModelRequest, x_rag_action: str | None = Header(default=None)):
    if x_rag_action != "switch-model":
        raise HTTPException(status_code=403, detail="Yêu cầu đổi model không hợp lệ.")
    thanh_cong, thong_bao = service.doi_model(request.model)
    if not thanh_cong:
        raise HTTPException(status_code=409, detail=thong_bao)
    return {"model": service.llm_model, "message": thong_bao}


@app.post("/api/drive/sync")
def dong_bo_drive(x_rag_action: str | None = Header(default=None)):
    """Kéo tài liệu mới từ thư mục Drive dùng chung rồi tự cập nhật chỉ mục."""
    if x_rag_action != "drive-sync":
        raise HTTPException(status_code=403, detail="Yêu cầu đồng bộ không hợp lệ.")
    started, message = service.start_drive_sync()
    if not started:
        raise HTTPException(status_code=409, detail=message)
    return service.drive_dict()


# Câu trả lời được sinh trong một luồng riêng, nối với luồng phát HTTP bằng
# hàng chờ, chứ không sinh thẳng trong luồng phát. Lý do rất cụ thể: khi người
# dùng bấm "Cuộc trò chuyện mới", bấm dừng hay đóng tab, trình duyệt chỉ cắt
# kết nối. Bộ sinh nằm trong luồng phát sẽ treo lại vĩnh viễn ở đúng chỗ yield
# dở dang, không ai gọi tiếp và cũng không ai đóng nó, nên khối "with khoá sinh
# câu trả lời" không bao giờ thoát: máy chủ báo "đang xử lý một câu hỏi" mãi và
# mọi câu hỏi sau đều xếp hàng sau một câu chẳng còn ai đọc. Luồng riêng thì tự
# chạy tiếp, tự phát hiện bên nhận đã đi, tự đóng bộ sinh và nhả khoá.
SO_SU_KIEN_CHO = 64          # đủ đệm cho mạng chậm, không đủ để sinh hết một câu
GIAY_CHO_BEN_NHAN = 20.0     # hàng chờ đầy lâu hơn thế coi như bên nhận đã đi
_HET_SU_KIEN = object()


def _xep_hang(hang: queue.Queue, su_kien) -> bool:
    """Đưa sự kiện vào hàng chờ; False nghĩa là thôi sinh tiếp."""
    han = time.monotonic() + GIAY_CHO_BEN_NHAN
    while True:
        if service.huy_sinh.is_set():
            return False
        try:
            hang.put(su_kien, timeout=0.5)
            return True
        except queue.Full:
            # Hàng đầy nghĩa là bên nhận không lấy nữa. Chờ có hạn rồi bỏ, để
            # tab đã đóng không giữ khoá thêm một câu trả lời nữa.
            if time.monotonic() >= han:
                return False


@app.post("/api/chat/dung")
def chat_dung():
    """Xin dừng câu trả lời đang sinh dở.

    Máy chủ chỉ giữ một lượt sinh tại một thời điểm nên lời xin dừng cũng chung
    cho cả máy: mở hai tab cùng hỏi thì tab này bấm dừng sẽ dừng câu của tab kia.
    Chấp nhận được với một máy chủ mỗi lần chỉ trả lời được một câu.
    """
    return {"dung": service.yeu_cau_dung()}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest, x_rag_client: str | None = Header(default=None)):
    if service.status.state != "ready":
        raise HTTPException(status_code=503, detail=service.status.message)

    history = [message.model_dump() for message in request.history]
    hang: queue.Queue = queue.Queue(maxsize=SO_SU_KIEN_CHO)

    def sinh_va_ghi():
        # Gom lại trong lúc phát để ghi vào lịch sử sau khi xong. Ghi ở cuối chứ
        # không ghi dần từng token: một lượt hỏi là một dòng, không phải hàng
        # nghìn lần cập nhật. Việc gom nằm trong luồng sinh chứ không nằm bên
        # luồng phát, nhờ vậy câu bị dừng giữa chừng vẫn được ghi lại - phần đã
        # trả lời được cũng là dữ liệu đáng xem khi phân tích.
        cau_tra_loi = ""
        cac_nguon: list = []
        thong_tin = {"giay": 0.0, "trich_dan_ok": True, "so_lieu_ok": True,
                     "tu_choi": False, "tu_cache": False}
        bo_sinh = service.stream_answer(
            request.question, history, request.tep_ids, request.pham_vi
        )
        try:
            for event in bo_sinh:
                loai = event.get("type")
                if loai == "token":
                    cau_tra_loi += event.get("content", "")
                elif loai == "sources":
                    cac_nguon = event.get("sources", [])
                elif loai == "done":
                    thong_tin["giay"] = event.get("elapsed_seconds") or 0.0
                    thong_tin["trich_dan_ok"] = event.get("citations_ok", True)
                    thong_tin["so_lieu_ok"] = event.get("figures_ok", True)
                    thong_tin["tu_choi"] = bool(event.get("abstained"))
                    thong_tin["tu_cache"] = bool(event.get("tu_cache"))
                if not _xep_hang(hang, event):
                    break
        except Exception as exc:
            _xep_hang(hang, {"type": "error", "message": str(exc)})
        finally:
            # Đóng tay ngay trong luồng vừa lặp nó: lúc này bộ sinh đang treo ở
            # một yield chứ không đang chạy, nên close() vào được, khối "with
            # khoá" thoát và khoá sinh câu trả lời chắc chắn được nhả.
            # getattr vì test thay stream_answer bằng iterator thường, không
            # phải bộ sinh; bản thật luôn có close().
            dong = getattr(bo_sinh, "close", None)
            if dong is not None:
                dong()
            if cau_tra_loi.strip():
                lich_su_chat.ghi_luot(
                    client_id=x_rag_client or "",
                    cau_hoi=request.question,
                    tra_loi=cau_tra_loi,
                    hoi_thoai_id=request.hoi_thoai_id,
                    nguon=[n.get("name") for n in cac_nguon],
                    model=service.llm_model,
                    giay=thong_tin["giay"],
                    trich_dan_ok=thong_tin["trich_dan_ok"],
                    so_lieu_ok=thong_tin["so_lieu_ok"],
                    tu_choi=thong_tin["tu_choi"],
                    tu_cache=thong_tin["tu_cache"],
                )
            # Báo hết dòng sau khi đã ghi lịch sử: giao diện đọc xong dòng là
            # gọi ngay danh sách hội thoại, báo sớm thì lượt vừa rồi chưa kịp
            # nằm trong danh sách đó.
            try:
                hang.put_nowait(_HET_SU_KIEN)
            except queue.Full:
                pass  # bên nhận không lấy nữa thì cũng không cần báo hết

    def generate():
        luong = threading.Thread(
            target=sinh_va_ghi, name="sinh-cau-tra-loi", daemon=True
        )
        luong.start()
        while True:
            try:
                su_kien = hang.get(timeout=1.0)
            except queue.Empty:
                # Khoảng lặng dài là bình thường (truy hồi, token đầu tiên trên
                # CPU). Chỉ dừng khi luồng sinh đã chết mà hàng chờ cũng cạn.
                if luong.is_alive():
                    continue
                break
            if su_kien is _HET_SU_KIEN:
                break
            yield json.dumps(su_kien, ensure_ascii=False) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# LỊCH SỬ HỘI THOẠI PHÍA MÁY CHỦ
# ============================================================
# X-RAG-Client chỉ là chuỗi ngẫu nhiên do trình duyệt sinh, KHÔNG phải xác thực.
# Nó gom hội thoại theo trình duyệt cho tới khi có đăng nhập thật; đừng dùng nó
# để bảo vệ dữ liệu nhạy cảm.
def _client_id(header: str | None) -> str:
    ma = (header or "").strip()
    if not ma:
        raise HTTPException(status_code=400, detail="Thiếu mã trình duyệt.")
    return ma[:64]


@app.get("/api/hoi-thoai")
def liet_ke_hoi_thoai(
    x_rag_client: str | None = Header(default=None), gioi_han: int = 50
):
    return {"hoi_thoai": lich_su_chat.danh_sach_hoi_thoai(_client_id(x_rag_client), gioi_han)}


@app.get("/api/hoi-thoai/{hoi_thoai_id}")
def xem_hoi_thoai(hoi_thoai_id: str, x_rag_client: str | None = Header(default=None)):
    chi_tiet = lich_su_chat.chi_tiet_hoi_thoai(hoi_thoai_id)
    if chi_tiet is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    if chi_tiet.get("client_id") != _client_id(x_rag_client):
        # Không phải bảo mật thật (mã trình duyệt giả được), nhưng đủ để hai
        # người dùng chung máy chủ không vô tình thấy hội thoại của nhau.
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    return chi_tiet


@app.delete("/api/hoi-thoai/{hoi_thoai_id}")
def xoa_hoi_thoai(hoi_thoai_id: str, x_rag_client: str | None = Header(default=None)):
    chi_tiet = lich_su_chat.chi_tiet_hoi_thoai(hoi_thoai_id)
    if chi_tiet is None or chi_tiet.get("client_id") != _client_id(x_rag_client):
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    lich_su_chat.xoa_hoi_thoai(hoi_thoai_id)
    return {"da_xoa": hoi_thoai_id}


@app.delete("/api/hoi-thoai")
def xoa_toan_bo_hoi_thoai(x_rag_client: str | None = Header(default=None)):
    so = lich_su_chat.xoa_theo_client(_client_id(x_rag_client))
    return {"da_xoa": so}


@app.get("/api/thong-ke")
def thong_ke_su_dung(so_ngay: int = 30):
    """Người dùng hỏi gì, câu nào chậm, câu nào bị từ chối - dữ liệu để biết
    nên cải tiến chỗ nào thay vì đoán."""
    return {
        **lich_su_chat.thong_ke(so_ngay),
        "cache": cache_ngu_nghia.cache.thong_ke(),
    }


@app.delete("/api/cache")
def xoa_cache(x_rag_action: str | None = Header(default=None)):
    if x_rag_action != "clear-cache":
        raise HTTPException(status_code=403, detail="Yêu cầu xóa cache không hợp lệ.")
    return {"da_xoa": cache_ngu_nghia.cache.xoa_het()}


@app.post("/api/tep")
async def tai_len_tep(
    request: Request,
    ten: str,
    x_rag_action: str | None = Header(default=None),
):
    """Nhận thẳng byte của tệp trong body (không cần python-multipart)."""
    if x_rag_action != "upload-file":
        raise HTTPException(status_code=403, detail="Yêu cầu tải tệp không hợp lệ.")
    do_dai = request.headers.get("content-length")
    if do_dai and do_dai.isdigit() and int(do_dai) > GIOI_HAN_BYTE:
        raise HTTPException(
            status_code=413,
            detail=f"Tệp vượt quá giới hạn {GIOI_HAN_BYTE // 1048576} MB.",
        )
    du_lieu = await request.body()
    try:
        tep = kho_tep.them(ten, du_lieu)
    except LoiTepDinhKem as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return tep.cong_khai()


@app.post("/api/kho/tep")
async def tai_tep_vao_kho(
    request: Request,
    ten: str,
    x_rag_action: str | None = Header(default=None),
):
    """Nút "+" trong Kho tài liệu: lưu tệp vào kho rồi hẹn lập chỉ mục."""
    if x_rag_action != "upload-library":
        raise HTTPException(status_code=403, detail="Yêu cầu tải tệp không hợp lệ.")
    do_dai = request.headers.get("content-length")
    if do_dai and do_dai.isdigit() and int(do_dai) > GIOI_HAN_BYTE:
        raise HTTPException(
            status_code=413,
            detail=f"Tệp vượt quá giới hạn {GIOI_HAN_BYTE // 1048576} MB.",
        )
    du_lieu = await request.body()
    trang_thai, thong_bao = service.nhap_tep_tu_giao_dien(ten, du_lieu)
    if trang_thai in {"loi", "khong_ho_tro"}:
        raise HTTPException(status_code=400, detail=thong_bao)
    return {"trang_thai": trang_thai, "thong_bao": thong_bao}


@app.get("/api/tep")
def danh_sach_tep():
    return {"tep": kho_tep.danh_sach()}


@app.get("/api/tep/{tep_id}")
def trang_thai_tep(tep_id: str):
    tep = kho_tep.lay(tep_id)
    if tep is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp đính kèm.")
    return tep.cong_khai()


@app.delete("/api/tep/{tep_id}")
def xoa_tep(tep_id: str):
    if not kho_tep.xoa(tep_id):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp đính kèm.")
    return {"da_xoa": tep_id}


@app.get("/api/tep/{tep_id}/noi-dung")
def mo_tep_dinh_kem(tep_id: str):
    tep = kho_tep.lay(tep_id)
    if tep is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp đính kèm.")
    xem_truc_tiep = {
        ".pdf", ".txt", ".md", ".csv", ".html", ".htm",
        ".mp4", ".webm", ".mov", ".mp3", ".wav", ".m4a", ".ogg",
        ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
    }
    return FileResponse(
        tep.duong_dan,
        filename=tep.ten,
        content_disposition_type="inline" if tep.duoi in xem_truc_tiep else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@app.get("/api/source")
def open_source(name: str):
    source_path = service.resolve_source_file(name)
    if source_path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nguồn tài liệu duy nhất.")
    extension = Path(source_path).suffix.lower()
    # Video/âm thanh phải mở inline thì trình duyệt mới tua tới mốc "#t=" của
    # trích dẫn được; các định dạng Office vẫn tải về để mở bằng app tương ứng.
    xem_truc_tiep = {
        ".pdf", ".txt", ".csv", ".html", ".htm",
        ".mp4", ".webm", ".mov", ".mp3", ".wav", ".m4a", ".ogg",
        ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff",
    }
    disposition = "inline" if extension in xem_truc_tiep else "attachment"
    return FileResponse(
        source_path,
        filename=name,
        content_disposition_type=disposition,
        headers={"X-Content-Type-Options": "nosniff"},
    )


class GiaoDienTinh(StaticFiles):
    """Trang HTML luôn phải hỏi lại máy chủ trước khi dùng bản trong bộ nhớ đệm.

    index.html không có số phiên bản trong đường dẫn, nên nếu trình duyệt tự ý
    giữ lại bản cũ thì người dùng vẫn thấy giao diện cũ sau khi triển khai -
    kể cả khi app.js và styles.css đã đổi ?v=. "no-cache" không cấm lưu, chỉ
    bắt hỏi lại: máy chủ trả 304 nếu tệp chưa đổi nên gần như không tốn gì.
    Các tệp tĩnh còn lại vẫn để trình duyệt nhớ bình thường vì đã có ?v=.
    """

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        duong_dan = str(args[0] if args else kwargs.get("full_path", ""))
        if duong_dan.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        return response


app.mount("/", GiaoDienTinh(directory=STATIC_DIR, html=True), name="static")
