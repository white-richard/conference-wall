(function () {
  "use strict";

  let slides = [];
  let slideSeconds = 15;
  let currentIndex = 0;
  let isPaused = false;
  let timerId = null;

  // Simple seeded pseudo-random generator for deterministic testing via ?seed=...
  function createRandom(seedParam) {
    if (!seedParam) {
      return Math.random;
    }
    let s = 0;
    for (let i = 0; i < seedParam.length; i++) {
      s = (s << 5) - s + seedParam.charCodeAt(i);
      s |= 0;
    }
    return function () {
      s = (s + 0x6d2b79f5) | 0;
      let t = Math.imul(s ^ (s >>> 15), 1 | s);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const urlParams = new URLSearchParams(window.location.search);
  const seedParam = urlParams.get("seed");
  const randomFunc = createRandom(seedParam);

  function fisherYatesShuffle(array, lastSlideId) {
    const arr = array.slice();
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(randomFunc() * (i + 1));
      const temp = arr[i];
      arr[i] = arr[j];
      arr[j] = temp;
    }
    // Ensure first slide of new cycle isn't the same as last slide of previous cycle
    if (arr.length > 1 && lastSlideId && arr[0].id === lastSlideId) {
      const swapIdx = 1 + Math.floor(randomFunc() * (arr.length - 1));
      const tmp = arr[0];
      arr[0] = arr[swapIdx];
      arr[swapIdx] = tmp;
    }
    return arr;
  }

  function preloadImage(url) {
    if (url) {
      const img = new Image();
      img.src = url;
    }
  }

  function renderSlide(slide) {
    if (!slide) return;

    const slideImg = document.getElementById("slide-image");
    const acronymEl = document.getElementById("slide-acronym");
    const yearEl = document.getElementById("slide-year");
    const fullnameEl = document.getElementById("slide-fullname");
    const focusEl = document.getElementById("slide-focus");
    const locationEl = document.getElementById("slide-location");
    const deadlineEl = document.getElementById("slide-deadline");
    const commentEl = document.getElementById("slide-comment");
    const urlEl = document.getElementById("slide-url");
    const creditEl = document.getElementById("photo-credit");

    if (slideImg) {
      slideImg.src = slide.photo_path;
      slideImg.alt = slide.location_display || "Conference Location";
    }

    if (acronymEl) acronymEl.textContent = slide.acronym;
    if (yearEl) yearEl.textContent = " " + slide.year;
    if (fullnameEl) fullnameEl.textContent = slide.full_name;
    if (focusEl) focusEl.textContent = slide.primary_focus;
    if (locationEl) locationEl.textContent = slide.location_display;
    if (deadlineEl) deadlineEl.textContent = slide.deadline_text;

    if (urlEl) {
      if (slide.conference_url) {
        urlEl.href = slide.conference_url;
        urlEl.style.pointerEvents = "auto";
      } else {
        urlEl.removeAttribute("href");
        urlEl.style.pointerEvents = "none";
      }
    }

    if (commentEl) {
      if (slide.deadline_comment) {
        commentEl.textContent = slide.deadline_comment;
        commentEl.classList.remove("hidden");
      } else {
        commentEl.classList.add("hidden");
      }
    }

    if (creditEl) {
      if (slide.photo_source_url) {
        creditEl.innerHTML = `<a href="${slide.photo_source_url}" target="_blank" rel="noopener noreferrer">${slide.photo_credit}</a>`;
      } else {
        creditEl.textContent = slide.photo_credit || "";
      }
    }

    // Preload next image
    const nextIdx = (currentIndex + 1) % slides.length;
    if (slides[nextIdx] && slides[nextIdx].photo_path) {
      preloadImage(slides[nextIdx].photo_path);
    }
  }

  function nextSlide() {
    if (slides.length === 0) return;
    const lastSlideId = slides[currentIndex] ? slides[currentIndex].id : null;
    currentIndex++;
    if (currentIndex >= slides.length) {
      slides = fisherYatesShuffle(slides, lastSlideId);
      currentIndex = 0;
    }
    renderSlide(slides[currentIndex]);
    resetTimer();
  }

  function prevSlide() {
    if (slides.length === 0) return;
    currentIndex--;
    if (currentIndex < 0) {
      currentIndex = slides.length - 1;
    }
    renderSlide(slides[currentIndex]);
    resetTimer();
  }

  function togglePause() {
    isPaused = !isPaused;
    if (isPaused) {
      if (timerId) clearInterval(timerId);
    } else {
      resetTimer();
    }
  }

  function resetTimer() {
    if (timerId) clearInterval(timerId);
    if (!isPaused && slides.length > 1) {
      timerId = setInterval(nextSlide, slideSeconds * 1000);
    }
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch((err) => {
        console.warn("Fullscreen request failed:", err);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      }
    }
  }

  function initControls() {
    document.addEventListener("keydown", (e) => {
      if (e.key === "ArrowRight") {
        nextSlide();
      } else if (e.key === "ArrowLeft") {
        prevSlide();
      } else if (e.key === " " || e.code === "Space") {
        e.preventDefault();
        togglePause();
      } else if (e.key === "f" || e.key === "F") {
        toggleFullscreen();
      }
    });

    const container = document.getElementById("slideshow-container");
    if (container) {
      container.addEventListener("click", (e) => {
        // Prevent click if user clicked a link
        if (e.target.tagName === "A" || e.target.closest("a")) {
          return;
        }
        nextSlide();
      });
    }
  }

  function initSlideshow() {
    fetch("slides.json")
      .then((res) => {
        if (!res.ok) {
          throw new Error("Failed to load slides.json: " + res.status);
        }
        return res.json();
      })
      .then((data) => {
        if (data.slide_seconds) {
          slideSeconds = Number(data.slide_seconds) || 15;
        }
        const rawSlides = Array.isArray(data.slides) ? data.slides : [];
        if (rawSlides.length === 0) {
          const emptyState = document.getElementById("empty-state");
          if (emptyState) emptyState.classList.remove("hidden");
          return;
        }

        slides = fisherYatesShuffle(rawSlides, null);
        currentIndex = 0;
        renderSlide(slides[currentIndex]);
        initControls();
        resetTimer();
      })
      .catch((err) => {
        console.error("Error initializing confwall slideshow:", err);
        const emptyState = document.getElementById("empty-state");
        if (emptyState) {
          emptyState.querySelector(".empty-message").textContent =
            "No selected conference submission deadlines in the next four months.";
          emptyState.classList.remove("hidden");
        }
      });
  }

  document.addEventListener("DOMContentLoaded", initSlideshow);
})();
