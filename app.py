#!/usr/bin/env python3
"""
工会知识库 API 服务
提供问答接口，支持 CORS，可部署到 Render/Railway 等免费云平台
"""
import json
import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允许所有跨域请求

# 加载知识库
KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'knowledge_base.json')

with open(KB_PATH, 'r', encoding='utf-8') as f:
    KB = json.load(f)

ENTRIES = KB['entries']


def search_knowledge_base(question: str, top_k: int = 3) -> list:
    """
    基于关键词匹配的知识检索
    返回最匹配的 top_k 条结果
    """
    question = question.strip()
    if not question:
        return []

    # 提取问题中的关键词（2-6字中文词组）
    q_words = set(re.findall(r'[\u4e00-\u9fa5]{2,6}', question))

    scored = []
    for entry in ENTRIES:
        score = 0
        entry_text = entry['title'] + ' ' + entry['content'] + ' ' + ' '.join(entry.get('keywords', []))

        # 1. 问题关键词在条目中的命中率
        hit_count = sum(1 for w in q_words if w in entry_text)
        if q_words:
            score += hit_count / len(q_words) * 40

        # 2. 条目关键词在问题中的命中率
        kw_list = entry.get('keywords', [])
        kw_hit = sum(1 for kw in kw_list if kw in question)
        score += kw_hit * 5

        # 3. 标题匹配加分
        if any(w in entry['title'] for w in q_words):
            score += 15

        # 4. 精确匹配章节名加分
        chapter = entry.get('chapter', '')
        if any(w in chapter for w in q_words):
            score += 10

        # 5. 内容精确包含问题中的长词组加分
        long_words = [w for w in q_words if len(w) >= 4]
        for lw in long_words:
            if lw in entry_text:
                score += 3

        if score > 0:
            scored.append((score, entry))

    # 按分数降序排列
    scored.sort(key=lambda x: -x[0])

    results = []
    for score, entry in scored[:top_k]:
        # 计算置信度（基于分数归一化）
        max_possible = 40 + len(entry.get('keywords', [])) * 5 + 15 + 10 + 3 * 5
        confidence = min(score / max(max_possible, 1) * 100, 100)
        confidence = round(confidence, 1)

        results.append({
            'answer': entry['content'][:2000],  # 限制返回长度
            'source': entry['source_title'],
            'source_file': entry['source_file'],
            'chapter': entry['chapter'],
            'confidence': confidence
        })

    return results


@app.route('/api/ask', methods=['POST', 'GET'])
def ask():
    """
    问答接口
    POST/GET /api/ask?question=xxx
    返回: {answer, source, source_file, chapter, confidence, related}
    """
    # 支持 GET 和 POST
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
    else:
        question = request.args.get('question', '').strip()

    if not question:
        return jsonify({
            'success': False,
            'error': '请提供问题参数 question'
        }), 400

    results = search_knowledge_base(question)

    if not results:
        return jsonify({
            'success': True,
            'answer': '未在知识库中找到与您问题相关的信息。知识库仅包含工会福利、关爱服务、帮扶救助、财务管理相关文件内容。',
            'source': '',
            'source_file': '',
            'chapter': '',
            'confidence': 0,
            'related': []
        })

    best = results[0]

    return jsonify({
        'success': True,
        'answer': best['answer'],
        'source': best['source'],
        'source_file': best['source_file'],
        'chapter': best['chapter'],
        'confidence': best['confidence'],
        'related': results[1:]  # 相关条目
    })


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'total_entries': KB['total_entries'],
        'version': KB['version'],
        'description': KB['description']
    })


@app.route('/api/sources', methods=['GET'])
def sources():
    """查看知识库来源文件"""
    return jsonify({
        'success': True,
        'sources': KB['source_files'],
        'total_entries': KB['total_entries']
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"工会知识库 API 启动中...")
    print(f"知识库条目: {KB['total_entries']} 条")
    print(f"监听端口: {port}")
    print(f"API 地址: http://localhost:{port}/api/ask?question=测试问题")
    app.run(host='0.0.0.0', port=port, debug=False)
