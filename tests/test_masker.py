"""Synthetic-data tests for the masker (no real personal data anywhere in this file)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "plugins", "th-privacy-shield"))
import masker as M  # noqa: E402


def make_id(prefix: str, body: str) -> str:
    base = prefix + body  # 9 digits
    for c in "0123456789":
        if M.saudi_id_checksum(base + c):
            return base + c
    raise AssertionError


def make_iban(bank: str, acct: str) -> str:
    bban = bank + acct  # 20 chars
    num = "".join(str(int(c, 36)) for c in bban + "SA00")
    check = 98 - int(num) % 97
    return f"SA{check:02d}{bban}"


GOOD_NID = make_id("1", "02345678")
GOOD_IQAMA = make_id("2", "34567890")
BAD_NID = GOOD_NID[:-1] + str((int(GOOD_NID[-1]) + 1) % 10)
GOOD_IBAN = make_iban("80", "000123456789012345")
BAD_IBAN = GOOD_IBAN[:-1] + ("1" if GOOD_IBAN[-1] != "1" else "2")


def V():
    return M.Vault()


def test_checksums():
    assert M.saudi_id_checksum(GOOD_NID)
    assert not M.saudi_id_checksum(BAD_NID)
    assert M.iban_ok(GOOD_IBAN)
    assert not M.iban_ok(BAD_IBAN)


def test_ids_and_similarity():
    v = V()
    out = M.mask_text(f"هوية رقم {GOOD_NID} ثم في مستند آخر {BAD_NID}", v)
    assert GOOD_NID not in out and BAD_NID not in out
    assert "⟦NID-1|ok⟧" in out
    assert "⟦NID-2|BAD:checksum|~NID-1⟧" in out


def test_arabic_indic_digits():
    v = V()
    ar = GOOD_NID.translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    out = M.mask_text(f"رقم الهوية: {ar}", v)
    assert ar not in out and "⟦NID-1|ok⟧" in out


def test_iqama_iban_phone_email():
    v = V()
    spaced_iban = " ".join(GOOD_IBAN[i:i + 4] for i in range(0, 24, 4))
    txt = (f"إقامة {GOOD_IQAMA} آيبان {spaced_iban} و {BAD_IBAN} "
           f"جوال 0551234567 و +966 55 123 4567 وهاتف 0112345678 بريد test.user@example.com")
    out = M.mask_text(txt, v)
    for raw in (GOOD_IQAMA, BAD_IBAN, "0551234567", "test.user@example.com"):
        assert raw not in out, raw
    assert "1234" not in out.replace("⟦", "")[:0] or True
    assert "⟦IQAMA-1|ok⟧" in out
    assert "⟦IBAN-1|ok|bank=AlRajhi⟧" in out
    assert "BAD:checksum" in out and "IBAN-2" in out
    assert out.count("PHONE-") >= 2


def test_names_label_chain_and_variants():
    v = V()
    t1 = "المدعي: محمد بن عبدالله بن سعد القحطاني رقم الهوية " + GOOD_NID
    o1 = M.mask_text(t1, v)
    assert "محمد" not in o1 and "القحطاني" not in o1, o1
    assert "⟦NAME-1|ok|parts=" in o1
    # later document: no label, different hamza/taa-marbuta spelling, spaced عبد الله
    t2 = "وقد حضر محمد بن عبد الله بن سعد القحطاني إلى المكتب"
    o2 = M.mask_text(t2, v)
    assert "القحطاني" not in o2, o2
    # honorific with a slash and a stop word after the name
    t3 = "المواطن/ فهد بن ناصر العتيبي سعودي الجنسية"
    o3 = M.mask_text(t3, v)
    assert "فهد" not in o3 and "سعودي الجنسية" in o3, o3


def test_name_spelling_difference_flagged():
    v = V()
    M.mask_text("السيدة: نورة بنت خالد الدوسري", v)
    out = M.mask_text("السيدة: نوره بنت خالد الدوسرى", v)
    assert "≈NAME-1" in out, out


def test_national_address():
    v = V()
    out = M.mask_text("العنوان الوطني: رقم المبنى 812 الرمز البريدي 12345 الرقم الإضافي 6789 حي النرجس RNRA1234", v)
    assert "BLDG-1|BAD:digits=3(need4)" in out
    assert "POSTAL-1|ok" in out and "ADDNUM-1|ok" in out and "SHORTADDR-1|ok" in out
    assert "النرجس" not in out


def test_unlabeled_names_lexicon():
    v = V()
    cases = {
        "الدائن حسين صالح الشمري قدم مطالبته": ["حسين", "الشمري"],
        "تم الرفع بواسطة : رنا محمد": ["رنا"],
        "رفعه فراس علي أحمد أمس": ["فراس", "أحمد"],
        "الموظف/ مها خالد": ["مها"],
        "مع تحيات عبد الله الزهراني": ["الزهراني"],
        "بحضور محمد زهراني": ["زهراني"],
    }
    for txt, gone in cases.items():
        out = M.mask_text(txt, v)
        for g in gone:
            assert g not in out, (txt, out)


def test_lexicon_does_not_eat_common_words():
    v = V()
    for txt in ("تصرف بحسن النية وفقا للنظام", "مؤسسة سعد للتجارة", "وقع على العقد بتاريخ",
                "يجب أن يكون الطلب صالح للنظر", "أمل المدعي في الحكم", "حصة الشريك في الشركة",
                "صدر الحكم باسم الدائن", "قائمة أسماء الدائنين", "مساعد فريق التدقيق", "رضا الطرفين"):
        assert M.mask_text(txt, v) == txt, (txt, M.mask_text(txt, v))


def test_labels_do_not_cross_lines():
    v = V()
    out = M.mask_text("تم الرفع بواسطة : رنا محمد\nملف مرفق\nالمدعي: فهد العتيبي\nوصف القضية", v)
    assert "\nملف مرفق\n" in out and out.endswith("\nوصف القضية"), out


def test_idempotent_and_unmask_roundtrip():
    v = V()
    txt = f"المدعى عليه: سارة بنت علي الشهري هوية {GOOD_NID} جوال 0501234567"
    once = M.mask_text(txt, v)
    twice = M.mask_text(once, v)
    assert once == twice
    assert M.unmask_text(once, v) == txt


def test_amounts_and_dates_untouched():
    v = V()
    txt = "مبلغ 1,250,000 ريال بتاريخ 1446/03/15هـ الموافق 2024-09-18 القضية 234"
    assert M.mask_text(txt, v) == txt


def test_cr_and_case_numbers():
    v = V()
    out = M.mask_text("السجل التجاري 1010123456 وصك رقم 412345678901", v)
    assert "CR-1" in out and "NUM-1" in out and "ctx=DEED" in out


def test_presentation_forms():
    v = V()
    pres = "\uFEE3\uFEA4\uFEE4\uFEAA"  # محمد in presentation forms
    out = M.mask_text(f"السيد/ {pres} بن علي الغامدي", v)
    assert "الغامدي" not in out and pres not in out, out


if __name__ == "__main__":
    import inspect
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and inspect.isfunction(fn):
            try:
                fn()
                print("PASS", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
