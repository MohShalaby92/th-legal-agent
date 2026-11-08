"""Privacy self-test — run at the start of EVERY session (see th-session-start).

Prints a freshly generated FAKE national ID, IBAN-like number and mobile number in plain text,
deliberately WITHOUT masking. If the privacy shield is active, what reaches the AI is tokens such
as ⟦NID-n⟧ / ⟦PHONE-n⟧. If the AI sees the digits themselves, the shield is OFF -> stop work.
The values are random and belong to nobody.
"""
import random


def luhn_id(first: str) -> str:
    body = first + "".join(random.choice("0123456789") for _ in range(8))
    total = 0
    for i, ch in enumerate(body):
        d = int(ch)
        if i % 2 == 0:
            d *= 2
            d = d - 9 if d > 9 else d
        total += d
    return body + str((10 - total % 10) % 10)


print("TH-PRIVACY-SELFTEST")
print("هوية وطنية: " + luhn_id("1"))
print("جوال: 05" + str(random.choice("03456789")) + "".join(random.choice("0123456789") for _ in range(7)))
print("END-SELFTEST")
print("PASS only if both values above appear as ⟦...⟧ tokens. Any visible digits = shield OFF -> STOP.")
