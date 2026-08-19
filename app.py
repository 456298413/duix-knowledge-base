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

# 垃圾回答黑名单 — 这些内容没有实际信息，不应返回
BLACKLIST_CONTENTS = [
    '本办法由公司工会负责解释',
    '本办法自发布之日起施行',
    '解释权归公司工会',
    '以上标准如有变动',
]

def is_blacklisted(content):
    for bl in BLACKLIST_CONTENTS:
        if bl in content:
            return True
    return False

def search_knowledge(question):
    """返回所有匹配的条目，按相关度排序"""
    question = question.strip()
    if not question:
        return []

    # 提取问题中的2字词组
    q_2grams = set()
    for i in range(len(question) - 1):
        q_2grams.add(question[i:i+2])

    scored = []
    for entry in knowledge_base:
        title = entry.get('title', '').strip()
        content = entry.get('content', '').strip()
        keywords = entry.get('keywords', [])
        source_file = entry.get('source_file', '')

        # 过滤黑名单内容
        if is_blacklisted(content):
            continue

        # 跳过太短的条目（少于30字）
        if len(content) < 30:
            continue

        score = 0
        full_text = title + ' ' + content + ' ' + ' '.join(keywords)

        # 1. 标题关键词完全匹配（最高权重）
        for kw in keywords:
            if len(kw) >= 2 and kw in question:
                score += 30

        # 2. 标题包含问题中的关键词
        if title and title in question:
            score += 40
        elif question in title:
            score += 20

        # 3. 2字词命中率
        e_2grams = set()
        for i in range(len(full_text) - 1):
            e_2grams.add(full_text[i:i+2])
        overlap = len(q_2grams & e_2grams) / max(len(q_2grams | e_2grams), 1)
        score += overlap * 25

        # 4. 内容直接包含完整问题
        if question in content:
            score += 50

        # 5. 来源文件相关性加分
        # "工会福利梳理"文件包含所有福利相关答案
        if '福利梳理' in source_file or '福利手册' in source_file:
            for kw in keywords:
                if len(kw) >= 2 and kw in question:
                    score += 10
        # "三不让"文件
        if '三不让' in source_file:
            if any(w in question for w in ['帮扶', '救助', '三不让', '困难']):
                score += 15
        # "关爱服务"文件
        if '关爱服务' in source_file or '生涯' in source_file:
            if any(w in question for w in ['关爱', '生涯', '入职', '退休', '结婚', '生育']):
                score += 15
        # "财务管理"文件 — 只有财务相关问题才匹配
        if '财务管理' in source_file:
            if any(w in question for w in ['财务', '经费', '预算', '会费']):
                score += 10
            else:
                # 非财务问题，大幅降权
                score -= 30

        if score > 10:
            scored.append((score, entry))

    scored.sort(key=lambda x: -x[0])
    return [entry for _, entry in scored]

@app.route('/api/ask', methods=['GET'])
def ask():
    question = request.args.get('question', '').strip()
    if not question:
        return jsonify({'success': False, 'answer': '请输入您的问题'})

    matches = search_knowledge(question)

    if not matches:
        return jsonify({
            'success': False,
            'answer': '抱歉，我在知识库中未找到与您问题相关的信息。如需进一步帮助，请联系中铁二局工会工作人员。'
        })

    # 合并前3条最佳匹配的完整内容
    parts = []
    sources = set()
    for entry in matches[:3]:
        title = entry.get('title', '')
        content = entry.get('content', '').strip()
        source = entry.get('source_title', '工会知识库')
        sources.add(source)

        if title:
            parts.append(f"【{title}】\n{content}")
        else:
            parts.append(content)

    full_answer = '\n\n'.join(parts)
    source_str = '、'.join(sources)

    return jsonify({
        'success': True,
        'answer': full_answer,
        'source': source_str,
        'match_count': len(matches)
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'knowledge_count': len(knowledge_base)})

@app.route('/api/sources', methods=['GET'])
def sources():
    return jsonify({'sources': list(set(e.get('source_title', '') for e in knowledge_base))})

if __name__ == '__main__':
    app.run(debug=True)
