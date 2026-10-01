"""
Chạy toàn bộ phần đo trên kho thật bằng một lệnh và gom kết quả vào một tệp.

    python chay_do_luong.py                 # kiểm tra điều kiện, đo IR, đo hỏi theo mốc
    python chay_do_luong.py --chi-kiem-tra  # chỉ kiểm tra điều kiện, không đo
    python chay_do_luong.py --bo-ir         # bỏ phần đo IR (đã có số rồi)

Kiểm tra trước khi chạy (lỗi nào cũng dừng trước khi tốn thời gian):
  - chỉ mục FAISS đã có. Thiếu chỉ mục thì RAGService sẽ tự lập chỉ mục từ đầu,
    mất hàng giờ và đo trên một kho khác với kho đang dùng, nên dừng hẳn;
  - Ollama đang chạy và có đủ model nhúng lẫn model trả lời (RAGService đòi cả
    hai ngay khi khởi tạo, kể cả khi chỉ đo truy hồi);
  - các bộ câu hỏi có mặt.

Không cần chạy van_ban_meta.py trước: RAGService.initialize() tự dựng lại hồ sơ
văn bản và đồ thị quan hệ từ chỉ mục mỗi lần khởi tạo.

Kết quả ghi ra ket_qua_do_luong.md: phiên bản mã nguồn, model, các biến RAG_*,
toàn bộ bảng in ra của từng bước và bảng chỉ số IR. Dán nguyên tệp này để phân
tích; không cần gửi kèm tệp nào khác.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests

THU_MUC_DU_AN = os.path.dirname(os.path.abspath(__file__))
DUONG_DAN_BAO_CAO = os.path.join(THU_MUC_DU_AN, "ket_qua_do_luong.md")
DUONG_DAN_BANG_IR = os.path.join(THU_MUC_DU_AN, "bang_chi_so_ir.md")
CAC_BO_CAU_HOI = ("bo_cau_hoi_benchmark.json", "bo_cau_hoi_moc_thoi_gian.json")


@dataclass
class KetQuaKiemTra:
    ten: str
    dat: bool
    chi_tiet: str


@dataclass
class KetQuaBuoc:
    ten: str
    lenh: list[str]
    ma_thoat: int
    giay: float
    dau_ra: str = field(repr=False)


def _duong_dan_chi_muc() -> str:
    # Cùng biến môi trường và mặc định với main.DUONG_DAN_LUU_INDEX; không import
    # main vì main nạp langchain và mô hình, chậm và có thể hỏng đúng lúc cần báo lỗi.
    return os.getenv("RAG_INDEX_PATH", os.path.join(THU_MUC_DU_AN, "faiss_index_data_giao_duc"))


def _model_tra_loi() -> str:
    """Cùng thứ tự ưu tiên với RAGService._tai_lua_chon_model."""
    if os.getenv("RAG_LLM_MODEL"):
        return os.environ["RAG_LLM_MODEL"]
    duong_dan = os.path.abspath(os.getenv("RAG_CAI_DAT", os.path.join(THU_MUC_DU_AN, "cai_dat.json")))
    try:
        with open(duong_dan, encoding="utf-8") as tep:
            ten = json.load(tep).get("llm_model")
        if isinstance(ten, str) and ten.strip():
            return ten.strip()
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    return "qwen3.5:4b"


def kiem_tra_chi_muc(duong_dan: str | None = None) -> KetQuaKiemTra:
    duong_dan = duong_dan or _duong_dan_chi_muc()
    thieu = [ten for ten in ("index.faiss", "index.pkl")
             if not os.path.isfile(os.path.join(duong_dan, ten))]
    if thieu:
        return KetQuaKiemTra(
            "Chỉ mục FAISS", False,
            f"thiếu {', '.join(thieu)} trong {duong_dan}. Đặt RAG_INDEX_PATH trỏ tới chỉ mục "
            "đang dùng; KHÔNG để hệ thống tự lập chỉ mục mới chỉ để đo.",
        )
    co = sum(os.path.getsize(os.path.join(duong_dan, ten)) for ten in ("index.faiss", "index.pkl"))
    return KetQuaKiemTra("Chỉ mục FAISS", True, f"{duong_dan} ({co / 1e6:.0f} MB)")


def kiem_tra_ollama(model_tra_loi: str | None = None) -> KetQuaKiemTra:
    dia_chi = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model_nhung = os.getenv("RAG_EMBEDDING_MODEL", "bge-m3")
    model_tra_loi = model_tra_loi or _model_tra_loi()
    try:
        phan_hoi = requests.get(f"{dia_chi}/api/tags", timeout=4)
        phan_hoi.raise_for_status()
        da_cai = {muc.get("name", "") for muc in phan_hoi.json().get("models", [])}
    except (requests.RequestException, ValueError) as loi:
        return KetQuaKiemTra("Ollama", False, f"không gọi được {dia_chi} ({loi}). Mở Ollama rồi chạy lại.")
    thieu = [m for m in (model_nhung, model_tra_loi) if m not in da_cai and f"{m}:latest" not in da_cai]
    if thieu:
        return KetQuaKiemTra("Ollama", False, "chưa có model: " + ", ".join(
            f"{m} (ollama pull {m})" for m in thieu))
    return KetQuaKiemTra("Ollama", True, f"{dia_chi}, nhúng {model_nhung}, trả lời {model_tra_loi}")


def kiem_tra_bo_cau_hoi(thu_muc: str = THU_MUC_DU_AN) -> KetQuaKiemTra:
    thieu = [ten for ten in CAC_BO_CAU_HOI if not os.path.isfile(os.path.join(thu_muc, ten))]
    if thieu:
        return KetQuaKiemTra("Bộ câu hỏi", False, "thiếu " + ", ".join(thieu))
    return KetQuaKiemTra("Bộ câu hỏi", True, ", ".join(CAC_BO_CAU_HOI))


def kiem_tra_tat_ca() -> list[KetQuaKiemTra]:
    return [kiem_tra_chi_muc(), kiem_tra_ollama(), kiem_tra_bo_cau_hoi()]


def phien_ban_ma_nguon() -> str:
    def git(*tham_so):
        return subprocess.run(["git", *tham_so], cwd=THU_MUC_DU_AN, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=10).stdout.strip()
    try:
        ma = git("rev-parse", "--short", "HEAD")
        nhanh = git("rev-parse", "--abbrev-ref", "HEAD")
        # Chỉ tệp .py đã sửa mới làm số đo khác mã đã commit; tệp kết quả do
        # chính lần đo ghi ra thì không.
        sua = [dong[3:] for dong in git("status", "--porcelain").splitlines() if dong.endswith(".py")]
    except (OSError, subprocess.SubprocessError):
        return "không đọc được git"
    if not ma:
        return "không đọc được git"
    return f"{ma} ({nhanh})" + (f", mã đang sửa chưa commit: {', '.join(sua)}" if sua else "")


def chay_buoc(ten: str, lenh: list[str], ghi=print) -> KetQuaBuoc:
    """Chạy một bước, vừa in ra màn hình vừa giữ lại toàn bộ đầu ra."""
    # PYTHONUNBUFFERED: stdout của tiến trình con là ống dẫn nên mặc định đệm theo
    # khối; không tắt thì tiến độ từng câu chỉ hiện ra khi cả bước đã xong.
    moi_truong = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"}
    ghi(f"\n>>> {ten}: {' '.join(lenh)}")
    bat_dau = time.monotonic()
    cac_dong = []
    try:
        tien_trinh = subprocess.Popen(
            lenh, cwd=THU_MUC_DU_AN, env=moi_truong, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        )
    except OSError as loi:
        return KetQuaBuoc(ten, lenh, -1, 0.0, f"không chạy được: {loi}")
    for dong in tien_trinh.stdout:
        dong = dong.rstrip("\n")
        cac_dong.append(dong)
        ghi(dong)
    ma_thoat = tien_trinh.wait()
    return KetQuaBuoc(ten, lenh, ma_thoat, time.monotonic() - bat_dau, "\n".join(cac_dong))


def cac_buoc_mac_dinh(bo_ir: bool, bo_moc: bool) -> list[tuple[str, list[str]]]:
    buoc = []
    if not bo_ir:
        buoc.append(("Đo IR", [sys.executable, "benchmark_chatbot.py", "--ir"]))
    if not bo_moc:
        buoc.append(("Đo hỏi theo mốc thời gian", [sys.executable, "benchmark_moc_thoi_gian.py"]))
    return buoc


def _doc_neu_co(duong_dan: str) -> str | None:
    try:
        with open(duong_dan, encoding="utf-8") as tep:
            return tep.read()
    except OSError:
        return None


def viet_bao_cao(kiem_tra: list[KetQuaKiemTra], cac_ket_qua: list[KetQuaBuoc],
                 bat_dau: datetime, bang_ir: str | None) -> str:
    dong = [
        "# Kết quả đo trên kho thật",
        "",
        f"- Thời điểm: {bat_dau:%Y-%m-%d %H:%M}",
        f"- Mã nguồn: {phien_ban_ma_nguon()}",
        f"- Python: {sys.version.split()[0]}",
    ]
    bien = {k: v for k, v in sorted(os.environ.items()) if k.startswith("RAG_") or k == "OLLAMA_BASE_URL"}
    dong.append("- Biến môi trường: " + (", ".join(f"`{k}={v}`" for k, v in bien.items()) or "mặc định"))
    dong += ["", "## Kiểm tra điều kiện", ""]
    dong += [f"- {'đạt' if k.dat else 'KHÔNG ĐẠT'} · {k.ten}: {k.chi_tiet}" for k in kiem_tra]
    for kq in cac_ket_qua:
        trang_thai = "xong" if kq.ma_thoat == 0 else f"LỖI (mã thoát {kq.ma_thoat})"
        dong += ["", f"## {kq.ten}: {trang_thai}, {kq.giay / 60:.1f} phút", "",
                 f"`{' '.join(os.path.basename(p) if i == 0 else p for i, p in enumerate(kq.lenh))}`",
                 "", "```", kq.dau_ra, "```"]
    if bang_ir and any(kq.ma_thoat == 0 and "--ir" in kq.lenh for kq in cac_ket_qua):
        dong += ["", "## Bảng chỉ số IR", "", bang_ir.strip()]
    return "\n".join(dong) + "\n"


def main(argv: list[str] | None = None) -> int:
    for luong in (sys.stdout, sys.stderr):
        if hasattr(luong, "reconfigure"):
            luong.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chi-kiem-tra", action="store_true", help="chỉ kiểm tra điều kiện, không đo")
    parser.add_argument("--bo-ir", action="store_true", help="bỏ phần đo IR")
    parser.add_argument("--bo-moc", action="store_true", help="bỏ phần đo hỏi theo mốc thời gian")
    parser.add_argument("--ra", default=DUONG_DAN_BAO_CAO, help="tệp báo cáo (mặc định ket_qua_do_luong.md)")
    tham_so = parser.parse_args(argv)

    bat_dau = datetime.now()
    kiem_tra = kiem_tra_tat_ca()
    print("Kiểm tra điều kiện:")
    for k in kiem_tra:
        print(f"  [{'x' if k.dat else ' '}] {k.ten}: {k.chi_tiet}")
    if not all(k.dat for k in kiem_tra):
        print("\nChưa đủ điều kiện; sửa các mục chưa đạt ở trên rồi chạy lại.")
        return 2
    if tham_so.chi_kiem_tra:
        return 0

    cac_ket_qua = []
    for ten, lenh in cac_buoc_mac_dinh(tham_so.bo_ir, tham_so.bo_moc):
        cac_ket_qua.append(chay_buoc(ten, lenh))
        # Ghi sau từng bước: bước sau hỏng hay bị ngắt thì số của bước trước vẫn còn.
        with open(tham_so.ra, "w", encoding="utf-8") as tep:
            tep.write(viet_bao_cao(kiem_tra, cac_ket_qua, bat_dau, _doc_neu_co(DUONG_DAN_BANG_IR)))

    loi = [kq.ten for kq in cac_ket_qua if kq.ma_thoat != 0]
    print(f"\nĐã ghi {tham_so.ra}" + (f" - có bước lỗi: {', '.join(loi)}" if loi else ""))
    return 1 if loi else 0


if __name__ == "__main__":
    raise SystemExit(main())
