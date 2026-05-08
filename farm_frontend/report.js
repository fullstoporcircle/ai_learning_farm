"use strict";

var reportModule = (function () {
    var API_BASE = window.API_BASE_URL || "";

    function escapeHtml(str) {
        if (!str) return "";
        var div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }

    async function apiFetch(url, options) {
        options = options || {};
        var headers = options.headers || {};
        headers["Content-Type"] = headers["Content-Type"] || "application/json";
        var res = await fetch(API_BASE + url, { ...options, headers });
        if (!res.ok) {
            var errText = await res.text();
            throw new Error("HTTP " + res.status + ": " + errText);
        }
        return await res.json();
    }

    function showToast(msg, type) {
        type = type || "info";
        var existing = document.querySelector(".toast");
        if (existing) existing.remove();
        var toast = document.createElement("div");
        toast.className = "toast toast-" + type;
        toast.textContent = msg;
        toast.setAttribute("role", "status");
        document.body.appendChild(toast);
        requestAnimationFrame(function () {
            toast.classList.add("show");
            setTimeout(function () {
                toast.classList.remove("show");
                setTimeout(function () { toast.remove(); }, 300);
            }, 2800);
        });
    }

    function open() {
        if (typeof _saveFocus === 'function') _saveFocus();
        var modal = document.getElementById("report-modal");
        if (modal) {
            modal.style.display = "block";
            modal.setAttribute("aria-hidden", "false");
        }
        loadWeeklyReport();
    }

    function close() {
        var modal = document.getElementById("report-modal");
        if (modal) {
            modal.style.display = "none";
            modal.setAttribute("aria-hidden", "true");
        }
        if (typeof _restoreFocus === 'function') _restoreFocus();
    }

    async function loadWeeklyReport() {
        var body = document.getElementById("report-modal-body");
        var footer = document.getElementById("report-modal-footer");
        if (!body) return;

        body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--color-text-muted);">⏳ 正在生成学习报告...</div>';
        if (footer) footer.style.display = "none";

        try {
            var data = await apiFetch("/api/report/weekly");

            var html = '<div id="report-content">';

            html += '<div style="text-align:center;margin-bottom:20px;">';
            html += '<h4 style="font-size:18px;font-weight:600;">📊 本周学习报告</h4>';
            html += '<p style="font-size:12px;color:var(--color-text-muted);">最近 7 天学习数据统计</p>';
            html += '</div>';

            html += '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px;">';
            html += buildStatCard("📝", data.review_count || 0, "复习次数");
            html += buildStatCard("🌱", data.new_knowledge_count || 0, "新增知识点");
            html += buildStatCard("🎯", Math.round((data.avg_accuracy || 0) * 100) + "%", "平均正确率");
            var totalMasteryPct = Math.round((data.total_mastery || 0) * 100);
            html += buildStatCard("📈", totalMasteryPct + "%", "总掌握度");
            html += '</div>';

            var timeline = data.daily_timeline || data.mastery_timeline || [];
            if (timeline.length > 0) {
                html += '<div style="margin-bottom:20px;">';
                html += '<h5 style="font-size:14px;font-weight:600;margin-bottom:8px;">📈 每日学习趋势</h5>';
                html += '<div style="background:var(--color-bg-card);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:16px;">';
                html += '<canvas id="report-chart" style="width:100%;height:240px;"></canvas>';
                html += '</div></div>';
            }

            if (data.weak_points && data.weak_points.length > 0) {
                html += '<div style="margin-bottom:16px;">';
                html += '<h5 style="font-size:14px;font-weight:600;margin-bottom:8px;">⚠️ 薄弱知识点 TOP5（已复习过但掌握度低）</h5>';
                data.weak_points.forEach(function (w) {
                    var pct = Math.round((w.mastery || 0) * 100);
                    var barColor = pct < 30 ? "var(--color-error)" : pct < 60 ? "var(--color-warning)" : "var(--color-primary)";
                    html +=
                        '<div style="margin-bottom:6px;">' +
                        '<div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:2px;">' +
                        '<span>' + escapeHtml(w.title) + ' <small>(' + escapeHtml(w.type || "") + ')</small></span>' +
                        '<span style="color:var(--color-text-muted);">' + pct + '%</span>' +
                        '</div>' +
                        '<div style="width:100%;height:6px;background:var(--color-border);border-radius:3px;">' +
                        '<div style="width:' + pct + '%;height:100%;background:' + barColor + ';border-radius:3px;"></div>' +
                        '</div></div>';
                });
                html += '</div>';
            }

            if (data.recommended_reviews && data.recommended_reviews.length > 0) {
                html += '<div style="margin-bottom:12px;">';
                html += '<h5 style="font-size:14px;font-weight:600;margin-bottom:8px;">📅 待复习知识点</h5>';
                data.recommended_reviews.slice(0, 5).forEach(function (r) {
                    html += '<div style="font-size:12px;color:var(--color-text-secondary);padding:4px 0;border-bottom:1px solid var(--color-border);">· ' + escapeHtml(r.title) + '</div>';
                });
                html += '</div>';
            }

            html += '</div>';

            body.innerHTML = html;

            if (timeline.length > 0 && typeof Chart !== "undefined") {
                renderChart(timeline);
            } else if (timeline.length > 0) {
                var chartCanvas = document.getElementById("report-chart");
                if (chartCanvas) {
                    var ctx = chartCanvas.getContext("2d");
                    renderSimpleChart(ctx, timeline, chartCanvas);
                }
            }

            if (footer) {
                footer.style.display = "flex";
                footer.style.justifyContent = "center";
                footer.style.gap = "10px";
                footer.innerHTML =
                    '<button class="btn btn-primary" id="report-export-btn">📸 导出图片</button>' +
                    '<button class="btn btn-secondary" id="report-qq-btn">💬 分享到QQ</button>' +
                    '<button class="btn btn-secondary" id="report-close-btn">关闭</button>';

                document.getElementById("report-export-btn").addEventListener("click", exportAsImage);
                document.getElementById("report-qq-btn").addEventListener("click", shareToQQ);
                document.getElementById("report-close-btn").addEventListener("click", function () { close(); });
            }
        } catch (e) {
            body.innerHTML = '<div style="text-align:center;color:var(--color-error);padding:20px;">❌ 加载报告失败: ' + escapeHtml(e.message) + '</div>';
        }
    }

    function buildStatCard(icon, value, label) {
        return '<div style="text-align:center;padding:12px;background:var(--color-bg-subtle);border-radius:var(--radius-md);border:1px solid var(--color-border);">' +
            '<div style="font-size:20px;margin-bottom:4px;">' + icon + '</div>' +
            '<div style="font-size:22px;font-weight:700;color:var(--color-primary);">' + value + '</div>' +
            '<div style="font-size:11px;color:var(--color-text-muted);">' + label + '</div>' +
            '</div>';
    }

    function renderChart(timeline) {
        var canvas = document.getElementById("report-chart");
        if (!canvas) return;

        var hasMastery = timeline[0].avg_mastery !== undefined;
        var hasWatering = timeline[0].watering_count !== undefined;

        var datasets = [{
            label: "平均得分",
            data: timeline.map(function (t) { return Math.round((t.avg_score || 0) * 100); }),
            borderColor: "#4A7C59",
            backgroundColor: "rgba(74, 124, 89, 0.1)",
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            pointBackgroundColor: "#4A7C59",
        }];

        if (hasMastery) {
            datasets.push({
                label: "掌握度",
                data: timeline.map(function (t) { return Math.round((t.avg_mastery || 0) * 100); }),
                borderColor: "#5B8FC4",
                backgroundColor: "rgba(91, 143, 196, 0.1)",
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: "#5B8FC4",
                borderDash: [5, 5],
            });
        }

        if (hasWatering) {
            datasets.push({
                label: "浇水次数",
                data: timeline.map(function (t) { return t.watering_count || 0; }),
                borderColor: "#D4A843",
                backgroundColor: "rgba(212, 168, 67, 0.1)",
                fill: false,
                tension: 0.3,
                pointRadius: 3,
                pointBackgroundColor: "#D4A843",
                yAxisID: "y1",
            });
        }

        var scales = {
            y: {
                beginAtZero: true,
                max: 100,
                ticks: { callback: function (v) { return v + "%"; } },
            },
        };

        if (hasWatering) {
            scales.y1 = {
                position: "right",
                beginAtZero: true,
                grid: { display: false },
            };
        }

        new Chart(canvas, {
            type: "line",
            data: {
                labels: timeline.map(function (t) { return t.date; }),
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: scales,
                plugins: {
                    legend: { position: "bottom", labels: { font: { size: 11 } } },
                },
            },
        });
    }

    function renderSimpleChart(ctx, timeline, canvas) {
        var w = canvas.width = canvas.offsetWidth * 2;
        var h = canvas.height = 400;
        var padding = 40;
        var chartW = w - padding * 2;
        var chartH = h - padding * 2;

        ctx.fillStyle = "#FFFFFF";
        ctx.fillRect(0, 0, w, h);

        var maxVal = 100;
        var stepX = chartW / Math.max(1, timeline.length - 1);

        ctx.strokeStyle = "#4A7C59";
        ctx.lineWidth = 3;
        ctx.beginPath();
        timeline.forEach(function (t, i) {
            var x = padding + i * stepX;
            var y = padding + chartH - (t.avg_score * chartH);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();

        ctx.fillStyle = "#6B7C6A";
        ctx.font = "12px Inter, sans-serif";
        ctx.textAlign = "center";
        timeline.forEach(function (t, i) {
            var x = padding + i * stepX;
            ctx.fillText(t.date, x, h - 10);
        });
    }

    async function exportAsImage() {
        var content = document.getElementById("report-content");
        if (!content) {
            showToast("报告内容未找到", "warning");
            return;
        }

        if (typeof html2canvas === "undefined") {
            showToast("html2canvas 未加载，请检查网络", "error");
            return;
        }

        showToast("正在生成图片...", "info");
        try {
            var canvas = await html2canvas(content, {
                backgroundColor: "#FFFFFF",
                scale: 2,
                useCORS: true,
                logging: false,
            });

            canvas.toBlob(function (blob) {
                var a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "learning_report_" + new Date().toISOString().slice(0, 10) + ".png";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                showToast("💾 报告图片已开始下载", "success");
            }, "image/png");
        } catch (e) {
            showToast("导出失败: " + e.message, "error");
        }
    }

    function shareToQQ() {
        var title = encodeURIComponent("我的AI知识农场学习周报");
        var summary = encodeURIComponent("快来看看我本周的学习成果吧~");
        var url = encodeURIComponent(window.location.href);
        var shareUrl =
            "https://connect.qq.com/widget/shareqq/index.html" +
            "?url=" + url +
            "&title=" + title +
            "&summary=" + summary;
        window.open(shareUrl, "_blank", "width=600,height=500");
    }

    function setup() {
        var closeBtn = document.getElementById("report-modal-close");
        var modal = document.getElementById("report-modal");
        if (closeBtn) {
            closeBtn.addEventListener("click", function () { close(); });
        }
        if (modal) {
            modal.addEventListener("click", function (e) {
                if (e.target === modal) close();
            });
        }
    }

    return {
        open: open,
        close: close,
        setup: setup,
    };
})();

document.addEventListener("DOMContentLoaded", function () {
    reportModule.setup();
});
