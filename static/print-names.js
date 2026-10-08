/* WFAPrint: ask the teacher for their names file before a printout that carries a child's name.
 *
 * Needs WFANames (wfa-shared names-file.js, loaded in base.html). Names are read in the browser,
 * sent ONLY in the body of that one print request (never in a URL), and the file is cleared from
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

  function downloadPdfPost(url, names, fallbackName) {
    return postJson(url, names ? { names: names } : {}).then(function (resp) {
      if (!resp.ok) throw new Error('The PDF could not be made (' + resp.status + ').');
      var cd = resp.headers.get('Content-Disposition') || '';
      var m = /filename="?([^";]+)"?/i.exec(cd);
      return resp.blob().then(function (blob) { downloadBlob(blob, m ? m[1] : (fallbackName || 'download.pdf')); });
    });
  }

  root.WFAPrint = { pidsFrom: pidsFrom, askNames: askNames, postJson: postJson, downloadBlob: downloadBlob, downloadPdfPost: downloadPdfPost };
})(typeof window !== 'undefined' ? window : this);
