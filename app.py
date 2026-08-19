#!/usr/bin/env python3
"""
工会知识库 API 服务
"""
import json
import os
import re
import time
import jwt
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DUIX_APP_ID = os.environ.get('DUIX_APP_ID', '1539357019641876480')
DUIX_APP_KEY = os.environ.get('DUIX_APP_KEY', '7bf9f999-d214-441d-91dd-3833d0bb24be')

_base_dir = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(_base_dir, 'knowledge_base', 'knowledge_base.json')
if not os.path.exists(KB_PATH):
    KB_PATH = os.path.join(_base_dir, 'knowledge_base.json')

with open(KB_PATH, 'r', encoding='utf-8') as f:
    KB = json.load(f)

ENTRIES = KB['entries']


def search_knowledge_base(question, top_k=3):
    question = question.strip()
    if not question:
        return []
    q_words = set(re.findall(r'[\u4e00-\u9fa5]{2,6}', question))
    scored = []
    for entry in ENTIES:
        score = 0
        entry_text = entry['title'] + ' ' + entry['content'] + ' ' + ' '.join(entry.get('keywords', []))
        hit_count = sum(1 for w in q_words if w in entry_text)
        if q_words:
            score += hit_count / len(q_words) * 40
        kw_list = entry.get('keywords', [])
        kw_hit = sum(1 for kw in kw_list if kw in question)
        score += kw_hit * 5
        if any(w in entry['title'] for w in q_words):
            score += 15
        chapter = entry.get('chapter', '')
        if any(w in chapter for w in q_words):
            score += 10
        long_words = [w for w in q_words if len(w) >= 4]
        for lw in long_words:
            if lw in entry_text:
                score += 3
        if score > 0:
            scored.append((score, entry))
    scored.sort(key=lambda x: -x[0])
    results = []
    for score, entry in scored[:top_k]:
        max_possible = 40 + len(entry.get('keywords', [])) * 5 + 15 + 10 + 3 * 5
        confidence = min(score / max(max_possible, 1) * 100, 100)
        confidence = round(confidence, 1)
        results.append({
            'answer': entry['content'][:2000],
            'source': entry['source_title'],
            'source_file': entry['source_file'],
            'chapter': entry['chapter'],
            'confidence': confidence
        })
    return results


@app.route('/api/ask', methods=['POST', 'GET'])
def ask():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
    else:
        question = request.args.get('question', '').strip()
    if not question:
        return jsonify({'success': False, 'error': '请提供问题参数 question'}), 400
    results = search_knowledge_base(question)
    if not results:
        return jsonify({
            'success': True,
            'answer': '未在知识库中找到与您问题相关的信息。',
            'source': '', 'source_file': '', 'chapter': '', 'confidence': 0, 'related': []
        })
    best = results[0]
    return jsonify({
        'success': True,
        'answer': best['answer'],
        'source': best['source'],
        'source_file': best['source_file'],
        'chapter': best['chapter'],
        'confidence': best['confidence'],
        'related': results[1:]
    })


@app.route('/api/sign', methods=['GET'])
def get_sign():
    try:
        payload = {
            'appId': DUIX_APP_ID,
            'iat': int(time.time()),
            'exp': int(time.time()) + 1800
        }
        sign = jwt.encode(payload, DUIX_APP_KEY, algorithm='HS256')
        return jsonify({'success': True, 'sign': sign, 'appId': DUIX_APP_ID, 'expires_in': 1800})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'total_entries': KB['total_entries'],
        'version': KB['version'],
        'description': KB['description']
    })


@app.route('/api/sources', methods=['GET'])
def sources():
    return jsonify({
        'success': True,
        'sources': KB['source_files'],
        'total_entries': KB['total_entries']
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
