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

def search_knowledge(question):
    question = question.strip()
    if not question:
        return None
    scored = []
    for entry in knowledge_base:
        score = 0
        text = entry.get('title', '') + ' ' + entry.get('content', '') + ' ' + ' '.join(entry.get('keywords', []))
        # 标题精确匹配
        if entry.get('title', '') in question or question in entry.get('title', ''):
            score += 50
        # 关键词匹配
        for kw in entry.get('keywords', []):
            if kw in question:
                score += 20
        # 内容包含
        if question in entry.get('content', ''):
            score += 30
        # 2字词命中率
        q_chars = set()
        for i in range(len(question) - 1):
            q_chars.add(question[i:i+2])
        entry_chars = set()
        for i in range(len(text) - 1):
            entry_chars.add(text[i:i+2])
        overlap = len(q_chars & entry_chars) / max(len(q_chars | entry_chars), 1)
        score += overlap * 20
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1] if scored else None

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
            'source': result.get('source_title', '工会知识库'),
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
    return jsonify({'sources': list(set(e.get('source_title', '') for e in knowledge_base))})

if __name__ == '__main__':
    app.run(debug=True)
