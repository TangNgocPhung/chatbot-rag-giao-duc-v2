"""
PHÂN LOẠI Ý ĐỊNH CÂU HỎI BẰNG KNN (k láng giềng gần nhất)
=========================================================
Mô hình học máy tự train của dự án, chạy TRƯỚC mô hình ngôn ngữ: đọc câu hỏi
rồi đoán người hỏi muốn gì - tra cứu văn bản, tính lương, hỏi định mức tiết
dạy, tính điểm/xếp loại học sinh, làm một phép tính, chào hỏi, hay hỏi một
chuyện không dính tới giáo dục.

Vì sao KNN:

1. Kho đã có sẵn một không gian vector tốt - bge-m3, model nhúng của chính chỉ
   mục FAISS. Câu cùng ý định nằm gần nhau trong không gian đó, nên chỉ cần
   "tìm k câu mẫu giống nhất rồi bỏ phiếu" là đủ, không phải học thêm tầng nào.
2. "Train" chỉ là nhúng vài trăm câu mẫu và cất lại: vài chục giây trên CPU,
   thêm câu mẫu mới không phải train lại từ đầu.
3. Giải thích được từng quyết định: giao diện hiện luôn mấy câu mẫu gần nhất
   đã bỏ phiếu, ai cũng kiểm lại được vì sao máy đoán như vậy.

Dùng vào việc gì (rag_service.py):

- Câu nhận ra chắc chắn là ngoài phạm vi (giá vàng, thời tiết, nấu ăn...) thì
  từ chối ngay, không tốn lượt truy hồi + hàng chục giây sinh văn bản trên CPU.
- Câu chào hỏi / cảm ơn thì đáp lời chào kèm câu gợi ý, thay vì đi tìm "xin
  chào" trong kho văn bản pháp luật rồi trả lời "không tìm thấy".
- Mọi câu khác vẫn đi đường cũ; nhãn chỉ hiện lên cho người dùng xem. Công cụ
  tính vẫn chọn bằng quy tắc - quy tắc vừa nhận ý định vừa bóc được tham số
  (hạng, bậc, hệ số...), KNN chỉ nhận được ý định.

Chỉ hành động khi đủ chắc (tỉ lệ phiếu >= NGUONG[nhãn]) và theo luật riêng
cho câu nối tiếp / câu đang lọc phạm vi (hanh_dong_cho_cau). Ngưỡng chọn bằng
số liệu: xem `python phan_loai_y_dinh.py danh_gia`.

Cách dùng:
    python phan_loai_y_dinh.py train            # nhúng câu mẫu, lưu mô hình
    python phan_loai_y_dinh.py danh_gia         # chọn k, đo trên tập test, so sánh mô hình
    python phan_loai_y_dinh.py hoi "giá vàng hôm nay"
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
from collections import Counter

import numpy as np

from hybrid_retrieval import bo_dau

THU_MUC = os.path.dirname(os.path.abspath(__file__))
DUONG_DU_LIEU = os.path.join(THU_MUC, "du_lieu_y_dinh.json")
DUONG_BENCHMARK = os.path.join(THU_MUC, "bo_cau_hoi_benchmark.json")
DUONG_MO_HINH = os.path.join(THU_MUC, "mo_hinh_y_dinh.npz")
DUONG_BO_NHO_VECTOR = os.path.join(THU_MUC, "bo_nho_vector_y_dinh.npz")
DUONG_KET_QUA = os.path.join(THU_MUC, "ket_qua_phan_loai_y_dinh.json")
DUONG_BANG = os.path.join(THU_MUC, "bang_phan_loai_y_dinh.md")

# k chọn bằng kiểm định chéo bỏ-một (danh_gia); mô hình đã lưu mang theo k của nó.
# Không thử k=1: một láng giềng thì độ tin cậy luôn là 100%, mất luôn cái
# ngưỡng dùng để quyết định có được tự chặn câu hỏi hay không.
K_MAC_DINH = 7
CAC_K_THU = (3, 5, 7, 9, 11, 15)
# Tỉ lệ phiếu tối thiểu để được hành động thay người dùng. Lời chào đòi cao
# hơn: đáp "Xin chào!" cho một câu hỏi thật trông vô lý hơn hẳn một lần từ
# chối, mà lời chào thật gần như luôn được đủ phiếu (chạy thử 6/10/2026: "Ai là
# tổng thống Mỹ?" được 0,7 phiếu chào hỏi vì mẫu "Bạn là ai?").
NGUONG = {
    "ngoai_pham_vi": float(os.getenv("RAG_Y_DINH_NGUONG", "0.7")),
    "chao_hoi": float(os.getenv("RAG_Y_DINH_NGUONG_CHAO", "0.9")),
}
NHAN_HANH_DONG = ("ngoai_pham_vi", "chao_hoi")
CAC_NGUONG_THU = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)

# Câu của bộ benchmark mang nhãn theo nhóm: mọi nhóm có trong kho là tra cứu.
NHAN_THEO_NHOM_BENCHMARK = {"ngoai_pham_vi": "ngoai_pham_vi"}


def bat() -> bool:
    return os.getenv("RAG_PHAN_LOAI_Y_DINH", "1") == "1"


# ============================================================
# DỮ LIỆU
# ============================================================
def nap_du_lieu(
    duong_du_lieu: str = DUONG_DU_LIEU, duong_benchmark: str | None = DUONG_BENCHMARK
) -> tuple[dict[str, str], list[tuple[str, str]], list[dict]]:
    """Trả về (tên hiển thị của nhãn, tập train, tập test).

    Tập test gồm câu thật trong du_lieu_y_dinh.json cộng toàn bộ bộ benchmark
    của chatbot - nạp trực tiếp từ tệp benchmark chứ không chép sang, để hai
    bên không lệch nhau khi benchmark được sửa."""
    with open(duong_du_lieu, encoding="utf-8") as f:
        du_lieu = json.load(f)
    ten_nhan = du_lieu["nhan"]
    train = [
        (cau, nhan) for nhan, cac_cau in du_lieu["train"].items() for cau in cac_cau
    ]
    test = [dict(muc) for muc in du_lieu.get("test", [])]
    if duong_benchmark and os.path.exists(duong_benchmark):
        with open(duong_benchmark, encoding="utf-8") as f:
            for muc in json.load(f)["cau_hoi"]:
                test.append({
                    "cau_hoi": muc["cau_hoi"],
                    "nhan": NHAN_THEO_NHOM_BENCHMARK.get(muc.get("nhom", ""), "tra_cuu"),
                    "nguon": "benchmark",
                })
    la = sorted(({nhan for _, nhan in train} | {m["nhan"] for m in test})
                - set(ten_nhan))
    if la:
        raise ValueError(f"Nhãn không khai báo trong 'nhan': {la}")
    return ten_nhan, train, test


def van_tay(train: list[tuple[str, str]], ten_model_nhung: str) -> str:
    """Đổi câu mẫu hay đổi model nhúng thì mô hình cũ không dùng được nữa."""
    h = hashlib.sha1(ten_model_nhung.encode("utf-8"))
    for cau, nhan in train:
        h.update(f"\x00{nhan}\x01{cau}".encode("utf-8"))
    return h.hexdigest()[:16]


def chuan_hoa(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=np.float32)
    do_dai = np.linalg.norm(X, axis=-1, keepdims=True)
    return X / np.maximum(do_dai, 1e-12)


def nhung(cac_cau: list[str], embeddings, duong_bo_nho: str | None = None,
          lo: int = 32) -> np.ndarray:
    """Nhúng theo lô; có bộ nhớ thì câu đã nhúng lần trước không phải gọi lại."""
    bo_nho: dict[str, np.ndarray] = {}
    if duong_bo_nho and os.path.exists(duong_bo_nho):
        with np.load(duong_bo_nho, allow_pickle=False) as f:
            bo_nho = dict(zip(f["cau"].tolist(), f["X"]))
    can_nhung = [c for c in dict.fromkeys(cac_cau) if c not in bo_nho]
    for i in range(0, len(can_nhung), lo):
        phan = can_nhung[i:i + lo]
        for cau, v in zip(phan, embeddings.embed_documents(phan)):
            bo_nho[cau] = np.asarray(v, dtype=np.float32)
    if duong_bo_nho and can_nhung:
        cau = list(bo_nho)
        np.savez_compressed(duong_bo_nho, cau=np.array(cau), X=np.stack([bo_nho[c] for c in cau]))
    return chuan_hoa(np.stack([bo_nho[c] for c in cac_cau]))


# ============================================================
# MÔ HÌNH KNN
# ============================================================
class BoPhanLoaiKNN:
    """KNN trên vector đã chuẩn hoá: tích vô hướng chính là độ tương đồng
    cosin. Bỏ phiếu có trọng số theo độ tương đồng, nên một láng giềng rất
    giống nặng ký hơn một láng giềng chỉ hơi giống."""

    def __init__(self, X: np.ndarray, nhan: list[str], cau: list[str],
                 k: int = K_MAC_DINH, van_tay: str = ""):
        self.X = chuan_hoa(X)
        self.nhan = np.array(nhan)
        self.cau = list(cau)
        self.k = int(k)
        self.van_tay = van_tay
        self.cac_nhan = sorted(set(nhan))

    # --- lưu / nạp ---------------------------------------------------------
    def luu(self, duong: str = DUONG_MO_HINH) -> None:
        tam = duong + ".tmp.npz"
        np.savez_compressed(
            tam, X=self.X, nhan=self.nhan, cau=np.array(self.cau),
            k=np.array(self.k), van_tay=np.array(self.van_tay),
        )
        os.replace(tam, duong)

    @classmethod
    def nap(cls, duong: str = DUONG_MO_HINH) -> "BoPhanLoaiKNN":
        with np.load(duong, allow_pickle=False) as f:
            return cls(f["X"], f["nhan"].tolist(), f["cau"].tolist(),
                       int(f["k"]), str(f["van_tay"]))

    # --- dự đoán -----------------------------------------------------------
    def bo_phieu(self, do_giong: np.ndarray, k: int | None = None,
                 bo_chinh_no: bool = False) -> tuple[list[str], np.ndarray, np.ndarray]:
        """do_giong: ma trận (n câu hỏi × số câu mẫu). Trả về nhãn đoán, độ tin
        cậy (tỉ lệ phiếu của nhãn thắng) và chỉ số k láng giềng của từng câu.

        bo_chinh_no: dùng cho kiểm định chéo bỏ-một - câu mẫu không được tự
        bầu cho chính nó."""
        k = min(k or self.k, len(self.cau) - (1 if bo_chinh_no else 0))
        S = np.array(do_giong, dtype=np.float32, copy=True)
        if bo_chinh_no:
            np.fill_diagonal(S, -np.inf)
        idx = np.argsort(-S, axis=1)[:, :k]
        trong_so = np.clip(np.take_along_axis(S, idx, axis=1), 0.0, None)
        nhan_lg = self.nhan[idx]
        cac_nhan = np.array(self.cac_nhan)
        # phieu[i, j] = tổng trọng số láng giềng của câu i mang nhãn j
        phieu = np.stack([(trong_so * (nhan_lg == n)).sum(axis=1) for n in cac_nhan], axis=1)
        thang = phieu.argmax(axis=1)
        tong = np.maximum(phieu.sum(axis=1), 1e-12)
        return cac_nhan[thang].tolist(), phieu[np.arange(len(thang)), thang] / tong, idx

    def du_doan_nhieu(self, V: np.ndarray, k: int | None = None) -> tuple[list[str], np.ndarray]:
        nhan, tin_cay, _ = self.bo_phieu(chuan_hoa(V) @ self.X.T, k)
        return nhan, tin_cay

    def du_doan(self, vector, ten_nhan: dict[str, str] | None = None,
                so_lang_gieng_hien: int = 3) -> dict:
        v = chuan_hoa(np.asarray(vector, dtype=np.float32)[None, :])
        S = v @ self.X.T
        nhan, tin_cay, idx = self.bo_phieu(S)
        ket_qua = {
            "nhan": nhan[0],
            "ten_nhan": (ten_nhan or {}).get(nhan[0], nhan[0]),
            "do_tin_cay": round(float(tin_cay[0]), 3),
            "k": self.k,
            "lang_gieng": [
                {
                    "cau_hoi": self.cau[j],
                    "nhan": str(self.nhan[j]),
                    "ten_nhan": (ten_nhan or {}).get(str(self.nhan[j]), str(self.nhan[j])),
                    "do_giong": round(float(S[0, j]), 3),
                }
                for j in idx[0][:so_lang_gieng_hien]
            ],
        }
        return ket_qua


def train(embeddings, ten_model_nhung: str, k: int | None = None,
          duong_luu: str | None = DUONG_MO_HINH) -> BoPhanLoaiKNN:
    _, du_train, _ = nap_du_lieu(duong_benchmark=None)
    cac_cau = [c for c, _ in du_train]
    X = nhung(cac_cau, embeddings)
    bo = BoPhanLoaiKNN(X, [n for _, n in du_train], cac_cau,
                       k=k or K_MAC_DINH, van_tay=van_tay(du_train, ten_model_nhung))
    if duong_luu:
        bo.luu(duong_luu)
    return bo


# ============================================================
# DÙNG TRONG DỊCH VỤ
# ============================================================
class PhanLoaiYDinh:
    """Giữ một bộ phân loại cho cả dịch vụ. Chưa sẵn sàng thì du_doan trả None
    và câu hỏi đi đường cũ - phân loại ý định là phần thêm, không được làm hỏng
    luồng trả lời."""

    def __init__(self, duong_mo_hinh: str = DUONG_MO_HINH):
        self.duong_mo_hinh = duong_mo_hinh
        self.bo: BoPhanLoaiKNN | None = None
        self.ten_nhan: dict[str, str] = {}
        self.trang_thai = "chua_nap"
        self._khoa = threading.Lock()

    def chuan_bi(self, embeddings, ten_model_nhung: str) -> None:
        """Nạp mô hình đã lưu; câu mẫu hay model nhúng đổi thì train lại."""
        if not bat():
            self.trang_thai = "tat"
            return
        with self._khoa:
            try:
                ten_nhan, du_train, _ = nap_du_lieu(duong_benchmark=None)
                can_co = van_tay(du_train, ten_model_nhung)
                bo = None
                if os.path.exists(self.duong_mo_hinh):
                    bo = BoPhanLoaiKNN.nap(self.duong_mo_hinh)
                    if bo.van_tay != can_co:
                        bo = None
                if bo is None:
                    self.trang_thai = "dang_train"
                    bat_dau = time.perf_counter()
                    # Giữ k của mô hình cũ: k là kết quả của lần đánh giá gần nhất.
                    k_cu = BoPhanLoaiKNN.nap(self.duong_mo_hinh).k if os.path.exists(self.duong_mo_hinh) else None
                    bo = train(embeddings, ten_model_nhung, k=k_cu, duong_luu=self.duong_mo_hinh)
                    print(f"🧭 Đã train bộ phân loại ý định: {len(bo.cau)} câu mẫu, "
                          f"k={bo.k}, {time.perf_counter() - bat_dau:.0f} giây")
                self.ten_nhan, self.bo = ten_nhan, bo
                self.trang_thai = "san_sang"
            except Exception as exc:
                self.trang_thai = "loi"
                print(f"⚠️  Không chuẩn bị được bộ phân loại ý định: {exc}")

    def du_doan(self, vector) -> dict | None:
        if self.bo is None or vector is None or not bat():
            return None
        try:
            return self.bo.du_doan(vector, self.ten_nhan)
        except Exception as exc:
            print(f"⚠️  Phân loại ý định lỗi: {exc}")
            return None


def du_chac_de_hanh_dong(y_dinh: dict | None, nguong: float | None = None) -> str | None:
    """Nhãn mà dịch vụ được phép tự hành động theo (chặn / đáp lời chào), hoặc None."""
    if not y_dinh or y_dinh.get("nhan") not in NHAN_HANH_DONG:
        return None
    if y_dinh.get("do_tin_cay", 0.0) < (NGUONG[y_dinh["nhan"]] if nguong is None else nguong):
        return None
    return y_dinh["nhan"]


_LOI_CHAO = re.compile(r"\b(xin chao|chao|hello|hi|cam on|cam ta|thank|thanks|tam biet|bye|hen gap lai)\b")
SO_TU_LOI_CHAO_TOI_DA = 6


def hanh_dong_cho_cau(y_dinh: dict | None, cau_hoi: str, co_lich_su: bool,
                      co_loc_pham_vi: bool) -> str | None:
    """Việc dịch vụ được tự làm thay mô hình ngôn ngữ, hoặc None (đi đường thường).

    Giữa hội thoại, câu nối tiếp đứng một mình bị KNN đọc sai: "còn giáo viên
    thì sao" nghe như lạc đề, "nói rõ hơn", "tại sao vậy" nằm sát câu chào
    hỏi (đo 6/10/2026: 0,9 phiếu chào hỏi). Nên khi có lịch sử thì không bao
    giờ tự chặn, và chỉ đáp lời chào khi câu ngắn VÀ có chữ chào / cảm ơn /
    tạm biệt thật. Đang lọc phạm vi thì người hỏi đã khoanh vùng kho, không
    chặn thay họ."""
    hanh_dong = du_chac_de_hanh_dong(y_dinh)
    if hanh_dong == "ngoai_pham_vi" and (co_lich_su or co_loc_pham_vi):
        return None
    if hanh_dong == "chao_hoi" and co_lich_su:
        chu = bo_dau(cau_hoi).lower()
        if len(chu.split()) > SO_TU_LOI_CHAO_TOI_DA or not _LOI_CHAO.search(chu):
            return None
    return hanh_dong


# ============================================================
# ĐÁNH GIÁ
# ============================================================
def _do_luong(dung: list[str], doan: list[str], cac_nhan: list[str]) -> dict:
    """Accuracy, precision/recall/F1 từng lớp, macro-F1 và ma trận nhầm lẫn -
    tự tính để không bắt máy chủ cài scikit-learn."""
    dung_a, doan_a = np.array(dung), np.array(doan)
    tung_lop = {}
    for n in cac_nhan:
        tp = int(((doan_a == n) & (dung_a == n)).sum())
        so_doan, so_that = int((doan_a == n).sum()), int((dung_a == n).sum())
        p = tp / so_doan if so_doan else 0.0
        r = tp / so_that if so_that else 0.0
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        tung_lop[n] = {"precision": round(p, 4), "recall": round(r, 4),
                       "f1": round(f1, 4), "so_cau": so_that}
    co_mat = [n for n in cac_nhan if tung_lop[n]["so_cau"]]
    return {
        "accuracy": round(float((dung_a == doan_a).mean()), 4),
        "macro_f1": round(float(np.mean([tung_lop[n]["f1"] for n in co_mat])), 4),
        "tung_lop": tung_lop,
        "ma_tran_nham_lan": {
            that: {du: int(((dung_a == that) & (doan_a == du)).sum()) for du in cac_nhan}
            for that in cac_nhan
        },
    }


def _so_sanh_mo_hinh(X_tr, y_tr, X_te, y_te, cau_tr, cau_te, cac_nhan) -> dict:
    """Đặt KNN cạnh vài mô hình quen thuộc. Chỉ chạy khi có scikit-learn - đây
    là việc của người viết báo cáo, máy chủ không cần."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.naive_bayes import GaussianNB, MultinomialNB
        from sklearn.neighbors import KNeighborsClassifier
        from sklearn.pipeline import make_pipeline
        from sklearn.svm import LinearSVC
    except ImportError:
        return {}
    ket_qua = {}

    def do(ten, mo_hinh, Xa, Xb, thoi_gian_train=None):
        bat_dau = time.perf_counter()
        mo_hinh.fit(Xa, y_tr)
        giay_train = time.perf_counter() - bat_dau
        doan = list(mo_hinh.predict(Xb))
        m = _do_luong(y_te, doan, cac_nhan)
        ket_qua[ten] = {"accuracy": m["accuracy"], "macro_f1": m["macro_f1"],
                        "giay_train": round(giay_train, 3)}

    do("Logistic Regression (bge-m3)", LogisticRegression(max_iter=2000, C=10), X_tr, X_te)
    do("SVM tuyến tính (bge-m3)", LinearSVC(C=1.0), X_tr, X_te)
    do("Naive Bayes Gauss (bge-m3)", GaussianNB(), X_tr, X_te)
    do("KNN của scikit-learn k=7 (bge-m3, đối chứng)",
       KNeighborsClassifier(n_neighbors=7, metric="cosine", weights="distance"), X_tr, X_te)
    # Không dùng vector bge-m3: cho thấy phần đóng góp của không gian nhúng.
    do("KNN k=7 (TF-IDF n-gram ký tự)",
       make_pipeline(TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True),
                     KNeighborsClassifier(n_neighbors=7, metric="cosine", weights="distance")),
       cau_tr, cau_te)
    do("Naive Bayes đa thức (TF-IDF từ)",
       make_pipeline(TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), MultinomialNB(alpha=0.1)),
       cau_tr, cau_te)
    return ket_qua


def danh_gia(embeddings, ten_model_nhung: str) -> dict:
    ten_nhan, du_train, du_test = nap_du_lieu()
    cac_nhan = list(ten_nhan)
    cau_tr = [c for c, _ in du_train]
    y_tr = [n for _, n in du_train]
    cau_te = [m["cau_hoi"] for m in du_test]
    y_te = [m["nhan"] for m in du_test]
    print(f"Nhúng {len(cau_tr)} câu train + {len(cau_te)} câu test bằng {ten_model_nhung}...")
    X_tr = nhung(cau_tr, embeddings, DUONG_BO_NHO_VECTOR)
    X_te = nhung(cau_te, embeddings, DUONG_BO_NHO_VECTOR)

    # 1. Chọn k bằng kiểm định chéo bỏ-một trên tập train: với KNN thì làm được
    #    trọn vẹn chỉ bằng một ma trận tương đồng, không phải train lại lần nào.
    bo = BoPhanLoaiKNN(X_tr, y_tr, cau_tr, van_tay=van_tay(du_train, ten_model_nhung))
    S_tr = bo.X @ bo.X.T
    chon_k = {}
    for k in CAC_K_THU:
        doan, _, _ = bo.bo_phieu(S_tr, k, bo_chinh_no=True)
        chon_k[k] = _do_luong(y_tr, doan, cac_nhan)["macro_f1"]
    # Hoà điểm thì lấy k lớn hơn: bỏ phiếu đông người ít bị một câu mẫu lạ kéo lệch.
    k_tot = max(chon_k, key=lambda k: (chon_k[k], k))
    bo.k = k_tot

    # 2. Đo trên tập test - tập chưa hề dùng để chọn k.
    doan_te, tin_cay_te = bo.du_doan_nhieu(X_te)
    tong = _do_luong(y_te, doan_te, cac_nhan)
    theo_nguon = {}
    for nguon in sorted({m["nguon"] for m in du_test}):
        chi_so = [i for i, m in enumerate(du_test) if m["nguon"] == nguon]
        theo_nguon[nguon] = {
            "so_cau": len(chi_so),
            "accuracy": round(float(np.mean([doan_te[i] == y_te[i] for i in chi_so])), 4),
        }

    # 3. Ngưỡng hành động: chặn sớm / đáp lời chào. Thứ cần bằng 0 là số câu
    #    trong phạm vi bị chặn nhầm - mỗi câu như vậy là một người bị từ chối oan.
    nguong = {}
    for t in CAC_NGUONG_THU:
        dong = {}
        for nhan_hd in NHAN_HANH_DONG:
            hanh_dong = [doan_te[i] == nhan_hd and tin_cay_te[i] >= t for i in range(len(y_te))]
            so_that = sum(1 for y in y_te if y == nhan_hd)
            dong[nhan_hd] = {
                "bat_dung": sum(1 for i, h in enumerate(hanh_dong) if h and y_te[i] == nhan_hd),
                "tren_tong": so_that,
                "bat_nham": sum(1 for i, h in enumerate(hanh_dong) if h and y_te[i] != nhan_hd),
                "cau_bat_nham": [cau_te[i] for i, h in enumerate(hanh_dong) if h and y_te[i] != nhan_hd],
            }
        nguong[str(t)] = dong

    sai = [
        {"cau_hoi": cau_te[i], "that": y_te[i], "doan": doan_te[i],
         "do_tin_cay": round(float(tin_cay_te[i]), 3), "nguon": du_test[i]["nguon"]}
        for i in range(len(y_te)) if doan_te[i] != y_te[i]
    ]
    ket_qua = {
        "thoi_diem": time.strftime("%Y-%m-%d %H:%M"),
        "model_nhung": ten_model_nhung,
        "so_cau_train": len(cau_tr),
        "so_cau_train_theo_nhan": dict(Counter(y_tr)),
        "so_cau_test": len(cau_te),
        "so_cau_test_theo_nhan": dict(Counter(y_te)),
        "kiem_dinh_cheo_bo_mot": {str(k): v for k, v in chon_k.items()},
        "k_chon": k_tot,
        "test": tong,
        "test_theo_nguon": theo_nguon,
        "nguong_hanh_dong": nguong,
        "nguong_dang_dung": dict(NGUONG),
        "cau_sai": sai,
        "so_sanh_mo_hinh": {
            f"KNN tự cài k={k_tot} (bge-m3, phiếu theo độ tương đồng)":
                {"accuracy": tong["accuracy"], "macro_f1": tong["macro_f1"], "giay_train": 0.0},
            **_so_sanh_mo_hinh(X_tr, y_tr, X_te, y_te, cau_tr, cau_te, cac_nhan),
        },
    }
    bo.luu(DUONG_MO_HINH)
    with open(DUONG_KET_QUA, "w", encoding="utf-8") as f:
        json.dump(ket_qua, f, ensure_ascii=False, indent=1)
    with open(DUONG_BANG, "w", encoding="utf-8") as f:
        f.write(bang_markdown(ket_qua, ten_nhan))
    return ket_qua


def _so(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def bang_markdown(kq: dict, ten_nhan: dict[str, str]) -> str:
    cac_nhan = list(ten_nhan)
    dong = [
        "# Bộ phân loại ý định câu hỏi (KNN)",
        "",
        f"Đo lúc {kq['thoi_diem']} · model nhúng `{kq['model_nhung']}` · "
        f"{kq['so_cau_train']} câu train · {kq['so_cau_test']} câu test · k = {kq['k_chon']}.",
        "Sinh bởi `python phan_loai_y_dinh.py danh_gia`; tập test là câu thật (bộ benchmark, "
        "lịch sử chat, câu trong test của các công cụ tính), không trùng câu nào với tập train.",
        "",
        "## Chọn k (kiểm định chéo bỏ-một trên tập train)",
        "",
        "| k | " + " | ".join(kq["kiem_dinh_cheo_bo_mot"]) + " |",
        "|---|" + "---|" * len(kq["kiem_dinh_cheo_bo_mot"]),
        "| macro-F1 | " + " | ".join(_so(v) for v in kq["kiem_dinh_cheo_bo_mot"].values()) + " |",
        "",
        "## Kết quả trên tập test",
        "",
        f"Accuracy **{_so(kq['test']['accuracy'])}** · macro-F1 **{_so(kq['test']['macro_f1'])}**",
        "",
        "| Nhãn | Precision | Recall | F1 | Số câu |",
        "|---|---|---|---|---|",
    ]
    for n in cac_nhan:
        m = kq["test"]["tung_lop"][n]
        if m["so_cau"]:
            dong.append(f"| {ten_nhan[n]} | {_so(m['precision'])} | {_so(m['recall'])} | "
                        f"{_so(m['f1'])} | {m['so_cau']} |")
    dong += ["", "Theo nguồn câu hỏi: " + " · ".join(
        f"{n}: {_so(v['accuracy'])} ({v['so_cau']} câu)" for n, v in kq["test_theo_nguon"].items()
    ), "", "### Ma trận nhầm lẫn (hàng: nhãn thật, cột: nhãn đoán)", ""]
    co_mat = [n for n in cac_nhan if kq["test"]["tung_lop"][n]["so_cau"]
              or any(kq["test"]["ma_tran_nham_lan"][t][n] for t in cac_nhan)]
    dong.append("| | " + " | ".join(ten_nhan[n] for n in co_mat) + " |")
    dong.append("|---|" + "---|" * len(co_mat))
    for t in co_mat:
        dong.append(f"| {ten_nhan[t]} | " + " | ".join(
            str(kq["test"]["ma_tran_nham_lan"][t][d]) for d in co_mat) + " |")
    dong += ["", "## Ngưỡng tự hành động", "",
             "Câu được đoán là ngoài phạm vi / chào hỏi với độ tin cậy từ ngưỡng trở lên thì "
             "được trả lời ngay, không qua truy hồi và mô hình ngôn ngữ. Cột *nhầm* là số câu "
             "lẽ ra phải đi đường thường mà bị chặn - cần bằng 0. Dấu * là ngưỡng đang dùng.", "",
             "| Ngưỡng | Chặn ngoài phạm vi đúng | Chặn nhầm | Đáp lời chào đúng | Đáp nhầm |",
             "|---|---|---|---|---|"]
    for t, v in kq["nguong_hanh_dong"].items():
        a, b = v["ngoai_pham_vi"], v["chao_hoi"]
        sao = {n: " *" if float(t) == kq["nguong_dang_dung"][n] else "" for n in NHAN_HANH_DONG}
        dong.append(f"| {t.replace('.', ',')} | {a['bat_dung']}/{a['tren_tong']}{sao['ngoai_pham_vi']} | "
                    f"{a['bat_nham']} | {b['bat_dung']}/{b['tren_tong']}{sao['chao_hoi']} | {b['bat_nham']} |")
    dong += ["", "## So sánh với mô hình khác (cùng tập train/test)", "",
             "| Mô hình | Accuracy | macro-F1 |", "|---|---|---|"]
    for ten, m in kq["so_sanh_mo_hinh"].items():
        dong.append(f"| {ten} | {_so(m['accuracy'])} | {_so(m['macro_f1'])} |")
    if kq["cau_sai"]:
        dong += ["", "## Câu đoán sai trên tập test", "",
                 "| Câu hỏi | Nhãn thật | Đoán | Tin cậy |", "|---|---|---|---|"]
        for s in kq["cau_sai"]:
            dong.append(f"| {s['cau_hoi'].replace('|', '/')} | {ten_nhan[s['that']]} | "
                        f"{ten_nhan[s['doan']]} | {_so(s['do_tin_cay'])} |")
    return "\n".join(dong) + "\n"


def _embeddings_mac_dinh():
    from langchain_ollama import OllamaEmbeddings
    ten = os.getenv("RAG_EMBEDDING_MODEL", "bge-m3")
    return OllamaEmbeddings(
        model=ten, base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ), ten


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    lenh = sys.argv[1] if len(sys.argv) > 1 else "danh_gia"
    emb, ten_model = _embeddings_mac_dinh()
    if lenh == "train":
        bo = train(emb, ten_model)
        print(f"Đã lưu {DUONG_MO_HINH}: {len(bo.cau)} câu mẫu, k={bo.k}")
    elif lenh == "danh_gia":
        kq = danh_gia(emb, ten_model)
        print(f"k={kq['k_chon']} · accuracy {kq['test']['accuracy']} · macro-F1 {kq['test']['macro_f1']}")
        print(f"Chi tiết: {DUONG_BANG}")
    elif lenh == "hoi":
        pl = PhanLoaiYDinh()
        pl.chuan_bi(emb, ten_model)
        print(json.dumps(pl.du_doan(emb.embed_query(" ".join(sys.argv[2:]))),
                         ensure_ascii=False, indent=1))
    else:
        print(__doc__)
