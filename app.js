(() => {
  const DEFAULT_LANGS = ["ur", "hinglish"];
  const STORAGE = { tr: "qa18.trLangs", wbw: "qa18.wbwLangs" };

  const els = {
    count: document.getElementById("count"),
    search: document.getElementById("search"),
    select: document.getElementById("ayah-select"),
    prev: document.getElementById("prev"),
    next: document.getElementById("next"),
    trLangs: document.getElementById("tr-langs"),
    wbwLangs: document.getElementById("wbw-langs"),
    ayah: document.getElementById("ayah"),
  };

  const cache = new Map();
  const state = { verses: [], languages: null, filtered: [], current: null, tr: [], wbw: [] };

  const loadJSON = (path) => {
    if (!cache.has(path)) {
      cache.set(path, fetch(path).then((r) => {
        if (!r.ok) throw new Error(`Failed to load ${path}`);
        return r.json();
      }).catch((err) => {
        cache.delete(path);
        throw err;
      }));
    }
    return cache.get(path);
  };
  const joinMarks = (text) => text.replace(/\s+([\u06D6-\u06DC\u06DF-\u06ED])/g, "$1");
  const translation = (code) => loadJSON(`data/translations/${code}.json`);
  const wordByWord = (code) => loadJSON(`data/wbw/${code}.json`);

  const readPref = (key, valid) => {
    try {
      const saved = JSON.parse(localStorage.getItem(key));
      if (Array.isArray(saved)) {
        const ok = saved.filter((c) => valid.includes(c));
        if (ok.length) return ok;
      }
    } catch (_) { /* ignore */ }
    return DEFAULT_LANGS.filter((c) => valid.includes(c));
  };
  const savePref = (key, value) => {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (_) { /* ignore */ }
  };

  const el = (tag, attrs = {}, ...children) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === "class") node.className = v;
      else node.setAttribute(k, v);
    }
    for (const child of children) {
      if (child !== null && child !== undefined) node.append(child);
    }
    return node;
  };

  function renderChips(container, langs, selected, onChange) {
    container.replaceChildren(...langs.map((lang) => {
      const chip = el("button", {
        type: "button",
        class: "chip",
        "aria-pressed": String(selected.includes(lang.code)),
        title: lang.translator ? `${lang.label} — ${lang.translator}` : lang.label,
      }, lang.label);
      chip.addEventListener("click", () => {
        const on = selected.includes(lang.code);
        if (on && selected.length === 1) return;
        const next = on
          ? selected.filter((c) => c !== lang.code)
          : langs.map((l) => l.code).filter((c) => c === lang.code || selected.includes(c));
        onChange(next);
      });
      return chip;
    }));
  }

  function renderLanguageControls() {
    renderChips(els.trLangs, state.languages.translations, state.tr, (next) => {
      state.tr = next;
      savePref(STORAGE.tr, next);
      renderLanguageControls();
      renderAyah();
    });
    renderChips(els.wbwLangs, state.languages.wbw, state.wbw, (next) => {
      state.wbw = next;
      savePref(STORAGE.wbw, next);
      renderLanguageControls();
      renderAyah();
    });
  }

  const VOCATIVE = /^\s*a(?:ey|e|ye|y)\b[^.]{0,40}?\b(?:ho|walon|walo)\b\s*[,!.]?/i;

  function optionLabel(v, index, hinglish) {
    let snippet = (hinglish[v.key] || "").replace(VOCATIVE, "").replace(/^[\s,!.]+/, "");
    snippet = snippet.charAt(0).toUpperCase() + snippet.slice(1);
    const short = snippet.length > 70 ? `${snippet.slice(0, 70)}…` : snippet;
    return `${index + 1}. ${v.surahName} ${v.key} — ${short}`;
  }

  async function renderSelect() {
    const [hinglish, en] = await Promise.all([translation("hinglish"), translation("en")]);
    const q = els.search.value.trim().toLowerCase();
    state.filtered = state.verses.filter((v) => {
      if (!q) return true;
      return [v.key, v.surahName, v.surahMeaning, String(v.surah), hinglish[v.key], en[v.key]]
        .some((s) => (s || "").toLowerCase().includes(q));
    });
    els.select.replaceChildren(...state.filtered.map((v) => {
      const index = state.verses.indexOf(v);
      return el("option", { value: v.key }, optionLabel(v, index, hinglish));
    }));
    if (!state.filtered.length) {
      els.select.append(el("option", { value: "", disabled: "" }, "No matching ayah"));
    } else if (state.filtered.some((v) => v.key === state.current)) {
      els.select.value = state.current;
    }
    updateNav();
  }

  function updateNav() {
    const i = state.verses.findIndex((v) => v.key === state.current);
    els.prev.disabled = i <= 0;
    els.next.disabled = i < 0 || i >= state.verses.length - 1;
  }

  function select(key, { pushHash = true } = {}) {
    if (!state.verses.some((v) => v.key === key)) return;
    state.current = key;
    if ([...els.select.options].some((o) => o.value === key)) els.select.value = key;
    if (pushHash && location.hash.slice(1) !== key) history.replaceState(null, "", `#${key}`);
    updateNav();
    renderAyah();
  }

  let renderToken = 0;
  async function renderAyah() {
    const verse = state.verses.find((v) => v.key === state.current);
    if (!verse) {
      els.ayah.replaceChildren(el("p", { class: "empty" }, "Select an ayah to see its meaning."));
      return;
    }
    const token = ++renderToken;
    const langs = state.languages;
    const trLangs = state.tr.map((c) => langs.translations.find((l) => l.code === c));
    const wbwLangs = state.wbw.map((c) => langs.wbw.find((l) => l.code === c));

    let trData, wbwData;
    try {
      [trData, wbwData] = await Promise.all([
        Promise.all(trLangs.map((l) => translation(l.code))),
        Promise.all(wbwLangs.map((l) => wordByWord(l.code))),
      ]);
    } catch (err) {
      if (token === renderToken) {
        els.ayah.replaceChildren(el("p", { class: "empty" }, `Could not load data: ${err.message}`));
      }
      return;
    }
    if (token !== renderToken) return;

    const index = state.verses.indexOf(verse);
    const head = el("div", { class: "ayah-head" },
      el("div", {},
        el("h2", {}, `${verse.surahName} `, el("span", { class: "meta" }, `(${verse.surahMeaning})`)),
        el("span", { class: "meta" }, `Surah ${verse.surah}, Ayah ${verse.ayah} · `),
        el("span", { class: "badge" }, `${index + 1} / ${state.verses.length}`)),
      el("span", { class: "surah-ar", lang: "ar", dir: "rtl" }, verse.surahNameArabic));

    const arabic = el("p", { class: "arabic", lang: "ar", dir: "rtl" }, joinMarks(verse.arabic));

    const words = el("div", { class: "words" }, ...verse.words.map((w, i) => el("div", { class: "word" },
      el("div", { class: "w-ar", lang: "ar", dir: "rtl" }, joinMarks(w.ar)),
      w.tl ? el("div", { class: "w-tl" }, w.tl) : null,
      ...wbwLangs.map((l, j) => el("div", {
        class: "w-m",
        lang: l.code === "hinglish" ? "en" : l.code,
        dir: l.rtl ? "rtl" : "ltr",
        title: l.label,
      }, (wbwData[j][verse.key] || [])[i] || "")))));

    const translations = trLangs.map((l, j) => el("div", {
      class: "translation",
      lang: l.code === "hinglish" ? "en" : l.code,
      dir: l.rtl ? "rtl" : "ltr",
    },
      el("div", { class: "t-label" }, `${l.label} `, l.translator ? el("small", {}, `— ${l.translator}`) : null),
      el("p", {}, trData[j][verse.key] || "")));

    els.ayah.replaceChildren(
      head,
      arabic,
      el("h3", { class: "section-title" }, `Word by word (${wbwLangs.map((l) => l.label).join(" · ")})`),
      words,
      el("h3", { class: "section-title" }, "Translation"),
      ...translations,
    );
  }

  function step(delta) {
    const i = state.verses.findIndex((v) => v.key === state.current);
    const next = state.verses[i + delta];
    if (!next) return;
    if (!state.filtered.includes(next)) {
      els.search.value = "";
      renderSelect().then(() => select(next.key));
    } else {
      select(next.key);
    }
  }

  async function init() {
    try {
      [state.verses, state.languages] = await Promise.all([
        loadJSON("data/verses.json"),
        loadJSON("data/languages.json"),
      ]);
    } catch (err) {
      els.ayah.replaceChildren(el("p", { class: "empty" }, `Could not load data: ${err.message}`));
      return;
    }
    els.count.textContent = state.verses.length;
    state.tr = readPref(STORAGE.tr, state.languages.translations.map((l) => l.code));
    state.wbw = readPref(STORAGE.wbw, state.languages.wbw.map((l) => l.code));
    renderLanguageControls();

    const fromHash = decodeURIComponent(location.hash.slice(1));
    state.current = state.verses.some((v) => v.key === fromHash) ? fromHash : state.verses[0].key;
    await renderSelect();
    select(state.current, { pushHash: false });

    els.select.addEventListener("change", () => select(els.select.value));
    els.search.addEventListener("input", async () => {
      await renderSelect();
      if (state.filtered.length && !state.filtered.some((v) => v.key === state.current)) {
        select(state.filtered[0].key);
      }
    });
    els.prev.addEventListener("click", () => step(-1));
    els.next.addEventListener("click", () => step(1));
    window.addEventListener("hashchange", () => select(decodeURIComponent(location.hash.slice(1)), { pushHash: false }));
    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, select, textarea")) return;
      if (e.key === "ArrowLeft") step(-1);
      if (e.key === "ArrowRight") step(1);
    });
  }

  init();
})();
