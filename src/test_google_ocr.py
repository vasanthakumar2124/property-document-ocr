
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter
from google.api_core.client_options import ClientOptions
from google.cloud import documentai

PROJECT_ID = "skp-project-512307"
LOCATION = "asia-southeast1"
PROCESSOR_ID = "41435869e50a798d"

BASE_DIR = Path(__file__).resolve().parent
INPUT_PDF = BASE_DIR / "Full_Docs" / "Search docs.pdf"
OUTPUT_FILE = BASE_DIR / "Full_Docs" / "full_search_ocr.txt"

# Your processor's reported synchronous limit is 30 pages.
BATCH_SIZE = 15


def extract_page_text(page, document):
    """Get the text associated with one page."""
    if not page.layout or not page.layout.text_anchor:
        return ""

    parts = []
    for segment in page.layout.text_anchor.text_segments:
        start = int(segment.start_index or 0)
        end = int(segment.end_index)
        parts.append(document.text[start:end])

    return "".join(parts).strip()


def main():
    if not INPUT_PDF.exists():
        print(f"PDF not found: {INPUT_PDF}")
        return

    reader = PdfReader(str(INPUT_PDF))
    total_pages = len(reader.pages)

    print(f"Input PDF: {INPUT_PDF.name}")
    print(f"Total pages: {total_pages}")

    client = documentai.DocumentProcessorServiceClient(
        client_options=ClientOptions(
            api_endpoint=f"{LOCATION}-documentai.googleapis.com"
        )
    )

    processor_name = client.processor_path(
        PROJECT_ID, LOCATION, PROCESSOR_ID
    )

    with TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        with OUTPUT_FILE.open("w", encoding="utf-8") as output:
            output.write(f"Source PDF: {INPUT_PDF.name}\n")
            output.write(f"Total source pages: {total_pages}\n")

            for start in range(0, total_pages, BATCH_SIZE):
                end = min(start + BATCH_SIZE, total_pages)

                print(
                    f"\nProcessing source pages "
                    f"{start + 1}-{end}..."
                )

                # Create a temporary PDF containing this batch.
                writer = PdfWriter()
                for index in range(start, end):
                    writer.add_page(reader.pages[index])

                chunk_path = temp_dir / f"batch_{start + 1}_{end}.pdf"
                with chunk_path.open("wb") as chunk_file:
                    writer.write(chunk_file)

                # Send the batch to Document AI.
                with chunk_path.open("rb") as pdf_file:
                    raw_document = documentai.RawDocument(
                        content=pdf_file.read(),
                        mime_type="application/pdf",
                    )

                request = documentai.ProcessRequest(
                    name=processor_name,
                    raw_document=raw_document,
                )

                result = client.process_document(request=request)
                document = result.document

                print(f"Pages returned: {len(document.pages)}")

                if len(document.pages) != end - start:
                    raise RuntimeError(
                        f"Expected {end - start} pages in batch "
                        f"{start + 1}-{end}, but received "
                        f"{len(document.pages)}. Stopping to avoid "
                        "silently producing an incomplete output."
                    )

                # Preserve the original source page numbers.
                for page in document.pages:
                    source_page_number = start + page.page_number

                    output.write(
                        f"\n{'=' * 35}\n"
                        f"SOURCE PAGE {source_page_number}\n"
                        f"{'=' * 35}\n"
                    )

                    page_text = extract_page_text(page, document)
                    output.write(page_text + "\n")

                output.flush()
                print(f"Completed source pages {start + 1}-{end}")

    print("\nOCR processing completed!")
    print(f"Total source pages: {total_pages}")
    print(f"Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
