/* Minimal progressive enhancement: no external dependencies, no trackers. */
(function () {
  "use strict";

  // Auto-dismiss flash-like banners after a while (keeps them readable first).
  document.addEventListener("DOMContentLoaded", function () {
    var banners = document.querySelectorAll(".reminder-banner[role='status']");
    banners.forEach(function (b) {
      b.setAttribute("aria-live", "polite");
    });

    // Ensure keyboard users can skip to main content.
    var main = document.getElementById("main");
    if (main && !document.getElementById("skip-link")) {
      var link = document.createElement("a");
      link.id = "skip-link";
      link.href = "#main";
      link.textContent = "Skip to content";
      link.className = "btn btn-ghost btn-sm";
      link.style.position = "absolute";
      link.style.left = "-9999px";
      document.body.prepend(link);
      link.addEventListener("focus", function () {
        link.style.left = "8px";
        link.style.top = "8px";
        link.style.zIndex = "99";
        link.style.position = "fixed";
        link.style.background = "#fff";
      });
      link.addEventListener("blur", function () {
        link.style.left = "-9999px";
      });
    }
  });
})();
