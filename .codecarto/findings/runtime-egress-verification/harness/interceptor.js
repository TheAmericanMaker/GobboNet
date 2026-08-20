/* GobboNet egress interceptor — injected at serve time, runs before all app code.
   Wraps every browser API capable of leaving the machine and reports each call. */
(function () {
  var SINK = '/_capture';
  var seq = 0;
  function host(u) {
    try { return new URL(u, location.href).host; } catch (e) { return '?' + u; }
  }
  function isLocal(u) {
    var h = host(u).split(':')[0];
    return h === '127.0.0.1' || h === 'localhost' || h === '::1' || h === '' ||
           /^192\.168\./.test(h) || /^10\./.test(h) || /\.local$/.test(h);
  }
  function report(rec) {
    rec.n = ++seq;
    rec.host = host(rec.url);
    rec.local = isLocal(rec.url);
    rec.t = Date.now();
    try {
      rec.stack = (new Error().stack || '').split('\n').slice(3, 6)
        .map(function (s) { return s.trim(); }).join(' | ');
    } catch (e) {}
    // Use the ORIGINAL fetch so our own reporting is not re-intercepted.
    _origFetch.call(window, SINK, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rec)
    }).catch(function () {});
    (window.__EGRESS = window.__EGRESS || []).push(rec);
  }

  var _origFetch = window.fetch;
  window.fetch = function (input, init) {
    var url = (typeof input === 'string') ? input : (input && input.url) || String(input);
    if (String(url).indexOf(SINK) === -1) {
      var m = (init && init.method) || (input && input.method) || 'GET';
      var b = init && init.body;
      report({ api: 'fetch', method: m, url: String(url),
               headers: (init && init.headers) ? JSON.parse(JSON.stringify(
                 init.headers instanceof Headers
                   ? Object.fromEntries(init.headers.entries()) : init.headers)) : null,
               body: (typeof b === 'string') ? b.slice(0, 20000)
                     : (b ? '[' + (b.constructor && b.constructor.name) + ']' : null) });
    }
    return _origFetch.apply(this, arguments);
  };

  var XO = XMLHttpRequest.prototype.open, XS = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) {
    this.__m = m; this.__u = u; return XO.apply(this, arguments);
  };
  XMLHttpRequest.prototype.send = function (body) {
    report({ api: 'xhr', method: this.__m, url: String(this.__u),
             body: (typeof body === 'string') ? body.slice(0, 20000) : (body ? '[binary]' : null) });
    return XS.apply(this, arguments);
  };

  var WS = window.WebSocket;
  window.WebSocket = function (u, p) {
    report({ api: 'websocket', method: 'WS', url: String(u) });
    return new WS(u, p);
  };
  window.WebSocket.prototype = WS.prototype;

  if (window.EventSource) {
    var ES = window.EventSource;
    window.EventSource = function (u, c) {
      report({ api: 'eventsource', method: 'SSE', url: String(u) });
      return new ES(u, c);
    };
    window.EventSource.prototype = ES.prototype;
  }

  if (navigator.sendBeacon) {
    var SB = navigator.sendBeacon.bind(navigator);
    navigator.sendBeacon = function (u, d) {
      report({ api: 'sendBeacon', method: 'POST', url: String(u),
               body: (typeof d === 'string') ? d.slice(0, 20000) : '[blob]' });
      return SB(u, d);
    };
  }

  // Catch dynamically-injected remote subresources (script/img/link/iframe).
  var setAttr = Element.prototype.setAttribute;
  Element.prototype.setAttribute = function (n, v) {
    if ((n === 'src' || n === 'href') && /^(https?:)?\/\//i.test(String(v)))
      report({ api: 'dom:' + this.tagName.toLowerCase() + '[' + n + ']', method: 'GET', url: String(v) });
    return setAttr.apply(this, arguments);
  };
  ['HTMLScriptElement', 'HTMLImageElement', 'HTMLIFrameElement', 'HTMLLinkElement'].forEach(function (k) {
    if (!window[k]) return;
    var prop = (k === 'HTMLLinkElement') ? 'href' : 'src';
    var d = Object.getOwnPropertyDescriptor(window[k].prototype, prop);
    if (!d || !d.set) return;
    Object.defineProperty(window[k].prototype, prop, {
      get: d.get,
      set: function (v) {
        if (/^(https?:)?\/\//i.test(String(v)))
          report({ api: 'dom:' + k + '.' + prop, method: 'GET', url: String(v) });
        return d.set.call(this, v);
      }
    });
  });

  console.log('%c[EGRESS INTERCEPTOR ACTIVE]', 'background:#900;color:#fff');
})();
