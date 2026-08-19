#!/usr/bin/env python3
"""
工会知识库 API 服务 v4 — 主题分类 + 精准匹配 + 主动澄清 + 指定文件搜索
"""
import json
import os
import re
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

# ============================================================
# 黑名单：过滤无意义的条目
# ============================================================
BLACKLIST = [
    '本办法由公司工会负责解释', '本办法自发布之日起施行',
    '解释权归公司工会', '以上标准如有变动', '本办法自2025年1月1日起施行',
]

# ============================================================
# 来源文件识别
# ============================================================
SOURCE_FILE_MAP = {
    '福利梳理': {
        'keywords': ['福利梳理', '福利手册', '福利文件', '福利办法'],
        'marker': '福利梳理',
        'full_name': '西安公司工会职业生涯全过程福利手册',
    },
    '关爱服务': {
        'keywords': ['关爱服务', '关爱意见', '关爱实施', '职业生涯关爱', '全过程关爱', '关爱文件'],
        'marker': '关爱服务实施意见',
        'full_name': '中铁二局职工职业生涯全过程关爱服务实施意见',
    },
    '三不让': {
        'keywords': ['三不让', '帮扶救助办法', '三不让办法', '三不让文件', '三不让实施'],
        'marker': '三不让',
        'full_name': '三不让帮扶救助实施办法',
    },
    '财务管理': {
        'keywords': ['财务管理', '财务管理办法', '财务文件', '经费管理'],
        'marker': '财务管理办法',
        'full_name': '工会财务管理办法',
    },
}


def detect_source(question):
    """检测问题是否指定了某个来源文件"""
    for source_name, config in SOURCE_FILE_MAP.items():
        for kw in config['keywords']:
            if kw in question:
                return source_name
    return None


# ============================================================
# 主题分类配置
# ============================================================
TOPIC_CATEGORIES = {
    'welfare': {
        'name': '工会福利',
        'keywords': [
            ('福利', 15), ('慰问', 12), ('入职', 10), ('入会', 10),
            ('恋爱', 10), ('交友', 10), ('结婚', 12), ('新婚', 12),
            ('生育', 10), ('哺乳', 10), ('二孩', 10), ('三孩', 10),
            ('子女入学', 12), ('助学', 10), ('生日', 10),
            ('生病', 10), ('住院', 10), ('医疗', 10),
            ('困难', 10), ('帮扶', 10), ('受灾', 10),
            ('亲人去世', 12), ('去世', 8),
            ('退休', 10), ('离岗', 10),
            ('年节', 10), ('节日', 10), ('春节', 8),
            ('元旦', 8), ('慰问品', 10), ('慰问金', 10),
        ],
        'threshold': 10,
        'sub_topics': {
            '入职入会': {'keys': ['入职', '入会', '迎新']},
            '恋爱交友': {'keys': ['恋爱', '交友', '联谊', '婚恋']},
            '结婚成家': {'keys': ['结婚', '新婚', '婚礼']},
            '生育哺乳': {'keys': ['生育', '哺乳', '二孩', '三孩', '妈咪']},
            '子女入学': {'keys': ['子女入学', '助学', '入学', '奖学金']},
            '职工生日': {'keys': ['生日', '蛋糕']},
            '生病住院': {'keys': ['生病', '住院', '医疗', '报销', '大病']},
            '困难帮扶': {'keys': ['困难', '帮扶', '受灾', '灾难']},
            '亲人去世': {'keys': ['去世', '吊唁', '后事']},
            '退休离岗': {'keys': ['退休', '离岗']},
            '年节慰问': {'keys': ['年节', '节日', '春节', '元旦']},
        },
    },
    'career': {
        'name': '职业生涯关爱',
        'keywords': [
            ('职业生涯', 20), ('关爱服务', 15), ('十大关爱', 12),
            ('关爱实施意见', 15), ('全过程关爱', 15),
        ],
        'threshold': 12,
        'sub_topics': {
            '入职入会': {'keys': ['入职', '入会']},
            '恋爱交友': {'keys': ['恋爱', '交友']},
            '结婚成家': {'keys': ['结婚']},
            '生育哺乳': {'keys': ['生育', '哺乳']},
            '子女入学': {'keys': ['子女入学', '入学']},
            '职工生日': {'keys': ['生日']},
            '生病住院': {'keys': ['生病', '住院']},
            '困难帮扶': {'keys': ['困难', '帮扶']},
            '亲人去世': {'keys': ['去世']},
            '退休离岗': {'keys': ['退休', '离岗']},
        },
    },
    'sbr': {
        'name': '三不让帮扶救助',
        'keywords': [
            ('三不让', 20), ('帮困', 15), ('困难补助', 15),
            ('帮困助学', 15), ('医疗救助', 15),
            ('大病补助', 15), ('看不起病', 12), ('大病', 12),
            ('上不起学', 15), ('生活保', 12),
        ],
        'threshold': 12,
    },
    'finance': {
        'name': '财务管理办法',
        'keywords': [
            ('财务', 15), ('经费', 12), ('预算', 10),
            ('会费', 12), ('资产', 10), ('负债', 10),
            ('收支', 10), ('审计', 10), ('账户', 10),
        ],
        'threshold': 10,
    },
}

# 澄清菜单：模糊问题时返回选项
CLARIFY_MENUS = {
    'welfare': {
        'items': [
            {'label': '入职入会', 'key': '入职入会'},
            {'label': '恋爱交友', 'key': '恋爱交友'},
            {'label': '结婚成家', 'key': '结婚成家'},
            {'label': '生育哺乳', 'key': '生育哺乳'},
            {'label': '子女入学', 'key': '子女入学'},
            {'label': '职工生日', 'key': '职工生日'},
            {'label': '生病住院', 'key': '生病住院'},
            {'label': '困难帮扶', 'key': '困难帮扶'},
            {'label': '亲人去世', 'key': '亲人去世'},
            {'label': '退休离岗', 'key': '退休离岗'},
            {'label': '年节慰问', 'key': '年节慰问'},
        ],
        'source': '西安公司工会职业生涯全过程福利手册',
    },
    'career': {
        'items': [
            {'label': '入职入会', 'key': '入职入会'},
            {'label': '恋爱交友', 'key': '恋爱交友'},
            {'label': '结婚成家', 'key': '结婚成家'},
            {'label': '生育哺乳', 'key': '生育哺乳'},
            {'label': '子女入学', 'key': '子女入学'},
            {'label': '职工生日', 'key': '职工生日'},
            {'label': '生病住院', 'key': '生病住院'},
            {'label': '困难帮扶', 'key': '困难帮扶'},
            {'label': '亲人去世', 'key': '亲人去世'},
            {'label': '退休离岗', 'key': '退休离岗'},
        ],
        'source': '中铁二局职工职业生涯全过程关爱服务实施意见',
    },
    'sbr': {
        'items': [
            {'label': '三不让总体介绍', 'key': '三不让总体'},
            {'label': '困难补助', 'key': '困难补助'},
            {'label': '帮困助学', 'key': '帮困助学'},
            {'label': '医疗救助', 'key': '医疗救助'},
        ],
        'source': '三不让帮扶救助实施办法',
    },
    'finance': {
        'items': [
            {'label': '预算管理', 'key': '预算'},
            {'label': '经费收入管理', 'key': '经费收入'},
            {'label': '经费支出管理', 'key': '经费支出'},
            {'label': '资产与负债管理', 'key': '资产'},
        ],
        'source': '工会财务管理办法',
    },
}


def detect_topics(question):
    """检测问题涉及的主题分类"""
    chinese_text = re.sub(r'[^\u4e00-\u9fa5]', '', question)
    topics = {}
    for cat, config in TOPIC_CATEGORIES.items():
        score = 0
        for kw, weight in config['keywords']:
            if kw in chinese_text or kw in question:
                score += weight
        if score >= config['threshold']:
            topics[cat] = score
    return sorted(topics.items(), key=lambda x: -x[1])


def score_entry(question, entry):
    """改进的条目评分算法"""
    score = 0
    chinese_text = re.sub(r'[^\u4e00-\u9fa5]', '', question)
    entry_text = entry['title'] + ' ' + entry['content'] + ' ' + ' '.join(entry.get('keywords', []))

    # 1. 标题完全匹配（最高优先）
    title_clean = re.sub(r'[^\u4e00-\u9fa5]', '', entry.get('title', ''))
    if chinese_text and (chinese_text in title_clean or title_clean in chinese_text):
        score += 100

    # 2. 关键词精确匹配
    for kw in entry.get('keywords', []):
        if len(kw) >= 2 and kw in question:
            score += len(kw) * 6

    # 3. 长短语匹配
    for length in range(4, min(len(chinese_text) + 1, 9)):
        for i in range(len(chinese_text) - length + 1):
            lp = chinese_text[i:i + length]
            if lp in entry_text:
                score += len(lp) * 10

    # 4. 2-gram 模糊匹配
    q_words = set()
    for i in range(len(chinese_text) - 1):
        q_words.add(chinese_text[i:i+2])
    if q_words:
        match_count = sum(1 for w in q_words if w in entry_text)
        score += match_count / len(q_words) * 25

    # 5. 标题中的词额外加分
    for w in q_words:
        if w in entry.get('title', ''):
            score += 8

    return score


def find_best_entry(question, filter_fn=None, max_results=3):
    """找到最佳匹配条目（每个来源只取最好的一个）"""
    scored = []
    for entry in ENTRIES:
        if filter_fn and not filter_fn(entry):
            continue
        if any(b in entry.get('content', '') for b in BLACKLIST):
            continue
        if len(entry.get('content', '').strip()) < 20:
            continue
        s = score_entry(question, entry)
        if s > 8:
            scored.append((s, entry))
    scored.sort(key=lambda x: -x[0])

    seen_sources = set()
    results = []
    for s, entry in scored:
        source = entry.get('source_file', '')
        if source not in seen_sources:
            seen_sources.add(source)
            results.append((s, entry))
        if len(results) >= max_results:
            break
    return results


def find_entry_by_subtopic(sub_key):
    """按子主题关键词查找具体条目"""
    for cat, menu in CLARIFY_MENUS.items():
        for item in menu['items']:
            if item['key'] == sub_key:
                label = item['label']
                for entry in ENTRIES:
                    if label in entry.get('title', '') and len(entry.get('content', '')) > 50:
                        return entry
                for entry in ENTRIES:
                    if label in entry.get('content', '') and len(entry.get('content', '')) > 50:
                        return entry

    for entry in ENTRIES:
        if sub_key in entry.get('title', '') and len(entry.get('content', '')) > 30:
            return entry
    return None


def try_clarify(question, topics, source_filter=None):
    """尝试返回澄清菜单（问题太模糊时）"""
    if not topics:
        return None

    top_score = topics[0][1]

    if len(topics) >= 2 and not source_filter:
        return {
            'type': 'clarify',
            'answer': '您的问题可能涉及以下方面，请问您具体想了解哪一项？',
            'menu_items': [
                {'label': TOPIC_CATEGORIES[cat]['name'], 'key': cat}
                for cat, _ in topics
            ],
            'source': '知识库',
        }

    cat = topics[0][0]
    config = TOPIC_CATEGORIES[cat]

    if 'sub_topics' in config:
        sub_scores = {}
        for sub_name, sub_info in config['sub_topics'].items():
            for key in sub_info['keys']:
                if key in question:
                    sub_scores[sub_name] = sub_scores.get(sub_name, 0) + len(key) * 5

        if sub_scores:
            best_sub = max(sub_scores.items(), key=lambda x: x[1])
            if best_sub[1] >= 10:
                entry = find_entry_by_subtopic(best_sub[0])
                if entry:
                    if source_filter:
                        marker = SOURCE_FILE_MAP[source_filter]['marker']
                        if marker in entry.get('source_file', '') or marker in entry.get('source_title', ''):
                            return {'type': 'answer', 'entry': entry}
                        else:
                            return None
                    return {'type': 'answer', 'entry': entry}

        menu_config = CLARIFY_MENUS.get(cat)
        if menu_config and not source_filter:
            topic_name = config['name']
            return {
                'type': 'clarify',
                'answer': f'「{topic_name}」包含以下方面，请问您想了解哪一项？',
                'menu_items': menu_config['items'],
                'source': menu_config['source'],
            }

    return None


def source_filtered_search(question, source_name):
    """在指定来源文件中搜索"""
    marker = SOURCE_FILE_MAP[source_name]['marker']
    full_name = SOURCE_FILE_MAP[source_name]['full_name']

    filter_fn = lambda e: marker in e.get('source_file', '') or marker in e.get('source_title', '')
    results = find_best_entry(question, filter_fn=filter_fn, max_results=3)

    if results:
        top_score, top_entry = results[0]
        if top_score >= 10:
            parts = []
            for score, entry in results[:3]:
                title = entry.get('title', '').strip()
                content = entry.get('content', '').strip()
                source = entry.get('source_title', '')
                parts.append(f"【{title}】\n{content}\n（来源：{source}）")
            return {
                'type': 'detail',
                'answer': '\n\n'.join(parts)[:3000],
                'source': full_name,
            }

    main_entries = []
    for entry in ENTRIES:
        if marker in entry.get('source_file', '') or marker in entry.get('source_title', ''):
            if len(entry.get('content', '').strip()) > 50:
                if not any(b in entry.get('content', '') for b in BLACKLIST):
                    main_entries.append(entry)

    if main_entries:
        parts = []
        for entry in main_entries[:3]:
            title = entry.get('title', '').strip()
            content = entry.get('content', '').strip()
            if len(content) > 500:
                content = content[:500] + '…'
            source = entry.get('source_title', '')
            parts.append(f"【{title}】\n{content}\n（来源：{source}）")
        return {
            'type': 'detail',
            'answer': f'以下是「{full_name}」中的主要内容：\n\n' + '\n\n'.join(parts)[:3000],
            'source': full_name,
        }

    return None


def general_search(question):
    """通用搜索（兜底）"""
    results = find_best_entry(question)
    if results:
        top_score, top_entry = results[0]
        if top_score < 10:
            return None
        parts = []
        for score, entry in results[:3]:
            title = entry.get('title', '').strip()
            content = entry.get('content', '').strip()
            source = entry.get('source_title', '')
            parts.append(f"【{title}】\n{content}\n（来源：{source}）")
        return {
            'type': 'detail',
            'answer': '\n\n'.join(parts)[:3000],
            'source': top_entry.get('source_title', ''),
        }
    return None


def format_entry_answer(entry):
    """格式化条目为答案"""
    title = entry.get('title', '').strip()
    content = entry.get('content', '').strip()
    source = entry.get('source_title', '')
    return {
        'type': 'detail',
        'answer': f"【{title}】\n{content}",
        'source': source,
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
        # 0. 检测是否指定了来源文件
        source_filter = detect_source(question)

        if source_filter:
            marker = SOURCE_FILE_MAP[source_filter]['marker']
            filter_fn = lambda e: marker in e.get('source_file', '') or marker in e.get('source_title', '')
            results = find_best_entry(question, filter_fn=filter_fn, max_results=1)

            if results and results[0][0] >= 15:
                result = format_entry_answer(results[0][1])
                return jsonify({
                    'success': True,
                    'type': 'detail',
                    'answer': result['answer'],
                    'source': result['source'],
                })

            topics = detect_topics(question)
            if topics:
                clarify = try_clarify(question, topics, source_filter=source_filter)
                if clarify:
                    if clarify.get('type') == 'clarify':
                        return jsonify({
                            'success': True,
                            'type': 'clarify',
                            'answer': clarify['answer'],
                            'menu_items': clarify['menu_items'],
                            'source': clarify.get('source', ''),
                        })
                    elif clarify.get('type') == 'answer':
                        result = format_entry_answer(clarify['entry'])
                        return jsonify({
                            'success': True,
                            'type': 'detail',
                            'answer': result['answer'],
                            'source': result['source'],
                        })

            src_result = source_filtered_search(question, source_filter)
            if src_result:
                return jsonify({
                    'success': True,
                    'type': 'detail',
                    'answer': src_result['answer'],
                    'source': src_result['source'],
                })

        # 1. 检测主题
        topics = detect_topics(question)

        # 2. 尝试澄清
        clarify = try_clarify(question, topics)
        if clarify:
            if clarify.get('type') == 'clarify':
                return jsonify({
                    'success': True,
                    'type': 'clarify',
                    'answer': clarify['answer'],
                    'menu_items': clarify['menu_items'],
                    'source': clarify.get('source', ''),
                })
            elif clarify.get('type') == 'answer':
                result = format_entry_answer(clarify['entry'])
                return jsonify({
                    'success': True,
                    'type': 'detail',
                    'answer': result['answer'],
                    'source': result['source'],
                })

        # 3. 按关键词搜索具体条目
        entry = find_entry_by_subtopic(question)
        if entry:
            result = format_entry_answer(entry)
            return jsonify({
                'success': True,
                'type': 'detail',
                'answer': result['answer'],
                'source': result['source'],
            })

        # 4. 通用搜索兜底
        result = general_search(question)
        if result:
            return jsonify({
                'success': True,
                'type': 'detail',
                'answer': result['answer'],
                'source': result['source'],
            })

        # 5. 未找到
        return jsonify({
            'success': True,
            'type': 'not_found',
            'answer': '抱歉，未找到相关信息。您可以试试以下快捷问题：\n• 工会福利\n• 职业生涯关爱\n• 三不让帮扶救助\n• 财务管理办法',
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
