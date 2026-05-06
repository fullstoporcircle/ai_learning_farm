"use strict";

const API_BASE_URL = window.API_BASE_URL || "http://localhost:5000";

const elements = {
    farmGrid: document.getElementById("farm-grid"),
    textInput: document.getElementById("text-input"),
    extractBtn: document.getElementById("extract-btn"),
    resultPanel: document.getElementById("result-panel"),
    resultContent: document.getElementById("result-content"),
    backpackList: document.getElementById("backpack-list"),
    backpackCount: document.getElementById("backpack-count"),
    refreshBtn: document.getElementById("refresh-btn"),
    resetBtn: document.getElementById("reset-btn"),
    farmStats: document.getElementById("farm-stats"),
    modal: document.getElementById("water-modal"),
    modalTitle: document.getElementById("modal-title"),
    modalBody: document.getElementById("modal-body"),
    modalFooter: document.getElementById("modal-footer"),
    modalClose: document.getElementById("modal-close"),
    clipboardBtn: document.getElementById("clipboard-btn"),
    autoPlantBtn: document.getElementById("auto-plant-btn"),
    waterAllBtn: document.getElementById("water-all-btn"),
    reviewPanel: document.getElementById("review-panel"),
    reviewList: document.getElementById("review-list"),
    shortcutHint: document.getElementById("shortcut-hint"),
    sidebarToggle: document.getElementById("sidebar-toggle"),
    sidebar: document.getElementById("sidebar"),
};

const SVG_ICONS = {
    seed: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#8D6E63" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="14" rx="5" ry="6"/><path d="M12 8V2"/><path d="M9 5l3-3 3 3"/></svg>',
    seedling: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4A7C59" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22V8"/><path d="M12 8c-4 0-6-3-6-6 4 0 6 3 6 6z"/><path d="M12 12c4 0 6-3 6-6-4 0-6 3-6 6z"/></svg>',
    flowering: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4A7C59" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22V10"/><circle cx="12" cy="7" r="3"/><path d="M12 4V2"/><path d="M8 5.5L6.5 4"/><path d="M16 5.5L17.5 4"/><path d="M9 10l-3 1"/><path d="M15 10l3 1"/></svg>',
    fruiting: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4A7C59" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22V10"/><circle cx="9" cy="10" r="3"/><circle cx="15" cy="10" r="3"/><path d="M12 7V2"/><path d="M10 4l2-2 2 2"/></svg>',
    harvest: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4A7C59" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6h6l-5 4 2 6-6-4-6 4 2-6-5-4h6z"/></svg>',
    empty: '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#C8C8C8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="4 3"/></svg>',
};

const STAGES = {
    SEED: { min: 0, class: "plot-stage-seed", icon: SVG_ICONS.seed },
    SEEDLING: { min: 20, class: "plot-stage-seedling", icon: SVG_ICONS.seedling },
    FLOWERING: { min: 50, class: "plot-stage-flowering", icon: SVG_ICONS.flowering },
    FRUITING: { min: 80, class: "plot-stage-fruiting", icon: SVG_ICONS.fruiting },
    HARVEST: { min: 100, class: "plot-stage-fruiting", icon: SVG_ICONS.harvest },
};

let farmData = [];
let currentLearning = null;
let backpackData = [];

/* ============ 工具函数 ============ */
function escapeHtml(str) {
    if (!str) return "";
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

function renderLatex(el) {
    if (typeof renderMathInElement === "function" && el) {
        try {
            renderMathInElement(el, {
                delimiters: [
                    {left: "$$", right: "$$", display: true},
                    {left: "$", right: "$", display: false},
                ],
                throwOnError: false,
            });
        } catch (_) {}
    }
}

function showToast(msg, type) {
    type = type || "info";
    const existing = document.querySelector(".toast");
    if (existing) existing.remove();

    const toast = document.createElement("div");
    toast.className = "toast toast-" + type;
    toast.textContent = msg;
    toast.setAttribute("role", "status");
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add("show");
        setTimeout(() => {
            toast.classList.remove("show");
            setTimeout(() => toast.remove(), 300);
        }, 2800);
    });
}

async function apiFetch(url, options) {
    options = options || {};
    const headers = options.headers || {};
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
    try {
        const res = await fetch(API_BASE_URL + url, { ...options, headers });
        if (!res.ok) {
            const errText = await res.text();
            var errMsg = "HTTP " + res.status;
            try {
                var errJson = JSON.parse(errText);
                errMsg += ": " + (errJson.error || errText);
                if (errJson.debug) {
                    errMsg += "（总计" + errJson.debug.total + "块，已用" + errJson.debug.occupied + "块，空闲" + errJson.debug.empty + "块）";
                }
            } catch (_) {
                errMsg += ": " + errText;
            }
            throw new Error(errMsg);
        }
        return await res.json();
    } catch (e) {
        console.error("API错误 [" + url + "]:", e);
        throw e;
    }
}

function setLoading(el, loading) {
    if (loading) {
        el.disabled = true;
        el.setAttribute("data-original-text", el.textContent);
        el.textContent = "⏳ 处理中...";
    } else {
        el.disabled = false;
        const original = el.getAttribute("data-original-text");
        if (original) el.textContent = original;
    }
}

/* ============ 动画辅助 ============ */
function showWaterAnimation(plotEl) {
    const rect = plotEl.getBoundingClientRect();
    const dropSvg = '<svg width="20" height="20" viewBox="0 0 24 24" fill="#64B5F6" stroke="none"><path d="M12 2C12 2 5 11 5 15.5C5 19.09 8.13 22 12 22C15.87 22 19 19.09 19 15.5C19 11 12 2 12 2Z"/></svg>';
    for (let i = 0; i < 3; i++) {
        const el = document.createElement("div");
        el.className = "water-animation";
        el.innerHTML = '<span class="drop">' + dropSvg + "</span>";
        el.style.left = (rect.left + rect.width / 2 + (i - 1) * 20 - 10) + "px";
        el.style.top = (rect.top + 10) + "px";
        el.style.animationDelay = (i * 0.15) + "s";
        document.body.appendChild(el);
        setTimeout(function () { el.remove(); }, 1500);
    }
}

function showHarvestAnimation(plotEl) {
    plotEl.classList.add("harvesting");
    const rect = plotEl.getBoundingClientRect();
    const coin = document.createElement("div");
    coin.className = "coin-float";
    coin.textContent = "+50";
    coin.style.left = (rect.left + rect.width / 2 - 20) + "px";
    coin.style.top = (rect.top - 10) + "px";
    document.body.appendChild(coin);
    setTimeout(function () {
        coin.remove();
        plotEl.classList.remove("harvesting");
    }, 1600);
}

function showErrorFlash(plotEl) {
    plotEl.classList.add("answer-wrong");
    setTimeout(function () { plotEl.classList.remove("answer-wrong"); }, 1200);
}

/* ============ 键盘快捷键 ============ */
function setupKeyboardShortcuts() {
    function showHint() {
        if (elements.shortcutHint) {
            elements.shortcutHint.classList.add("show");
            clearTimeout(elements.shortcutHint._timeout);
            elements.shortcutHint._timeout = setTimeout(function () {
                elements.shortcutHint.classList.remove("show");
            }, 4000);
        }
    }
    showHint();

    document.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
            var submitBtn = document.querySelector(".modal-footer .btn-primary");
            var verifyBtn = document.getElementById("verify-btn");
            var textareaFocused = document.activeElement && document.activeElement.tagName === "TEXTAREA";

            if (verifyBtn && textareaFocused) {
                e.preventDefault();
                verifyBtn.click();
                return;
            }
            if (submitBtn && !textareaFocused) {
                var finishBtn = document.getElementById("finish-btn");
                var harvestBtn = document.getElementById("harvest-btn");
                var closeWaterBtn = document.getElementById("close-water-btn");
                if (finishBtn && finishBtn.style.display !== "none") {
                    e.preventDefault();
                    finishBtn.click();
                } else if (harvestBtn && harvestBtn.style.display !== "none") {
                    e.preventDefault();
                    harvestBtn.click();
                } else if (closeWaterBtn && closeWaterBtn.style.display !== "none") {
                    e.preventDefault();
                    closeWaterBtn.click();
                } else {
                    e.preventDefault();
                    submitBtn.click();
                }
                return;
            }
        }
        if (e.key === "Escape") {
            if (elements.modal && elements.modal.style.display === "block") {
                var closeBtn = elements.modalClose;
                if (closeBtn) closeBtn.click();
                return;
            }
            var bpPopup = document.querySelector(".backpack-popup");
            if (bpPopup) {
                bpPopup.remove();
                return;
            }
        }
    });
}

/* ============ 渲染农场 ============ */
function renderFarm(data) {
    farmData = data || farmData;
    if (!elements.farmGrid) return;
    elements.farmGrid.innerHTML = "";

    farmData.forEach(function (plot) {
        var plotEl = document.createElement("div");
        plotEl.className = "plot";
        plotEl.dataset.plotId = plot.id;

        if (!plot.item_id) {
            plotEl.classList.add("empty");
            plotEl.innerHTML =
                '<div class="plot-icon">' + SVG_ICONS.empty + "</div>" +
                '<div class="plot-label">空地</div>';
        } else {
            plotEl.classList.add("planted-" + (plot.type || "concept"));
            var stage = getStage(plot.growth_value || 0);

            if (plot.growth_value >= 100) {
                plotEl.classList.add("harvestable");
            }

            plotEl.classList.add(stage.class);

            plotEl.innerHTML =
                '<div class="plot-icon">' + stage.icon + "</div>" +
                '<div class="plot-name">' + escapeHtml(plot.title || "??") + "</div>" +
                '<div class="plot-progress">' +
                '<div class="plot-progress-bar" style="width:' + (plot.growth_value || 0) + '%"></div>' +
                "</div>" +
                '<div class="plot-badges">' +
                (plot.is_paired
                    ? '<span class="badge badge-paired">配对: ' + escapeHtml(plot.paired_with || "") + "</span>"
                    : "") +
                (plot.growth_value >= 100
                    ? '<span class="badge badge-harvest">🌟 可收获</span>'
                    : "") +
                "</div>";

            if (plot.mastery !== undefined) {
                var masteryPercent = Math.round((plot.mastery || 0) * 100);
                var masteryBar = document.createElement("div");
                masteryBar.className = "plot-mastery-bar";
                masteryBar.innerHTML =
                    '<span class="mastery-label">掌握度</span>' +
                    '<div class="mastery-track">' +
                    '<div class="mastery-fill" style="width:' + masteryPercent + '%"></div>' +
                    "</div>" +
                    '<span class="mastery-value">' + masteryPercent + "%</span>";
                plotEl.appendChild(masteryBar);
            }
        }

        plotEl.addEventListener("click", function (e) {
            handlePlotClick(plot, plotEl, e);
        });
        elements.farmGrid.appendChild(plotEl);
    });

    updateFarmStats();
}

function getStage(growth) {
    if (growth >= 100) return STAGES.HARVEST;
    if (growth >= 80) return STAGES.FRUITING;
    if (growth >= 50) return STAGES.FLOWERING;
    if (growth >= 20) return STAGES.SEEDLING;
    return STAGES.SEED;
}

function updateFarmStats() {
    if (!elements.farmStats) return;
    var empty = 0, growing = 0, harvestable = 0, total = farmData.length;
    farmData.forEach(function (p) {
        if (!p.item_id) empty++;
        else if (p.growth_value >= 100) harvestable++;
        else growing++;
    });
    elements.farmStats.innerHTML =
        "总计 " + total + " 块 | 空地 " + empty +
        " | 生长中 " + growing + " | 可收获 " + harvestable;
}

/* ============ 地块点击 ============ */
function handlePlotClick(plot, plotEl, event) {
    if (plot.growth_value >= 100) {
        harvestPlot(plot, plotEl);
        return;
    }

    if (plot.item_id) {
        showKnowledgeDetail(plot);
        return;
    }

    showBackpackPopup(plot, plotEl, event);
}

/* ============ 背包悬浮窗 ============ */
function showBackpackPopup(plot, plotEl, event) {
    var existing = document.querySelector(".backpack-popup");
    if (existing) existing.remove();

    if (!backpackData || backpackData.length === 0) {
        showToast("背包中没有种子，请先提取知识点！", "warning");
        return;
    }

    var popup = document.createElement("div");
    popup.className = "backpack-popup";

    var titleEl = document.createElement("div");
    titleEl.style.cssText =
        "padding:8px 12px;font-family:'Patrick Hand',cursive;font-size:16px;" +
        "color:#5D4037;border-bottom:1px solid var(--color-soil);text-align:center;";
    titleEl.textContent = "🎒 选择种子种植";
    popup.appendChild(titleEl);

    backpackData.forEach(function (seed) {
        var item = document.createElement("div");
        item.className = "backpack-item";
        item.style.cssText =
            "padding:10px 12px;cursor:pointer;border-radius:8px;margin:4px;" +
            "background:linear-gradient(180deg,#FFFFFF,#F1F8E9);";
        item.innerHTML =
            "<strong style='font-family:\"Patrick Hand\",cursive;font-size:14px;'>" +
            escapeHtml(seed.title) +
            "</strong>" +
            "<span style='float:right;font-size:12px;color:#8D6E63;'>x" +
            (seed.quantity || 1) +
            "</span>" +
            "<br><small style='color:#8D6E63;'>" +
            escapeHtml(seed.type || "") +
            "</small>";

        item.addEventListener("click", function (e) {
            e.stopPropagation();
            plantSeed(plot, seed, plotEl);
            popup.remove();
        });
        popup.appendChild(item);
    });

    var rect = plotEl.getBoundingClientRect();
    popup.style.position = "fixed";
    popup.style.top = (rect.bottom + 8) + "px";
    popup.style.left = (rect.left) + "px";

    document.body.appendChild(popup);

    var onDocClick = function (e) {
        if (!popup.contains(e.target) && e.target !== plotEl) {
            popup.remove();
            document.removeEventListener("click", onDocClick);
        }
    };
    setTimeout(function () {
        document.addEventListener("click", onDocClick);
    }, 10);
}

async function plantSeed(plot, seed, plotEl) {
    try {
        await apiFetch("/api/plant", {
            method: "POST",
            body: JSON.stringify({
                plot_id: plot.id,
                item_id: seed.id || seed.item_id,
            }),
        });
        showToast("🌱 " + escapeHtml(seed.title) + " 种植成功！", "success");
        plotEl.classList.remove("empty");
        await loadFarm();
        await loadBackpack();

        var bpPopup = document.querySelector(".backpack-popup");
        if (bpPopup) bpPopup.remove();
    } catch (e) {
        showToast("种植失败: " + e.message, "error");
    }
}

/* ============ 浇水流程 ============ */
async function startWatering(plot) {
    try {
        var data = await apiFetch("/api/water", {
            method: "POST",
            body: JSON.stringify({ plot_id: plot.id }),
        });
        currentLearning = { plot: plot, data: data };
        openModal();
        renderLearningContent(data, plot);
    } catch (e) {
        showToast("浇水失败: " + e.message, "error");
    }
}

function renderLearningContent(data, plot) {
    if (!elements.modalTitle || !elements.modalBody || !elements.modalFooter) return;

    elements.modalTitle.textContent = "💧 知识灌溉 - " + escapeHtml(plot.title || "知识点");

    if (data.type === "fact_review") {
        renderFactReview(data, plot);
    } else if (data.type === "concept_verify") {
        renderConceptVerify(data, plot);
    } else {
        elements.modalBody.innerHTML =
            "<p style='text-align:center;padding:20px;'>" +
            escapeHtml(data.message || "未知题型") +
            "</p>";
        elements.modalFooter.innerHTML =
            '<button class="btn btn-primary" id="close-water-btn">关闭</button>';
        var closeBtn = document.getElementById("close-water-btn");
        if (closeBtn) closeBtn.addEventListener("click", closeModal);
    }
}

function renderFactReview(data, plot) {
    currentLearning.referenceAnswer = data.card.content || null;

    var enhancedHtml = "";
    if (data.card.formula) {
        enhancedHtml +=
            '<div class="kc-formula" style="margin-top:8px;">' +
            '<strong>公式：</strong>' + data.card.formula +
            "</div>";
    }
    if (data.card.derivation_steps && data.card.derivation_steps.length > 0) {
        enhancedHtml +=
            '<div style="margin-top:8px;">' +
            "<strong>推导步骤：</strong><ol style='margin:4px 0 0 16px;'>" +
            data.card.derivation_steps.map(function (s) { return "<li>" + escapeHtml(s) + "</li>"; }).join("") +
            "</ol></div>";
    }
    if (data.card.common_mistakes && data.card.common_mistakes.length > 0) {
        enhancedHtml +=
            '<div style="margin-top:8px;background:#FFF3E0;border-radius:8px;padding:10px;">' +
            "<strong>⚠️ 常见误解：</strong><ul style='margin:4px 0 0 16px;'>" +
            data.card.common_mistakes.map(function (m) { return "<li>" + escapeHtml(m) + "</li>"; }).join("") +
            "</ul></div>";
    }
    if (data.card.application_examples && data.card.application_examples.length > 0) {
        enhancedHtml +=
            '<div style="margin-top:8px;background:#E8F5E9;border-radius:8px;padding:10px;">' +
            "<strong>🔧 应用案例：</strong><ul style='margin:4px 0 0 16px;'>" +
            data.card.application_examples.map(function (e) { return "<li>" + escapeHtml(e) + "</li>"; }).join("") +
            "</ul></div>";
    }

    elements.modalBody.innerHTML =
        '<div class="collapsible-header open" id="card-header">' +
        '<span class="collapse-arrow">▶</span> 知识卡片</div>' +
        '<div class="collapsible-body open" id="card-body">' +
        "<h4>" + escapeHtml(data.card.title) + "</h4>" +
        '<p class="card-content">' + escapeHtml(data.card.content) + "</p>" +
        enhancedHtml +
        (data.card.hint
            ? '<p style="color:#8D6E63;margin-top:8px;">💡 ' + escapeHtml(data.card.hint) + "</p>"
            : "") +
        (data.card.example
            ? '<p style="color:#558B2F;margin-top:4px;">📝 ' + escapeHtml(data.card.example) + "</p>"
            : "") +
        "</div>" +
        '<div class="collapsible-header" id="ref-header">' +
        '<span class="collapse-arrow">▶</span> 📖 显示参考答案</div>' +
        '<div class="collapsible-body" id="ref-body">' +
        '<div class="reference-answer-content" id="ref-answer-content">' +
        (currentLearning.referenceAnswer
            ? '<div class="reference-answer-box">' + escapeHtml(currentLearning.referenceAnswer) + '</div>'
            : '<p style="color:var(--color-text-muted);">暂无参考答案，请参考卡片中的定义。</p>') +
        "</div>" +
        "</div>";

    elements.modalFooter.innerHTML =
        '<button class="btn btn-primary" id="finish-btn">✅ 我已理解</button>';

    setupCollapsible("card-header", "card-body");
    setupCollapsible("ref-header", "ref-body");

    renderLatex(elements.modalBody);

    var finishBtn = document.getElementById("finish-btn");
    if (finishBtn) {
        finishBtn.addEventListener("click", function () {
            finishLearning(plot, true);
        });
    }
}

function renderConceptVerify(data, plot) {
    currentLearning.verify_type = data.verify_type;
    currentLearning.referenceAnswer = null;

    elements.modalBody.innerHTML =
        '<div class="paired-info">📋 题型: ' + getVerifyTypeLabel(data.verify_type) + "</div>" +
        '<p class="question-text" style="font-size:15px;line-height:1.6;">' +
        escapeHtml(data.question) +
        "</p>" +
        '<label for="answer-input" style="display:block;margin-top:12px;font-family:\'Patrick Hand\',cursive;">你的回答：</label>' +
        '<textarea id="answer-input" class="answer-textarea" rows="3"' +
        'placeholder="请输入你的理解..." aria-label="输入答案"></textarea>' +
        '<div id="feedback-area" style="display:none;margin-top:12px;"></div>' +
        '<div class="collapsible-header" id="ref-header" style="margin-top:12px;">' +
        '<span class="collapse-arrow">▶</span> 📖 显示参考答案</div>' +
        '<div class="collapsible-body" id="ref-body">' +
        '<div class="reference-answer-content" id="ref-answer-content">' +
        '<p style="color:var(--color-text-muted);">请先提交答案后查看参考答案</p>' +
        "</div>" +
        "</div>";

    elements.modalFooter.innerHTML =
        '<button class="btn btn-secondary" id="verify-btn">🔍 验证答案</button>' +
        '<button class="btn btn-primary" id="finish-btn" style="display:none;">✅ 完成学习</button>';

    setupCollapsible("ref-header", "ref-body");

    var verifyBtn = document.getElementById("verify-btn");
    var finishBtn = document.getElementById("finish-btn");
    var answerInput = document.getElementById("answer-input");

    if (verifyBtn) {
        verifyBtn.addEventListener("click", function () {
            submitAnswer(plot);
        });
    }
    if (finishBtn) {
        finishBtn.addEventListener("click", function () {
            finishLearning(plot, true);
        });
    }
    if (answerInput) {
        answerInput.focus();
    }

    renderLatex(elements.modalBody);
}

function setupCollapsible(headerId, bodyId) {
    var header = document.getElementById(headerId);
    var body = document.getElementById(bodyId);
    if (!header || !body) return;

    header.addEventListener("click", function () {
        var isOpen = body.classList.contains("open");
        if (isOpen) {
            body.classList.remove("open");
            header.classList.remove("open");
        } else {
            body.classList.add("open");
            header.classList.add("open");
        }
    });
}

function getVerifyTypeLabel(vt) {
    var labels = {
        explain: "📝 解释说明", apply: "🔧 实际应用", compare: "⚖️ 比较异同",
        relation: "🔗 关系分析", debug: "🐛 纠错辨析", recite: "📢 复述记忆",
        variant: "🔄 变式举例", calc: "🔢 计算推导", critique: "💭 批判分析",
        synthesis: "🧩 综合创新", evaluate: "📊 评估判断", summarize: "📋 总结归纳",
    };
    return labels[vt] || "📝 解释说明";
}

async function submitAnswer(plot) {
    var input = document.getElementById("answer-input");
    var feedbackArea = document.getElementById("feedback-area");
    if (!input || !feedbackArea) return;

    var answer = input.value.trim();
    if (!answer) {
        showToast("请输入你的回答", "warning");
        return;
    }

    var verifyBtn = document.getElementById("verify-btn");
    if (verifyBtn) setLoading(verifyBtn, true);

    try {
        var data = await apiFetch("/api/water_submit", {
            method: "POST",
            body: JSON.stringify({
                plot_id: plot.id,
                answer: answer,
                verify_type: currentLearning.verify_type || "explain",
            }),
        });

        feedbackArea.style.display = "block";
        var rawScore = data.score !== undefined ? data.score : 0;
        var score = rawScore <= 1 ? Math.round(rawScore * 100) : Math.round(rawScore);
        var scoreColor = score >= 70 ? "#558B2F" : score >= 40 ? "#F57F17" : "#C62828";
        var scoreEmoji = score >= 80 ? "🎉" : score >= 60 ? "👍" : score >= 40 ? "🤔" : "💪";

        if (data.reference_answer) {
            currentLearning.referenceAnswer = data.reference_answer;
        }

        var feedbackSummary = "";
        var feedbackImprovement = "";
        var feedbackFurther = "";
        var correctParts = [];
        var missingParts = [];
        var mistakes = [];
        var correctDerivation = "";

        if (typeof data.feedback === "object" && data.feedback !== null) {
            feedbackSummary = data.feedback.summary || "";
            feedbackImprovement = data.feedback.reference_answer || "";
            feedbackFurther = (data.feedback.further_study || []).join("、");
            correctParts = data.feedback.correct_parts || [];
            missingParts = data.feedback.missing_parts || [];
            mistakes = data.feedback.mistakes || [];
            correctDerivation = data.feedback.correct_derivation || "";
        }

        var feedbackHtml =
            '<div style="margin-bottom:12px;">' +
            '<span style="font-size:24px;">' + scoreEmoji + '</span> ' +
            '<strong style="font-size:18px;color:' + scoreColor + ';">得分: ' + score + '%</strong>' +
            "</div>";

        if (correctParts.length > 0) {
            feedbackHtml +=
                '<div style="background:#E8F5E9;border-left:4px solid #4CAF50;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>✅ 正确部分：</strong><ul style="margin:4px 0 0 16px;padding:0;">' +
                correctParts.map(function (p) { return "<li>" + escapeHtml(p) + "</li>"; }).join("") +
                "</ul></div>";
        }

        if (missingParts.length > 0) {
            feedbackHtml +=
                '<div style="background:#FFF8E1;border-left:4px solid #FF9800;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>⚠️ 遗漏要点：</strong><ul style="margin:4px 0 0 16px;padding:0;">' +
                missingParts.map(function (p) { return "<li>" + escapeHtml(p) + "</li>"; }).join("") +
                "</ul></div>";
        }

        if (mistakes.length > 0) {
            feedbackHtml +=
                '<div style="background:#FFEBEE;border-left:4px solid #F44336;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>❌ 错误点：</strong><ul style="margin:4px 0 0 16px;padding:0;">' +
                mistakes.map(function (p) { return "<li>" + escapeHtml(p) + "</li>"; }).join("") +
                "</ul></div>";
        }

        if (correctDerivation) {
            feedbackHtml +=
                '<div style="background:#ECEFF1;border-left:4px solid #607D8B;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>📐 正确推导 / 详解：</strong><p style="margin:4px 0 0 0;white-space:pre-wrap;">' +
                escapeHtml(correctDerivation) +
                "</p></div>";
        }

        if (feedbackImprovement) {
            feedbackHtml +=
                '<div style="background:#E3F2FD;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>📖 参考答案：</strong><br>' + escapeHtml(feedbackImprovement) +
                "</div>";
        }

        if (feedbackFurther) {
            feedbackHtml +=
                '<div style="background:#F3E5F5;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>📚 延伸学习：</strong><br>' + escapeHtml(feedbackFurther) +
                "</div>";
        }

        if (!feedbackSummary && correctParts.length === 0 && missingParts.length === 0 && mistakes.length === 0) {
            feedbackHtml +=
                '<div style="background:#F1F8E9;border-radius:8px;padding:12px;margin-bottom:8px;">' +
                '<strong>📝 你的回答已提交！</strong><br>继续加油！' +
                "</div>";
        }

        feedbackArea.innerHTML = feedbackHtml;

        var refContentEl = document.getElementById("ref-answer-content");
        if (refContentEl) {
            var refAnswer = currentLearning.referenceAnswer || data.reference_answer;
            if (refAnswer) {
                refContentEl.innerHTML =
                    '<div class="reference-answer-box">' +
                    escapeHtml(refAnswer) +
                    "</div>";
            } else {
                refContentEl.innerHTML =
                    '<p style="color:var(--color-text-muted);">暂无参考答案，请参考卡片中的定义。</p>';
            }
        }

        renderLatex(elements.modalBody);

        var finishBtn = document.getElementById("finish-btn");
        if (finishBtn) finishBtn.style.display = "inline-block";

        var plotEl = document.querySelector('[data-plot-id="' + plot.id + '"]');
        if (score < 40 && plotEl) showErrorFlash(plotEl);

        input.disabled = true;
    } catch (e) {
        showToast("评估失败: " + e.message, "error");
    } finally {
        if (verifyBtn) setLoading(verifyBtn, false);
    }
}

async function finishLearning(plot, understood) {
    try {
        await apiFetch("/api/finish_learning/" + plot.id, {
            method: "POST",
            body: JSON.stringify({ understood: !!understood }),
        });
        showToast("🎉 学习完成！", "success");

        var plotEl = document.querySelector('[data-plot-id="' + plot.id + '"]');
        if (plotEl) showWaterAnimation(plotEl);

        closeModal();
        await loadFarm();
    } catch (e) {
        showToast("操作失败: " + e.message, "error");
    }
}

/* ============ 收获 ============ */
var lastHarvestItemId = null;

async function harvestPlot(plot, plotEl) {
    try {
        var data = await apiFetch("/api/harvest/" + plot.id, { method: "POST" });
        if (plotEl) showHarvestAnimation(plotEl);

        var coinEl = document.querySelector(".coin-float");
        if (coinEl) {
            coinEl.textContent = "⭐ +" + (data.coins_earned || data.reward || 50);
        }

        lastHarvestItemId = plot.item_id;

        openModal();
        if (elements.modalTitle) elements.modalTitle.textContent = "🌟 收获成功！";
        if (elements.modalBody) {
            elements.modalBody.innerHTML =
                '<div style="text-align:center;padding:20px 0;">' +
                '<div style="font-size:48px;margin-bottom:12px;">' + SVG_ICONS.harvest + "</div>" +
                '<p style="font-size:18px;color:#4A7C59;">' +
                '恭喜收获！获得 <strong>' + (data.coins_earned || data.reward || 50) + '</strong> 星星</p>' +
                '</div>';
        }
        if (elements.modalFooter) {
            elements.modalFooter.innerHTML =
                '<button class="btn btn-primary" id="gen-card-btn">📸 生成知识卡片</button>' +
                '<button class="btn btn-secondary" id="harvest-done-btn">✅ 完成</button>';
        }

        var genCardBtn = document.getElementById("gen-card-btn");
        var harvestDoneBtn = document.getElementById("harvest-done-btn");

        if (genCardBtn) {
            genCardBtn.addEventListener("click", function () {
                if (lastHarvestItemId) {
                    generateKnowledgeCard(lastHarvestItemId);
                } else {
                    showToast("无法生成卡片：知识点ID缺失", "warning");
                }
            });
        }
        if (harvestDoneBtn) {
            harvestDoneBtn.addEventListener("click", function () {
                closeModal();
                loadFarm();
            });
        }

        setTimeout(async function () { await loadFarm(); }, 600);
    } catch (e) {
        showToast("收获失败: " + e.message, "error");
    }
}

/* ============ 知识卡片生成 ============ */
var currentCardBlob = null;

async function generateKnowledgeCard(itemId) {
    try {
        var data = await apiFetch("/api/generate_card", {
            method: "POST",
            body: JSON.stringify({ knowledge_item_id: itemId }),
        });

        if (!data.card) {
            showToast("获取卡片数据失败", "error");
            return;
        }

        var card = data.card;
        var wrapper = document.getElementById("knowledge-card-wrapper");
        var cardEl = document.getElementById("knowledge-card");

        document.getElementById("kc-date").textContent = card.date;
        document.getElementById("kc-type-badge").textContent =
            card.type === "fact" ? "📌 事实" : "💡 概念";
        document.getElementById("kc-title").textContent = card.title;
        document.getElementById("kc-content").textContent = card.content;
        document.getElementById("kc-stars").textContent = card.stars;
        document.getElementById("kc-mastery-pct").textContent = card.mastery + "%";
        document.getElementById("kc-quote").textContent = card.quote;
        document.getElementById("kc-domain").textContent = "📚 " + card.domain;

        var formulaEl = document.getElementById("kc-formula");
        if (formulaEl && card.formula) {
            formulaEl.innerHTML = card.formula;
            formulaEl.style.display = "block";
            renderLatex(formulaEl);
        } else if (formulaEl) {
            formulaEl.style.display = "none";
        }

        var derivEl = document.getElementById("kc-derivation");
        if (derivEl && card.derivation_steps && card.derivation_steps.length > 0) {
            derivEl.innerHTML =
                "<strong>推导步骤：</strong><ol style='margin:4px 0 0 16px;'>" +
                card.derivation_steps.map(function (s) { return "<li>" + escapeHtml(s) + "</li>"; }).join("") +
                "</ol>";
            derivEl.style.display = "block";
        } else if (derivEl) {
            derivEl.style.display = "none";
        }

        var mistakesEl = document.getElementById("kc-mistakes");
        if (mistakesEl && card.common_mistakes && card.common_mistakes.length > 0) {
            mistakesEl.innerHTML =
                "<strong>⚠️ 常见误解：</strong><ul style='margin:4px 0 0 16px;'>" +
                card.common_mistakes.map(function (m) { return "<li>" + escapeHtml(m) + "</li>"; }).join("") +
                "</ul>";
            mistakesEl.style.display = "block";
        } else if (mistakesEl) {
            mistakesEl.style.display = "none";
        }

        var examplesEl = document.getElementById("kc-examples");
        if (examplesEl && card.application_examples && card.application_examples.length > 0) {
            examplesEl.innerHTML =
                "<strong>🔧 应用案例：</strong><ul style='margin:4px 0 0 16px;'>" +
                card.application_examples.map(function (e) { return "<li>" + escapeHtml(e) + "</li>"; }).join("") +
                "</ul>";
            examplesEl.style.display = "block";
        } else if (examplesEl) {
            examplesEl.style.display = "none";
        }

        var tagsEl = document.getElementById("kc-tags");
        tagsEl.innerHTML = "";
        (card.tags || []).forEach(function (tag) {
            var span = document.createElement("span");
            span.className = "kc-tag";
            span.textContent = "#" + tag;
            tagsEl.appendChild(span);
        });

        wrapper.style.display = "block";
        wrapper.style.position = "fixed";
        wrapper.style.left = "-9999px";
        wrapper.style.top = "0";
        wrapper.style.zIndex = "-1";

        await new Promise(function (r) { setTimeout(r, 100); });

        if (typeof html2canvas === "undefined") {
            showToast("html2canvas 未加载，请检查网络", "error");
            wrapper.style.display = "none";
            return;
        }

        var canvas = await html2canvas(cardEl, {
            backgroundColor: null,
            scale: 2,
            useCORS: true,
            logging: false,
        });

        wrapper.style.display = "none";

        canvas.toBlob(function (blob) {
            currentCardBlob = blob;
            var imgUrl = URL.createObjectURL(blob);

            var previewImg = document.getElementById("card-preview-img");
            if (previewImg) previewImg.src = imgUrl;

            var cardModal = document.getElementById("card-modal");
            if (cardModal) cardModal.style.display = "block";
        }, "image/png");
    } catch (e) {
        showToast("生成卡片失败: " + e.message, "error");
    }
}

/* ============ 卡片分享与复制 ============ */
(function setupCardModal() {
    var closeBtn = document.getElementById("card-modal-close");
    var copyBtn = document.getElementById("card-copy-btn");
    var qqBtn = document.getElementById("card-qq-btn");
    var downloadBtn = document.getElementById("card-download-btn");
    var cardModal = document.getElementById("card-modal");

    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            if (cardModal) cardModal.style.display = "none";
        });
    }
    if (cardModal) {
        cardModal.addEventListener("click", function (e) {
            if (e.target === cardModal) cardModal.style.display = "none";
        });
    }

    if (copyBtn) {
        copyBtn.addEventListener("click", async function () {
            if (!currentCardBlob) {
                showToast("请先生成卡片", "warning");
                return;
            }
            try {
                await navigator.clipboard.write([
                    new ClipboardItem({ "image/png": currentCardBlob }),
                ]);
                showToast("📋 图片已复制到剪贴板！", "success");
            } catch (e) {
                showToast("复制失败，请尝试保存图片", "warning");
            }
        });
    }

    if (qqBtn) {
        qqBtn.addEventListener("click", function () {
            var title = encodeURIComponent("我在AI知识农场收获了一个知识点！");
            var summary = encodeURIComponent("快来一起种知识吧~");
            var url = encodeURIComponent(window.location.href);
            var pics = "";
            var previewImg = document.getElementById("card-preview-img");
            if (previewImg && previewImg.src) {
                pics = encodeURIComponent(previewImg.src);
            }
            var shareUrl =
                "https://connect.qq.com/widget/shareqq/index.html" +
                "?url=" + url +
                "&title=" + title +
                "&summary=" + summary +
                "&pics=" + pics;
            window.open(shareUrl, "_blank", "width=600,height=500");
        });
    }

    if (downloadBtn) {
        downloadBtn.addEventListener("click", function () {
            if (!currentCardBlob) {
                showToast("请先生成卡片", "warning");
                return;
            }
            var a = document.createElement("a");
            a.href = URL.createObjectURL(currentCardBlob);
            a.download = "knowledge_card_" + Date.now() + ".png";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            showToast("💾 图片已开始下载", "success");
        });
    }
})();

/* ============ 知识点提取 ============ */
elements.extractBtn.addEventListener("click", async function () {
    var text = elements.textInput.value.trim();
    if (!text) {
        showToast("请先输入或粘贴对话内容", "warning");
        return;
    }

    setLoading(elements.extractBtn, true);
    elements.resultPanel.style.display = "none";

    try {
        var data = await apiFetch("/api/extract", {
            method: "POST",
            body: JSON.stringify({ text: text }),
        });

        var count = data.knowledge_points ? data.knowledge_points.length : 0;
        elements.resultPanel.style.display = "block";
        elements.resultContent.innerHTML =
            "✅ 成功提取 <strong>" + count + "</strong> 个知识点！";

        var pointsHtml = "";
        (data.knowledge_points || []).forEach(function (p) {
            pointsHtml +=
                '<div style="margin:6px 0;padding:8px;background:#F1F8E9;border-radius:6px;">' +
                "<strong>" + escapeHtml(p.title) + "</strong>" +
                " <span>(" + escapeHtml(p.type) + ")</span>" +
                "</div>";
        });
        elements.resultContent.innerHTML += pointsHtml;

        await loadBackpack();
        await loadFarm();

        var totalSeeds = backpackData.reduce(function (s, seed) {
            return s + (seed.quantity || 1);
        }, 0);
        showToast("🎉 提取成功！背包新增 " + count + " 个种子", "success");

        if (totalSeeds > 0) {
            var emptyPlot = farmData.find(function (p) {
                return !p.item_id;
            });
            if (emptyPlot) {
                elements.resultContent.innerHTML +=
                    '<div class="quick-actions">' +
                    '<button class="btn auto-plant-btn" id="quick-auto-plant-btn"' +
                    'aria-label="自动种植第一个种子">🌱 一键种植到空地</button>' +
                    "</div>";
                var quickPlantBtn = document.getElementById("quick-auto-plant-btn");
                if (quickPlantBtn) {
                    quickPlantBtn.addEventListener("click", autoPlantSeed);
                }
            }
        }
    } catch (e) {
        showToast("提取失败: " + e.message, "error");
    } finally {
        setLoading(elements.extractBtn, false);
    }
});

/* ============ 剪贴板导入 ============ */
if (elements.clipboardBtn) {
    elements.clipboardBtn.addEventListener("click", async function () {
        try {
            var text = "";
            if (navigator.clipboard && navigator.clipboard.readText) {
                text = await navigator.clipboard.readText();
            }
            if (!text) {
                showToast("剪贴板为空或无权限，请手动粘贴", "warning");
                elements.textInput.focus();
                return;
            }
            elements.textInput.value = text;
            showToast("📋 已从剪贴板导入 " + text.length + " 字符", "success");
            elements.textInput.focus();
        } catch (e) {
            showToast("无法读取剪贴板，请手动粘贴（Ctrl+V）", "warning");
            elements.textInput.focus();
        }
    });
}

/* ============ 自动种植 ============ */
async function autoPlantSeed() {
    try {
        var data = await apiFetch("/api/auto_plant", { method: "POST" });

        if (data.status === "empty") {
            showToast(data.message || "背包中没有种子", "warning");
            return;
        }
        if (data.status === "full") {
            var fullMsg = data.message || "没有空闲地块";
            if (data.debug) {
                fullMsg += "（总计" + data.debug.total + "块，已用" + data.debug.occupied + "块，空闲" + data.debug.empty + "块）";
            }
            showToast(fullMsg, "warning");
            return;
        }

        showToast("🌱 " + escapeHtml(data.title) + " 已自动种植到空地！", "success");
        await loadFarm();
        await loadBackpack();
    } catch (e) {
        showToast("自动种植失败: " + e.message, "error");
    }
}

if (elements.autoPlantBtn) {
    elements.autoPlantBtn.addEventListener("click", autoPlantSeed);
}

/* ============ 一键浇水 ============ */
async function batchWaterAll() {
    try {
        var data = await apiFetch("/api/batch_water_info");

        if (!data.waterable_plots || data.waterable_plots.length === 0) {
            showToast("没有需要浇水的作物", "info");
            return;
        }

        var plots = data.waterable_plots;
        showToast("💧 检测到 " + plots.length + " 个可浇水作物，请依次作答", "info");

        openModal();
        if (elements.modalTitle) elements.modalTitle.textContent = "💧 批量灌溉";
        if (elements.modalBody) {
            elements.modalBody.innerHTML =
                '<div class="batch-progress-text">准备灌溉 ' + plots.length + ' 个作物...</div>' +
                '<div class="batch-progress">' +
                '<div class="batch-progress-fill" id="batch-fill" style="width:0%"></div>' +
                "</div>" +
                '<div id="batch-plots-list" style="margin-top:8px;"></div>';
        }
        if (elements.modalFooter) {
            elements.modalFooter.innerHTML =
                '<button class="btn btn-primary" id="batch-start-btn">💧 开始浇水</button>';
        }

        var startBtn = document.getElementById("batch-start-btn");
        if (startBtn) {
            startBtn.addEventListener("click", function () {
                processBatchWatering(plots, 0);
            });
        }

        var listEl = document.getElementById("batch-plots-list");
        if (listEl) {
            plots.forEach(function (p) {
                listEl.innerHTML +=
                    '<div style="padding:4px 8px;"><small>' +
                    escapeHtml(p.title) + " (" + escapeHtml(p.type) + ")</small></div>";
            });
        }
    } catch (e) {
        showToast("获取浇水列表失败: " + e.message, "error");
    }
}

async function processBatchWatering(plots, index) {
    if (index >= plots.length) {
        if (elements.modalBody) {
            elements.modalBody.innerHTML =
                '<div style="text-align:center;padding:30px;">' +
                '<div style="font-size:42px;">' + SVG_ICONS.harvest + "</div>" +
                '<p style="font-size:18px;color:#558B2F;">全部灌溉完成！</p>' +
                "</div>";
        }
        if (elements.modalFooter) {
            elements.modalFooter.innerHTML =
                '<button class="btn btn-primary" id="batch-done-btn">✅ 完成</button>';
            var doneBtn = document.getElementById("batch-done-btn");
            if (doneBtn) {
                doneBtn.addEventListener("click", function () {
                    closeModal();
                    loadFarm();
                });
            }
        }
        return;
    }

    var plot = plots[index];
    var fillEl = document.getElementById("batch-fill");
    if (fillEl) {
        fillEl.style.width = ((index / plots.length) * 100) + "%";
    }

    try {
        var pool = {
            type: "concept", title: plot.title,
            mastery: plot.mastery / 100, depth: "basic",
        };
        var waterData = await apiFetch("/api/water/" + plot.plot_id);
        currentLearning = { plot: pool, data: waterData };
        currentLearning._batchPlotId = plot.plot_id;

        if (elements.modalBody) {
            if (waterData.type === "fact_review") {
                renderFactReview(waterData, pool);
                patchBatchFactFinish(plots, index);
            } else {
                renderConceptVerify(waterData, pool);
                patchBatchConceptFinish(plots, index);
            }
        }
    } catch (e) {
        showToast("浇水失败 (" + plot.title + "): " + e.message, "error");
        processBatchWatering(plots, index + 1);
    }
}

function patchBatchFactFinish(plots, index) {
    var finishBtn = document.getElementById("finish-btn");
    if (finishBtn) {
        var origHandler = finishBtn.onclick;
        finishBtn.addEventListener("click", function () {
            apiFetch("/api/finish_learning/" + currentLearning._batchPlotId, {
                method: "POST",
                body: JSON.stringify({ understood: true }),
            }).then(function () {
                processBatchWatering(plots, index + 1);
            });
        }, { once: true });

        finishBtn.textContent = "✅ 理解 & 下一题 (→)";
    }
}

function patchBatchConceptFinish(plots, index) {
    var finishBtn = document.getElementById("finish-btn");
    if (finishBtn) {
        finishBtn.addEventListener("click", function () {
            apiFetch("/api/finish_learning/" + currentLearning._batchPlotId, {
                method: "POST",
                body: JSON.stringify({ understood: true }),
            }).then(function () {
                processBatchWatering(plots, index + 1);
            });
        }, { once: true });

        finishBtn.textContent = "✅ 完成 & 下一题 (→)";
    }
}

if (elements.waterAllBtn) {
    elements.waterAllBtn.addEventListener("click", batchWaterAll);
}

/* ============ 复习计划面板 ============ */
async function loadReviewPlan() {
    if (!elements.reviewList) return;

    try {
        var data = await apiFetch("/api/review_plan");
        if (!data.due_items || data.due_items.length === 0) {
            elements.reviewList.innerHTML =
                '<p style="text-align:center;color:#8D6E63;padding:12px;">🎉 暂无需要复习的知识点</p>';
            return;
        }

        elements.reviewList.innerHTML = "";
        data.due_items.forEach(function (item) {
            var el = document.createElement("div");
            el.className = "review-item";
            el.innerHTML =
                '<span class="review-title">' +
                escapeHtml(item.title) +
                "</span>" +
                '<span class="review-meta">' +
                (item.overdue_days > 0
                    ? '<span class="review-badge overdue">逾期' + item.overdue_days + "天</span>"
                    : '<span class="review-badge due-today">今天复习</span>') +
                '<span>' + escapeHtml(item.type) + "</span>" +
                "</span>";

            el.addEventListener("click", function () {
                var pool = {
                    id: item.plot_id,
                    type: item.type || "concept",
                    title: item.title,
                    mastery: item.mastery / 100,
                    depth: item.depth || "basic",
                    growth_value: item.growth || 0,
                };
                startWatering(pool);
            });
            elements.reviewList.appendChild(el);
        });
    } catch (e) {
        elements.reviewList.innerHTML =
            '<p style="text-align:center;color:#C62828;">加载复习计划失败</p>';
    }
}

/* ============ 侧边栏 ============ */
if (elements.sidebarToggle) {
    elements.sidebarToggle.addEventListener("click", function () {
        if (elements.sidebar) {
            elements.sidebar.classList.toggle("open");
            if (elements.sidebar.classList.contains("open")) {
                loadReviewPlan();
            }
        }
    });
}

/* ============ 加载数据 ============ */
async function loadFarm() {
    try {
        var data = await apiFetch("/api/farm");
        farmData = data.plots || [];
        renderFarm(farmData);
    } catch (e) {
        console.error("加载农场失败:", e);
    }
}

async function loadBackpack() {
    if (!elements.backpackList || !elements.backpackCount) return;

    try {
        var data = await apiFetch("/api/backpack");
        backpackData = data.backpack || data.items || data || [];
        renderBackpack(backpackData);
    } catch (e) {
        console.error("加载背包失败:", e);
    }
}

function renderBackpack(items) {
    if (!elements.backpackList) return;
    elements.backpackList.innerHTML = "";

    var totalCount = 0;
    items.forEach(function (seed) {
        totalCount += seed.quantity || 1;
        var el = document.createElement("div");
        el.className = "backpack-item";
        el.dataset.itemId = seed.item_id || seed.id;
        el.dataset.seedData = JSON.stringify(seed);
        el.style.cursor = "pointer";
        el.innerHTML =
            "<h4>" + escapeHtml(seed.title) + "</h4>" +
            '<span class="backpack-item-type ' + (seed.type || "") + '">' +
            escapeHtml(seed.type || "") +
            "</span>" +
            '<span class="backpack-item-qty">x' +
            (seed.quantity || 1) +
            "</span>";
        elements.backpackList.appendChild(el);
    });

    elements.backpackCount.textContent = totalCount;
}

function handleBackpackClick(e) {
    var item = e.target.closest(".backpack-item");
    if (!item) return;

    var seed;
    try {
        seed = JSON.parse(item.dataset.seedData);
    } catch (_) {
        seed = { item_id: item.dataset.itemId, id: item.dataset.itemId, title: "未知" };
    }

    if (e.shiftKey) {
        showKnowledgeDetail({
            title: seed.title,
            content: seed.content || "",
            type: seed.type || "concept",
            difficulty: seed.difficulty || 2,
            mastery: seed.mastery || 0,
            tags: seed.tags || [],
            domain: seed.domain || "通用",
            depth: seed.depth || "basic",
            growth_value: 0,
            item_id: seed.item_id || seed.id,
        });
        return;
    }

    var emptyPlot = farmData.find(function (p) { return !p.item_id; });
    if (!emptyPlot) {
        showToast("没有空闲地块！请先收获成熟作物", "warning");
        return;
    }
    plantSeed(emptyPlot, seed, document.querySelector(
        '[data-plot-id="' + emptyPlot.id + '"]'
    ));
}

/* ============ 弹窗 ============ */
function openModal() {
    if (elements.modal) {
        elements.modal.style.display = "block";
        elements.modal.setAttribute("aria-hidden", "false");
    }
}

function closeModal() {
    if (elements.modal) {
        elements.modal.style.display = "none";
        elements.modal.setAttribute("aria-hidden", "true");
    }
    currentLearning = null;
}

if (elements.modalClose) {
    elements.modalClose.addEventListener("click", closeModal);
}

if (elements.modal) {
    elements.modal.addEventListener("click", function (e) {
        if (e.target === elements.modal) closeModal();
    });
}

/* ============ 刷新按钮 ============ */
if (elements.refreshBtn) {
    elements.refreshBtn.addEventListener("click", async function () {
        await loadFarm();
        await loadBackpack();
        showToast("农场已刷新", "info");
    });
}

if (elements.resetBtn) {
    elements.resetBtn.addEventListener("click", async function () {
        if (!confirm("确定要重置农场吗？所有作物和知识点将被清除。")) return;
        try {
            await apiFetch("/api/reset", { method: "POST" });
            showToast("农场已重置，页面即将刷新", "success");
            setTimeout(function () { location.reload(); }, 800);
        } catch (e) {
            showToast("重置失败: " + e.message, "error");
        }
    });
}

/* ============ 知识点详情弹窗 ============ */
function showKnowledgeDetail(plot) {
    var modal = document.getElementById("kp-detail-modal");
    var titleEl = document.getElementById("kp-detail-title");
    var bodyEl = document.getElementById("kp-detail-body");
    var footerEl = document.getElementById("kp-detail-footer");
    if (!modal || !bodyEl) return;

    var kpTitle = plot.title || "未知知识点";
    var kpContent = plot.content || "暂无内容";
    var kpType = plot.type || "concept";
    var kpDifficulty = plot.difficulty || 2;
    var kpMastery = plot.mastery !== null && plot.mastery !== undefined ? Math.round(plot.mastery * 100) : 0;
    var kpTags = plot.tags || [];
    var kpDomain = plot.domain || "通用";
    var kpDepth = plot.depth || "basic";
    var growth = plot.growth_value || 0;

    titleEl.textContent = kpTitle;

    var diffStars = "";
    for (var d = 0; d < 5; d++) {
        diffStars += d < kpDifficulty ? "&#9733;" : "&#9734;";
    }

    var depthLabel = { basic: "基础", intermediate: "进阶", advanced: "高级" };
    var stage = getStage(growth);
    var stageLabel = {
        "plot-stage-seed": "种子期",
        "plot-stage-seedling": "幼苗期",
        "plot-stage-flowering": "开花期",
        "plot-stage-fruiting": "结果期",
    };

    bodyEl.innerHTML =
        '<div class="kp-detail-row"><span class="kp-detail-label">类型</span>' +
        '<span class="kp-detail-value kp-type-badge ' + kpType + '">' +
        (kpType === "fact" ? "事实" : "概念") + "</span></div>" +

        '<div class="kp-detail-row"><span class="kp-detail-label">难度</span>' +
        '<span class="kp-detail-value">' + diffStars + "</span></div>" +

        '<div class="kp-detail-row"><span class="kp-detail-label">掌握度</span>' +
        '<span class="kp-detail-value">' + kpMastery + "%</span></div>" +

        '<div class="kp-detail-row"><span class="kp-detail-label">领域</span>' +
        '<span class="kp-detail-value">' + escapeHtml(kpDomain) + "</span></div>" +

        '<div class="kp-detail-row"><span class="kp-detail-label">层级</span>' +
        '<span class="kp-detail-value">' + (depthLabel[kpDepth] || kpDepth) + "</span></div>" +

        '<div class="kp-detail-row"><span class="kp-detail-label">生长进度</span>' +
        '<span class="kp-detail-value">' + (stageLabel[stage.class] || "种子期") +
        " (" + growth + "%)</span></div>" +

        (kpTags.length > 0
            ? '<div class="kp-detail-row"><span class="kp-detail-label">标签</span>' +
              '<span class="kp-detail-value">' + kpTags.map(function (t) { return "#" + escapeHtml(t); }).join(" ") + "</span></div>"
            : "") +

        '<div class="kp-detail-content-box">' +
        '<div class="kp-detail-label">核心内容</div>' +
        '<p>' + escapeHtml(kpContent) + "</p></div>";

    footerEl.innerHTML = "";
    if (growth < 100) {
        var waterBtn = document.createElement("button");
        waterBtn.className = "btn btn-primary";
        waterBtn.textContent = "浇水灌溉";
        waterBtn.addEventListener("click", function () {
            modal.style.display = "none";
            startWatering(plot);
        });
        footerEl.appendChild(waterBtn);
    }

    var closeBtn2 = document.createElement("button");
    closeBtn2.className = "btn btn-secondary";
    closeBtn2.textContent = "关闭";
    closeBtn2.addEventListener("click", function () {
        modal.style.display = "none";
    });
    footerEl.appendChild(closeBtn2);

    modal.style.display = "block";
}

(function setupKpDetailModal() {
    var modal = document.getElementById("kp-detail-modal");
    var closeBtn = document.getElementById("kp-detail-close");

    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            if (modal) modal.style.display = "none";
        });
    }
    if (modal) {
        modal.addEventListener("click", function (e) {
            if (e.target === modal) modal.style.display = "none";
        });
    }
})();
async function init() {
    setupKeyboardShortcuts();
    if (elements.backpackList) {
        elements.backpackList.addEventListener("click", handleBackpackClick);
    }
    await loadFarm();
    await loadBackpack();
    loadReviewPlan();
    setupBilibiliImport();
    setupTopicSummary();
    checkAvailableTopics();
}

document.addEventListener("DOMContentLoaded", init);

/* ============ B站视频导入 ============ */
function setupBilibiliImport() {
    var sprintBtn = document.getElementById("bili-sprint-btn");
    var normalBtn = document.getElementById("bili-normal-btn");
    var urlInput = document.getElementById("bili-url-input");

    if (sprintBtn) {
        sprintBtn.addEventListener("click", function () {
            importFromBilibili("sprint");
        });
    }
    if (normalBtn) {
        normalBtn.addEventListener("click", function () {
            importFromBilibili("normal");
        });
    }
    if (urlInput) {
        urlInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                importFromBilibili("sprint");
            }
        });
    }
}

async function importFromBilibili(mode) {
    var urlInput = document.getElementById("bili-url-input");
    var resultDiv = document.getElementById("bili-result");
    var url = (urlInput ? urlInput.value : "").trim();

    if (!url) {
        showToast("请先粘贴B站视频链接", "warning");
        return;
    }

    if (!url.includes("bilibili.com") && !url.match(/BV[a-zA-Z0-9]+/)) {
        showToast("请输入有效的B站视频链接", "warning");
        return;
    }

    var activeBtn = mode === "sprint"
        ? document.getElementById("bili-sprint-btn")
        : document.getElementById("bili-normal-btn");

    if (activeBtn) setLoading(activeBtn, true);
    if (resultDiv) {
        resultDiv.style.display = "block";
        resultDiv.innerHTML = '<div style="text-align:center;padding:20px;color:#8D6E63;">⏳ 正在获取视频内容并分析...</div>';
    }

    try {
        var data = await apiFetch("/api/import_content", {
            method: "POST",
            body: JSON.stringify({ source_url: url, learning_mode: mode }),
        });

        if (data.error) {
            if (resultDiv) {
                resultDiv.innerHTML = '<div style="color:#C62828;padding:12px;">❌ ' + escapeHtml(data.error) + "</div>";
            }
            return;
        }

        renderBilibiliResult(data, mode, resultDiv);

        if (data.saved_items && data.saved_items.length > 0) {
            var plantedCount = data.planted_count || 0;
            var totalCount = data.total_count || data.saved_items.length;

            if (mode === "sprint") {
                if (data.warning) {
                    var warnMsg = data.warning;
                    if (data.debug) {
                        warnMsg += "（总计" + data.debug.total + "块，已用" + data.debug.occupied + "块，空闲" + data.debug.empty + "块）";
                    }
                    showToast(warnMsg, "warning");
                } else if (plantedCount > 0) {
                    showToast("快读完成！" + plantedCount + " 个知识点已种植到农场", "success");
                } else {
                    var fullMsg = "农场已满，请先收获部分作物";
                    if (data.debug) {
                        fullMsg += "（总计" + data.debug.total + "块，已用" + data.debug.occupied + "块，空闲" + data.debug.empty + "块）";
                    }
                    showToast(fullMsg, "warning");
                }
            } else {
                showToast("沉浸学习完成！" + data.saved_items.length + " 个知识点已加入背包", "success");
            }

            await loadBackpack();
            await loadFarm();
        }
    } catch (e) {
        if (resultDiv) {
            resultDiv.innerHTML = '<div style="color:#C62828;padding:12px;">❌ 导入失败: ' + escapeHtml(e.message) + "</div>";
        }
    } finally {
        if (activeBtn) setLoading(activeBtn, false);
    }
}

function renderBilibiliResult(data, mode, container) {
    if (!container) return;

    var videoInfo = data.video_info || {};
    var durationMin = Math.round((videoInfo.duration || 0) / 60);

    var html = '<div class="bili-card">';

    html += '<div class="bili-card-header">';
    html += '<div class="bili-card-title">' + escapeHtml(videoInfo.title || "未知视频") + "</div>";
    html += '<div class="bili-card-meta">UP: ' + escapeHtml(videoInfo.owner || "") + " · " + durationMin + "分钟";
    if (data.source === "subtitle") {
        html += ' · 📝 字幕来源';
    } else {
        html += ' · 📄 简介来源';
    }
    html += "</div></div>";

    html += '<div class="bili-card-summary">';
    html += '<strong>📋 核心摘要</strong>';
    html += '<p>' + escapeHtml(data.summary || "暂无摘要") + "</p>";
    html += "</div>";

    if (data.timestamp_index && data.timestamp_index.length > 0) {
        html += '<div class="bili-card-timestamps">';
        html += '<strong>⏱️ 关键时间点</strong>';
        html += '<div class="timestamp-list">';
        data.timestamp_index.forEach(function (ts) {
            html += '<span class="timestamp-item">' + escapeHtml(ts.time) + " " + escapeHtml(ts.topic) + "</span>";
        });
        html += "</div></div>";
    }

    if (data.qa_pairs && data.qa_pairs.length > 0) {
        html += '<div class="bili-card-qa">';
        html += '<strong>❓ 快速问答</strong>';
        data.qa_pairs.forEach(function (qa) {
            html += '<div class="qa-item">';
            html += '<div class="qa-q">Q: ' + escapeHtml(qa.question) + "</div>";
            html += '<div class="qa-a">A: ' + escapeHtml(qa.answer) + "</div>";
            html += "</div>";
        });
        html += "</div>";
    }

    var points = data.knowledge_points || [];
    if (points.length > 0) {
        html += '<div class="bili-card-points">';
        html += '<strong>💡 提取的知识点 (' + points.length + ')</strong>';
        points.forEach(function (p, i) {
            html += '<div class="bili-point-item">';
            html += '<span class="bili-point-type ' + (p.type || "concept") + '">' + escapeHtml(p.type || "concept") + "</span>";
            html += '<span class="bili-point-title">' + escapeHtml(p.title) + "</span>";
            if (p.timestamp) {
                html += '<span class="bili-point-ts">@' + escapeHtml(p.timestamp) + "</span>";
            }

            if (mode === "sprint") {
                var savedItem = (data.saved_items && data.saved_items[i]) ? data.saved_items[i] : null;
                var hasPlot = savedItem && savedItem.plot_id;
                if (hasPlot) {
                    html += '<span class="bili-planted-badge">已种植</span>';
                } else {
                    html += '<button class="bili-import-one-btn" data-point-index="' + i + '"';
                    html += ' data-title="' + escapeHtml(p.title).replace(/"/g, "&quot;") + '"';
                    html += ' data-content="' + escapeHtml(p.content || "").replace(/"/g, "&quot;") + '"';
                    html += ' data-type="' + (p.type || "concept") + '"';
                    html += ' data-tags="' + escapeHtml((p.tags || []).join(",")).replace(/"/g, "&quot;") + '"';
                    html += ' data-domain="' + escapeHtml(p.domain || "通用").replace(/"/g, "&quot;") + '"';
                    html += ' data-difficulty="' + (p.difficulty || 2) + '"';
                    html += '>导入背包</button>';
                }
            }

            html += "</div>";
        });
        html += "</div>";
    }

    if (mode === "sprint" && points.length > 0) {
        var plantedCount = data.planted_count || 0;
        var totalCount = data.total_count || points.length;
        html += '<div class="bili-card-actions">';
        if (plantedCount === totalCount) {
            html += '<p class="bili-status-ok">已自动种植 ' + plantedCount + " 个知识点到农场</p>";
        } else if (plantedCount > 0) {
            html += '<p class="bili-status-partial">已种植 ' + plantedCount + "/" + totalCount + " 个，剩余无空地</p>";
            html += '<button class="btn bili-import-all-btn" id="bili-import-all-btn">将剩余导入背包</button>';
        } else {
            var farmFullMsg = "农场已满，无法自动种植";
            if (data.debug) {
                farmFullMsg += "（总计" + data.debug.total + "块，已用" + data.debug.occupied + "块，空闲" + data.debug.empty + "块）";
            }
            html += '<p class="bili-status-partial">' + farmFullMsg + '</p>';
            html += '<button class="btn bili-import-all-btn" id="bili-import-all-btn">全部导入背包</button>';
        }
        html += "</div>";
    }

    if (mode === "normal" && data.saved_items && data.saved_items.length > 0) {
        html += '<div class="bili-card-actions">';
        html += '<p class="bili-status-ok">已自动导入 ' + data.saved_items.length + " 个知识点到背包</p>";
        html += "</div>";
    }

    html += "</div>";
    container.innerHTML = html;

    container.querySelectorAll(".bili-import-one-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            importSinglePoint(btn);
        });
    });

    var importAllBtn = document.getElementById("bili-import-all-btn");
    if (importAllBtn) {
        importAllBtn.addEventListener("click", function () {
            importAllSprintPoints(data);
        });
    }
}

async function importSinglePoint(btn) {
    var title = btn.getAttribute("data-title");
    var content = btn.getAttribute("data-content");
    var type = btn.getAttribute("data-type");
    var tagsStr = btn.getAttribute("data-tags");
    var domain = btn.getAttribute("data-domain");
    var difficulty = parseInt(btn.getAttribute("data-difficulty")) || 2;

    try {
        var result = await apiFetch("/api/extract", {
            method: "POST",
            body: JSON.stringify({
                text: content,
                _force_items: [{
                    title: title,
                    content: content,
                    type: type,
                    tags: tagsStr ? tagsStr.split(",") : [],
                    domain: domain,
                    difficulty: difficulty,
                }],
            }),
        });

        btn.textContent = "✅ 已导入";
        btn.disabled = true;
        btn.style.opacity = "0.6";
        showToast("🌱 " + title + " 已导入背包！", "success");
        await loadBackpack();
    } catch (e) {
        showToast("导入失败: " + e.message, "error");
    }
}

async function importAllSprintPoints(data) {
    var points = data.knowledge_points || [];
    if (points.length === 0) return;

    var importAllBtn = document.getElementById("bili-import-all-btn");
    if (importAllBtn) {
        importAllBtn.disabled = true;
        importAllBtn.textContent = "⏳ 导入中...";
    }

    var successCount = 0;
    for (var i = 0; i < points.length; i++) {
        var p = points[i];
        try {
            await apiFetch("/api/extract", {
                method: "POST",
                body: JSON.stringify({
                    text: p.content || p.title,
                    _force_items: [p],
                }),
            });
            successCount++;

            var btn = document.querySelector('.bili-import-one-btn[data-point-index="' + i + '"]');
            if (btn) {
                btn.textContent = "✅ 已导入";
                btn.disabled = true;
                btn.style.opacity = "0.6";
            }
        } catch (e) {
            console.error("导入知识点失败:", p.title, e);
        }
    }

    showToast("🎉 成功导入 " + successCount + "/" + points.length + " 个知识点！", "success");
    if (importAllBtn) {
        importAllBtn.textContent = "✅ 全部导入完成";
    }
    await loadBackpack();
    await loadFarm();
}

/* ============ 专题总结 ============ */
function setupTopicSummary() {
    var summaryBtn = document.getElementById("summary-btn");
    var alertSummaryBtn = document.getElementById("alert-summary-btn");
    var summaryModalClose = document.getElementById("summary-modal-close");
    var backToTopics = document.getElementById("back-to-topics");
    var summaryModal = document.getElementById("summary-modal");

    if (summaryBtn) {
        summaryBtn.addEventListener("click", function () {
            openSummaryModal();
        });
    }
    if (alertSummaryBtn) {
        alertSummaryBtn.addEventListener("click", function () {
            openSummaryModal();
        });
    }
    if (summaryModalClose) {
        summaryModalClose.addEventListener("click", function () {
            closeSummaryModal();
        });
    }
    if (summaryModal) {
        summaryModal.addEventListener("click", function (e) {
            if (e.target === summaryModal) {
                closeSummaryModal();
            }
        });
    }
    if (backToTopics) {
        backToTopics.addEventListener("click", function () {
            showTopicSelector();
        });
    }
}

function openSummaryModal() {
    var modal = document.getElementById("summary-modal");
    if (modal) {
        modal.style.display = "block";
        modal.setAttribute("aria-hidden", "false");
    }
    showTopicSelector();
}

function closeSummaryModal() {
    var modal = document.getElementById("summary-modal");
    if (modal) {
        modal.style.display = "none";
        modal.setAttribute("aria-hidden", "true");
    }
}

async function showTopicSelector() {
    var selector = document.getElementById("topic-selector");
    var resultDiv = document.getElementById("summary-result");
    var footer = document.getElementById("summary-modal-footer");

    if (resultDiv) resultDiv.style.display = "none";
    if (footer) footer.style.display = "none";
    if (!selector) return;

    selector.style.display = "block";
    selector.innerHTML = '<div style="text-align:center;padding:30px;color:var(--color-text-muted);">⏳ 加载专题列表...</div>';

    try {
        var data = await apiFetch("/api/available_topics");
        var topics = data.available_topics || [];

        if (topics.length === 0) {
            selector.innerHTML =
                '<div class="empty-message">' +
                '📚 暂无可生成总结的专题<br>' +
                '<small style="color:var(--color-text-muted);">需要至少3个相同标签的知识点才能生成专题总结</small>' +
                '</div>';
            return;
        }

        var html = '<p class="selector-hint">选择一个专题标签，AI将为你生成结构化的总结报告：</p>';
        html += '<div class="topic-list">';

        topics.forEach(function (topic) {
            html +=
                '<div class="topic-card" data-tag="' + escapeHtml(topic.tag) + '">' +
                '<div class="topic-tag">' + escapeHtml(topic.tag) + '</div>' +
                '<div class="topic-count">' + topic.count + ' 个知识点</div>' +
                '</div>';
        });

        html += '</div>';
        selector.innerHTML = html;

        selector.querySelectorAll(".topic-card").forEach(function (card) {
            card.addEventListener("click", function () {
                var tag = card.getAttribute("data-tag");
                generateTopicSummary(tag);
            });
        });
    } catch (e) {
        selector.innerHTML =
            '<div class="empty-message" style="color:var(--color-error);">❌ 加载失败: ' + escapeHtml(e.message) + '</div>';
    }
}

async function generateTopicSummary(tag) {
    var selector = document.getElementById("topic-selector");
    var resultDiv = document.getElementById("summary-result");
    var footer = document.getElementById("summary-modal-footer");

    if (selector) selector.style.display = "none";
    if (resultDiv) {
        resultDiv.style.display = "block";
        resultDiv.innerHTML = '<div style="text-align:center;padding:40px;color:var(--color-text-muted);">⏳ AI正在生成专题总结，请稍候...</div>';
    }

    try {
        var data = await apiFetch("/api/generate_summary", {
            method: "POST",
            body: JSON.stringify({ tags: [tag] }),
        });

        var summaryText = data.summary || "生成总结失败，请重试。";
        var itemCount = data.item_count || 0;

        var html =
            '<div class="summary-header">' +
            '<h4>📚 ' + escapeHtml(tag) + ' 专题总结</h4>' +
            '<span class="summary-count">基于 ' + itemCount + ' 个知识点</span>' +
            '</div>' +
            '<div class="summary-markdown">' +
            renderMarkdown(summaryText) +
            '</div>';

        if (resultDiv) {
            resultDiv.innerHTML = html;
            renderLatex(resultDiv);
        }

        if (footer) footer.style.display = "flex";
    } catch (e) {
        if (resultDiv) {
            resultDiv.innerHTML =
                '<div class="empty-message" style="color:var(--color-error);">❌ 生成失败: ' + escapeHtml(e.message) + '</div>';
        }
    }
}

function renderMarkdown(text) {
    if (typeof marked === "function" || (typeof marked === "object" && typeof marked.parse === "function")) {
        try {
            if (typeof marked.parse === "function") {
                return marked.parse(text);
            }
            return marked(text);
        } catch (e) {
            console.error("Markdown渲染失败:", e);
        }
    }
    return escapeHtml(text).replace(/\n/g, "<br>");
}

async function checkAvailableTopics() {
    var alertEl = document.getElementById("topic-summary-alert");
    if (!alertEl) return;

    try {
        var data = await apiFetch("/api/available_topics");
        var topics = data.available_topics || [];

        if (topics.length > 0) {
            alertEl.style.display = "block";
            var alertText = alertEl.querySelector(".alert-text");
            if (alertText) {
                alertText.textContent = "发现有 " + topics.length + " 个专题可以生成总结！";
            }
        } else {
            alertEl.style.display = "none";
        }
    } catch (e) {
        alertEl.style.display = "none";
    }
}
