import re
import os
import logging
from PyPDF2 import PdfReader
from docx import Document
from utils.text_processing import clean_text

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        logger.info(f"Extracting text from PDF: {pdf_path}")
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            num_pages = len(reader.pages)
            logger.info(f"PDF has {num_pages} pages.")
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        logger.info(f"Successfully extracted {len(text)} characters from PDF.")
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}", exc_info=True)
    return text

def extract_text_from_docx(docx_path):
    text = ""
    try:
        logger.info(f"Extracting text from DOCX: {docx_path}")
        doc = Document(docx_path)
        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"
        logger.info(f"Successfully extracted {len(text)} characters from DOCX.")
    except Exception as e:
        logger.error(f"Error processing DOCX {docx_path}: {e}", exc_info=True)
    return text

def process_resume(file_path):
    logger.info(f"Processing resume file: {file_path}")
    text = ""
    try:
        if file_path.endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif file_path.endswith('.docx'):
            text = extract_text_from_docx(file_path)
        else:
            logger.info("Processing as plain text file.")
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    text = file.read()
            except UnicodeDecodeError:
                logger.warning("UTF-8 decode failed, trying latin-1.")
                with open(file_path, 'r', encoding='latin-1') as file:
                    text = file.read()
        
        cleaned_text = clean_text(text)
        logger.info(f"Finished processing resume. Cleaned text length: {len(cleaned_text)}")
        return cleaned_text
    except Exception as e:
        logger.error(f"General error in process_resume for {file_path}: {e}", exc_info=True)
        return ""

def process_jd(file_path):
    return process_resume(file_path)