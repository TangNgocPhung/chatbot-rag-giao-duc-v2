/* ============================================================
   SỔ TAY CỦA CUỘC TRÒ CHUYỆN
   ============================================================
   Học với chatbot thường phải mở thêm một tab Google Docs để ghi chép, và
   muốn hỏi một đoạn trong PDF thì phải chép tay đoạn đó sang khung chat. Ở đây
   mỗi cuộc trò chuyện có một cuốn sổ riêng nằm ngay bên cạnh:
     - Ghi chú: gõ tự do, hoặc chép nhanh câu trả lời / đoạn đã bôi đen.
     - Bảng vẽ: vẽ tay sơ đồ, công thức.
     - Tài liệu: đọc thẳng PDF hay ảnh chụp trang sách, khoanh chỗ chưa hiểu
       rồi bấm "Giải thích" - máy chủ đọc chữ trong vùng khoanh (OCR nếu là
       bản scan) và gửi thành câu hỏi.
   Sổ lưu trong IndexedDB của trình duyệt (localStorage chỉ có vài MB, không đủ
   chứa ảnh vùng khoanh), khoá theo mã cuộc trò chuyện, và tải về được dạng
   Word, bản in PDF hoặc ảnh bảng vẽ.

   Tệp này nạp SAU app.js và dùng lại các hàm chung của nó (showToast,
   submitQuestion, themTepDinhKem...). app.js gọi ngược lại qua
   window.khongGianHoc, luôn kèm ?. để trang vẫn chạy nếu tệp này lỗi.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const ws = {
    root: $id('workspace'),
    nutMo: $id('soTayButton'),
    cham: $id('soTayCham'),
    tenCuoc: $id('wsTenCuoc'),
    resizer: $id('wsResizer'),
    dong: $id('wsDongButton'),
    taiVe: $id('wsTaiVeButton'),
    taiVeMenu: $id('wsTaiVeMenu'),
    tabs: [...document.querySelectorAll('.ws-tab')],
    panes: [...document.querySelectorAll('.ws-pane')],
    ghiChu: $id('wsGhiChuNoiDung'),
    trangThaiGhiChu: $id('wsTrangThaiGhiChu'),
    congCuGhiChu: document.querySelector('#wsGhiChu .ws-toolbar'),
    congCuBang: $id('wsCongCuBang'),
    bangKhung: $id('wsBangVeKhung'),
    bangCanvas: $id('wsBangVeCanvas'),
    docTrong: $id('wsDocTrong'),
    docDaMo: $id('wsDocDaMo'),
    moTep: $id('wsMoTepButton'),
    fileInput: $id('wsFileInput'),
    docXem: $id('wsDocXem'),
    docChon: $id('wsDocChon'),
    trangTruoc: $id('wsTrangTruoc'),
    trangSau: $id('wsTrangSau'),
    soTrang: $id('wsSoTrang'),
    tongTrang: $id('wsTongTrang'),
    thuNho: $id('wsThuNho'),
    phongTo: $id('wsPhongTo'),
    tiLe: $id('wsTiLe'),
    congCuDoc: $id('wsCongCuDoc'),
    trangList: $id('wsDocTrangList'),
    thanhChon: $id('thanhChon'),
  };
  if (!ws.root) return;

  const DUOI_DOC_DUOC = /\.(pdf|png|jpe?g|webp|bmp|tiff?)$/i;
  const KHOA_MO = 'rag-so-tay-mo';
  const KHOA_TAB = 'rag-so-tay-tab';
  const KHOA_RONG = 'rag-so-tay-rong';
  const CAU_HOI_TOI_DA = 1900; // khung hỏi và máy chủ nhận tối đa 2000 ký tự

  const docLuu = (khoa) => { try { return localStorage.getItem(khoa); } catch { return null; } };
  const ghiLuu = (khoa, giaTri) => { try { localStorage.setItem(khoa, giaTri); } catch { /* chế độ riêng tư */ } };
  const hepVao = (giaTri, nho, lon) => Math.min(lon, Math.max(nho, giaTri));
  const lamTron = (so) => Math.round(so * 10000) / 10000;

  // ------------------------------------------------------------
  // LƯU TRỮ: khách -> IndexedDB; đã đăng nhập -> máy chủ, theo tài khoản
  // ------------------------------------------------------------
  const khoTrinhDuyet = (() => {
    let moDb = null;
    const boNhoTam = new Map(); // khi trình duyệt chặn IndexedDB (chế độ riêng tư cũ)
    let dungBoNhoTam = typeof indexedDB === 'undefined';

    function mo() {
      if (!moDb) {
        moDb = new Promise((resolve, reject) => {
          const yeuCau = indexedDB.open('rag-so-tay', 1);
          yeuCau.onupgradeneeded = () => yeuCau.result.createObjectStore('so', { keyPath: 'id' });
          yeuCau.onsuccess = () => resolve(yeuCau.result);
          yeuCau.onerror = () => reject(yeuCau.error);
        });
      }
      return moDb;
    }

    async function lam(cheDo, viec) {
      if (!dungBoNhoTam) {
        try {
          const db = await mo();
          return await new Promise((resolve, reject) => {
            const giaoDich = db.transaction('so', cheDo);
            const yeuCau = viec(giaoDich.objectStore('so'));
            giaoDich.oncomplete = () => resolve(yeuCau?.result);
            giaoDich.onerror = () => reject(giaoDich.error);
            giaoDich.onabort = () => reject(giaoDich.error);
          });
        } catch (loi) {
          if (loi?.name === 'QuotaExceededError') throw loi;
          dungBoNhoTam = true;
          showToast('Trình duyệt không cho lưu sổ tay lâu dài - sổ chỉ giữ tới khi đóng trang');
        }
      }
      return viec(null);
    }

    return {
      lay: (id) => lam('readonly', (kho) => (kho ? kho.get(id) : { result: boNhoTam.get(id) })),
      ghi: (ban) => lam('readwrite', (kho) => (kho ? kho.put(ban) : boNhoTam.set(ban.id, ban))),
      xoa: (id) => lam('readwrite', (kho) => (kho ? kho.delete(id) : boNhoTam.delete(id))),
      xoaHet: () => lam('readwrite', (kho) => (kho ? kho.clear() : boNhoTam.clear())),
      tatCa: () => lam('readonly', (kho) => (kho ? kho.getAll() : { result: [...boNhoTam.values()] })),
    };
  })();

  const duongDanSo = (id) => `/api/so-tay/${encodeURIComponent(id)}`;
  const khoMayChu = {
    async lay(id) {
      const phanHoi = await fetch(duongDanSo(id), { cache: 'no-store' });
      if (!phanHoi.ok) throw new Error('Không tải được sổ tay từ máy chủ');
      return (await phanHoi.json()).so_tay || undefined;
    },
    async ghi(ban) {
      const phanHoi = await fetch(duongDanSo(ban.id), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ban),
      });
      if (!phanHoi.ok) {
        const loi = new Error((await phanHoi.json().catch(() => ({}))).detail || 'Không lưu được sổ tay lên máy chủ');
        if (phanHoi.status === 413) loi.name = 'QuotaExceededError';
        throw loi;
      }
    },
    async xoa(id) {
      await fetch(duongDanSo(id), { method: 'DELETE' });
    },
    // "Xóa lịch sử" của tài khoản đã xóa luôn sổ trên máy chủ; sổ mồ côi thì
    // máy chủ giữ theo tài khoản nên không cần dọn từ phía trình duyệt.
    xoaHet: async () => {},
    tatCa: async () => [],
  };

  const khoHienTai = () => (nguoiDung ? khoMayChu : khoTrinhDuyet);
  const khoSo = {
    lay: (id) => khoHienTai().lay(id),
    ghi: (ban) => khoHienTai().ghi(ban),
    xoa: (id) => khoHienTai().xoa(id),
    xoaHet: () => khoHienTai().xoaHet(),
    tatCa: () => khoHienTai().tatCa(),
  };

  // ------------------------------------------------------------
  // TRẠNG THÁI SỔ ĐANG MỞ
  // ------------------------------------------------------------
  let so = null;
  let henLuu = 0;
  let phienNap = 0;
  const daXoa = new Set();

  const soTrong = (id) => ({ id, ghiChu: '', bang: [], taiLieu: {}, taiLieuMo: null, capNhat: Date.now() });

  function coGhiChu(ban) {
    if (!ban?.ghiChu) return false;
    return /<img\s/i.test(ban.ghiChu) || ban.ghiChu.replace(/<[^>]*>|&nbsp;/g, '').trim().length > 0;
  }

  function coNoiDung(ban) {
    if (!ban) return false;
    const coDanhDau = Object.values(ban.taiLieu || {})
      .some((tl) => Object.values(tl.net || {}).some((mang) => mang.length));
    return coGhiChu(ban) || ban.bang?.length > 0 || coDanhDau || Object.keys(ban.taiLieu || {}).length > 0;
  }

  function capNhatCham() {
    ws.cham.classList.toggle('hidden', !(coGhiChu(so) || so?.bang?.length));
  }

  async function luuNgay() {
    window.clearTimeout(henLuu);
    henLuu = 0;
    if (!so || daXoa.has(so.id)) return;
    so.capNhat = Date.now();
    try {
      if (coNoiDung(so)) await khoSo.ghi(structuredClone(so));
      else await khoSo.xoa(so.id);
      if (ws.trangThaiGhiChu.dataset.dangLuu) {
        delete ws.trangThaiGhiChu.dataset.dangLuu;
        capNhatTrangThaiGhiChu();
      }
    } catch (loi) {
      showToast(loi?.name === 'QuotaExceededError'
        ? 'Sổ tay đã quá lớn - hãy tải về rồi xóa bớt ảnh'
        : (nguoiDung ? loi?.message || 'Không lưu được sổ tay lên máy chủ' : 'Không lưu được sổ tay vào trình duyệt'));
    }
    capNhatCham();
  }

  function henLuuSo() {
    window.clearTimeout(henLuu);
    // Lưu lên máy chủ là gửi cả cuốn sổ (có thể kèm ảnh) - đợi lâu hơn một
    // chút để gõ liền mạch không thành mỗi phím một lần gửi.
    henLuu = window.setTimeout(luuNgay, nguoiDung ? 1500 : 450);
  }

  // Sổ khách viết trước khi đăng ký đi theo sang tài khoản, như lịch sử chat.
  async function chuyenSoKhachLenTaiKhoan() {
    let cacSo = [];
    try {
      cacSo = (await khoTrinhDuyet.tatCa()) || [];
    } catch {
      return;
    }
    let loi = false;
    for (const ban of cacSo) {
      try {
        await khoMayChu.ghi(ban);
      } catch {
        loi = true;
      }
    }
    if (!loi) await khoTrinhDuyet.xoaHet().catch(() => {});
  }

  function tenCuocTroChuyen() {
    return currentChat?.title || 'Cuộc trò chuyện mới';
  }

  function capNhatTieuDe() {
    ws.tenCuoc.textContent = tenCuocTroChuyen();
    ws.tenCuoc.title = tenCuocTroChuyen();
  }

  async function doiCuocTroChuyen() {
    const id = maCuocTroChuyenHienTai();
    capNhatTieuDe();
    if (so?.id === id) return;
    await luuNgay();
    const phien = ++phienNap;
    // Gán sổ trống ngay để thao tác trong lúc chờ IndexedDB không rơi vào sổ cũ.
    so = soTrong(id);
    let ban = null;
    try {
      ban = await khoSo.lay(id);
    } catch {
      /* đọc hỏng thì coi như sổ mới */
    }
    if (phien !== phienNap) return;
    if (ban) so = Object.assign(soTrong(id), ban);
    napGiaoDien();
  }

  function napGiaoDien() {
    dongHoiVung();
    doanChoHoi = null;
    ws.ghiChu.innerHTML = lamSach(so.ghiChu);
    capNhatTrangThaiGhiChu();
    hoanTacBang.length = 0;
    hoanTacDoc.length = 0;
    veBang();
    dongTaiLieuHienTai();
    capNhatDanhSachDaMo();
    const mo = so.taiLieuMo && so.taiLieu[so.taiLieuMo];
    if (mo) moTaiLieu({ ...mo, trang: mo.trang }, { chuyenTab: false });
    capNhatCham();
  }

  function xoaSo(id) {
    daXoa.add(id);
    if (so?.id === id) window.clearTimeout(henLuu);
    khoSo.xoa(id).catch(() => {});
  }

  async function xoaHetSo() {
    window.clearTimeout(henLuu);
    if (so) daXoa.add(so.id);
    try {
      await khoSo.xoaHet();
    } catch {
      /* lần mở trang sau sẽ dọn nốt các sổ mồ côi */
    }
  }

  // Sổ của cuộc trò chuyện đã rơi khỏi lịch sử (xóa ở tab khác, bị cắt bớt
  // khi bộ nhớ đầy) thì không ai mở lại được nữa. Chờ lâu hẳn mới dọn để
  // không xóa nhầm sổ của cuộc vừa bị đẩy khỏi danh sách "Gần đây".
  async function donSoMoCoi() {
    const conDung = new Set(loadHistory().map((chat) => chat.id));
    const han = Date.now() - 60 * 24 * 3600 * 1000;
    try {
      for (const ban of (await khoSo.tatCa()) || []) {
        if (!conDung.has(ban.id) && ban.id !== so?.id && (ban.capNhat || 0) < han) {
          await khoSo.xoa(ban.id);
        }
      }
    } catch {
      /* không quan trọng */
    }
  }

  // ------------------------------------------------------------
  // MỞ / ĐÓNG / ĐỔI CỠ / ĐỔI THẺ
  // ------------------------------------------------------------
  const laManHep = () => window.matchMedia('(max-width: 800px)').matches;

  function moSoTay(the) {
    ws.root.classList.remove('hidden');
    elements.appShell.classList.add('co-so-tay');
    ws.nutMo.setAttribute('aria-expanded', 'true');
    ws.nutMo.classList.add('active');
    ghiLuu(KHOA_MO, '1');
    if (the) chonThe(the);
    if (laManHep()) closeSidebar();
    window.requestAnimationFrame(() => {
      doKichThuocBang();
      capNhatCoTrang();
    });
  }

  function dongSoTay() {
    ws.root.classList.add('hidden');
    elements.appShell.classList.remove('co-so-tay');
    ws.nutMo.setAttribute('aria-expanded', 'false');
    ws.nutMo.classList.remove('active');
    ghiLuu(KHOA_MO, '0');
    dongMenuTaiVe();
    luuNgay();
  }

  function chonThe(the) {
    for (const nut of ws.tabs) {
      const chon = nut.dataset.tab === the;
      nut.setAttribute('aria-selected', String(chon));
      nut.tabIndex = chon ? 0 : -1;
    }
    for (const pane of ws.panes) pane.classList.toggle('hidden', pane.dataset.pane !== the);
    ghiLuu(KHOA_TAB, the);
    if (the === 'bang-ve') window.requestAnimationFrame(doKichThuocBang);
    if (the === 'tai-lieu') {
      window.requestAnimationFrame(() => {
        capNhatCoTrang();
        // Tài liệu mở lại lúc sổ đang ẩn thì chưa cuộn được tới trang đang đọc dở.
        const trangDo = docDangMo && so?.taiLieu[docDangMo.khoa]?.trang;
        if (trangDo > 1 && ws.trangList.scrollTop === 0) denTrang(trangDo, false);
      });
    }
  }

  function datDoRong(px) {
    const lon = Math.max(360, window.innerWidth - 560);
    const rong = hepVao(Math.round(px), 320, lon);
    elements.appShell.style.setProperty('--rong-so-tay', `${rong}px`);
    return rong;
  }

  ws.nutMo.addEventListener('click', () => {
    if (ws.root.classList.contains('hidden')) moSoTay();
    else dongSoTay();
  });
  ws.dong.addEventListener('click', dongSoTay);
  ws.tabs.forEach((nut, viTri) => {
    nut.addEventListener('click', () => chonThe(nut.dataset.tab));
    nut.addEventListener('keydown', (event) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
      const buoc = event.key === 'ArrowRight' ? 1 : -1;
      const ke = ws.tabs[(viTri + buoc + ws.tabs.length) % ws.tabs.length];
      chonThe(ke.dataset.tab);
      ke.focus();
    });
  });

  ws.resizer.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    ws.resizer.setPointerCapture(event.pointerId);
    elements.appShell.classList.add('dang-keo-so-tay');
    const keo = (e) => datDoRong(window.innerWidth - e.clientX);
    const tha = () => {
      ws.resizer.removeEventListener('pointermove', keo);
      elements.appShell.classList.remove('dang-keo-so-tay');
      ghiLuu(KHOA_RONG, String(ws.root.getBoundingClientRect().width | 0));
      doKichThuocBang();
      capNhatCoTrang();
    };
    ws.resizer.addEventListener('pointermove', keo);
    ws.resizer.addEventListener('pointerup', tha, { once: true });
    ws.resizer.addEventListener('pointercancel', tha, { once: true });
  });
  ws.resizer.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault();
    const hienTai = ws.root.getBoundingClientRect().width;
    const rong = datDoRong(hienTai + (event.key === 'ArrowLeft' ? 32 : -32));
    ghiLuu(KHOA_RONG, String(rong));
    doKichThuocBang();
    capNhatCoTrang();
  });

  document.addEventListener('keydown', (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === '/') {
      event.preventDefault();
      if (ws.root.classList.contains('hidden')) moSoTay();
      else dongSoTay();
    } else if (event.key === 'Escape') {
      if (!ws.taiVeMenu.classList.contains('hidden')) dongMenuTaiVe();
      else if (document.querySelector('.hoi-vung')) dongHoiVung();
    }
  });
  window.addEventListener('pagehide', () => { luuNgay(); });
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') luuNgay();
  });

  // ------------------------------------------------------------
  // GHI CHÚ
  // ------------------------------------------------------------
  // Nội dung ghi chú là HTML người dùng dán vào, nên mỗi lần nạp và mỗi lần
  // chèn đều lọc lại theo danh sách trắng: không script, không thuộc tính
  // on*, ảnh chỉ nhận data: do chính trang này tạo ra.
  const THE_GIU = new Set([
    'P', 'DIV', 'BR', 'B', 'STRONG', 'I', 'EM', 'U', 'S', 'UL', 'OL', 'LI', 'H3', 'H4', 'H5',
    'BLOCKQUOTE', 'MARK', 'SPAN', 'SMALL', 'CODE', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TH',
    'TD', 'IMG', 'INPUT', 'HR',
  ]);
  const THE_BO_HAN = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'TEMPLATE', 'SVG', 'MATH', 'NOSCRIPT', 'BUTTON', 'SELECT', 'TEXTAREA']);

  function lamSach(html) {
    const tam = new DOMParser().parseFromString(`<body>${html || ''}</body>`, 'text/html');
    const duyet = (nut) => {
      for (const con of [...nut.children]) {
        if (THE_BO_HAN.has(con.tagName)) {
          con.remove();
          continue;
        }
        if (!THE_GIU.has(con.tagName)) {
          duyet(con);
          con.replaceWith(...con.childNodes);
          continue;
        }
        for (const { name: ten, value: giaTri } of [...con.attributes]) {
          const giu = ten === 'class'
            || (con.tagName === 'IMG' && ten === 'src' && /^data:image\/(png|jpeg|webp);base64,[a-z0-9+/=]+$/i.test(giaTri))
            || (con.tagName === 'IMG' && (ten === 'width' || ten === 'alt'))
            || (con.tagName === 'INPUT' && ((ten === 'type' && giaTri === 'checkbox') || ten === 'checked'));
          if (!giu) con.removeAttribute(ten);
        }
        if ((con.tagName === 'INPUT' && con.getAttribute('type') !== 'checkbox')
            || (con.tagName === 'IMG' && !con.getAttribute('src'))) {
          con.remove();
          continue;
        }
        duyet(con);
      }
    };
    duyet(tam.body);
    return tam.body.innerHTML;
  }

  function capNhatTrangThaiGhiChu() {
    const chu = ws.ghiChu.innerText.trim();
    const soChu = chu ? chu.split(/\s+/).length : 0;
    ws.ghiChu.classList.toggle('trong', !soChu && !ws.ghiChu.querySelector('img, input, li'));
    if (ws.trangThaiGhiChu.dataset.dangLuu) {
      ws.trangThaiGhiChu.textContent = 'Đang lưu…';
      return;
    }
    ws.trangThaiGhiChu.textContent = soChu || ws.ghiChu.querySelector('img')
      ? `Đã lưu trong trình duyệt · ${soChu.toLocaleString('vi-VN')} chữ`
      : 'Chưa có ghi chú';
  }

  function khiGhiChuDoi() {
    so.ghiChu = ws.ghiChu.innerHTML;
    ws.trangThaiGhiChu.dataset.dangLuu = '1';
    capNhatTrangThaiGhiChu();
    henLuuSo();
  }

  ws.ghiChu.addEventListener('input', khiGhiChuDoi);
  // Dán chỉ lấy chữ thuần: HTML chép từ trang khác mang theo màu chữ, phông
  // chữ, nền trắng... làm vỡ giao diện tối và phình dung lượng sổ.
  ws.ghiChu.addEventListener('paste', (event) => {
    const chu = event.clipboardData?.getData('text/plain');
    if (chu == null) return;
    event.preventDefault();
    document.execCommand('insertText', false, chu);
  });
  ws.ghiChu.addEventListener('drop', (event) => {
    if (event.dataTransfer?.files?.length) event.preventDefault();
  });
  // Ô đánh dấu trong vùng soạn thảo: trình duyệt chỉ đổi thuộc tính "checked"
  // của đối tượng, không đổi HTML, nên phải ghi tay thì mới lưu lại được.
  ws.ghiChu.addEventListener('change', (event) => {
    const o = event.target;
    if (o.matches?.('input[type="checkbox"]')) {
      o.toggleAttribute('checked', o.checked);
      o.closest('.viec')?.classList.toggle('xong', o.checked);
      khiGhiChuDoi();
    }
  });

  try {
    document.execCommand('styleWithCSS', false, false);
  } catch {
    /* trình duyệt cũ */
  }

  function vungChonTrongGhiChu() {
    const chon = window.getSelection();
    if (!chon?.rangeCount) return null;
    const vung = chon.getRangeAt(0);
    return ws.ghiChu.contains(vung.commonAncestorContainer) ? vung : null;
  }

  function toVang() {
    const vung = vungChonTrongGhiChu();
    if (!vung) return;
    const dau = vung.commonAncestorContainer;
    const markCo = (dau.nodeType === 1 ? dau : dau.parentElement)?.closest('mark');
    if (markCo && ws.ghiChu.contains(markCo)) {
      markCo.replaceWith(...markCo.childNodes);
    } else if (!vung.collapsed) {
      const mark = document.createElement('mark');
      mark.append(vung.extractContents());
      vung.insertNode(mark);
    }
    khiGhiChuDoi();
  }

  ws.congCuGhiChu.addEventListener('mousedown', (event) => {
    // Giữ nguyên vùng đang bôi đen trong ghi chú khi bấm nút định dạng.
    if (event.target.closest('button')) event.preventDefault();
  });
  ws.congCuGhiChu.addEventListener('click', (event) => {
    const nut = event.target.closest('button[data-lenh]');
    if (!nut) return;
    if (!vungChonTrongGhiChu()) ws.ghiChu.focus();
    const lenh = nut.dataset.lenh;
    if (lenh === 'to-vang') {
      toVang();
      return;
    }
    if (lenh === 'tieu-de') {
      const dangLa = String(document.queryCommandValue('formatBlock')).toLowerCase();
      document.execCommand('formatBlock', false, dangLa === 'h4' ? 'p' : 'h4');
    } else if (lenh === 'checklist') {
      document.execCommand('insertHTML', false, '<div class="viec"><input type="checkbox">&nbsp;</div>');
    } else {
      document.execCommand(lenh, false, null);
    }
    khiGhiChuDoi();
  });

  // Chép một khối vào cuối sổ. Luôn đi qua lamSach rồi thêm một dòng trống
  // phía sau để người dùng gõ tiếp ngay dưới đoạn vừa chép.
  function ghiVaoSo(khoi, { mo = true, thongBao = 'Đã ghi vào sổ tay' } = {}) {
    if (!so) return;
    const tam = document.createElement('div');
    tam.innerHTML = lamSach(khoi.outerHTML);
    const dongTrong = document.createElement('p');
    dongTrong.append(document.createElement('br'));
    const vuaThem = tam.firstElementChild;
    ws.ghiChu.append(...tam.childNodes, dongTrong);
    khiGhiChuDoi();
    luuNgay();
    if (mo) {
      moSoTay('ghi-chu');
      window.requestAnimationFrame(() => {
        vuaThem?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        vuaThem?.classList.add('vua-them');
        window.setTimeout(() => vuaThem?.classList.remove('vua-them'), 1600);
      });
    }
    showToast(thongBao);
  }

  function thoiGianNgan() {
    return new Date().toLocaleString('vi-VN', { hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit' });
  }

  function ghiCauTraLoi(cauHoi, phanTraLoi) {
    const khoi = document.createElement('blockquote');
    khoi.className = 'trich-chat';
    const dau = document.createElement('p');
    dau.className = 'trich-nguon';
    dau.textContent = `Trợ lý giáo dục · ${thoiGianNgan()}`;
    khoi.append(dau);
    if (cauHoi) {
      const hoi = document.createElement('p');
      const nhan = document.createElement('strong');
      nhan.textContent = 'Hỏi: ';
      hoi.append(nhan, cauHoi);
      khoi.append(hoi);
    }
    const ban = phanTraLoi.cloneNode(true);
    ban.querySelectorAll('.answer-warning, .answer-notice').forEach((nut) => nut.remove());
    khoi.append(...ban.childNodes);
    ghiVaoSo(khoi);
  }

  function ghiBanDich(goc, banDich, tuNgonNgu, sangNgonNgu) {
    if (!banDich) return;
    const khoi = document.createElement('blockquote');
    khoi.className = 'trich-chat';
    const dau = document.createElement('p');
    dau.className = 'trich-nguon';
    dau.textContent = `Bản dịch ${tuNgonNgu ? `${tuNgonNgu} → ` : ''}${sangNgonNgu} · ${thoiGianNgan()}`;
    const doanGoc = document.createElement('p');
    doanGoc.textContent = goc;
    const doanDich = document.createElement('p');
    const dam = document.createElement('strong');
    dam.textContent = banDich;
    doanDich.append(dam);
    khoi.append(dau, doanGoc, doanDich);
    ghiVaoSo(khoi, { mo: false, thongBao: 'Đã ghi bản dịch vào sổ tay' });
  }

  // ------------------------------------------------------------
  // BÔI ĐEN TRONG KHUNG CHAT -> "Ghi vào sổ" / "Hỏi về đoạn này"
  // ------------------------------------------------------------
  let vungChonChat = null;
  let henThanhChon = 0;

  function anThanhChon() {
    ws.thanhChon.classList.add('hidden');
    vungChonChat = null;
  }

  function capNhatThanhChon() {
    const chon = window.getSelection();
    if (!chon || chon.isCollapsed || !chon.rangeCount) {
      anThanhChon();
      return;
    }
    const vung = chon.getRangeAt(0);
    const goc = vung.commonAncestorContainer;
    const phanTu = goc.nodeType === 1 ? goc : goc.parentElement;
    if (!phanTu?.closest('#messages .answer-text, #messages .user-bubble, #messages .message-body')
        || chon.toString().trim().length < 2) {
      anThanhChon();
      return;
    }
    vungChonChat = vung.cloneRange();
    const khung = vung.getBoundingClientRect();
    ws.thanhChon.classList.remove('hidden');
    const rong = ws.thanhChon.offsetWidth;
    const tren = khung.top - ws.thanhChon.offsetHeight - 8;
    ws.thanhChon.style.top = `${tren < 8 ? khung.bottom + 8 : tren}px`;
    ws.thanhChon.style.left = `${hepVao(khung.left + khung.width / 2 - rong / 2, 8, window.innerWidth - rong - 8)}px`;
  }

  document.addEventListener('selectionchange', () => {
    window.clearTimeout(henThanhChon);
    henThanhChon = window.setTimeout(capNhatThanhChon, 180);
  });
  elements.chatScroll.addEventListener('scroll', anThanhChon, { passive: true });
  ws.thanhChon.addEventListener('mousedown', (event) => event.preventDefault());
  ws.thanhChon.addEventListener('click', (event) => {
    const nut = event.target.closest('button[data-chon]');
    if (!nut || !vungChonChat) return;
    const chu = vungChonChat.toString().trim();
    if (nut.dataset.chon === 'ghi') {
      const khoi = document.createElement('blockquote');
      khoi.className = 'trich-chat';
      const dau = document.createElement('p');
      dau.className = 'trich-nguon';
      dau.textContent = `Trích từ cuộc trò chuyện · ${thoiGianNgan()}`;
      const noiDung = document.createElement('div');
      noiDung.append(vungChonChat.cloneContents());
      khoi.append(dau, noiDung);
      ghiVaoSo(khoi);
    } else if (nut.dataset.chon === 'dich') {
      window.dichGiaoDien?.moKhungDich(chu);
    } else {
      dienKhungHoi(`Giải thích rõ hơn giúp mình đoạn này: "${catNgan(chu, 1500)}"`);
    }
    window.getSelection()?.removeAllRanges();
    anThanhChon();
  });

  function catNgan(chu, toiDa) {
    const gon = chu.replace(/\s+/g, ' ').trim();
    return gon.length > toiDa ? `${gon.slice(0, toiDa - 1).trimEnd()}…` : gon;
  }

  function dienKhungHoi(noiDung) {
    elements.input.value = noiDung.slice(0, 2000);
    resizeInput();
    if (laManHep()) dongSoTay();
    elements.input.focus();
    elements.input.setSelectionRange(elements.input.value.length, elements.input.value.length);
  }

  // ------------------------------------------------------------
  // VẼ: dùng chung cho bảng vẽ và lớp đánh dấu trên từng trang tài liệu
  // ------------------------------------------------------------
  // Nét vẽ lưu dạng véc-tơ với toạ độ 0..1 theo khung, nên phóng to, thu nhỏ
  // hay đổi cỡ sổ tay đều vẽ lại sắc nét, và mỗi nét chỉ tốn vài trăm byte.
  //   { c: 'but' | 'to-sang' | 'khoanh', m: màu, d: độ dày theo bề rộng, p: [x, y, x, y...] }
  // Khoanh để hỏi kéo khung chữ nhật như Snipping Tool: { c: 'khoanh', h: 'cn',
  // p: [x góc đầu, y góc đầu, x góc cuối, y góc cuối] }. Nét khoanh tay do bản cũ
  // lưu (không có h) vẫn vẽ lại được.
  const MAU = [
    ['#1f2a44', 'Mực đen'],
    ['#2f62c9', 'Xanh dương'],
    ['#d64534', 'Đỏ'],
    ['#2f8a5b', 'Xanh lá'],
    ['#8a4fc7', 'Tím'],
  ];
  const MAU_TO_SANG = '#ffd43b';
  const MAU_KHOANH = '#d64534';

  function veNet(ctx, net, w, h) {
    const p = net.p;
    if (!p || p.length < 2) return;
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    if (net.c === 'khoanh') {
      ctx.strokeStyle = MAU_KHOANH;
      ctx.lineWidth = Math.max(2, w * 0.003);
      ctx.setLineDash([w * 0.012, w * 0.008]);
      ctx.fillStyle = 'rgba(214, 69, 52, .08)';
      if (net.h === 'cn') {
        const [x0, y0, x1, y1] = p;
        const trai = Math.min(x0, x1) * w;
        const tren = Math.min(y0, y1) * h;
        const rong = Math.abs(x1 - x0) * w;
        const cao = Math.abs(y1 - y0) * h;
        ctx.fillRect(trai, tren, rong, cao);
        ctx.strokeRect(trai, tren, rong, cao);
        ctx.restore();
        return;
      }
    } else {
      ctx.strokeStyle = net.m;
      ctx.lineWidth = Math.max(1, net.d * w);
      if (net.c === 'to-sang') ctx.globalAlpha = 0.38;
    }
    ctx.beginPath();
    ctx.moveTo(p[0] * w, p[1] * h);
    if (p.length === 2) ctx.lineTo(p[0] * w + 0.1, p[1] * h);
    for (let i = 2; i < p.length - 2; i += 2) {
      const giuaX = ((p[i] + p[i + 2]) / 2) * w;
      const giuaY = ((p[i + 1] + p[i + 3]) / 2) * h;
      ctx.quadraticCurveTo(p[i] * w, p[i + 1] * h, giuaX, giuaY);
    }
    if (p.length >= 4) ctx.lineTo(p[p.length - 2] * w, p[p.length - 1] * h);
    if (net.c === 'khoanh') {
      ctx.closePath();
      ctx.fill();
    }
    ctx.stroke();
    ctx.restore();
  }

  // Gắn thao tác vẽ vào một canvas. cauHinh:
  //   layNet() -> mảng nét của mặt này; congCu() -> { cu, mau, co }
  //   doDay(congCu) -> độ dày; them(net) / xoa(nets) / khoanh(net) / batDau()
  function ganMatVe(canvas, cauHinh) {
    let dangVe = null;
    let conTro = null;
    let henVe = 0;

    const toaDo = (event) => {
      const khung = canvas.getBoundingClientRect();
      return [
        hepVao((event.clientX - khung.left) / khung.width, 0, 1),
        hepVao((event.clientY - khung.top) / khung.height, 0, 1),
      ];
    };

    function ve() {
      henVe = 0;
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const net of cauHinh.layNet()) veNet(ctx, net, canvas.width, canvas.height);
      if (dangVe && !dangVe.tay) veNet(ctx, dangVe, canvas.width, canvas.height);
    }
    const henVeLai = () => { if (!henVe) henVe = window.requestAnimationFrame(ve); };

    function doKichThuoc() {
      const khung = canvas.getBoundingClientRect();
      if (!khung.width) return;
      const tiLe = window.devicePixelRatio || 1;
      const rong = Math.round(khung.width * tiLe);
      const cao = Math.round(khung.height * tiLe);
      if (canvas.width !== rong || canvas.height !== cao) {
        canvas.width = rong;
        canvas.height = cao;
      }
      ve();
    }

    function tayTai(x, y) {
      const w = canvas.width;
      const h = canvas.height;
      const nguong = 12 * (window.devicePixelRatio || 1);
      const trung = cauHinh.layNet().filter((net) => {
        // Khung chữ nhật chỉ lưu hai góc: tẩy trúng khi chạm vào cạnh khung.
        if (net.h === 'cn') {
          const [x0, x1] = [Math.min(net.p[0], net.p[2]) * w, Math.max(net.p[0], net.p[2]) * w];
          const [y0, y1] = [Math.min(net.p[1], net.p[3]) * h, Math.max(net.p[1], net.p[3]) * h];
          const [px, py] = [x * w, y * h];
          const ngoai = Math.hypot(Math.max(x0 - px, 0, px - x1), Math.max(y0 - py, 0, py - y1));
          const trong = Math.min(px - x0, x1 - px, py - y0, y1 - py);
          return (ngoai > 0 ? ngoai : trong) <= nguong;
        }
        const banKinh = Math.max(nguong, ((net.d || 0) * w) / 2 + nguong / 2);
        for (let i = 0; i < net.p.length; i += 2) {
          if (Math.hypot((net.p[i] - x) * w, (net.p[i + 1] - y) * h) <= banKinh) return true;
        }
        return false;
      });
      if (trung.length) {
        cauHinh.xoa(trung);
        ve();
      }
    }

    canvas.addEventListener('pointerdown', (event) => {
      const cc = cauHinh.congCu();
      if (cc.cu === 'cuon') return;
      if (event.pointerType === 'mouse' && event.button !== 0) return;
      event.preventDefault();
      cauHinh.batDau?.();
      canvas.setPointerCapture(event.pointerId);
      conTro = event.pointerId;
      const [x, y] = toaDo(event);
      if (cc.cu === 'tay') {
        dangVe = { tay: true };
        tayTai(x, y);
        return;
      }
      if (cc.cu === 'khoanh') {
        dangVe = { c: 'khoanh', h: 'cn', p: [lamTron(x), lamTron(y), lamTron(x), lamTron(y)] };
        henVeLai();
        return;
      }
      dangVe = {
        c: cc.cu,
        m: cc.cu === 'to-sang' ? MAU_TO_SANG : cc.mau,
        d: cauHinh.doDay(cc),
        p: [lamTron(x), lamTron(y)],
      };
      henVeLai();
    });

    canvas.addEventListener('pointermove', (event) => {
      if (!dangVe || event.pointerId !== conTro) return;
      if (dangVe.h === 'cn') {
        const [x, y] = toaDo(event);
        dangVe.p[2] = lamTron(x);
        dangVe.p[3] = lamTron(y);
        henVeLai();
        return;
      }
      const cacSuKien = event.getCoalescedEvents?.() || [event];
      for (const suKien of cacSuKien) {
        const [x, y] = toaDo(suKien);
        if (dangVe.tay) {
          tayTai(x, y);
          continue;
        }
        const p = dangVe.p;
        if (Math.hypot(x - p[p.length - 2], y - p[p.length - 1]) > 0.0015) p.push(lamTron(x), lamTron(y));
      }
      if (!dangVe.tay) henVeLai();
    });

    const ketThuc = (event) => {
      if (!dangVe || event.pointerId !== conTro) return;
      const net = dangVe;
      dangVe = null;
      conTro = null;
      if (net.tay) return;
      if (net.c === 'khoanh') cauHinh.khoanh?.(net);
      else cauHinh.them(net);
      ve();
    };
    canvas.addEventListener('pointerup', ketThuc);
    canvas.addEventListener('pointercancel', ketThuc);

    return { ve, doKichThuoc };
  }

  const ICON = {
    khoanh: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4.5" width="14" height="11" rx="1" stroke-dasharray="3 2.4"/><path d="m14 12 6.5 2.6-2.8 1.1-1.1 2.8L14 12Z"/></svg>',
    but: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 20 4-1 11-11-3-3L5 16l-1 4Z"/><path d="m14 7 3 3"/></svg>',
    'to-sang': '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 14.5 7.5-7.5 3 3-7.5 7.5H9v-3Z"/><path d="m9 17.5-2.5 2.5H3.5L7 16.5M13.5 10l3 3"/></svg>',
    tay: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8.5 20 3.8 15.3a1.6 1.6 0 0 1 0-2.3L13 3.8a1.6 1.6 0 0 1 2.3 0l4.9 4.9a1.6 1.6 0 0 1 0 2.3L11 20H8.5Z"/><path d="M13 20h8M8 9.5l6.5 6.5"/></svg>',
    cuon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 13V6a1.5 1.5 0 0 1 3 0v5.5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v7.5a6.5 6.5 0 0 1-6.5 6.5h-.3a5.7 5.7 0 0 1-4.9-2.8l-1.8-3a1.5 1.5 0 0 1 2.5-1.6L8 14"/></svg>',
    hoanTac: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/></svg>',
    xoa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 13h8l1-13"/></svg>',
  };
  const NHAN_CU = {
    khoanh: 'Khoanh để hỏi',
    but: 'Bút',
    'to-sang': 'Tô sáng',
    tay: 'Tẩy',
    cuon: 'Cuộn',
  };
  const NHAN_CO = { manh: 'Nét mảnh', vua: 'Nét vừa', dam: 'Nét đậm' };
  const THU_TU_CO = ['manh', 'vua', 'dam'];

  // Thanh công cụ vẽ dựng bằng JS vì bảng vẽ và trình đọc dùng chung một kiểu.
  function dungThanhCongCu(khung, trangThai, { cacCu, coCo, khiHoanTac, khiXoaHet, nhanXoaHet }) {
    khung.replaceChildren();
    const nutCu = new Map();
    for (const cu of cacCu) {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = `cong-cu cu-${cu}`;
      nut.innerHTML = ICON[cu];
      nut.title = NHAN_CU[cu];
      nut.setAttribute('aria-label', NHAN_CU[cu]);
      if (cu === 'khoanh') {
        const chu = document.createElement('span');
        chu.textContent = 'Khoanh để hỏi';
        nut.append(chu);
      }
      nut.addEventListener('click', () => {
        trangThai.cu = cu;
        capNhat();
      });
      nutCu.set(cu, nut);
      khung.append(nut);
    }
    const gach = () => {
      const g = document.createElement('span');
      g.className = 'ws-toolbar-gach';
      khung.append(g);
    };
    gach();
    const oMau = document.createElement('div');
    oMau.className = 'bang-mau';
    for (const [ma, ten] of MAU) {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = 'o-mau';
      nut.style.setProperty('--mau', ma);
      nut.title = ten;
      nut.setAttribute('aria-label', `Màu ${ten}`);
      nut.dataset.mau = ma;
      nut.addEventListener('click', () => {
        trangThai.mau = ma;
        if (trangThai.cu !== 'but') trangThai.cu = 'but';
        capNhat();
      });
      oMau.append(nut);
    }
    khung.append(oMau);
    let nutCo = null;
    if (coCo) {
      nutCo = document.createElement('button');
      nutCo.type = 'button';
      nutCo.className = 'cong-cu co-net';
      nutCo.addEventListener('click', () => {
        trangThai.co = THU_TU_CO[(THU_TU_CO.indexOf(trangThai.co) + 1) % THU_TU_CO.length];
        capNhat();
      });
      khung.append(nutCo);
    }
    gach();
    const hoanTac = document.createElement('button');
    hoanTac.type = 'button';
    hoanTac.className = 'cong-cu';
    hoanTac.innerHTML = ICON.hoanTac;
    hoanTac.title = 'Hoàn tác (Ctrl + Z)';
    hoanTac.setAttribute('aria-label', 'Hoàn tác');
    hoanTac.addEventListener('click', khiHoanTac);
    const xoaHet = document.createElement('button');
    xoaHet.type = 'button';
    xoaHet.className = 'cong-cu';
    xoaHet.innerHTML = ICON.xoa;
    xoaHet.title = nhanXoaHet;
    xoaHet.setAttribute('aria-label', nhanXoaHet);
    xoaHet.addEventListener('click', khiXoaHet);
    khung.append(hoanTac, xoaHet);

    function capNhat() {
      for (const [cu, nut] of nutCu) nut.setAttribute('aria-pressed', String(trangThai.cu === cu));
      for (const nut of oMau.children) {
        nut.setAttribute('aria-pressed', String(trangThai.mau === nut.dataset.mau && trangThai.cu === 'but'));
      }
      if (nutCo) {
        nutCo.title = NHAN_CO[trangThai.co];
        nutCo.setAttribute('aria-label', `Độ dày: ${NHAN_CO[trangThai.co]}`);
        nutCo.innerHTML = `<i class="co-${trangThai.co}"></i>`;
      }
      trangThai.khiDoi?.();
    }
    capNhat();
    return capNhat;
  }

  // ------------------------------------------------------------
  // BẢNG VẼ
  // ------------------------------------------------------------
  const TI_LE_BANG = 1.4; // cao / rộng, gần khổ A4 dọc
  const congCuBang = { cu: 'but', mau: MAU[0][0], co: 'vua' };
  const DO_DAY_BANG = { manh: 0.003, vua: 0.006, dam: 0.012 };
  const hoanTacBang = [];

  const matBang = ganMatVe(ws.bangCanvas, {
    layNet: () => so?.bang || [],
    congCu: () => congCuBang,
    doDay: (cc) => (cc.cu === 'to-sang' ? 0.03 : DO_DAY_BANG[cc.co]),
    them: (net) => {
      so.bang.push(net);
      hoanTacBang.push({ loai: 'them', nets: [net] });
      khiBangDoi();
    },
    xoa: (nets) => {
      so.bang = so.bang.filter((net) => !nets.includes(net));
      hoanTacBang.push({ loai: 'xoa', nets });
      khiBangDoi();
    },
  });

  function khiBangDoi() {
    henLuuSo();
    capNhatCham();
  }

  function veBang() {
    matBang.ve();
  }

  function doKichThuocBang() {
    if (ws.bangKhung.offsetParent) matBang.doKichThuoc();
  }

  function hoanTacTrenBang() {
    const buoc = hoanTacBang.pop();
    if (!buoc) return;
    if (buoc.loai === 'them') so.bang = so.bang.filter((net) => !buoc.nets.includes(net));
    else so.bang.push(...buoc.nets);
    veBang();
    khiBangDoi();
  }

  dungThanhCongCu(ws.congCuBang, congCuBang, {
    cacCu: ['but', 'to-sang', 'tay'],
    coCo: true,
    khiHoanTac: hoanTacTrenBang,
    nhanXoaHet: 'Xóa sạch bảng',
    khiXoaHet: async () => {
      if (!so?.bang.length) return;
      const dongY = await hoiXacNhan({
        tieuDe: 'Xóa sạch bảng vẽ?',
        moTa: 'Mọi nét trên bảng vẽ của cuộc trò chuyện này sẽ bị xóa. Có thể bấm hoàn tác ngay sau đó.',
        nhanDongY: 'Xóa bảng',
      });
      if (!dongY) return;
      hoanTacBang.push({ loai: 'xoa', nets: so.bang });
      so.bang = [];
      veBang();
      khiBangDoi();
    },
  });
  ws.bangCanvas.style.aspectRatio = `1 / ${TI_LE_BANG}`;

  // ------------------------------------------------------------
  // TRÌNH ĐỌC TÀI LIỆU
  // ------------------------------------------------------------
  const congCuDoc = {
    cu: window.matchMedia('(pointer: coarse)').matches ? 'cuon' : 'khoanh',
    mau: MAU[2][0],
    co: 'vua',
    khiDoi: () => ws.trangList.dataset.congCu = congCuDoc.cu,
  };
  const hoanTacDoc = [];
  const MUC_PHONG = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
  let tiLe = 1;
  let docDangMo = null; // { khoa, ten, tep, nguon, thamSo, kichThuoc, trang: [{ el, img, canvas, mat, daTai }] }
  let quanSatTrang = null;
  let henCuon = 0;

  const docDuoc = (ten) => DUOI_DOC_DUOC.test(ten || '');

  function tuDuongDan(url, ten) {
    if (!url || !docDuoc(ten || url.split('#')[0].split('?')[0])) return null;
    let duongDan;
    try {
      duongDan = new URL(url, window.location.href);
    } catch {
      return null;
    }
    if (duongDan.origin !== window.location.origin) return null;
    if (duongDan.pathname.endsWith('/api/source')) {
      const nguon = duongDan.searchParams.get('name');
      return nguon && docDuoc(nguon) ? { nguon, ten: nguon } : null;
    }
    const khop = duongDan.pathname.match(/\/api\/tep\/([A-Za-z0-9]+)\/noi-dung$/);
    return khop ? { tep: khop[1], ten: ten || 'Tệp đính kèm' } : null;
  }

  const khoaTaiLieu = (tl) => (tl.tep ? `tep:${tl.tep}` : `nguon:${tl.nguon}`);

  function thamSoTaiLieu(tl) {
    const thamSo = new URLSearchParams();
    if (tl.tep) thamSo.set('tep', tl.tep);
    else thamSo.set('nguon', tl.nguon);
    return thamSo.toString();
  }

  async function layThongTin(thamSo) {
    const phanHoi = await fetch(`/api/doc/thong-tin?${thamSo}`);
    const noiDung = await phanHoi.json().catch(() => ({}));
    if (!phanHoi.ok) {
      const loi = new Error(noiDung.detail || `Máy chủ trả về lỗi ${phanHoi.status}.`);
      loi.status = phanHoi.status;
      throw loi;
    }
    return noiDung;
  }

  function dongTaiLieuHienTai() {
    dongHoiVung();
    quanSatTrang?.disconnect();
    quanSatTrang = null;
    docDangMo = null;
    ws.trangList.replaceChildren();
    ws.docXem.classList.add('hidden');
    ws.docTrong.classList.remove('hidden');
  }

  async function moTaiLieu(thongTin, { chuyenTab = true } = {}) {
    if (!so) return;
    if (chuyenTab) moSoTay('tai-lieu');
    const khoa = khoaTaiLieu(thongTin);
    if (docDangMo?.khoa === khoa) {
      if (thongTin.trang) denTrang(thongTin.trang);
      return;
    }
    const phien = phienNap;
    dongTaiLieuHienTai();
    ws.docTrong.classList.add('hidden');
    ws.docXem.classList.remove('hidden');
    ws.trangList.innerHTML = '<div class="doc-dang-tai">Đang mở tài liệu…</div>';

    let thamSo = thamSoTaiLieu(thongTin);
    let thongTinTrang;
    try {
      try {
        thongTinTrang = await layThongTin(thamSo);
      } catch (loi) {
        // Tệp đính kèm chỉ nằm trong bộ nhớ máy chủ; khởi động lại là mất.
        // Nhưng bản gốc đã được chép vào kho tài liệu nên vẫn mở lại được.
        if (!thongTin.tep || loi.status !== 404 || !thongTin.ten) throw loi;
        thamSo = new URLSearchParams({ nguon: thongTin.ten }).toString();
        thongTinTrang = await layThongTin(thamSo);
      }
    } catch (loi) {
      if (phien !== phienNap) return;
      ws.trangList.replaceChildren();
      const baoLoi = document.createElement('div');
      baoLoi.className = 'doc-dang-tai loi';
      baoLoi.textContent = loi.message || 'Không mở được tài liệu.';
      ws.trangList.append(baoLoi);
      return;
    }
    if (phien !== phienNap || !so) return;

    const muc = so.taiLieu[khoa] || (so.taiLieu[khoa] = { ten: thongTin.ten, net: {} });
    if (thongTin.tep) muc.tep = thongTin.tep;
    if (thongTin.nguon) muc.nguon = thongTin.nguon;
    muc.ten = thongTin.ten || muc.ten;
    muc.moLuc = Date.now();
    so.taiLieuMo = khoa;
    henLuuSo();

    docDangMo = {
      khoa,
      ten: muc.ten,
      tep: muc.tep,
      nguon: muc.nguon,
      thamSo,
      kichThuoc: thongTinTrang.trang,
      trang: [],
    };
    hoanTacDoc.length = 0;
    dungCacTrang();
    capNhatDanhSachDaMo();
    denTrang(thongTin.trang || muc.trang || 1, false);
  }

  function dungCacTrang() {
    ws.trangList.replaceChildren();
    ws.trangList.style.setProperty('--ti-le', tiLe);
    ws.tiLe.textContent = `${Math.round(tiLe * 100)}%`;
    const tong = docDangMo.kichThuoc.length;
    ws.tongTrang.textContent = `/ ${tong}`;
    ws.soTrang.max = String(tong);
    quanSatTrang = new IntersectionObserver((cacMuc) => {
      for (const muc of cacMuc) {
        if (muc.isIntersecting) taiTrang(Number(muc.target.dataset.so));
      }
    }, { root: ws.trangList, rootMargin: '800px 0px' });

    docDangMo.kichThuoc.forEach(([rong, cao], viTri) => {
      const soTrang = viTri + 1;
      const el = document.createElement('div');
      el.className = 'doc-trang';
      el.dataset.so = String(soTrang);
      el.style.aspectRatio = `${rong} / ${cao}`;
      const img = document.createElement('img');
      img.alt = `Trang ${soTrang}`;
      img.decoding = 'async';
      img.draggable = false;
      const canvas = document.createElement('canvas');
      canvas.className = 'lop-ve';
      const nhan = document.createElement('span');
      nhan.className = 'doc-so';
      nhan.textContent = String(soTrang);
      el.append(img, canvas, nhan);
      ws.trangList.append(el);
      docDangMo.trang.push({ el, img, canvas, mat: null, rongDaTai: 0 });
      quanSatTrang.observe(el);
    });
  }

  function netCuaTrang(soTrang) {
    const muc = so.taiLieu[docDangMo.khoa];
    return muc.net[soTrang] || (muc.net[soTrang] = []);
  }

  function taiTrang(soTrang) {
    const trang = docDangMo?.trang[soTrang - 1];
    if (!trang) return;
    const rongCan = Math.ceil(trang.el.clientWidth * (window.devicePixelRatio || 1));
    if (rongCan > trang.rongDaTai) {
      trang.rongDaTai = Math.ceil(rongCan / 200) * 200;
      trang.img.src = `/api/doc/trang?${docDangMo.thamSo}&so=${soTrang}&rong=${trang.rongDaTai}`;
    }
    if (!trang.mat) {
      const doc = docDangMo;
      trang.mat = ganMatVe(trang.canvas, {
        layNet: () => (so.taiLieu[doc.khoa]?.net[soTrang] || []),
        congCu: () => congCuDoc,
        doDay: (cc) => (cc.cu === 'to-sang' ? 0.022 : 0.0035),
        batDau: dongHoiVung,
        them: (net) => {
          netCuaTrang(soTrang).push(net);
          hoanTacDoc.push({ loai: 'them', soTrang, nets: [net] });
          henLuuSo();
        },
        xoa: (nets) => {
          const muc = so.taiLieu[doc.khoa];
          muc.net[soTrang] = netCuaTrang(soTrang).filter((net) => !nets.includes(net));
          hoanTacDoc.push({ loai: 'xoa', soTrang, nets });
          henLuuSo();
        },
        khoanh: (net) => khiKhoanh(net, soTrang),
      });
    }
    trang.mat.doKichThuoc();
  }

  function capNhatCoTrang() {
    if (!docDangMo || !ws.trangList.offsetParent) return;
    for (const trang of docDangMo.trang) {
      if (trang.mat) taiTrang(Number(trang.el.dataset.so));
    }
  }

  function trangDangXem() {
    if (!docDangMo) return 1;
    const moc = ws.trangList.scrollTop + ws.trangList.clientHeight * 0.3;
    for (const trang of docDangMo.trang) {
      if (trang.el.offsetTop + trang.el.offsetHeight > moc) return Number(trang.el.dataset.so);
    }
    return docDangMo.trang.length;
  }

  function denTrang(soTrang, muot = true) {
    if (!docDangMo) return;
    const dich = hepVao(Math.round(Number(soTrang) || 1), 1, docDangMo.trang.length);
    const el = docDangMo.trang[dich - 1].el;
    ws.trangList.scrollTo({ top: el.offsetTop - 10, behavior: muot ? 'smooth' : 'auto' });
    ws.soTrang.value = String(dich);
  }

  ws.trangList.addEventListener('scroll', () => {
    if (henCuon) return;
    henCuon = window.requestAnimationFrame(() => {
      henCuon = 0;
      if (!docDangMo) return;
      const soTrang = trangDangXem();
      if (document.activeElement !== ws.soTrang) ws.soTrang.value = String(soTrang);
      const muc = so.taiLieu[docDangMo.khoa];
      if (muc && muc.trang !== soTrang) {
        muc.trang = soTrang;
        henLuuSo();
      }
    });
  }, { passive: true });

  ws.trangTruoc.addEventListener('click', () => denTrang(trangDangXem() - 1));
  ws.trangSau.addEventListener('click', () => denTrang(trangDangXem() + 1));
  ws.soTrang.addEventListener('change', () => denTrang(ws.soTrang.value));
  ws.soTrang.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') denTrang(ws.soTrang.value);
  });

  function doiTiLe(moi) {
    if (!docDangMo) return;
    const dangXem = trangDangXem();
    tiLe = moi;
    ws.trangList.style.setProperty('--ti-le', tiLe);
    ws.tiLe.textContent = `${Math.round(tiLe * 100)}%`;
    window.requestAnimationFrame(() => {
      capNhatCoTrang();
      denTrang(dangXem, false);
    });
  }
  ws.phongTo.addEventListener('click', () => doiTiLe(MUC_PHONG.find((m) => m > tiLe + 0.01) || tiLe));
  ws.thuNho.addEventListener('click', () => doiTiLe([...MUC_PHONG].reverse().find((m) => m < tiLe - 0.01) || tiLe));
  ws.tiLe.addEventListener('click', () => doiTiLe(1));

  function hoanTacTrenDoc() {
    const buoc = hoanTacDoc.pop();
    if (!buoc || !docDangMo) return;
    const muc = so.taiLieu[docDangMo.khoa];
    const mang = netCuaTrang(buoc.soTrang);
    if (buoc.loai === 'them') muc.net[buoc.soTrang] = mang.filter((net) => !buoc.nets.includes(net));
    else mang.push(...buoc.nets);
    docDangMo.trang[buoc.soTrang - 1]?.mat?.ve();
    henLuuSo();
  }

  dungThanhCongCu(ws.congCuDoc, congCuDoc, {
    cacCu: ['khoanh', 'cuon', 'but', 'to-sang', 'tay'],
    coCo: false,
    khiHoanTac: hoanTacTrenDoc,
    nhanXoaHet: 'Xóa mọi đánh dấu trên tài liệu này',
    khiXoaHet: async () => {
      if (!docDangMo) return;
      const muc = so.taiLieu[docDangMo.khoa];
      if (!Object.values(muc.net).some((mang) => mang.length)) return;
      const dongY = await hoiXacNhan({
        tieuDe: 'Xóa mọi đánh dấu?',
        moTa: `Các nét khoanh, bút và tô sáng trên "${muc.ten}" sẽ bị xóa.`,
        nhanDongY: 'Xóa đánh dấu',
      });
      if (!dongY) return;
      muc.net = {};
      hoanTacDoc.length = 0;
      for (const trang of docDangMo.trang) trang.mat?.ve();
      henLuuSo();
    },
  });

  document.addEventListener('keydown', (event) => {
    if (!(event.ctrlKey || event.metaKey) || event.key.toLowerCase() !== 'z' || event.shiftKey) return;
    if (ws.root.classList.contains('hidden')) return;
    const dangGo = event.target.closest?.('input, textarea, [contenteditable="true"]');
    if (dangGo) return;
    const the = ws.tabs.find((nut) => nut.getAttribute('aria-selected') === 'true')?.dataset.tab;
    if (the === 'bang-ve') {
      event.preventDefault();
      hoanTacTrenBang();
    } else if (the === 'tai-lieu') {
      event.preventDefault();
      hoanTacTrenDoc();
    }
  });

  // --- Danh sách tài liệu đã mở trong cuộc trò chuyện này ---
  function capNhatDanhSachDaMo() {
    const cacMuc = Object.entries(so?.taiLieu || {})
      .sort((a, b) => (b[1].moLuc || 0) - (a[1].moLuc || 0));
    ws.docChon.replaceChildren();
    for (const [khoa, muc] of cacMuc) {
      const lua = document.createElement('option');
      lua.value = khoa;
      lua.textContent = muc.ten;
      ws.docChon.append(lua);
    }
    const moThem = document.createElement('option');
    moThem.value = '__mo__';
    moThem.textContent = '+ Mở tệp khác…';
    const dong = document.createElement('option');
    dong.value = '__dong__';
    dong.textContent = 'Đóng trình đọc';
    ws.docChon.append(moThem, dong);
    if (docDangMo) ws.docChon.value = docDangMo.khoa;

    ws.docDaMo.replaceChildren();
    if (!cacMuc.length) return;
    const tieuDe = document.createElement('p');
    tieuDe.className = 'doc-da-mo-tieu-de';
    tieuDe.textContent = 'Đã mở trong cuộc trò chuyện này';
    ws.docDaMo.append(tieuDe);
    for (const [, muc] of cacMuc.slice(0, 6)) {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = 'doc-da-mo-muc';
      nut.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h8l4 4v14H7V3Z"/><path d="M15 3v5h4"/></svg>';
      const ten = document.createElement('span');
      ten.textContent = muc.ten;
      nut.append(ten);
      nut.addEventListener('click', () => moTaiLieu({ ...muc }));
      ws.docDaMo.append(nut);
    }
  }

  ws.docChon.addEventListener('change', () => {
    const giaTri = ws.docChon.value;
    if (giaTri === '__mo__') {
      ws.docChon.value = docDangMo?.khoa || '';
      ws.fileInput.click();
    } else if (giaTri === '__dong__') {
      dongTaiLieuHienTai();
      so.taiLieuMo = null;
      henLuuSo();
      capNhatDanhSachDaMo();
    } else if (so.taiLieu[giaTri]) {
      moTaiLieu({ ...so.taiLieu[giaTri] });
    }
  });

  ws.moTep.addEventListener('click', () => ws.fileInput.click());
  ws.fileInput.addEventListener('change', async () => {
    const tep = ws.fileInput.files?.[0];
    ws.fileInput.value = '';
    if (!tep) return;
    // Mở bằng cách đính kèm vào cuộc trò chuyện: câu hỏi về vùng khoanh sau
    // đó được trả lời theo đúng tệp này thay vì cả kho.
    const daTai = await themTepDinhKem([tep]);
    if (daTai[0]) moTaiLieu({ tep: daTai[0].id, ten: daTai[0].ten });
  });

  // ------------------------------------------------------------
  // KHOANH ĐỂ HỎI
  // ------------------------------------------------------------
  function dongHoiVung() {
    document.querySelectorAll('.hoi-vung').forEach((hop) => hop.remove());
  }

  function khungBao(p) {
    let x0 = 1;
    let y0 = 1;
    let x1 = 0;
    let y1 = 0;
    for (let i = 0; i < p.length; i += 2) {
      x0 = Math.min(x0, p[i]);
      x1 = Math.max(x1, p[i]);
      y0 = Math.min(y0, p[i + 1]);
      y1 = Math.max(y1, p[i + 1]);
    }
    const le = 0.004;
    return {
      x0: hepVao(x0 - le, 0, 1), y0: hepVao(y0 - le, 0, 1),
      x1: hepVao(x1 + le, 0, 1), y1: hepVao(y1 + le, 0, 1),
    };
  }

  function khiKhoanh(net, soTrang) {
    const vung = khungBao(net.p);
    // Chạm nhẹ một cái (không phải khoanh) thì bỏ qua, đừng để lại vết.
    if (vung.x1 - vung.x0 < 0.02 && vung.y1 - vung.y0 < 0.012) return;
    netCuaTrang(soTrang).push(net);
    hoanTacDoc.push({ loai: 'them', soTrang, nets: [net] });
    henLuuSo();
    moHoiVung(soTrang, vung);
  }

  function moHoiVung(soTrang, vung) {
    dongHoiVung();
    const doc = docDangMo;
    const trang = doc.trang[soTrang - 1];
    const hop = document.createElement('div');
    hop.className = 'hoi-vung';
    hop.setAttribute('role', 'dialog');
    hop.setAttribute('aria-label', `Hỏi về vùng vừa khoanh ở trang ${soTrang}`);
    hop.innerHTML = `
      <div class="hoi-vung-dau">
        <strong>Trang ${soTrang}</strong>
        <span class="hoi-vung-trang-thai">Đang đọc chữ trong vùng khoanh…</span>
        <button type="button" class="hoi-vung-dong" aria-label="Đóng">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>
        </button>
      </div>
      <textarea rows="4" maxlength="1600" aria-label="Chữ trong vùng khoanh" placeholder="Chữ trong vùng khoanh sẽ hiện ở đây. Bạn có thể sửa lại hoặc tự gõ."></textarea>
      <div class="hoi-vung-nut">
        <button type="button" class="chinh" data-vung="giai-thich">Giải thích</button>
        <button type="button" data-vung="hoi">Hỏi câu khác</button>
        <button type="button" data-vung="ghi">Ghi vào sổ</button>
      </div>`;
    hop.addEventListener('pointerdown', (event) => event.stopPropagation());
    trang.el.append(hop);

    // Đặt ngay dưới vùng khoanh; vùng nằm gần đáy trang thì đặt lên trên.
    const rongTrang = trang.el.clientWidth;
    const rongHop = Math.min(340, rongTrang - 16);
    hop.style.width = `${rongHop}px`;
    hop.style.left = `${hepVao(vung.x0 * rongTrang, 8, rongTrang - rongHop - 8)}px`;
    if (vung.y1 > 0.72) hop.style.bottom = `calc(${(1 - vung.y0) * 100}% + 6px)`;
    else hop.style.top = `calc(${vung.y1 * 100}% + 6px)`;
    hop.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

    const oChu = hop.querySelector('textarea');
    const trangThai = hop.querySelector('.hoi-vung-trang-thai');
    hop.querySelector('.hoi-vung-dong').addEventListener('click', dongHoiVung);

    const thanYeuCau = { so: soTrang, ...vung };
    const thamSo = new URLSearchParams(doc.thamSo);
    if (thamSo.get('tep')) thanYeuCau.tep = thamSo.get('tep');
    else thanYeuCau.nguon = thamSo.get('nguon');
    fetch('/api/doc/vung', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(thanYeuCau),
    })
      .then(async (phanHoi) => {
        const noiDung = await phanHoi.json().catch(() => ({}));
        if (!phanHoi.ok) throw new Error(noiDung.detail || 'Không đọc được chữ trong vùng này.');
        return noiDung;
      })
      .then((noiDung) => {
        if (!hop.isConnected) return;
        oChu.value = noiDung.van_ban || '';
        trangThai.textContent = {
          lop_chu: 'Chữ lấy từ tài liệu',
          ocr: 'Chữ nhận dạng từ ảnh - sửa lại nếu sai',
          trong: 'Không đọc được chữ - hãy gõ câu hỏi của bạn',
        }[noiDung.cach] || '';
        oChu.focus();
      })
      .catch((loi) => {
        if (!hop.isConnected) return;
        trangThai.textContent = loi.message;
        trangThai.classList.add('loi');
      });

    const taoDoanTrich = (chu) => ({
      van_ban: chu.slice(0, 4000),
      ten: doc.ten,
      trang: soTrang,
      ...(thanYeuCau.tep ? { tep: thanYeuCau.tep } : {}),
    });

    hop.querySelector('.hoi-vung-nut').addEventListener('click', async (event) => {
      const nut = event.target.closest('button[data-vung]');
      if (!nut) return;
      const chu = oChu.value.trim();
      const viec = nut.dataset.vung;
      if (viec === 'ghi') {
        ghiVungVaoSo(doc, soTrang, vung, chu);
        dongHoiVung();
        return;
      }
      if (viec === 'hoi') {
        const tienTo = chu
          ? `Về đoạn "${catNgan(chu, 1400)}" (trang ${soTrang}, ${doc.ten}): `
          : `Về trang ${soTrang} của ${doc.ten}: `;
        if (chu) {
          await damBaoDinhKem(doc);
          doanChoHoi = { tienTo: tienTo.trim(), doan: taoDoanTrich(chu) };
        }
        dienKhungHoi(tienTo);
        dongHoiVung();
        return;
      }
      if (!chu) {
        showToast('Chưa có chữ để giải thích - hãy gõ đoạn cần hỏi vào ô');
        oChu.focus();
        return;
      }
      await damBaoDinhKem(doc);
      const dau = `Giải thích dễ hiểu giúp mình đoạn sau trong tài liệu "${doc.ten}" (trang ${soTrang}):\n"`;
      const cauHoi = `${dau}${catNgan(chu, CAU_HOI_TOI_DA - dau.length - 1)}"`;
      dongHoiVung();
      if (inFlight || !hoiDuoc() || dangDocTep()) {
        doanChoHoi = { tienTo: cauHoi, doan: taoDoanTrich(chu) };
        dienKhungHoi(cauHoi);
        showToast(dangDocTep()
          ? 'Tệp vẫn đang được đọc - câu hỏi đã điền sẵn, bấm gửi khi tệp sẵn sàng'
          : 'Chưa gửi được ngay - câu hỏi đã điền vào khung hỏi');
        return;
      }
      if (laManHep()) dongSoTay();
      submitQuestion(cauHoi, { doanTrich: taoDoanTrich(chu) });
    });
  }

  // Đoạn khoanh chờ đi kèm câu hỏi người dùng gõ nốt trong khung hỏi ("Hỏi
  // câu khác"). Chỉ gắn khi câu gửi đi vẫn giữ nguyên phần mở đầu đã điền.
  let doanChoHoi = null;

  function doanTrichCho(cauHoi) {
    if (!doanChoHoi || !cauHoi.startsWith(doanChoHoi.tienTo)) return null;
    const doan = doanChoHoi.doan;
    doanChoHoi = null;
    return doan;
  }

  // Tệp đọc trong trình đọc mà không còn trong hàng đính kèm (mở lại cuộc trò
  // chuyện cũ) thì gắn lại, để câu hỏi về vùng khoanh trả lời theo đúng tệp.
  async function damBaoDinhKem(doc) {
    const tepId = new URLSearchParams(doc.thamSo).get('tep');
    if (!tepId || tepDinhKem.has(tepId) || tepDinhKem.size >= SO_TEP_TOI_DA) return;
    try {
      const phanHoi = await fetch(`/api/tep/${encodeURIComponent(tepId)}`);
      if (!phanHoi.ok) return;
      const tep = await phanHoi.json();
      if (tep.trang_thai === 'loi') return;
      tepDinhKem.set(tep.id, tep);
      renderAttachments();
      if (tep.trang_thai === 'dang_xu_ly') theoDoiTep(tep.id);
    } catch {
      /* không gắn được thì hỏi trên cả kho */
    }
  }

  function catAnhVung(img, vung) {
    if (!img.complete || !img.naturalWidth) return null;
    const sx = vung.x0 * img.naturalWidth;
    const sy = vung.y0 * img.naturalHeight;
    const sw = (vung.x1 - vung.x0) * img.naturalWidth;
    const sh = (vung.y1 - vung.y0) * img.naturalHeight;
    const heSo = Math.min(1, 900 / sw);
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(sw * heSo));
    canvas.height = Math.max(1, Math.round(sh * heSo));
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
    return { src: canvas.toDataURL('image/jpeg', 0.86), rong: canvas.width };
  }

  function ghiVungVaoSo(doc, soTrang, vung, chu) {
    const khoi = document.createElement('blockquote');
    khoi.className = 'trich-tai-lieu';
    const dau = document.createElement('p');
    dau.className = 'trich-nguon';
    dau.textContent = `${doc.ten} · trang ${soTrang}`;
    khoi.append(dau);
    const anh = catAnhVung(doc.trang[soTrang - 1].img, vung);
    if (anh) {
      const img = document.createElement('img');
      img.src = anh.src;
      img.alt = `Vùng khoanh ở trang ${soTrang}`;
      img.width = Math.min(anh.rong, 520);
      khoi.append(img);
    }
    if (chu) {
      const doan = document.createElement('p');
      doan.textContent = chu;
      khoi.append(doan);
    }
    ghiVaoSo(khoi, { mo: false, thongBao: 'Đã ghi vùng khoanh vào sổ tay' });
  }

  // ------------------------------------------------------------
  // TẢI SỔ TAY VỀ MÁY
  // ------------------------------------------------------------
  function dongMenuTaiVe() {
    ws.taiVeMenu.classList.add('hidden');
    ws.taiVe.setAttribute('aria-expanded', 'false');
  }

  ws.taiVe.addEventListener('click', (event) => {
    event.stopPropagation();
    const dangMo = !ws.taiVeMenu.classList.contains('hidden');
    ws.taiVeMenu.classList.toggle('hidden', dangMo);
    ws.taiVe.setAttribute('aria-expanded', String(!dangMo));
  });
  document.addEventListener('click', (event) => {
    if (!ws.taiVeMenu.contains(event.target)) dongMenuTaiVe();
  });
  ws.taiVeMenu.addEventListener('click', async (event) => {
    const nut = event.target.closest('button[data-tai]');
    if (!nut) return;
    dongMenuTaiVe();
    await luuNgay();
    if (nut.dataset.tai === 'doc') taiWord();
    else if (nut.dataset.tai === 'pdf') inSoTay();
    else taiAnhBang();
  });

  const thoatHtml = (chu) => String(chu).replace(/[&<>"]/g, (k) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[k]));

  function tenTepXuat(duoi) {
    const ten = boDau(tenCuocTroChuyen()).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48);
    return `so-tay-${ten || 'cuoc-tro-chuyen'}.${duoi}`;
  }

  function taiXuong(blob, ten) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = ten;
    document.body.append(a);
    a.click();
    a.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  function veBangRaCanvas(rong = 1500) {
    const canvas = document.createElement('canvas');
    canvas.width = rong;
    canvas.height = Math.round(rong * TI_LE_BANG);
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fffdf8';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    for (const net of so.bang) veNet(ctx, net, canvas.width, canvas.height);
    return canvas;
  }

  function htmlSoTay(choWord) {
    const ghiChu = document.createElement('div');
    ghiChu.innerHTML = lamSach(so.ghiChu);
    // Word không vẽ ô đánh dấu HTML; đổi sang ký hiệu cho bản in giống nhau.
    ghiChu.querySelectorAll('input[type="checkbox"]').forEach((o) => {
      o.replaceWith(o.hasAttribute('checked') ? '☑ ' : '☐ ');
    });
    const coChu = coGhiChu(so);
    const bang = so.bang.length ? veBangRaCanvas(1200).toDataURL('image/png') : '';
    const tieuDe = thoatHtml(tenCuocTroChuyen());
    const ngay = new Date().toLocaleString('vi-VN');
    const khaiBao = choWord
      ? '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">'
      : '<!doctype html><html lang="vi">';
    return `${khaiBao}<head><meta charset="utf-8"><title>Sổ tay - ${tieuDe}</title>
<style>
  body { font-family: Calibri, "Segoe UI", Arial, sans-serif; font-size: 12pt; line-height: 1.55; color: #1c2635; max-width: 760px; margin: 24px auto; padding: 0 16px; }
  h1 { font-family: Cambria, "Times New Roman", serif; font-size: 22pt; font-weight: normal; margin: 0 0 4px; color: #17315f; }
  h2 { font-family: Cambria, "Times New Roman", serif; font-size: 15pt; font-weight: normal; color: #17315f; margin-top: 22px; }
  h4 { font-size: 13pt; margin: 14px 0 6px; }
  .meta { color: #6b778a; font-size: 10pt; margin: 0 0 18px; }
  blockquote { margin: 10px 0; padding: 6px 12px; border-left: 3px solid #6f93c6; background: #f4f7fc; }
  blockquote.trich-tai-lieu { border-left-color: #d64534; background: #fdf4f2; }
  .trich-nguon { color: #6b778a; font-size: 9.5pt; margin: 0 0 4px; }
  mark { background: #fff1a6; }
  img { max-width: 100%; }
  table { border-collapse: collapse; } td, th { border: 1px solid #c9d3e0; padding: 4px 8px; }
  @media print { body { margin: 0 auto; } }
</style></head><body>
<h1>Sổ tay học tập</h1>
<p class="meta">${tieuDe} · xuất lúc ${thoatHtml(ngay)}</p>
${coChu ? ghiChu.innerHTML : '<p><i>Chưa có ghi chú.</i></p>'}
${bang ? `<h2>Bảng vẽ</h2><p><img src="${bang}" width="600" alt="Bảng vẽ"></p>` : ''}
</body></html>`;
  }

  // Phần HTML phải mã hoá quoted-printable: Word bỏ qua phần text/html mã hoá
  // base64 và hiện ra một trang rác (đã thử bằng Word thật), còn ảnh thì base64
  // vẫn đọc bình thường.
  function quotedPrintable(chu) {
    const byte = new TextEncoder().encode(chu.replace(/\r?\n/g, '\r\n'));
    const cacDong = [];
    let dong = '';
    for (let i = 0; i < byte.length; i += 1) {
      const b = byte[i];
      if (b === 13 && byte[i + 1] === 10) {
        // Khoảng trắng cuối dòng bị bộ đọc MIME cắt mất, phải mã hoá lại.
        if (/[ \t]$/.test(dong)) dong = `${dong.slice(0, -1)}${dong.endsWith(' ') ? '=20' : '=09'}`;
        cacDong.push(dong);
        dong = '';
        i += 1;
        continue;
      }
      const manh = (b >= 33 && b <= 126 && b !== 61) || b === 32
        ? String.fromCharCode(b)
        : `=${b.toString(16).toUpperCase().padStart(2, '0')}`;
      if (dong.length + manh.length > 73) {
        cacDong.push(`${dong}=`);
        dong = '';
      }
      dong += manh;
    }
    cacDong.push(dong);
    return cacDong.join('\r\n');
  }
  const chiaDong = (chu) => chu.replace(/.{76}/g, '$&\r\n');

  // .doc thực chất là MHTML: một trang HTML kèm ảnh đóng gói trong cùng tệp.
  // Word mở được thẳng, còn ảnh data: nhét trong HTML thường thì Word bỏ qua.
  function taiWord() {
    if (!coGhiChu(so) && !so.bang.length) {
      showToast('Sổ tay đang trống - chưa có gì để tải về');
      return;
    }
    const anh = [];
    const html = htmlSoTay(true).replace(
      /src="data:image\/(png|jpeg|webp);base64,([^"]+)"/g,
      (_, kieu, duLieu) => {
        const duoi = kieu === 'jpeg' ? 'jpg' : kieu;
        const ten = `file:///C:/so-tay/anh-${anh.length + 1}.${duoi}`;
        anh.push({ kieu, duLieu, ten });
        return `src="${ten}"`;
      },
    );
    const ranh = `----=_SoTay_${Date.now().toString(36)}`;
    const phan = [
      'MIME-Version: 1.0',
      `Content-Type: multipart/related; boundary="${ranh}"; type="text/html"`,
      '',
      `--${ranh}`,
      'Content-Type: text/html; charset="utf-8"',
      'Content-Transfer-Encoding: quoted-printable',
      'Content-Location: file:///C:/so-tay/so-tay.htm',
      '',
      quotedPrintable(html),
    ];
    for (const muc of anh) {
      phan.push(
        `--${ranh}`,
        `Content-Type: image/${muc.kieu}`,
        'Content-Transfer-Encoding: base64',
        `Content-Location: ${muc.ten}`,
        '',
        chiaDong(muc.duLieu),
      );
    }
    phan.push(`--${ranh}--`, '');
    taiXuong(new Blob([phan.join('\r\n')], { type: 'application/msword' }), tenTepXuat('doc'));
    showToast('Đã tải sổ tay dạng Word');
  }

  function inSoTay() {
    if (!coGhiChu(so) && !so.bang.length) {
      showToast('Sổ tay đang trống - chưa có gì để in');
      return;
    }
    const cuaSo = window.open('', '_blank');
    if (!cuaSo) {
      showToast('Trình duyệt đã chặn cửa sổ in - hãy cho phép cửa sổ bật lên');
      return;
    }
    cuaSo.document.open();
    cuaSo.document.write(htmlSoTay(false));
    cuaSo.document.close();
    // Đợi ảnh data: giải mã xong rồi mới mở hộp in, nếu không ảnh ra trang trắng.
    window.setTimeout(() => {
      cuaSo.focus();
      cuaSo.print();
    }, 500);
  }

  function taiAnhBang() {
    if (!so.bang.length) {
      showToast('Bảng vẽ đang trống');
      return;
    }
    veBangRaCanvas().toBlob((blob) => {
      if (blob) taiXuong(blob, tenTepXuat('png').replace('so-tay-', 'bang-ve-'));
    }, 'image/png');
  }

  // ------------------------------------------------------------
  // KHỞI ĐỘNG
  // ------------------------------------------------------------
  new ResizeObserver(() => {
    doKichThuocBang();
    capNhatCoTrang();
  }).observe(ws.root);

  const rongDaLuu = Number(docLuu(KHOA_RONG));
  if (rongDaLuu) datDoRong(rongDaLuu);
  const theDaLuu = docLuu(KHOA_TAB);
  chonThe(['ghi-chu', 'bang-ve', 'tai-lieu'].includes(theDaLuu) ? theDaLuu : 'ghi-chu');
  if (docLuu(KHOA_MO) === '1' && !laManHep()) moSoTay();

  window.khongGianHoc = {
    doiCuocTroChuyen,
    capNhatTieuDe,
    xoaSo,
    xoaHetSo,
    ghiCauTraLoi,
    moTaiLieu,
    tuDuongDan,
    docDuoc,
    doanTrichCho,
    ghiBanDich,
    // Đăng nhập / đăng xuất: lưu nốt sổ đang mở vào kho cũ trước khi đổi kho.
    truocKhiDoiNguoiDung: luuNgay,
    napLai: async () => {
      window.clearTimeout(henLuu);
      so = null;
      await doiCuocTroChuyen();
    },
    chuyenSoKhachLenTaiKhoan,
  };

  doiCuocTroChuyen().then(donSoMoCoi);
  // Hàng tệp đính kèm đã vẽ trước khi tệp này nạp: vẽ lại để có nút "Đọc".
  if (tepDinhKem.size) renderAttachments();
})();
