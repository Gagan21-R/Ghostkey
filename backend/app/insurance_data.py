"""SYNTHETIC insurance demo records. Fictional people, policies and claims for the "KRISIS Mutual (demo)"
insurer — not real records, not connected to any real insurer."""

SYNTHETIC_NOTICE = "Synthetic demo record — fictional policyholder and claim; no real insurer is connected."

POLICYHOLDERS = {
    "ph-anita": {"id": "ph-anita", "name": "Anita Desai", "policy_ref": "POL-HLT-20419", "product": "Family health floater", "sum_insured": 500000,
                 "policy_start": "2024-04-01", "registered_phone": "+91 98860 XXXXX", "payout_account": "HDFC ••4421",
                 "payout_account_changed_at": None, "authorized_representatives": ["Vikram Desai (spouse)"], "voice_enrolled": True,
                 "speaker_id": "cust-zira-rao-7d3e", "synthetic": True},
    "ph-ramesh": {"id": "ph-ramesh", "name": "Ramesh Iyer", "policy_ref": "POL-MTR-88310", "product": "Private car comprehensive", "sum_insured": 900000,
                  "policy_start": "2026-09-20", "registered_phone": "+91 99020 XXXXX", "payout_account": "SBI ••1187",
                  "payout_account_changed_at": "2026-10-15", "authorized_representatives": [], "voice_enrolled": False, "speaker_id": "", "synthetic": True},
    "ph-fatima": {"id": "ph-fatima", "name": "Fatima Khan", "policy_ref": "POL-LIF-55102", "product": "Term life", "sum_insured": 5000000,
                  "policy_start": "2021-01-15", "registered_phone": "+91 97400 XXXXX", "payout_account": "ICICI ••9034",
                  "payout_account_changed_at": None, "authorized_representatives": ["Imran Khan (brother, nominee)"], "voice_enrolled": False, "speaker_id": "", "synthetic": True},
}

CLAIMS = {
    "CLM-2026-1042": {"claim_id": "CLM-2026-1042", "policyholder_id": "ph-anita", "claimant": "Anita Desai", "claimant_relation": "self",
                      "claim_type": "Hospitalisation", "amount": 84000, "incident_date": "2026-10-02", "reported_date": "2026-10-04",
                      "status": "Under review", "documents": ["discharge_summary", "hospital_bill", "id_proof"], "required_documents": ["discharge_summary", "hospital_bill", "id_proof"],
                      "requested_action": "submit_claim", "new_payout_account": None, "duplicate_of": None, "synthetic": True},
    "CLM-2026-1077": {"claim_id": "CLM-2026-1077", "policyholder_id": "ph-anita", "claimant": "Caller claiming to be Anita Desai", "claimant_relation": "self",
                      "claim_type": "Hospitalisation", "amount": 420000, "incident_date": "2026-10-11", "reported_date": "2026-10-12",
                      "status": "Payout change requested", "documents": ["hospital_bill"], "required_documents": ["discharge_summary", "hospital_bill", "id_proof"],
                      "requested_action": "change_payout_details", "new_payout_account": "Unknown bank ••7765", "duplicate_of": None, "synthetic": True},
    "CLM-2026-1103": {"claim_id": "CLM-2026-1103", "policyholder_id": "ph-ramesh", "claimant": "Ramesh Iyer", "claimant_relation": "self",
                      "claim_type": "Accident damage", "amount": 610000, "incident_date": "2026-09-18", "reported_date": "2026-10-14",
                      "status": "Submitted", "documents": ["fir_copy"], "required_documents": ["fir_copy", "surveyor_report", "repair_estimate", "id_proof"],
                      "requested_action": "submit_high_value_claim", "new_payout_account": None, "duplicate_of": None, "synthetic": True},
    "CLM-2026-1121": {"claim_id": "CLM-2026-1121", "policyholder_id": "ph-fatima", "claimant": "Imran Khan", "claimant_relation": "brother, nominee",
                      "claim_type": "Critical illness rider", "amount": 1500000, "incident_date": "2026-10-05", "reported_date": "2026-10-09",
                      "status": "Submitted", "documents": ["medical_certificate", "id_proof", "nominee_proof"], "required_documents": ["medical_certificate", "id_proof", "nominee_proof"],
                      "requested_action": "submit_high_value_claim", "new_payout_account": None, "duplicate_of": "CLM-2025-0877", "synthetic": True},
}

POLICYHOLDERS.update({
    "ph-george": {"id": "ph-george", "name": "George Mathew", "policy_ref": "POL-HLT-31877", "product": "Senior citizen health", "sum_insured": 700000,
                  "policy_start": "2019-06-10", "registered_phone": "+91 94470 XXXXX", "payout_account": "Federal ••2210", "payout_account_changed_at": None,
                  "authorized_representatives": ["Anna Mathew (daughter)"], "voice_enrolled": False, "speaker_id": "", "synthetic": True},
    "ph-sunil": {"id": "ph-sunil", "name": "Sunil Bhatia", "policy_ref": "POL-HOM-40291", "product": "Home contents", "sum_insured": 1200000,
                 "policy_start": "2025-11-02", "registered_phone": "+91 98110 XXXXX", "payout_account": "Kotak ••6612", "payout_account_changed_at": None,
                 "authorized_representatives": [], "voice_enrolled": False, "speaker_id": "", "synthetic": True},
    "ph-lata": {"id": "ph-lata", "name": "Lata Krishnan", "policy_ref": "POL-TRV-77015", "product": "International travel", "sum_insured": 3000000,
                "policy_start": "2026-09-28", "registered_phone": "+91 99620 XXXXX", "payout_account": "Axis ••0458", "payout_account_changed_at": "2026-10-13",
                "authorized_representatives": [], "voice_enrolled": False, "speaker_id": "", "synthetic": True},
    "ph-arvind": {"id": "ph-arvind", "name": "Arvind Kulkarni", "policy_ref": "POL-MTR-12940", "product": "Two-wheeler comprehensive", "sum_insured": 120000,
                  "policy_start": "2024-02-14", "registered_phone": "+91 98450 XXXXX", "payout_account": "BoB ••3391", "payout_account_changed_at": None,
                  "authorized_representatives": [], "voice_enrolled": False, "speaker_id": "", "synthetic": True},
})

CLAIMS.update({
    "CLM-2026-1130": {"claim_id": "CLM-2026-1130", "policyholder_id": "ph-george", "claimant": "Anna Mathew", "claimant_relation": "daughter",
                      "claim_type": "Cataract surgery", "amount": 65000, "incident_date": "2026-10-06", "reported_date": "2026-10-08", "status": "Submitted",
                      "documents": ["discharge_summary", "hospital_bill", "id_proof"], "required_documents": ["discharge_summary", "hospital_bill", "id_proof"],
                      "requested_action": "submit_claim", "new_payout_account": None, "duplicate_of": None, "synthetic": True},
    "CLM-2026-1134": {"claim_id": "CLM-2026-1134", "policyholder_id": "ph-sunil", "claimant": "Sunil Bhatia", "claimant_relation": "self",
                      "claim_type": "Burglary", "amount": 380000, "incident_date": "2026-10-01", "reported_date": "2026-10-03", "status": "Submitted",
                      "documents": ["fir_copy", "invoice_copies", "id_proof"], "required_documents": ["fir_copy", "invoice_copies", "id_proof"],
                      "requested_action": "submit_high_value_claim", "new_payout_account": None, "duplicate_of": None, "synthetic": True},
    "CLM-2026-1138": {"claim_id": "CLM-2026-1138", "policyholder_id": "ph-lata", "claimant": "Caller claiming to be Lata Krishnan", "claimant_relation": "self",
                      "claim_type": "Lost baggage abroad", "amount": 240000, "incident_date": "2026-09-27", "reported_date": "2026-10-14", "status": "Payout change requested",
                      "documents": ["airline_report"], "required_documents": ["airline_report", "passport_copy", "purchase_receipts"],
                      "requested_action": "change_payout_details", "new_payout_account": "Unknown bank ••5520", "duplicate_of": None, "synthetic": True},
    "CLM-2026-1142": {"claim_id": "CLM-2026-1142", "policyholder_id": "ph-arvind", "claimant": "Arvind Kulkarni", "claimant_relation": "self",
                      "claim_type": "Bike accident repair", "amount": 38000, "incident_date": "2026-10-09", "reported_date": "2026-10-10", "status": "Submitted",
                      "documents": ["repair_estimate", "photos", "id_proof"], "required_documents": ["repair_estimate", "photos", "id_proof"],
                      "requested_action": "submit_claim", "new_payout_account": None, "duplicate_of": None, "synthetic": True},
    "CLM-2026-1147": {"claim_id": "CLM-2026-1147", "policyholder_id": "ph-george", "claimant": "Caller claiming to be George Mathew", "claimant_relation": "self",
                      "claim_type": "Hospitalisation", "amount": 510000, "incident_date": "2026-10-11", "reported_date": "2026-10-12", "status": "Contact change requested",
                      "documents": ["hospital_bill", "id_proof", "discharge_summary"], "required_documents": ["hospital_bill", "id_proof", "discharge_summary"],
                      "requested_action": "change_contact_details", "new_payout_account": None, "duplicate_of": None, "synthetic": True},
    "CLM-2026-1151": {"claim_id": "CLM-2026-1151", "policyholder_id": "ph-ramesh", "claimant": "Ramesh Iyer", "claimant_relation": "self",
                      "claim_type": "Windscreen damage", "amount": 22000, "incident_date": "2026-10-12", "reported_date": "2026-10-13", "status": "Submitted",
                      "documents": ["photos", "id_proof"], "required_documents": ["photos", "id_proof"],
                      "requested_action": "submit_claim", "new_payout_account": None, "duplicate_of": "CLM-2026-1103", "synthetic": True},
})

PRIOR_CLAIM_REFS = {"CLM-2025-0877", "CLM-2026-1103"}  # synthetic history used for the duplicate-reference check
