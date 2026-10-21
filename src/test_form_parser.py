
from pathlib import Path
from google.api_core.client_options import ClientOptions
from google.cloud import documentai_v1 as documentai

PROJECT_ID = "skp-project-512307"
LOCATION = "asia-southeast1"
PROCESSOR_ID = "e38a25ecb85d10e2"

PDF_PATH = Path("26-1345.pdf")
OUTPUT_PATH = Path("26-1345_form_parser.txt")

client = documentai.DocumentProcessorServiceClient(
    client_options=ClientOptions(
        api_endpoint=f"{LOCATION}-documentai.googleapis.com"
    )
)

processor_name = client.processor_path(
    PROJECT_ID, LOCATION, PROCESSOR_ID
)

if not PDF_PATH.exists():
    raise FileNotFoundError(f"PDF not found: {PDF_PATH.resolve()}")

request = documentai.ProcessRequest(
    name=processor_name,
    raw_document=documentai.RawDocument(
        content=PDF_PATH.read_bytes(),
        mime_type="application/pdf",
    ),
)

print(f"Sending {PDF_PATH.name} to Google Document AI Form Parser...")

result = client.process_document(request=request)
document = result.document

# Save extracted text
OUTPUT_PATH.write_text(document.text, encoding="utf-8")

print("\nForm Parser completed successfully!")
print(f"Characters extracted: {len(document.text)}")
print(f"Text saved to: {OUTPUT_PATH.resolve()}")

# Display detected form fields
print("\n--- Detected Form Fields ---")

for page_number, page in enumerate(document.pages, start=1):
    for field in page.form_fields:
        field_name = field.field_name.text_anchor.content if field.field_name.text_anchor else ""
        field_value = field.field_value.text_anchor.content if field.field_value.text_anchor else ""

        print(f"Page {page_number}")
        print(f"Field: {field_name.strip()}")
        print(f"Value: {field_value.strip()}")
        print("-" * 40)

# Display detected tables
print("\n--- Detected Tables ---")

for page_number, page in enumerate(document.pages, start=1):
    for table_number, table in enumerate(page.tables, start=1):
        print(f"Page {page_number}, Table {table_number}")
        print(f"Rows: {len(table.body_rows)}")
