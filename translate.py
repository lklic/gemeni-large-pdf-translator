import os
import fitz  # PyMuPDF
from PIL import Image, ImageFile, PngImagePlugin
import io
from dotenv import load_dotenv

# Enable PIL plugin loading and truncated image support
ImageFile.LOAD_TRUNCATED_IMAGES = True
import google.generativeai as genai
import concurrent.futures
import re
import time
import logging
from threading import Lock
from cost_tracker import GeminiCostTracker, extract_token_usage

# Load environment variables from .env file
load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel('gemini-2.5-pro')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration constants
MAX_RETRY_ATTEMPTS = 5  # Single source of truth for retry attempts

# Thread-safe progress tracking
progress_lock = Lock()

def clean_and_validate_markdown(text):
    """Enhanced cleaning function to remove HTML entities and markup."""
    # Clean HTML entities
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    
    # Remove HTML tags (br, p, div, etc.)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p\s*/?>', '\n\n', text)
    text = re.sub(r'</p>', '', text)
    text = re.sub(r'<div[^>]*>', '', text)
    text = re.sub(r'</div>', '', text)
    text = re.sub(r'<[^>]+>', '', text)  # Remove any remaining HTML tags
    
    # Remove code block wrapping if present (from AI response)
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.split('\n')
        # Remove first and last lines if they are just ```
        if lines[0].strip() == "```" or lines[0].strip().startswith("```markdown"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = '\n'.join(lines)
    
    # Clean up excessive whitespace while preserving intentional spacing
    text = re.sub(r'\n{4,}', '\n\n\n', text)  # Max 3 consecutive newlines
    text = re.sub(r'[ \t]+\n', '\n', text)  # Remove trailing spaces
    
    return text.strip()

def transcribe_page_to_markdown(image, page_num, filename, cost_tracker=None):
    """Stage 1: Transcribe page to markdown with perfect layout preservation."""
    logger.info(f"[{filename}] Starting transcription for page {page_num}")
    start_time = time.time()
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            logger.info(f"[{filename}] Page {page_num} transcription attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}")
            
            response = model.generate_content([
                """TASK: Extract text as clean markdown with perfect layout preservation

This is a PDF page from a scanned book. Convert ALL text to markdown format while preserving:

FORMATTING RULES:
- Every single line break and spacing exactly as shown
- All indentation and alignment using proper markdown
- Convert formatting to markdown (*italics*, **bold**, headers with #)
- Preserve table-of-contents formatting with dot leaders
- Maintain footnote positioning and numbering
- Keep page numbers and headers in correct positions
- Use markdown hard line breaks (two spaces + newline) for single line breaks
- Use double newlines only for true paragraph separations

CRITICAL: NO HTML TAGS ALLOWED
- Never use <br>, <p>, <div>, or any HTML tags
- Use only markdown syntax for formatting
- Use proper line breaks and spacing instead of HTML

OUTPUT: Clean markdown with perfect layout preservation and NO HTML markup.""",
                image
            ])
            
            # Track cost if cost_tracker is provided
            if cost_tracker:
                input_tokens, output_tokens = extract_token_usage(response)
                elapsed_time = time.time() - start_time
                cost_tracker.log_api_call('transcription', page_num, input_tokens, output_tokens, elapsed_time)
            
            transcribed_text = clean_and_validate_markdown(response.text)
            elapsed_time = time.time() - start_time
            
            logger.info(f"[{filename}] Page {page_num} transcription completed successfully in {elapsed_time:.2f}s")
            return transcribed_text
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{filename}] Page {page_num} transcription attempt {attempt + 1} failed after {elapsed_time:.2f}s: {e}")
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                error_msg = f"Error: Could not transcribe page {page_num} after {MAX_RETRY_ATTEMPTS} attempts. {e}"
                logger.error(f"[{filename}] Page {page_num} transcription failed completely")
                return error_msg
    
    return f"Error: Transcription failed after {MAX_RETRY_ATTEMPTS} attempts."

def translate_markdown_page(markdown_text, page_num, filename, cost_tracker=None):
    """Stage 2: Translate markdown text to English."""
    logger.info(f"[{filename}] Starting translation for page {page_num}")
    start_time = time.time()
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            logger.info(f"[{filename}] Page {page_num} translation attempt {attempt + 1}/{MAX_RETRY_ATTEMPTS}")
            
            response = model.generate_content([
                f"""TASK: Translate the text to English

Translate this markdown text to English while:

FORMATTING RULES:
- Keeping ALL markdown formatting exactly as is
- Maintaining identical structure and layout
- Preserving all markdown syntax (*italics*, **bold**, headers, etc.)
- Keeping line breaks and spacing unchanged
- Maintaining footnotes, page numbers, and structural elements

TRANSLATION RULES:
- Translate only the main language content to English
- Keep proper nouns, place names, and technical terms appropriately
- Maintain academic tone and terminology
- Preserve citations and references exactly

CRITICAL: Output clean markdown only - NO HTML tags or code blocks

---

{markdown_text}"""
            ])
            
            # Track cost if cost_tracker is provided
            if cost_tracker:
                input_tokens, output_tokens = extract_token_usage(response)
                elapsed_time = time.time() - start_time
                cost_tracker.log_api_call('translation', page_num, input_tokens, output_tokens, elapsed_time)
            
            translated_text = clean_and_validate_markdown(response.text)
            elapsed_time = time.time() - start_time
            
            logger.info(f"[{filename}] Page {page_num} translation completed successfully in {elapsed_time:.2f}s")
            return translated_text
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"[{filename}] Page {page_num} translation attempt {attempt + 1} failed after {elapsed_time:.2f}s: {e}")
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                error_msg = f"Error: Could not translate page {page_num} after {MAX_RETRY_ATTEMPTS} attempts. {e}"
                logger.error(f"[{filename}] Page {page_num} translation failed completely")
                return error_msg
    
    return f"Error: Translation failed after {MAX_RETRY_ATTEMPTS} attempts."

def save_page_file(content, page_num, folder_path, stage_name, filename):
    """Save individual page content to specified folder."""
    try:
        os.makedirs(folder_path, exist_ok=True)
        page_file_path = os.path.join(folder_path, f"page_{page_num}.md")
        
        with open(page_file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"[{filename}] Page {page_num} {stage_name} saved to {page_file_path}")
        return True
        
    except Exception as e:
        logger.error(f"[{filename}] Failed to save page {page_num} {stage_name}: {e}")
        return False

def compile_final_document(translation_folder, output_path, filename, num_pages):
    """Stage 3: Compile all translated pages into final document."""
    logger.info(f"[{filename}] Starting compilation of {num_pages} pages")
    start_time = time.time()
    
    try:
        final_markdown = ""
        
        for page_num in range(1, num_pages + 1):
            page_file_path = os.path.join(translation_folder, f"page_{page_num}.md")
            
            if os.path.exists(page_file_path):
                with open(page_file_path, 'r', encoding='utf-8') as f:
                    page_content = f.read()
                
                # Only add page separator if content exists and isn't an error
                if page_content.strip() and not page_content.startswith("Error:"):
                    # Add page delimiter before each page (except the first one)
                    if page_num > 1:
                        final_markdown += f"\n\n## PDF Page: {page_num} \n\n"
                    elif page_num == 1:
                        # Add delimiter for first page too
                        final_markdown += f"## PDF Page: {page_num} \n\n"
                    
                    final_markdown += page_content + "\n\n"
                    logger.info(f"[{filename}] Added page {page_num} to final document")
                else:
                    logger.warning(f"[{filename}] Page {page_num} is empty or contains errors, skipping")
            else:
                logger.warning(f"[{filename}] Page {page_num} translation file not found: {page_file_path}")
        
        # Save final compiled document
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(final_markdown)
        
        elapsed_time = time.time() - start_time
        logger.info(f"[{filename}] Final document compiled successfully in {elapsed_time:.2f}s: {output_path}")
        return True
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[{filename}] Compilation failed after {elapsed_time:.2f}s: {e}")
        return False

def transcribe_single_page(page_data, transcription_folder, filename, progress_tracker, cost_tracker=None):
    """Transcribe a single page and save it."""
    page_num, image, is_blank = page_data
    
    if is_blank:
        logger.info(f"[{filename}] Page {page_num} is blank, skipping transcription")
        save_page_file("", page_num, transcription_folder, "transcription", filename)
        
        with progress_lock:
            progress_tracker['transcribed'] += 1
            progress = int((progress_tracker['transcribed'] + progress_tracker['translated']) / (progress_tracker['total_pages'] * 2) * 95)
            progress_tracker['progress'][filename] = progress
            logger.info(f"[{filename}] Progress: {progress_tracker['transcribed']}/{progress_tracker['total_pages']} pages transcribed ({progress}%)")
        
        return page_num, ""
    
    # Transcribe the page
    transcribed_text = transcribe_page_to_markdown(image, page_num, filename, cost_tracker)
    
    # Save transcription
    if not save_page_file(transcribed_text, page_num, transcription_folder, "transcription", filename):
        return page_num, f"Error: Failed to save transcription for page {page_num}"
    
    with progress_lock:
        progress_tracker['transcribed'] += 1
        progress = int((progress_tracker['transcribed'] + progress_tracker['translated']) / (progress_tracker['total_pages'] * 2) * 95)
        progress_tracker['progress'][filename] = progress
        logger.info(f"[{filename}] Progress: {progress_tracker['transcribed']}/{progress_tracker['total_pages']} pages transcribed ({progress}%)")
    
    return page_num, transcribed_text

def translate_single_page(page_num, transcribed_text, translation_folder, filename, progress_tracker, cost_tracker=None):
    """Translate a single transcribed page and save it."""
    if not transcribed_text or transcribed_text.startswith("Error:"):
        # Save error or empty content
        save_page_file(transcribed_text, page_num, translation_folder, "translation", filename)
        
        with progress_lock:
            progress_tracker['translated'] += 1
            progress = int((progress_tracker['transcribed'] + progress_tracker['translated']) / (progress_tracker['total_pages'] * 2) * 95)
            progress_tracker['progress'][filename] = progress
            logger.info(f"[{filename}] Progress: {progress_tracker['translated']}/{progress_tracker['total_pages']} pages translated ({progress}%)")
        
        return page_num, transcribed_text
    
    # Translate the page
    translated_text = translate_markdown_page(transcribed_text, page_num, filename, cost_tracker)
    
    # Save translation
    if not save_page_file(translated_text, page_num, translation_folder, "translation", filename):
        translated_text = f"Error: Failed to save translation for page {page_num}"
    
    with progress_lock:
        progress_tracker['translated'] += 1
        progress = int((progress_tracker['transcribed'] + progress_tracker['translated']) / (progress_tracker['total_pages'] * 2) * 95)
        progress_tracker['progress'][filename] = progress
        logger.info(f"[{filename}] Progress: {progress_tracker['translated']}/{progress_tracker['total_pages']} pages translated ({progress}%)")
    
    return page_num, translated_text

def translate_pdf(pdf_path, translation_progress):
    """Enhanced three-stage PDF translation with true concurrent processing and cost tracking."""
    filename = os.path.basename(pdf_path)
    logger.info(f"[{filename}] Starting enhanced PDF translation process")
    start_time = time.time()
    
    # Use directory name without .pdf extension to match app.py structure
    dir_name = os.path.splitext(filename)[0]
    pdf_dir = os.path.join('data', dir_name)
    
    # Create folder structure
    transcription_folder = os.path.join(pdf_dir, 'transcription')
    translation_folder = os.path.join(pdf_dir, 'translation')
    
    logger.info(f"[{filename}] Creating directory structure:")
    logger.info(f"[{filename}] - Main: {pdf_dir}")
    logger.info(f"[{filename}] - Transcription: {transcription_folder}")
    logger.info(f"[{filename}] - Translation: {translation_folder}")
    
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(transcription_folder, exist_ok=True)
    os.makedirs(translation_folder, exist_ok=True)

    # Initialize cost tracker
    cost_tracker = GeminiCostTracker(pdf_dir, filename)
    logger.info(f"[{filename}] Cost tracking initialized")

    try:
        # Extract pages from PDF
        logger.info(f"[{filename}] Opening PDF and extracting pages")
        doc = fitz.open(pdf_path)
        num_pages = len(doc)
        logger.info(f"[{filename}] PDF contains {num_pages} pages")
        
        page_images = []
        for page_num, page in enumerate(doc):
            if not page.get_text() and not page.get_images():
                page_images.append((page_num + 1, None, True))
                logger.info(f"[{filename}] Page {page_num + 1} is blank")
            else:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_images.append((page_num + 1, img, False))
                logger.info(f"[{filename}] Page {page_num + 1} extracted successfully")
        
        doc.close()
        logger.info(f"[{filename}] PDF extraction completed")

        # Initialize progress tracker
        progress_tracker = {
            'transcribed': 0,
            'translated': 0,
            'total_pages': num_pages,
            'progress': translation_progress
        }

        # Stage 1: Concurrent transcription of ALL pages
        logger.info(f"[{filename}] Starting Stage 1: Concurrent transcription of all {num_pages} pages")
        transcription_results = {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as transcription_executor:
            # Submit all transcription tasks at once
            transcription_futures = {
                transcription_executor.submit(transcribe_single_page, page_data, transcription_folder, filename, progress_tracker, cost_tracker): page_data[0]
                for page_data in page_images
            }
            
            # Stage 2: Start translation immediately as each transcription completes
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as translation_executor:
                translation_futures = {}
                
                # Process transcription results as they complete
                for transcription_future in concurrent.futures.as_completed(transcription_futures):
                    page_num, transcribed_text = transcription_future.result()
                    transcription_results[page_num] = transcribed_text
                    
                    # Immediately start translation for this page
                    translation_future = translation_executor.submit(
                        translate_single_page, page_num, transcribed_text, translation_folder, filename, progress_tracker, cost_tracker
                    )
                    translation_futures[translation_future] = page_num
                
                # Wait for all translations to complete
                translation_results = {}
                for translation_future in concurrent.futures.as_completed(translation_futures):
                    page_num, translated_text = translation_future.result()
                    translation_results[page_num] = translated_text

        # Stage 3: Compilation
        logger.info(f"[{filename}] Starting Stage 3: Compilation")
        output_path = os.path.join(pdf_dir, 'translated.md')
        
        if compile_final_document(translation_folder, output_path, filename, num_pages):
            # Final progress update
            translation_progress[filename] = 100
            elapsed_time = time.time() - start_time
            logger.info(f"[{filename}] Enhanced PDF translation completed successfully in {elapsed_time:.2f}s")
        else:
            translation_progress[filename] = -1
            logger.error(f"[{filename}] PDF translation failed during compilation")
            
        # Save cost tracking data
        cost_tracker.save_cost_log()
        cost_summary = cost_tracker.save_cost_summary()
        
        if cost_summary:
            logger.info(f"[{filename}] Cost tracking completed - Total: ${cost_summary['total_cost']:.6f}")
        
    except Exception as e:
        elapsed_time = time.time() - start_time
        logger.error(f"[{filename}] Enhanced PDF translation failed after {elapsed_time:.2f}s: {e}")
        translation_progress[filename] = -1
        
        # Still save cost data even if translation failed
        try:
            cost_tracker.save_cost_log()
            cost_tracker.save_cost_summary()
        except Exception as cost_error:
            logger.error(f"[{filename}] Failed to save cost data: {cost_error}")
