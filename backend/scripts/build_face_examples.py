"""Builds the exam examples from Caltech Faces 1999 (MIT licence; real people photographed for research).

The dataset has no identity labels, so photos are grouped by person with SFace embeddings (strict cosine 0.55),
then 11 student cases are assembled. Transformations (darkening, side-by-side composite, background crop,
duplicate frame) are applied to real photos and are labelled as such in the manifest.

Usage: .venv/Scripts/python scripts/build_face_examples.py datasets/raw examples/exam
"""
import glob
import json
import os
import shutil
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import face_service  # noqa: E402

RAW, OUT = sys.argv[1], sys.argv[2]
GROUP_THRESHOLD = 0.55


def embed(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(face_service.DETECTOR, "", (w, h), 0.85, 0.3, 5000)
    _, faces = det.detect(img)
    if faces is None or len(faces) != 1:
        return None
    rec = face_service._recognizer()
    f = rec.feature(rec.alignCrop(img, faces[0])).flatten()
    return f / np.linalg.norm(f)


def main():
    paths = sorted(glob.glob(os.path.join(RAW, "image_*.jpg")))
    groups: list[dict] = []
    for p in paths:
        e = embed(p)
        if e is None:
            continue
        best = max(groups, key=lambda g: float(g["centroid"] @ e), default=None)
        if best is not None and float(best["centroid"] @ e) >= GROUP_THRESHOLD:
            best["items"].append((p, e))
            c = np.mean([x[1] for x in best["items"]], axis=0)
            best["centroid"] = c / np.linalg.norm(c)
        else:
            groups.append({"items": [(p, e)], "centroid": e})
    people = sorted([g for g in groups if len(g["items"]) >= 5], key=lambda g: -len(g["items"]))
    print(f"{len(paths)} photos → {len(groups)} groups, {len(people)} people with ≥5 photos")
    if len(people) < 10:
        sys.exit("not enough distinct people")

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    P = [[x[0] for x in g["items"]] for g in people[:10]]
    src = lambda p: f"Caltech Faces 1999 {os.path.basename(p)} (MIT licence)"  # noqa: E731

    def save(sid, name, img_or_path):
        d = os.path.join(OUT, sid)
        os.makedirs(d, exist_ok=True)
        out = os.path.join(d, name)
        if isinstance(img_or_path, str):
            shutil.copy(img_or_path, out)
        else:
            cv2.imwrite(out, img_or_path, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return f"{sid}/{name}"

    def dark(p):
        img = cv2.imread(p).astype(np.float32)
        return np.clip((img / 255.0) ** 2.6 * 255 * 0.35, 0, 255).astype(np.uint8)

    def pair(a, b):
        A, B = cv2.imread(a), cv2.imread(b)
        B = cv2.resize(B, (A.shape[1], A.shape[0]))
        return np.hstack([A, B])

    def background(p):
        img = cv2.imread(p)
        h, w = img.shape[:2]
        return cv2.resize(img[int(h * 0.75):, : int(w * 0.25)], (448, 296))

    cases = []

    def case(sid, student, scenario, truth, expected, ref, frames, notes, sources):
        cases.append({"id": sid, "student": student, "scenario": scenario, "ground_truth": truth, "expected_state": expected,
                      "reference": save(sid, "reference.jpg", ref) if ref else None,
                      "frames": [save(sid, f"frame_{i}.jpg", f) for i, f in enumerate(frames)], "notes": notes, "sources": sources, "real_human": True})

    names = ["Aarav Menon", "Diya Kapoor", "Kabir Singh", "Isha Reddy", "Rohan Das", "Sneha Pillai", "Aditya Rao", "Meghna Joshi", "Vivaan Shah", "Tara Bose", "Nikhil Verma"]
    for k in range(4):  # genuine students, different photos of the same person
        p = P[k]
        case(f"S{k + 1:02d}", names[k], "Genuine student, live frames", "same person", "FACE_MATCH_SUPPORTED", p[0], p[1:4],
             "Reference and frames are different real photos of the same person.", [src(x) for x in p[:4]])
    for k, (a, b) in enumerate([(4, 5), (6, 7)]):  # substitutes
        case(f"S{k + 5:02d}", names[4 + k], "Substitute sits the exam", "different person", "FACE_MISMATCH_SUSPECTED", P[a][0], P[b][1:4],
             "Frames show a different real person than the enrolled student.", [src(P[a][0])] + [src(x) for x in P[b][1:4]])
    case("S07", names[6], "Genuine student, very poor lighting", "same person (darkened)", "LIVENESS_INCONCLUSIVE", P[8][0], [dark(x) for x in P[8][1:4]],
         "Real photos of the enrolled student, darkened to simulate a dim room.", [src(x) for x in P[8][:4]])
    case("S08", names[7], "A second person in view", "same person + another person", "MULTIPLE_FACES_DETECTED", P[9][0], [pair(P[9][i], P[0][i]) for i in (1, 2, 3)],
         "Each frame places the enrolled student next to another real person.", [src(x) for x in P[9][:4] + P[0][1:4]])
    case("S09", names[8], "Printed photo held up (replay)", "same photo repeated", "LIVENESS_INCONCLUSIVE", P[1][0], [P[1][1]] * 3,
         "Three pixel-identical frames, as a held-up photo would produce. Heuristic only — no liveness model.", [src(P[1][0]), src(P[1][1])])
    case("S10", names[9], "Student looks away from the camera", "no face in frame", "NO_FACE_DETECTED", P[2][0], [background(x) for x in P[2][1:4]],
         "Frames are background crops of real photos with no face.", [src(x) for x in P[2][:4]])
    case("S11", names[10], "Single uploaded photo only", "same person, one image", "FACE_MATCH_SUPPORTED", P[3][0], [P[3][4]],
         "A match on one image is not enough to start the exam (needs 3 live frames).", [src(P[3][0]), src(P[3][4])])

    json.dump({"source": "Caltech Faces 1999 — https://data.caltech.edu/records/6rjah-hdv18 (MIT licence)",
               "grouping": f"Photos grouped by person using SFace embeddings (cosine ≥ {GROUP_THRESHOLD}); dataset has no identity labels.",
               "names_note": "Student names are fictional.", "cases": cases}, open(os.path.join(OUT, "manifest.json"), "w"), indent=2)

    # verify with the real model
    for c in cases:
        ref = face_service.embed(open(os.path.join(OUT, c["reference"]), "rb").read())
        frames = [face_service.analyze_frame(open(os.path.join(OUT, f), "rb").read(), ref.get("embedding"), i) for i, f in enumerate(c["frames"])]
        sims = [None if fr["best_similarity"] is None else round(fr["best_similarity"], 3) for fr in frames]
        print(f"{c['id']} {c['scenario'][:38]:38} faces={[fr['faces'] for fr in frames]} sims={sims} bright={[round(fr['brightness']) for fr in frames]}")


if __name__ == "__main__":
    main()
