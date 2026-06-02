/*
 * blog-technical theme behaviour: color-scheme toggle, back-to-top button, and
 * per-code-block copy buttons. Vanilla JS, no dependencies. Configuration is
 * read from this script tag's data-* attributes so the template stays declarative.
 *
 * Behaviour adapted from hugo-PaperMod (MIT); see THEME-LICENSE.
 */
(function () {
  "use strict";
  var cfg = document.currentScript.dataset;

  // Light/dark toggle. The pre-paint script in <head> already set the initial
  // value; here we only wire the button to flip and persist the user's choice.
  if (cfg.themeToggle === "true") {
    var btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", function () {
        var el = document.documentElement;
        var next = el.dataset.theme === "dark" ? "light" : "dark";
        el.dataset.theme = next;
        localStorage.setItem("pref-theme", next);
      });
    }
  }

  // Back-to-top control: reveal it once the page is scrolled past one viewport.
  if (cfg.scrollTop === "true") {
    var top = document.getElementById("top-link");
    if (top) {
      window.addEventListener("scroll", function () {
        var y = document.documentElement.scrollTop || document.body.scrollTop;
        top.classList.toggle("hidden", y < window.innerHeight);
      });
    }
  }

  // Copy buttons on code blocks. Targets every <pre> holding a <code>; copies
  // the code's text and briefly swaps the label to confirm.
  if (cfg.codeCopy === "true") {
    var copyLabel = cfg.copyLabel || "copy";
    var copiedLabel = cfg.copiedLabel || "copied!";
    document.querySelectorAll("pre > code").forEach(function (code) {
      var pre = code.parentNode;
      if (pre.querySelector(".copy-code")) return;
      var button = document.createElement("button");
      button.className = "copy-code";
      button.type = "button";
      button.textContent = copyLabel;
      button.addEventListener("click", function () {
        navigator.clipboard.writeText(code.textContent).then(function () {
          button.textContent = copiedLabel;
          setTimeout(function () { button.textContent = copyLabel; }, 2000);
        });
      });
      pre.style.position = pre.style.position || "relative";
      pre.appendChild(button);
    });
  }
})();
