"""FastAPI phục vụ giao diện web và API streaming cho Chatbot RAG Giáo dục."""

from __future__ import annotations

import json
import queue
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

import bao_ve_truy_cap
import cache_ngu_nghia
import dich_thuat
import giong_noi
import lich_su_chat
import phan_loai_giao_duc
import quan_ly_kho
import tai_khoan
import trinh_doc_tai_lieu
from rag_service import service
from tep_dinh_kem import GIOI_HAN_BYTE, LoiTepDinhKem, kho_tep


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"


class DoanTrich(BaseModel):
    """Đoạn người dùng khoanh trong trình đọc tài liệu để hỏi."""

    van_ban: str = Field(min_length=1, max_length=4000)
    ten: str = Field(default="", max_length=260)
    trang: int = Field(default=1, ge=1, le=100000)
    tep: str | None = Field(default=None, max_length=64)


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
    # Hỏi về một vùng vừa khoanh: đoạn này thành bằng chứng số 1 của câu trả lời.
    doan_trich: DoanTrich | None = None

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


# ============================================================
# TÀI KHOẢN VÀ QUYỀN
# ============================================================
def nguoi_dung_hien_tai(request: Request) -> dict | None:
    """Người đang đăng nhập (theo cookie phiên), hoặc None nếu là khách."""
    if request is None:  # gọi thẳng hàm route trong test, không qua HTTP
        return None
    if not hasattr(request.state, "nguoi_dung"):
        request.state.nguoi_dung = tai_khoan.nguoi_dung_theo_phien(
            request.cookies.get(tai_khoan.TEN_COOKIE)
        )
    return request.state.nguoi_dung


def yeu_cau_quan_tri(request: Request) -> None:
    """Các thao tác đụng tới cả hệ thống: kho tài liệu, chỉ mục, mô hình, Drive."""
    if not tai_khoan.bat_khoa_quan_tri():
        return
    nguoi_dung = nguoi_dung_hien_tai(request)
    if nguoi_dung is None:
        raise HTTPException(status_code=401, detail="Hãy đăng nhập bằng tài khoản quản trị.")
    if not nguoi_dung["quan_tri"]:
        raise HTTPException(status_code=403, detail="Chỉ quản trị viên mới làm được thao tác này.")


def _la_quan_tri(request: Request) -> bool:
    if not tai_khoan.bat_khoa_quan_tri():
        return True
    nguoi_dung = nguoi_dung_hien_tai(request)
    return bool(nguoi_dung and nguoi_dung["quan_tri"])


def _dia_chi_ip(request: Request) -> str:
    # Sau Caddy/đường hầm thì địa chỉ thật nằm ở X-Forwarded-For; chỉ dùng để
    # đếm số lần đăng nhập sai nên lấy nhầm cũng không mở ra lỗ hổng nào.
    chuyen_tiep = request.headers.get("x-forwarded-for", "")
    return (chuyen_tiep.split(",")[0].strip() or (request.client.host if request.client else ""))[:64]


@app.get("/api/status")
def get_status():
    return service.status_dict()


@app.get("/api/documents")
def get_documents(request: Request):
    kho = service.document_inventory()
    if _la_quan_tri(request):
        # Quản trị viên thấy ai đã đưa từng tài liệu vào kho, và bao nhiêu tệp
        # đang chờ duyệt; người khác chỉ thấy danh sách tài liệu như trước.
        nguoi_dua = quan_ly_kho.nguoi_dua_vao_kho()
        for tai_lieu in kho.get("documents", []):
            if tai_lieu.get("name") in nguoi_dua:
                tai_lieu.update(nguoi_dua[tai_lieu["name"]])
        kho.setdefault("summary", {})["cho_duyet"] = quan_ly_kho.dem_cho_duyet()
    return kho


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


@app.post("/api/index/update", dependencies=[Depends(yeu_cau_quan_tri)])
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


@app.post("/api/model", dependencies=[Depends(yeu_cau_quan_tri)])
def doi_model(request: ModelRequest, x_rag_action: str | None = Header(default=None)):
    if x_rag_action != "switch-model":
        raise HTTPException(status_code=403, detail="Yêu cầu đổi model không hợp lệ.")
    thanh_cong, thong_bao = service.doi_model(request.model)
    if not thanh_cong:
        raise HTTPException(status_code=409, detail=thong_bao)
    return {"model": service.llm_model, "message": thong_bao}


@app.post("/api/drive/sync", dependencies=[Depends(yeu_cau_quan_tri)])
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
def chat_stream(
    request: ChatRequest,
    x_rag_client: str | None = Header(default=None),
    http: Request = None,
):
    if service.status.state != "ready":
        raise HTTPException(status_code=503, detail=service.status.message)
    chu_so_huu = _chu_so_huu(http, x_rag_client, bat_buoc=False)

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
        # Những gì giao diện cần để vẽ lại câu trả lời y như lúc hỏi, đặt đúng
        # tên khoá mà app.js dùng cho lịch sử trong trình duyệt.
        chi_tiet: dict = {"hieuLuc": [], "warning": "", "goiY": [], "interrupted": True}
        # Chỉ truyền khi có, để lượt hỏi thường gọi đúng chữ ký cũ.
        them = {"doan_trich": request.doan_trich.model_dump()} if request.doan_trich else {}
        bo_sinh = service.stream_answer(
            request.question, history, request.tep_ids, request.pham_vi, **them
        )
        try:
            for event in bo_sinh:
                loai = event.get("type")
                if loai == "token":
                    cau_tra_loi += event.get("content", "")
                elif loai == "sources":
                    cac_nguon = event.get("sources", [])
                elif loai == "hieu_luc":
                    chi_tiet["hieuLuc"].append({"message": event.get("message"), "kind": event.get("kind")})
                elif loai == "warning":
                    chi_tiet["warning"] = event.get("message", "")
                elif loai == "goi_y":
                    chi_tiet["goiY"] = event.get("goi_y", [])
                elif loai == "done":
                    chi_tiet["interrupted"] = False
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
                    client_id=chu_so_huu,
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
                    chi_tiet={**chi_tiet, "sources": cac_nguon, "elapsed": thong_tin["giay"]},
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
# Chủ của hội thoại: tài khoản đang đăng nhập ("nd:<id>"), hoặc với khách là
# mã X-RAG-Client do trình duyệt tự sinh. Mã của khách KHÔNG phải xác thực - ai
# cũng gửi được mã của người khác - nên chỉ đủ để hai khách chung máy chủ không
# vô tình thấy hội thoại của nhau; muốn lịch sử thật sự riêng tư thì đăng nhập.
def _chu_so_huu(request: Request, header: str | None, bat_buoc: bool = True) -> str:
    nguoi_dung = nguoi_dung_hien_tai(request)
    if nguoi_dung is not None:
        return f"nd:{nguoi_dung['id']}"
    ma = (header or "").strip()[:60]
    if not ma:
        if bat_buoc:
            raise HTTPException(status_code=400, detail="Thiếu mã trình duyệt.")
        return ""
    # Khách không được mạo danh tài khoản bằng cách tự gửi mã "nd:...".
    return ma.replace(":", "-")


@app.get("/api/hoi-thoai")
def liet_ke_hoi_thoai(
    request: Request, x_rag_client: str | None = Header(default=None), gioi_han: int = 50
):
    return {"hoi_thoai": lich_su_chat.danh_sach_hoi_thoai(
        _chu_so_huu(request, x_rag_client), gioi_han
    )}


@app.get("/api/hoi-thoai/{hoi_thoai_id}")
def xem_hoi_thoai(
    hoi_thoai_id: str, request: Request, x_rag_client: str | None = Header(default=None)
):
    chi_tiet = lich_su_chat.chi_tiet_hoi_thoai(hoi_thoai_id)
    if chi_tiet is None or chi_tiet.get("client_id") != _chu_so_huu(request, x_rag_client):
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    return chi_tiet


@app.delete("/api/hoi-thoai/{hoi_thoai_id}")
def xoa_hoi_thoai(
    hoi_thoai_id: str, request: Request, x_rag_client: str | None = Header(default=None)
):
    chu_so_huu = _chu_so_huu(request, x_rag_client)
    nguoi_dung = nguoi_dung_hien_tai(request)
    if nguoi_dung is not None:
        # Sổ tay có thể tồn tại cả khi hội thoại chưa có lượt hỏi nào.
        tai_khoan.xoa_so_tay(nguoi_dung["id"], hoi_thoai_id)
    chi_tiet = lich_su_chat.chi_tiet_hoi_thoai(hoi_thoai_id)
    if chi_tiet is None or chi_tiet.get("client_id") != chu_so_huu:
        raise HTTPException(status_code=404, detail="Không tìm thấy hội thoại.")
    lich_su_chat.xoa_hoi_thoai(hoi_thoai_id)
    return {"da_xoa": hoi_thoai_id}


@app.delete("/api/hoi-thoai")
def xoa_toan_bo_hoi_thoai(request: Request, x_rag_client: str | None = Header(default=None)):
    so = lich_su_chat.xoa_theo_client(_chu_so_huu(request, x_rag_client))
    nguoi_dung = nguoi_dung_hien_tai(request)
    if nguoi_dung is not None:
        tai_khoan.xoa_so_tay(nguoi_dung["id"])
    return {"da_xoa": so}


# ------------------------------------------------------------
# ĐĂNG KÝ / ĐĂNG NHẬP
# ------------------------------------------------------------
class DangKy(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    mat_khau: str = Field(min_length=1, max_length=200)
    ten: str = Field(default="", max_length=120)


class DangNhap(BaseModel):
    email: str = Field(min_length=1, max_length=254)
    mat_khau: str = Field(min_length=1, max_length=200)


class DoiMatKhau(BaseModel):
    mat_khau_cu: str = Field(min_length=1, max_length=200)
    mat_khau_moi: str = Field(min_length=1, max_length=200)


def _dat_cookie_phien(request: Request, phan_hoi: Response, ma_phien: str) -> None:
    https = (
        request.url.scheme == "https"
        or request.headers.get("x-forwarded-proto", "").lower() == "https"
    )
    phan_hoi.set_cookie(
        tai_khoan.TEN_COOKIE, ma_phien,
        max_age=tai_khoan.GIAY_PHIEN, httponly=True, samesite="lax",
        secure=https, path="/",
    )


def _phan_hoi_tai_khoan(request: Request, nguoi_dung: dict) -> JSONResponse:
    phan_hoi = JSONResponse({"nguoi_dung": nguoi_dung})
    _dat_cookie_phien(request, phan_hoi, tai_khoan.tao_phien(nguoi_dung["id"]))
    return phan_hoi


def _loi_tai_khoan(exc: tai_khoan.LoiTaiKhoan) -> HTTPException:
    return HTTPException(status_code=exc.ma_http, detail=str(exc))


@app.get("/api/tai-khoan/toi")
def tai_khoan_hien_tai(request: Request):
    return {
        "nguoi_dung": nguoi_dung_hien_tai(request),
        "khoa_quan_tri": tai_khoan.bat_khoa_quan_tri(),
        "so_cho_duyet": quan_ly_kho.dem_cho_duyet() if _la_quan_tri(request) else 0,
    }


@app.post("/api/tai-khoan/dang-ky")
def dang_ky(
    thong_tin: DangKy, request: Request, x_rag_client: str | None = Header(default=None)
):
    try:
        nguoi_dung = tai_khoan.dang_ky(
            thong_tin.email, thong_tin.mat_khau, thong_tin.ten, ip=_dia_chi_ip(request)
        )
    except tai_khoan.LoiTaiKhoan as exc:
        raise _loi_tai_khoan(exc) from exc
    # Những gì khách vừa hỏi trên trình duyệt này đi theo sang tài khoản mới,
    # như ChatGPT giữ lại cuộc trò chuyện dở khi người dùng bấm đăng ký. Chỉ
    # làm lúc đăng ký: đăng nhập trên máy dùng chung mà kéo luôn lịch sử của
    # người ngồi trước thì thành lộ hội thoại của họ.
    ma_khach = _chu_so_huu(request, x_rag_client, bat_buoc=False)
    if ma_khach and not ma_khach.startswith("nd:"):
        lich_su_chat.chuyen_chu_so_huu(ma_khach, f"nd:{nguoi_dung['id']}")
    return _phan_hoi_tai_khoan(request, nguoi_dung)


@app.post("/api/tai-khoan/dang-nhap")
def dang_nhap(thong_tin: DangNhap, request: Request):
    try:
        nguoi_dung = tai_khoan.dang_nhap(
            thong_tin.email, thong_tin.mat_khau, ip=_dia_chi_ip(request)
        )
    except tai_khoan.LoiTaiKhoan as exc:
        raise _loi_tai_khoan(exc) from exc
    return _phan_hoi_tai_khoan(request, nguoi_dung)


@app.post("/api/tai-khoan/dang-xuat")
def dang_xuat(request: Request):
    tai_khoan.xoa_phien(request.cookies.get(tai_khoan.TEN_COOKIE))
    phan_hoi = JSONResponse({"nguoi_dung": None})
    phan_hoi.delete_cookie(tai_khoan.TEN_COOKIE, path="/")
    return phan_hoi


@app.post("/api/tai-khoan/doi-mat-khau")
def doi_mat_khau(thong_tin: DoiMatKhau, request: Request):
    nguoi_dung = nguoi_dung_hien_tai(request)
    if nguoi_dung is None:
        raise HTTPException(status_code=401, detail="Hãy đăng nhập trước.")
    try:
        tai_khoan.doi_mat_khau(
            nguoi_dung["id"], thong_tin.mat_khau_cu, thong_tin.mat_khau_moi,
            giu_phien=request.cookies.get(tai_khoan.TEN_COOKIE),
        )
    except tai_khoan.LoiTaiKhoan as exc:
        raise _loi_tai_khoan(exc) from exc
    return {"ok": True}


# ------------------------------------------------------------
# SỔ TAY THEO TÀI KHOẢN (khách thì sổ nằm trong trình duyệt)
# ------------------------------------------------------------
def _nguoi_dung_bat_buoc(request: Request) -> dict:
    nguoi_dung = nguoi_dung_hien_tai(request)
    if nguoi_dung is None:
        raise HTTPException(status_code=401, detail="Hãy đăng nhập để lưu sổ tay trên máy chủ.")
    return nguoi_dung


def _ma_hoi_thoai(ma: str) -> str:
    if not 8 <= len(ma) <= 64 or not all(c.isalnum() or c in "-_" for c in ma):
        raise HTTPException(status_code=400, detail="Mã hội thoại không hợp lệ.")
    return ma


@app.get("/api/so-tay/{hoi_thoai_id}")
def lay_so_tay(hoi_thoai_id: str, request: Request):
    nguoi_dung = _nguoi_dung_bat_buoc(request)
    return {"so_tay": tai_khoan.lay_so_tay(nguoi_dung["id"], _ma_hoi_thoai(hoi_thoai_id))}


@app.put("/api/so-tay/{hoi_thoai_id}")
async def ghi_so_tay(hoi_thoai_id: str, request: Request):
    nguoi_dung = _nguoi_dung_bat_buoc(request)
    ma = _ma_hoi_thoai(hoi_thoai_id)
    du_lieu = await request.body()
    if len(du_lieu) > tai_khoan.SO_TAY_TOI_DA_BYTE:
        raise HTTPException(status_code=413, detail="Sổ tay quá lớn.")
    try:
        ban = json.loads(du_lieu or b"{}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Sổ tay không đúng định dạng.") from exc
    if not isinstance(ban, dict):
        raise HTTPException(status_code=400, detail="Sổ tay không đúng định dạng.")
    try:
        tai_khoan.ghi_so_tay(nguoi_dung["id"], ma, ban)
    except tai_khoan.LoiTaiKhoan as exc:
        raise _loi_tai_khoan(exc) from exc
    return {"ok": True}


@app.delete("/api/so-tay/{hoi_thoai_id}")
def xoa_so_tay(hoi_thoai_id: str, request: Request):
    nguoi_dung = _nguoi_dung_bat_buoc(request)
    tai_khoan.xoa_so_tay(nguoi_dung["id"], _ma_hoi_thoai(hoi_thoai_id))
    return {"ok": True}


@app.get("/api/thong-ke", dependencies=[Depends(yeu_cau_quan_tri)])
def thong_ke_su_dung(so_ngay: int = 30):
    """Người dùng hỏi gì, câu nào chậm, câu nào bị từ chối - dữ liệu để biết
    nên cải tiến chỗ nào thay vì đoán."""
    return {
        **lich_su_chat.thong_ke(so_ngay),
        "cache": cache_ngu_nghia.cache.thong_ke(),
    }


@app.delete("/api/cache", dependencies=[Depends(yeu_cau_quan_tri)])
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
        tep = kho_tep.them(ten, du_lieu, nguoi=nguoi_dung_hien_tai(request))
    except LoiTepDinhKem as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return tep.cong_khai()


@app.post("/api/kho/tep", dependencies=[Depends(yeu_cau_quan_tri)])
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
    trang_thai, thong_bao = service.nhap_tep_tu_giao_dien(
        ten, du_lieu, nguoi=nguoi_dung_hien_tai(request)
    )
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


# ============================================================
# ĐỌC TÀI LIỆU NGAY TRONG KHUNG CHAT
# ============================================================
# Tài liệu được chỉ tới bằng một trong hai cách, đúng như hai nơi giao diện
# có tệp: tep = id tệp đính kèm, nguon = tên tệp trong kho (giống /api/source).
# Mỗi trang là một ảnh riêng nên resolve_source_file bị gọi hàng chục lần khi
# cuộn một tệp dày; nó duyệt cả cây thư mục kho nên nhớ kết quả ít phút.
_GIAY_NHO_NGUON = 300.0
_nguon_da_tim: dict[str, tuple[float, str]] = {}


def _tai_lieu_can_doc(tep: str | None, nguon: str | None) -> str:
    if tep:
        tep_dinh_kem = kho_tep.lay(tep)
        if tep_dinh_kem is None:
            raise HTTPException(status_code=404, detail="Tệp đính kèm không còn trên máy chủ.")
        duong_dan = tep_dinh_kem.duong_dan
    elif nguon:
        da_tim = _nguon_da_tim.get(nguon)
        if da_tim and time.monotonic() - da_tim[0] < _GIAY_NHO_NGUON and Path(da_tim[1]).is_file():
            duong_dan = da_tim[1]
        else:
            duong_dan = service.resolve_source_file(nguon)
            if duong_dan is None:
                raise HTTPException(status_code=404, detail="Không tìm thấy nguồn tài liệu duy nhất.")
            _nguon_da_tim[nguon] = (time.monotonic(), duong_dan)
    else:
        raise HTTPException(status_code=400, detail="Thiếu tệp cần đọc.")
    if not trinh_doc_tai_lieu.doc_duoc(duong_dan):
        raise HTTPException(status_code=415, detail="Chỉ đọc trực tiếp được tệp PDF và ảnh.")
    return duong_dan


@app.get("/api/doc/thong-tin")
def thong_tin_tai_lieu(tep: str | None = None, nguon: str | None = None):
    duong_dan = _tai_lieu_can_doc(tep, nguon)
    try:
        return trinh_doc_tai_lieu.thong_tin(duong_dan)
    except trinh_doc_tai_lieu.LoiDocTaiLieu as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # PDF hỏng, ảnh sai định dạng...
        raise HTTPException(status_code=422, detail=f"Không mở được tài liệu: {exc}") from exc


@app.get("/api/doc/trang")
def anh_trang_tai_lieu(
    so: int, rong: int = 1000, tep: str | None = None, nguon: str | None = None
):
    duong_dan = _tai_lieu_can_doc(tep, nguon)
    try:
        du_lieu, kieu = trinh_doc_tai_lieu.render_trang(duong_dan, so, rong)
    except trinh_doc_tai_lieu.LoiDocTaiLieu as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Không render được trang: {exc}") from exc
    return Response(
        du_lieu,
        media_type=kieu,
        headers={"Cache-Control": "private, max-age=600", "X-Content-Type-Options": "nosniff"},
    )


class VungKhoanh(BaseModel):
    tep: str | None = Field(default=None, max_length=64)
    nguon: str | None = Field(default=None, max_length=260)
    so: int = Field(ge=1, le=100000)
    x0: float = Field(ge=0, le=1)
    y0: float = Field(ge=0, le=1)
    x1: float = Field(ge=0, le=1)
    y1: float = Field(ge=0, le=1)


@app.post("/api/doc/vung")
def chu_trong_vung_khoanh(vung: VungKhoanh):
    """Chữ nằm trong vùng người dùng vừa khoanh trên trang."""
    duong_dan = _tai_lieu_can_doc(vung.tep, vung.nguon)
    try:
        return trinh_doc_tai_lieu.chu_trong_vung(
            duong_dan, vung.so, (vung.x0, vung.y0, vung.x1, vung.y1)
        )
    except trinh_doc_tai_lieu.LoiDocTaiLieu as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Không đọc được vùng này: {exc}") from exc


# ============================================================
# QUẢN TRỊ KHO TÀI LIỆU: duyệt tệp gửi lên, gỡ / khôi phục tài liệu
# ============================================================
def _nguoi_quan_tri(request: Request) -> dict:
    yeu_cau_quan_tri(request)
    # Máy tắt khoá quản trị (chạy một mình) thì không có ai đăng nhập.
    return nguoi_dung_hien_tai(request) or {"ten": "Quản trị viên"}


def _loi_kho(exc: quan_ly_kho.LoiQuanLyKho) -> HTTPException:
    return HTTPException(status_code=exc.ma_http, detail=str(exc))


@app.get("/api/quan-ly/tai-len")
def danh_sach_tai_len(request: Request, trang_thai: str | None = None):
    _nguoi_quan_tri(request)
    if trang_thai not in {None, "cho_duyet", "trong_kho", "tu_choi"}:
        raise HTTPException(status_code=400, detail="Trạng thái không hợp lệ.")
    return {
        "tai_len": quan_ly_kho.danh_sach_tai_len(trang_thai),
        "so_cho_duyet": quan_ly_kho.dem_cho_duyet(),
    }


@app.get("/api/quan-ly/tai-len/{ma}/tep")
def xem_tep_cho_duyet(ma: str, request: Request):
    _nguoi_quan_tri(request)
    try:
        ban, duong_dan = quan_ly_kho.lay_ban_cho(ma)
    except quan_ly_kho.LoiQuanLyKho as exc:
        raise _loi_kho(exc) from exc
    return FileResponse(
        duong_dan, filename=ban["ten"], content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@app.post("/api/quan-ly/tai-len/{ma}/duyet")
def duyet_tep(ma: str, request: Request, x_rag_action: str | None = Header(default=None)):
    nguoi = _nguoi_quan_tri(request)
    if x_rag_action != "duyet-tep":
        raise HTTPException(status_code=403, detail="Yêu cầu không hợp lệ.")
    try:
        ket_qua = quan_ly_kho.duyet(ma, nguoi, service.dua_tep_duyet_vao_kho)
    except quan_ly_kho.LoiQuanLyKho as exc:
        raise _loi_kho(exc) from exc
    return {"ket_qua": ket_qua, "so_cho_duyet": quan_ly_kho.dem_cho_duyet()}


@app.post("/api/quan-ly/tai-len/{ma}/tu-choi")
def tu_choi_tep(ma: str, request: Request, x_rag_action: str | None = Header(default=None)):
    nguoi = _nguoi_quan_tri(request)
    if x_rag_action != "tu-choi-tep":
        raise HTTPException(status_code=403, detail="Yêu cầu không hợp lệ.")
    try:
        quan_ly_kho.tu_choi(ma, nguoi)
    except quan_ly_kho.LoiQuanLyKho as exc:
        raise _loi_kho(exc) from exc
    return {"so_cho_duyet": quan_ly_kho.dem_cho_duyet()}


class GoTaiLieu(BaseModel):
    ten: str = Field(min_length=1, max_length=260)


@app.post("/api/quan-ly/kho/go")
def go_tai_lieu(thong_tin: GoTaiLieu, request: Request, x_rag_action: str | None = Header(default=None)):
    nguoi = _nguoi_quan_tri(request)
    if x_rag_action != "go-tai-lieu":
        raise HTTPException(status_code=403, detail="Yêu cầu không hợp lệ.")
    try:
        ket_qua = service.go_tai_lieu(thong_tin.ten, nguoi)
    except quan_ly_kho.LoiQuanLyKho as exc:
        raise _loi_kho(exc) from exc
    _nguon_da_tim.pop(thong_tin.ten, None)
    return ket_qua


@app.get("/api/quan-ly/thung-rac")
def thung_rac(request: Request):
    _nguoi_quan_tri(request)
    return {"thung_rac": quan_ly_kho.danh_sach_thung_rac()}


@app.post("/api/quan-ly/thung-rac/{ma}/khoi-phuc")
def khoi_phuc_tai_lieu(ma: str, request: Request, x_rag_action: str | None = Header(default=None)):
    _nguoi_quan_tri(request)
    if x_rag_action != "khoi-phuc":
        raise HTTPException(status_code=403, detail="Yêu cầu không hợp lệ.")
    try:
        ten = service.khoi_phuc_tai_lieu(ma)
    except quan_ly_kho.LoiQuanLyKho as exc:
        raise _loi_kho(exc) from exc
    return {"ten": ten}


# ============================================================
# DỊCH ĐA NGÔN NGỮ (mọi ngôn ngữ Google Translate hỗ trợ)
# ============================================================
class YeuCauDich(BaseModel):
    van_ban: str = Field(min_length=1, max_length=dich_thuat.KY_TU_TOI_DA)
    nguon: str = Field(default="tu_dong", max_length=10)
    dich_sang: str = Field(default="en", max_length=10)


_mo_hinh_dich_da_chon: dict = {"ten": None, "luc": 0.0}


def _chon_mo_hinh_dich() -> str:
    """Mô hình dịch cấu hình sẵn nếu máy có, không thì dùng mô hình trả lời."""
    if time.monotonic() - _mo_hinh_dich_da_chon["luc"] < 300 and _mo_hinh_dich_da_chon["ten"]:
        return _mo_hinh_dich_da_chon["ten"]
    muon = dich_thuat.mo_hinh_dich()
    co_san = {m["name"] for m in service.danh_sach_model().get("models", [])}
    ten = muon if muon in co_san else service.llm_model
    _mo_hinh_dich_da_chon.update(ten=ten, luc=time.monotonic())
    return ten


@app.get("/api/dich/cau-hinh")
def cau_hinh_dich():
    """Giao diện cần biết văn bản có rời máy chủ không để báo cho người dùng."""
    return {
        "cong_cu": "google" if dich_thuat.khoa_google() else "cuc_bo",
        "ngon_ngu": dich_thuat.ngon_ngu_cho_giao_dien(),
        "ky_tu_toi_da": dich_thuat.KY_TU_TOI_DA,
    }


@app.post("/api/dich")
def dich_van_ban(yeu_cau: YeuCauDich):
    try:
        van_ban, nguon, dich_sang = dich_thuat.chuan_hoa_yeu_cau(
            yeu_cau.van_ban, yeu_cau.nguon, yeu_cau.dich_sang
        )
    except dich_thuat.LoiDich as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    def phat(su_kien: dict) -> str:
        return json.dumps(su_kien, ensure_ascii=False) + "\n"

    def generate():
        bat_dau = time.perf_counter()
        canh_bao = ""
        if dich_thuat.khoa_google():
            try:
                ban_dich, nguon_that = dich_thuat.dich_bang_google(van_ban, nguon, dich_sang)
                yield phat({"type": "ngon_ngu", "nguon": nguon_that, "dich_sang": dich_sang, "cong_cu": "google"})
                yield phat({"type": "token", "content": ban_dich})
                yield phat({"type": "done", "giay": round(time.perf_counter() - bat_dau, 1)})
                return
            except dich_thuat.LoiGoogle as exc:
                # Google lỗi (hết hạn mức, chưa bật API...) thì vẫn dịch được
                # bằng máy chủ, kèm lời giải thích vì sao chất lượng kém đi.
                canh_bao = f"{exc} Đang dùng bản dịch máy trên máy chủ."

        nguon_that = dich_thuat.nhan_dien(van_ban) if nguon == "tu_dong" else nguon
        yield phat({"type": "ngon_ngu", "nguon": nguon_that, "dich_sang": dich_sang, "cong_cu": "cuc_bo"})
        canh_bao = " ".join(filter(None, [canh_bao, dich_thuat.canh_bao_mo_hinh_nho(nguon_that, dich_sang)]))
        if canh_bao:
            yield phat({"type": "warning", "message": canh_bao})
        try:
            for su_kien in dich_thuat.dich_cuc_bo(van_ban, nguon_that, dich_sang, _chon_mo_hinh_dich()):
                yield phat(su_kien)
        except Exception as exc:  # Ollama tắt, thiếu mô hình, hết RAM...
            yield phat({"type": "error", "message": f"Không dịch được: {exc}"})
            return
        yield phat({"type": "done", "giay": round(time.perf_counter() - bat_dau, 1)})

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ============================================================
# NÓI THAY VÌ GÕ: ghi âm -> chữ, tự nhận ngôn ngữ (faster-whisper trên máy)
# ============================================================
@app.post("/api/giong-noi")
async def nhan_giong_noi(
    request: Request,
    x_rag_action: str | None = Header(default=None),
):
    """Nhận thẳng byte ghi âm trong body như /api/tep."""
    if x_rag_action != "voice-input":
        raise HTTPException(status_code=403, detail="Yêu cầu ghi âm không hợp lệ.")
    do_dai = request.headers.get("content-length")
    if do_dai and do_dai.isdigit() and int(do_dai) > giong_noi.BYTE_TOI_DA:
        raise HTTPException(status_code=413, detail="Đoạn ghi âm quá dài, hãy nói ngắn hơn.")
    du_lieu = await request.body()
    try:
        # Whisper chạy CPU vài giây: đẩy sang luồng khác để máy chủ vẫn phục vụ người khác.
        return await run_in_threadpool(giong_noi.nhan_dien_giong_noi, du_lieu)
    except giong_noi.LoiGiongNoi as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except giong_noi.media_transcribe.ThieuFasterWhisper as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


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
