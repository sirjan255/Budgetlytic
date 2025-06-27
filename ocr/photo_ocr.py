"""
photo_ocr.py

Note:
- This code only processes user-submitted images and does not store or share images or text without explicit user action.
- Requires your own Google Cloud Vision API key and compliance with its terms.
- No stored images or data are used outside your app’s intended user workflow.

This module provides a function to extract text from an image using the Google Cloud Vision API.
"""

from google.cloud import vision

def extract_text_from_image(image_bytes):
    """
    Extract text from image bytes using Google Cloud Vision OCR.

    Args:
        image_bytes (bytes): The image file content in bytes (e.g., from file.read()).

    Returns:
        str: The extracted text as a string, or an empty string if nothing detected.
    """
    # Creating a Google Cloud Vision client (assumes GOOGLE_APPLICATION_CREDENTIALS is set)
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""