
from google.cloud import documentai_v1 as documentai
from google.api_core.client_options import ClientOptions

PROJECT_ID = "skp-project-512307"
LOCATION = "asia-southeast1"
PROCESSOR_ID = "41435869e50a798d"

options = ClientOptions(
    api_endpoint=f"{LOCATION}-documentai.googleapis.com"
)

client = documentai.DocumentProcessorServiceClient(
    client_options=options
)

name = client.processor_path(
    PROJECT_ID,
    LOCATION,
    PROCESSOR_ID
)

try:
    processor = client.get_processor(name=name)
    print("Google Document AI connection successful!")
    print("Processor name:", processor.display_name)
    print("Processor type:", processor.type_)
    print("Processor ID:", PROCESSOR_ID)
    print("Status:", processor.state.name)

except Exception as error:
    print("Connection failed:", error)
