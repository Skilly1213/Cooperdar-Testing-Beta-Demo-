import { f as b } from "./firebase-config-F0v7j6pp.js";
const w = "modulepreload"
    , v = function (u) {
        return "/" + u
    }
    , p = {}
    , f = function (t, e, o) {
        let h = Promise.resolve();
        if (e && e.length > 0) {
            document.getElementsByTagName("link");
            const i = document.querySelector("meta[property=csp-nonce]")
                , r = (i == null ? void 0 : i.nonce) || (i == null ? void 0 : i.getAttribute("nonce"));
            h = Promise.allSettled(e.map(s => {
                if (s = v(s),
                    s in p)
                    return;
                p[s] = !0;
                const a = s.endsWith(".css")
                    , c = a ? '[rel="stylesheet"]' : "";
                if (document.querySelector(`link[href="${s}"]${c}`))
                    return;
                const n = document.createElement("link");
                if (n.rel = a ? "stylesheet" : w,
                    a || (n.as = "script"),
                    n.crossOrigin = "",
                    n.href = s,
                    r && n.setAttribute("nonce", r),
                    document.head.appendChild(n),
                    a)
                    return new Promise((d, g) => {
                        n.addEventListener("load", d),
                            n.addEventListener("error", () => g(new Error(`Unable to preload CSS for ${s}`)))
                    }
                    )
            }
            ))
        }
        function l(i) {
            const r = new Event("vite:preloadError", {
                cancelable: !0
            });
            if (r.payload = i,
                window.dispatchEvent(r),
                !r.defaultPrevented)
                throw i
        }
        return h.then(i => {
            for (const r of i || [])
                r.status === "rejected" && l(r.reason);
            return t().catch(l)
        }
        )
    };
class y {
    constructor() {
        this.synth = window.speechSynthesis,
            this.enabled = !0,
            this.voice = null,
            this.rate = 1,
            this.pitch = 1,
            this.volume = 1,
            this.loadSettings(),
            this.initVoices()
    }
    initVoices() {
        const t = () => {
            const e = this.synth.getVoices();
            e.length > 0 && (this.voice = e.find(o => o.lang.startsWith("en-")) || e[0])
        }
            ;
        t(),
            speechSynthesis.onvoiceschanged !== void 0 && (speechSynthesis.onvoiceschanged = t)
    }
    loadSettings() {
        const t = JSON.parse(localStorage.getItem("ttsSettings") || "{}");
        this.enabled = t.enabled !== !1,
            this.rate = t.rate || 1,
            this.pitch = t.pitch || 1,
            this.volume = t.volume || 1
    }
    saveSettings() {
        localStorage.setItem("ttsSettings", JSON.stringify({
            enabled: this.enabled,
            rate: this.rate,
            pitch: this.pitch,
            volume: this.volume
        }))
    }
    speak(t) {
        if (!this.enabled || !this.synth)
            return;
        this.synth.cancel();
        const e = new SpeechSynthesisUtterance(t);
        e.voice = this.voice,
            e.rate = this.rate,
            e.pitch = this.pitch,
            e.volume = this.volume,
            this.synth.speak(e)
    }
    announceSuggestionAdded(t) {
        const e = `New camera suggestion by ${t}`;
        this.speak(e)
    }
    toggle() {
        return this.enabled = !this.enabled,
            this.saveSettings(),
            this.enabled
    }
    setRate(t) {
        this.rate = Math.max(.5, Math.min(2, t)),
            this.saveSettings()
    }
    setPitch(t) {
        this.pitch = Math.max(.5, Math.min(2, t)),
            this.saveSettings()
    }
    setVolume(t) {
        this.volume = Math.max(0, Math.min(1, t)),
            this.saveSettings()
    }
}
const S = new y;
class A {
    constructor() {
        this.db = null,
            this.isInitialized = !1,
            this.firebaseConfig = b
    }
    async initialize() {
        if (!this.isInitialized)
            try {
                const { initializeApp: t } = await f(async () => {
                    const { initializeApp: a } = await import("https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js");
                    return {
                        initializeApp: a
                    }
                }
                    , [])
                    , { getDatabase: e, ref: o, push: h, serverTimestamp: l, onValue: i, remove: r } = await f(async () => {
                        const { getDatabase: a, ref: c, push: n, serverTimestamp: d, onValue: g, remove: m } = await import("https://www.gstatic.com/firebasejs/10.7.1/firebase-database.js");
                        return {
                            getDatabase: a,
                            ref: c,
                            push: n,
                            serverTimestamp: d,
                            onValue: g,
                            remove: m
                        }
                    }
                        , [])
                    , s = t(this.firebaseConfig);
                this.db = e(s),
                    this.firebaseMethods = {
                        ref: o,
                        push: h,
                        serverTimestamp: l,
                        onValue: i,
                        remove: r
                    },
                    this.isInitialized = !0,
                    console.log("Firebase initialized successfully")
            } catch (t) {
                throw console.error("Error initializing Firebase:", t),
                t
            }
    }
    async submitCameraSuggestion(t) {
        this.isInitialized || await this.initialize();
        try {
            const { ref: e, push: o, serverTimestamp: h } = this.firebaseMethods
                , l = e(this.db, "suggestions");
            let i = "anonymous";
            if (window.authManager) {
                const a = window.authManager.getCurrentUser();
                a && a.email && (i = a.email)
            }
            const r = {
                url: t.url,
                name: t.name,
                location_text: t.location_text,
                timestamp: h(),
                status: "pending",
                userAgent: navigator.userAgent,
                submitter_email: i,
                submitted_at: new Date().toISOString()
            };
            await o(l, r);
            const s = i.split("@")[0];
            return S.announceSuggestionAdded(s),
            {
                success: !0,
                message: "Camera suggestion submitted successfully!"
            }
        } catch (e) {
            return console.error("Error submitting camera suggestion:", e),
            {
                success: !1,
                message: "Failed to submit suggestion. Please try again."
            }
        }
    }
    async listenToSuggestions(t) {
        this.isInitialized || await this.initialize();
        try {
            const { ref: e, onValue: o } = this.firebaseMethods
                , h = e(this.db, "suggestions");
            o(h, l => {
                const i = l.val()
                    , r = [];
                i && Object.keys(i).forEach(s => {
                    r.push({
                        id: s,
                        ...i[s]
                    })
                }
                ),
                    t(r)
            }
            )
        } catch (e) {
            console.error("Error listening to suggestions:", e)
        }
    }
    validateSuggestion(t) {
        const e = [];
        return !t.url || t.url.trim() === "" ? e.push("Camera URL is required") : this.isValidUrl(t.url) || e.push("Please enter a valid URL"),
            !t.name || t.name.trim() === "" ? e.push("Camera name is required") : t.name.length > 100 && e.push("Camera name must be less than 100 characters"),
            !t.location_text || t.location_text.trim() === "" ? e.push("Location description is required") : t.location_text.length > 200 && e.push("Location description must be less than 200 characters"),
        {
            isValid: e.length === 0,
            errors: e
        }
    }
    isValidUrl(t) {
        try {
            const e = new URL(t);
            return e.protocol === "http:" || e.protocol === "https:"
        } catch {
            return !1
        }
    }
    isConfigured() {
        return this.firebaseConfig.apiKey !== "YOUR_API_KEY"
    }
}
class E {
    constructor() {
        this.auth = null,
            this.currentUser = null,
            this.isInitialized = !1,
            this.firebaseManager = new A,
            this.authStateChangeCallbacks = []
    }
    async initialize() {
        if (this.isInitialized)
            return Promise.resolve();
        try {
            await this.firebaseManager.initialize();
            this.currentUser = { email: "guest@yallcams.com", displayName: "Guest User" };
            this.isInitialized = !0;
            console.log("Auth manager initialized successfully (no-auth mode)");
            this.authStateChangeCallbacks.forEach(e => e(this.currentUser));
            return Promise.resolve()
        } catch (t) {
            console.error("Error initializing:", t);
            this.currentUser = { email: "guest@yallcams.com", displayName: "Guest User" };
            this.isInitialized = !0;
            return Promise.resolve()
        }
    }
    handleAuthStateChange(t) {
        this.currentUser = t || { email: "guest@yallcams.com", displayName: "Guest User" },
            console.log("User authenticated:", this.currentUser.email),
            this.authStateChangeCallbacks.forEach(e => e(this.currentUser))
    }
    onAuthStateChange(t) {
        this.authStateChangeCallbacks.push(t),
            this.isInitialized && t(this.currentUser)
    }
    isAuthorizedEmail(t) {
        return !0
    }
    async signInWithGoogle() {
        this.currentUser = { email: "guest@yallcams.com", displayName: "Guest User" };
        this.authStateChangeCallbacks.forEach(e => e(this.currentUser));
        return this.currentUser
    }
    async signOut() {
        this.isInitialized || await this.initialize();
        try {
            const { signOut: t } = this.authMethods;
            await t(this.auth),
                this.currentUser = null,
                console.log("User signed out")
        } catch (t) {
            throw console.error("Error signing out:", t),
            t
        }
    }
    isAuthenticated() {
        return !0
    }
    getCurrentUser() {
        return this.currentUser || { email: "guest@yallcams.com", displayName: "Guest User" }
    }
}
export { E as A, A as F, f as _, S as t };
