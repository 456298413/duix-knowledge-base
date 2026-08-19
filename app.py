from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import io
import edge_tts
import asyncio

app = Flask(__name__)
CORS(app)

KB_PATH = os.path.join(os.path.dirname(__file__), 'knowledge_base', 'knowledge_base.json')
with open(KB_PATH, 'r', encoding='utf-8') as f:
    kb_data = json.load(f)
knowledge_base = kb_data['entries']  # 关键：提取 entries 列表

VOICES = {
    'xiaoxiao': 'zh-CN-XiaoxiaoNeural',
    'yunxi': 'zh-CN-YunxiNeural',
    'yunyang': 'zh-CN-YunyangNeural',
    'xiaoyi': 'zh-CN-XiaoyiNeural'
}

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

@app.route('/api/tts', methods=['GET'])
def tts():
    text = request.args.get('text', '').strip()
    voice = request.args.get('voice', 'xiaoxiao').strip().lower()
    if not text:
        return jsonify({'error': 'text is required'}), 400
    if len(text) > 500:
        text = text[:500]
    voice_id = VOICES.get(voice, VOICES['xiaoxiao'])
    try:
        async def generate():
            communicate = edge_tts.Communicate(text, voice_id)
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk['type'] == 'audio':
                    audio_data.extend(chunk['data'])
            return bytes(audio_data)
        audio_bytes = asyncio.run(generate())
        buf = io.BytesIO(audio_bytes)
        buf.seek(0)
        return send_file(buf, mimetype='audio/mpeg',
                         headers={'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
