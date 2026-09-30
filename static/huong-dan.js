/* ============================================================
   HƯỚNG DẪN SỬ DỤNG
   ============================================================
   Nút "Hướng dẫn" ở thanh trên (và lời mời trên màn hình chào) mở
   HUONG_DAN_SU_DUNG.md ngay trong một hộp thoại. Nội dung lấy từ máy chủ (/api/huong-dan) chứ không chép vào trang,
   để bản trên GitHub và bản trên giao diện luôn là một: sửa tệp .md là xong.

   Tài liệu dài nên không trải thành một trang cuộn: mỗi mục "## n. …" là một
   trang, phần mở đầu cùng Mục lục là trang đầu. Cột trái liệt kê các trang
   (màn hẹp thì ẩn, dùng nút Mục lục), cuối trang có nút Trước / Tiếp.

   Bộ dựng Markdown bên dưới chỉ lo đúng phần cú pháp tài liệu đó dùng: tiêu
   đề, đoạn, danh sách lồng nhau, bảng, khối trích dẫn, đường kẻ, chữ đậm,
   nghiêng, mã và liên kết. Không phải bộ dựng đầy đủ - tiêu đề gạch dưới
   (setext), mã nhiều dòng hay HTML nhúng đều không nhận. Mọi chữ được thoát
   HTML trước khi dựng; liên kết chỉ nhận http(s) và #mục trong tài liệu.
   ============================================================ */
(() => {
  const $id = (id) => document.getElementById(id);
  const hd = {
    hop: $id('huongDanDialog'),
    dong: $id('huongDanDong'),
    mucLuc: $id('huongDanMucLuc'),
    noiDung: $id('huongDanNoiDung'),
    dieuHuong: $id('huongDanDieuHuong'),
    chan: $id('huongDanChan'),
    truoc: $id('huongDanTruoc'),
    tiep: $id('huongDanTiep'),
    soTrang: $id('huongDanSoTrang'),
  };
  if (!hd.hop || !hd.noiDung) return;

  // Tiêu đề trong tài liệu được gắn id có tiền tố để không trùng id của trang;
  // liên kết #mục vẫn giữ nguyên như trên GitHub, bấm vào thì tự đổi sang.
  const TIEN_TO_ID = 'hd-';
  const MA_MUC_LUC = 'mục-lục';

  // ---------- Markdown -> HTML ----------
  function thoat(chu) {
    return chu
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // url và chu đã được thoát HTML.
  function lienKet(url, chu) {
    if (url.startsWith('#')) return `<a href="${url}">${chu}</a>`;
    if (/^https?:\/\//i.test(url)) return `<a href="${url}" target="_blank" rel="noopener noreferrer">${chu}</a>`;
    return chu;
  }

  function dungTrongDong(chu) {
    // Tách `mã` ra trước để dấu * bên trong không bị hiểu thành đậm/nghiêng.
    return chu.split(/(`[^`]+`)/).map((doan) => {
      if (/^`[^`]+`$/.test(doan)) return `<code>${thoat(doan.slice(1, -1))}</code>`;
      return thoat(doan)
        .replace(/&lt;(https?:\/\/.+?)&gt;/g, (_, url) => lienKet(url, url))
        .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, chuLk, url) => lienKet(url, chuLk))
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/(^|[^*])\*([^*\s][^*]*?)\*(?!\*)/g, '$1<em>$2</em>');
    }).join('');
  }

  // Cùng quy tắc với GitHub (github-slugger) để mục lục viết trong tệp, như
  // "#9-tài-khoản-có-cần-đăng-ký-không", trỏ đúng cả hai nơi.
  function taoMa(chuTieuDe, daDung) {
    const tron = chuTieuDe
      .replace(/`([^`]*)`/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
      .replace(/\*+/g, '');
    const goc = tron.toLowerCase().replace(/[^\p{L}\p{M}\p{N}\s_-]/gu, '').replace(/ /g, '-');
    const lan = daDung.get(goc) || 0;
    daDung.set(goc, lan + 1);
    return lan ? `${goc}-${lan}` : goc;
  }

  const LA_TIEU_DE = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
  const LA_DUONG_KE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
  const LA_TRICH_DAN = /^\s*>/;
  const LA_MUC_DS = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
  const LA_DONG_CHIA_BANG = /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/;

  const doLui = (dong) => dong.match(/^\s*/)[0].length;
  const laBang = (dong, i) => dong[i].includes('|') && i + 1 < dong.length && LA_DONG_CHIA_BANG.test(dong[i + 1]);

  function batDauKhoiMoi(dong, i) {
    const d = dong[i];
    return LA_TIEU_DE.test(d) || LA_DUONG_KE.test(d) || LA_TRICH_DAN.test(d) || LA_MUC_DS.test(d) || laBang(dong, i);
  }

  function tachO(dong) {
    return dong.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map((o) => o.trim().replace(/\\\|/g, '|'));
  }

  function dungBang(dong, i) {
    const canh = tachO(dong[i + 1]).map((o) => {
      if (o.startsWith(':') && o.endsWith(':')) return 'hd-giua';
      if (o.endsWith(':')) return 'hd-phai';
      return '';
    });
    const o = (the, noiDung, cot) => {
      const lop = canh[cot] ? ` class="${canh[cot]}"` : '';
      return `<${the}${lop}>${dungTrongDong(noiDung)}</${the}>`;
    };
    const dau = tachO(dong[i]).map((chu, cot) => o('th', chu, cot)).join('');
    const hang = [];
    let k = i + 2;
    while (k < dong.length && dong[k].trim() && dong[k].includes('|')) {
      hang.push(`<tr>${tachO(dong[k]).map((chu, cot) => o('td', chu, cot)).join('')}</tr>`);
      k += 1;
    }
    const html = `<div class="hd-bang"><table><thead><tr>${dau}</tr></thead><tbody>${hang.join('')}</tbody></table></div>`;
    return [html, k];
  }

  function dungMuc(dongMuc, tt) {
    // Đoạn đầu của mục viết liền (danh sách "chặt" như GitHub), phần sau như
    // danh sách con thì dựng thành khối.
    let k = 0;
    const doan = [];
    while (k < dongMuc.length && dongMuc[k].trim() && (k === 0 || !batDauKhoiMoi(dongMuc, k))) {
      doan.push(dongMuc[k].trim());
      k += 1;
    }
    return `<li>${dungTrongDong(doan.join(' '))}${dungKhoi(dongMuc.slice(k), tt)}</li>`;
  }

  function dungDanhSach(dong, i, tt) {
    const dau = dong[i].match(LA_MUC_DS);
    const lui = dau[1].length;
    const coThuTu = /\d/.test(dau[2]);
    const cacMuc = [];
    let thut = 0;
    while (i < dong.length) {
      const d = dong[i];
      const m = d.match(LA_MUC_DS);
      if (m && m[1].length === lui) {
        if (/\d/.test(m[2]) !== coThuTu) break;
        cacMuc.push([m[3]]);
        thut = d.length - m[3].length;
        i += 1;
      } else if (!d.trim()) {
        // Dòng trống: danh sách còn tiếp nếu dòng kế là mục cùng cấp hoặc
        // phần thụt vào của mục đang dở.
        let j = i + 1;
        while (j < dong.length && !dong[j].trim()) j += 1;
        const ke = dong[j] && dong[j].match(LA_MUC_DS);
        if (j < dong.length && (doLui(dong[j]) > lui || (ke && ke[1].length === lui))) {
          cacMuc[cacMuc.length - 1].push('');
          i += 1;
        } else {
          break;
        }
      } else if (doLui(d) > lui) {
        cacMuc[cacMuc.length - 1].push(d.slice(Math.min(doLui(d), thut)));
        i += 1;
      } else {
        break;
      }
    }
    const the = coThuTu ? 'ol' : 'ul';
    const batDau = coThuTu && parseInt(dau[2], 10) !== 1 ? ` start="${parseInt(dau[2], 10)}"` : '';
    return [`<${the}${batDau}>${cacMuc.map((muc) => dungMuc(muc, tt)).join('')}</${the}>`, i];
  }

  // tt: trạng thái chung cho cả tài liệu (id đã dùng, đã bỏ tiêu đề # chưa).
  function dungKhoi(dong, tt) {
    let html = '';
    let i = 0;
    while (i < dong.length) {
      const d = dong[i];
      if (!d.trim()) {
        i += 1;
        continue;
      }
      const tieuDe = d.match(LA_TIEU_DE);
      if (tieuDe) {
        const cap = tieuDe[1].length;
        i += 1;
        // Tên tài liệu đã nằm ở đầu hộp thoại nên bỏ tiêu đề # đầu tiên.
        if (cap === 1 && !tt.daBoTieuDe) {
          tt.daBoTieuDe = true;
          continue;
        }
        // Hộp thoại đã có h2 nên mọi cấp lùi xuống một bậc.
        const the = `h${Math.min(cap + 1, 6)}`;
        const ma = taoMa(tieuDe[2], tt.daDung);
        html += `<${the} id="${thoat(TIEN_TO_ID + ma)}">${dungTrongDong(tieuDe[2])}</${the}>`;
        continue;
      }
      if (LA_DUONG_KE.test(d)) {
        html += '<hr>';
        i += 1;
        continue;
      }
      if (LA_TRICH_DAN.test(d)) {
        const trong = [];
        while (i < dong.length && LA_TRICH_DAN.test(dong[i])) {
          trong.push(dong[i].replace(/^\s*> ?/, ''));
          i += 1;
        }
        html += `<blockquote>${dungKhoi(trong, tt)}</blockquote>`;
        continue;
      }
      if (laBang(dong, i)) {
        const [bang, tiep] = dungBang(dong, i);
        html += bang;
        i = tiep;
        continue;
      }
      if (LA_MUC_DS.test(d)) {
        const [ds, tiep] = dungDanhSach(dong, i, tt);
        html += ds;
        i = tiep;
        continue;
      }
      const doan = [];
      while (i < dong.length && dong[i].trim() && (!doan.length || !batDauKhoiMoi(dong, i))) {
        doan.push(dong[i].trim());
        i += 1;
      }
      html += `<p>${dungTrongDong(doan.join(' '))}</p>`;
    }
    return html;
  }

  function dungMarkdown(van) {
    const dong = van.replace(/\r\n?/g, '\n').replace(/\t/g, '    ').split('\n');
    return dungKhoi(dong, { daDung: new Map(), daBoTieuDe: false });
  }

  // ---------- Hộp thoại ----------
  let daTai = false;
  let dangTai = null;

  function baoTrangThai(chu, choThuLai = false) {
    const p = document.createElement('p');
    p.className = 'hd-trang-thai';
    p.textContent = chu;
    if (choThuLai) {
      const nut = document.createElement('button');
      nut.type = 'button';
      nut.className = 'hd-thu-lai';
      nut.textContent = 'Thử lại';
      nut.addEventListener('click', taiNoiDung);
      p.append(document.createElement('br'), nut);
    }
    hd.noiDung.replaceChildren(p);
  }

  function taiNoiDung() {
    if (daTai) return Promise.resolve();
    if (dangTai) return dangTai;
    baoTrangThai('Đang tải hướng dẫn…');
    dangTai = (async () => {
      try {
        const phanHoi = await fetch('/api/huong-dan', { cache: 'no-cache' });
        if (!phanHoi.ok) throw new Error(String(phanHoi.status));
        chiaTrang(dungMarkdown(await phanHoi.text()));
        veDieuHuong();
        daTai = true;
        denTrang(0);
      } catch {
        baoTrangThai('Chưa tải được hướng dẫn. Hãy kiểm tra kết nối mạng rồi thử lại.', true);
      } finally {
        dangTai = null;
      }
    })();
    return dangTai;
  }

  const kieuCuon = () => (matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth');

  // ---------- Chia trang ----------
  // Mỗi trang: { so, ten, nut: [các phần tử của trang] }. Các phần tử được
  // dựng một lần rồi chuyển qua lại giữa các trang, không dựng lại.
  let cacTrang = [];
  let trangHienTai = 0;
  const nutDieuHuong = [];

  function chiaTrang(html) {
    const tam = document.createElement('div');
    tam.innerHTML = html;
    cacTrang = [{ so: '', ten: 'Giới thiệu', nut: [] }];
    [...tam.children].forEach((nut) => {
      // "## n. …" dựng thành h3. Mục lục ở lại trang đầu cùng phần mở đầu.
      if (nut.tagName === 'H3' && nut.id !== TIEN_TO_ID + MA_MUC_LUC) {
        const [, so = '', ten = nut.textContent] = nut.textContent.match(/^(\d+)\.\s+(.*)$/) || [];
        cacTrang.push({ so, ten, nut: [nut] });
        return;
      }
      cacTrang[cacTrang.length - 1].nut.push(nut);
    });
    // Đường kẻ "---" ngăn các mục trong tệp; ở mép trang thì thừa.
    cacTrang.forEach((trang) => {
      while (trang.nut.length && trang.nut[0].tagName === 'HR') trang.nut.shift();
      while (trang.nut.length && trang.nut[trang.nut.length - 1].tagName === 'HR') trang.nut.pop();
    });
  }

  function veDieuHuong() {
    if (!hd.dieuHuong) return;
    nutDieuHuong.length = 0;
    const ds = document.createElement('ol');
    cacTrang.forEach((trang, i) => {
      const nut = document.createElement('button');
      nut.type = 'button';
      const so = document.createElement('span');
      so.className = 'hd-dh-so';
      so.textContent = trang.so || 'i';
      so.setAttribute('aria-hidden', 'true');
      nut.append(so, document.createTextNode(trang.ten));
      nut.addEventListener('click', () => denTrang(i));
      nutDieuHuong.push(nut);
      const muc = document.createElement('li');
      muc.append(nut);
      ds.append(muc);
    });
    hd.dieuHuong.replaceChildren(ds);
  }

  function tenDayDu(trang) {
    return trang.so ? `${trang.so}. ${trang.ten}` : trang.ten;
  }

  function datNutChuyen(nut, trang) {
    nut.classList.toggle('an', !trang);
    nut.disabled = !trang;
    nut.querySelector('strong').textContent = trang ? tenDayDu(trang) : '';
  }

  function denTrang(i, dich = null) {
    if (!cacTrang.length) return;
    trangHienTai = Math.max(0, Math.min(i, cacTrang.length - 1));
    hd.noiDung.replaceChildren(...cacTrang[trangHienTai].nut);
    if (dich && dich !== cacTrang[trangHienTai].nut[0]) dich.scrollIntoView({ block: 'start' });
    else hd.noiDung.scrollTop = 0;

    nutDieuHuong.forEach((nut, k) => {
      if (k === trangHienTai) nut.setAttribute('aria-current', 'page');
      else nut.removeAttribute('aria-current');
    });
    nutDieuHuong[trangHienTai]?.scrollIntoView({ block: 'nearest' });

    hd.chan?.classList.remove('hidden');
    if (hd.truoc) datNutChuyen(hd.truoc, cacTrang[trangHienTai - 1]);
    if (hd.tiep) datNutChuyen(hd.tiep, cacTrang[trangHienTai + 1]);
    if (hd.soTrang) hd.soTrang.textContent = `${trangHienTai + 1} / ${cacTrang.length}`;
  }

  // Liên kết #mục có thể trỏ tới tiêu đề ở trang khác: tìm trang chứa nó.
  function cuonToi(ma) {
    const id = TIEN_TO_ID + ma;
    const chon = `#${CSS.escape(id)}`;
    for (let i = 0; i < cacTrang.length; i += 1) {
      for (const nut of cacTrang[i].nut) {
        const dich = nut.id === id ? nut : nut.querySelector(chon);
        if (!dich) continue;
        if (i === trangHienTai) dich.scrollIntoView({ behavior: kieuCuon(), block: 'start' });
        else denTrang(i, dich);
        return true;
      }
    }
    return false;
  }

  function moHuongDan() {
    if (!hd.hop.open) hd.hop.showModal();
    taiNoiDung();
  }

  // Nút ở thanh trên và lời mời trên màn hình chào.
  document.querySelectorAll('[data-mo-huong-dan]').forEach((nut) => nut.addEventListener('click', moHuongDan));
  hd.dong?.addEventListener('click', () => hd.hop.close());
  hd.hop.addEventListener('click', (event) => {
    if (event.target === hd.hop) hd.hop.close();
  });
  hd.mucLuc?.addEventListener('click', () => {
    if (!cuonToi(MA_MUC_LUC)) denTrang(0);
  });
  hd.truoc?.addEventListener('click', () => denTrang(trangHienTai - 1));
  hd.tiep?.addEventListener('click', () => denTrang(trangHienTai + 1));
  hd.hop.addEventListener('keydown', (event) => {
    if (!daTai || event.altKey || event.ctrlKey || event.metaKey) return;
    if (event.target.closest('input, textarea, select')) return;
    if (event.key === 'ArrowRight') denTrang(trangHienTai + 1);
    else if (event.key === 'ArrowLeft') denTrang(trangHienTai - 1);
    else return;
    event.preventDefault();
  });
  hd.noiDung.addEventListener('click', (event) => {
    const lk = event.target.closest('a[href^="#"]');
    if (!lk) return;
    event.preventDefault();
    let ma = lk.getAttribute('href').slice(1);
    try {
      ma = decodeURIComponent(ma);
    } catch {
      /* giữ nguyên nếu không phải chuỗi đã mã hoá */
    }
    cuonToi(ma);
  });

  window.huongDanGiaoDien = { mo: moHuongDan, dungMarkdown };
})();
