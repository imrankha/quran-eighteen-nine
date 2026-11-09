"""Minimal Devanagari -> Hinglish (casual Roman script) transliteration."""

CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "w", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h", "ळ": "l",
    "क़": "q", "ख़": "kh", "ग़": "gh", "ज़": "z", "ड़": "r",
    "ढ़": "rh", "फ़": "f", "य़": "y",
}
NUKTA_FORMS = {"क": "क़", "ख": "ख़", "ग": "ग़", "ज": "ज़", "ड": "ड़", "ढ": "ढ़", "फ": "फ़", "य": "य़"}
VOWELS = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ॲ": "e",
}
MATRAS = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}
NASAL = {"ं": "n", "ँ": "n", "ः": "h"}
VIRAMA = "्"
NUKTA = "़"
INHERENT = "INHERENT"
SPECIAL_WORDS = {"allah": "Allah", "men": "mein", "ap": "aap"}


def _word_units(word):
    """Split a Devanagari word into [consonant, vowel, suffix] units.
    vowel is INHERENT, "" (virama) or a roman vowel."""
    units = []
    chars = list(word)
    i = 0
    while i < len(chars):
        ch = chars[i]
        if i + 1 < len(chars) and chars[i + 1] == NUKTA and ch in NUKTA_FORMS:
            ch = NUKTA_FORMS[ch]
            i += 1
        if ch in CONSONANTS:
            units.append([CONSONANTS[ch], INHERENT, ""])
        elif ch in VOWELS:
            units.append(["", VOWELS[ch], ""])
        elif ch in MATRAS and units:
            units[-1][1] = MATRAS[ch]
        elif ch == VIRAMA and units:
            units[-1][1] = ""
        elif ch in NASAL and units:
            if units[-1][1] == INHERENT:
                units[-1][1] = "a"
            units[-1][2] += NASAL[ch]
        elif ch != NUKTA:
            units.append([ch, "", ""])
        i += 1
    return units


def _has_vowel(unit):
    return unit[1] not in ("", None)


def _transliterate_word(word):
    units = _word_units(word)
    n = len(units)
    conjunct_ending = n > 1 and units[-2][1] == "" and units[-1][0] == "y"
    if n > 1 and units[-1][1] == INHERENT and not conjunct_ending:
        units[-1][1] = None
    i = n - 2
    while i >= 1:
        u, prev, nxt = units[i], units[i - 1], units[i + 1]
        if (
            u[1] == INHERENT
            and _has_vowel(prev)
            and nxt[0]
            and _has_vowel(nxt)
        ):
            u[1] = None
            i -= 2
            continue
        i -= 1
    out = "".join(
        c + ("a" if v == INHERENT else (v or "")) + suffix for c, v, suffix in units
    )
    return SPECIAL_WORDS.get(out.lower(), out)


def devanagari_to_hinglish(text):
    out, word = [], []
    for ch in text:
        if "\u0900" <= ch <= "\u097f" and ch not in "।॥":
            word.append(ch)
            continue
        if word:
            out.append(_transliterate_word("".join(word)))
            word = []
        out.append("." if ch in "।॥" else ch)
    if word:
        out.append(_transliterate_word("".join(word)))
    return "".join(out)


if __name__ == "__main__":
    for sample in ["ऐ लोगो जो", "ईमान लाए हो", "तुम मदद माँगो", "अल्लाह", "करने वालों", "नमाज़", "प्राप्त करो", "समझ", "धैर्य", "निःसंदेह"]:
        print(sample, "->", devanagari_to_hinglish(sample))
