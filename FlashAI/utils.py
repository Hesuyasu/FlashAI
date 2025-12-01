"""Utility helpers for PDF text extraction and AI flashcard generation.

The AI generation attempts to use the Bytez SDK if available and an API key
is configured (env var BYTEZ_API_KEY). If that fails, a deterministic fallback
heuristic creates simple flashcards by splitting the text into sentences.
"""

import json
import re
import random

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    from decouple import config
except Exception:
    def config(key, default=None):
        return default

try:
    from django.conf import settings
except Exception:
    settings = None

try:
    from bytez import Bytez 
except Exception: 
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
    except Exception as e: 
        print("PDF extraction error:", e)
        return ""
    return text


def extract_last_json_array(text):
    if not text:
        return None
    # Prefer the last bracketed array; tolerate leading/trailing noise
    matches = re.findall(r'\[[\s\S]*?\]', text)
    js = matches[-1] if matches else None
    if js:
        s = js.strip()
        # Remove common markdown wrappers
        if s.startswith("```"):
            s = s.strip('`').strip()
        return s
    # Attempt salvage if response starts an array but is truncated (missing closing ])
    start_idx = text.find('[')
    if start_idx != -1:
        candidate = text[start_idx:]
        # If there is no closing bracket, attempt to auto-complete
        if ']' not in candidate:
            # Balance curly braces inside array
            open_obj = candidate.count('{')
            close_obj = candidate.count('}')
            if close_obj < open_obj:
                candidate += '}' * (open_obj - close_obj)
            candidate += ']'
        # Trim trailing junk after the last probable object end
        # Heuristic: keep until last '}' before final ']'
        last_obj_end = candidate.rfind('}')
        if last_obj_end != -1:
            # Ensure candidate ends with ']' only once
            tail = candidate[last_obj_end+1:]
            # Remove extraneous characters between last object and closing bracket
            tail = re.sub(r'[^\]]+', '', tail)
            candidate = candidate[:last_obj_end+1] + tail
        salvaged = candidate.strip()
        return salvaged if salvaged.startswith('[') else None
    return None

def try_json_loads(s):
    """Safely parse JSON, returning None on any error."""
    if not s:
        return None
    s = s.strip()
    # Some providers return code fences or BOM; clean them
    s = s.lstrip('\ufeff').strip()
    if s.startswith("``"):
        s = s.strip('`').strip()
    # Ensure it looks like an array; otherwise, attempt object parse
    try:
        return json.loads(s)
    except Exception:
        return None

def parse_json_array_lenient(s):
    """Parse as many complete JSON objects from an array as possible.

    Handles truncated arrays like: [ {..}, {..}, {..  (missing close)
    Returns a list with recovered objects or None if nothing could be parsed.
    """
    if not s:
        return None
    s = s.strip()
    # Locate array bounds
    start = s.find('[')
    if start == -1:
        return None
    # Prefer up to the last closing bracket if present, else to the end
    end = s.rfind(']')
    inner = s[start+1:end] if end != -1 else s[start+1:]
    dec = json.JSONDecoder()
    pos = 0
    items = []
    length = len(inner)
    while pos < length:
        # Skip whitespace and commas
        while pos < length and inner[pos] in ' \t\r\n,':
            pos += 1
        if pos >= length:
            break
        try:
            obj, nxt = dec.raw_decode(inner, pos)
            items.append(obj)
            pos = nxt
        except Exception:
            # Stop at first incomplete/invalid object
            break
        # Skip trailing spaces/commas before next object
        while pos < length and inner[pos] in ' \t\r\n,':
            pos += 1
    return items if items else None


def assign_options_random(correct, wrongs):
    wrongs = [w for w in wrongs if w and str(w).strip()]
    # Ensure exactly 3 wrongs
    pool = list(map(str, wrongs))
    while len(pool) < 3:
        pool.append("Option")
    pool = pool[:3]
    slots = [None, None, None, None]
    correct_idx = random.randint(0, 3)
    slots[correct_idx] = str(correct)
    wi = 0
    for i in range(4):
        if slots[i] is None:
            slots[i] = pool[wi]
            wi += 1
    letters = ['A', 'B', 'C', 'D']
    return {
        'option_a': slots[0],
        'option_b': slots[1],
        'option_c': slots[2],
        'option_d': slots[3],
        'correct_option': letters[correct_idx]
    }

def _fallback_flashcards(cleaned_text, limit=3):
    """Generate Q/A pairs heuristically and include simple MCQ options.

    Attempts to form definition-style questions by parsing common patterns.
    Always returns MCQ-ready dicts with option_a–d and correct_option set.
    """

    def normalize_subject(subj: str) -> str:
        subj = subj.strip().strip(' .,:;\t\n\r')
        subj = re.sub(r'^(?:In|On|At|During|Within|From)\s+[^,]+,\s*', '', subj, flags=re.I)
        subj = re.sub(r'^(?:an?|the)\s+', '', subj, flags=re.I)
        if len(subj) <= 60:
            subj = subj[0:1].upper() + subj[1:]
        return subj

    def derive_qa(sentence: str):
        s = sentence.strip()
        if len(s) < 10:
            return None
        m = re.match(r'^\s*([^:\-]{2,80})\s*[:\-]\s+(.+)$', s)
        if m:
            subj, rest = m.group(1), m.group(2)
            subj = normalize_subject(subj)
            if subj:
                qverb = 'are' if re.search(r'\b(s|S)\b$|\band\b', subj) or subj.lower().endswith('s') else 'is'
                question = f"What {qverb} {subj}?"
                answer = (f"{subj} {qverb} " + rest).strip()
                return question[:120], answer[:300]

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
            # Synthesize lightweight MCQ options
            correct = re.split(r'[.;\n]', a)[0][:60]
            words = re.findall(r'\b[A-Za-z][A-Za-z\-]{2,}\b', cleaned_text)
            distractor_pool = [w.capitalize() for w in words if w.lower() not in correct.lower()][:6] or [
                "Concept", "Process", "Component", "Protocol", "Dataset", "Method"
            ]
            correct_text = correct or "Correct answer"
            opts = assign_options_random(correct_text, distractor_pool)
            card = {
                "question": q,
                "answer": a,
                **opts,
            }
            cards.append(card)
    # If we could not reach the requested limit, add generic MCQs to fill
    if len(cards) < limit:
        def synthesize_generic(idx: int):
            words = re.findall(r'\b[A-Za-z][A-Za-z\-]{3,}\b', cleaned_text)
            unique = []
            seen = set()
            for w in words:
                lw = w.lower()
                if lw not in seen:
                    seen.add(lw)
                    unique.append(w.capitalize())
                if len(unique) >= 6:
                    break
            pool = unique or ["Concept", "Process", "Component", "Protocol", "Dataset", "Method"]
            correct = (unique[0] if unique else "Key concept") + " from the text"
            # Build three wrongs from pool in a rolling fashion
            wrongs = [pool[(idx + j) % len(pool)] for j in range(3)]
            opts = assign_options_random(correct, wrongs)
            return {
                "question": "Which statement best describes the topic?",
                "answer": "It refers to key ideas in the provided text.",
                **opts,
            }

        needed = limit - len(cards)
        for i in range(needed):
            cards.append(synthesize_generic(i))
    return cards


def generate_flashcards_with_ai(text):
    """Attempt AI generation; fallback to heuristic if unavailable.

    Returns list of dicts: [{question: str, answer: str}, ...]
    """
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return []

    # Prefer env/.env via decouple; fall back to Django settings if provided
    api_key = config('BYTEZ_API_KEY', default=None) or (
        getattr(settings, 'BYTEZ_API_KEY', None) if settings else None
    )
    if not (api_key and Bytez):
        print("AI disabled or missing key/SDK; using fallback (synthetic MCQs).")
        if not api_key:
            print("BYTEZ_API_KEY not found via decouple or settings.")
        if not Bytez:
            print("Bytez SDK not installed. Add 'bytez' to requirements.txt and install.")
        return _fallback_flashcards(cleaned_text)
    else:
        print("AI enabled: BYTEZ_API_KEY detected and Bytez SDK available.")

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
        
        print("=" * 80)
        print("RAW AI RESPONSE:")
        print(output)
        print("=" * 80)
        
        if hasattr(output, 'error') and output.error:
            print("BYTEZ ERROR:", output.error)
            return _fallback_flashcards(cleaned_text)
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
            print("WARNING: No JSON array found; attempting salvage")
            # Salvage attempt already performed inside extract_last_json_array; if still None, fallback
            return _fallback_flashcards(cleaned_text)
        
        print("EXTRACTED JSON STRING:")
        print(json_string)
        print("=" * 80)
        
        flashcards = try_json_loads(json_string)
        if not isinstance(flashcards, list) or not flashcards:
            # Try lenient recovery from truncated arrays
            recovered = parse_json_array_lenient(json_string)
            if recovered:
                print(f"LENIENT PARSE: recovered {len(recovered)} item(s) from truncated JSON array")
                flashcards = recovered
            else:
                print("WARNING: JSON parsing failed or not a list; using fallback")
                return _fallback_flashcards(cleaned_text)
        
        print("PARSED FLASHCARDS:")
        for idx, c in enumerate(flashcards[:10]):
            print(f"Card {idx + 1}:", c)
        print("=" * 80)
        
        def _short_phrase(text: str) -> str:
            t = (text or '').strip()
            if not t:
                return ''
            t = re.split(r'[.;\n]', t)[0]
            t = re.sub(r'\s+', ' ', t).strip()
            return t[:60]

        def _distractors(source: str, avoid: str, k: int = 3):
            words = re.findall(r'\b[A-Za-z][A-Za-z\-]{2,}\b', source)
            uniq = []
            seen = set()
            for w in words:
                lw = w.lower()
                if lw not in seen and lw not in avoid.lower():
                    seen.add(lw)
                    uniq.append(w.capitalize())
                if len(uniq) >= 12:
                    break
            pool = uniq or ["Concept", "Process", "Component", "Protocol", "Dataset", "Method", "Library", "Model"]
            out = []
            for i in range(k):
                out.append(pool[i % len(pool)])
            return out

        valid = []
        for c in flashcards[:10]:
            q = c.get('question') or c.get('Question')
            a = c.get('answer') or c.get('Answer')
            if q and a:
                card_data = {'question': str(q)[:255], 'answer': str(a)[:1000]}
                if c.get('option_a'):
                    card_data['option_a'] = str(c.get('option_a', ''))[:255]
                    card_data['option_b'] = str(c.get('option_b', ''))[:255]
                    card_data['option_c'] = str(c.get('option_c', ''))[:255]
                    card_data['option_d'] = str(c.get('option_d', ''))[:255]
                    card_data['correct_option'] = str(c.get('correct_option', ''))[:1].upper()
                    print(f"MCQ DETECTED: {card_data['question'][:50]}... with options A-D")
                else:
                    # Synthesize MCQ options from Q/A when AI omits them
                    correct = _short_phrase(card_data['answer']) or _short_phrase(card_data['question']) or 'Correct answer'
                    wrongs = _distractors(cleaned_text, correct, 3)
                    opts = assign_options_random(correct, wrongs)
                    card_data.update(opts)
                    print(f"SYNTHETIC MCQ: {card_data['question'][:50]}... (correct={card_data['correct_option']})")
                valid.append(card_data)
        if not valid:
            return _fallback_flashcards(cleaned_text)
        # Ensure we return exactly 3 by topping up with fallback if needed
        if len(valid) < 3:
            needed = 3 - len(valid)
            valid.extend(_fallback_flashcards(cleaned_text, limit=needed))
        return valid
    except Exception as e:
        print("AI generation exception:", e)
        return _fallback_flashcards(cleaned_text)
