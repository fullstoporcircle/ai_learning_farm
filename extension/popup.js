"use strict";

var grabbedText = "";

function setStatus(msg, isError) {
    var el = document.getElementById("status");
    el.textContent = msg;
    el.style.color = isError ? "#C62828" : "#558B2F";
}

function showPreview(text) {
    var preview = document.getElementById("preview");
    preview.textContent = text.substring(0, 500) + (text.length > 500 ? "\n... (截断预览)" : "");
    preview.classList.add("show");
}

document.getElementById("grab-btn").addEventListener("click", async function () {
    try {
        var [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (!tab) {
            setStatus("无法获取当前标签页", true);
            return;
        }

        var result = await chrome.scripting.executeScript({
            target: { tabId: tab.id },
            func: extractConversation,
        });

        if (result && result[0] && result[0].result) {
            grabbedText = result[0].result;
            showPreview(grabbedText);
            document.getElementById("send-btn").disabled = false;
            setStatus("抓取成功！" + grabbedText.length + " 字符");
        } else {
            setStatus("未找到对话内容，请确保在 DeepSeek/ChatGPT 页面", true);
        }
    } catch (e) {
        setStatus("抓取失败: " + e.message, true);
    }
});

document.getElementById("send-btn").addEventListener("click", async function () {
    if (!grabbedText) {
        setStatus("请先抓取对话", true);
        return;
    }

    var farmUrl = document.getElementById("farm-url").value.trim().replace(/\/+$/, "");
    if (!farmUrl) {
        setStatus("请输入农场地址", true);
        return;
    }

    try {
        var res = await fetch(farmUrl + "/api/extract", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: grabbedText }),
        });

        if (!res.ok) throw new Error("HTTP " + res.status);

        var data = await res.json();
        var count = data.knowledge_points ? data.knowledge_points.length : 0;
        setStatus("成功提取 " + count + " 个知识点！请刷新农场页面查看");
    } catch (e) {
        setStatus("发送失败: " + e.message + "\n请确认农场后端已启动", true);
    }
});

document.getElementById("open-btn").addEventListener("click", function () {
    chrome.tabs.create({ url: document.getElementById("farm-url").value.trim() });
});

chrome.storage.local.get("farmUrl", function (data) {
    if (data.farmUrl) {
        document.getElementById("farm-url").value = data.farmUrl;
    }
});

document.getElementById("farm-url").addEventListener("change", function () {
    chrome.storage.local.set({ farmUrl: this.value.trim() });
});

function extractConversation() {
    var userMessages = [];
    var assistantMessages = [];

    var selectors = [
        "div[data-message-author-role='user']",
        ".whitespace-pre-wrap",
        ".markdown.prose p",
        '[class*="message"] [class*="content"]',
    ];

    document.querySelectorAll(
        'div[class*="user"], [data-role="user"], .user-message, .human-message'
    ).forEach(function (el) {
        var text = (el.textContent || "").trim();
        if (text && text.length > 3) userMessages.push(text);
    });

    document.querySelectorAll(
        'div[class*="assistant"], [data-role="assistant"], ' +
        '.bot-message, .ai-message, .agent-turn, .gpt-message, ' +
        '.deepseek-message, .response-content'
    ).forEach(function (el) {
        var text = (el.textContent || "").trim();
        if (text && text.length > 3) assistantMessages.push(text);
    });

    if (userMessages.length === 0 && assistantMessages.length === 0) {
        var bodyText = document.body.innerText;
        if (bodyText.length > 10) return bodyText.substring(0, 8000);
        return "";
    }

    var lastUser = userMessages[userMessages.length - 1] || "";
    var lastAssistant = assistantMessages[assistantMessages.length - 1] || "";

    var parts = [];
    if (lastUser) parts.push("用户提问：\n" + lastUser);
    if (lastAssistant) parts.push("AI回复：\n" + lastAssistant);

    if (parts.length === 0) {
        parts.push("用户消息：");
        userMessages.slice(-3).forEach(function (m) { parts.push(m); });
        parts.push("AI消息：");
        assistantMessages.slice(-3).forEach(function (m) { parts.push(m); });
    }

    return parts.join("\n\n");
}
