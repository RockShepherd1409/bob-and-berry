/* Bob & Berry — optional enhancements.
 *
 * Everything essential already works without this file: calling, WhatsApp,
 * SMS and email are plain links in the HTML, and the photos open as
 * normal images. This script adds: the in-place language switch, copy
 * buttons and the photo lightbox.
 *
 * Privacy: nothing here talks to a server or reads the visitor's location.
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

  /* ------------------------------------------------ keep bottom padding = bar height */
  var bar = $('.sticky-bar');
  if (bar && 'ResizeObserver' in window) {
    new ResizeObserver(function () {
      H.style.setProperty('--bar-h', Math.ceil(bar.getBoundingClientRect().height) + 'px');
    }).observe(bar);
  }
})();
