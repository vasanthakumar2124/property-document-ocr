from __future__ import annotations

import argparse
import csv
import shutil
import sys
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pytesseract import Output

DEFAULT_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
DEFAULT_DPI = 350
LANGUAGE = "eng"
TIMEOUT_SECONDS = 150


def configure_tesseract() -> None:
    found = shutil.which("tesseract")
    if found:
        pytesseract.pytesseract.tesseract_cmd = found
    elif DEFAULT_TESSERACT.exists():
        pytesseract.pytesseract.tesseract_cmd = str(DEFAULT_TESSERACT)
    else:
        raise FileNotFoundError(
            "Tesseract was not found on PATH or at " + str(DEFAULT_TESSERACT)
            + ". Install Tesseract OCR or edit DEFAULT_TESSERACT in this script."
        )
    print("Tesseract version:", pytesseract.get_tesseract_version())


def render_page(page: pymupdf.Page, dpi: int) -> Image.Image:
    scale = dpi / 72.0
    pix = page.get_pixmap(
        matrix=pymupdf.Matrix(scale, scale),
        colorspace=pymupdf.csRGB,
        alpha=False,
    )
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def preprocess_variants(image: Image.Image) -> list[tuple[str, Image.Image]]:
    """Return conservative grayscale and thresholded variants for OCR retries."""
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Sharpness(gray).enhance(1.4)
    gray = ImageEnhance.Contrast(gray).enhance(1.15)

    # Global threshold can help faint/low-contrast scans. Keep the grayscale
    # variant too, because thresholding can erase thin characters and stamps.
    thresholded = gray.point(lambda px: 255 if px >= 175 else 0, mode="1").convert("L")
    return [("enhanced_grayscale", gray), ("thresholded", thresholded)]


def run_ocr(image: Image.Image, psm: int) -> dict:
    config = f"--oem 3 --psm {psm}"
    data = pytesseract.image_to_data(
        image,
        lang=LANGUAGE,
        config=config,
        output_type=Output.DICT,
        timeout=TIMEOUT_SECONDS,
    )
    words: list[str] = []
    confidences: list[float] = []
    for raw_text, raw_conf in zip(data.get("text", []), data.get("conf", [])):
        word = (raw_text or "").strip()
        try:
            conf = float(raw_conf)
        except (TypeError, ValueError):
            conf = -1
        if word:
            words.append(word)
            if conf >= 0:
                confidences.append(conf)

    # Reconstruct approximate lines using Tesseract's block/paragraph/line IDs.
    line_words: dict[tuple[str, str, str, str], list[str]] = {}
    for i, raw_text in enumerate(data.get("text", [])):
        word = (raw_text or "").strip()
        if not word:
            continue
        key = (
            str(data.get("block_num", [""])[i]),
            str(data.get("par_num", [""])[i]),
            str(data.get("line_num", [""])[i]),
            str(data.get("page_num", [""])[i]),
        )
        line_words.setdefault(key, []).append(word)
    text_lines = [" ".join(items) for items in line_words.values()]
    text = "\n".join(text_lines).strip()
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

    # Prefer substantial text with reasonable confidence, rather than selecting
    # a short high-confidence fragment over a fuller page transcription.
    score = len(words) * (0.35 + max(0.0, min(avg_conf, 100.0)) / 100.0)
    return {
        "text": text,
        "word_count": len(words),
        "average_confidence": round(avg_conf, 2),
        "score": score,
        "psm": psm,
    }


def write_text_safely(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(path)


def process_pdf(pdf_path: Path, output_root: Path, dpi: int) -> tuple[dict, list[dict]]:
    folder = output_root / pdf_path.stem
    folder.mkdir(parents=True, exist_ok=True)
    copied_pdf = folder / pdf_path.name
    if pdf_path.resolve() != copied_pdf.resolve():
        shutil.copy2(pdf_path, copied_pdf)

    txt_path = folder / f"{pdf_path.stem}.txt"
    header = [
        f"Source document: {pdf_path.name}",
        "OCR engine: Tesseract",
        f"OCR language: {LANGUAGE}",
        f"Render DPI: {dpi}",
        "Method: multiple page-segmentation modes; enhanced image; threshold retry for weak pages",
        "NOTE: OCR may misread small text, stamps, seals, handwriting, and low-quality scans.",
    ]
    page_rows: list[dict] = []

    with pymupdf.open(pdf_path) as pdf:
        total_pages = len(pdf)
        all_sections = header + [f"Total pages: {total_pages}"]
        write_text_safely(txt_path, "\n".join(all_sections) + "\n")

        for page_index, page in enumerate(pdf, start=1):
            print(f"  Page {page_index}/{total_pages}...", flush=True)
            page_errors: list[str] = []
            try:
                original = render_page(page, dpi)
                variants = preprocess_variants(original)
                candidates: list[dict] = []

                # PSM 3: automatic layout; PSM 4: column-oriented text; PSM 11: sparse text.
                for variant_name, image in variants[:1]:
                    for psm in (3, 4, 11):
                        try:
                            result = run_ocr(image, psm)
                            result["variant"] = variant_name
                            candidates.append(result)
                        except Exception as exc:
                            page_errors.append(f"{variant_name}/PSM{psm}: {exc}")

                best = max(candidates, key=lambda c: c["score"], default=None)
                # Retry with thresholding if blank or suspiciously short/low-confidence.
                needs_retry = (
                    best is None
                    or best["word_count"] < 12
                    or best["average_confidence"] < 35
                )
                if needs_retry:
                    for psm in (3, 11):
                        try:
                            result = run_ocr(variants[1][1], psm)
                            result["variant"] = "thresholded"
                            candidates.append(result)
                        except Exception as exc:
                            page_errors.append(f"thresholded/PSM{psm}: {exc}")
                    if candidates:
                        best = max(candidates, key=lambda c: c["score"])

                if best and best["text"]:
                    status = "success"
                    if best["word_count"] < 12 or best["average_confidence"] < 35:
                        status = "review_needed"
                    extracted = best["text"]
                    word_count = best["word_count"]
                    avg_conf = best["average_confidence"]
                    method = f'{best["variant"]}/PSM{best["psm"]}'
                else:
                    status = "empty_result"
                    extracted = "[NO TEXT RETURNED BY OCR. MANUAL REVIEW REQUIRED.]"
                    word_count = 0
                    avg_conf = 0.0
                    method = "none"

            except Exception as exc:
                status = "failed"
                extracted = f"[OCR FAILED: {exc}]"
                word_count = 0
                avg_conf = 0.0
                method = "none"
                page_errors.append(str(exc))

            all_sections.extend([
                "",
                "=" * 78,
                f"PAGE {page_index} | STATUS: {status} | WORDS: {word_count} | AVG CONFIDENCE: {avg_conf}",
                f"METHOD: {method}",
                "=" * 78,
                extracted,
            ])
            write_text_safely(txt_path, "\n".join(all_sections) + "\n")

            page_rows.append({
                "source_file": pdf_path.name,
                "page_number": page_index,
                "status": status,
                "word_count": word_count,
                "average_confidence": avg_conf,
                "method": method,
                "errors": " | ".join(page_errors),
            })
            print(f"    {status}; words={word_count}; confidence={avg_conf}; method={method}")

    failed = sum(row["status"] in {"failed", "empty_result", "review_needed"} for row in page_rows)
    summary = {
        "source_file": pdf_path.name,
        "total_pages": total_pages,
        "success_pages": sum(row["status"] == "success" for row in page_rows),
        "review_needed_pages": sum(row["status"] == "review_needed" for row in page_rows),
        "empty_pages": sum(row["status"] == "empty_result" for row in page_rows),
        "failed_pages": sum(row["status"] == "failed" for row in page_rows),
        "output_folder": str(folder),
        "text_file": str(txt_path),
        "status": "review_needed" if failed else "success",
    }
    return summary, page_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch OCR PDFs into per-document folders using Tesseract.")
    parser.add_argument("--input-dir", default=str(Path(__file__).resolve().parent / "input_pdfs"),
                        help="Folder containing source PDFs (not the ZIP file itself).")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parent / "output"),
                        help="Folder where per-PDF output folders will be created.")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help="PDF render DPI (default: 350).")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_root = Path(args.output_dir).expanduser().resolve()
    if not input_dir.is_dir():
        print(f"Input directory does not exist: {input_dir}")
        return 1

    pdfs = sorted(p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        print(f"No PDFs found directly inside: {input_dir}")
        print("Extract the source ZIP first, then pass the folder containing the PDF files with --input-dir.")
        return 1

    try:
        configure_tesseract()
    except Exception as exc:
        print("TESSERACT SETUP ERROR:", exc)
        return 1

    output_root.mkdir(parents=True, exist_ok=True)
    document_rows: list[dict] = []
    page_rows_all: list[dict] = []
    print(f"PDF files found: {len(pdfs)}")
    print(f"Output folder: {output_root}")

    for index, pdf_path in enumerate(pdfs, start=1):
        print(f"\n[{index}/{len(pdfs)}] Processing {pdf_path.name}")
        try:
            summary, page_rows = process_pdf(pdf_path, output_root, args.dpi)
            document_rows.append(summary)
            page_rows_all.extend(page_rows)
        except Exception as exc:
            print(f"Document error: {exc}")
            document_rows.append({
                "source_file": pdf_path.name, "total_pages": 0, "success_pages": 0,
                "review_needed_pages": 0, "empty_pages": 0, "failed_pages": 1,
                "output_folder": "", "text_file": "", "status": f"document_error: {exc}",
            })

    def save_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            return
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    save_csv(output_root / "document_summary.csv", document_rows)
    save_csv(output_root / "page_quality_report.csv", page_rows_all)
    print("\nBATCH OCR FINISHED")
    print(f"Documents processed: {len(document_rows)}")
    print(f"Pages processed: {sum(r['total_pages'] for r in document_rows)}")
    print(f"Pages needing review: {sum(r['review_needed_pages'] for r in document_rows)}")
    print(f"Empty pages: {sum(r['empty_pages'] for r in document_rows)}")
    print(f"Failed pages: {sum(r['failed_pages'] for r in document_rows)}")
    print(f"Document summary: {output_root / 'document_summary.csv'}")
    print(f"Page report: {output_root / 'page_quality_report.csv'}")
    print("Review rows marked review_needed, empty_result, or failed; 'success' does not guarantee perfect accuracy.")
    return 0 if all(r["failed_pages"] == 0 and r["empty_pages"] == 0 for r in document_rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
