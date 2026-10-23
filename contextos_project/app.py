from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from pathlib import Path
from werkzeug.utils import secure_filename
import json, zipfile, io, re, os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-local-dev-key')
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
UPLOAD_DIR = BASE_DIR / 'uploads'
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
MEMORY_FILE = DATA_DIR / 'memories.json'
ALLOWED_EXTENSIONS = {'.zip', '.json'}


def load_memories():
    if not MEMORY_FILE.exists():
        return []
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_memories(memories):
    MEMORY_FILE.write_text(json.dumps(memories, ensure_ascii=False, indent=2), encoding='utf-8')


def text_from_content(content):
    """Extract readable text from common ChatGPT export message content shapes."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if isinstance(item.get('text'), str):
                    parts.append(item['text'])
                elif isinstance(item.get('content'), str):
                    parts.append(item['content'])
        return '\n'.join(parts)
    if isinstance(content, dict):
        if isinstance(content.get('text'), str):
            return content['text']
        return ''
    return ''


def extract_user_messages(obj):
    """Read conversations.json format and return user-authored message text."""
    messages = []
    conversations = obj if isinstance(obj, list) else obj.get('conversations', []) if isinstance(obj, dict) else []
    if not isinstance(conversations, list):
        return messages
    for conv in conversations:
        if not isinstance(conv, dict):
            continue
        mapping = conv.get('mapping')
        if isinstance(mapping, dict):
            for node in mapping.values():
                if not isinstance(node, dict):
                    continue
                msg = node.get('message')
                if not isinstance(msg, dict):
                    continue
                author = msg.get('author', {})
                if isinstance(author, dict) and author.get('role') == 'user':
                    text = text_from_content(msg.get('content', {})).strip()
                    if text:
                        messages.append(text)
        # Also support simpler exported structures
        for msg in conv.get('messages', []) if isinstance(conv.get('messages'), list) else []:
            if isinstance(msg, dict) and (msg.get('role') == 'user' or msg.get('author') == 'user'):
                text = text_from_content(msg.get('content', msg.get('text', ''))).strip()
                if text:
                    messages.append(text)
    return messages


def make_suggestions(messages):
    """Conservative, reviewable suggestions; no AI API is called."""
    joined = '\n'.join(messages[-500:])
    patterns = [
        ('Education', r'(?i)\b(BTech|B\.Tech|college|university|student|semester|AKTU|Data Science)\b'),
        ('Learning preference', r'(?i)\b(basic se|zero level|easy words|simple English|step by step|line by line)\b'),
        ('Programming', r'(?i)\b(Python|pandas|Flask|C programming|linked list|SQL)\b'),
        ('Project', r'(?i)\b(ContextOS|VARUNA|traffic signal|mini-project|hackathon)\b'),
    ]
    suggestions = []
    for label, pattern in patterns:
        matches = []
        for message in messages:
            if re.search(pattern, message):
                clean = re.sub(r'\s+', ' ', message).strip()
                if len(clean) > 240:
                    clean = clean[:237] + '...'
                if clean and clean not in matches:
                    matches.append(clean)
        if matches:
            suggestions.append({'category': label, 'fact': matches[-1]})
    return suggestions[:20]


@app.route('/', methods=['GET'])
def index():
    memories = load_memories()
    return render_template('index.html', memories=memories, total=len(memories))


@app.route('/memory/add', methods=['POST'])
def add_memory():
    fact = request.form.get('fact', '').strip()
    category = request.form.get('category', 'General').strip() or 'General'
    if not fact:
        flash('Pehle memory text likho.', 'error')
        return redirect(url_for('index'))
    memories = load_memories()
    memories.append({'id': max([m.get('id', 0) for m in memories if isinstance(m, dict)] + [0]) + 1,
                     'category': category[:60], 'fact': fact[:2000]})
    save_memories(memories)
    flash('Memory save ho gayi.', 'success')
    return redirect(url_for('index'))


@app.route('/memory/delete/<int:memory_id>', methods=['POST'])
def delete_memory(memory_id):
    memories = [m for m in load_memories() if m.get('id') != memory_id]
    save_memories(memories)
    flash('Memory delete kar di gayi.', 'success')
    return redirect(url_for('index'))


@app.route('/import', methods=['POST'])
def import_chatgpt():
    uploaded = request.files.get('chat_file')
    if not uploaded or not uploaded.filename:
        flash('Pehle ChatGPT export ki ZIP ya conversations.json file choose karo.', 'error')
        return redirect(url_for('index'))
    suffix = Path(secure_filename(uploaded.filename)).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        flash('Sirf .zip ya .json file allowed hai.', 'error')
        return redirect(url_for('index'))
    try:
        raw = uploaded.read()
        json_objects = []
        if suffix == '.zip':
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                candidates = [n for n in archive.namelist() if Path(n).name.lower() == 'conversations.json']
                if not candidates:
                    flash('ZIP mein conversations.json nahi mili. ChatGPT ka original data export ZIP upload karo.', 'error')
                    return redirect(url_for('index'))
                with archive.open(candidates[0]) as f:
                    json_objects.append(json.load(f))
        else:
            json_objects.append(json.loads(raw.decode('utf-8-sig')))
        messages = []
        for obj in json_objects:
            messages.extend(extract_user_messages(obj))
        if not messages:
            flash('File khul gayi, lekin pehchaanne layak user messages nahi mile. Original ChatGPT export use karo.', 'error')
            return redirect(url_for('index'))
        suggestions = make_suggestions(messages)
        # Save import suggestions separately so the user can review before adding them.
        (DATA_DIR / 'suggestions.json').write_text(json.dumps(suggestions, ensure_ascii=False, indent=2), encoding='utf-8')
        flash(f'{len(messages)} user messages read hue. {len(suggestions)} reviewable suggestions banaye gaye; ye abhi memory mein save nahi hue.', 'success')
        return redirect(url_for('suggestions'))
    except (zipfile.BadZipFile, json.JSONDecodeError, UnicodeDecodeError, OSError, KeyError) as exc:
        flash(f'File read nahi ho paayi: {exc}', 'error')
        return redirect(url_for('index'))


@app.route('/suggestions', methods=['GET', 'POST'])
def suggestions():
    path = DATA_DIR / 'suggestions.json'
    try:
        items = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    except (json.JSONDecodeError, OSError):
        items = []
    if request.method == 'POST':
        selected = request.form.getlist('selected')
        memories = load_memories()
        next_id = max([m.get('id', 0) for m in memories if isinstance(m, dict)] + [0]) + 1
        count = 0
        for index, item in enumerate(items):
            if str(index) in selected:
                memories.append({'id': next_id, 'category': item['category'], 'fact': item['fact']})
                next_id += 1
                count += 1
        save_memories(memories)
        flash(f'{count} selected memories save ho gayi.', 'success')
        return redirect(url_for('index'))
    return render_template('suggestions.html', items=items)


@app.route('/export')
def export_pack():
    memories = load_memories()
    if not memories:
        flash('Pehle kam se kam ek memory save ya import karo.', 'error')
        return redirect(url_for('index'))
    lines = [
        'USER CONTEXT PACK',
        'Use this information as helpful context, not as guaranteed truth. Ask if something is outdated or unclear.',
        'The user chose to share the following facts:', ''
    ]
    for item in memories:
        lines.append(f"- [{item.get('category', 'General')}] {item.get('fact', '')}")
    lines += ['', 'CURRENT TASK: [Type your question here]',
              '', 'Privacy note: Review this text before sharing it with another AI. Remove anything private or sensitive.']
    content = '\n'.join(lines)
    return send_file(io.BytesIO(content.encode('utf-8')), mimetype='text/plain; charset=utf-8',
                     as_attachment=True, download_name='contextos_context_pack.txt')


@app.route('/health')
def health():
    return {'status': 'ok', 'memories': len(load_memories())}


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
