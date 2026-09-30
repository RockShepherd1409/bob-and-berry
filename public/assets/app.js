/* Bob & Berry — optional enhancements.
 *
 * Everything essential already works without this file: calling, WhatsApp,
 * SMS and email are plain links in the HTML, and the photos open as
 * normal images. This script adds: the in-place language switch, copy
 * buttons, the photo lightbox, and the "share your location" sheet.
 *
 * Privacy: nothing here talks to a server. The finder's location is only
 * read after they tap the button, and it only ever goes into a message
 * they review and send themselves.
 */
(function () {
  'use strict';

  var H = document.documentElement;
  var BB = window.BB;
  if (!BB) return;

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function t(key, vars) {
    var s = BB.t(key) || '';
    if (vars) for (var k in vars) s = s.split('{' + k + '}').join(vars[k]);
    return s;
  }
  function lang() { return H.lang === 'he' ? 'he' : 'en'; }
  var page = {};
  try { page = JSON.parse($('#bb-page').textContent); } catch (e) { /* optional */ }

  /* ------------------------------------------------ status toast */
  var toast = $('#bb-toast'), toastTimer;
  function say(msg) {
    if (!toast) return;
    toast.textContent = '';
    // Re-inserting the text makes screen readers announce repeated messages.
    setTimeout(function () { toast.textContent = msg; toast.classList.add('is-shown'); }, 30);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.classList.remove('is-shown'); }, 4500);
  }

  /* ------------------------------------------------ language switch */
  $$('.lang a[data-lang]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      var l = a.getAttribute('data-lang');
      e.preventDefault();
      try { localStorage.setItem('bb-lang', l); } catch (err) { /* private mode */ }
      try {
        var u = new URL(location.href);
        if (u.searchParams.has('lang')) { u.searchParams.set('lang', l); history.replaceState(history.state, '', u.toString()); }
      } catch (err) { /* old browser */ }
      BB.apply(l);
      document.dispatchEvent(new CustomEvent('bb:lang'));
      a.focus();
    });
  });

  /* ------------------------------------------------ copy to clipboard */
  function legacyCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    var ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(ta);
    return ok;
  }
  function copyText(text) {
    return new Promise(function (resolve, reject) {
      function fallback() { legacyCopy(text) ? resolve() : reject(); }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(resolve, fallback);
      } else {
        fallback();
      }
    });
  }
  function selectText(el) {
    try {
      var r = document.createRange();
      r.selectNodeContents(el);
      var s = window.getSelection();
      s.removeAllRanges();
      s.addRange(r);
    } catch (e) { /* ignore */ }
  }
  $$('[data-copy]').forEach(function (btn) {
    btn.hidden = false;
    btn.addEventListener('click', function () {
      var target = document.getElementById(btn.getAttribute('data-copy-target') || '');
      copyText(btn.getAttribute('data-copy')).then(
        function () { say(t('copied')); },
        function () { if (target) selectText(target); say(t('copy_failed')); }
      );
    });
  });

  /* ------------------------------------------------ broken images */
  function markBroken(img) {
    var box = img.closest('.ph');
    if (box) box.classList.add('is-broken');
  }
  $$('img[data-ph]').forEach(function (img) {
    img.addEventListener('error', function () { markBroken(img); });
    if (img.loading !== 'lazy' && img.complete && !img.naturalWidth && img.getAttribute('src')) markBroken(img);
  });

  /* ------------------------------------------------ modal helper */
  var canDialog = typeof HTMLDialogElement === 'function' && 'showModal' in HTMLDialogElement.prototype;

  // Opens a <dialog> as a modal and guarantees cleanup however it closes
  // (button, Esc, Android Back, backdrop). Watching the `open` attribute as
  // well as the `close` event keeps this reliable across browsers.
  function modal(dlg, onClosed) {
    var active = false, returnTo = null;
    function finish() {
      if (!active) return;
      active = false;
      H.classList.remove('no-scroll');
      if (onClosed) onClosed();
      if (returnTo && document.contains(returnTo)) returnTo.focus();
    }
    dlg.addEventListener('close', finish);
    if ('MutationObserver' in window) {
      new MutationObserver(function () { if (!dlg.open) finish(); })
        .observe(dlg, { attributes: true, attributeFilter: ['open'] });
    }
    return function open(focusEl, from) {
      returnTo = from || null;
      active = true;
      dlg.showModal();
      H.classList.add('no-scroll');
      if (focusEl) focusEl.focus();
    };
  }

  /* ------------------------------------------------ photo lightbox */
  var lb = $('#bb-lightbox');
  var thumbs = $$('.gallery a.thumb');
  if (lb && thumbs.length && canDialog) {
    var stage = $('.lb-stage', lb);
    var lbImg = $('img', stage);
    var lbSrc = $('source', stage);
    var count = $('.lb-count', lb);
    var caption = $('.lb-caption', lb);
    var closeBtn = $('.lb-close', lb);
    var idx = 0;
    var openLightbox = modal(lb, function () {
      lbImg.removeAttribute('src');
      lbImg.removeAttribute('srcset');
      lbSrc.removeAttribute('srcset');
    });

    var preload = function (i) {
      var a = thumbs[(i + thumbs.length) % thumbs.length];
      var p = new Image();
      p.sizes = '100vw';
      p.srcset = a.getAttribute('data-srcset-webp') || a.getAttribute('data-srcset');
    };
    var render = function () {
      var a = thumbs[idx], thumbImg = $('img', a);
      stage.classList.remove('is-broken');
      lbSrc.srcset = a.getAttribute('data-srcset-webp') || '';
      lbImg.srcset = a.getAttribute('data-srcset');
      lbImg.src = a.getAttribute('href');
      lbImg.alt = thumbImg ? thumbImg.alt : '';
      caption.textContent = lbImg.alt;
      count.textContent = t('photo_counter', { i: idx + 1, total: thumbs.length });
    };
    var show = function (i) {
      idx = (i + thumbs.length) % thumbs.length;
      render();
      if (thumbs.length > 1) { preload(idx + 1); preload(idx - 1); }
    };

    lbImg.addEventListener('error', function () { if (lbImg.getAttribute('src')) stage.classList.add('is-broken'); });
    thumbs.forEach(function (a, i) {
      a.addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.button > 0) return;
        e.preventDefault();
        show(i);
        openLightbox(closeBtn, a);
      });
    });
    closeBtn.addEventListener('click', function () { lb.close(); });
    $('.lb-prev', lb).addEventListener('click', function () { show(idx - 1); });
    $('.lb-next', lb).addEventListener('click', function () { show(idx + 1); });
    lb.addEventListener('keydown', function (e) {
      var fwd = H.dir === 'rtl' ? 'ArrowLeft' : 'ArrowRight';
      var back = H.dir === 'rtl' ? 'ArrowRight' : 'ArrowLeft';
      if (e.key === fwd) { e.preventDefault(); show(idx + 1); }
      else if (e.key === back) { e.preventDefault(); show(idx - 1); }
      else if (e.key === 'Home') { e.preventDefault(); show(0); }
      else if (e.key === 'End') { e.preventDefault(); show(thumbs.length - 1); }
    });
    // Swipe. In Hebrew the gallery runs right-to-left, so the direction flips.
    var sx = null, sy = 0;
    stage.addEventListener('pointerdown', function (e) {
      if (e.pointerType === 'mouse' || !e.isPrimary) return;
      sx = e.clientX; sy = e.clientY;
    });
    stage.addEventListener('pointerup', function (e) {
      if (sx === null) return;
      var dx = e.clientX - sx, dy = e.clientY - sy;
      sx = null;
      if (Math.abs(dx) < 45 || Math.abs(dx) < Math.abs(dy) * 1.3) return;
      var forward = dx < 0;
      if (H.dir === 'rtl') forward = !forward;
      show(idx + (forward ? 1 : -1));
    });
    stage.addEventListener('pointercancel', function () { sx = null; });
    document.addEventListener('bb:lang', function () { if (lb.open) render(); });
  }

  /* ------------------------------------------------ share location */
  var sheet = $('#bb-locate');
  var openers = $$('[data-open-locate]');
  if (sheet && openers.length && canDialog && page.contact) {
    var getBtn = $('#loc-get'), getLabel = $('#loc-get-label');
    var status = $('#loc-status');
    var place = $('#loc-place');
    var msg = $('#loc-msg');
    var reset = $('#loc-reset');
    var waLink = $('#loc-wa'), smsLink = $('#loc-sms'), copyBtn = $('#loc-copy');
    var coords = null, state = '', edited = false, watchdog = null, requestId = 0;
    var openSheet = modal(sheet);

    var names = function () { return page.names[lang()]; };
    var compose = function () {
      var c = page.contact, l = lang();
      var lines = [t('msg_found', { to: c.short[l], name: names() })];
      var p = place.value.trim();
      if (coords) {
        var line = t('msg_map', { url: coords.url });
        if (coords.acc) line += ' ' + t('msg_accuracy', { m: coords.acc });
        lines.push(line);
      }
      if (p) lines.push(t('msg_place', { place: p }));
      if (!coords && !p) lines.push(t('msg_where_blank'));
      lines.push(c.contactMe[l]);
      return lines.join('\n');
    };
    var updateLinks = function () {
      var text = msg.value;
      var enc = encodeURIComponent(text);
      if (waLink) waLink.href = 'https://wa.me/' + page.contact.wa + '?text=' + enc;
      smsLink.href = 'sms:' + page.contact.sms + '?&body=' + enc;
      reset.hidden = !edited;
    };
    var refresh = function () {
      if (!edited) msg.value = compose();
      updateLinks();
    };
    var setStatus = function (key, tone, vars) {
      state = key;
      status.setAttribute('data-tone', tone || '');
      status.textContent = key ? t(key, vars) : '';
      getLabel.textContent = t(coords ? 'loc_again' : 'loc_get');
    };
    var geoError = function (code) {
      getBtn.disabled = false;
      setStatus(code === 1 ? 'loc_denied' : code === 3 ? 'loc_timeout' : 'loc_unavailable', 'warn');
      place.focus();
    };

    var MAP_URL = /https:\/\/www\.google\.com\/maps\/search\/\?api=1&query=[-0-9.,]+/;
    var unsupported = function () {
      getBtn.disabled = false;
      setStatus('loc_unsupported', 'warn');
      place.focus();
    };

    getBtn.addEventListener('click', function () {
      var geo = navigator.geolocation;
      if (!geo || typeof geo.getCurrentPosition !== 'function' || !window.isSecureContext) return unsupported();
      var id = ++requestId;
      getBtn.disabled = true;
      setStatus('loc_finding', '');
      clearTimeout(watchdog);
      // Some browsers never answer if the permission prompt is ignored.
      watchdog = setTimeout(function () { if (id === requestId && getBtn.disabled) geoError(3); }, 25000);
      try {
        geo.getCurrentPosition(function (pos) {
          if (id !== requestId) return;
          clearTimeout(watchdog);
          getBtn.disabled = false;
          var lat = pos.coords.latitude.toFixed(5), lng = pos.coords.longitude.toFixed(5);
          var acc = Math.round(pos.coords.accuracy || 0);
          coords = {
            url: 'https://www.google.com/maps/search/?api=1&query=' + lat + ',' + lng,
            acc: acc
          };
          if (edited) {
            // Keep the finder's own wording: update the map link if it is
            // already in their text, otherwise add it on a new line.
            var line = t('msg_map', { url: coords.url }) + (acc ? ' ' + t('msg_accuracy', { m: acc }) : '');
            msg.value = MAP_URL.test(msg.value) ? msg.value.replace(MAP_URL, coords.url)
                                               : msg.value.replace(/\s*$/, '') + '\n' + line;
          }
          if (acc > 100) setStatus('loc_rough', 'warn', { m: acc });
          else setStatus('loc_ok', 'ok');
          refresh();
        }, function (err) {
          if (id !== requestId) return;
          clearTimeout(watchdog);
          geoError(err && err.code);
        }, { enableHighAccuracy: true, timeout: 20000, maximumAge: 30000 });
      } catch (e) {
        clearTimeout(watchdog);
        unsupported();
      }
    });

    place.addEventListener('input', refresh);
    msg.addEventListener('input', function () { edited = true; updateLinks(); });
    reset.addEventListener('click', function () { edited = false; refresh(); msg.focus(); });
    copyBtn.addEventListener('click', function () {
      copyText(msg.value).then(function () { say(t('loc_copied')); }, function () {
        msg.focus();
        msg.select();
        say(t('copy_failed'));
      });
    });

    openers.forEach(function (b) {
      b.hidden = false;
      b.addEventListener('click', function () {
        refresh();
        openSheet(getBtn, b);
      });
    });
    $$('[data-close]', sheet).forEach(function (b) { b.addEventListener('click', function () { sheet.close(); }); });
    sheet.addEventListener('click', function (e) { if (e.target === sheet) sheet.close(); });
    document.addEventListener('bb:lang', function () {
      if (state) setStatus(state, status.getAttribute('data-tone'), coords && coords.acc ? { m: coords.acc } : null);
      else getLabel.textContent = t('loc_get');
      refresh();
    });
  }

  /* ------------------------------------------------ keep bottom padding = bar height */
  var bar = $('.sticky-bar');
  if (bar && 'ResizeObserver' in window) {
    new ResizeObserver(function () {
      H.style.setProperty('--bar-h', Math.ceil(bar.getBoundingClientRect().height) + 'px');
    }).observe(bar);
  }
})();
