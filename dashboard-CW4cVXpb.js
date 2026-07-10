import { f as c } from "./firebase-config-F0v7j6pp.js";/* empty css                  */import { initializeApp as r } from "https://www.gstatic.com/firebasejs/9.22.0/firebase-app.js"; import { getAuth as o, onAuthStateChanged as v, signOut as m } from "https://www.gstatic.com/firebasejs/9.22.0/firebase-auth.js"; const p = r(c), i = o(p); v(i, s => s); document.getElementById("auth-btn").addEventListener("click", async () => { try { await m(i), window.location.href = "/login.html" } catch (s) { console.error("Sign out error:", s) } }); async function l() {
    try {
        const a = await (await fetch("https://pub-ad3d883b91e84369b65f132fa32d1020.r2.dev/stats.json")).json(), d = new Date(a.generated_at); document.getElementById("last-updated").textContent = `Updated: ${d.toLocaleTimeString()}`; const n = document.getElementById("stats-content"); n.innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-value">${a.total_cameras.toLocaleString()}</div>
                            <div class="stat-label">Total Cameras</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${a.streaming_cameras.toLocaleString()}</div>
                            <div class="stat-label">Streaming Now</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${a.streaming_percentage.toFixed(1)}%</div>
                            <div class="stat-label">Stream Rate</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-value">${a.summary.unique_states}</div>
                            <div class="stat-label">States Covered</div>
                        </div>
                    </div>
                    
                    <div class="details-section">
                        <div class="details-title">Camera Types</div>
                        <div class="details-list">
                            <div class="detail-item">
                                <span class="detail-name">Traffic Cameras</span>
                                <span class="detail-value">${a.cameras_by_type.traffic.toLocaleString()}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-name">General Cameras</span>
                                <span class="detail-value">${a.cameras_by_type.general.toLocaleString()}</span>
                            </div>
                            <div class="detail-item">
                                <span class="detail-name">Chaser Cameras</span>
                                <span class="detail-value">${a.cameras_by_type.chaser.toLocaleString()}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="details-section">
                        <div class="details-title">Top States by Camera Count</div>
                        <div class="details-list">
                            ${Object.entries(a.cameras_by_state).sort(([, t], [, e]) => e - t).slice(0, 10).map(([t, e]) => `
                                    <div class="detail-item">
                                        <span class="detail-name">${t}</span>
                                        <span class="detail-value">${e.toLocaleString()}</span>
                                    </div>
                                `).join("")}
                        </div>
                    </div>
                    
                    <div class="details-section">
                        <div class="details-title">Stream Types Available</div>
                        <div class="details-list">
                            ${Object.entries(a.stream_types_available).filter(([, t]) => t > 0).map(([t, e]) => `
                                    <div class="detail-item">
                                        <span class="detail-name">${t}</span>
                                        <span class="detail-value">${e.toLocaleString()}</span>
                                    </div>
                                `).join("")}
                        </div>
                    </div>
                `} catch (s) { console.error("Error loading stats:", s), document.getElementById("stats-content").innerHTML = '<div class="error">Failed to load statistics. Please try again later.</div>' }
} l(); setInterval(l, 6e4);
