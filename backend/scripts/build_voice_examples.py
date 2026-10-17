"""Builds family/SIM and insurance voice examples.

Human voices: MINDS-14 (PolyAI, CC BY 4.0) — real people phoning an e-banking helpline. The family or
insurance context wrapped around each call (relationship, request, claim, carrier events) is SYNTHETIC.
AI voices: Microsoft neural TTS (edge-tts) — synthetic speech, not a clone of any real person.

Usage: py -E -P scripts/build_voice_examples.py examples
"""
import asyncio
import io
import json
import os
import sys
import time
import urllib.request

import soundfile as sf

OUT = sys.argv[1] if len(sys.argv) > 1 else "examples"
API = "https://datasets-server.huggingface.co/rows?dataset=PolyAI%2Fminds14"
INTENTS = ["abroad", "address", "app_error", "atm_limit", "balance", "business_loan", "card_issues", "cash_deposit",
           "direct_debit", "freeze", "high_value_payment", "joint_account", "latest_transactions", "pay_bill"]

FAMILY = [  # id, locale, intent, relation, claimed caller, action, amount, carrier/account events, independent verification
    ("F01", "en-GB", "card_issues", "daughter", "Meera (daughter)", "send_money", 5000, [], "passed"),
    ("F02", "en-US", "abroad", "son", "Rohan (son)", "emergency_transfer", 40000, [{"type": "number_reassigned"}], "failed"),
    ("F03", "en-AU", "freeze", "husband", "Suresh (husband)", "chat", None, [], None),
    ("F04", "en-US", "high_value_payment", "brother", "Anil (brother)", "send_money", 150000, [{"type": "sim_swap_alert"}], "not completed"),
    ("F05", "en-GB", "pay_bill", "mother", "Lakshmi (mother)", "send_money", 3000, [], "passed"),
    ("F06", "en-AU", "latest_transactions", "nephew", "Karthik (nephew)", "share_otp", None, [], None),
    ("F07", "en-US", "cash_deposit", "cousin", "Divya (cousin)", "emergency_transfer", 25000, [{"type": "number_reassigned", "confirmed": False}], "passed"),
    ("F08", "en-GB", "atm_limit", "sister", "Priya (sister)", "send_money", 10000, [{"account": "recovery_channel_changed"}], "failed"),
    ("F09", "en-AU", "joint_account", "father", "Ramesh (father)", "chat", None, [], None),
    ("F10", "en-US", "direct_debit", "son", "Arjun (son)", "send_money", 8000, [], "not completed"),
]
FAMILY_AI = [
    ("F11", "en-IN-PrabhatNeural", "Ma, it's Rohan. I've had an accident and I'm at the hospital. Send fifty thousand rupees right now, and please don't tell papa.",
     "son", "Rohan (son)", "emergency_transfer", 50000, [{"type": "number_reassigned"}], "failed"),
    ("F12", "hi-IN-MadhurNeural", "माँ, मैं रोहन बोल रहा हूँ। बैंक से एक कोड आया होगा, जल्दी से मुझे वह ओटीपी बता दो, बहुत ज़रूरी है।",
     "son", "Rohan (son)", "share_otp", None, [{"type": "sim_swap_alert"}], None),
]

INSURANCE = [  # id, locale, intent, claim type, action, amount, docs complete?, anomaly, auth ("full"|None)
    ("I01", "en-US", "address", "Contact details update", "change_contact_details", None, True, None, "full"),
    ("I02", "en-GB", "pay_bill", "Premium payment", "pay_premium", 18500, True, None, None),
    ("I03", "en-AU", "high_value_payment", "Hospitalisation", "submit_high_value_claim", 450000, True, None, None),
    ("I04", "en-US", "card_issues", "Claim payout card problem", "change_payout_details", 62000, True, None, "full"),
    ("I05", "en-GB", "freeze", "Lost payout card", "freeze_payouts", None, True, None, None),
    ("I06", "en-AU", "abroad", "Travel medical claim", "submit_claim", 95000, False, None, None),
    ("I07", "en-US", "latest_transactions", "Claim status", "claim_status", None, True, None, None),
    ("I08", "en-GB", "joint_account", "Add nominee", "add_nominee", None, True, None, None),
    ("I09", "en-AU", "direct_debit", "Premium auto-debit", "pay_premium", 9200, True, None, None),
    ("I10", "en-US", "balance", "Accident claim", "submit_claim", 120000, True, "duplicate", None),
]
INSURANCE_AI = [
    ("I11", "en-IN-NeerjaNeural", "Hello, I am the policyholder. Please change the payout account on my claim to a new account ending seven seven six five today. I am in a hurry.",
     "Hospitalisation", "change_payout_details", 380000, True, "payout_changed", None),
    ("I12", "en-IN-PrabhatNeural", "I'm calling about my critical illness claim of fifteen lakh rupees. Please approve it quickly, the documents are already with you.",
     "Critical illness", "submit_high_value_claim", 1500000, True, "duplicate", "full"),
]
NAMES = ["Kiran Patel", "Neha Gupta", "Sanjay Nair", "Pooja Sharma", "Ravi Kumar", "Ayesha Siddiqui", "Manoj Pillai", "Shalini Rao",
         "Deepak Joshi", "Farah Khan", "Gautam Sen", "Rekha Iyer"]


def get_bytes(url, tries=5):
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


_rows = {}


def rows(locale):
    if locale not in _rows:
        out, offset = [], 0
        while True:
            page = json.loads(get_bytes(f"{API}&config={locale}&split=train&offset={offset}&length=100"))
            out += [{"path": i["row"]["path"], "text": i["row"]["transcription"], "intent": INTENTS[i["row"]["intent_class"]], "src": i["row"]["audio"][0]["src"]} for i in page["rows"]]
            offset += 100
            if offset >= page["num_rows_total"]:
                break
        _rows[locale] = out
    return _rows[locale]


used = set()


def pick(locale, intent):
    for r in sorted((r for r in rows(locale) if r["intent"] == intent and len(r["text"].split()) >= 7), key=lambda r: -len(r["text"])):
        if r["path"] in used:
            continue
        data, sr = sf.read(io.BytesIO(get_bytes(r["src"])))
        if 5.5 <= len(data) / sr <= 25:
            used.add(r["path"])
            return r, data, sr
    raise SystemExit(f"no clip for {locale}/{intent}")


async def tts(voice, text, path):
    import edge_tts
    await edge_tts.Communicate(text, voice).save(path)


def write_human(folder, cid, locale, intent):
    r, data, sr = pick(locale, intent)
    os.makedirs(os.path.join(folder, cid), exist_ok=True)
    sf.write(os.path.join(folder, cid, "call.wav"), data, sr, subtype="PCM_16")
    return {"audio": f"{cid}/call.wav", "seconds": round(len(data) / sr, 1), "transcript": r["text"], "voice_truth": "human",
            "voice_source": f"MINDS-14 {locale} {r['path'].split('/')[-1]} (CC BY 4.0, real caller)", "dataset_intent": intent}


def write_ai(folder, cid, voice, text):
    os.makedirs(os.path.join(folder, cid), exist_ok=True)
    path = os.path.join(folder, cid, "call.mp3")
    asyncio.run(tts(voice, text, path))
    data, sr = sf.read(path)
    return {"audio": f"{cid}/call.mp3", "seconds": round(len(data) / sr, 1), "transcript": text, "voice_truth": "ai_synthetic",
            "voice_source": f"Microsoft neural TTS {voice} (synthetic, not a clone of a real person)"}


def main():
    fam_dir, ins_dir = os.path.join(OUT, "family"), os.path.join(OUT, "insurance")
    fam = []
    for cid, locale, intent, rel, claimed, action, amount, events, iv in FAMILY:
        fam.append({"id": cid, "relation": rel, "claimed_caller": claimed, "protected_person": "Asha Rao", "action": action, "amount": amount,
                    "carrier_events": [e for e in events if "type" in e], "account_events": [{"type": e["account"]} for e in events if "account" in e],
                    "independent_verification": iv, **write_human(fam_dir, cid, locale, intent)})
        print(cid, fam[-1]["seconds"], fam[-1]["transcript"][:70])
    for cid, voice, text, rel, claimed, action, amount, events, iv in FAMILY_AI:
        fam.append({"id": cid, "relation": rel, "claimed_caller": claimed, "protected_person": "Asha Rao", "action": action, "amount": amount,
                    "carrier_events": events, "account_events": [], "independent_verification": iv, **write_ai(fam_dir, cid, voice, text)})
        print(cid, "AI", fam[-1]["seconds"])
    json.dump({"note": "Human voices: MINDS-14 real callers (CC BY 4.0). Family relationships, requests and carrier events are SYNTHETIC.", "examples": fam},
              open(os.path.join(fam_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    ins = []
    for k, row in enumerate(INSURANCE + INSURANCE_AI):
        cid, src, intent_or_text, ctype, action, amount, docs_ok, anomaly, auth = row
        human = cid in {r[0] for r in INSURANCE}
        audio = write_human(ins_dir, cid, src, intent_or_text) if human else write_ai(ins_dir, cid, src, intent_or_text)
        required = ["claim_form", "id_proof", "supporting_bills"]
        ins.append({"id": cid, "policyholder": NAMES[k], "policy_ref": f"POL-DEMO-{7100 + k}", "claim_id": f"CLM-DEMO-{3000 + k}", "claim_type": ctype,
                    "action": action, "amount": amount, "documents": required if docs_ok else required[:1], "required_documents": required,
                    "anomaly": anomaly, "auth": auth, "synthetic_record": True, **audio})
        print(cid, "human" if human else "AI", audio["seconds"])
    json.dump({"note": "Human voices: MINDS-14 real callers (CC BY 4.0). Policyholders and claims are SYNTHETIC demo records.", "examples": ins},
              open(os.path.join(ins_dir, "manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
