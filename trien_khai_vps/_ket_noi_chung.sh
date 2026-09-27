# shellcheck shell=bash
# shellcheck disable=SC2034  # SSH, SCP duoc dung o kich ban source tep nay
# =====================================================================
#  KET NOI SSH DUNG CHUNG CHO 02 / 03 / 04   (source, khong chay rieng)
# =====================================================================
#  Moi kich ban day goi ssh/scp chuc lan. Khoa SSH khong vao duoc tai
#  khoan dang dung (vd khoa chi nam trong /root/.ssh/authorized_keys ma
#  chay bang debian) thi MOI lan deu hoi mat khau: 27/09/2026 phai go
#  khoang 10 lan, go sai vai lan la cham nguong fail2ban (5 lan sai trong
#  10 phut -> chan IP 1 gio).
#
#  Cach lam: mo MOT ket noi chinh (SSH ControlMaster), moi lenh sau di
#  chung ket noi do nen chi xac thuc mot lan. Go sai mat khau thi dung
#  ngay, khong hoi tiep. May nao ssh khong gop duoc ket noi thi tu lui ve
#  cach cu (moi lenh mot ket noi) va canh bao. Tat han: KHONG_GOP_KET_NOI=1.
#
#  Can dat truoc khi source: MAY_CHU, NGUOI_SSH, KHOA.
#  Sinh ra: SSH, SCP (dung nhu cu: $SSH "lenh", $SCP tep dich), cung hai
#  ham mo_ket_noi_chung va dong_ket_noi_chung (goi trong trap EXIT).
# =====================================================================

SSH_OPT="-i $KHOA -o StrictHostKeyChecking=accept-new -o ConnectTimeout=15 -o ServerAliveInterval=20 -o ServerAliveCountMax=3"
SSH="ssh $SSH_OPT $NGUOI_SSH@$MAY_CHU"
SCP="scp $SSH_OPT"
THU_MUC_KET_NOI=""

mo_ket_noi_chung() {
  echo "    Neu bi hoi \"$NGUOI_SSH@$MAY_CHU's password\": do la mat khau dang nhap Linux"
  echo "    cua tai khoan $NGUOI_SSH tren VPS, KHONG phai mat khau trong mat_khau.bat."
  if [ "${KHONG_GOP_KET_NOI:-0}" = "1" ]; then
    echo "    KHONG_GOP_KET_NOI=1 - moi lenh ssh/scp tu mo ket noi rieng."
    return 0
  fi

  local thu_muc duong
  thu_muc="$(mktemp -d)"
  duong="$thu_muc/cm"
  # ControlPersist: ket noi chinh tach ra chay nen, con lenh "true" di qua no
  # nhu mot lenh ssh binh thuong. Thanh cong nghia la gop duoc that (ca phan
  # chuyen stdin/stdout qua socket), khong chi mo duoc socket.
  # stderr vao tep de phan biet sai mat khau (phai dung) voi may khong gop
  # duoc (lui ve cach cu). Dau nhac mat khau van hien vi ssh ghi thang ra tty.
  # shellcheck disable=SC2086
  if ssh -n $SSH_OPT -o ControlMaster=yes -o ControlPersist=10m -o ControlPath="$duong" \
       "$NGUOI_SSH@$MAY_CHU" true 2>"$thu_muc/loi"; then
    THU_MUC_KET_NOI="$thu_muc"
    SSH="ssh $SSH_OPT -o ControlMaster=no -o ControlPath=$duong $NGUOI_SSH@$MAY_CHU"
    SCP="scp $SSH_OPT -o ControlMaster=no -o ControlPath=$duong"
    echo "    Da mo ket noi chung - cac buoc sau khong hoi lai mat khau."
    return 0
  fi

  # Ket noi chinh co the van song (dang nhap duoc nhung khong gop duoc): dong lai.
  ssh -o ControlPath="$duong" -O exit "$NGUOI_SSH@$MAY_CHU" >/dev/null 2>&1 || true
  if grep -qiE 'Permission denied|Too many authentication|Host key verification|REMOTE HOST IDENTIFICATION|Could not resolve|Connection (timed out|refused)|No route to host|Network is unreachable' "$thu_muc/loi"; then
    sed 's/^/      /' "$thu_muc/loi"
    rm -rf "$thu_muc" 2>/dev/null || true
    echo "[LOI] Khong vao duoc $NGUOI_SSH@$MAY_CHU - chua dong gi vao VPS."
    echo "      - Sai mat khau: do la mat khau Linux cua '$NGUOI_SSH', khong phai mat_khau.bat."
    echo "        Cach chua goc: chep khoa SSH cho tai khoan nay (HUONG_DAN.md, muc 'Cach vao may')."
    echo "      - 'timed out' / 'refused' ngay sau vai lan go sai: fail2ban co the da chan IP"
    echo "        cua ban 1 gio. Doi het gio, hoac vao console KVM cua OVH chay:"
    echo "        fail2ban-client set sshd unbanip <IP may ban>"
    exit 1
  fi
  echo "[canh bao] ssh tren may nay khong gop duoc ket noi (ControlMaster) - moi buoc se"
  echo "           tu mo ket noi rieng, co the hoi mat khau nhieu lan. Chi tiet:"
  sed 's/^/      /' "$thu_muc/loi"
  rm -rf "$thu_muc" 2>/dev/null || true
}

dong_ket_noi_chung() {
  [ -n "$THU_MUC_KET_NOI" ] || return 0
  ssh -o ControlPath="$THU_MUC_KET_NOI/cm" -O exit "$NGUOI_SSH@$MAY_CHU" >/dev/null 2>&1 || true
  rm -rf "$THU_MUC_KET_NOI" 2>/dev/null || true
  THU_MUC_KET_NOI=""
}
