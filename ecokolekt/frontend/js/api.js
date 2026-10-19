/* EcoKolekt — client API + session (JWT). Espace de noms global : window.EK */
(function () {
  "use strict";
  var EK = (window.EK = window.EK || {});

  var meta = document.querySelector('meta[name="ek-api"]');
  var BASE = String(window.EK_API || (meta && meta.content) || "http://localhost:8000/api").replace(/\/$/, "");
  EK.API_BASE = BASE;

  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* mode privé */ } },
    del: function (k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
  };
  EK.store = store;

  var session = (EK.session = {
    user: null,
    access: store.get("ek.access"),
    refresh: store.get("ek.refresh"),
    set: function (d) {
      if (d.access) { this.access = d.access; store.set("ek.access", d.access); }
      if (d.refresh) { this.refresh = d.refresh; store.set("ek.refresh", d.refresh); }
      if (d.user) this.user = d.user;
    },
    clear: function () { this.user = this.access = this.refresh = null; store.del("ek.access"); store.del("ek.refresh"); },
  });

  function ApiError(status, data) {
    this.status = status;
    this.data = data || {};
    this.message = ApiError.text(data, status);
  }
  ApiError.text = function (d, status) {
    if (d && typeof d === "object") {
      if (d.detail) return String(d.detail);
      var k = Object.keys(d)[0];
      if (k) { var v = d[k]; return String(Array.isArray(v) ? v[0] : v); }
    }
    return status === 0 ? "Connexion impossible. Vérifiez votre réseau." : "Une erreur est survenue (" + status + ").";
  };
  ApiError.prototype = Object.create(Error.prototype);
  EK.ApiError = ApiError;

  var refreshing = null;
  function refreshToken() {
    if (!session.refresh) return Promise.reject(new ApiError(401, {}));
    refreshing = refreshing || fetch(BASE + "/auth/token/refresh/", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh: session.refresh }),
    }).then(function (r) {
      if (!r.ok) throw new ApiError(401, {});
      return r.json();
    }).then(function (d) { session.set(d); }).finally(function () { refreshing = null; });
    return refreshing;
  }

  function qs(params) {
    var p = new URLSearchParams();
    Object.keys(params || {}).forEach(function (k) {
      if (params[k] !== undefined && params[k] !== null && params[k] !== "") p.append(k, params[k]);
    });
    var s = p.toString();
    return s ? "?" + s : "";
  }

  function request(method, path, body, opts, retried) {
    opts = opts || {};
    var headers = {};
    if (session.access && opts.auth !== false) headers.Authorization = "Bearer " + session.access;
    var init = { method: method, headers: headers };
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) { headers["Content-Type"] = "application/json"; init.body = JSON.stringify(body); }
    return fetch(BASE + path, init).then(function (res) {
      if (res.status === 401 && !retried && opts.auth !== false && session.refresh) {
        return refreshToken().then(function () { return request(method, path, body, opts, true); })
          .catch(function () { session.clear(); EK.onLogout && EK.onLogout(); throw new ApiError(401, { detail: "Session expirée." }); });
      }
      if (opts.blob) {
        if (!res.ok) throw new ApiError(res.status, {});
        return res.blob();
      }
      return res.text().then(function (t) {
        var data = null;
        try { data = t ? JSON.parse(t) : null; } catch (e) { data = null; }
        if (!res.ok) throw new ApiError(res.status, data);
        return data;
      });
    }, function () { throw new ApiError(0, {}); });
  }

  EK.navId = 0;
  EK.api = {
    /* Une réponse GET qui arrive après un changement de page est ignorée : elle ne doit pas écrire dans la page suivante. */
    get: function (p, params, o) {
      var id = EK.navId, pr = request("GET", p + qs(params), undefined, o);
      if (o && o.keep) return pr;
      return new Promise(function (resolve, reject) {
        pr.then(function (v) { if (id === EK.navId) resolve(v); }, function (e) { if (id === EK.navId) reject(e); });
      });
    },
    post: function (p, b, o) { return request("POST", p, b || {}, o); },
    patch: function (p, b) { return request("PATCH", p, b); },
    del: function (p) { return request("DELETE", p); },
    blob: function (p) { return request("GET", p, undefined, { blob: true }); },
    items: function (d) { return Array.isArray(d) ? d : (d && d.results) || []; },
  };

  EK.loadMe = function () {
    return EK.api.get("/me/").then(function (u) { session.user = u; return u; });
  };
})();
