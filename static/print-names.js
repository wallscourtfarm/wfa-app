/* WFAPrint: ask the teacher for their names file before a printout that carries a child's name.
 *
 * Needs WFANames (wfa-shared names-file.js, loaded in base.html). Names are read in the browser and written
 * onto the downloaded PDF IN THIS BROWSER (stampPdf); they are never sent to the server. The file is cleared from
 * memory straight afterwards. Nothing is saved in the browser (no localStorage / cookies / caches).
 *
 *   WFAPrint.pidsFrom(selector)         -> array of pupil_ids from [data-pupil-id] elements (or null if none)
 *   WFAPrint.askNames(pids)             -> Promise<{names, cancelled}>
 *        names     : {pupil_id: {first, last}} for just those pupils (all pupils in the file if pids is
 *                    null/empty), or null for "Print without names"
 *        cancelled : true only if the names dialog failed (print should not go ahead)
 *   WFAPrint.postJson(url, body)        -> Promise<Response>  (POST, JSON)
 *   WFAPrint.downloadBlob(blob, name)
 *   WFAPrint.downloadPdfPost(url, names, fallbackName) -> Promise<void>  (POST {names}, save the returned PDF)
 */
(function (root) {
  'use strict';

  function pidsFrom(selector) {
    var seen = {}, out = [];
    root.document.querySelectorAll(selector || '[data-pupil-id]').forEach(function (el) {
      var id = el.getAttribute('data-pupil-id');
      if (id && !seen[id]) { seen[id] = 1; out.push(id); }
    });
    return out.length ? out : null;
  }

  function askNames(pids) {
    if (!root.WFANames || typeof root.WFANames.pick !== 'function') {
      return Promise.resolve({ names: null, cancelled: false });
    }
    return root.WFANames.pick({ purpose: 'Names will be printed on this sheet.' }).then(function (file) {
      if (!file) return { names: null, cancelled: false };           // "Print without names"
      var names;
      try {
        names = file.toMap(pids && pids.length ? pids : undefined);
      } finally {
        try { file.clear(); } catch (e) { /* nothing to clear */ }
      }
      return { names: Object.keys(names).length ? names : null, cancelled: false };
    }, function () {
      return { names: null, cancelled: true };
    });
  }

  function postJson(url, body) {
    return root.fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  }

  function downloadBlob(blob, name) {
    var url = root.URL.createObjectURL(blob);
    var a = root.document.createElement('a');
    a.href = url; a.download = name; root.document.body.appendChild(a); a.click();
    root.document.body.removeChild(a);
    setTimeout(function () { root.URL.revokeObjectURL(url); }, 1000);
  }

  // ── Writing names onto a PDF, in the browser ────────────────────────────────────────────────
  // The server draws sheets with INITIALS and records every name slot in the PDF's Keywords field
  // ("WFASTAMPS2:" + JSON, see stamps.py). stampPdf() paints the real name over each initials label using
  // pdf-lib (loaded from cdnjs on first use). Names never leave this page.
  var PDFLIB_URL = 'https://cdnjs.cloudflare.com/ajax/libs/pdf-lib/1.17.1/pdf-lib.min.js';
  var pdfLibPromise = null;
  function loadPdfLib() {
    if (root.PDFLib) return Promise.resolve(root.PDFLib);
    if (!pdfLibPromise) pdfLibPromise = new Promise(function (res, rej) {
      var s = root.document.createElement('script');
      s.src = PDFLIB_URL; s.onload = function () { res(root.PDFLib); };
      s.onerror = function () { pdfLibPromise = null; rej(new Error('Could not load the PDF library.')); };
      root.document.head.appendChild(s);
    });
    return pdfLibPromise;
  }

  function latin(t) { return String(t || '').normalize('NFC').replace(/[^\u0020-\u007E\u00A0-\u00FF]/g, ''); }

  function stampPdf(bytes, names) {
    if (!names) return Promise.resolve(bytes);
    return loadPdfLib().then(function (L) {
      return L.PDFDocument.load(bytes, { updateMetadata: false }).then(function (doc) {
        var kw = doc.getKeywords() || '';
        if (kw.indexOf('WFASTAMPS2:') !== 0) return bytes;                 // nothing to stamp
        var stamps = JSON.parse(kw.slice(11));
        return Promise.all([doc.embedFont(L.StandardFonts.HelveticaBold), doc.embedFont(L.StandardFonts.Helvetica)]).then(function (fonts) {
          var pages = doc.getPages(), rgb = function (a) { return L.rgb(a[0], a[1], a[2]); };
          stamps.forEach(function (r) {
            var n = names[r.id]; if (!n) return;
            var nm = r.m === 'n' ? ((n.first || '') + ' ' + (n.last || '')).trim() : (n.first || '');
            nm = latin(nm); if (!nm) return;
            var page = pages[r.pg]; if (!page) return;
            var font = r.b ? fonts[0] : fonts[1], full = (r.pre || '') + nm;
            var newW = font.widthOfTextAtSize(full, r.s);
            if (r.pill) {                                                 // white pill whose width follows the name
              var px = r.pill[0], py = r.pill[1], ph = r.pill[2], pad = r.pill[3], rad = r.pill[4];
              var pw = Math.max(r.w + 2 * pad, newW + 2 * pad);
              page.drawSvgPath('M ' + rad + ',0 H ' + (pw - rad) + ' Q ' + pw + ',0 ' + pw + ',' + rad + ' V ' + (ph - rad) +
                ' Q ' + pw + ',' + ph + ' ' + (pw - rad) + ',' + ph + ' H ' + rad + ' Q 0,' + ph + ' 0,' + (ph - rad) +
                ' V ' + rad + ' Q 0,0 ' + rad + ',0 Z', { x: px, y: py + ph, color: L.rgb(1, 1, 1), borderWidth: 0 });
              page.drawText(nm, { x: r.x, y: r.y, size: r.s, font: font, color: rgb(r.tc) });
              return;
            }
            var span = Math.max(r.w, newW) + 4, x0 = r.a === 'c' ? r.x - span / 2 : r.x - 1;
            page.drawRectangle({ x: x0, y: r.y - 1, width: span, height: r.s * 0.95 + 1, color: rgb(r.cv) });
            var tx = r.a === 'c' ? r.x - newW / 2 : r.x;
            page.drawText(full, { x: tx, y: r.y, size: r.s, font: font, color: rgb(r.tc) });
          });
          doc.setKeywords([]);
          return doc.save();
        });
      });
    });
  }

  // Stamp (when names are given) and save a PDF supplied as bytes / a Blob.
  function deliverPdf(data, names, filename) {
    var p = data instanceof root.Blob ? data.arrayBuffer() : Promise.resolve(data);
    return p.then(function (buf) { return stampPdf(buf, names); }).then(function (out) {
      downloadBlob(new root.Blob([out], { type: 'application/pdf' }), filename);
    });
  }

  // POST (without names) and save the returned PDF, adding names in this browser when `names` is given.
  function downloadPdfPost(url, names, fallbackName) {
    return postJson(url, {}).then(function (resp) {
      if (!resp.ok) throw new Error('The PDF could not be made (' + resp.status + ').');
      var cd = resp.headers.get('Content-Disposition') || '';
      var m = /filename="?([^";]+)"?/i.exec(cd);
      return resp.blob().then(function (blob) { return deliverPdf(blob, names, m ? m[1] : (fallbackName || 'download.pdf')); });
    });
  }

  root.WFAPrint = { pidsFrom: pidsFrom, askNames: askNames, postJson: postJson, downloadBlob: downloadBlob,
                    downloadPdfPost: downloadPdfPost, stampPdf: stampPdf, deliverPdf: deliverPdf };
})(typeof window !== 'undefined' ? window : this);
