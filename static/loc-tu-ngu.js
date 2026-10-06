/* ============================================================
   LỌC TỪ NGỮ TRƯỚC KHI GỬI
   ============================================================
   Báo người dùng sửa câu có từ chửi thề, tục tĩu, 18+ NGAY trong ô nhập, thay
   vì gửi đi rồi mới nhận lời nhắc từ máy chủ: câu bị giữ lại để sửa, không lọt
   vào lịch sử trò chuyện.

   Đây chỉ là lớp báo sớm. Chốt chặn thật là loc_tu_ngu.kiem_tra() trong
   stream_answer, vì ai cũng gọi thẳng được /api/chat/stream.

   Danh sách từ lấy từ /api/loc-tu-ngu chứ không chép vào đây, để chỉ có một
   bản. Thuật toán thì phải là bản port đúng từng bước của loc_tu_ngu.py:
   tests/test_loc_tu_ngu.py chạy cùng bộ câu qua cả hai bản và so kết quả.
   Chưa tải được danh sách (mạng lỗi, máy chủ cũ) thì không chặn gì - máy chủ
   vẫn lo phần đó.

   Chạy được cả trong Node (không có window, không fetch) để test so khớp.
   ============================================================ */
(function (goc) {
  // Python: [^\W\d_] là chữ cái; \w là chữ, số, gạch dưới.
  const CHU = '\\p{L}';
  const W = '[\\p{L}\\p{N}_]';
  const LEET = { 0: 'o', 1: 'i', 3: 'e', 4: 'a', '@': 'a', '!': 'i', $: 's' };
  const RE_LEET = new RegExp(`(?<=${CHU})[0134@!$]+(?=${CHU})`, 'gu');
  const RE_PHAN_CACH = /[^\p{L}\p{N}_*]+|_+/gu;
  const RE_CHU_LE = new RegExp(`(?<!\\S)${CHU}(?: ${CHU}(?!\\S))+`, 'gu');
  const RE_LAP = new RegExp(`(${W})\\1+`, 'gu');
  const RE_LAP_3 = new RegExp(`(${W})\\1{2,}`, 'gu');
  const RE_CF = /\p{Cf}/gu;

  // Chỉ thoát ký tự cú pháp: với cờ u, thoát thừa ("\-") là lỗi cú pháp.
  const thoat = (chuoi) => chuoi.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&');

  // Như can_cu_van_ban.bo_dau.
  function boDau(chuoi) {
    return chuoi.normalize('NFD').replace(/\p{Mn}/gu, '')
      .replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase();
  }

  function chuanHoa(vanBan) {
    let ket = (vanBan || '').normalize('NFC').toLowerCase().replace(RE_CF, '');
    ket = ket.replace(RE_LEET, (doan) => [...doan].map((c) => LEET[c]).join(''));
    return ket.replace(RE_PHAN_CACH, ' ').split(/\s+/).filter(Boolean).join(' ');
  }

  function cacDangGoLach(vanBan) {
    const ghep = vanBan.replace(RE_CHU_LE, (doan) => doan.replace(/ /g, ''));
    return [ghep, ghep.replace(RE_LAP_3, '$1$1'), ghep.replace(RE_LAP, '$1')];
  }

  function gocKhongDau(vanBan) {
    return vanBan.split(/\s+/).filter(Boolean)
      .map((tu) => (boDau(tu) === tu ? tu : '#')).join(' ');
  }

  function bienDich(danhSach) {
    const ketQua = {};
    for (const [nhom, cacTu] of Object.entries(danhSach)) {
      const mau = [...new Set(cacTu)]
        .sort((a, b) => b.length - a.length)
        .map((tu) => tu.split(/\s+/).filter(Boolean).map(thoat).join('\\s+'))
        .join('|');
      ketQua[nhom] = new RegExp(`(?<![\\p{L}\\p{N}_*])(?:${mau})(?![\\p{L}\\p{N}_*])`, 'gu');
    }
    return ketQua;
  }

  function tuDon(danhSach) {
    const ketQua = [];
    for (const [nhom, cacTu] of Object.entries(danhSach)) {
      for (const tu of cacTu) {
        if (!tu.includes(' ') && !tu.includes('*') && tu.length >= 3) ketQua.push([nhom, tu]);
      }
    }
    return ketQua;
  }

  // Chuẩn hoá NFC cả danh sách: lỡ một mục ở dạng tách dấu thì sẽ không bao
  // giờ khớp với câu đã chuẩn hoá NFC.
  function nfc(danhSach) {
    return Object.fromEntries(Object.entries(danhSach || {})
      .map(([nhom, cacTu]) => [nhom, cacTu.map((tu) => tu.normalize('NFC'))]));
  }

  let boLoc = null;

  function nap(duLieu) {
    if (!duLieu || !duLieu.bat) {
      boLoc = null;
      return;
    }
    const coDau = nfc(duLieu.co_dau);
    const khongDau = nfc(duLieu.khong_dau);
    const hopLe = (duLieu.hop_le || []).map((cum) => cum.normalize('NFC'));
    boLoc = {
      thuTu: Object.keys(coDau),
      mauCoDau: bienDich(coDau),
      mauKhongDau: bienDich(khongDau),
      tuDonCoDau: tuDon(coDau),
      tuDonKhongDau: tuDon(khongDau),
      reHopLe: hopLe.length
        ? new RegExp(`(?<!${W})(?:${hopLe.map(thoat).join('|')})(?!${W})`, 'gu')
        : null,
    };
  }

  function kiemTra(vanBan) {
    const khongViPham = { viPham: false, nhom: [], tuKhop: [] };
    if (!boLoc) return khongViPham;
    let chuan = chuanHoa(vanBan);
    if (boLoc.reHopLe) chuan = chuan.replace(boLoc.reHopLe, ' ');
    if (!chuan.trim()) return khongViPham;
    const cacDang = [chuan, ...cacDangGoLach(chuan)];
    const gocNhin = [
      [boLoc.mauCoDau, cacDang],
      [boLoc.mauKhongDau, cacDang.map(gocKhongDau)],
    ];
    const nhomViPham = new Set();
    const tuKhop = new Set();
    for (const [boMau, dang] of gocNhin) {
      for (const [nhom, mau] of Object.entries(boMau)) {
        for (const d of dang) {
          for (const khop of d.matchAll(mau)) {
            nhomViPham.add(nhom);
            tuKhop.add(khop[0]);
          }
        }
      }
    }
    // Chữ lẻ đã ghép ("đ ị t m ẹ" -> "địtmẹ") không còn ranh giới từ: tìm từ
    // đơn như chuỗi con, chỉ trên phần ghép.
    for (const [doan] of chuan.matchAll(RE_CHU_LE)) {
      const khoi = doan.replace(/ /g, '');
      const cacKhoi = [khoi, khoi.replace(RE_LAP, '$1')];
      const ds = boDau(khoi) === khoi ? boLoc.tuDonKhongDau : boLoc.tuDonCoDau;
      for (const [nhom, tu] of ds) {
        if (cacKhoi.some((k) => k.includes(tu))) {
          nhomViPham.add(nhom);
          tuKhop.add(tu);
        }
      }
    }
    if (!nhomViPham.size) return khongViPham;
    return {
      viPham: true,
      nhom: boLoc.thuTu.filter((nhom) => nhomViPham.has(nhom)),
      tuKhop: [...tuKhop],
    };
  }

  // Khác lời nhắc của máy chủ: câu chưa gửi đi, người dùng còn sửa được.
  const LOI_NHAC = 'Câu hỏi có từ ngữ không phù hợp với môi trường học đường. '
    + 'Bạn vui lòng sửa lại cho lịch sự rồi gửi.';

  const api = {
    nap,
    kiemTra,
    dangBat: () => boLoc !== null,
    LOI_NHAC,
  };
  goc.locTuNgu = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;

  if (typeof fetch === 'function' && typeof window !== 'undefined') {
    fetch('/api/loc-tu-ngu')
      .then((phanHoi) => (phanHoi.ok ? phanHoi.json() : null))
      .then((duLieu) => { if (duLieu) nap(duLieu); })
      .catch(() => { /* Không tải được thì để máy chủ tự chặn. */ });
  }
})(typeof window !== 'undefined' ? window : globalThis);
