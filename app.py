#!/usr/bin/env python3
"""
工会知识库 API 服务 v4 — 主题分类 + 精准匹配 + 主动澄清 + 指定文件搜索
"""
import json
import os
import re
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO
import asyncio
import speech_recognition as sr
from pydub import AudioSegment
from edge_tts import Communicate

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

# 文件头条目 ID（内容只有文件头文本，不应作为搜索结果返回）
FILE_HEADER_IDS = {'career-00', 'sbr-00', 'finance-00'}

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
# 快捷按钮处理：点击按钮时直接返回章节菜单
# ============================================================
QUICK_BUTTON_QUERIES = {
    'career': ['职业生涯关爱', '职业生涯全过程', '全过程关爱服务'],
    'sbr': ['三不让帮扶救助', '三不让帮扶', '三不让办法', '三不让'],
    'finance': ['财务管理办法', '工会财务管理', '经费管理办法'],
    'welfare': ['工会福利', '福利梳理', '福利手册', '福利办法'],
}

QUICK_MENUS = {
    'career': {
        'answer': '「职业生涯全过程关爱服务」包含以下章节，请问您想了解哪一章？',
        'items': [
            {'label': '一、指导思想', 'key': 'career-01'},
            {'label': '二、工作原则', 'key': 'career-02'},
            {'label': '三、目的意义', 'key': 'career-03'},
            {'label': '四、主要任务（十大关爱服务）', 'key': 'career-04'},
            {'label': '五、具体要求', 'key': 'career-05'},
        ],
        'source': '中铁二局职工职业生涯全过程关爱服务实施意见',
    },
    'sbr': {
        'answer': '「三不让帮扶救助实施办法」包含以下章节，请问您想了解哪一章？',
        'items': [
            {'label': '第一章 总则', 'key': 'sbr-01'},
            {'label': '第二章 组织领导及要求', 'key': 'sbr-02'},
            {'label': '第三章 专项资金来源及管理', 'key': 'sbr-03'},
            {'label': '第四章 困难职工分类', 'key': 'sbr-04'},
            {'label': '第五章 困难补助', 'key': 'sbr-05'},
            {'label': '第六章 帮困助学', 'key': 'sbr-06'},
            {'label': '第七章 医疗救助', 'key': 'sbr-07'},
            {'label': '第八章 工作制度', 'key': 'sbr-08'},
            {'label': '第九章 附则', 'key': 'sbr-09'},
        ],
        'source': '三不让帮扶救助实施办法',
    },
    'finance': {
        'answer': '「工会财务管理办法」包含以下章节，请问您想了解哪一章？',
        'items': [
            {'label': '第一章 总则', 'key': 'finance-01'},
            {'label': '第二章 财务管理体制', 'key': 'finance-02'},
            {'label': '第三章 预算管理', 'key': 'finance-03'},
            {'label': '第四章 经费收入管理', 'key': 'finance-04'},
            {'label': '第五章 经费支出管理', 'key': 'finance-05'},
            {'label': '第六章 资金管理', 'key': 'finance-06'},
            {'label': '第七章 资产管理', 'key': 'finance-07'},
            {'label': '第八章 会计管理', 'key': 'finance-08'},
            {'label': '第九章 财务监督', 'key': 'finance-09'},
            {'label': '第十章 财务报表和财务分析', 'key': 'finance-10'},
            {'label': '第十一章 附则', 'key': 'finance-11'},
        ],
        'source': '中铁二局集团有限公司工会财务管理办法',
    },
    'welfare': {
        'answer': '「工会职业生涯全过程福利手册」包含以下内容，请问您想了解哪一项？',
        'items': [
            {'label': '一、入职入会', 'key': 'welfare-01'},
            {'label': '二、恋爱交友', 'key': 'welfare-02'},
            {'label': '三、结婚成家', 'key': 'welfare-03'},
            {'label': '四、生育哺乳', 'key': 'welfare-04'},
            {'label': '五、子女入学', 'key': 'welfare-05'},
            {'label': '六、职工生日', 'key': 'welfare-06'},
            {'label': '七、生病住院', 'key': 'welfare-07'},
            {'label': '八、困难帮扶', 'key': 'welfare-08'},
            {'label': '九、亲人去世', 'key': 'welfare-09'},
            {'label': '十、退休离岗', 'key': 'welfare-10'},
            {'label': '十一、年节慰问', 'key': 'welfare-11'},
        ],
        'source': '西安公司工会职业生涯全过程福利手册',
    },
}


def handle_quick_query(question):
    """处理快捷按钮查询，直接返回章节菜单"""
    for cat, queries in QUICK_BUTTON_QUERIES.items():
        for q in queries:
            if q in question:
                menu = QUICK_MENUS[cat]
                return {
                    'type': 'clarify',
                    'answer': menu['answer'],
                    'menu_items': menu['items'],
                    'source': menu['source'],
                }
    return None


def find_entry_by_id(entry_id):
    """根据条目ID直接查找"""
    for entry in ENTRIES:
        if entry['id'] == entry_id:
            return entry
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
            ('亲人去世', 15), ('去世', 12),
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
            {'label': '一、入职入会', 'key': 'welfare-01'},
            {'label': '二、恋爱交友', 'key': 'welfare-02'},
            {'label': '三、结婚成家', 'key': 'welfare-03'},
            {'label': '四、生育哺乳', 'key': 'welfare-04'},
            {'label': '五、子女入学', 'key': 'welfare-05'},
            {'label': '六、职工生日', 'key': 'welfare-06'},
            {'label': '七、生病住院', 'key': 'welfare-07'},
            {'label': '八、困难帮扶', 'key': 'welfare-08'},
            {'label': '九、亲人去世', 'key': 'welfare-09'},
            {'label': '十、退休离岗', 'key': 'welfare-10'},
            {'label': '十一、年节慰问', 'key': 'welfare-11'},
        ],
        'source': '西安公司工会职业生涯全过程福利手册',
    },
    'career': {
        'items': [
            {'label': '一、指导思想', 'key': '指导思想'},
            {'label': '二、工作原则', 'key': '工作原则'},
            {'label': '三、目的意义', 'key': '目的意义'},
            {'label': '四、主要任务', 'key': '主要任务'},
            {'label': '五、具体要求', 'key': '具体要求'},
        ],
        'source': '中铁二局职工职业生涯全过程关爱服务实施意见',
    },
    'sbr': {
        'items': [
            {'label': '第一章 总则', 'key': '第一章 总则'},
            {'label': '第二章 组织领导及要求', 'key': '第二章 组织领导'},
            {'label': '第三章 专项资金来源及管理', 'key': '第三章 专项资金'},
            {'label': '第四章 困难职工分类', 'key': '第四章 困难职工分类'},
            {'label': '第五章 困难补助', 'key': '第五章 困难补助'},
            {'label': '第六章 帮困助学', 'key': '第六章 帮困助学'},
            {'label': '第七章 医疗救助', 'key': '第七章 医疗救助'},
            {'label': '第八章 工作制度', 'key': '第八章 工作制度'},
            {'label': '第九章 附则', 'key': '第九章 附则'},
        ],
        'source': '三不让帮扶救助实施办法',
    },
    'finance': {
        'items': [
            {'label': '第一章 总则', 'key': '第一章 总则'},
            {'label': '第二章 财务管理体制', 'key': '第二章 财务管理体制'},
            {'label': '第三章 预算管理', 'key': '第三章 预算管理'},
            {'label': '第四章 经费收入管理', 'key': '第四章 经费收入'},
            {'label': '第五章 经费支出管理', 'key': '第五章 经费支出'},
            {'label': '第六章 资金管理', 'key': '第六章 资金管理'},
            {'label': '第七章 资产管理', 'key': '第七章 资产管理'},
            {'label': '第八章 会计管理', 'key': '第八章 会计管理'},
            {'label': '第九章 财务监督', 'key': '第九章 财务监督'},
            {'label': '第十章 财务报表和财务分析', 'key': '第十章 财务报表'},
            {'label': '第十一章 附则', 'key': '第十一章 附则'},
        ],
        'source': '中铁二局集团有限公司工会财务管理办法',
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


def find_best_entry(question, filter_fn=None, max_results=1):
    """找到最佳匹配条目（默认只返回最匹配的一条）"""
    scored = []
    for entry in ENTRIES:
        if filter_fn and not filter_fn(entry):
            continue
        # 过滤文件头条目
        if entry.get('id', '') in FILE_HEADER_IDS:
            continue
        if any(b in entry.get('content', '') for b in BLACKLIST):
            continue
        if len(entry.get('content', '').strip()) < 20:
            continue
        s = score_entry(question, entry)
        if s > 8:
            scored.append((s, entry))
    scored.sort(key=lambda x: -x[0])

    # 只取分数最高的条目（默认 max_results=1）
    results = []
    for s, entry in scored[:max_results]:
        results.append((s, entry))
    return results


def find_entry_by_subtopic(sub_key):
    """按子主题关键词查找具体条目（优先用ID精确匹配）"""
    # 1. 如果 sub_key 是条目 ID，直接查找
    entry = find_entry_by_id(sub_key)
    if entry and len(entry.get('content', '')) > 50:
        return entry

    # 2. 检查是否是澄清菜单里的key（可能是条目ID）
    for cat, menu in CLARIFY_MENUS.items():
        for item in menu['items']:
            if item['key'] == sub_key:
                # 如果 key 是条目 ID
                entry = find_entry_by_id(item['key'])
                if entry and len(entry.get('content', '')) > 50:
                    return entry
                # 否则按 label 标题匹配
                label = item['label']
                for entry in ENTRIES:
                    title = entry.get('title', '')
                    if label in title and len(entry.get('content', '')) > 50:
                        return entry
                # 标题包含关键词的任意部分
                label_parts = re.findall(r'[\u4e00-\u9fa5]+', label)
                for entry in ENTRIES:
                    title = entry.get('title', '')
                    if any(p in title for p in label_parts) and len(entry.get('content', '')) > 50:
                        return entry
                # 内容匹配
                for entry in ENTRIES:
                    if label in entry.get('content', '') and len(entry.get('content', '')) > 50:
                        return entry

    # 3. 通用子主题搜索：在标题中搜索
    for entry in ENTRIES:
        if sub_key in entry.get('title', '') and len(entry.get('content', '')) > 30:
            return entry
    # 在内容中搜索（取第一条）
    for entry in ENTRIES:
        if sub_key in entry.get('content', '') and len(entry.get('content', '')) > 50:
            return entry
    return None


def try_clarify(question, topics, source_filter=None):
    """尝试返回澄清菜单（问题太模糊时）"""
    if not topics:
        return None

    top_score = topics[0][1]

    # 多个主题匹配 → 返回主菜单
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

    # 单个主题
    cat = topics[0][0]
    config = TOPIC_CATEGORIES[cat]

    # 检查是否有子主题匹配
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
                    # 如果指定了来源文件，检查该条目是否匹配
                    if source_filter:
                        marker = SOURCE_FILE_MAP[source_filter]['marker']
                        if marker in entry.get('source_file', '') or marker in entry.get('source_title', ''):
                            return {'type': 'answer', 'entry': entry}
                        else:
                            # 指定了来源但条目不匹配，在指定来源中搜索
                            return None
                    return {'type': 'answer', 'entry': entry}

        # 没有具体子主题匹配 → 返回子主题菜单
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

    # 在指定来源的条目中搜索（只取最佳一条）
    filter_fn = lambda e: marker in e.get('source_file', '') or marker in e.get('source_title', '')
    results = find_best_entry(question, filter_fn=filter_fn, max_results=1)

    if results:
        top_score, top_entry = results[0]
        if top_score >= 10:
            title = top_entry.get('title', '').strip()
            content = top_entry.get('content', '').strip()
            source = top_entry.get('source_title', '')
            return {
                'type': 'detail',
                'answer': f"【{title}】\n{content}\n（来源：{source}）",
                'source': full_name,
            }

    # 指定了来源但没找到具体匹配 → 返回该来源的概览菜单
    menu_items = []
    for entry in ENTRIES:
        if marker in entry.get('source_file', '') or marker in entry.get('source_title', ''):
            if len(entry.get('content', '').strip()) > 50:
                if not any(b in entry.get('content', '') for b in BLACKLIST):
                    title = entry.get('title', '').strip()
                    # 提取简短标题
                    short_title = re.sub(r'^[一二三四五六七八九十]+[、.]\s*', '', title)
                    if len(short_title) > 20:
                        short_title = short_title[:20] + '…'
                    menu_items.append({'label': short_title, 'key': title})

    if menu_items:
        return {
            'type': 'clarify',
            'answer': f'「{full_name}」包含以下内容，请问您想了解哪一条？',
            'menu_items': menu_items[:8],
            'source': full_name,
        }

    return None


def general_search(question):
    """通用搜索（兜底）— 只返回最匹配的一条"""
    results = find_best_entry(question, max_results=1)
    if results:
        top_score, top_entry = results[0]
        if top_score < 10:
            return None
        title = top_entry.get('title', '').strip()
        content = top_entry.get('content', '').strip()
        source = top_entry.get('source_title', '')
        return {
            'type': 'detail',
            'answer': f"【{title}】\n{content}\n（来源：{source}）",
            'source': source,
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
        # 0. 快捷按钮处理：优先返回章节菜单
        quick_result = handle_quick_query(question)
        if quick_result:
            return jsonify({
                'success': True,
                'type': quick_result['type'],
                'answer': quick_result['answer'],
                'menu_items': quick_result['menu_items'],
                'source': quick_result.get('source', ''),
            })

        # 0.5 检测是否指定了来源文件
        source_filter = detect_source(question)

        # 0.6 检测是否为菜单选择（前端发送 __ENTRY__:id:label 格式）
        if question.startswith('__ENTRY__:'):
            parts = question.split(':', 2)
            if len(parts) >= 2:
                entry_id = parts[1]
                entry = find_entry_by_id(entry_id)
                if entry and len(entry.get('content', '')) > 50:
                    result = format_entry_answer(entry)
                    return jsonify({
                        'success': True,
                        'type': 'detail',
                        'answer': result['answer'],
                        'source': result['source'],
                    })
            # 解析失败，去掉前缀继续正常流程
            question = parts[2] if len(parts) > 2 else question

        # 如果指定了来源文件，优先在指定文件中精确搜索
        if source_filter:
            # 先尝试在指定文件中找具体条目
            marker = SOURCE_FILE_MAP[source_filter]['marker']
            filter_fn = lambda e: marker in e.get('source_file', '') or marker in e.get('source_title', '')
            results = find_best_entry(question, filter_fn=filter_fn, max_results=1)

            if results and results[0][0] >= 15:
                # 找到高匹配度条目，直接返回
                result = format_entry_answer(results[0][1])
                return jsonify({
                    'success': True,
                    'type': 'detail',
                    'answer': result['answer'],
                    'source': result['source'],
                })

            # 高匹配度没找到，尝试主题分类（在指定来源内）
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

            # 兜底：来源限定搜索
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

        # 2. 尝试澄清（模糊问题时返回菜单）
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


# ============================================================
# TTS 缓存：相同文本只生成一次音频
# ============================================================
import hashlib

TTS_CACHE_DIR = os.path.join(_base_dir, 'tts_cache')
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

def _tts_cache_path(text):
    h = hashlib.md5(text.encode('utf-8')).hexdigest()
    return os.path.join(TTS_CACHE_DIR, f'{h}.mp3')

@app.route('/api/tts', methods=['GET'])
def tts_api():
    """将文本转为 MP3 音频返回（温柔女声 XiaoxiaoNeural），带文件缓存"""
    text = request.args.get('text', '').strip()
    if not text:
        return jsonify({'success': False, 'error': 'text is required'}), 400

    # 命中缓存 → 直接返回文件（~10ms）
    cache_path = _tts_cache_path(text)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        return send_file(cache_path, mimetype='audio/mpeg', as_attachment=False,
                         download_name='tts.mp3')

    # 未命中 → 生成音频
    try:
        async def _generate():
            communicate = Communicate(text, "zh-CN-XiaoxiaoNeural", rate="-5%", pitch="+2Hz")
            chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b''.join(chunks)

        audio_data = asyncio.run(_generate())

        # 写入缓存
        with open(cache_path, 'wb') as f:
            f.write(audio_data)

        buf = BytesIO(audio_data)
        buf.seek(0)
        return send_file(buf, mimetype='audio/mpeg', as_attachment=False,
                         download_name='tts.mp3')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/preload_tts', methods=['GET', 'POST'])
def preload_tts():
    """预生成所有条目的 TTS 音频缓存（后台线程执行，不阻塞返回）"""
    import threading

    def _do_preload():
        generated = 0
        skipped = 0
        errors = 0
        for entry in ENTRIES:
            if entry.get('id', '') in FILE_HEADER_IDS:
                continue
            content = entry.get('content', '').strip()
            if len(content) < 20:
                continue
            if any(b in content for b in BLACKLIST):
                continue
            title = entry.get('title', '').strip()
            # 生成两种格式的文本（匹配 /api/ask 返回的两种 answer 格式）
            texts = [
                f"【{title}】\n{content}",
                f"【{title}】\n{content}\n（来源：{entry.get('source_title', '')}）",
            ]
            for text in texts:
                cache_path = _tts_cache_path(text)
                if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
                    skipped += 1
                    continue
                try:
                    async def _generate(t=text):
                        comm = Communicate(t, "zh-CN-XiaoxiaoNeural", rate="-5%", pitch="+2Hz")
                        chunks = []
                        async for chunk in comm.stream():
                            if chunk["type"] == "audio":
                                chunks.append(chunk["data"])
                        return b''.join(chunks)
                    audio_data = asyncio.run(_generate())
                    with open(cache_path, 'wb') as f:
                        f.write(audio_data)
                    generated += 1
                except Exception as e:
                    errors += 1
                    print(f"TTS preload error: {e}")
        print(f"TTS preload done: generated={generated}, skipped={skipped}, errors={errors}")

    threading.Thread(target=_do_preload, daemon=True).start()
    return jsonify({'success': True, 'message': 'preload started in background'})


@app.route('/api/stt', methods=['POST'])
def stt_api():
    """语音转文字：接收音频 → 转为 WAV → Google STT 识别中文"""
    if 'audio' not in request.files:
        return jsonify({'success': False, 'error': '没有收到音频文件'}), 400
    try:
        audio_file = request.files['audio']
        # 读取上传的音频（webm/ogg/mp4 等格式）
        audio_seg = AudioSegment.from_file(audio_file)
        # 转为 WAV（16kHz 单声道，Google STT 要求的格式）
        wav_seg = audio_seg.set_frame_rate(16000).set_channels(1)
        wav_buf = BytesIO()
        wav_seg.export(wav_buf, format='wav')
        wav_buf.seek(0)

        # 用 Google 免费语音识别（支持中文）
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_buf) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data, language='zh-CN')
        return jsonify({'success': True, 'text': text})
    except sr.UnknownValueError:
        return jsonify({'success': False, 'error': '未能识别语音内容，请再说一次'}), 200
    except sr.RequestError as e:
        return jsonify({'success': False, 'error': f'语音识别服务不可用: {e}'}), 503
    except Exception as e:
        return jsonify({'success': False, 'error': f'处理失败: {str(e)}'}), 500


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
