"use strict";
const $ = (id) => document.getElementById(id);
const input = $("video-input"), zone = $("dropzone"), button = $("analyze-btn"), video = $("video");
const timeline = $("timeline"), eventList = $("event-list"), riskChart = $("risk-chart");
const colors = {accident:"#fa776d",near_miss:"#f5c263",red_light:"#f68b68",wrong_way:"#f68b68",illegal_u_turn:"#f68b68",stopped_vehicle:"#79d6b5",jaywalking:"#bbf36b",failure_to_yield:"#bbf36b",illegal_turn:"#f68b68",solid_line_crossing:"#88a8ff",stop_line:"#79d6b5",congestion:"#79d6b5",road_obstacle:"#88a8ff",fire_smoke:"#f5c263"};
let selectedFile = null, objectUrl = null, videoDuration = 0, busy = false, riskPoints = [], currentEvents = [];
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

function showError(message) {
  const errorBox = $("error");
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
}

function clearError() {
  const errorBox = $("error");
  errorBox.textContent = "";
  errorBox.classList.add("hidden");
}

input.addEventListener("change", () => setFile(input.files[0]));
zone.addEventListener("dragover", e => { e.preventDefault(); if (!busy) zone.classList.add("drag"); });
zone.addEventListener("dragleave", () => zone.classList.remove("drag"));
zone.addEventListener("drop", e => { e.preventDefault(); zone.classList.remove("drag"); if (!busy) setFile(e.dataTransfer.files[0]); });
video.addEventListener("loadedmetadata", () => {
  videoDuration = Number.isFinite(video.duration) ? video.duration : 0;
  $("meta-resolution").textContent = video.videoWidth + " × " + video.videoHeight;
  $("meta-duration").textContent = videoDuration.toFixed(1) + " s";
  if (videoDuration > 120.1) { button.disabled = true; showError("Video 2 daqiqadan oshmasin. Qisqaroq MP4 tanlang."); }
});
video.addEventListener("timeupdate", () => renderRisk(riskPoints));

function setFile(file) {
  if (busy || !file) return;
  clearError();
  if (!file.name.toLowerCase().endsWith(".mp4")) return showError("Faqat MP4 video qabul qilinadi.");
  if (file.size > 250 * 1024 * 1024) return showError("Fayl 250 MB dan katta. Kichikroq MP4 tanlang.");
  if (!file.size) return showError("Fayl bo‘sh.");
  selectedFile = file;
  $("selected-file").textContent = file.name + " · " + (file.size / 1024 / 1024).toFixed(1) + " MB";
  button.disabled = false;
  if (objectUrl) URL.revokeObjectURL(objectUrl);
  objectUrl = URL.createObjectURL(file);
  video.src = objectUrl;
  video.classList.remove("hidden");
  $("empty-video").classList.add("hidden");
  $("video-meta").classList.remove("hidden");
  clearResults();
}

async function readJson(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) throw new Error("Server javobi olinmadi (HTTP " + response.status + ").");
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Tahlil bajarilmadi.");
  return data;
}

function setProgress(message, percent = null) {
  $("progress-text").textContent = message;
  const bar = $("progress-bar");
  if (percent === null) bar.removeAttribute("value"); else bar.value = percent;
}

button.addEventListener("click", async () => {
  if (!selectedFile || busy) return;
  busy = true;
  button.disabled = true;
  input.disabled = true;
  zone.classList.add("disabled");
  $("progress").classList.remove("hidden");
  $("progress-bar").classList.remove("hidden");
  clearError(); clearResults();
  setProgress("Video serverga yuklanmoqda…");
  const form = new FormData(); form.append("video", selectedFile);
  try {
    const started = await readJson(await fetch("/api/analyze", {method:"POST", body:form}));
    let state, failures = 0;
    for (;;) {
      await delay(1200);
      try {
        state = await readJson(await fetch("/api/jobs/" + encodeURIComponent(started.job_id), {cache:"no-store"}));
        failures = 0;
      } catch (err) { if (++failures >= 3) throw err; continue; }
      setProgress(state.message, state.progress);
      if (state.status === "error") throw new Error(state.message);
      if (state.status === "done") break;
    }
    const data = state.result;
    videoDuration = data.duration || videoDuration;
    $("meta-resolution").textContent = data.width + " × " + data.height;
    $("meta-duration").textContent = videoDuration.toFixed(1) + " s";
    currentEvents = data.events || [];
    riskPoints = data.risk || [];
    renderEvents(currentEvents); renderRisk(riskPoints);
    const peak = riskPoints.length ? Math.max(...riskPoints.map(p => p[1])) : null;
    $("risk-summary").textContent = peak === null ? "Xavf natijasi yo‘q." : "Eng yuqori xavf ko‘rsatkichi: " + peak.toFixed(3) + " · " + riskPoints.length + " vaqt nuqtasi";
    $("download-json").href = "/api/jobs/" + encodeURIComponent(started.job_id) + "/download";
    $("download-json").classList.remove("hidden");
  } catch (error) { showError(error.message || "Server bilan aloqa uzildi."); }
  finally {
    busy = false; input.disabled = false; zone.classList.remove("disabled");
    $("progress").classList.add("hidden"); $("progress-bar").classList.add("hidden");
    button.disabled = !selectedFile || videoDuration > 120.1;
  }
});

function seek(t) {
  video.currentTime = Math.max(0, Math.min(videoDuration, t));
  video.play().catch(() => {});
}

function renderEvents(events) {
  timeline.replaceChildren(); eventList.replaceChildren();
  $("event-count").textContent = events.length + " hodisa";
  timeline.style.height = "";
  if (!events.length) {
    const empty = document.createElement("div"); empty.className = "timeline-empty";
    empty.textContent = "Bu videoda hodisa aniqlanmadi. Bu xavf yo‘qligini kafolatlamaydi.";
    timeline.append(empty); return;
  }
  const duration = videoDuration || Math.max(...events.map(e => e[1]), 1);
  const labels = [...new Set(events.map(e => e[2]))];
  timeline.style.height = (labels.length * 26 + 20) + "px";
  for (const event of events) {
    const [start, end, label] = event;
    const title = label + ": " + start.toFixed(1) + "–" + end.toFixed(1) + " s";
    const bar = document.createElement("button");
    bar.type = "button"; bar.className = "event-bar"; bar.title = title; bar.setAttribute("aria-label", title);
    bar.style.cssText = "position:absolute;left:" + (start / duration * 96 + 2) + "%;width:" + Math.max(.5, (end-start) / duration * 96) + "%;top:" + (10 + labels.indexOf(label) * 26) + "px;background:" + (colors[label] || "#bbf36b");
    bar.addEventListener("click", () => seek(start)); timeline.append(bar);
    const row = document.createElement("button"); row.type = "button"; row.className = "event-row";
    const dot = document.createElement("span"); dot.className = "event-dot"; dot.style.background = colors[label] || "#bbf36b";
    const name = document.createElement("span"); name.className = "event-name"; name.textContent = label;
    const timing = document.createElement("small"); timing.textContent = start.toFixed(1) + "–" + end.toFixed(1) + " s"; name.append(timing);
    const arrow = document.createElement("span"); arrow.className = "event-time"; arrow.textContent = "↗";
    row.append(dot, name, arrow); row.addEventListener("click", () => seek(start)); eventList.append(row);
  }
}

function clearResults() {
  currentEvents = []; riskPoints = [];
  timeline.innerHTML = '<div class="timeline-empty">Tahlil natijasi hali yo‘q</div>';
  timeline.style.height = ""; eventList.replaceChildren();
  $("event-count").textContent = "0 hodisa"; $("risk-summary").textContent = "";
  $("download-json").classList.add("hidden"); renderRisk([]);
}

function renderRisk(points) {
  const ctx = riskChart.getContext("2d"), width = riskChart.clientWidth, height = 110, dpr = window.devicePixelRatio || 1;
  riskChart.width = Math.max(1, Math.floor(width * dpr)); riskChart.height = Math.floor(height * dpr);
  ctx.scale(dpr, dpr); ctx.clearRect(0, 0, width, height);
  const left = 30, right = width - 12, top = 10, bottom = 86;
  ctx.font = "10px monospace"; ctx.fillStyle = "#98a6a0"; ctx.strokeStyle = "#2a3835"; ctx.lineWidth = 1;
  for (const score of [0, .5, 1]) {
    const y = bottom - score * (bottom - top);
    ctx.fillText(String(score), 5, y + 3); ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
  }
  const duration = videoDuration || 1;
  ctx.fillText("0 s", left, 103); ctx.fillText(duration.toFixed(1) + " s", Math.max(left, right - 42), 103);
  if (!points.length) return;
  ctx.strokeStyle = "#bbf36b"; ctx.lineWidth = 2; ctx.beginPath();
  points.forEach(([t, score], i) => {
    const x = left + (right-left) * t / duration, y = bottom - Math.max(0,Math.min(1,score)) * (bottom-top);
    if (!i) ctx.moveTo(x,y); else ctx.lineTo(x,y);
  }); ctx.stroke();
  const cursor = left + (right-left) * video.currentTime / duration;
  ctx.strokeStyle = "#f2f4ef"; ctx.lineWidth = 1; ctx.setLineDash([3,3]); ctx.beginPath(); ctx.moveTo(cursor,top); ctx.lineTo(cursor,bottom); ctx.stroke(); ctx.setLineDash([]);
}
riskChart.addEventListener("click", e => {
  if (!selectedFile) return;
  const bounds = riskChart.getBoundingClientRect(); seek((e.clientX-bounds.left-30) / Math.max(1,bounds.width-42) * videoDuration);
});
window.addEventListener("resize", () => { renderRisk(riskPoints); });

async function loadSamples() {
  try {
    const data = await readJson(await fetch("/api/samples"));
    $("eda-status").textContent = data.message;
    if (!data.videos.length) return;
    const grid = $("eda-grid"); grid.replaceChildren();
    for (const row of data.videos) {
      const card = document.createElement("article"), name = document.createElement("small"), detail = document.createElement("strong"), stats = document.createElement("span");
      name.textContent = row.filename;
      detail.textContent = row.width + " × " + row.height;
      const fps = Number(row.fps), duration = Number(row.duration_sec);
      stats.textContent = fps.toFixed(2) + " fps · " + duration.toFixed(1) + " s · Yorug‘lik: " + row.mean_brightness_0_255 + "/255";
      card.append(name,detail,stats);
      if (row.detected_objects_by_class) {
        const counts = document.createElement("p"); counts.className = "eda-counts";
        counts.textContent = "Tanlangan kadrlardagi obyekt aniqlashlari (noyob obyektlar emas): " + Object.entries(row.detected_objects_by_class).map(([name,n]) => name + ": " + n).join(", "); card.append(counts);
      }
      if (row.motion_heatmap) {
        const img = document.createElement("img"); img.loading = "lazy"; img.src = "/artifacts/eda/" + encodeURIComponent(row.motion_heatmap); img.alt = row.filename + " obyekt markazlari zichligi"; card.append(img);
      }
      grid.append(card);
    }
    const link = document.createElement("a"); link.href = "/artifacts/eda/eda_summary.json"; link.textContent = "EDA JSON ni ochish ↗"; link.className = "eda-download"; $("eda-status").append(" ", link);
  } catch (_) { $("eda-status").textContent = "EDA holati olinmadi. Hisoblangan natijalar texnik hisobotda ko‘rsatiladi."; }
}
renderRisk([]); loadSamples();
