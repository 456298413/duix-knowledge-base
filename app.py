from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

_base_dir = os.path.dirname(os.path.abspath(__file__))
for kb_path in [
    os.path.join(_base_dir, 'knowledge_base.json'),
    os.path.join(_base_dir, 'knowledge_base', 'knowledge_base.json'),
]:
    if os.path.exists(kb_path):
        KB_PATH = kb_path
        break
else:
    KB_PATH = os.path.join(_base_dir, 'knowledge_base.json')

with open(KB_PATH, 'r', encoding='utf-8') as f:
    kb_data = json.load(f)
knowledge_base = kb_data['entries']

def fuzzy_match(question, entry):
    q = question.lower()
    keywords = entry.get('keywords', [])
    title = entry.get('title', '').lower()
    if title in q or q in title:
        return True
    for kw in keywords:
        if kw.lower() in q:
            return True
    q_words = set(q)
    t_words = set(title)
    if len(q_words & t_words) / max(len(q_words | t_words), 1) > 0.5:
        return True
    return False

def search_knowledge(question):
    results = []
    for entry in knowledge_base:
        if fuzzy_match(question, entry):
            results.append(entry)
    results.sort(key=lambda x: len(x.get('keywords', [])), reverse=True)
    return results[0] if results else None

@app.route('/api/ask', methods=['GET'])
def ask():
    question = request.args.get('question', '').strip()
    if not question:
        return jsonify({'success': False, 'answer': '请输入您的问题'})
    result = search_knowledge(question)
    if result:
        return jsonify({
            'success': True,
            'answer': result['content'],
            'source': result.get('source', '工会知识库'),
            'title': result.get('title', '')
        })
    else:
        return jsonify({
            'success': False,
            'answer': '抱歉，我在知识库中未找到与您问题相关的信息。如需进一步帮助，请联系中铁二局工会工作人员。'
        })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'knowledge_count': len(knowledge_base)})

@app.route('/api/sources', methods=['GET'])
def sources():
    return jsonify({'sources': list(set(e.get('source', '') for e in knowledge_base))})

if __name__ == '__main__':
    app.run(debug=True)
