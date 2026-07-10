(function () {
    const r = document.createElement("link").relList;
    if (r && r.supports && r.supports("modulepreload"))
        return;
    for (const e of document.querySelectorAll('link[rel="modulepreload"]'))
        s(e);
    new MutationObserver(e => {
        for (const t of e)
            if (t.type === "childList")
                for (const o of t.addedNodes)
                    o.tagName === "LINK" && o.rel === "modulepreload" && s(o)
    }
    ).observe(document, {
        childList: !0,
        subtree: !0
    });
    function i(e) {
        const t = {};
        return e.integrity && (t.integrity = e.integrity),
            e.referrerPolicy && (t.referrerPolicy = e.referrerPolicy),
            e.crossOrigin === "use-credentials" ? t.credentials = "include" : e.crossOrigin === "anonymous" ? t.credentials = "omit" : t.credentials = "same-origin",
            t
    }
    function s(e) {
        if (e.ep)
            return;
        e.ep = !0;
        const t = i(e);
        fetch(e.href, t)
    }
}
)();
const n = {
    apiKey: "AIzaSyBJTjjE2Ezfh4Dby_XXgPbaBnkIu3F2Q2Y",
    authDomain: "yallsoft.firebaseapp.com",
    databaseURL: "https://yallsoft-default-rtdb.firebaseio.com",
    projectId: "yallsoft",
    storageBucket: "yallsoft.firebasestorage.app",
    messagingSenderId: "489816130887",
    appId: "1:489816130887:web:fef7164a16e2a916243862",
    measurementId: "G-FCJ2JQ0FYQ"
};
export { n as f };
