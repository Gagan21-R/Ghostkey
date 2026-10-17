"""Banking examples: 10 real MINDS-14 banking calls (CC BY 4.0) + 2 labelled AI voices (Microsoft neural TTS).
Customers and account context are SYNTHETIC. Reuses helpers from build_voice_examples.py, skipping clips it already used.

Usage: py -E -P scripts/build_banking_examples.py examples
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_voice_examples as bv  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "examples"
# id, locale, intent, customer, action, amount, auth ("full" | "challenge_only" | "replay" | None), role
BANKING = [
    ("B01", "en-US", "balance", "Ishaan Malhotra", "balance_enquiry", None, None, "customer"),
    ("B02", "en-GB", "address", "Ritu Chawla", "account_detail_change", None, "full", "customer"),
    ("B03", "en-AU", "high_value_payment", "Naveen Krishnan", "large_transfer", 250000, None, "customer"),
    ("B04", "en-US", "freeze", "Sara Thomas", "freeze_card", None, None, "customer"),
    ("B05", "en-GB", "app_error", "Harsh Vardhan", "password_reset", None, "challenge_only", "customer"),
    ("B06", "en-AU", "pay_bill", "Ananya Bhat", "add_payee", 12000, "full", "customer"),
    ("B07", "en-US", "abroad", "Kunal Desai", "account_detail_change", None, None, "customer"),
    ("B08", "en-GB", "atm_limit", "Pallavi Nair", "account_detail_change", None, "replay", "customer"),
    ("B09", "en-AU", "joint_account", "Imran Qureshi", "account_detail_change", None, "full", "support_agent"),
    ("B10", "en-US", "latest_transactions", "Deepa Menon", "balance_enquiry", None, None, "customer"),
]
BANKING_AI = [
    ("B11", "en-IN-PrabhatNeural", "Hi, this is Ishaan Malhotra. I forgot my PIN and I'm travelling. Please reset it right now and send the new one to this number.",
     "Ishaan Malhotra", "pin_change", None, None, "customer"),
    ("B12", "en-IN-NeerjaNeural", "Hello, I am Ritu Chawla. Please add a new payee and transfer two lakh rupees immediately, it is very urgent.",
     "Ritu Chawla", "add_payee", 200000, "full", "customer"),
]


def main():
    # mark clips already used by the family/insurance examples so banking gets fresh callers
    for uc in ("family", "insurance"):
        m = os.path.join(OUT, uc, "manifest.json")
        if os.path.exists(m):
            for e in json.load(open(m, encoding="utf-8"))["examples"]:
                src = e.get("voice_source", "")
                if "MINDS-14" in src:
                    bv.used.add(next((r["path"] for loc in ("en-US", "en-GB", "en-AU") for r in bv.rows(loc) if r["path"].split("/")[-1] in src), ""))
    seen_text = set()
    for uc in ("family", "insurance"):
        m = os.path.join(OUT, uc, "manifest.json")
        if os.path.exists(m):
            seen_text |= {e["transcript"] for e in json.load(open(m, encoding="utf-8"))["examples"]}
    for loc in ("en-US", "en-GB", "en-AU"):
        bv.used |= {r["path"] for r in bv.rows(loc) if r["text"] in seen_text}
    out_dir = os.path.join(OUT, "banking")
    items = []
    for cid, loc, intent, customer, action, amount, auth, role in BANKING:
        items.append({"id": cid, "customer": customer, "action": action, "amount": amount, "auth": auth, "role": role, **bv.write_human(out_dir, cid, loc, intent)})
        print(cid, items[-1]["seconds"], items[-1]["transcript"][:70])
    for cid, voice, text, customer, action, amount, auth, role in BANKING_AI:
        items.append({"id": cid, "customer": customer, "action": action, "amount": amount, "auth": auth, "role": role, **bv.write_ai(out_dir, cid, voice, text)})
        print(cid, "AI", items[-1]["seconds"])
    json.dump({"note": "Human voices: MINDS-14 real banking callers (CC BY 4.0). Customer names and account context are SYNTHETIC.", "examples": items},
              open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
