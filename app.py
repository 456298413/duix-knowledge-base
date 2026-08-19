#!/usr/bin/env python3
"""
工会知识库 API 服务 — 多轮对话版
概览类问题返回选项菜单，用户选择后返回详细内容
"""
import json
import os
import re
from collections import defaultdict
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 加载知识库
_base_dir = os.path.dirname(os.path.abspath(__file__))
KB_PATH = os.path.join(_base_dir, 'knowledge_base', 'knowledge_base.json')
if not os.path.exists(KB_PATH):
    KB_PATH = os.path.join(_base_dir, 'knowledge_base.json')

with open(KB_PATH, 'r', encoding='utf-8') as f:
    KB = json.load(f)

ENTRIES = KB['entries']

BLACKLIST = [
    '本办法由公司工会负责解释', '本办法自发布之日起施行',
    '解释权归公司工会', '以上标准如有变动', '本办法自2025年1月1日起施行',
]

WELFARE_CHAPTERS = {
    '入职入会': '一、入职入会',
    '恋爱交友': '二、恋爱交友',
    '结婚成家': '三、结婚成家',
    '生育哺乳': '四、生育哺乳',
    '子女入学': '五、子女入学',
    '职工生日': '六、职工生日',
    '生病住院': '七、生病住院',
    '困难帮扶': '八、困难帮扶',
    '亲人去世': '九、亲人去世',
    '退休离岗': '十、退休离岗',
    '年节慰问': '十一、年节慰问',
}


def find_entry_by_chapter(chapter_key):
    for entry in ENTRIES:
        if chapter_key in entry.get('title', '') or chapter_key in entry.get('keywords', []):
            return entry
    return None


def score_entry(question, entry):
    score = 0
    chinese_text = re.sub(r'[^\u4e00-\u9fa5]', '', question)
    q_words = set()
    for i in range(len(chinese_text) - 1):
        q_words.add(chinese_text[i:i+2])
    entry_text = entry['title'] + ' ' + entry['content'] + ' ' + ' '.join(entry.get('keywords', []))
    source_combined = entry.get('source_file', '') + ' ' + entry.get('source_title', '')

    if q_words:
        score += sum(1 for w in q_words if w in entry_text) / len(q_words) * 50
    for kw in entry.get('keywords', []):
        if len(kw) <= 3:
            if any(kw == w or kw in w for w in q_words):
                score += 8
        else:
            if sum(1 for w in q_words if w in kw) >= 2:
                score += 8
    for length in range(4, min(len(chinese_text) + 1, 7)):
        for i in range(len(chinese_text) - length + 1):
            lp = chinese_text[i:i + length]
            if lp in entry_text:
                score += len(lp) * 8
    topic_map = [
        (['福利', '关爱', '慰问', '入职', '结婚', '生育', '退休', '困难', '生日', '生病', '年节', '休假'], '福利梳理', 35),
        (['财务', '经费', '预算', '支出', '收入'], '财务管理办法', 30),
        (['三不让', '救助', '帮困', '大病', '助医', '助学'], '三不让', 30),
        (['关爱', '生涯'], '关爱服务', 25),
    ]
    for keywords, marker, bonus in topic_map:
        if any(ww in question for ww in keywords) and marker in source_combined:
            score += bonus
            break
    for w in q_words:
        if w in entry['title']:
            score += 10
    return score


def is_overview_question(question):
    patterns = ['有哪些', '包含什么', '包括哪些', '一共', '多少项', '列表',
                '全部内容', '全部福利', '所有福利', '汇总', '概览',
                '有什么福利', '介绍一下福利', '福利情况']
    return any(p in question for p in patterns)


def build_menu_response(question):
    if any(w in question for w in ['福利', '关爱']):
        menu_text = "工会为职工提供以下方面的关爱服务，请问您想了解哪一项？\n\n"
        menu_items = []
        for key, title in WELFARE_CHAPTERS.items():
            entry = find_entry_by_chapter(key)
            if entry:
                menu_text += f"  {title}\n"
                menu_items.append({'label': title, 'key': key})
        menu_text += "\n请直接回复序号或名称，安安为您详细介绍~"
        return {
            'type': 'menu', 'answer': menu_text,
            'menu_items': menu_items,
            'source': '西安公司工会职业生涯全过程福利手册',
        }
    elif any(w in question for w in ['三不让', '帮扶', '救助']):
        menu_text = "「三不让」帮扶救助涵盖以下方面，请问您想了解哪一项？\n\n"
        menu_text += "  1. 困难补助\n  2. 帮困助学\n  3. 医疗救助\n\n"
        menu_text += "请直接回复序号或名称~"
        return {
            'type': 'menu', 'answer': menu_text,
            'menu_items': [
                {'label': '困难补助', 'key': '困难补助'},
                {'label': '帮困助学', 'key': '帮困助学'},
                {'label': '医疗救助', 'key': '医疗救助'},
            ],
            'source': '三不让帮扶救助实施办法',
        }
    elif any(w in question for w in ['财务', '经费']):
        menu_text = "工会财务管理涵盖以下方面，请问您想了解哪一项？\n\n"
        menu_text += "  1. 预算管理\n  2. 经费收入管理\n  3. 经费支出管理\n  4. 资产与负债管理\n\n"
        menu_text += "请直接回复序号或名称~"
        return {
            'type': 'menu', 'answer': menu_text,
            'menu_items': [
                {'label': '预算管理', 'key': '预算'},
                {'label': '经费收入管理', 'key': '经费收入'},
                {'label': '经费支出管理', 'key': '经费支出'},
                {'label': '资产与负债管理', 'key': '资产'},
            ],
            'source': '工会财务管理办法',
        }
    else:
        menu_text = "知识库涵盖以下内容，请问您想了解哪方面？\n\n"
        menu_text += "  1. 工会福利与关爱服务\n  2. 三不让帮扶救助\n  3. 工会财务管理\n\n"
        menu_text += "请直接回复序号或名称~"
        return {
            'type': 'menu', 'answer': menu_text,
            'menu_items': [
                {'label': '工会福利与关爱服务', 'key': '福利'},
                {'label': '三不让帮扶救助', 'key': '三不让'},
                {'label': '工会财务管理', 'key': '财务'},
            ],
            'source': '知识库',
        }


def build_detail_answer(question):
    scored = []
    for entry in ENTRIES:
        s = score_entry(question, entry)
        if s > 5:
            scored.append((s, entry))
    scored.sort(key=lambda x: -x[0])
    top = [(s, e) for s, e in scored if not any(b in e.get('content', '') for b in BLACKLIST)]
    if not top:
        return None
    parts = []
    for score, entry in top[:5]:
        title = entry.get('title', '').strip()
        content = entry.get('content', '').strip()
        source = entry.get('source_title', '')
        parts.append(f"【{title}】\n{content}\n（来源：{source}）")
    return {
        'type': 'detail', 'answer': '\n\n'.join(parts)[:3000],
        'source': top[0][1].get('source_title', ''),
    }


@app.route('/api/ask', methods=['POST', 'GET'])
def ask():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
    else:
        question = request.args.get('question', '').strip()

    if not question:
        return jsonify({'success': False, 'answer': '请输入您的问题'}), 400

    try:
        if is_overview_question(question):
            menu = build_menu_response(question)
            return jsonify({
                'success': True, 'type': 'menu',
                'answer': menu['answer'],
                'menu_items': menu['menu_items'],
                'source': menu['source'],
            })

        result = build_detail_answer(question)
        if result:
            return jsonify({
                'success': True, 'type': 'detail',
                'answer': result['answer'],
                'source': result['source'],
            })

        return jsonify({
            'success': True, 'type': 'detail',
            'answer': '未在知识库中找到相关信息。您可以试试：\n• 工会有哪些福利？\n• 三不让是什么？\n• 结婚有什么慰问？\n• 工会经费怎么管理？',
            'source': '',
        })
    except Exception as e:
        import traceback
        print("ERROR:", traceback.format_exc())
        return jsonify({'success': False, 'answer': '查询出错：' + str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'total_entries': KB['total_entries']})


@app.route('/api/sources', methods=['GET'])
def sources():
    return jsonify({'success': True, 'sources': KB['source_files'], 'total_entries': KB['total_entries']})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"知识库条目: {KB['total_entries']} 条")
    app.run(host='0.0.0.0', port=port, debug=False)
