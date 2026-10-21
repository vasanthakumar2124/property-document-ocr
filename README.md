# Property Document OCR

A Python-based OCR project for extracting text from property documents and full-search PDF records using Tesseract OCR and Google Cloud Document AI.

## Features

- Extract text from PDF documents using Tesseract OCR.
- Process PDF documents in batches using Google Document AI.
- Experiment with Google Document AI's OCR Processor and Form Parser.
- Check available Document AI processors.
- Save extracted text for downstream property-document analysis.

## Project Structure

```text
property-document-ocr/
├── src/
│   ├── batch_ocr.py
│   ├── check_processors.py
│   ├── test_form_parser.py
│   └── test_google_ocr.py
├── .gitignore
├── README.md
└── requirements.txt
```

Input PDFs, extracted OCR text, and generated output files are excluded from version control because property records may contain sensitive information.

## Requirements

- Python 3.12 or a compatible Python version
- Tesseract OCR (for Tesseract-based processing)
- Google Cloud project with the Document AI API enabled (for Google OCR and Form Parser)

## Installation

Clone the repository:

```bash
git clone https://github.com/vasanthakumar2124/property-document-ocr.git
cd property-document-ocr
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```bash
python -m pip install -r requirements.txt
```

## Google Cloud Setup

For Google Document AI scripts:

1. Create or select a Google Cloud project.
2. Enable the Document AI API.
3. Create the required OCR Processor or Form Parser processor.
4. Configure Application Default Credentials.
5. Update project, region, and processor settings in the relevant script or configure them through environment variables.

Never commit API keys, service-account credentials, or private property documents.

## Usage

Run the relevant script from the repository root, for example:

```bash
python src/check_processors.py
```

Refer to each script's configuration before running OCR or Form Parser processing. Input paths, processor IDs, and Google Cloud settings may need to be configured for your environment.

## Notes

This repository is intended for OCR experimentation and property-document text extraction. OCR output can contain errors, especially in handwritten text, tables, legal descriptions, and scanned records. Verify important names, dates, recording references, and property details against the original document.
