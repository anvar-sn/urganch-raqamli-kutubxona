import csv
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile


QUIZ_TEMPLATE_TEXT = """1. Alisher Navoiy qaysi asarda «Tilga ixtiyorsiz — elga e’tiborsiz» hikmatini keltirgan?
*A) Mahbub ul-qulub
B) Hayrat ul-abror
C) Farhod va Shirin
D) Lison ut-tayr

2. Python dasturlash tilida ro‘yxat (list) uzunligini qaysi funksiya aniqlaydi?
A) count()
*B) len()
C) size()
D) length()

Nyutonning ikkinchi qonuni formulasini belgilang.
====
F = m / a
====
#F = m * a
====
F = m + a
====
F = a / m
++++
"""


_Q_PREFIX_RE = re.compile(
    r'^\s*(?:(?:savol|question|№|#)\s*)?\d{1,4}\s*(?:[-–—.]\s*savol\b|[.)\]\-:])\s*',
    re.IGNORECASE,
)
_OPT_PREFIX_RE = re.compile(
    r'^\s*(?:[A-Fa-fА-Еа-е]\s*[.)\]]|\d{1,2}\s*[.)\]]|[-–•])\s*'
)
_ANSWER_LINE_RE = re.compile(
    r'^\s*(?:answer|javob|to[\'‘’`]?g[\'‘’`]?ri\s*(?:javob)?|kalit)\s*[:=\-]\s*(.+?)\s*$',
    re.IGNORECASE,
)
_CORRECT_TRAILING_RE = re.compile(
    r'(?:\s*(?:\*|✓|✔|\[\+\]|\(\s*to[\'‘’`]?g[\'‘’`]?ri\s*\)|\(\s*\+\s*\)))\s*$',
    re.IGNORECASE,
)
_CORRECT_LEADING_RE = re.compile(
    r'^\s*(?:(\*|\+|#|✓|✔|\[\+\])\s*)'
)


def extract_text_from_uploaded_file(uploaded_file):
    """Extract UTF-8 plain text from .txt, .md, .docx, .csv, or .json quiz files."""
    name = (getattr(uploaded_file, 'name', '') or '').lower()
    raw = uploaded_file.read()
    if not raw:
        return ''

    if name.endswith('.docx'):
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            xml_bytes = zf.read('word/document.xml')
        root = ET.fromstring(xml_bytes)
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        lines = []
        for para in root.findall('.//w:p', ns):
            texts = [t.text for t in para.findall('.//w:t', ns) if t.text]
            lines.append(''.join(texts).strip())
        return '\n'.join(lines)

    for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'latin-1'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text = ''
    if not text:
        return ''

    if name.endswith('.csv'):
        reader = csv.reader(io.StringIO(text))
        blocks = []
        for idx, row in enumerate(reader):
            cells = [c.strip() for c in row]
            if not any(cells):
                continue
            if idx == 0 and any(k in cells[0].lower() for k in ('savol', 'question')):
                continue
            q_text = cells[0]
            opts = [c for c in cells[1:5] if c]
            ans = cells[5] if len(cells) > 5 else ''
            if q_text and len(opts) >= 2:
                block_lines = [q_text]
                for opt_idx, opt in enumerate(opts, start=1):
                    letter = chr(64 + opt_idx)
                    block_lines.append(f'{letter}) {opt}')
                if ans:
                    block_lines.append(f'ANSWER: {ans}')
                blocks.append('\n'.join(block_lines))
        return '\n\n'.join(blocks)

    if name.endswith('.json'):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                data = data.get('questions', [])
            if isinstance(data, list):
                blocks = []
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    q_text = str(item.get('text') or item.get('question') or '').strip()
                    opts = [str(o).strip() for o in (item.get('options') or []) if str(o).strip()]
                    corr = item.get('correct') or item.get('answer') or 0
                    if q_text and len(opts) >= 2:
                        lines = [q_text]
                        for opt_idx, opt in enumerate(opts[:6], start=1):
                            prefix = '*' if str(corr) == str(opt_idx) else ''
                            lines.append(f'{prefix}{chr(64 + opt_idx)}) {opt}')
                        blocks.append('\n'.join(lines))
                return '\n\n'.join(blocks)
        except Exception:
            pass

    return text


def _strip_correct_markers(text):
    """Detect and remove leading/trailing correct-answer markers from an option line."""
    s = text.strip()
    is_correct = False
    m_lead = _CORRECT_LEADING_RE.match(s)
    if m_lead:
        is_correct = True
        s = s[m_lead.end():].strip()
    m_pref = _OPT_PREFIX_RE.match(s)
    if m_pref:
        s = s[m_pref.end():].strip()
        m_lead_after = _CORRECT_LEADING_RE.match(s)
        if m_lead_after:
            is_correct = True
            s = s[m_lead_after.end():].strip()
    if _CORRECT_TRAILING_RE.search(s):
        is_correct = True
        s = _CORRECT_TRAILING_RE.sub('', s).strip()
    return s, is_correct


def _resolve_answer_token(token, option_count):
    tok = (token or '').strip().upper().rstrip('.)]')
    cyr_map = {'А': 'A', 'Б': 'B', 'В': 'C', 'Г': 'D', 'Д': 'E', 'Е': 'F'}
    if tok in cyr_map:
        tok = cyr_map[tok]
    if len(tok) == 1 and 'A' <= tok <= 'F':
        idx = ord(tok) - 64
        return idx if 1 <= idx <= option_count else 0
    if tok.isdigit():
        idx = int(tok)
        return idx if 1 <= idx <= option_count else 0
    return 0


def _split_plain_chunk(text):
    """Split a non-==== chunk into blocks by blank lines or numbered question prefixes."""
    blocks = []
    current = []
    letter_opt_re = re.compile(r'^\s*(?:[*+#✓✔]|\[\+\])?\s*[A-Fa-fА-Еа-е]\s*[.)\]]')
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        has_letter_opts = current and any(letter_opt_re.match(x) for x in current[1:])
        is_new_q = bool(_Q_PREFIX_RE.match(stripped)) and (
            has_letter_opts or bool(re.search(r'(?:savol|question)\s*\d+', stripped, re.I))
        )
        if is_new_q:
            blocks.append(current)
            current = [stripped]
        else:
            current.append(stripped)
    if current:
        blocks.append(current)
    return blocks


def _split_question_blocks(raw_text):
    text = (raw_text or '').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        return []

    major_chunks = re.split(r'\n?\s*(?:\+{4,}|---+)\s*\n?', text)
    blocks = []
    for chunk in major_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        for sub in re.split(r'\n\s*\n+', chunk):
            sub = sub.strip()
            if not sub:
                continue
            if '====' in sub:
                blocks.append(re.split(r'\n\s*={3,}\s*\n|\n', sub))
            else:
                blocks.extend(_split_plain_chunk(sub))
    return blocks


def parse_quiz_text(raw_text):
    """Parse pasted Google Docs, Word, Aiken, or HEMIS quiz blocks into structured dicts."""
    questions = []
    for raw_lines in _split_question_blocks(raw_text):
        lines = [ln.strip() for ln in raw_lines if ln and ln.strip() and not re.match(r'^={3,}$', ln.strip())]
        if len(lines) < 2:
            continue

        # First line of every block is always part of the question prompt
        q_parts = [_Q_PREFIX_RE.sub('', lines[0]).strip()]
        opt_lines = []
        explicit_answer = ''

        has_prefixed_opts = any(
            _OPT_PREFIX_RE.match(ln) for ln in lines[1:]
        )

        for ln in lines[1:]:
            m_ans = _ANSWER_LINE_RE.match(ln)
            if m_ans and opt_lines:
                explicit_answer = m_ans.group(1).strip()
                continue
            is_opt = bool(_OPT_PREFIX_RE.match(ln) or _CORRECT_LEADING_RE.match(ln))
            if not opt_lines and has_prefixed_opts and not is_opt:
                q_parts.append(ln)
            else:
                opt_lines.append(ln)

        q_text = ' '.join(p for p in q_parts if p).strip()[:1000]
        if not q_text or len(opt_lines) < 2:
            continue

        options = []
        correct_idx = 0
        for idx, opt_raw in enumerate(opt_lines[:6], start=1):
            clean_opt, marked = _strip_correct_markers(opt_raw)
            clean_opt = clean_opt[:500]
            if not clean_opt:
                continue
            options.append(clean_opt)
            if marked and correct_idx == 0:
                correct_idx = len(options)

        if explicit_answer and options:
            resolved = _resolve_answer_token(explicit_answer, len(options))
            if resolved:
                correct_idx = resolved

        if len(options) >= 2:
            questions.append(
                {
                    'text': q_text,
                    'options': options,
                    'correct': correct_idx,
                }
            )
    return questions
