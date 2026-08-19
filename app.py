#!/usr/bin/env python3
"""
工会知识库 API 服务
提供问答接口，支持 CORS，可部署到 Render/Railway 等免费云平台
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
CORS(app)  # 允许所有跨域请求

# DUIX 数字人配置（从环境变量读取，本地开发可用默认值）
DUIX_APP_ID = os.environ.get('DUIX_APP_ID', '1539357019641876480')
DUIX_APP_KEY = os.environ.get('DUIX_APP_KEY', '7bf9f999-d214-441d-91dd-3833d0bb24be')

# 加载知识库（兼容两种路径：knowledge_base/ 子目录或根目录）
_base_dir = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(_base_dir, 'knowledge_base', 'knowledge_base.json')
if not os.path.exists(KB_PATH):
    KB_PATH = os.path.join(_base_dir, 'knowledge_base.json')

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

    # 提取中文内容
    chinese_text = re.sub(r'[^\u4e00-\u9fa5]', '', question)
    if not chinese_text:
        return []

    # 提取所有2字词组（滑动窗口）作为核心搜索词
    q_words = set()
    for i in range(len(chinese_text) - 1):
        q_words.add(chinese_text[i:i+2])
    # 提取4字及以上完整短语用于精确匹配加分
    long_phrases = set()
    for length in range(4, min(len(chinese_text) + 1, 7)):
        for i in range(len(chinese_text) - length + 1):
            long_phrases.add(chinese_text[i:i + length])

    scored = []
    for entry in ENTRIES:
        score = 0
        entry_text = entry['title'] + ' ' + entry['content'] + ' ' + ' '.join(entry.get('keywords', []))

        # 1. 2字词命中率
        hit_count = sum(1 for w in q_words if w in entry_text)
        if q_words:
            score += hit_count / len(q_words) * 50

        # 2. 条目关键词与问题的关联度
        kw_list = entry.get('keywords', [])
        kw_score = 0
        for kw in kw_list:
            if len(kw) <= 3:
                if any(kw == w or kw in w for w in q_words):
                    kw_score += 8
            else:
                hit_by_qw = sum(1 for w in q_words if w in kw)
                if hit_by_qw >= 2:
                    kw_score += 8
        score += kw_score

        # 3. 长短语精确匹配加分（4字+）
        for lp in long_phrases:
            if lp in entry_text:
                score += len(lp) * 8
            if lp in entry['title']:
                score += len(lp) * 12

        # 4. 章节名匹配
        chapter = entry.get('chapter', '')
        for w in q_words:
            if w in chapter:
                score += 5

        # 5. 来源文件与问题话题的相关性加分
        source_file = entry.get('source_file', '')
        source_title = entry.get('source_title', '')
        source_combined = source_file + ' ' + source_title
        topic_rules = [
            (['福利', '关爱', '慰问', '入职', '结婚', '生育', '退休', '困难', '帮扶', '生日', '生病', '休假'], '福利梳理', 35),
            (['财务', '经费', '预算', '支出', '收入'], '财务管理', 25),
            (['帮扶', '救助', '三不让'], '三不让', 25),
            (['关爱', '生涯'], '关爱服务', 25),
        ]
        for keywords, file_marker, bonus in topic_rules:
            if any(ww in question for ww in keywords) and file_marker in source_combined:
                score += bonus
                break

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
    """
    问答接口
    POST/GET /api/ask?question=xxx
    返回: {answer, source, source_file, chapter, confidence, related}
    """
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

    try:
        results = search_knowledge_base(question)
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("search_knowledge_base 出错:", error_detail)
        return jsonify({
            'success': False,
            'error': '知识库检索出错: ' + str(e)
        }), 500

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
        'related': results[1:]
    })


@app.route('/api/sign', methods=['GET'])
def get_sign():
    """生成 DUIX H5 SDK 所需的 JWT 签名
    参考官方文档: https://docs.duix.com/documentation/get-token
    """
    try:
        payload = {
            'appId': DUIX_APP_ID,
            'iat': int(time.time()),
            'exp': int(time.time()) + 1800  # 30 分钟过期
        }
        sign = jwt.encode(payload, DUIX_APP_KEY, algorithm='HS256')
        return jsonify({
            'success': True,
            'sign': sign,
            'appId': DUIX_APP_ID,
            'expires_in': 1800
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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
