"use strict";

var examModule = (function () {
    var API_BASE = window.API_BASE_URL || "";
    var currentSession = null;
    var currentQuestions = [];
    var currentAnswers = [];
    var currentIndex = 0;
    var timerInterval = null;
    var elapsedSeconds = 0;

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
        var modal = document.getElementById("exam-modal");
        if (modal) {
            modal.style.display = "block";
            modal.setAttribute("aria-hidden", "false");
        }
        showSetupView();
    }

    function close() {
        var modal = document.getElementById("exam-modal");
        if (modal) {
            modal.style.display = "none";
            modal.setAttribute("aria-hidden", "true");
        }
        if (typeof _restoreFocus === 'function') _restoreFocus();
        stopTimer();
        currentSession = null;
        currentQuestions = [];
        currentAnswers = [];
        currentIndex = 0;
    }

    async function showSetupView() {
        var body = document.getElementById("exam-modal-body");
        var footer = document.getElementById("exam-modal-footer");
        if (!body) return;

        stopTimer();
        body.innerHTML = '<div style="text-align:center;padding:20px;color:var(--color-text-muted);">⏳ 加载知识点标签...</div>';
        if (footer) footer.style.display = "none";

        try {
            var topicData = await apiFetch("/api/available_topics");
            var topics = topicData.available_topics || [];

            var itemsData = await apiFetch("/api/farm");
            var totalItems = (itemsData.plots || []).filter(function (p) { return p.item_id; }).length;

            var html = '<div style="margin-bottom:16px;">';
            html += '<h4 style="font-size:16px;font-weight:600;margin-bottom:12px;">📝 考试设置</h4>';

            html += '<div style="margin-bottom:16px;">';
            html += '<label style="display:block;font-size:13px;color:var(--color-text-secondary);margin-bottom:6px;">题目数量</label>';
            html += '<div style="display:flex;gap:8px;flex-wrap:wrap;">';
            [3, 5, 10].forEach(function (n) {
                var selected = n === 5 ? 'background:var(--color-primary);color:#FFFFFF;border-color:var(--color-primary);' : '';
                html += '<button class="exam-count-btn" data-count="' + n + '" style="padding:6px 16px;border-radius:20px;border:1px solid var(--color-border);cursor:pointer;font-size:13px;' + selected + '">' + n + ' 题</button>';
            });
            html += '</div></div>';

            html += '<div style="margin-bottom:16px;">';
            html += '<label style="display:block;font-size:13px;color:var(--color-text-secondary);margin-bottom:6px;">选择专题标签（可选，不选则随机出题）</label>';
            html += '<div style="display:flex;gap:8px;flex-wrap:wrap;">';
            topics.forEach(function (t) {
                html += '<button class="exam-tag-btn" data-tag="' + escapeHtml(t.tag) + '" style="padding:4px 12px;border-radius:16px;border:1px solid var(--color-border);cursor:pointer;font-size:12px;background:var(--color-bg-card);">' + escapeHtml(t.tag) + ' (' + t.count + ')</button>';
            });
            html += '</div></div>';

            html += '<div style="margin-bottom:12px;">';
            html += '<label style="display:flex;align-items:center;gap:8px;cursor:pointer;font-size:13px;">';
            html += '<input type="checkbox" id="exam-adaptive" style="accent-color:var(--color-primary);"> 启用智能难度自适应';
            html += '</label></div>';

            html += '<p style="font-size:12px;color:var(--color-text-muted);">当前共有 ' + totalItems + ' 个知识点可出题</p>';
            html += '</div>';

            body.innerHTML = html;

            body.querySelectorAll(".exam-count-btn").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    body.querySelectorAll(".exam-count-btn").forEach(function (b) {
                        b.style.background = "";
                        b.style.color = "";
                        b.style.borderColor = "var(--color-border)";
                    });
                    btn.style.background = "var(--color-primary)";
                    btn.style.color = "#FFFFFF";
                    btn.style.borderColor = "var(--color-primary)";
                });
            });

            body.querySelectorAll(".exam-tag-btn").forEach(function (btn) {
                btn.addEventListener("click", function () {
                    var isActive = btn.style.background !== "" && btn.style.background !== "var(--color-bg-card)";
                    if (isActive) {
                        btn.style.background = "var(--color-bg-card)";
                        btn.style.color = "";
                        btn.style.borderColor = "var(--color-border)";
                    } else {
                        btn.style.background = "var(--color-primary)";
                        btn.style.color = "#FFFFFF";
                        btn.style.borderColor = "var(--color-primary)";
                    }
                });
            });

            if (footer) {
                footer.style.display = "flex";
                footer.innerHTML = '<button class="btn btn-primary" id="exam-start-btn" style="margin:0 auto;">🚀 开始考试</button>';
                document.getElementById("exam-start-btn").addEventListener("click", startExam);
            }
        } catch (e) {
            body.innerHTML = '<div style="text-align:center;color:var(--color-error);padding:20px;">❌ 加载失败: ' + escapeHtml(e.message) + '</div>';
        }
    }

    async function startExam() {
        var body = document.getElementById("exam-modal-body");
        var footer = document.getElementById("exam-modal-footer");

        var countBtn = body.querySelector(".exam-count-btn[style*='var(--color-primary)']");
        var count = countBtn ? parseInt(countBtn.getAttribute("data-count")) : 5;

        var tags = [];
        body.querySelectorAll(".exam-tag-btn").forEach(function (btn) {
            if (btn.style.background === "var(--color-primary)") {
                tags.push(btn.getAttribute("data-tag"));
            }
        });

        var useAdaptive = document.getElementById("exam-adaptive") ? document.getElementById("exam-adaptive").checked : false;

        if (footer) {
            footer.innerHTML = '<div style="text-align:center;width:100%;color:var(--color-text-muted);">⏳ 正在生成题目...</div>';
        }

        try {
            var data = await apiFetch("/api/exam/start", {
                method: "POST",
                body: JSON.stringify({ tags: tags, count: count, use_adaptive: useAdaptive }),
            });

            currentSession = data.session_id;
            currentQuestions = data.questions || [];
            currentAnswers = [];
            currentIndex = 0;
            elapsedSeconds = 0;

            startTimer();
            showQuestion();
        } catch (e) {
            showToast("开始考试失败: " + e.message, "error");
            showSetupView();
        }
    }

    function startTimer() {
        stopTimer();
        timerInterval = setInterval(function () {
            elapsedSeconds++;
            var timerEl = document.getElementById("exam-timer");
            if (timerEl) {
                var m = Math.floor(elapsedSeconds / 60);
                var s = elapsedSeconds % 60;
                timerEl.textContent = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;
            }
        }, 1000);
    }

    function stopTimer() {
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
    }

    function showQuestion() {
        var body = document.getElementById("exam-modal-body");
        var footer = document.getElementById("exam-modal-footer");
        if (!body || currentIndex >= currentQuestions.length) return;

        var q = currentQuestions[currentIndex];
        var progress = ((currentIndex) / currentQuestions.length * 100).toFixed(0);

        var html =
            '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">' +
            '<span style="font-size:13px;color:var(--color-text-secondary);">第 ' + (currentIndex + 1) + ' / ' + currentQuestions.length + ' 题</span>' +
            '<span id="exam-timer" style="font-family:var(--font-display);font-size:14px;font-weight:600;color:var(--color-primary);">00:00</span>' +
            '</div>' +
            '<div style="width:100%;height:4px;background:var(--color-border);border-radius:2px;margin-bottom:16px;">' +
            '<div style="width:' + progress + '%;height:100%;background:var(--color-primary);border-radius:2px;transition:width 0.3s;"></div>' +
            '</div>' +
            '<div style="background:var(--color-bg-subtle);border-radius:var(--radius-md);padding:14px;margin-bottom:16px;border:1px solid var(--color-border);">' +
            '<div style="font-size:12px;color:var(--color-text-muted);margin-bottom:6px;">' + escapeHtml(q.title) + ' (' + escapeHtml(q.type || "concept") + ')</div>' +
            '<p style="font-size:15px;line-height:1.7;color:var(--color-text-primary);">' + escapeHtml(q.text) + '</p>' +
            '</div>' +
            '<label style="display:block;font-size:13px;color:var(--color-text-secondary);margin-bottom:6px;">你的回答：</label>' +
            '<textarea id="exam-answer-input" class="answer-textarea" rows="4" style="width:100%;padding:10px 12px;border:1px solid var(--color-border);border-radius:var(--radius-md);font-size:14px;resize:vertical;" placeholder="请输入你的答案..."></textarea>';

        body.innerHTML = html;

        var input = document.getElementById("exam-answer-input");
        if (input) input.focus();

        if (footer) {
            footer.style.display = "flex";
            footer.style.justifyContent = "space-between";
            footer.innerHTML = '';

            if (currentIndex > 0) {
                var prevBtn = document.createElement("button");
                prevBtn.className = "btn btn-secondary";
                prevBtn.textContent = "← 上一题";
                prevBtn.addEventListener("click", function () { prevQuestion(); });
                footer.appendChild(prevBtn);
            }

            var spacer = document.createElement("div");
            spacer.style.flex = "1";
            footer.appendChild(spacer);

            var nextBtnText = currentIndex < currentQuestions.length - 1 ? "下一题 →" : "📝 提交考试";
            var nextBtn = document.createElement("button");
            nextBtn.className = "btn btn-primary";
            nextBtn.textContent = nextBtnText;
            nextBtn.addEventListener("click", function () { nextQuestion(); });
            footer.appendChild(nextBtn);
        }
    }

    function nextQuestion() {
        var input = document.getElementById("exam-answer-input");
        var answer = input ? input.value.trim() : "";

        if (!answer) {
            showToast("请输入答案后再继续", "warning");
            return;
        }

        currentAnswers[currentIndex] = {
            question_id: currentQuestions[currentIndex].id,
            user_answer: answer,
        };

        currentIndex++;

        if (currentIndex >= currentQuestions.length) {
            submitExam();
        } else {
            showQuestion();
        }
    }

    function prevQuestion() {
        var input = document.getElementById("exam-answer-input");
        if (input) {
            currentAnswers[currentIndex] = {
                question_id: currentQuestions[currentIndex].id,
                user_answer: input.value.trim(),
            };
        }
        currentIndex = Math.max(0, currentIndex - 1);
        showQuestion();

        var restoreInput = document.getElementById("exam-answer-input");
        if (restoreInput && currentAnswers[currentIndex]) {
            restoreInput.value = currentAnswers[currentIndex].user_answer || "";
        }
    }

    async function submitExam() {
        stopTimer();
        var body = document.getElementById("exam-modal-body");
        var footer = document.getElementById("exam-modal-footer");

        if (body) {
            body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--color-text-muted);">⏳ AI正在评分，请稍候...</div>';
        }
        if (footer) footer.style.display = "none";

        try {
            var data = await apiFetch("/api/exam/submit", {
                method: "POST",
                body: JSON.stringify({
                    session_id: currentSession,
                    answers: currentAnswers.filter(Boolean),
                }),
            });

            showResult(data);
        } catch (e) {
            showToast("提交失败: " + e.message, "error");
        }
    }

    async function showResult(submitData) {
        var body = document.getElementById("exam-modal-body");
        var footer = document.getElementById("exam-modal-footer");

        try {
            var result = await apiFetch("/api/exam/result/" + currentSession);
            var rate = Math.round(result.correct_rate * 100);
            var avg = Math.round(result.avg_score * 100);
            var emoji = rate >= 80 ? "🎉" : rate >= 60 ? "👍" : rate >= 40 ? "🤔" : "💪";
            var color = rate >= 70 ? "var(--color-primary)" : rate >= 40 ? "var(--color-warning)" : "var(--color-error)";

            var m = Math.floor(elapsedSeconds / 60);
            var s = elapsedSeconds % 60;
            var timeStr = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s;

            var html =
                '<div style="text-align:center;margin-bottom:20px;">' +
                '<div style="font-size:48px;margin-bottom:8px;">' + emoji + '</div>' +
                '<div style="font-size:28px;font-weight:700;color:' + color + ';">' + rate + '%</div>' +
                '<div style="font-size:13px;color:var(--color-text-muted);margin-top:4px;">正确率 · 平均分 ' + avg + '% · 用时 ' + timeStr + '</div>' +
                '</div>';

            html += '<div style="display:flex;gap:12px;margin-bottom:16px;justify-content:center;">';
            html += '<div style="text-align:center;padding:10px 16px;background:var(--color-bg-subtle);border-radius:var(--radius-md);">';
            html += '<div style="font-size:20px;font-weight:600;color:var(--color-primary);">' + result.correct_count + '/' + result.total_questions + '</div>';
            html += '<div style="font-size:11px;color:var(--color-text-muted);">正确题数</div></div>';
            html += '<div style="text-align:center;padding:10px 16px;background:var(--color-bg-subtle);border-radius:var(--radius-md);">';
            html += '<div style="font-size:20px;font-weight:600;color:var(--color-warning);">' + timeStr + '</div>';
            html += '<div style="font-size:11px;color:var(--color-text-muted);">总用时</div></div>';
            html += '</div>';

            if (result.detail && result.detail.length > 0) {
                html += '<div style="margin-bottom:12px;"><strong style="font-size:14px;">📋 逐题详情</strong></div>';
                result.detail.forEach(function (d, i) {
                    var scorePct = Math.round(d.score * 100);
                    var scoreColor = scorePct >= 60 ? "var(--color-primary)" : "var(--color-error)";
                    var icon = d.is_correct ? "✅" : "❌";
                    html +=
                        '<div style="padding:10px;margin-bottom:8px;border:1px solid var(--color-border);border-radius:var(--radius-md);border-left:3px solid ' + scoreColor + ';">' +
                        '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">' +
                        '<span style="font-size:13px;font-weight:500;">' + icon + ' ' + escapeHtml(d.title) + '</span>' +
                        '<span style="font-size:14px;font-weight:600;color:' + scoreColor + ';">' + scorePct + '%</span>' +
                        '</div>' +
                        '<div style="font-size:12px;color:var(--color-text-muted);max-height:60px;overflow:hidden;">' +
                        '你的回答: ' + escapeHtml(d.user_answer || "未作答").substring(0, 80) +
                        '</div></div>';
                });
            }

            if (result.weak_points && result.weak_points.length > 0) {
                html += '<div style="margin-top:12px;padding:12px;background:#FFF3E0;border-radius:var(--radius-md);border:1px solid #FFE0B2;">';
                html += '<strong style="font-size:13px;">⚠️ 薄弱知识点</strong>';
                result.weak_points.forEach(function (w) {
                    html += '<div style="font-size:12px;color:var(--color-text-secondary);margin-top:4px;">· ' + escapeHtml(w.title) + ' (得分 ' + Math.round(w.score * 100) + '%)</div>';
                });
                html += '</div>';
            }

            body.innerHTML = html;

            if (footer) {
                footer.style.display = "flex";
                footer.style.justifyContent = "center";
                footer.style.gap = "10px";
                footer.innerHTML =
                    '<button class="btn btn-primary" id="exam-retry-btn">🔄 再考一次</button>' +
                    '<button class="btn btn-secondary" id="exam-close-btn">关闭</button>';

                document.getElementById("exam-retry-btn").addEventListener("click", function () { showSetupView(); });
                document.getElementById("exam-close-btn").addEventListener("click", function () { close(); });
            }
        } catch (e) {
            if (body) {
                body.innerHTML = '<div style="text-align:center;color:var(--color-error);padding:20px;">❌ 加载结果失败: ' + escapeHtml(e.message) + '</div>';
            }
        }
    }

    function setup() {
        var closeBtn = document.getElementById("exam-modal-close");
        var modal = document.getElementById("exam-modal");
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
    examModule.setup();
});
