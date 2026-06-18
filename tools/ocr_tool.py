import re
import sys
from pathlib import Path


SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.append(str(SRC_PATH))


def extract_medicine_from_image(image_path):
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError:
        return {
            "medicine_name": "",
            "text": "",
            "error": "OCR dependencies are not installed. Install pytesseract and Pillow.",
        }

    try:
        image = Image.open(image_path)
        image = ImageOps.grayscale(image)
        image = image.point(lambda pixel: 255 if pixel > 160 else 0)
        text = pytesseract.image_to_string(image)
    except Exception as exc:
        return {
            "medicine_name": "",
            "text": "",
            "error": f"OCR failed: {exc}",
        }

    from risk_model import df, get_medicine_info

    normalized_text = text.lower()
    for medicine_name in sorted(df["Medicine"].dropna().unique(), key=len, reverse=True):
        pattern = r"\b" + re.escape(medicine_name.lower()) + r"\b"
        if re.search(pattern, normalized_text):
            return {"medicine_name": medicine_name, "text": text, "error": None}

    best_candidate = ""
    best_score = 0
    for token in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text):
        result, matched_name, score = get_medicine_info(token)
        if result is not None and not result.empty and score > best_score:
            best_candidate = matched_name
            best_score = score

    if best_candidate and best_score >= 75:
        return {"medicine_name": best_candidate, "text": text, "error": None}

    return {
        "medicine_name": "",
        "text": text,
        "error": "No known medicine name was detected in the image.",
    }
