/**
 * Zoom-on-hover: shows a magnified lens following the cursor.
 *
 * Usage:
 *   <div class="zoom-container" data-zoom-src="/path/to/full-res.jpg">
 *     <img src="/path/to/preview.jpg" class="zoom-img">
 *   </div>
 */
(function () {
  var LENS_SIZE = 280;

  function initZoom(container) {
    var img = container.querySelector(".zoom-img");
    if (!img) return;

    var zoomSrc = container.dataset.zoomSrc || img.src;

    // Create lens element using CSS background-image (most reliable zoom method)
    var lens = document.createElement("div");
    lens.className = "zoom-lens";
    Object.assign(lens.style, {
      position: "absolute",
      width: LENS_SIZE + "px",
      height: LENS_SIZE + "px",
      border: "2px solid rgba(200,169,110,0.7)",
      borderRadius: "50%",
      pointerEvents: "none",
      opacity: "0",
      transition: "opacity 0.15s",
      overflow: "hidden",
      zIndex: "100",
      boxShadow: "0 4px 24px rgba(0,0,0,0.5)",
      backgroundRepeat: "no-repeat",
    });

    container.style.position = "relative";
    container.style.cursor = "crosshair";
    container.appendChild(lens);

    // Preload full-res image to get natural dimensions
    var zoomImg = new Image();
    zoomImg.src = zoomSrc;
    var ready = false;

    function onReady() {
      ready = true;
      lens.style.backgroundImage = "url(" + zoomSrc + ")";
    }

    zoomImg.onload = onReady;
    if (zoomImg.complete && zoomImg.naturalWidth) onReady();

    container.addEventListener("mouseenter", function () {
      lens.style.opacity = "1";
    });

    container.addEventListener("mousedown", function () {
      lens.style.opacity = "0";
    });

    container.addEventListener("mouseup", function () {
      lens.style.opacity = "1";
    });

    container.addEventListener("mouseleave", function () {
      lens.style.opacity = "0";
    });

    container.addEventListener("mousemove", function (e) {
      if (!ready) return;

      var rect = img.getBoundingClientRect();
      var x = e.clientX - rect.left;
      var y = e.clientY - rect.top;

      // Position lens centered on cursor
      lens.style.left = (x - LENS_SIZE / 2) + "px";
      lens.style.top = (y - LENS_SIZE / 2) + "px";

      // Full-res image shown at natural size inside the lens
      var natW = zoomImg.naturalWidth;
      var natH = zoomImg.naturalHeight;
      lens.style.backgroundSize = natW + "px " + natH + "px";

      // Map cursor position on displayed image → full-res coordinates
      var ratioX = natW / rect.width;
      var ratioY = natH / rect.height;
      var bgX = -(x * ratioX - LENS_SIZE / 2);
      var bgY = -(y * ratioY - LENS_SIZE / 2);
      lens.style.backgroundPosition = bgX + "px " + bgY + "px";
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll(".zoom-container").forEach(initZoom);
  });

  window.initZoomOn = function (el) { initZoom(el); };
})();
