#!/usr/bin/env python3
"""Fetch every ayah containing "يا أيها الذين آمنوا" with translations and
word-by-word meanings, and write static JSON files into ./data."""
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from hinglish import devanagari_to_hinglish

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QURAN_COM = "https://api.quran.com/api/v4"
PHRASE = "يا أيها الذين آمنوا"

# code -> (label, native label, quran.com translation id, rtl)
TRANSLATIONS = {
    "ur": ("Urdu", "اردو", 234, True),
    "hinglish": ("Hinglish (Roman Urdu)", "Hinglish", 831, False),
    "en": ("English", "English", 20, False),
    "hi": ("Hindi", "हिन्दी", 122, False),
    "bn": ("Bengali", "বাংলা", 161, False),
    "ta": ("Tamil", "தமிழ்", 50, False),
    "te": ("Telugu", "తెలుగు", 227, False),
    "ml": ("Malayalam", "മലയാളം", 37, False),
    "mr": ("Marathi", "मराठी", 226, False),
    "gu": ("Gujarati", "ગુજરાતી", 225, False),
    "kn": ("Kannada", "ಕನ್ನಡ", 771, False),
    "fa": ("Persian", "فارسی", 29, True),
    "id": ("Indonesian", "Indonesia", 33, False),
    "tr": ("Turkish", "Türkçe", 77, False),
    "fr": ("French", "Français", 31, False),
    "es": ("Spanish", "Español", 83, False),
    "de": ("German", "Deutsch", 27, False),
    "ru": ("Russian", "Русский", 45, False),
}

# Word-by-word languages offered by quran.com (+ Hinglish derived from Hindi).
WBW = {
    "ur": ("Urdu", "اردو", True),
    "hinglish": ("Hinglish", "Hinglish", False),
    "en": ("English", "English", False),
    "hi": ("Hindi", "हिन्दी", False),
    "bn": ("Bengali", "বাংলা", False),
    "id": ("Indonesian", "Indonesia", False),
    "tr": ("Turkish", "Türkçe", False),
    "fa": ("Persian", "فارسی", True),
}


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "quran-eighteen-nine/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception:
            if attempt == 3:
                raise


def clean(text):
    text = re.sub(r"<sup[^>]*>.*?</sup>", "", text or "")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def find_verse_keys():
    surahs = get("https://api.alquran.cloud/v1/quran/quran-simple-clean")["data"]["surahs"]
    return [
        f"{s['number']}:{a['numberInSurah']}"
        for s in surahs
        for a in s["ayahs"]
        if PHRASE in a["text"]
    ]


def fetch_verse(key, wbw_lang, translation_ids=""):
    url = (
        f"{QURAN_COM}/verses/by_key/{key}?words=true&language={wbw_lang}"
        "&word_fields=text_uthmani&fields=text_uthmani"
    )
    if translation_ids:
        url += f"&translations={translation_ids}"
    return get(url)["verse"]


def main():
    keys = find_verse_keys()
    print(f"Found {len(keys)} ayaat")
    chapters = {c["id"]: c for c in get(f"{QURAN_COM}/chapters?language=en")["chapters"]}
    authors = {}
    for t in get(f"{QURAN_COM}/resources/translations")["translations"]:
        name = next(
            (n.strip() for n in (t["author_name"], t["name"])
             if n and n.strip() != "Unknown" and not n.strip().endswith("Translation")),
            "",
        )
        authors[t["id"]] = name
    tr_ids = ",".join(str(t[2]) for t in TRANSLATIONS.values())
    id_to_code = {t[2]: code for code, t in TRANSLATIONS.items()}

    with ThreadPoolExecutor(8) as pool:
        base = list(pool.map(lambda k: fetch_verse(k, "en", tr_ids), keys))
        wbw_raw = {
            lang: list(pool.map(lambda k, l=lang: fetch_verse(k, l), keys))
            for lang in WBW
            if lang != "hinglish"
        }

    verses = []
    translations = {code: {} for code in TRANSLATIONS}
    for key, v in zip(keys, base):
        s, a = map(int, key.split(":"))
        ch = chapters[s]
        words = [w for w in v["words"] if w["char_type_name"] == "word"]
        verses.append({
            "key": key,
            "surah": s,
            "ayah": a,
            "surahName": ch["name_simple"],
            "surahNameArabic": ch["name_arabic"],
            "surahMeaning": ch["translated_name"]["name"],
            "arabic": v["text_uthmani"],
            "words": [
                {"ar": w["text_uthmani"], "tl": w["transliteration"]["text"] or ""}
                for w in words
            ],
        })
        for t in v["translations"]:
            translations[id_to_code[t["resource_id"]]][key] = clean(t["text"])

    wbw = {}
    for lang, rows in wbw_raw.items():
        wbw[lang] = {}
        for key, v in zip(keys, rows):
            wbw[lang][key] = [
                clean(w["translation"]["text"])
                for w in v["words"]
                if w["char_type_name"] == "word"
            ]
        fallback = sum(
            1 for v in rows for w in v["words"]
            if w["char_type_name"] == "word" and w["translation"]["language_name"] != WBW[lang][0].lower()
        )
        print(f"wbw {lang}: {fallback} words fell back to another language")
    wbw["hinglish"] = {
        key: [devanagari_to_hinglish(m) for m in meanings]
        for key, meanings in wbw["hi"].items()
    }

    DATA.mkdir(exist_ok=True)
    (DATA / "translations").mkdir(exist_ok=True)
    (DATA / "wbw").mkdir(exist_ok=True)

    def dump(path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    dump(DATA / "verses.json", verses)
    dump(DATA / "languages.json", {
        "translations": [
            {"code": c, "label": t[0], "native": t[1], "rtl": t[3], "translator": authors.get(t[2], "")}
            for c, t in TRANSLATIONS.items()
        ],
        "wbw": [{"code": c, "label": w[0], "native": w[1], "rtl": w[2]} for c, w in WBW.items()],
    })
    for code, data in translations.items():
        assert len(data) == len(keys), f"missing translations for {code}"
        dump(DATA / "translations" / f"{code}.json", data)
    for code, data in wbw.items():
        dump(DATA / "wbw" / f"{code}.json", data)


if __name__ == "__main__":
    main()
