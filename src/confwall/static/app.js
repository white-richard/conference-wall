(function () {
  "use strict";

  let slides = [];
  let slideSeconds = 15;
  let currentIndex = 0;
  let isPaused = false;
  let timerId = null;

  // Below this, the deadline is close enough to be worth a live ticking countdown.
  const COUNTDOWN_WINDOW_MS = 30 * 24 * 60 * 60 * 1000;

  // ?seed=... makes the shuffle reproducible so the browser test can assert an order.
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

  function shuffle(array, lastSlideId) {
    const arr = array.slice();
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(randomFunc() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    // Otherwise a reshuffle can show the same slide twice in a row across the wrap.
    if (arr.length > 1 && lastSlideId && arr[0].id === lastSlideId) {
      const swapIdx = 1 + Math.floor(randomFunc() * (arr.length - 1));
      [arr[0], arr[swapIdx]] = [arr[swapIdx], arr[0]];
    }
    return arr;
  }

  function preloadImage(url) {
    if (url) {
      const img = new Image();
      img.src = url;
    }
  }

  let countdownIntervalId = null;

  function renderSlide(slide) {
    if (!slide) return;

    if (countdownIntervalId) {
      clearInterval(countdownIntervalId);
      countdownIntervalId = null;
    }

    const slideImg = document.getElementById("slide-image");
    const acronymEl = document.getElementById("slide-acronym");
    const yearEl = document.getElementById("slide-year");
    const fullnameEl = document.getElementById("slide-fullname");
    const focusEl = document.getElementById("slide-focus");
    const publisherEl = document.getElementById("slide-publisher");
    const formatEl = document.getElementById("slide-format");
    const ranksEl = document.getElementById("slide-ranks");
    const locationEl = document.getElementById("slide-location");
    const deadlineEl = document.getElementById("slide-deadline");
    const commentEl = document.getElementById("slide-comment");
    const abstractBoxEl = document.getElementById("slide-abstract-box");
    const abstractEl = document.getElementById("slide-abstract");
    const countdownEl = document.getElementById("slide-countdown");
    const countdownTextEl = document.getElementById("slide-countdown-text");
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

    if (publisherEl) {
      if (slide.publisher_tag) {
        publisherEl.textContent = slide.publisher_tag;
        const pubClass = slide.publisher_tag.toLowerCase().replace(/[^a-z0-9]/g, "");
        publisherEl.className = `publisher-pill publisher-${pubClass}`;
        publisherEl.classList.remove("hidden");
      } else {
        publisherEl.classList.add("hidden");
      }
    }

    if (formatEl) {
      if (slide.format_tag) {
        formatEl.textContent = slide.format_tag;
        formatEl.className = `format-pill format-${slide.format_tag.toLowerCase().replace(/[^a-z0-9]/g, "")}`;
        formatEl.classList.remove("hidden");
      } else {
        formatEl.classList.add("hidden");
      }
    }

    if (ranksEl) {
      let ranksHtml = "";
      if (slide.rank_core) {
        ranksHtml += `<span class="rank-badge rank-core">CORE ${slide.rank_core}</span>`;
      }
      if (slide.rank_ccf) {
        ranksHtml += `<span class="rank-badge rank-ccf">CCF ${slide.rank_ccf}</span>`;
      }
      ranksEl.innerHTML = ranksHtml;
    }

    if (locationEl) locationEl.textContent = slide.location_display;
    if (deadlineEl) deadlineEl.textContent = slide.deadline_text;

    if (abstractBoxEl && abstractEl) {
      if (slide.abstract_deadline_text) {
        abstractEl.textContent = slide.abstract_deadline_text;
        abstractBoxEl.classList.remove("hidden");
      } else {
        abstractBoxEl.classList.add("hidden");
      }
    }

    function msUntilDeadline() {
      if (!slide.deadline_utc) return null;
      return new Date(slide.deadline_utc).getTime() - Date.now();
    }

    function updateCountdown() {
      if (!countdownEl || !countdownTextEl) return;
      const diffMs = msUntilDeadline();

      if (diffMs !== null && diffMs > 0 && diffMs <= COUNTDOWN_WINDOW_MS) {
        const totalSeconds = Math.floor(diffMs / 1000);
        const days = Math.floor(totalSeconds / (24 * 3600));
        const hours = Math.floor((totalSeconds % (24 * 3600)) / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        let timeStr = "";
        if (days > 0) {
          timeStr = `${days}d ${hours}h ${minutes}m ${seconds}s remaining!`;
        } else {
          timeStr = `${hours}h ${minutes}m ${seconds}s remaining!`;
        }

        countdownTextEl.textContent = timeStr;
        countdownEl.classList.remove("hidden");

        if (days <= 7) {
          countdownEl.classList.add("urgent");
        } else {
          countdownEl.classList.remove("urgent");
        }
      } else {
        countdownEl.classList.add("hidden");
      }
    }

    updateCountdown();
    const msLeft = msUntilDeadline();
    if (msLeft !== null && msLeft > 0 && msLeft <= COUNTDOWN_WINDOW_MS) {
      countdownIntervalId = setInterval(updateCountdown, 1000);
    }

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
      slides = shuffle(slides, lastSlideId);
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

  function updateFullscreenIcon() {
    const fsBtn = document.getElementById("fullscreen-btn");
    if (!fsBtn) return;
    const iconFs = fsBtn.querySelector(".icon-fullscreen");
    const iconExit = fsBtn.querySelector(".icon-exit-fullscreen");
    if (document.fullscreenElement) {
      if (iconFs) iconFs.classList.add("hidden");
      if (iconExit) iconExit.classList.remove("hidden");
      fsBtn.setAttribute("title", "Exit Fullscreen (Press F)");
    } else {
      if (iconFs) iconFs.classList.remove("hidden");
      if (iconExit) iconExit.classList.add("hidden");
      fsBtn.setAttribute("title", "Toggle Fullscreen (Press F)");
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

    const fsBtn = document.getElementById("fullscreen-btn");
    if (fsBtn) {
      fsBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        toggleFullscreen();
      });
    }

    document.addEventListener("fullscreenchange", updateFullscreenIcon);

    const container = document.getElementById("slideshow-container");
    if (container) {
      container.addEventListener("click", (e) => {
        if (
          e.target.tagName === "A" ||
          e.target.closest("a") ||
          e.target.tagName === "BUTTON" ||
          e.target.closest("button")
        ) {
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

        slides = shuffle(rawSlides, null);
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
