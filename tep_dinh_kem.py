"""
Kho tệp người dùng đính kèm ngay trong khung chat.

Khác với kho tri thức chính (FAISS + BM25 dựng sẵn cho ~200 văn bản), tệp đính
kèm là thứ dùng một lần: người dùng thả file vào, hỏi vài câu rồi bỏ. Nên ở đây
KHÔNG embed vào FAISS (bge-m3 trên CPU mất hàng phút cho một file dày, và sẽ
làm bẩn chỉ mục chung) mà chỉ chunk rồi dựng BM25 riêng cho từng tệp - đủ để
hỏi xoáy vào một tài liệu vì phạm vi tìm kiếm chỉ còn vài chục đoạn.

Việc đọc tệp chạy nền vì một PDF scan phải OCR, một video phải phiên âm; giao
diện hỏi trạng thái qua /api/tep/{id} cho tới khi "san_sang".

TÀI LIỆU RIÊNG: tệp là của người tải lên ("nd:<id>" với tài khoản, "kh:<mã
trình duyệt>" với khách). Chỉ chủ thấy tệp trong danh sách ("Tài liệu của tôi"
ở Kho tài liệu) - kể cả quản trị viên cũng không xem được tệp riêng của người
khác. Tệp KHÔNG tự vào kho chung nữa: chủ tệp bấm "Đề xuất vào kho chung" thì
mới gọi hook do rag_service gắn vào (quản trị viên: vào thẳng kho; người khác:
vào hàng chờ duyệt, ghi rõ ai đề xuất).

Các đoạn đã đọc được ghi ra đĩa ({id}.json cạnh tệp gốc) nên máy chủ khởi động
lại không mất tệp. Tệp của tài khoản giữ tới khi chủ xoá (có hạn mức theo
người); tệp của khách giữ theo số ngày và giới hạn chung của máy chủ.
"""

from __future__ import annotations

import json
import os
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass, field

from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from chunking_utils import chunk_theo_cau_truc, load_file_an_toan_neu_can
from document_loaders import DINH_DANG_HO_TRO, suy_loai_tai_lieu
from hybrid_retrieval import mo_rong_truy_van, tach_tu_mo_rong

THU_MUC_TEP = os.path.abspath(os.getenv(
    "RAG_THU_MUC_TEP_DINH_KEM",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tep_dinh_kem"),
))
GIOI_HAN_BYTE = max(1, int(os.getenv("RAG_GIOI_HAN_TEP_MB", "40"))) * 1024 * 1024
# Tệp của khách: giới hạn chung cho cả máy chủ và giữ theo số ngày.
SO_TEP_TOI_DA = max(1, int(os.getenv("RAG_SO_TEP_DINH_KEM_TOI_DA", "200")))
NGAY_GIU_TEP = max(1, int(os.getenv("RAG_NGAY_GIU_TEP_DINH_KEM", "30")))
# Tài liệu riêng của mỗi tài khoản: không hết hạn, nhưng mỗi người có hạn mức.
SO_TEP_MOI_NGUOI = max(1, int(os.getenv("RAG_SO_TAI_LIEU_RIENG_TOI_DA", "100")))
KY_TU_TOI_THIEU = 40  # ít hơn mức này coi như không đọc được nội dung

# rag_service gắn hàm chép tệp vào kho tài liệu ở đây. Để dạng hook vì
# rag_service đã import module này, import ngược lại sẽ thành vòng.
_hook_luu_kho = None


def dat_hook_luu_kho(hook) -> None:
    """Đăng ký hàm (duong_dan, ten, nguoi) -> (trang_thai, thong_bao) đề xuất tệp vào kho.

    nguoi là chủ tệp: quản trị viên thì tệp vào thẳng kho, người khác thì vào
    hàng chờ duyệt (xem quan_ly_kho).
    """
    global _hook_luu_kho
    _hook_luu_kho = hook


def chu_cua(nguoi: dict | None, ma_khach: str | None = None) -> str | None:
    """Khoá chủ sở hữu: "nd:<id>" với tài khoản, "kh:<mã trình duyệt>" với khách."""
    if nguoi and nguoi.get("id"):
        return f"nd:{nguoi['id']}"
    return f"kh:{ma_khach}" if ma_khach else None


class LoiTepDinhKem(ValueError):
    """Lỗi người dùng sửa được (sai định dạng, quá nặng, không tồn tại)."""


def _ten_an_toan(ten_goc: str) -> str:
    """Bỏ đường dẫn và ký tự điều khiển, chỉ giữ lại tên hiển thị."""
    ten = unicodedata.normalize("NFC", (ten_goc or "").strip())
    ten = ten.replace("\\", "/").split("/")[-1]
    ten = "".join(ky_tu for ky_tu in ten if ky_tu.isprintable())
    ten = ten.strip(" .")
    return ten[:160] or "tai-lieu"


@dataclass
class TepDinhKem:
    id: str
    ten: str
    duoi: str
    loai: str
    duong_dan: str
    kich_thuoc: int
    tao_luc: float
    trang_thai: str = "dang_xu_ly"  # dang_xu_ly | san_sang | loi
    thong_bao: str = "Đang đọc nội dung tệp..."
    so_chunk: int = 0
    so_ky_tu: int = 0
    # rieng | cho_duyet | da_luu | da_co | tu_choi | loi - tình trạng với kho chung
    # (rieng = chỉ chủ tệp thấy, chưa đề xuất vào kho chung)
    luu_kho: str = "rieng"
    thong_bao_kho: str = ""
    chunks: list = field(default_factory=list)
    bm25: object | None = None
    # Người tải lên (không lộ ra cong_khai): khi đề xuất, quyết định vào thẳng kho hay chờ duyệt.
    nguoi: dict | None = None
    # Chủ sở hữu (chu_cua). None: tệp của khách từ bản cũ, không ai liệt kê được.
    chu: str | None = None
    ma_bam: str = ""

    def cong_khai(self) -> dict:
        """Bản mô tả trả cho giao diện - không lộ đường dẫn trên máy."""
        return {
            "id": self.id,
            "ten": self.ten,
            "loai": self.loai,
            "tao_luc": self.tao_luc,
            "kich_thuoc": self.kich_thuoc,
            "trang_thai": self.trang_thai,
            "thong_bao": self.thong_bao,
            "so_chunk": self.so_chunk,
            "so_ky_tu": self.so_ky_tu,
            "luu_kho": self.luu_kho,
            "thong_bao_kho": self.thong_bao_kho,
            "url": f"/api/tep/{self.id}/noi-dung",
        }


class KhoTepDinhKem:
    def __init__(self):
        self._tep: dict[str, TepDinhKem] = {}
        self._lock = threading.Lock()

    # ----- vòng đời -----
    def them(
        self, ten_goc: str, du_lieu: bytes, nguoi: dict | None = None, chu: str | None = None
    ) -> TepDinhKem:
        chu = chu or chu_cua(nguoi)
        if chu and chu.startswith("nd:"):
            with self._lock:
                so_tep = sum(1 for t in self._tep.values() if t.chu == chu)
            if so_tep >= SO_TEP_MOI_NGUOI:
                raise LoiTepDinhKem(
                    f"Bạn đã có {so_tep} tài liệu riêng (tối đa {SO_TEP_MOI_NGUOI}). "
                    "Hãy xoá bớt trong Kho tài liệu > Của tôi."
                )
        ten = _ten_an_toan(ten_goc)
        duoi = os.path.splitext(ten)[1].lower()
        if duoi not in DINH_DANG_HO_TRO:
            raise LoiTepDinhKem(
                f"Chưa hỗ trợ định dạng {duoi or 'này'}. "
                f"Định dạng đọc được: {', '.join(sorted(DINH_DANG_HO_TRO))}"
            )
        if not du_lieu:
            raise LoiTepDinhKem("Tệp rỗng.")
        if len(du_lieu) > GIOI_HAN_BYTE:
            raise LoiTepDinhKem(
                f"Tệp nặng {len(du_lieu) / 1048576:.1f} MB, vượt giới hạn "
                f"{GIOI_HAN_BYTE // 1048576} MB."
            )

        os.makedirs(THU_MUC_TEP, exist_ok=True)
        ma = uuid.uuid4().hex
        duong_dan = os.path.join(THU_MUC_TEP, f"{ma}{duoi}")
        with open(duong_dan, "wb") as f:
            f.write(du_lieu)

        tep = TepDinhKem(
            id=ma,
            ten=ten,
            duoi=duoi,
            loai=suy_loai_tai_lieu(ten),
            duong_dan=duong_dan,
            kich_thuoc=len(du_lieu),
            tao_luc=time.time(),
            nguoi=nguoi,
            chu=chu,
        )
        with self._lock:
            self._tep[ma] = tep
        self._don_bot_tep_cu()
        threading.Thread(
            target=self._xu_ly, args=(tep,), daemon=True, name=f"doc-tep-{ma[:6]}"
        ).start()
        return tep

    def lay(self, tep_id: str) -> TepDinhKem | None:
        """Lấy thẳng, KHÔNG kiểm tra chủ - chỉ dùng nội bộ; đường dẫn từ người dùng đi qua cua()."""
        with self._lock:
            return self._tep.get(tep_id)

    @staticmethod
    def duoc_dung(tep: TepDinhKem, chu: str | None) -> bool:
        """Tệp của tài khoản: chỉ đúng tài khoản đó. Tệp của khách: mã tệp (32 ký
        tự ngẫu nhiên, không còn liệt kê cho ai) chính là chìa khoá - ảnh trang
        do thẻ <img> tải về không gửi kèm được mã trình duyệt."""
        if tep.chu and tep.chu.startswith("nd:"):
            return chu == tep.chu
        return True

    def cua(self, tep_id: str, chu: str | None) -> TepDinhKem | None:
        tep = self.lay(tep_id)
        return tep if tep is not None and self.duoc_dung(tep, chu) else None

    def lay_san_sang(self, tep_id: str, chu: str | None = None, *, kiem_chu: bool = True) -> TepDinhKem:
        tep = self.cua(tep_id, chu) if kiem_chu else self.lay(tep_id)
        if tep is None:
            raise LoiTepDinhKem("Tệp đính kèm không còn trên máy chủ, hãy tải lại tệp.")
        if tep.trang_thai == "dang_xu_ly":
            raise LoiTepDinhKem(f"Đang đọc nội dung tệp {tep.ten}, vui lòng đợi.")
        if tep.trang_thai != "san_sang":
            raise LoiTepDinhKem(f"{tep.ten}: {tep.thong_bao}")
        return tep

    def cac_tep_cua(self, chu: str | None) -> list[TepDinhKem]:
        """Tệp của đúng một chủ, mới nhất trước. Không có chủ thì không có gì."""
        if not chu:
            return []
        with self._lock:
            return sorted((t for t in self._tep.values() if t.chu == chu),
                          key=lambda t: t.tao_luc, reverse=True)

    def danh_sach(self, chu: str | None) -> list[dict]:
        return [tep.cong_khai() for tep in self.cac_tep_cua(chu)]

    def xoa(self, tep_id: str, chu: str | None = None, *, kiem_chu: bool = True) -> bool:
        with self._lock:
            tep = self._tep.get(tep_id)
            if tep is None or (kiem_chu and not self.duoc_dung(tep, chu)):
                return False
            self._tep.pop(tep_id, None)
        self._xoa_tren_dia(tep)
        return True

    def chuyen_chu(self, tu_chu: str, sang_chu: str, nguoi: dict | None) -> int:
        """Khách vừa đăng ký: tệp đã đính kèm đi theo sang tài khoản mới."""
        cac_tep = self.cac_tep_cua(tu_chu)
        for tep in cac_tep:
            tep.chu, tep.nguoi = sang_chu, nguoi
            if tep.trang_thai == "san_sang":
                self._ghi_ra_dia(tep)
        return len(cac_tep)

    def xoa_het_cua(self, chu: str) -> int:
        """Xoá tài khoản thì xoá luôn tài liệu riêng của người đó."""
        cac_tep = self.cac_tep_cua(chu)
        for tep in cac_tep:
            self.xoa(tep.id, kiem_chu=False)
        return len(cac_tep)

    def de_xuat(self, tep: TepDinhKem, ma_bam: str, nguoi: dict | None) -> tuple[str, str]:
        """Chủ tệp bấm "Đề xuất vào kho chung": giao cho hook của rag_service.

        nguoi là người đang bấm (quyền hiện tại), không phải bản lưu lúc tải lên.
        """
        if tep.trang_thai != "san_sang":
            raise LoiTepDinhKem("Tệp chưa đọc xong, hãy đợi một chút rồi đề xuất.")
        if _hook_luu_kho is None:
            raise LoiTepDinhKem("Máy chủ chưa bật việc đưa tệp vào kho chung.")
        tep.ma_bam = ma_bam
        try:
            tep.luu_kho, tep.thong_bao_kho = _hook_luu_kho(tep.duong_dan, tep.ten, nguoi)
        except Exception as exc:  # hỏng thì tài liệu riêng vẫn dùng được, chỉ báo lại
            tep.luu_kho, tep.thong_bao_kho = "loi", f"Chưa đề xuất được vào kho chung: {exc}"
        self._ghi_ra_dia(tep)
        return tep.luu_kho, tep.thong_bao_kho

    def _don_bot_tep_cu(self) -> None:
        """Tệp của khách: bỏ tệp quá NGAY_GIU_TEP ngày, rồi giữ lại SO_TEP_TOI_DA
        tệp mới nhất để không phình thư mục. Tài liệu riêng của tài khoản không
        bị đụng tới - tệp của người khác không được đẩy tài liệu của mình ra."""
        han = time.time() - NGAY_GIU_TEP * 86400
        with self._lock:
            theo_thoi_gian = sorted(
                (t for t in self._tep.values() if not (t.chu or "").startswith("nd:")),
                key=lambda t: t.tao_luc,
            )
            qua_han = [t for t in theo_thoi_gian if t.tao_luc < han]
            con_lai = [t for t in theo_thoi_gian if t.tao_luc >= han]
            if len(con_lai) > SO_TEP_TOI_DA:
                qua_han += con_lai[: len(con_lai) - SO_TEP_TOI_DA]
            for tep in qua_han:
                self._tep.pop(tep.id, None)
        for tep in qua_han:
            self._xoa_tren_dia(tep)

    @staticmethod
    def _duong_dan_ban_ghi(tep_id: str) -> str:
        return os.path.join(THU_MUC_TEP, f"{tep_id}.json")

    @classmethod
    def _xoa_tren_dia(cls, tep: TepDinhKem) -> None:
        for duong_dan in (tep.duong_dan, cls._duong_dan_ban_ghi(tep.id)):
            try:
                os.remove(duong_dan)
            except OSError:
                pass

    # ----- lưu ra đĩa / nạp lại khi khởi động -----
    def _ghi_ra_dia(self, tep: TepDinhKem) -> None:
        """Ghi các đoạn đã đọc để khởi động lại không phải OCR/phiên âm lại.
        Ghi hỏng thì tệp vẫn hỏi được tới lần khởi động kế, nên chỉ bỏ qua."""
        ban_ghi = {
            "id": tep.id, "ten": tep.ten, "duoi": tep.duoi, "loai": tep.loai,
            "kich_thuoc": tep.kich_thuoc, "tao_luc": tep.tao_luc,
            "thong_bao": tep.thong_bao, "so_ky_tu": tep.so_ky_tu,
            "luu_kho": tep.luu_kho, "thong_bao_kho": tep.thong_bao_kho,
            "nguoi": tep.nguoi, "chu": tep.chu, "ma_bam": tep.ma_bam,
            "chunks": [
                {"noi_dung": c.page_content, "metadata": c.metadata} for c in tep.chunks
            ],
        }
        dich = self._duong_dan_ban_ghi(tep.id)
        tam = dich + ".tmp"
        try:
            with open(tam, "w", encoding="utf-8") as f:
                json.dump(ban_ghi, f, ensure_ascii=False, default=str)
            os.replace(tam, dich)
        except (OSError, TypeError, ValueError):
            try:
                os.remove(tam)
            except OSError:
                pass

    def nap_lai_tu_dia(self) -> int:
        """Nạp lại các tệp đã đọc xong ở lần chạy trước. Tệp đang đọc dở lúc
        máy chủ tắt không có bản ghi nên bị bỏ qua (người dùng tải lại)."""
        if not os.path.isdir(THU_MUC_TEP):
            return 0
        da_nap = 0
        for ten_file in os.listdir(THU_MUC_TEP):
            if not ten_file.endswith(".json"):
                continue
            try:
                with open(os.path.join(THU_MUC_TEP, ten_file), encoding="utf-8") as f:
                    ban_ghi = json.load(f)
                ma = ban_ghi["id"]
                duong_dan = os.path.join(THU_MUC_TEP, f"{ma}{ban_ghi['duoi']}")
                if not os.path.isfile(duong_dan):
                    os.remove(os.path.join(THU_MUC_TEP, ten_file))
                    continue
                chunks = [
                    Document(page_content=c["noi_dung"], metadata=c.get("metadata") or {})
                    for c in ban_ghi.get("chunks") or []
                ]
                tep = TepDinhKem(
                    id=ma, ten=ban_ghi["ten"], duoi=ban_ghi["duoi"], loai=ban_ghi["loai"],
                    duong_dan=duong_dan, kich_thuoc=int(ban_ghi["kich_thuoc"]),
                    tao_luc=float(ban_ghi["tao_luc"]), trang_thai="san_sang",
                    thong_bao=ban_ghi.get("thong_bao") or f"Đã đọc {len(chunks)} đoạn nội dung.",
                    so_chunk=len(chunks), so_ky_tu=int(ban_ghi.get("so_ky_tu") or 0),
                    luu_kho=ban_ghi.get("luu_kho") or "rieng",
                    thong_bao_kho=ban_ghi.get("thong_bao_kho") or "",
                    chunks=chunks, nguoi=ban_ghi.get("nguoi"),
                    # Bản ghi từ trước khi có tài liệu riêng: suy chủ từ người tải lên.
                    chu=ban_ghi.get("chu") or chu_cua(ban_ghi.get("nguoi")),
                    ma_bam=ban_ghi.get("ma_bam") or "",
                )
            except (OSError, ValueError, KeyError, TypeError):
                continue
            with self._lock:
                self._tep.setdefault(ma, tep)
            da_nap += 1
        self._don_bot_tep_cu()
        return da_nap

    # ----- đọc và chunk -----
    def _xu_ly(self, tep: TepDinhKem) -> None:
        try:
            tai_lieu, loi = load_file_an_toan_neu_can(tep.duong_dan)
            if loi or not tai_lieu:
                tep.trang_thai = "loi"
                tep.thong_bao = f"Không đọc được nội dung tệp ({loi or 'tệp rỗng'})."
                return
            for doc in tai_lieu:
                doc.metadata["source_file"] = tep.ten
                doc.metadata["loai_tai_lieu"] = tep.loai
                doc.metadata["tep_dinh_kem"] = tep.id
            chunks = chunk_theo_cau_truc(tai_lieu)
            so_ky_tu = sum(len(chunk.page_content) for chunk in chunks)
            if so_ky_tu < KY_TU_TOI_THIEU:
                tep.trang_thai = "loi"
                tep.thong_bao = (
                    "Tệp gần như không có văn bản đọc được "
                    "(có thể là bản scan chưa OCR hoặc chỉ gồm hình ảnh)."
                )
                return
            for thu_tu, chunk in enumerate(chunks, 1):
                chunk.metadata["source_file"] = tep.ten
                chunk.metadata["loai_tai_lieu"] = tep.loai
                chunk.metadata["tep_dinh_kem"] = tep.id
                chunk.metadata["source_url"] = f"/api/tep/{tep.id}/noi-dung"
                chunk.metadata.setdefault("context_label", f"Đoạn {thu_tu}")
            tep.chunks = chunks
            tep.bm25 = self._dung_bm25(chunks)
            tep.so_chunk = len(chunks)
            tep.so_ky_tu = so_ky_tu
            # Tệp ở lại là tài liệu riêng của người tải lên; chỉ vào kho chung
            # khi chính họ bấm "Đề xuất vào kho chung" (de_xuat).
            tep.trang_thai = "san_sang"
            tep.thong_bao = f"Đã đọc {len(chunks)} đoạn nội dung."
            self._ghi_ra_dia(tep)
        except Exception as exc:  # loader bên thứ ba có thể ném đủ loại lỗi
            tep.trang_thai = "loi"
            tep.thong_bao = f"Không đọc được tệp: {exc}"

    @staticmethod
    def _dung_bm25(chunks: list[Document]):
        docs = []
        for chunk in chunks:
            tieu_de = " ".join(filter(None, [
                chunk.metadata.get("source_file"),
                chunk.metadata.get("chapter"),
                chunk.metadata.get("article"),
                chunk.metadata.get("context_label"),
            ]))
            metadata = dict(chunk.metadata)
            metadata["_noi_dung_goc"] = chunk.page_content
            docs.append(Document(
                page_content=f"{tieu_de}\n{chunk.page_content}",
                metadata=metadata,
            ))
        return BM25Retriever.from_documents(docs, preprocess_func=tach_tu_mo_rong)

    # ----- truy hồi trong đúng một tệp -----
    def truy_hoi(self, tep: TepDinhKem, cau_hoi: str, so_ket_qua: int) -> list[Document]:
        """Xếp hạng các đoạn của riêng tệp này theo BM25; không khớp thì lấy đầu tệp."""
        if not tep.chunks:
            return []
        if tep.bm25 is None and so_ket_qua > 0:
            # Tệp nạp lại từ đĩa chưa có BM25; dựng lúc được hỏi lần đầu.
            tep.bm25 = self._dung_bm25(tep.chunks)
        if tep.bm25 is None or so_ket_qua <= 0:
            return tep.chunks[:so_ket_qua]
        tokens = mo_rong_truy_van(tach_tu_mo_rong(cau_hoi), cau_hoi)
        if not tokens:
            return tep.chunks[:so_ket_qua]
        diem = tep.bm25.vectorizer.get_scores(tokens)
        thu_tu = sorted(range(len(diem)), key=lambda i: diem[i], reverse=True)
        ket_qua = [tep.chunks[i] for i in thu_tu[:so_ket_qua] if diem[i] > 0]
        # Câu hỏi chung chung ("tài liệu này nói gì") không khớp từ khóa nào -
        # vẫn phải đưa nội dung tệp vào ngữ cảnh thay vì trả lời "không thấy".
        return ket_qua or self.doan_dai_dien(tep, so_ket_qua)

    @staticmethod
    def doan_dai_dien(tep: TepDinhKem, so_doan: int) -> list[Document]:
        """Lấy các đoạn rải đều khắp tệp - dùng cho yêu cầu tóm tắt."""
        tong = len(tep.chunks)
        if tong <= so_doan:
            return list(tep.chunks)
        buoc = tong / so_doan
        vi_tri = sorted({min(tong - 1, int(i * buoc)) for i in range(so_doan)})
        return [tep.chunks[i] for i in vi_tri]


kho_tep = KhoTepDinhKem()
