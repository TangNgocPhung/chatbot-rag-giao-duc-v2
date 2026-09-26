#!/usr/bin/env bash
# =====================================================================
#  DAY MA NGUON + CHI MUC + KHOA NUT QUAN TRI
# =====================================================================
#  Chay TREN MAY WINDOWS nay (Git Bash):
#      bash trien_khai_vps/02_day_ma_nguon.sh <IP_VPS> [nguoi_dung_ssh]
#
#  Khong day: kho tai lieu 4,9 GB (dung 03_day_tai_lieu.sh), .venv,
#  __pycache__, lich su chat, cac ban sao luu *.truoc-khi-*.
#  Cung KHONG day trang thai rieng cua may chu (so ghi chep, FAISS,
#  drive_state.json, cai_dat.json) - xem DAY_CHI_MUC ben duoi.
#
#  MO HINH BAO VE (khac ban chay o may ca nhan):
#    - Ung dung chay KHONG mat khau: ai co dia chi cung hoi dap duoc.
#    - Caddy chan rieng cac duong dan quan tri bang HTTP Basic, mat khau
#      lay tu mat_khau.bat va bam bcrypt ngay tren VPS.
#  Mat khau khong bao gio in ra man hinh va khong nam tren dong lenh.
# =====================================================================
set -euo pipefail

MAY_CHU="${1:-${VPS_HOST:-}}"
NGUOI_SSH="${2:-${SSH_USER:-root}}"
KHOA="${SSH_KEY:-$HOME/.ssh/ovh_vps}"
THU_MUC_XA="/opt/chatbot-rag"

# Mac dinh CHI day ma nguon. So ghi chep, FAISS, drive_state.json va cai_dat.json
# la trang thai rieng cua may chu: VPS tu chay cap nhat chi muc ban dem, nguoi
# dung upload tai lieu qua giao dien, cai dat chon ngay tren UI. Ban o may nay
# gan nhu luc nao cung cu hon, day de len la xoa mat phan viec do va bat VPS
# embed lai hang gio. Chi lan trien khai DAU TIEN - VPS chua co chi muc nao -
# moi can:
#     DAY_CHI_MUC=1 bash trien_khai_vps/02_day_ma_nguon.sh <IP_VPS>
DAY_CHI_MUC="${DAY_CHI_MUC:-0}"

[ -n "$MAY_CHU" ] || { echo "[LOI] Thieu dia chi VPS. Vi du: bash $0 203.0.113.10 root"; exit 1; }
cd "$(dirname "$0")/.."
[ -f mat_khau.bat ] || { echo "[LOI] Khong thay mat_khau.bat - can co de khoa cac nut quan tri."; exit 1; }
[ -f "$KHOA" ] || { echo "[LOI] Khong thay khoa SSH $KHOA"; exit 1; }

SSH="ssh -i $KHOA -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 $NGUOI_SSH@$MAY_CHU"
SCP="scp -i $KHOA -o StrictHostKeyChecking=accept-new"
NHU_ROOT="sudo"
NHU_RAG="sudo -u rag"

buoc() { echo; echo "--- $*"; }

# ---------------------------------------------------------------------
# KIEM TRA TRUOC KHI DAY. Kich ban nen nguyen thu muc tren may nay, nen mot
# lan merge do dang (con dau <<<<<<< / >>>>>>>) cung len VPS nguyen xi: ngay
# 26/09/2026 api.py dinh dau xung dot, uvicorn chet ngay luc import, systemd
# khoi dong lai 1245 lan va Caddy tra 502 cho moi nguoi. Moi loi duoi day
# dung han TRUOC khi dong vao VPS. Khan cap that su moi bo qua: BO_KIEM_TRA=1.
# ---------------------------------------------------------------------
# Chay ca o may nay lan tren VPS (Python cua VPS co the cu hon may nay).
# compile() thay vi py_compile de khong sinh __pycache__ vao thu muc du an.
KIEM_CU_PHAP_PY='
import sys
loi = 0
for ten in sys.argv[1:]:
    try:
        with open(ten, "rb") as f:
            compile(f.read(), ten, "exec", dont_inherit=True)
    except (SyntaxError, ValueError) as exc:
        dong = getattr(exc, "lineno", None) or "?"
        print("[LOI] %s:%s: %s" % (ten, dong, exc))
        loi = 1
sys.exit(loi)
'

kiem_tra_truoc_khi_day() {
  local loi=0 py="" p tt

  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    for tt in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
      if [ -e "$(git rev-parse --git-path "$tt")" ]; then
        echo "[LOI] Git dang lam do dang ($tt). Hoan tat hoac huy truoc"
        echo "      (git merge --abort / git rebase --abort / git cherry-pick --abort)."
        loi=1
        break
      fi
    done
    local chua_giai
    chua_giai="$(git diff --name-only --diff-filter=U)"
    if [ -n "$chua_giai" ]; then
      echo "[LOI] Con tep xung dot chua giai quyet:"
      echo "$chua_giai" | sed 's/^/      /'
      loi=1
    fi

    # Chi canh bao: day ban cu hon GitHub hoac day kem thay doi chua commit
    # doi khi la co y, nhung phai biet minh dang day cai gi.
    if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
      GIT_TERMINAL_PROMPT=0 timeout 20 git fetch -q 2>/dev/null || true
      local cham
      cham="$(git rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)"
      if [ "$cham" -gt 0 ]; then
        echo "[canh bao] Dang cham $cham commit so voi $(git rev-parse --abbrev-ref '@{u}') - nen git pull truoc."
      fi
    fi
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
      echo "[canh bao] Co thay doi chua commit - chung cung se duoc day len:"
      git status --short --untracked-files=no | sed 's/^/      /'
    fi
    echo "    Se day: $(git log --oneline -1) (origin: $(git remote get-url origin 2>/dev/null || echo '?'))"
  else
    echo "[canh bao] Khong phai kho git - bo qua kiem tra trang thai merge."
  fi

  # Dau xung dot trong chinh cac tep se duoc day - bat ca truong hop da lo commit.
  local co_dau
  co_dau="$(grep -rlE '^(<<<<<<<|>>>>>>>)( |$)' \
            --include='*.py' --include='*.js' --include='*.html' --include='*.css' \
            ./*.py static tests trien_khai_vps 2>/dev/null || true)"
  if [ -n "$co_dau" ]; then
    echo "[LOI] Con dau xung dot git (<<<<<<< / >>>>>>>) trong:"
    echo "$co_dau" | sed 's/^/      /'
    loi=1
  fi

  # Tim Python that. Tren Windows "python3" co the chi la loi tat mo Microsoft
  # Store, nen phai chay thu chu khong chi command -v.
  for p in python3 python py; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys' >/dev/null 2>&1; then
      py="$p"
      break
    fi
  done
  if [ -n "$py" ]; then
    "$py" -c "$KIEM_CU_PHAP_PY" ./*.py tests/*.py || loi=1
  else
    echo "[canh bao] Khong tim thay Python tren may nay - cu phap se chi duoc kiem tren VPS."
  fi

  if command -v node >/dev/null 2>&1; then
    for p in static/*.js; do
      if ! node --check "$p" >/dev/null 2>&1; then
        echo "[LOI] $p loi cu phap JavaScript:"
        node --check "$p" 2>&1 | head -6 | sed 's/^/      /'
        loi=1
      fi
    done
  fi

  if [ "$loi" -ne 0 ]; then
    echo
    echo "[DUNG] Chua day gi len VPS. Sua cac loi tren roi chay lai."
    exit 1
  fi
  echo "    Kiem tra truoc khi day: OK"
}

if [ "${BO_KIEM_TRA:-0}" = "1" ]; then
  buoc "[canh bao] BO_KIEM_TRA=1 - bo qua kiem tra truoc khi day"
else
  buoc "Kiem tra ma nguon truoc khi day"
  kiem_tra_truoc_khi_day
fi

buoc "Kiem tra ket noi toi $NGUOI_SSH@$MAY_CHU"
$SSH 'echo "Dang nhap OK voi $(id -un)"
      . /etc/os-release 2>/dev/null && echo "He dieu hanh: $PRETTY_NAME"
      sudo -n true 2>/dev/null || { echo "[LOI] Tai khoan nay khong co quyen sudo khong mat khau."; exit 1; }
      [ -d /opt/chatbot-rag ] || { echo "[LOI] Chua chay 01_cai_dat_vps.sh tren VPS."; exit 1; }'

# ---------------------------------------------------------------------
buoc "Doc mat khau tu mat_khau.bat (khong in ra)"
doc_bien_bat() {  # doc dong dang:  set "TEN=gia tri"   trong file .bat
  local ten="$1" tep="$2"
  grep -i "set \"\?$ten=" "$tep" 2>/dev/null | tail -1 | sed "s/.*$ten=//I; s/\"[[:space:]]*$//" | tr -d '\r'
}
TAI_KHOAN="$(doc_bien_bat RAG_TAI_KHOAN mat_khau.bat)"; TAI_KHOAN="${TAI_KHOAN:-giaovien}"
MAT_KHAU="$(doc_bien_bat RAG_MAT_KHAU mat_khau.bat)"
[ -n "$MAT_KHAU" ] && [ "$MAT_KHAU" != "DAT_MAT_KHAU_VAO_DAY" ] \
  || { echo "[LOI] mat_khau.bat chua dat mat khau that."; exit 1; }
KHOA_DRIVE=""
[ -f khoa_api.bat ] && KHOA_DRIVE="$(doc_bien_bat RAG_DRIVE_API_KEY khoa_api.bat)"
# Gui ma xac minh email (gui_thu.py): Gmail + mat khau ung dung, xem khoa_api.mau.bat.
SMTP_TK=""; SMTP_MK=""
if [ -f khoa_api.bat ]; then
  SMTP_TK="$(doc_bien_bat RAG_SMTP_TAI_KHOAN khoa_api.bat)"
  SMTP_MK="$(doc_bien_bat RAG_SMTP_MAT_KHAU khoa_api.bat)"
fi

umask 077
TEP_TAM="$(mktemp)"; TEP_MK="$(mktemp)"
trap 'rm -f "$TEP_TAM" "$TEP_MK"' EXIT
printf '%s' "$MAT_KHAU" > "$TEP_MK"
{
  echo "# Sinh tu 02_day_ma_nguon.sh - sua mat_khau.bat roi chay lai, dung sua tay."
  echo "# Lop mat khau CUA UNG DUNG tat han: Caddy lo viec chan, va chi chan cac"
  echo "# duong dan quan tri. Xem /etc/caddy/quantri.caddy."
  echo "RAG_CONG_KHAI=0"
  echo "RAG_TAI_KHOAN=$TAI_KHOAN"
  echo "RAG_MAT_KHAU="
  echo "RAG_HOST=127.0.0.1"
  echo "RAG_PORT=8010"
  echo "RAG_LLM_MODEL=${RAG_LLM_MODEL:-llama3.2:3b}"
  echo "RAG_EMBEDDING_MODEL=${RAG_EMBEDDING_MODEL:-bge-m3}"
  echo "OLLAMA_BASE_URL=http://127.0.0.1:11434"
  echo "PYTHONUNBUFFERED=1"
  echo "PYTHONIOENCODING=utf-8"
  [ -n "$KHOA_DRIVE" ] && echo "RAG_DRIVE_API_KEY=$KHOA_DRIVE"
  if [ -n "$SMTP_TK" ] && [ -n "$SMTP_MK" ]; then
    echo "RAG_SMTP_TAI_KHOAN=$SMTP_TK"
    echo "RAG_SMTP_MAT_KHAU=$SMTP_MK"
  fi
} > "$TEP_TAM"
unset MAT_KHAU KHOA_DRIVE SMTP_MK
$SCP "$TEP_TAM" "$NGUOI_SSH@$MAY_CHU:/tmp/chatbot-rag.env" >/dev/null
$SCP "$TEP_MK"  "$NGUOI_SSH@$MAY_CHU:/tmp/mk.txt" >/dev/null
# Khoa chi dat tren VPS (RAG_EMAIL_QUAN_TRI...) ma may nay khong co thi giu
# nguyen gia tri cu, dung de lan day ma nguon nao cung xoa mat.
$SSH "$NHU_ROOT bash -c 'for k in RAG_EMAIL_QUAN_TRI RAG_SMTP_TAI_KHOAN RAG_SMTP_MAT_KHAU RAG_SMTP_MAY_CHU RAG_SMTP_CONG RAG_SMTP_NGUOI_GUI; do
        grep -q \"^\$k=\" /tmp/chatbot-rag.env || grep \"^\$k=\" /etc/chatbot-rag.env >> /tmp/chatbot-rag.env 2>/dev/null || true
      done'
      $NHU_ROOT install -o root -g rag -m 640 /tmp/chatbot-rag.env /etc/chatbot-rag.env && rm -f /tmp/chatbot-rag.env && echo 'Da ghi /etc/chatbot-rag.env'"

# KHOA_QUAN_TRI=1 thi dat mat khau cho cac duong dan quan tri; mac dinh 0 =
# khong chan gi, dung yeu cau "bo het cho hoi mat khau" ngay 15/09/2026.
if [ "${KHOA_QUAN_TRI:-0}" = "1" ]; then
buoc "Khoa cac nut quan tri trong Caddy (bam bcrypt ngay tren VPS)"
$SSH "$NHU_ROOT bash -s -- '$TAI_KHOAN'" <<'REMOTE_MK'
set -eu
TAI_KHOAN="$1"
BAM=$(caddy hash-password --plaintext "$(cat /tmp/mk.txt)")
shred -u /tmp/mk.txt 2>/dev/null || rm -f /tmp/mk.txt
printf 'basic_auth @quantri {\n\t%s %s\n}\n' "$TAI_KHOAN" "$BAM" > /etc/caddy/quantri.caddy
chmod 644 /etc/caddy/quantri.caddy
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 \
  && systemctl reload caddy && echo "Da khoa nut quan tri cho tai khoan $TAI_KHOAN" \
  || { echo "[LOI] Caddyfile khong hop le - xem: caddy validate --config /etc/caddy/Caddyfile"; exit 1; }
REMOTE_MK
else
buoc "Khong dat mat khau cho nut quan tri (dat KHOA_QUAN_TRI=1 neu muon bat lai)"
$SSH "$NHU_ROOT bash -c 'rm -f /tmp/mk.txt; printf \"# Khong chan duong dan nao. Dat KHOA_QUAN_TRI=1 khi chay 02_day_ma_nguon.sh de bat lai.\n\" > /etc/caddy/quantri.caddy; caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null 2>&1 && systemctl reload caddy && echo \"Moi duong dan deu mo\"'"
fi

# ---------------------------------------------------------------------
buoc "Day ma nguon + giao dien + tessdata (khoang 115 MB)"
# tessdata PHAI di kem: ocr_pdf.py tim vie.traineddata trong thu muc tessdata
# cua du an, thieu no thi PDF scan im lang tra ve rong, khong bao loi gi.
# --format=posix giu mtime toi nano giay. Dinh dang tar mac dinh cat mat
# phan le giay, the la tep tren VPS khong con khop modified_ns trong so ghi
# chep va giao dien bao "Cho cap nhat" du chi muc van con du.
TEP_TRANG_THAI=()
if [ "$DAY_CHI_MUC" = "1" ]; then
  buoc "Sao luu trang thai cu tren VPS truoc khi day de"
  $SSH "$NHU_ROOT bash -s" <<'REMOTE'
set -eu
cd /opt/chatbot-rag
DICH="sao_luu_truoc_day-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$DICH"
for t in data_giao_duc_da_xu_ly.json drive_state.json cai_dat.json faiss_index_data_giao_duc; do
  [ -e "$t" ] && cp -a "$t" "$DICH/" || true
done
chown -R rag:rag "$DICH"
echo "Da sao luu vao /opt/chatbot-rag/$DICH ($(du -sh "$DICH" | cut -f1))"
REMOTE
  TEP_TRANG_THAI=(cai_dat.json data_giao_duc_da_xu_ly.json drive_state.json
                  faiss_index_data_giao_duc/index.faiss faiss_index_data_giao_duc/index.pkl)
else
  buoc "Giu nguyen so ghi chep, FAISS, drive_state.json, cai_dat.json tren VPS"
  echo "    (dat DAY_CHI_MUC=1 neu that su muon day de - lan trien khai dau tien)"
fi

tar -czf - --format=posix \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='*.truoc-khi-*' \
  *.py requirements.txt README.md HUONG_DAN_*.md \
  static tests trien_khai_vps tessdata \
  bo_cau_hoi_benchmark.json ho_so_van_ban.json phan_loai_tai_lieu.json \
  tinh_trang_hieu_luc.json meta_llm.json drive_manifest.json \
  ${TEP_TRANG_THAI[@]+"${TEP_TRANG_THAI[@]}"} \
| $SSH "$NHU_ROOT tar -xzf - -C $THU_MUC_XA && $NHU_ROOT chown -R rag:rag $THU_MUC_XA && echo 'Da giai nen tren VPS'"

# ---------------------------------------------------------------------
buoc "Doi duong dan trong so ghi chep tu Windows sang Linux"
# data_giao_duc_da_xu_ly.json khoa theo duong dan TUYET DOI. Giu nguyen dang
# "D:\Mr_Hai\..." thi tren VPS moi tep deu trong nhu tep moi, va lan cap nhat
# chi muc dau tien se embed lai TOAN BO kho - nhieu gio CPU khong can thiet.
$SSH "$NHU_ROOT python3 - <<'PYEOF'
import json, pathlib, shutil, datetime, sys
p = pathlib.Path('/opt/chatbot-rag/data_giao_duc_da_xu_ly.json')
if not p.exists():
    print('Chua co so ghi chep tren VPS. Lan dau trien khai hay chay lai voi DAY_CHI_MUC=1,')
    print('hoac de VPS tu lap chi muc tu dau (nhieu gio CPU).')
    sys.exit(0)
d = json.loads(p.read_text(encoding='utf-8'))
GOC = '/opt/chatbot-rag/ollama-rag-desktop/data_giao_duc'
moi, doi = {}, 0
for khoa, gt in d.items():
    if 'data_giao_duc' in khoa and ('\\' in khoa or khoa[1:3] == ':\\'):
        moi[GOC + '/' + khoa.replace('\\', '/').split('data_giao_duc/', 1)[-1]] = gt
        doi += 1
    else:
        moi[khoa] = gt
if doi:
    shutil.copy2(p, p.with_name(p.name + datetime.datetime.now().strftime('.truoc-khi-doi-duong-dan-%Y%m%d-%H%M%S')))
    p.write_text(json.dumps(moi, ensure_ascii=False, indent=1), encoding='utf-8')
tep = {str(x) for x in pathlib.Path(GOC).rglob('*') if x.is_file()} if pathlib.Path(GOC).exists() else set()
print(f'Da doi {doi} duong dan. Tep tren dia: {len(tep)}, khop so ghi chep: {len(tep & set(moi))}, chua co chi muc: {len(tep - set(moi))}')
PYEOF
$NHU_ROOT chown rag:rag /opt/chatbot-rag/data_giao_duc_da_xu_ly.json*"

# ---------------------------------------------------------------------
buoc "Cai thu vien Python theo requirements.txt (lan dau mat vai phut)"
$SSH "$NHU_RAG $THU_MUC_XA/.venv/bin/python -m pip install -q --upgrade pip wheel setuptools && \
      $NHU_RAG $THU_MUC_XA/.venv/bin/python -m pip install -r $THU_MUC_XA/requirements.txt"

buoc "Kiem tra OCR da san sang chua"
$SSH "cd $THU_MUC_XA && $NHU_RAG ./.venv/bin/python -c \"
import ocr_pdf
ok, thong_bao = ocr_pdf.san_sang()
print('Tesseract:', ocr_pdf.tim_tesseract(), '| OCR:', thong_bao)
\""

# ---------------------------------------------------------------------
# Kiem lai bang chinh Python 3.11 cua VPS: cu phap moi cua Python tren may nay
# (vd f-string long nhau cua 3.12) qua duoc buoc kiem cuc bo nhung chet o day.
buoc "Kiem tra cu phap bang Python cua VPS truoc khi khoi dong lai"
if ! $SSH "cd $THU_MUC_XA && $NHU_RAG ./.venv/bin/python - *.py" <<<"$KIEM_CU_PHAP_PY"; then
  echo "[DUNG] Ma nguon moi khong chay duoc tren VPS - KHONG khoi dong lai dich vu."
  echo "       Sua loi tren roi chay lai kich ban nay."
  exit 1
fi
echo "Cu phap OK"

# ---------------------------------------------------------------------
buoc "Khoi dong dich vu va cho nap kho tri thuc (toi da 10 phut)"
$SSH "$NHU_ROOT bash -s" <<'REMOTE'
set -u
systemctl restart chatbot-rag
sleep 5
systemctl --no-pager --lines=8 status chatbot-rag || true
echo
# Chet luc khoi dong thi systemd tu khoi dong lai moi 5 giay: dung sang
# auto-restart/failed hoac doi PID nghia la da chet - bao ngay kem log thay
# vi in dau cham suot 10 phut.
pid_dau=$(systemctl show -p MainPID --value chatbot-rag)
for i in $(seq 1 120); do
  tt=$(curl -s http://127.0.0.1:8010/api/status 2>/dev/null | head -c 500)
  case "$tt" in
    *'"state":"ready"'*)  echo; echo "SAN SANG: $tt"; exit 0 ;;
    *'"state":"error"'*)  echo; echo "[LOI] $tt"; exit 1 ;;
    *) printf '.' ;;
  esac
  trang_thai=$(systemctl show -p SubState --value chatbot-rag)
  pid=$(systemctl show -p MainPID --value chatbot-rag)
  if [ "$trang_thai" = "auto-restart" ] || [ "$trang_thai" = "failed" ] || [ "$pid" != "$pid_dau" ]; then
    echo; echo "[LOI] chatbot-rag chet ngay sau khi khoi dong. Log gan nhat:"
    journalctl -u chatbot-rag -n 30 --no-pager
    exit 1
  fi
  sleep 5
done
echo; echo "[canh bao] Qua 10 phut chua san sang. Xem: sudo journalctl -u chatbot-rag -n 50"
REMOTE

echo
echo "=============================================================="
echo " XONG PHAN MA NGUON."
echo " Tiep theo: bash trien_khai_vps/03_day_tai_lieu.sh <IP_VPS> root"
echo "=============================================================="
