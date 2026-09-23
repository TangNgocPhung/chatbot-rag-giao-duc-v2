/* ============================================================
   DỊCH ĐA NGÔN NGỮ (mọi ngôn ngữ Google Translate hỗ trợ)
   ============================================================
   Khung dịch hai cột như Google Translate, dịch câu trả lời ngay dưới câu
   trả lời, và dịch đoạn vừa bôi đen. Mỗi chiều hiện ba ngôn ngữ dùng gần
   đây; nút mũi tên mở bảng tìm trong hơn 130 ngôn ngữ (danh sách lấy từ
   /api/dich/cau-hinh). Máy chủ lo phần dịch (/api/dich): dùng
   Google Cloud Translation nếu có key, không thì dịch bằng mô hình trên máy -
   khi đó giao diện ghi rõ "bản dịch máy, chỉ để tham khảo".
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const d = {
    hop: $id('dichDialog'),
    dong: $id('dichDong'),
    nutMo: $id('dichButton'),
    nguon: $id('dichNguon'),
    dich: $id('dichDich'),
    doi: $id('dichDoi'),
    vao: $id('dichVao'),
    ra: $id('dichRa'),
    dem: $id('dichDem'),
    xoa: $id('dichXoa'),
    ngheVao: $id('dichNgheVao'),
    ngheRa: $id('dichNgheRa'),
    chep: $id('dichChep'),
    ghi: $id('dichGhi'),
    trangThai: $id('dichTrangThai'),
    ghiChu: $id('dichGhiChu'),
    bang: $id('dichBangChon'),
    tim: $id('dichTimNgonNgu'),
    luoi: $id('dichLuoiNgonNgu'),
  };
  if (!d.hop) return;

  // Danh sách đầy đủ đến từ máy chủ; bốn ngôn ngữ này dùng tạm khi chưa tải xong.
  let NGON_NGU = [
    { ma: 'vi', ten: 'Tiếng Việt', ten_goc: 'Tiếng Việt' },
    { ma: 'en', ten: 'Tiếng Anh', ten_goc: 'English' },
    { ma: 'ja', ten: 'Tiếng Nhật', ten_goc: '日本語' },
    { ma: 'ko', ten: 'Tiếng Hàn', ten_goc: '한국어' },
  ];
  let TEN = {};
  let TEN_GOC = {};
  const GIONG_RIENG = { vi: 'vi-VN', en: 'en-US', ja: 'ja-JP', ko: 'ko-KR', 'zh-CN': 'zh-CN', 'zh-TW': 'zh-TW', 'mni-Mtei': 'mni' };
  const giong = (ma) => GIONG_RIENG[ma] || ma || '';
  const KHOA_LUU = 'rag-dich-ngon-ngu';
  const KY_TU_TOI_DA = 5000;
  const SO_GAN_DAY = 3;

  let nguon = 'tu_dong';
  let dichSang = 'en';
  let ganDayNguon = ['vi', 'en', 'ja'];
  let ganDayDich = ['en', 'vi', 'ja'];
  let nguonPhatHien = '';
  let congCu = 'cuc_bo';
  let dangGoi = null;
  let henDich = 0;
  let luuTho = {};

  function napNgonNgu(danhSach) {
    NGON_NGU = danhSach;
    TEN = Object.fromEntries(danhSach.map((n) => [n.ma, n.ten]));
    TEN_GOC = Object.fromEntries(danhSach.map((n) => [n.ma, n.ten_goc]));
    // Lựa chọn đã lưu có thể là ngôn ngữ chỉ có trong danh sách đầy đủ.
    const hopLe = (ma) => Boolean(TEN[ma]);
    if (luuTho.nguon === 'tu_dong' || hopLe(luuTho.nguon)) nguon = luuTho.nguon;
    if (hopLe(luuTho.dichSang)) dichSang = luuTho.dichSang;
    if (Array.isArray(luuTho.ganDayNguon)) ganDayNguon = luuTho.ganDayNguon.filter(hopLe);
    if (Array.isArray(luuTho.ganDayDich)) ganDayDich = luuTho.ganDayDich.filter(hopLe);
    ganDayNguon = themGanDay(ganDayNguon, nguon);
    ganDayDich = themGanDay(ganDayDich, dichSang);
  }

  // Ngôn ngữ vừa chọn lên đầu hàng nếu chưa có sẵn, như Google Translate.
  function themGanDay(ds, ma) {
    const moi = ds.filter((m) => TEN[m]);
    if (ma && ma !== 'tu_dong' && !moi.includes(ma)) moi.unshift(ma);
    for (const du of ['vi', 'en', 'ja', 'ko']) {
      if (moi.length >= SO_GAN_DAY) break;
      if (!moi.includes(du)) moi.push(du);
    }
    return moi.slice(0, SO_GAN_DAY);
  }

  try {
    luuTho = JSON.parse(localStorage.getItem(KHOA_LUU) || '{}') || {};
  } catch {
    /* dùng mặc định */
  }
  napNgonNgu(NGON_NGU);
  const luuLuaChon = () => {
    luuTho = { nguon, dichSang, ganDayNguon, ganDayDich };
    try {
      localStorage.setItem(KHOA_LUU, JSON.stringify(luuTho));
    } catch {
      /* chế độ riêng tư */
    }
  };

  // So khớp không phân biệt hoa thường và dấu: "phap", "Pháp", "français", "fr".
  const boDau = (chu) => chu.normalize('NFD').replace(/\p{M}/gu, '').replace(/đ/gi, 'd').toLowerCase();
  function locNgonNgu(tuKhoa) {
    const k = boDau(tuKhoa.trim());
    if (!k) return NGON_NGU;
    const dungMa = NGON_NGU.filter((n) => n.ma.toLowerCase() === k);
    return [...dungMa, ...NGON_NGU.filter((n) =>
      !dungMa.includes(n) && (boDau(n.ten).includes(k) || boDau(n.ten_goc).includes(k)))];
  }

  // ------------------------------------------------------------
  // GỌI MÁY CHỦ
  // ------------------------------------------------------------
  // Đọc dòng sự kiện ndjson; goiLai nhận từng sự kiện. Trả về bản dịch đầy đủ.
  async function goiDich(vanBan, tu, sang, goiLai, tinHieu) {
    const phanHoi = await fetch('/api/dich', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ van_ban: vanBan, nguon: tu, dich_sang: sang }),
      signal: tinHieu,
    });
    if (!phanHoi.ok) {
      const loi = await phanHoi.json().catch(() => ({}));
      throw new Error(typeof loi.detail === 'string' ? loi.detail : 'Không dịch được văn bản này.');
    }
    const docDong = phanHoi.body.getReader();
    const giaiMa = new TextDecoder();
    let dem = '';
    let banDich = '';
    for (;;) {
      const { value, done } = await docDong.read();
      dem += giaiMa.decode(value || new Uint8Array(), { stream: !done });
      const cacDong = dem.split('\n');
      dem = cacDong.pop() || '';
      for (const dong of cacDong) {
        if (!dong.trim()) continue;
        const suKien = JSON.parse(dong);
        if (suKien.type === 'error') throw new Error(suKien.message);
        if (suKien.type === 'token') banDich += suKien.content;
        goiLai(suKien, banDich);
      }
      if (done) break;
    }
    return banDich.trim();
  }

  // ------------------------------------------------------------
  // KHUNG DỊCH HAI CỘT
  // ------------------------------------------------------------
  function veChip() {
    d.nguon.replaceChildren();
    d.dich.replaceChildren();
    const taoChip = (ma, nhan, dangChon, khiChon, phu = '') => {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = 'dich-chip';
      nut.setAttribute('role', 'radio');
      nut.setAttribute('aria-checked', String(dangChon));
      nut.textContent = nhan;
      if (phu) {
        const nho = document.createElement('small');
        nho.textContent = phu;
        nut.append(nho);
      }
      nut.addEventListener('click', khiChon);
      return nut;
    };
    d.nguon.append(taoChip(
      'tu_dong',
      nguon === 'tu_dong' && nguonPhatHien ? TEN[nguonPhatHien] || nguonPhatHien : 'Phát hiện ngôn ngữ',
      nguon === 'tu_dong',
      () => doiNguon('tu_dong'),
      nguon === 'tu_dong' && nguonPhatHien ? '· đã phát hiện' : '',
    ));
    for (const ma of ganDayNguon) d.nguon.append(taoChip(ma, TEN[ma], nguon === ma, () => doiNguon(ma)));
    for (const ma of ganDayDich) d.dich.append(taoChip(ma, TEN[ma], dichSang === ma, () => doiDich(ma)));
    d.nguon.append(taoNutMoBang('nguon'));
    d.dich.append(taoNutMoBang('dich'));
    d.vao.lang = giong(nguon === 'tu_dong' ? nguonPhatHien : nguon);
    d.ra.lang = giong(dichSang);
  }

  function taoNutMoBang(phia) {
    const nut = document.createElement('button');
    nut.type = 'button';
    nut.className = 'dich-mo-bang';
    nut.setAttribute('aria-expanded', String(bangDangMo === phia));
    nut.setAttribute('aria-controls', 'dichBangChon');
    nut.setAttribute('aria-label', phia === 'nguon' ? 'Thêm ngôn ngữ nguồn' : 'Thêm ngôn ngữ đích');
    nut.title = 'Tất cả ngôn ngữ';
    nut.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 9 6 6 6-6"/></svg>';
    nut.addEventListener('click', () => (bangDangMo === phia ? dongBang() : moBang(phia)));
    return nut;
  }

  function doiNguon(ma) {
    dongBang(false);
    nguon = ma;
    if (ma !== 'tu_dong') nguonPhatHien = '';
    ganDayNguon = themGanDay(ganDayNguon, ma);
    luuLuaChon();
    veChip();
    henDichLai(0);
  }

  function doiDich(ma) {
    dongBang(false);
    dichSang = ma;
    ganDayDich = themGanDay(ganDayDich, ma);
    luuLuaChon();
    veChip();
    henDichLai(0);
  }

  // ------------------------------------------------------------
  // BẢNG CHỌN TẤT CẢ NGÔN NGỮ (phủ lên hai ô văn bản như Google Translate)
  // ------------------------------------------------------------
  let bangDangMo = '';

  function moBang(phia) {
    bangDangMo = phia;
    d.tim.value = '';
    d.bang.setAttribute('aria-label', phia === 'nguon' ? 'Chọn ngôn ngữ nguồn' : 'Chọn ngôn ngữ đích');
    d.bang.classList.remove('hidden');
    veBang();
    veChip();
    d.tim.focus();
  }

  function dongBang(traTieuDiem = true) {
    if (!bangDangMo) return;
    bangDangMo = '';
    d.bang.classList.add('hidden');
    veChip();
    if (traTieuDiem) d.vao.focus();
  }

  function veBang() {
    const phia = bangDangMo;
    const dangChon = phia === 'nguon' ? nguon : dichSang;
    const tuKhoa = d.tim.value.trim();
    const taoMuc = (ma, nhan, phu = '') => {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = 'dich-muc';
      nut.setAttribute('role', 'option');
      nut.setAttribute('aria-selected', String(ma === dangChon));
      nut.textContent = nhan;
      if (phu && phu !== nhan) {
        const nho = document.createElement('small');
        nho.textContent = phu;
        nut.append(nho);
      }
      nut.addEventListener('click', () => (phia === 'nguon' ? doiNguon(ma) : doiDich(ma)));
      return nut;
    };
    d.luoi.replaceChildren();
    if (phia === 'nguon' && !tuKhoa) d.luoi.append(taoMuc('tu_dong', 'Phát hiện ngôn ngữ'));
    // Có từ khoá thì giữ thứ tự của locNgonNgu (trùng mã đứng đầu), không thì xếp theo tên.
    const ds = tuKhoa ? locNgonNgu(tuKhoa) : NGON_NGU.slice().sort((a, b) => a.ten.localeCompare(b.ten, 'vi'));
    for (const n of ds) d.luoi.append(taoMuc(n.ma, n.ten, n.ten_goc));
    if (!ds.length) {
      const trong = document.createElement('p');
      trong.className = 'dich-bang-trong';
      trong.textContent = 'Không tìm thấy ngôn ngữ nào';
      d.luoi.append(trong);
    }
  }

  d.tim.addEventListener('input', veBang);
  d.tim.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      d.luoi.querySelector('.dich-muc')?.click();
    }
  });
  // Esc khi bảng đang mở chỉ đóng bảng, không đóng cả khung dịch.
  d.hop.addEventListener('cancel', (event) => {
    if (!bangDangMo) return;
    event.preventDefault();
    dongBang();
  });

  function capNhatDem() {
    d.dem.textContent = `${d.vao.value.length.toLocaleString('vi-VN')} / ${KY_TU_TOI_DA.toLocaleString('vi-VN')}`;
    d.xoa.classList.toggle('hidden', !d.vao.value);
  }

  function datKetQua(chu, trangThai = '') {
    d.ra.textContent = chu;
    d.ra.classList.toggle('trong', !chu);
    d.trangThai.textContent = trangThai;
    const coChu = Boolean(chu);
    for (const nut of [d.chep, d.ghi, d.ngheRa]) nut.disabled = !coChu;
  }

  function henDichLai(tre = congCu === 'google' ? 700 : 1400) {
    window.clearTimeout(henDich);
    henDich = window.setTimeout(dichNgay, tre);
  }

  async function dichNgay() {
    window.clearTimeout(henDich);
    dangGoi?.abort();
    const vanBan = d.vao.value.trim();
    if (!vanBan) {
      nguonPhatHien = '';
      veChip();
      datKetQua('');
      return;
    }
    const huy = new AbortController();
    dangGoi = huy;
    d.ra.classList.add('dang-dich');
    d.trangThai.textContent = 'Đang dịch…';
    const batDau = performance.now();
    try {
      const banDich = await goiDich(vanBan, nguon, dichSang, (suKien, tamThoi) => {
        if (huy.signal.aborted) return;
        if (suKien.type === 'ngon_ngu') {
          nguonPhatHien = suKien.nguon;
          congCu = suKien.cong_cu || congCu;
          veChip();
          capNhatGhiChu();
        } else if (suKien.type === 'phase') {
          d.trangThai.textContent = suKien.message;
        } else if (suKien.type === 'warning') {
          showToast(suKien.message, 4200);
        } else if (suKien.type === 'token') {
          d.ra.textContent = tamThoi;
          d.ra.classList.remove('trong');
        }
      }, huy.signal);
      if (huy.signal.aborted) return;
      const giay = ((performance.now() - batDau) / 1000).toFixed(1);
      datKetQua(banDich, congCu === 'google' ? `Google Dịch · ${giay} giây` : `Bản dịch máy · ${giay} giây`);
    } catch (loi) {
      if (loi.name === 'AbortError') return;
      datKetQua('', loi.message || 'Không dịch được.');
    } finally {
      if (dangGoi === huy) {
        dangGoi = null;
        d.ra.classList.remove('dang-dich');
      }
    }
  }

  function capNhatGhiChu() {
    d.ghiChu.textContent = congCu === 'google'
      ? 'Văn bản được gửi tới Google Cloud Translation để dịch. Đừng dán thông tin cá nhân nhạy cảm.'
      : 'Bản dịch máy do mô hình trên máy chủ tạo ra, chỉ để tham khảo - hãy kiểm tra lại trước khi dùng chính thức.';
    d.ghiChu.classList.toggle('canh-bao', congCu !== 'google');
  }

  function moKhungDich(vanBan = '') {
    closeSidebar();
    anThanhChonChat();
    if (vanBan) {
      d.vao.value = vanBan.slice(0, KY_TU_TOI_DA);
      // Dán tiếng Việt vào mà đích đang là tiếng Việt thì đổi đích sang tiếng Anh.
      if (dichSang === 'vi' && /[à-ỹđ]/i.test(vanBan)) dichSang = 'en';
    }
    veChip();
    capNhatDem();
    capNhatGhiChu();
    if (!d.hop.open) d.hop.showModal();
    d.vao.focus();
    if (d.vao.value.trim()) dichNgay();
    else datKetQua('');
  }

  function anThanhChonChat() {
    document.getElementById('thanhChon')?.classList.add('hidden');
  }

  d.vao.addEventListener('input', () => {
    capNhatDem();
    henDichLai();
  });
  d.vao.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      dichNgay();
    }
  });
  d.xoa.addEventListener('click', () => {
    d.vao.value = '';
    capNhatDem();
    dichNgay();
    d.vao.focus();
  });
  d.doi.addEventListener('click', () => {
    const cu = nguon === 'tu_dong' ? nguonPhatHien : nguon;
    if (!cu) {
      showToast('Hãy nhập văn bản hoặc chọn ngôn ngữ nguồn trước');
      return;
    }
    if (cu === dichSang) return;
    dongBang(false);
    const banDich = d.ra.textContent;
    nguon = dichSang;
    dichSang = cu;
    nguonPhatHien = '';
    ganDayNguon = themGanDay(ganDayNguon, nguon);
    ganDayDich = themGanDay(ganDayDich, dichSang);
    if (banDich) {
      d.vao.value = banDich;
      capNhatDem();
    }
    luuLuaChon();
    veChip();
    dichNgay();
  });
  d.chep.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(d.ra.textContent);
      showToast('Đã sao chép bản dịch');
    } catch {
      showToast('Trình duyệt không cho sao chép');
    }
  });
  d.ghi.addEventListener('click', () => {
    const tu = nguon === 'tu_dong' ? nguonPhatHien : nguon;
    window.khongGianHoc?.ghiBanDich(d.vao.value.trim(), d.ra.textContent, TEN[tu] || '', TEN[dichSang]);
  });

  // Đọc to bằng giọng có sẵn của hệ điều hành (Web Speech API) - không gửi gì
  // ra ngoài. Máy chưa cài giọng tiếng Nhật/Hàn thì báo thay vì im lặng.
  function docTo(chu, ma) {
    if (!chu || !('speechSynthesis' in window)) return;
    const loi = giong(ma);
    if (!loi || !TEN[ma]) return;
    const goc = loi.split('-')[0].toLowerCase();
    const coGiong = speechSynthesis.getVoices().some((g) => g.lang.replace('_', '-').toLowerCase().split('-')[0] === goc);
    if (speechSynthesis.getVoices().length && !coGiong) {
      showToast(`Máy này chưa có giọng đọc ${TEN[ma].replace('Tiếng', 'tiếng')} - cài thêm trong phần Ngôn ngữ của Windows`, 3600);
      return;
    }
    speechSynthesis.cancel();
    const loiNoi = new SpeechSynthesisUtterance(chu);
    loiNoi.lang = loi;
    speechSynthesis.speak(loiNoi);
  }
  d.ngheVao.addEventListener('click', () => docTo(d.vao.value, nguon === 'tu_dong' ? nguonPhatHien : nguon));
  d.ngheRa.addEventListener('click', () => docTo(d.ra.textContent, dichSang));

  d.nutMo.addEventListener('click', () => moKhungDich());
  d.dong.addEventListener('click', () => d.hop.close());
  d.hop.addEventListener('click', (event) => {
    if (event.target === d.hop) d.hop.close();
  });
  d.hop.addEventListener('close', () => {
    dongBang(false);
    dangGoi?.abort();
    if ('speechSynthesis' in window) speechSynthesis.cancel();
  });

  // ------------------------------------------------------------
  // DỊCH CÂU TRẢ LỜI NGAY DƯỚI CÂU TRẢ LỜI
  // ------------------------------------------------------------
  let menuDangMo = null;

  function dongMenuNgonNgu() {
    menuDangMo?.remove();
    menuDangMo = null;
  }
  document.addEventListener('click', (event) => {
    if (menuDangMo && !menuDangMo.contains(event.target)) dongMenuNgonNgu();
  });

  function moMenuDichCauTraLoi(nut, phanTraLoi) {
    if (menuDangMo) {
      dongMenuNgonNgu();
      return;
    }
    const menu = document.createElement('div');
    menu.className = 'dich-menu';
    const tim = document.createElement('input');
    tim.type = 'search';
    tim.className = 'dich-menu-tim';
    tim.placeholder = 'Tìm ngôn ngữ';
    tim.autocomplete = 'off';
    tim.setAttribute('aria-label', 'Tìm ngôn ngữ để dịch câu trả lời');
    const ds = document.createElement('div');
    ds.className = 'dich-menu-ds';
    ds.setAttribute('role', 'menu');
    const ve = () => {
      ds.replaceChildren();
      const tuKhoa = tim.value.trim();
      let muc = locNgonNgu(tuKhoa);
      // Chưa gõ gì: ngôn ngữ dịch gần đây lên đầu, sau đó thứ tự của máy chủ (thông dụng trước).
      if (!tuKhoa) {
        const dau = ganDayDich.map((ma) => muc.find((n) => n.ma === ma)).filter(Boolean);
        muc = [...dau, ...muc.filter((n) => !ganDayDich.includes(n.ma))];
      }
      for (const n of muc) {
        const nutMuc = document.createElement('button');
        nutMuc.type = 'button';
        nutMuc.setAttribute('role', 'menuitem');
        nutMuc.textContent = n.ten === n.ten_goc ? n.ten : `${n.ten} · ${n.ten_goc}`;
        nutMuc.addEventListener('click', (event) => {
          event.stopPropagation();
          dongMenuNgonNgu();
          dichCauTraLoi(phanTraLoi, n.ma);
        });
        ds.append(nutMuc);
      }
      if (!muc.length) {
        const trong = document.createElement('p');
        trong.textContent = 'Không tìm thấy ngôn ngữ nào';
        ds.append(trong);
      }
    };
    tim.addEventListener('input', ve);
    tim.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        event.preventDefault();
        ds.querySelector('button')?.click();
      } else if (event.key === 'Escape') {
        dongMenuNgonNgu();
        nut.focus();
      }
    });
    menu.append(tim, ds);
    ve();
    nut.parentElement.style.position = 'relative';
    nut.after(menu);
    menu.style.left = `${nut.offsetLeft}px`;
    menuDangMo = menu;
    tim.focus();
  }

  async function dichCauTraLoi(phanTraLoi, ma) {
    const than = phanTraLoi.closest('.message-body');
    than.querySelector('.ban-dich')?.remove();
    // innerText giữ xuống dòng và gạch đầu dòng; bỏ các khung cảnh báo.
    const ban = phanTraLoi.cloneNode(true);
    ban.querySelectorAll('.answer-warning, .answer-notice').forEach((n) => n.remove());
    const tam = document.createElement('div');
    tam.style.cssText = 'position:absolute;left:-9999px;white-space:pre-wrap';
    tam.append(ban);
    document.body.append(tam);
    const vanBan = ban.innerText.trim().slice(0, KY_TU_TOI_DA);
    tam.remove();
    if (!vanBan) return;

    const khoi = document.createElement('div');
    khoi.className = 'ban-dich';
    khoi.lang = giong(ma);
    const dau = document.createElement('div');
    dau.className = 'ban-dich-dau';
    const nhan = document.createElement('strong');
    nhan.textContent = `Bản dịch ${TEN[ma].replace('Tiếng', 'tiếng')}`;
    const phu = document.createElement('span');
    phu.textContent = 'Đang dịch…';
    const dong = document.createElement('button');
    dong.type = 'button';
    dong.className = 'ban-dich-dong';
    dong.setAttribute('aria-label', 'Ẩn bản dịch');
    dong.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>';
    const huy = new AbortController();
    dong.addEventListener('click', () => {
      huy.abort();
      khoi.remove();
    });
    dau.append(nhan, phu, dong);
    const noiDung = document.createElement('div');
    noiDung.className = 'ban-dich-noi-dung';
    khoi.append(dau, noiDung);
    phanTraLoi.after(khoi);
    try {
      const banDich = await goiDich(vanBan, 'tu_dong', ma, (suKien, tamThoi) => {
        if (suKien.type === 'ngon_ngu') {
          phu.textContent = suKien.cong_cu === 'google' ? 'Google Dịch' : 'Bản dịch máy, chỉ để tham khảo';
          if (suKien.nguon === ma) phu.textContent = 'Câu trả lời đã ở ngôn ngữ này';
        } else if (suKien.type === 'phase' || suKien.type === 'warning') {
          phu.textContent = suKien.message;
        } else if (suKien.type === 'token') {
          noiDung.textContent = tamThoi;
        }
      }, huy.signal);
      noiDung.textContent = banDich;
      if (phu.textContent.startsWith('Đang')) phu.textContent = 'Bản dịch máy, chỉ để tham khảo';
    } catch (loi) {
      if (loi.name === 'AbortError') return;
      phu.textContent = loi.message || 'Không dịch được';
      khoi.classList.add('loi');
    }
  }

  window.dichGiaoDien = { moKhungDich, moMenuDichCauTraLoi };

  // Biết trước công cụ dịch để ghi chú đúng ngay khi mở khung.
  fetch('/api/dich/cau-hinh')
    .then((r) => (r.ok ? r.json() : null))
    .then((cauHinh) => {
      if (cauHinh?.cong_cu) congCu = cauHinh.cong_cu;
      if (Array.isArray(cauHinh?.ngon_ngu) && typeof cauHinh.ngon_ngu[0] === 'object') {
        napNgonNgu(cauHinh.ngon_ngu);
        if (d.hop.open) veChip();
        if (bangDangMo) veBang();
      }
    })
    .catch(() => {});
  if ('speechSynthesis' in window) speechSynthesis.getVoices();
})();
