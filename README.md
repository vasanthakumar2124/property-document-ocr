# Improved Property PDF OCR (temporary standalone task)

This is a separate utility. It does not modify the existing DataFlood project.

## What changed
- Renders PDF pages at 350 DPI by default.
- Uses Tesseract with several page segmentation modes: PSM 3 (automatic layout), PSM 4 (column-oriented text), and PSM 11 (sparse text).
- Enhances contrast/sharpness and retries low-text or low-confidence pages using a thresholded image.
- Saves the selected OCR text page-by-page to reduce loss of progress if interrupted.
- Creates one folder per source PDF with the original PDF copy and a matching `.txt` file.
- Produces `document_summary.csv` and `page_quality_report.csv` so weak/empty pages can be reviewed.

## Important findings from the uploaded ZIP
The supplied `Example Docs.zip` contains **119 PDFs** (not 108) and **333 total pages**. The script will process all PDFs found directly inside the input folder. If only 108 should be processed, put only those 108 PDFs in the input folder.

## Setup on Windows
1. Extract `Example Docs.zip` to a folder, for example `C:\\Users\\YourName\\Documents\\Example Docs`.
2. Open PowerShell in this script folder and install dependencies:
   `python -m pip install -r requirements.txt`
3. Run the script with the extracted folder path:
   `python batch_ocr.py --input-dir "C:\\Users\\YourName\\Documents\\Example Docs"`
4. The default output folder is `output` beside the script. You can specify another location with `--output-dir "D:\\Property_OCR_Output"`.

The script finds Tesseract on PATH first, then checks `C:\\Program Files\\Tesseract-OCR\\tesseract.exe`. Edit `DEFAULT_TESSERACT` at the top of `batch_ocr.py` if needed.

## Output layout
```
output/
  111177/
    111177.pdf
    111177.txt
  1369366/
    1369366.pdf
    1369366.txt
  document_summary.csv
  page_quality_report.csv
```

## Limitations
OCR cannot guarantee correctness on faint scans, handwritten notes, stamps, seals, tiny text, or skewed pages. A page marked `success` only means some text was returned. Review low-confidence/empty pages and compare important property fields against the source PDF. The multi-pass selection improves coverage but cannot guarantee that every field is captured.
