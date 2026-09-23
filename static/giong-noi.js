/* ============================================================
   NÓI THAY VÌ GÕ
   ============================================================
   Nút micro trong khung hỏi: bấm để nói, bấm lần nữa để dừng (tự dừng sau
   60 giây, Esc để huỷ). Âm thanh gửi về máy chủ (/api/giong-noi), nơi
   faster-whisper chuyển thành chữ và tự nhận ra ngôn ngữ - không cần chọn
   trước tiếng gì. Chữ được chèn vào ô câu hỏi để người dùng xem lại rồi mới gửi.
   ============================================================ */
(() => {
  const nut = document.getElementById('micButton');
  const o = document.getElementById('questionInput');
  const goiY = document.querySelector('.composer .input-hint');
  if (!nut || !o) return;
  const nhan = nut.querySelector('span');
  const GOI_Y_GOC = goiY?.textContent || '';
  const GIAY_TOI_DA = 60;

  // getUserMedia chỉ có ở trang https hoặc localhost.
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    nut.disabled = true;
    nut.title = window.isSecureContext
      ? 'Trình duyệt này không hỗ trợ ghi âm'
      : 'Cần mở trang qua https (hoặc localhost) thì trình duyệt mới cho dùng micro';
    return;
  }

  let trangThai = 'nghi'; // nghi | ghi | xu_ly
  let ghiAm = null;
  let luong = null;
  let manh = [];
  let henGio = 0;
  let batDau = 0;
  let huy = false;

  const dongHo = (giay) => `${Math.floor(giay / 60)}:${String(giay % 60).padStart(2, '0')}`;

  function datTrangThai(tt, chu = '') {
    trangThai = tt;
    nut.classList.toggle('dang-ghi', tt === 'ghi');
    nut.classList.toggle('dang-xu-ly', tt === 'xu_ly');
    nut.setAttribute('aria-pressed', String(tt === 'ghi'));
    nut.disabled = tt === 'xu_ly';
    nhan.textContent = tt === 'ghi' ? 'Dừng' : tt === 'xu_ly' ? 'Đang nhận…' : 'Nói';
    if (goiY) goiY.textContent = chu || GOI_Y_GOC;
  }

  async function batDauGhi() {
    try {
      luong = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    } catch (loi) {
      showToast(
        loi.name === 'NotAllowedError'
          ? 'Trình duyệt chưa cho dùng micro - bấm biểu tượng bên trái địa chỉ trang để cho phép'
          : `Không mở được micro: ${loi.message || loi.name}`,
        4200,
      );
      return;
    }
    const kieu = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/mp4']
      .find((k) => MediaRecorder.isTypeSupported(k));
    ghiAm = new MediaRecorder(luong, kieu ? { mimeType: kieu } : undefined);
    manh = [];
    huy = false;
    ghiAm.addEventListener('dataavailable', (event) => {
      if (event.data.size) manh.push(event.data);
    });
    ghiAm.addEventListener('stop', guiDi);
    ghiAm.start();
    batDau = performance.now();
    datTrangThai('ghi', 'Đang nghe… 0:00 · bấm Dừng khi nói xong');
    henGio = window.setInterval(() => {
      const giay = Math.floor((performance.now() - batDau) / 1000);
      if (giay >= GIAY_TOI_DA) {
        dungGhi();
        return;
      }
      if (goiY) goiY.textContent = `Đang nghe… ${dongHo(giay)} · bấm Dừng khi nói xong`;
    }, 250);
  }

  function dungGhi(boQua = false) {
    huy = boQua;
    window.clearInterval(henGio);
    if (ghiAm?.state === 'recording') ghiAm.stop();
    luong?.getTracks().forEach((track) => track.stop());
    luong = null;
  }

  async function guiDi() {
    const duLieu = new Blob(manh, { type: ghiAm?.mimeType || 'audio/webm' });
    ghiAm = null;
    if (huy) {
      datTrangThai('nghi');
      return;
    }
    if (duLieu.size < 1000) {
      datTrangThai('nghi');
      showToast('Chưa ghi được gì - hãy nói rồi bấm Dừng');
      return;
    }
    datTrangThai('xu_ly', 'Đang chuyển giọng nói thành chữ…');
    try {
      const phanHoi = await fetch('/api/giong-noi', {
        method: 'POST',
        headers: { 'Content-Type': duLieu.type || 'application/octet-stream', 'X-RAG-Action': 'voice-input' },
        body: duLieu,
      });
      const ketQua = await phanHoi.json().catch(() => ({}));
      if (!phanHoi.ok) {
        throw new Error(typeof ketQua.detail === 'string' ? ketQua.detail : 'Không nhận được giọng nói.');
      }
      chenChu(ketQua.van_ban);
      const baoNgonNgu = `Đã nhận ra ${String(ketQua.ten_ngon_ngu || ketQua.ngon_ngu).replace(/^Tiếng/, 'tiếng')}`;
      datTrangThai('nghi', `${baoNgonNgu} · xem lại rồi nhấn Enter để gửi`);
      showToast(baoNgonNgu);
      window.setTimeout(() => {
        if (trangThai === 'nghi' && goiY?.textContent.startsWith('Đã nhận ra')) goiY.textContent = GOI_Y_GOC;
      }, 8000);
    } catch (loi) {
      datTrangThai('nghi');
      showToast(loi.message || 'Không nhận được giọng nói', 4200);
    }
  }

  // Chèn vào chỗ con trỏ, thêm khoảng trắng nếu dính chữ hai bên.
  function chenChu(chu) {
    const cu = o.value;
    const dau = o.selectionStart ?? cu.length;
    const cuoi = o.selectionEnd ?? cu.length;
    const truoc = cu.slice(0, dau);
    const sau = cu.slice(cuoi);
    const them = (truoc && !/\s$/.test(truoc) ? ' ' : '') + chu + (sau && !/^\s/.test(sau) ? ' ' : '');
    const toiDa = o.maxLength > 0 ? o.maxLength : Infinity;
    o.value = (truoc + them + sau).slice(0, toiDa);
    const viTri = Math.min(o.value.length, (truoc + them).length);
    o.focus();
    o.setSelectionRange(viTri, viTri);
    o.dispatchEvent(new Event('input', { bubbles: true })); // giãn ô và bật nút gửi
  }

  nut.addEventListener('click', () => {
    if (trangThai === 'nghi') batDauGhi();
    else if (trangThai === 'ghi') dungGhi();
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && trangThai === 'ghi') {
      dungGhi(true);
      showToast('Đã huỷ ghi âm');
    }
  });
  window.addEventListener('pagehide', () => dungGhi(true));
})();
