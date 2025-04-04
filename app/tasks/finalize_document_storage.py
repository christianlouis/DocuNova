#!/usr/bin/env python3

import os
import requests
import logging
import tempfile
from app.config import settings
from app.tasks.retry_config import BaseTaskWithRetry
# Import the shared Celery instance
from app.celery_app import celery

# 1) Import the aggregator task
from app.tasks.send_to_all import send_to_all_destinations

logger = logging.getLogger(__name__)


@celery.task(base=BaseTaskWithRetry)
def convert_to_pdfa(pdf_file_path):
    """
    Converts a regular PDF to PDF/A format using Gotenberg's API.
    
    Args:
        pdf_file_path: Path to the PDF file to convert
        
    Returns:
        Path to the converted PDF/A file
    """
    gotenberg_url = getattr(settings, "gotenberg_url", None)
    if not gotenberg_url:
        logger.error("Gotenberg URL is not configured in settings.")
        return pdf_file_path

    # Set PDF/A compliance level
    pdfa_level = settings.pdf_pdfa_level

    # Gotenberg URL for PDF/A conversion
    endpoint = f"{gotenberg_url}/forms/pdfengines/convert/pdfa"

    try:
        with open(pdf_file_path, "rb") as f:
            # Prepare form data for Gotenberg
            files = {"file": f}
            data = {"pdfa": pdfa_level}  # 1b, 2b, 3b
            
            response = requests.post(endpoint, files=files, data=data)

        if response.status_code == 200:
            # Create a new filename with -pdfa suffix
            base_name, ext = os.path.splitext(pdf_file_path)
            pdfa_file_path = f"{base_name}-pdfa{ext}"
            
            # Write the PDF/A content to file
            with open(pdfa_file_path, "wb") as out_file:
                out_file.write(response.content)
            logger.info(f"Converted to PDF/A: {pdfa_file_path}")
            return pdfa_file_path
        else:
            logger.error(f"PDF/A conversion failed for {pdf_file_path}. Status code: {response.status_code}")
            return pdf_file_path
    except Exception as e:
        logger.exception(f"Error converting to PDF/A: {e}")
        return pdf_file_path


@celery.task(base=BaseTaskWithRetry)
def finalize_document_storage(original_file: str, processed_file: str, metadata: dict):
    """
    Final storage step after embedding metadata.
    We will now call 'send_to_all_destinations' to push the final PDF to Dropbox/Nextcloud/Paperless.
    
    If PDF/A generation is enabled, we'll first convert the file to PDF/A format.
    """
    print(f"[INFO] Finalizing document storage for {processed_file}")

    # Check if we should generate PDF/A variant
    if settings.pdf_generate_pdfa:
        print(f"[INFO] Converting {processed_file} to PDF/A format")
        pdfa_file = convert_to_pdfa(processed_file)
        
        # If conversion was successful, use the PDF/A file instead
        if pdfa_file != processed_file:
            processed_file = pdfa_file
            print(f"[INFO] Using PDF/A variant: {processed_file}")

    # 2) Enqueue uploads to all destinations (Dropbox, Nextcloud, Paperless)
    send_to_all_destinations.delay(processed_file)

    return {
        "status": "Completed",
        "file": processed_file
    }
