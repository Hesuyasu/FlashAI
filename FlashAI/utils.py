"""Utility helpers for PDF text extraction and AI flashcard generation.

The AI generation attempts to use the Bytez SDK if available and an API key
is configured (env var BYTEZ_API_KEY). If that fails, a deterministic fallback
heuristic creates simple flashcards by splitting the text into sentences.
"""

import json
import re

try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover
    PyPDF2 = None

try:
    from decouple import config  # type: ignore
except Exception:  # pragma: no cover
    def config(key, default=None):
        return default

try:
    from bytez import Bytez  # type: ignore
except Exception:  # pragma: no cover
    Bytez = None


def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_text_from_pdf(pdf_file):
    """Extract raw text from a PDF file-like object.

    Accepts an uploaded file or opened FileField. Returns empty string if
    PyPDF2 is unavailable or parsing fails.
    """
    if not PyPDF2:
        return ""
    text = ""
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text
    except Exception as e:  # pragma: no cover
        print("PDF extraction error:", e)
        return ""
    return text


def extract_last_json_array(text):
    matches = re.findall(r'\[[\s\S]*?\]', text)
    return matches[-1] if matches else None


def _fallback_flashcards(cleaned_text, limit=3):
    """Generate better Q/A pairs heuristically from sentences.

    Attempts to form definition-style questions like "What is X?" by parsing
    common patterns ("X is ...", "X are ...", "X: ...", "X - ...").
    Falls back to a concise summary question when no pattern matches.
    """

    def normalize_subject(subj: str) -> str:
        subj = subj.strip().strip(' .,:;\t\n\r')
        # Drop leading context like "In networking," or articles
        subj = re.sub(r'^(?:In|On|At|During|Within|From)\s+[^,]+,\s*', '', subj, flags=re.I)
        subj = re.sub(r'^(?:an?|the)\s+', '', subj, flags=re.I)
        # Title-case short subjects lightly (avoid shouting for ALL CAPS)
        if len(subj) <= 60:
            subj = subj[0:1].upper() + subj[1:]
        return subj

    def derive_qa(sentence: str):
        s = sentence.strip()
        if len(s) < 10:
            return None
        # Handle colon or hyphen definition: "Term: definition" or "Term - definition"
        m = re.match(r'^\s*([^:\-]{2,80})\s*[:\-]\s+(.+)$', s)
        if m:
            subj, rest = m.group(1), m.group(2)
            subj = normalize_subject(subj)
            if subj:
                qverb = 'are' if re.search(r'\b(s|S)\b$|\band\b', subj) or subj.lower().endswith('s') else 'is'
                question = f"What {qverb} {subj}?"
                answer = (f"{subj} {qverb} " + rest).strip()
                return question[:120], answer[:300]

        # Handle "X is Y" and "X are Y"
        m = re.match(r'^\s*(?:In\s+[^,]+,\s*)?(?:The\s+|An\s+|A\s+)?([^.!?]{2,80}?)\s+is\s+(.+)$', s, flags=re.I)
        if m:
            subj, pred = m.group(1), m.group(2)
            subj = normalize_subject(subj)
            question = f"What is {subj}?"
            answer = f"{subj} is {pred}"
            return question[:120], answer[:300]
        m = re.match(r'^\s*(?:In\s+[^,]+,\s*)?(?:The\s+|An\s+|A\s+)?([^.!?]{2,80}?)\s+are\s+(.+)$', s, flags=re.I)
        if m:
            subj, pred = m.group(1), m.group(2)
            subj = normalize_subject(subj)
            question = f"What are {subj}?"
            answer = f"{subj} are {pred}"
            return question[:120], answer[:300]

        # Handle "X means/ refers to/ stands for/ is defined as Y"
        m = re.match(r'^\s*(?:The\s+|An\s+|A\s+)?([^.!?]{2,80}?)\s+(means|refers to|stands for|is defined as)\s+(.+)$', s, flags=re.I)
        if m:
            subj, verb, rest = m.group(1), m.group(2).lower(), m.group(3)
            subj = normalize_subject(subj)
            if verb == 'means' or verb == 'refers to' or verb == 'is defined as':
                question = f"What is {subj}?"
                answer = f"{subj} {verb} {rest}"
            else:  # stands for
                question = f"What does {subj} stand for?"
                answer = f"{subj} stands for {rest}"
            return question[:120], answer[:300]

        # Fallback: use first few words as a topic
        words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", s)
        topic = ' '.join(words[:5]) if words else 'this topic'
        topic = normalize_subject(topic)
        qverb = 'are' if topic.endswith('s') else 'is'
        question = f"What {qverb} {topic}?"
        answer = s
        return question[:120], answer[:300]

    sentences = re.split(r'[.!?]\s+', cleaned_text)
    cards = []
    for s in sentences:
        if len(cards) >= limit:
            break
        qa = derive_qa(s)
        if not qa:
            continue
        q, a = qa
        if q and a:
            cards.append({"question": q, "answer": a})
    return cards


def generate_flashcards_with_ai(text):
    """Attempt AI generation; fallback to heuristic if unavailable.

    Returns list of dicts: [{question: str, answer: str}, ...]
    """
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return []

    api_key = config('BYTEZ_API_KEY', default=None)
    if not (api_key and Bytez):
        return _fallback_flashcards(cleaned_text)

    try:
        sdk = Bytez(api_key)
        model = sdk.model("Qwen/Qwen3-4B-Instruct-2507")
        prompt = (
            "Generate exactly 3 study flashcards as a JSON array, nothing else. "
            "Each flashcard MUST be a multiple-choice question with these exact keys: "
            "'question', 'answer', 'option_a', 'option_b', 'option_c', 'option_d', and 'correct_option' (one of A, B, C, D). "
            "'question' is the question text, 'answer' is a brief explanation of why the correct option is right, "
            "options are the four choices (with one correct and three plausible distractors), and 'correct_option' is the letter (A, B, C, or D) of the right answer. "
            "Example: {\"question\": \"The server in a REST API hosts the data or functionality?\", \"answer\": \"The server hosts functionality and provides access to resources through endpoints.\", \"option_a\": \"Data\", \"option_b\": \"Functionality\", \"option_c\": \"Network\", \"option_d\": \"Protocol\", \"correct_option\": \"B\"}. "
            "Output ONLY a valid JSON array starting with '[' and ending with ']'. "
            "Do NOT include any explanation, markdown, code blocks, or reasoning. "
            f"Text: {cleaned_text[:1000]}"
        )
        output = model.run([
            {"role": "user", "content": prompt}
        ])
        
        # DEBUG: Print raw AI response
        print("=" * 80)
        print("RAW AI RESPONSE:")
        print(output)
        print("=" * 80)
        
        # Handle new Response object structure
        if hasattr(output, 'output') and isinstance(output.output, dict):
            content = output.output.get('content')
        elif isinstance(output, dict):
            content = output.get('content')
        else:
            content = str(output)
        
        if not content:
            print("WARNING: No content extracted from AI response")
            return _fallback_flashcards(cleaned_text)
        
        json_string = extract_last_json_array(content)
        if not json_string:
            print("WARNING: No JSON array found in AI response")
            return _fallback_flashcards(cleaned_text)
        
        print("EXTRACTED JSON STRING:")
        print(json_string)
        print("=" * 80)
        
        flashcards = json.loads(json_string)
        if not isinstance(flashcards, list):
            return _fallback_flashcards(cleaned_text)
        
        # DEBUG: Print parsed flashcards
        print("PARSED FLASHCARDS:")
        for idx, c in enumerate(flashcards[:10]):
            print(f"Card {idx + 1}:", c)
        print("=" * 80)
        
        # Basic validation of keys
        valid = []
        for c in flashcards[:10]:
            q = c.get('question') or c.get('Question')
            a = c.get('answer') or c.get('Answer')
            if q and a:
                card_data = {'question': str(q)[:255], 'answer': str(a)[:1000]}
                # Include MCQ fields if present
                if c.get('option_a'):
                    card_data['option_a'] = str(c.get('option_a', ''))[:255]
                    card_data['option_b'] = str(c.get('option_b', ''))[:255]
                    card_data['option_c'] = str(c.get('option_c', ''))[:255]
                    card_data['option_d'] = str(c.get('option_d', ''))[:255]
                    card_data['correct_option'] = str(c.get('correct_option', ''))[:1].upper()
                    print(f"MCQ DETECTED: {card_data['question'][:50]}... with options A-D")
                else:
                    print(f"REGULAR Q&A: {card_data['question'][:50]}...")
                valid.append(card_data)
        return valid or _fallback_flashcards(cleaned_text)
    except Exception as e:  # pragma: no cover
        print("AI generation exception:", e)
        return _fallback_flashcards(cleaned_text)
