// ==UserScript==
// @name         Reddit → Stash
// @namespace    https://github.com/carport727/reddit-stash-agent
// @version      __VERSION__
// @description  Send the Reddit posts you are looking at to the Reddit Stash Agent, which downloads them into Stash.
// @match        https://www.reddit.com/*
// @match        https://old.reddit.com/*
// @match        https://sh.reddit.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @connect      __AGENT_HOST__
// @connect      *
// @downloadURL  __AGENT_URL__/reddit-stash-agent.user.js
// @updateURL    __AGENT_URL__/reddit-stash-agent.user.js
// @run-at       document-idle
// ==/UserScript==

// Only reads the page you have open; it never loads other Reddit pages by itself.
// The agent fetches each post you send with your Reddit login, like "Download Reddit Post" in Stash.

(function () {
  "use strict";

  const DEFAULT_AGENT_URL = "__AGENT_URL__";
  const LOOKUP_BATCH = 200;
  const SCAN_DELAY_MS = 800;
  const REFRESH_QUEUED_MS = 15000;

  // url -> { url, status, error, elements: [element], buttons: [button] } (a post can appear twice on a page)
  const posts = new Map();

  function agentUrl() {
    return String(GM_getValue("agentUrl", DEFAULT_AGENT_URL) || DEFAULT_AGENT_URL).replace(/\/+$/, "");
  }

  function token() {
    return String(GM_getValue("token", "") || "");
  }

  function configure() {
    const url = prompt("Reddit Stash Agent URL", agentUrl());
    if (url === null) return false;
    const tok = prompt("Agent API token (AGENT_TOKEN, same as in the Stash plugin settings)", token());
    if (tok === null) return false;
    GM_setValue("agentUrl", url.trim());
    GM_setValue("token", tok.trim());
    scheduleScan(true);
    return true;
  }

  GM_registerMenuCommand("Reddit → Stash: settings", configure);

  function api(method, path, body) {
    return new Promise(function (resolve, reject) {
      GM_xmlhttpRequest({
        method: method,
        url: agentUrl() + path,
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token() },
        data: body ? JSON.stringify(body) : undefined,
        timeout: 30000,
        onload: function (response) {
          let data = null;
          try {
            data = JSON.parse(response.responseText);
          } catch (e) {
            // keep null
          }
          if (response.status === 401) reject(new Error("Wrong or missing token (menu: Reddit → Stash: settings)"));
          else if (response.status >= 400) reject(new Error((data && data.detail) || "Agent error " + response.status));
          else resolve(data);
        },
        onerror: function () {
          reject(new Error("Agent not reachable at " + agentUrl()));
        },
        ontimeout: function () {
          reject(new Error("Agent did not answer"));
        },
      });
    });
  }

  // Posts on the page: new Reddit (shreddit-post), old Reddit (div.thing), and the open post itself.
  function findPosts() {
    const found = [];
    document.querySelectorAll("shreddit-post[permalink]").forEach(function (el) {
      found.push({ url: "https://www.reddit.com" + el.getAttribute("permalink"), el: el, anchor: el });
    });
    document.querySelectorAll("div.thing.link[data-permalink]").forEach(function (el) {
      const anchor = el.querySelector(".entry") || el;
      found.push({ url: "https://www.reddit.com" + el.getAttribute("data-permalink"), el: el, anchor: anchor });
    });
    return found;
  }

  const LABELS = {
    new: "→ Stash",
    unknown: "→ Stash",
    queued: "⏳ queued",
    downloaded: "✓ in Stash",
    invalid: "✗ not a post",
    error: "⚠ retry",
  };

  function render(post) {
    post.buttons.forEach(function (button) {
      button.textContent = LABELS[post.status] || "…";
      button.title = post.error || "";
      button.disabled = post.status === "downloaded" || post.status === "queued" || post.status === "invalid";
      button.dataset.status = post.status || "";
    });
  }

  function makeButton(post) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "rsa-button";
    button.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      send([post.url]);
    });
    return button;
  }

  function applyResults(results) {
    (results || []).forEach(function (result) {
      const post = posts.get(result.url);
      if (!post) return;
      post.status = result.status;
      post.error = result.error || null;
      render(post);
    });
    updatePanel();
  }

  async function lookup(urls) {
    for (let i = 0; i < urls.length; i += LOOKUP_BATCH) {
      try {
        const data = await api("POST", "/api/posts/lookup", { urls: urls.slice(i, i + LOOKUP_BATCH) });
        applyResults(data.posts);
        setMessage(null);
      } catch (err) {
        setMessage(err.message, true);
        return;
      }
    }
  }

  async function send(urls) {
    if (!token() && !configure()) return;
    urls.forEach(function (url) {
      const post = posts.get(url);
      if (post) {
        post.status = "queued";
        render(post);
      }
    });
    try {
      const data = await api("POST", "/api/posts/download", { urls: urls });
      applyResults(data.posts);
      const counts = data.counts || {};
      setMessage(
        (counts.queued || 0) + " sent to Stash" + (counts.downloaded ? ", " + counts.downloaded + " already there" : ""),
        false
      );
    } catch (err) {
      urls.forEach(function (url) {
        const post = posts.get(url);
        if (post) {
          post.status = "error";
          post.error = err.message;
          render(post);
        }
      });
      setMessage(err.message, true);
    }
  }

  // Floating panel: count and "send all new posts of this page".
  let panel, panelText, panelButton, panelMessage;

  function buildPanel() {
    panel = document.createElement("div");
    panel.className = "rsa-panel";
    panelText = document.createElement("span");
    panelButton = document.createElement("button");
    panelButton.type = "button";
    panelButton.className = "rsa-button";
    panelButton.addEventListener("click", function () {
      const urls = [];
      posts.forEach(function (post) {
        if (post.status === "new" || post.status === "unknown" || post.status === "error") urls.push(post.url);
      });
      if (urls.length) send(urls);
    });
    panelMessage = document.createElement("div");
    panelMessage.className = "rsa-message";
    panel.append(panelText, panelButton, panelMessage);
    document.body.appendChild(panel);
  }

  function updatePanel() {
    if (!panel) buildPanel();
    let fresh = 0;
    let stored = 0;
    posts.forEach(function (post) {
      if (post.status === "new" || post.status === "unknown" || post.status === "error") fresh += 1;
      if (post.status === "downloaded") stored += 1;
    });
    panelText.textContent = "Reddit → Stash: " + fresh + " new, " + stored + " in Stash ";
    panelButton.textContent = "Send " + fresh + " new";
    panelButton.disabled = fresh === 0;
    panel.style.display = posts.size ? "" : "none";
  }

  function setMessage(text, isError) {
    if (!panel) buildPanel();
    panelMessage.textContent = text || "";
    panelMessage.classList.toggle("rsa-error", !!isError);
  }

  function scan() {
    const added = [];
    findPosts().forEach(function (item) {
      let post = posts.get(item.url);
      if (!post) {
        post = { url: item.url, status: null, error: null, elements: [], buttons: [] };
        posts.set(item.url, post);
        added.push(item.url);
      }
      if (post.elements.indexOf(item.el) === -1) {
        post.elements.push(item.el);
        const button = makeButton(post);
        post.buttons.push(button);
        item.anchor.insertAdjacentElement(item.anchor === item.el ? "beforebegin" : "afterbegin", button);
        render(post);
      }
    });
    if (added.length) {
      updatePanel();
      if (token()) lookup(added);
      else setMessage("Set agent URL and token: userscript menu → Reddit → Stash: settings", true);
    }
  }

  let scanTimer = null;
  function scheduleScan(refreshAll) {
    clearTimeout(scanTimer);
    scanTimer = setTimeout(function () {
      if (refreshAll) lookup(Array.from(posts.keys()));
      scan();
    }, SCAN_DELAY_MS);
  }

  // Refresh posts that are still being downloaded.
  setInterval(function () {
    const queued = [];
    posts.forEach(function (post) {
      if (post.status === "queued") queued.push(post.url);
    });
    if (queued.length && token()) lookup(queued);
  }, REFRESH_QUEUED_MS);

  const style = document.createElement("style");
  style.textContent = `
    .rsa-button { margin: 4px 0; padding: 2px 10px; border-radius: 999px; border: 1px solid #ff4500;
      background: #ff4500; color: #fff; font: 600 12px/1.6 sans-serif; cursor: pointer; }
    .rsa-button:disabled { cursor: default; opacity: .75; }
    .rsa-button[data-status="downloaded"] { background: #2e7d32; border-color: #2e7d32; }
    .rsa-button[data-status="queued"] { background: #555; border-color: #555; }
    .rsa-button[data-status="error"], .rsa-button[data-status="invalid"] { background: #b00020; border-color: #b00020; }
    .rsa-panel { position: fixed; right: 16px; bottom: 16px; z-index: 2147483647; max-width: 320px; padding: 10px 12px;
      border-radius: 12px; background: rgba(20,20,20,.92); color: #fff; font: 13px/1.4 sans-serif;
      box-shadow: 0 4px 16px rgba(0,0,0,.4); }
    .rsa-panel .rsa-button { margin-left: 6px; }
    .rsa-panel .rsa-button:disabled { background: #555; border-color: #555; }
    .rsa-message { margin-top: 4px; color: #9be29b; }
    .rsa-message.rsa-error { color: #ff8a80; }
  `;
  document.head.appendChild(style);

  new MutationObserver(function () {
    scheduleScan(false);
  }).observe(document.body, { childList: true, subtree: true });

  scan();
})();
