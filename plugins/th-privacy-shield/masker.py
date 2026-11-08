"""Local PII detection, validation and tokenisation for Saudi legal documents.

Everything here runs on the user's machine. Raw values never leave this module except
through the Vault (DPAPI-encrypted on disk) and explicit local unmasking.

Token format sent to the model:   ⟦CAT-n|status|hints⟧
    ⟦NID-3|ok⟧                 valid Saudi national ID
    ⟦NID-4|BAD:checksum|~NID-3⟧ fails checksum, one/two digits away from NID-3
    ⟦NAME-2|parts=4|≈NAME-1⟧    same name as NAME-1 after normalisation, but spelled differently
"""
from __future__ import annotations

import re
import threading
import unicodedata
from dataclasses import dataclass, field
from typing import Callable, Optional

# ----------------------------------------------------------------------------- normalisation
_DIGIT_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_PRESENTATION_FORMS = re.compile(r"[\uFB50-\uFDFF\uFE70-\uFEFF]")
_HARAKAT = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_BIDI = "\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"


_JSON_ESC = re.compile(r"\\u(06[0-9a-fA-F]{2}|0[eE][0-9a-fA-F]{2}|[fF][bBcCdDeE][0-9a-fA-F]{2}|20[0-6][0-9a-fA-F])")


def prepare(text: str) -> str:
    """Decode JSON-escaped Arabic (\\u0645...) and fold presentation forms into base letters."""
    if "\\u" in text:
        text = _JSON_ESC.sub(lambda m: chr(int(m.group(1), 16)), text)
    if _PRESENTATION_FORMS.search(text):
        text = unicodedata.normalize("NFKC", text)
    return text


def digits_view(text: str) -> str:
    """Same length as ``text``; Arabic-Indic digits become ASCII so regex spans line up."""
    return text.translate(_DIGIT_MAP)


def norm_arabic_name(s: str) -> str:
    s = _HARAKAT.sub("", s)
    s = re.sub("[أإآٱ]", "ا", s)
    s = s.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"\bعبد\s+ال", "عبدال", s)
    s = re.sub(r"\bابو\s+", "ابو", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def only_digits(s: str) -> str:
    return re.sub(r"\D", "", digits_view(s))


def levenshtein(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            best = min(best, v)
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]


# ----------------------------------------------------------------------------- validators
def saudi_id_checksum(d: str) -> bool:
    if len(d) != 10 or not d.isdigit():
        return False
    total = 0
    for i, ch in enumerate(d):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            total += n // 10 + n % 10
        else:
            total += n
    return total % 10 == 0


def iban_ok(raw: str) -> bool:
    s = re.sub(r"\s", "", digits_view(raw)).upper()
    if not re.fullmatch(r"SA\d{2}[0-9A-Z]{20}", s):
        return False
    r = s[4:] + s[:4]
    num = "".join(str(int(c, 36)) for c in r)
    return int(num) % 97 == 1


SA_BANKS = {
    "10": "SNB", "20": "Riyad", "30": "ANB", "45": "SAB", "55": "BSF", "60": "AlJazira",
    "65": "SAIB", "80": "AlRajhi", "05": "Alinma", "15": "AlBilad",
}

# ----------------------------------------------------------------------------- detectors
AR = r"\u0621-\u064A\u0660-\u0669\u0671-\u06D3\u064B-\u0652\u0640"
AW = rf"[{AR}]+"  # one Arabic word
NAME_UNIT = rf"(?:(?:عبد|أبو|ابو)[ 	\u00a0]*{AW}|{AW})"
GAP = rf"[\s\-\.{_BIDI}]?"  # allowed separator inside numbers


@dataclass
class Span:
    start: int
    end: int
    cat: str
    raw: str
    prio: int
    ctx: str = ""


NAME_STOP = set(
    """رقم هوية الهوية الهويه بطاقة سجل السجل الجنسية الجنسيه سعودي سعودية سعوديه الجنس بموجب وذلك
    حفيظة حفيظه المقيم المقيمة الساكن الساكنة ويحمل يحمل تحمل وتحمل تاريخ بتاريخ من في على عن الى إلى
    وهو وهي هو هي الذي التي المذكور المذكورة المذكوره المشار وفقا وفق حسب لدى بصفته بصفتها بصفته
    ويسكن ويقيم يسكن يقيم المولود المولودة مواليد ومقره مقره ومقرها صاحب صاحبة الهاتف جوال الجوال
    عنوانه عنوانها والمقيم والساكن ضد بشأن بخصوص والمدعى والمدعي وكيل وكيله وكيلها المحامي و""".split()
)
HONORIFICS = (
    "السيد|السيدة|السيده|المواطن|المواطنة|المواطنه|المقيم|المقيمة|الشيخ|الشيخة|المرحوم|المرحومة|"
    "المتوفى|المتوفاة|الأستاذ|الأستاذة|الاستاذ|الاستاذة|الدكتور|الدكتورة|المهندس|المهندسة|"
    "الأخ|الأخت|الاخ|الاخت|فضيلة|سعادة|معالي|ورثة|الورثة"
)
ROLE_LABELS = (
    "الاسم|اسم العميل|اسم الموكل|اسم الموكلة|الاسم الكامل|الاسم الرباعي|اسم المدعي|اسم المدعى عليه|"
    "المدعي|المدعية|المدعى عليه|المدعى عليها|المدعي عليه|الموكل|الموكلة|الوكيل|الوكيلة|"
    "المستأجر|المؤجر|البائع|المشتري|الكفيل|المدين|الدائن|الشاهد|الطرف الأول|الطرف الثاني|"
    "المالك|المورث|الوارث|المستفيد|مقدم الطلب|صاحب الطلب|العميل|بواسطة|تم الرفع بواسطة|تم إنشاؤه بواسطة|"
    "المحامي الرئيسي|المسؤول|المكلف|الموظف|المستخدم|المرسل|المستلم|اسم الدائن|اسم المدين|"
    "العملاء الأفراد|العميل الفرد|الخصم|الخصوم|القاضي|اسم القاضي|الأطراف|الطرف"
)
LATIN_LABELS = r"(?:Mr|Mrs|Ms|Miss|Dr|Name|Full Name|Client|Plaintiff|Defendant)"

RE_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
RE_IBAN = re.compile(rf"\bSA{GAP}\d{{2}}(?:{GAP}[0-9A-Z]){{18,23}}\b", re.I)
RE_PHONE = re.compile(
    rf"(?<![\d])(?:(?:\+|00){GAP}?966{GAP}?|0)(?:5\d|1\d)(?:{GAP}?\d){{7}}(?!\d)"
)
RE_PHONE_966 = re.compile(rf"(?<![\d])966{GAP}?5(?:{GAP}?\d){{8}}(?!\d)")
RE_TEN = re.compile(r"(?<!\d)\d{10}(?!\d)")
RE_LONGNUM = re.compile(r"(?<![\d,.])\d{8,}(?![\d,.]\d)")
RE_SHORTADDR = re.compile(r"\b[A-Z]{4}\d{4}\b")
RE_PASSPORT = re.compile(r"(?:جواز(?:\s+ال)?\s*سفر|رقم الجواز|Passport(?:\s*No\.?)?)\s*[:#/]?\s*([A-Z]{1,2}\d{6,8}|\d{8,9})", re.I)
RE_BLDG = re.compile(r"(?:رقم المبنى|رقم المبني|المبنى|Building(?:\s*No\.?)?)\s*[:/]?\s*(\d{1,6})")
RE_POSTAL = re.compile(r"(?:الرمز البريدي|ص\.?\s?ب|Postal\s*Code|Zip)\s*[:/]?\s*(\d{3,6})")
RE_ADDNUM = re.compile(r"(?:الرقم الإضافي|الرقم الاضافي|Additional\s*No\.?)\s*[:/]?\s*(\d{1,6})")
RE_STREET = re.compile(rf"(?<![{AR}])(?:حي|الحي|شارع|ش\.)[ 	\u00a0]*[:/]?[ 	\u00a0]*((?:{AW})(?:[ 	\u00a0]+{AW}){{0,3}})")
RE_HONOR = re.compile(rf"(?<![{AR}])(?:{HONORIFICS})[ 	\u00a0]*[:/]?[ 	\u00a0]*((?:{NAME_UNIT})(?:[ 	\u00a0]+{NAME_UNIT}){{0,6}})")
RE_ROLE = re.compile(rf"(?<![{AR}])(?:{ROLE_LABELS})[ 	\u00a0]*[:/][ 	\u00a0]*((?:{NAME_UNIT})(?:[ 	\u00a0]+{NAME_UNIT}){{0,6}})")
RE_CHAIN = re.compile(
    rf"(?<![{AR}])((?:{NAME_UNIT})[ 	\u00a0]+(?:بن|بنت|ابن|ابنة)[ 	\u00a0]+{NAME_UNIT}"
    rf"(?:[ 	\u00a0]+(?:بن|بنت)[ 	\u00a0]+{NAME_UNIT})*(?:[ 	\u00a0]+(?:آل[ 	\u00a0]+{AW}|ال{AW}))?)"
)
RE_LATIN_NAME = re.compile(rf"\b{LATIN_LABELS}\.?[ 	\u00a0]*[:/]?[ 	\u00a0]*((?:[A-Z][a-z'\-]+)(?:[ 	\u00a0]+[A-Z][a-z'\-]+){{1,5}})")

CR_CTX = rf"سجل\s*تجاري|السجل التجاري|(?<![{AR}])س\.?\s?ت(?![{AR}])|\bCR\b"

NUM_CONTEXT = [
    (re.compile(r"صك|الصك"), "DEED"),
    (re.compile(CR_CTX), "CR"),
    (re.compile(r"قضية|القضية|دعوى|الدعوى|طلب"), "CASE"),
    (re.compile(r"عقد|العقد"), "CONTRACT"),
    (re.compile(r"حساب|الحساب"), "ACCT"),
    (re.compile(r"وكالة|الوكالة"), "POA"),
    (re.compile(r"هوية|الهوية|إقامة|اقامة|الإقامة|الاقامة|حفيظة|سجل مدني|السجل المدني|ID|Iqama", re.I), "ID"),
]


def _trim_name(words_text: str) -> str:
    """Cut a captured name at the first stop word; keep 'عبد X' / 'بن' joints intact."""
    words = words_text.split()
    kept: list[str] = []
    for w in words:
        if w in NAME_STOP or (w.startswith("و") and w[1:] in NAME_STOP):
            break
        kept.append(w)
    while kept and kept[-1] in ("بن", "بنت", "ابن", "ابنة", "آل", "عبد", "أبو", "ابو"):
        kept.pop()
    return " ".join(kept)


def _context(text: str, start: int, width: int = 40) -> str:
    return text[max(0, start - width):start]


def _load_lexicon():
    import os
    strong, weak = set(), set()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "names_ar.txt")
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            amb = line.startswith("?")
            n = norm_arabic_name(line.lstrip("?"))
            (weak if amb else strong).add(n)
    except OSError:
        pass
    return strong, weak - strong


LEX_STRONG, LEX_WEAK = _load_lexicon()
LEX_ALL = LEX_STRONG | LEX_WEAK
CONNECTORS = {"بن", "بنت", "ابن", "ابنه", "ابو", "ام", "ال"}  # normalised forms ("آل" -> "ال")
COMMON_TRAIL_STOP = set(norm_arabic_name(w) for w in """
    المذكور المذكوره المدعي المدعيه المدعى المدين الدائن المحكمه الشركه المؤسسه الوكيل الموكل المحامي
    المحاميه المستشفى المكتب القضيه الدعوى الطلب العقد الحكم القرار النظام اللائحه المرفقات المستندات
    المبلغ الريال الريالات التاريخ الموافق الهجري الميلادي الرياض جده مكه المدينه الدمام الخبر الشرقيه
    التخصصي التجاري المحدوده القابضه العامه السعوديه السعودي العربيه الاول الثاني الثالث الاخير الجديد
    القديم التالي الحالي المختص المختصه الموقر الموقره الكريم المحترم المحترمه وفقه الله رحمه الله
    عليه السلام النبي الرسول الكريمه المالي الماليه الاداري الاداريه الوطني الوطنيه الالكتروني
""".split())


_AR_WORD = re.compile(rf"[{AR}]+")


def find_lexicon_names(text: str) -> list[tuple[int, int]]:
    """Spans of name sequences that start with a known given name (no label needed)."""
    words = [(m.start(), m.end(), m.group(0)) for m in _AR_WORD.finditer(text)]
    spans: list[tuple[int, int]] = []

    def adjacent(a, b) -> bool:  # only whitespace between the two words, no newline/punctuation
        gap = text[words[a][1]:words[b][0]]
        return len(gap) <= 3 and gap.strip(" \t\u00a0" + _BIDI) == ""

    def norm_at(k: int) -> tuple[str, int]:
        """Normalised word at k, joining 'عبد X' / 'أبو X'; returns (norm, words consumed)."""
        n = norm_arabic_name(words[k][2])
        if n in ("عبد", "ابو") and k + 1 < len(words) and adjacent(k, k + 1):
            return n + norm_arabic_name(words[k + 1][2]), 2
        return n, 1

    def is_name_word(n: str, raw: str) -> bool:
        if raw == "على":  # the preposition, not the name
            return False
        if n in LEX_ALL:
            return True
        if n.startswith("و") and n[1:] in LEX_STRONG:
            return True
        return False

    i = 0
    while i < len(words):
        n, used = norm_at(i)
        raw = words[i][2]
        if not is_name_word(n, raw):
            i += 1
            continue
        weak = (n in LEX_WEAK) or (n.startswith("و") and n[1:] in LEX_WEAK)
        j = i + used  # next word index
        names_in_seq = 1
        while j < len(words) and adjacent(j - 1, j):
            nj, uj = norm_at(j)
            if is_name_word(nj, words[j][2]):
                names_in_seq += 1
                j += uj
                continue
            if nj in CONNECTORS and j + 1 < len(words) and adjacent(j, j + 1):
                j += 1
                continue
            break
        if weak and names_in_seq < 2:
            i += 1
            continue
        # one trailing family name: al-prefixed (القحطاني) or nisba (زهراني), not a common word
        if j < len(words) and adjacent(j - 1, j):
            tn = norm_arabic_name(words[j][2])
            if tn not in COMMON_TRAIL_STOP and len(tn) >= 4 and (tn.startswith("ال") or tn.endswith("ي")):
                j += 1
        # drop a dangling connector at the end
        while j - 1 > i and norm_arabic_name(words[j - 1][2]) in CONNECTORS:
            j -= 1
        spans.append((words[i][0], words[j - 1][1]))
        i = j
    return spans


def find_spans(text: str, known_names: list[str]) -> list[Span]:
    dv = digits_view(text)
    spans: list[Span] = []
    add = spans.append
    for a, b in find_lexicon_names(text):
        add(Span(a, b, "NAME", text[a:b], 62))

    for m in RE_EMAIL.finditer(dv):
        add(Span(m.start(), m.end(), "EMAIL", text[m.start():m.end()], 90))
    for m in RE_IBAN.finditer(dv):
        add(Span(m.start(), m.end(), "IBAN", text[m.start():m.end()], 95))
    for m in RE_SHORTADDR.finditer(dv):
        add(Span(m.start(), m.end(), "SHORTADDR", text[m.start():m.end()], 70))
    for rx, cat in ((RE_PASSPORT, "PASSPORT"), (RE_BLDG, "BLDG"), (RE_POSTAL, "POSTAL"), (RE_ADDNUM, "ADDNUM")):
        for m in rx.finditer(dv):
            add(Span(m.start(1), m.end(1), cat, text[m.start(1):m.end(1)], 75))
    for rx in (RE_PHONE, RE_PHONE_966):
        for m in rx.finditer(dv):
            add(Span(m.start(), m.end(), "PHONE", text[m.start():m.end()], 88))
    for m in RE_TEN.finditer(dv):
        d = m.group(0)
        ctx = _context(dv, m.start())
        if re.search(CR_CTX, ctx):
            cat = "CR"
        elif d[0] == "1":
            cat = "NID"
        elif d[0] == "2":
            cat = "IQAMA"
        elif d[0] == "7":
            cat = "UNIFIED"
        else:
            cat = "NUM"
        add(Span(m.start(), m.end(), cat, text[m.start():m.end()], 85, ctx))
    for m in RE_LONGNUM.finditer(dv):
        add(Span(m.start(), m.end(), "NUM", text[m.start():m.end()], 40, _context(dv, m.start())))
    for m in RE_STREET.finditer(text):
        val = _trim_name(m.group(1))
        if val:
            add(Span(m.start(1), m.start(1) + len(val), "ADDR", val, 50))
    for rx, prio in ((RE_HONOR, 65), (RE_ROLE, 66), (RE_CHAIN, 60)):
        for m in rx.finditer(text):
            val = _trim_name(m.group(1))
            if val and len(val) >= 3:
                add(Span(m.start(1), m.start(1) + len(val), "NAME", val, prio))
    for m in RE_LATIN_NAME.finditer(text):
        add(Span(m.start(1), m.end(1), "NAME", m.group(1), 60))
    # every name already known to the vault, in any spelling variant
    for name in known_names:
        rx = _variant_regex(name)
        if rx is None:
            continue
        for m in rx.finditer(text):
            add(Span(m.start(), m.end(), "NAME", m.group(0), 64))
    return spans


_VARIANT_CACHE: dict[str, Optional[re.Pattern]] = {}
_VARIANT_LOCK = threading.Lock()


def _variant_regex(name: str) -> Optional[re.Pattern]:
    with _VARIANT_LOCK:
        if name in _VARIANT_CACHE:
            return _VARIANT_CACHE[name]
    n = norm_arabic_name(name)
    if len(n.replace(" ", "")) < 6 or " " not in n:  # single short words would over-mask
        rx = None
    else:
        harakat = "[\u064B-\u0652\u0670\u0640]*"
        parts = []
        for ch in n:
            if ch == " ":
                parts.append(r"[ 	\u00a0]*")
                continue
            cls = {"ا": "[اأإآٱ]", "ه": "[هة]", "ي": "[يىئ]", "و": "[وؤ]"}.get(ch, re.escape(ch))
            parts.append(cls + harakat)
        # 'عبدال' may be written with a space
        pat = "".join(parts)
        pat = pat.replace(re.escape("د") + harakat + "[اأإآٱ]" + harakat + re.escape("ل"),
                          re.escape("د") + harakat + r"[ 	\u00a0]*" + "[اأإآٱ]" + harakat + re.escape("ل"))
        rx = re.compile(rf"(?<![{AR}]){pat}(?![{AR}])")
    with _VARIANT_LOCK:
        _VARIANT_CACHE[name] = rx
    return rx


def resolve(spans: list[Span]) -> list[Span]:
    """Keep non-overlapping spans: higher priority, then longer, wins."""
    spans = sorted(spans, key=lambda s: (-s.prio, -(s.end - s.start), s.start))
    taken: list[Span] = []
    for s in spans:
        if any(not (s.end <= t.start or s.start >= t.end) for t in taken):
            continue
        taken.append(s)
    return sorted(taken, key=lambda s: s.start)


# ----------------------------------------------------------------------------- validation
def validate(cat: str, raw: str, ctx: str = "") -> tuple[str, list[str]]:
    """Return (status, hints). Status is 'ok' or 'BAD:<reason>'."""
    hints: list[str] = []
    d = only_digits(raw)
    if cat in ("NID", "IQAMA"):
        if len(d) != 10:
            return "BAD:length", hints
        want = "1" if cat == "NID" else "2"
        if d[0] != want:
            return "BAD:prefix", hints
        return ("ok" if saudi_id_checksum(d) else "BAD:checksum"), hints
    if cat == "UNIFIED":
        return ("ok" if len(d) == 10 else "BAD:length"), hints
    if cat == "CR":
        return ("ok" if len(d) == 10 else "BAD:length"), hints
    if cat == "IBAN":
        s = re.sub(r"[\s\-\.]", "", digits_view(raw)).upper()
        if len(s) != 24:
            return f"BAD:length={len(s)}", hints
        if s[4:6] in SA_BANKS:
            hints.append(f"bank={SA_BANKS[s[4:6]]}")
        else:
            hints.append(f"bankcode={s[4:6]}")
        return ("ok" if iban_ok(s) else "BAD:checksum"), hints
    if cat == "PHONE":
        local = d
        if local.startswith("00966"):
            local = "0" + local[5:]
        elif local.startswith("966"):
            local = "0" + local[3:]
        if re.fullmatch(r"05\d{8}", local):
            hints.append("mobile")
            return "ok", hints
        if re.fullmatch(r"01\d{8}", local):
            hints.append("landline")
            return "ok", hints
        return "BAD:format", hints
    if cat == "EMAIL":
        return "ok", hints
    if cat == "BLDG":
        return ("ok" if len(d) == 4 else f"BAD:digits={len(d)}(need4)"), hints
    if cat == "ADDNUM":
        return ("ok" if len(d) == 4 else f"BAD:digits={len(d)}(need4)"), hints
    if cat == "POSTAL":
        return ("ok" if len(d) == 5 else f"BAD:digits={len(d)}(need5)"), hints
    if cat == "SHORTADDR":
        return "ok", hints
    if cat == "PASSPORT":
        return "ok", hints
    if cat == "NAME":
        hints.append(f"parts={len(norm_arabic_name(raw).split())}")
        return "ok", hints
    if cat == "NUM":
        hints.append(f"len={len(d)}")
        for rx, label in NUM_CONTEXT:
            if rx.search(ctx):
                hints.append(f"ctx={label}")
                if label == "ID" and len(d) != 10:
                    return "BAD:id-length", hints
                break
        return "ok", hints
    return "ok", hints


# ----------------------------------------------------------------------------- vault + masking
TOKEN_RE = re.compile(r"(?:⟦|\[\[)([A-Z]+)-(\d+)(?:\|[^⟧\]\n]{0,120})?(?:⟧|\]\])")


@dataclass
class Entry:
    cat: str
    n: int
    raw: str
    key: str
    status: str
    hints: list[str] = field(default_factory=list)

    @property
    def tid(self) -> str:
        return f"{self.cat}-{self.n}"

    def token(self) -> str:
        bits = [self.tid, self.status] + self.hints
        return "⟦" + "|".join(bits) + "⟧"


def _key(cat: str, raw: str) -> str:
    if cat == "NAME" or cat == "ADDR":
        return cat + ":" + re.sub(r"\s+", " ", _HARAKAT.sub("", raw)).strip()
    if cat == "EMAIL":
        return cat + ":" + raw.lower()
    if cat in ("IBAN", "SHORTADDR", "PASSPORT"):
        return cat + ":" + re.sub(r"[\s\-\.]", "", digits_view(raw)).upper()
    return cat + ":" + only_digits(raw)


class Vault:
    """Bidirectional raw<->token map. Persistence is injected (see vault_store.py).

    With ``store`` (an object with load/save/lock/mtime), the vault is shared safely between
    processes: before assigning a new token it re-reads the file under a lock, so two processes
    never hand out the same token number for different values.
    """

    def __init__(self, load: Callable[[], dict] | None = None, save: Callable[[dict], None] | None = None,
                 store=None):
        self._lock = threading.RLock()
        self._store = store
        self._save = save or (store.save if store else None)
        self._load = load or (store.load if store else None)
        self._mtime = None
        self.by_key: dict[str, Entry] = {}
        self.by_tid: dict[str, Entry] = {}
        self.counters: dict[str, int] = {}
        self._reload()

    def _reload(self) -> None:
        if not self._load:
            return
        try:
            data = self._load() or {}
        except Exception:
            return
        for e in data.get("entries", []):
            try:
                ent = Entry(**e)
            except TypeError:
                continue
            self.by_key[ent.key] = ent
            self.by_tid[ent.tid] = ent
        for k, v in (data.get("counters") or {}).items():
            self.counters[k] = max(int(v), self.counters.get(k, 0))
        if self._store:
            self._mtime = self._store.mtime()

    def _refresh_if_changed(self) -> None:
        if self._store and self._store.mtime() != self._mtime:
            self._reload()

    def dump(self) -> dict:
        return {
            "entries": [e.__dict__ for e in self.by_tid.values()],
            "counters": self.counters,
        }

    def known_names(self) -> list[str]:
        with self._lock:
            self._refresh_if_changed()
            return [e.raw for e in self.by_tid.values() if e.cat == "NAME"]

    def _similar(self, cat: str, raw: str) -> list[str]:
        out: list[str] = []
        same_family = {"NID", "IQAMA", "UNIFIED", "CR", "NUM"} if cat in {"NID", "IQAMA", "UNIFIED", "CR", "NUM"} else {cat}
        if cat == "NAME":
            n = norm_arabic_name(raw)
            parts = n.split()
            for e in self.by_tid.values():
                if e.cat != "NAME":
                    continue
                en = norm_arabic_name(e.raw)
                if en == n:
                    out.append(f"≈{e.tid}")  # identical after normalisation -> spelling/diacritics differ
                elif levenshtein(en, n, 2) <= 2:
                    out.append(f"~{e.tid}")  # one or two letters differ
                else:
                    ep = en.split()
                    if len(parts) >= 2 and len(ep) >= 2 and parts != ep:
                        small, big = (parts, ep) if len(parts) < len(ep) else (ep, parts)
                        it = iter(big)
                        if all(p in it for p in small) and small[0] == big[0]:
                            out.append(f"⊂{e.tid}")  # shorter/longer form of the same name
        else:
            d = _key(cat, raw).split(":", 1)[1]
            for e in self.by_tid.values():
                if e.cat not in same_family:
                    continue
                ed = e.key.split(":", 1)[1]
                if ed != d and len(ed) == len(d) and levenshtein(ed, d, 2) <= 2:
                    out.append(f"~{e.tid}")
                elif ed != d and abs(len(ed) - len(d)) == 1 and levenshtein(ed, d, 1) <= 1:
                    out.append(f"~{e.tid}")
        return out[:3]

    def token_for(self, cat: str, raw: str, ctx: str = "") -> str:
        key = _key(cat, raw)
        with self._lock:
            ent = self.by_key.get(key)
            if ent is not None:
                return ent.token()
            if self._store:
                with self._store.lock():
                    self._refresh_if_changed()
                    ent = self.by_key.get(key) or self._new_entry(cat, raw, key, ctx)
                    try:
                        self._store.save(self.dump())
                        self._mtime = self._store.mtime()
                    except Exception:
                        pass
                return ent.token()
            ent = self._new_entry(cat, raw, key, ctx)
            if self._save:
                try:
                    self._save(self.dump())
                except Exception:
                    pass
            return ent.token()

    def _new_entry(self, cat: str, raw: str, key: str, ctx: str) -> Entry:
        status, hints = validate(cat, raw, ctx)
        hints = hints + self._similar(cat, raw)
        n = self.counters.get(cat, 0) + 1
        self.counters[cat] = n
        ent = Entry(cat=cat, n=n, raw=raw, key=key, status=status, hints=hints)
        self.by_key[key] = ent
        self.by_tid[ent.tid] = ent
        return ent

    def raw_for(self, tid: str) -> Optional[str]:
        with self._lock:
            e = self.by_tid.get(tid)
            if e is None and self._store:
                self._refresh_if_changed()
                e = self.by_tid.get(tid)
            return e.raw if e else None

    def clear(self) -> None:
        with self._lock:
            self.by_key.clear()
            self.by_tid.clear()
            self.counters.clear()
            _VARIANT_CACHE.clear()
            if self._store:
                with self._store.lock():
                    self._store.save(self.dump())
                    self._mtime = self._store.mtime()
            elif self._save:
                self._save(self.dump())


def mask_text(text: str, vault: Vault) -> str:
    if not text or not isinstance(text, str):
        return text
    text = prepare(text)
    # protect existing tokens from being re-detected
    spans = resolve(find_spans(text, vault.known_names()))
    if not spans:
        return text
    tok_ranges = [(m.start(), m.end()) for m in TOKEN_RE.finditer(text)]
    out = []
    pos = 0
    for s in spans:
        if any(not (s.end <= a or s.start >= b) for a, b in tok_ranges):
            continue
        out.append(text[pos:s.start])
        out.append(vault.token_for(s.cat, s.raw, s.ctx))
        pos = s.end
    out.append(text[pos:])
    return "".join(out)


def unmask_text(text: str, vault: Vault) -> str:
    if not text or not isinstance(text, str) or ("⟦" not in text and "[[" not in text):
        return text

    def rep(m: re.Match) -> str:
        raw = vault.raw_for(f"{m.group(1)}-{m.group(2)}")
        return raw if raw is not None else m.group(0)

    return TOKEN_RE.sub(rep, text)
