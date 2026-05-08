"""
AI知识农场 - 后端主应用
提供所有API路由和数据库初始化逻辑
"""

import sys
import io
import os

if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import List, Dict, Any

import json
import time
import logging
import random
import traceback

# ============================================
# 日志配置
# ============================================
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ============================================
# 环境变量加载（使用绝对路径）
# ============================================
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_load_result = load_dotenv(_env_path, override=True)

print("=" * 60)
print(f"[DIAG] app.py: load_dotenv result = {_load_result}")
print(f"[DIAG] app.py: .env path = {_env_path}")
print(f"[DIAG] app.py: USE_FALLBACK = {os.getenv('USE_FALLBACK', 'NOT_SET')}")
print(f"[DIAG] app.py: DEEPSEEK_API_KEY exists = {bool(os.getenv('DEEPSEEK_API_KEY'))}")
print("=" * 60)

# ============================================
# Flask 应用初始化
# ============================================
DEMO_USER_ID = 1

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 前端静态文件根目录（绝对路径）
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'farm_frontend'))

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///farm.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_AS_ASCII'] = False
app.json.ensure_ascii = False


@app.after_request
def set_utf8_charset(response):
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

# ============================================
# 数据库初始化
# ============================================
from models import db
db.init_app(app)

from models import User, KnowledgeItem, Plot, BackpackItem, StudySession, ExamSession, ExamAnswer, Fruit, Decoration, UserDecoration
from ai_service import (
    extract_knowledge_from_conversation,
    generate_fact_card,
    generate_concept_question,
    ai_evaluate_concept_answer,
    auto_classify,
    analyze_prerequisites,
    evaluate_coding_code,
    generate_assistant_message,
    generate_topic_summary,
    evaluate_and_answer_question,
    structure_video_content,
    summarize_long_text,
    MAX_PROMPT_LEN,
    SUMMARY_THRESHOLD,
    ENABLE_SUMMARY_COMPRESS,
    DEFAULT_MESSAGES
)
from bilibili_service import get_video_full_text, mock_bilibili_import

def _seed_decorations(database, model):
    """种子装饰数据"""
    items = [
        {"name": "木质边框", "key": "wood_border", "price": 50, "category": "border",
         "css_rule": ".farm-container { border: 6px solid #8D6E63; border-radius: 16px; }"},
        {"name": "星空背景", "key": "star_bg", "price": 120, "category": "background",
         "css_rule": "body { background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); }"},
        {"name": "金色边框", "key": "gold_border", "price": 100, "category": "border",
         "css_rule": ".farm-container { border: 4px solid #FFD700; border-radius: 12px; box-shadow: 0 0 20px rgba(255,215,0,0.3); }"},
        {"name": "春日花园", "key": "spring_garden", "price": 80, "category": "background",
         "css_rule": "body { background: linear-gradient(135deg, #e8f5e9, #c8e6c9, #a5d6a7); }"},
        {"name": "暗夜模式", "key": "dark_mode", "price": 150, "category": "theme",
         "css_rule": "body { background: #121212; color: #e0e0e0; } .farm-container { background: #1e1e1e; }"},
    ]
    for item in items:
        if not model.query.filter_by(key=item["key"]).first():
            database.session.add(model(**item))
    database.session.commit()

# ============================================
# 数据库迁移与初始化
# ============================================
with app.app_context():
    db.create_all()

    # 迁移: 添加 difficulty_offset 字段到 knowledge_items
    try:
        db.session.execute(db.text("SELECT difficulty_offset FROM knowledge_items LIMIT 1"))
    except Exception:
        logger.info("迁移: 添加 difficulty_offset 字段到 knowledge_items")
        db.session.execute(db.text("ALTER TABLE knowledge_items ADD COLUMN difficulty_offset FLOAT DEFAULT 0.0"))
        db.session.commit()

    # 迁移: 创建 exam_sessions 和 exam_answers 表
    try:
        db.session.execute(db.text("SELECT id FROM exam_sessions LIMIT 1"))
    except Exception:
        logger.info("迁移: 创建 exam_sessions 和 exam_answers 表")
        ExamSession.__table__.create(db.engine, checkfirst=True)
        ExamAnswer.__table__.create(db.engine, checkfirst=True)
        db.session.commit()

    # 迁移: 创建 study_sessions 表
    try:
        db.session.execute(db.text("SELECT id FROM study_sessions LIMIT 1"))
    except Exception:
        logger.info("迁移: 创建 study_sessions 表")
        StudySession.__table__.create(db.engine, checkfirst=True)
        db.session.commit()

    # 迁移: 创建 fruits, decorations, user_decorations 表
    try:
        db.session.execute(db.text("SELECT id FROM fruits LIMIT 1"))
    except Exception:
        logger.info("迁移: 创建 fruits 表")
        Fruit.__table__.create(db.engine, checkfirst=True)
    try:
        db.session.execute(db.text("SELECT id FROM decorations LIMIT 1"))
    except Exception:
        logger.info("迁移: 创建 decorations 表")
        Decoration.__table__.create(db.engine, checkfirst=True)
        db.session.commit()
    if Decoration.query.count() == 0:
        _seed_decorations(db, Decoration)
        db.session.commit()
    try:
        db.session.execute(db.text("SELECT id FROM user_decorations LIMIT 1"))
    except Exception:
        logger.info("迁移: 创建 user_decorations 表")
        UserDecoration.__table__.create(db.engine, checkfirst=True)
        db.session.commit()

    # 创建演示用户
    default_user = User.query.get(DEMO_USER_ID)
    if not default_user:
        default_user = User(id=DEMO_USER_ID, knowledge_coins=0)
        db.session.add(default_user)
        db.session.flush()
        logger.info("演示用户已创建: user_id=%d", DEMO_USER_ID)

    # 创建9个空地块
    existing_plots = Plot.query.filter_by(user_id=DEMO_USER_ID).count()
    if existing_plots == 0:
        for i in range(9):
            plot = Plot(
                user_id=DEMO_USER_ID,
                plot_index=i,
                is_harvestable=False
            )
            db.session.add(plot)
    elif existing_plots < 9:
        existing_indices = {p.plot_index for p in Plot.query.filter_by(user_id=DEMO_USER_ID).all()}
        for i in range(9):
            if i not in existing_indices:
                plot = Plot(
                    user_id=DEMO_USER_ID,
                    plot_index=i,
                    is_harvestable=False
                )
                db.session.add(plot)
                logger.info("迁移: 补齐地块 index=%d for user=%d", i, DEMO_USER_ID)

    # 清除旧的测试数据：无地块时确保背包和知识点为空
    # 如果地块全空且无种植记录，清空残留的测试知识点和背包
    if existing_plots > 0:
        planted_count = Plot.query.filter(
            Plot.user_id == DEMO_USER_ID,
            Plot.item_id.isnot(None)
        ).count()
        if planted_count == 0:
            BackpackItem.query.filter_by(user_id=DEMO_USER_ID).delete()
            KnowledgeItem.query.filter_by(user_id=DEMO_USER_ID).delete()
            logger.info("启动清理: 已清除残留的测试知识点和背包数据")

    # 迁移: 将 item_id=0 的地块更新为 NULL
    migrated_zero = Plot.query.filter(Plot.item_id == 0).update({Plot.item_id: None})
    if migrated_zero > 0:
        logger.info("迁移: %d 条地块 item_id=0 已更新为 NULL", migrated_zero)

    # 迁移: 处理 item_id 为空字符串的地块
    try:
        db.session.execute(
            db.text("UPDATE plots SET item_id = NULL WHERE CAST(item_id AS TEXT) = ''")
        )
        logger.info("迁移: 已处理 item_id 为空字符串的地块")
    except Exception:
        pass

    # 迁移: 修复 JSON 字段中的脏数据（prerequisite_ids, tags, derivation_steps, common_mistakes, application_examples）
    json_columns = ['prerequisite_ids', 'tags', 'derivation_steps', 'common_mistakes', 'application_examples']
    for col in json_columns:
        try:
            rows = db.session.execute(
                db.text(f"SELECT id, {col} FROM knowledge_items WHERE {col} IS NOT NULL")
            ).fetchall()
            fixed_count = 0
            for row in rows:
                raw_val = row[1]
                if raw_val is None:
                    continue
                if isinstance(raw_val, (list, dict)):
                    continue
                if isinstance(raw_val, str):
                    stripped = raw_val.strip()
                    if not stripped or stripped in ('[', '[]', 'null', 'None', ''):
                        db.session.execute(
                            db.text(f"UPDATE knowledge_items SET {col} = '[]' WHERE id = :rid"),
                            {"rid": row[0]}
                        )
                        fixed_count += 1
                    else:
                        try:
                            parsed = json.loads(stripped)
                            if not isinstance(parsed, list):
                                db.session.execute(
                                    db.text(f"UPDATE knowledge_items SET {col} = '[]' WHERE id = :rid"),
                                    {"rid": row[0]}
                                )
                                fixed_count += 1
                        except (json.JSONDecodeError, ValueError):
                            db.session.execute(
                                db.text(f"UPDATE knowledge_items SET {col} = '[]' WHERE id = :rid"),
                                {"rid": row[0]}
                            )
                            fixed_count += 1
            if fixed_count > 0:
                logger.info("迁移: 修复 %s 字段 %d 条脏数据", col, fixed_count)
        except Exception as e:
            logger.warning("迁移: 检查 %s 字段时出错: %s", col, e)

    db.session.commit()

# ============================================
# 环境变量开关
# ============================================
ENABLE_EXAM_MODE = os.getenv('ENABLE_EXAM_MODE', 'True').lower() == 'true'
ENABLE_REPORT = os.getenv('ENABLE_REPORT', 'True').lower() == 'true'
ENABLE_ADAPTIVE = os.getenv('ENABLE_ADAPTIVE', 'True').lower() == 'true'

print("=" * 60)
print(f"[MODULE] ENABLE_EXAM_MODE = {ENABLE_EXAM_MODE}")
print(f"[MODULE] ENABLE_REPORT = {ENABLE_REPORT}")
print(f"[MODULE] ENABLE_ADAPTIVE = {ENABLE_ADAPTIVE}")
print("=" * 60)


# ============================================
# 辅助函数
# ============================================

def calculate_similarity(title1: str, title2: str) -> float:
    """
    计算两个标题的相似度。使用Jaccard相似度（基于双字分词）。

    Args:
        title1: 第一个标题
        title2: 第二个标题

    Returns:
        相似度分数（0-1）
    """
    if not title1 or not title2:
        return 0.0

    def get_bigrams(text: str) -> set:
        text = text.lower().strip()
        bigrams = set()
        for i in range(len(text) - 1):
            bigrams.add(text[i:i + 2])
        return bigrams

    bigrams1 = get_bigrams(title1)
    bigrams2 = get_bigrams(title2)

    if not bigrams1 and not bigrams2:
        return 0.0

    intersection = bigrams1 & bigrams2
    union = bigrams1 | bigrams2

    return len(intersection) / len(union) if union else 0.0


def find_similar_concepts(user_id: int, threshold: float = 0.6) -> List[Dict[str, Any]]:
    """
    查找用户所有可配对的相似知识点。

    Args:
        user_id: 用户ID
        threshold: 相似度阈值

    Returns:
        相似知识点对列表
    """
    items = KnowledgeItem.query.filter_by(user_id=user_id).all()
    pairs = []

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            item1 = items[i]
            item2 = items[j]

            # 跳过已配对的知识
            if item1.paired_with_id or item2.paired_with_id:
                continue

            similarity = calculate_similarity(item1.title, item2.title)
            if similarity >= threshold:
                pairs.append({
                    'item1': {
                        'id': item1.id,
                        'title': item1.title,
                        'tags': item1.tags or [],
                        'domain': item1.domain,
                        'type': item1.type
                    },
                    'item2': {
                        'id': item2.id,
                        'title': item2.title,
                        'tags': item2.tags or [],
                        'domain': item2.domain,
                        'type': item2.type
                    },
                    'similarity': similarity
                })

    return pairs


def generate_coding_question(knowledge_item) -> Dict[str, Any]:
    """根据知识点生成编程题目"""
    from ai_service import _call_deepseek

    if os.getenv('USE_FALLBACK', 'True').lower() == 'true':
        return {
            'title': f'实现{knowledge_item.title}',
            'description': f'请编写一个Python函数来实现{knowledge_item.title}的功能。',
            'input_format': '输入参数说明',
            'output_format': '输出结果说明',
            'examples': [
                {
                    'input': '示例输入',
                    'output': '示例输出'
                }
            ],
            'difficulty': knowledge_item.difficulty
        }

    prompt = f"""你是一个编程题目生成助手。请根据以下知识点生成一道编程题：

知识点：
标题：{knowledge_item.title}
内容：{knowledge_item.content}

请生成一道编程题，包含：
1. 题目标题
2. 题目描述（详细说明要实现的功能）
3. 输入格式
4. 输出格式
5. 1-2个输入输出示例
6. 难度等级1-5

输出格式为JSON：
{{
    "title": "题目标题",
    "description": "详细描述",
    "input_format": "输入格式说明",
    "output_format": "输出格式说明",
    "examples": [{{"input": "...", "output": "..."}}],
    "difficulty": 3
}}"""

    response = _call_deepseek(prompt, temperature=0.5)
    import re
    json_match = re.search(r'(\{.*\})', response, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    return {
        'title': f'实现{knowledge_item.title}',
        'description': f'请编写代码实现{knowledge_item.title}相关功能。',
        'input_format': '输入说明',
        'output_format': '输出说明',
        'examples': [{'input': '', 'output': ''}],
        'difficulty': knowledge_item.difficulty
    }


# ============================================
# API 路由
# ============================================

# 1. GET / - 静态文件服务
@app.route('/')
def index():
    """返回前端首页"""
    return send_from_directory(FRONTEND_DIR, 'index.html')


# 1b. GET /<path:path> - 通用静态文件
@app.route('/<path:path>')
def serve_static(path):
    """返回 farm_frontend 目录下的静态文件（CSS/JS/图片等）"""
    return send_from_directory(FRONTEND_DIR, path)


# 2. GET /api/health - 健康检查
@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点，用于部署验证"""
    try:
        user = User.query.get(DEMO_USER_ID)
        plot_count = Plot.query.filter_by(user_id=DEMO_USER_ID).count()
        return jsonify({
            'status': 'ok',
            'service': 'ai-learning-farm',
            'database': 'connected',
            'user_exists': user is not None,
            'plot_count': plot_count,
            'use_fallback': os.getenv('USE_FALLBACK', 'True'),
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
        }), 500


# 3. GET /api/test_ai - AI测试
@app.route('/api/test_ai', methods=['GET'])
def test_ai():
    """测试 AI 调用是否正常工作"""
    from ai_service import _call_deepseek, USE_FALLBACK, DEEPSEEK_API_KEY, MODEL_NAME

    result = {
        'fallback_mode': USE_FALLBACK,
        'api_key_set': bool(DEEPSEEK_API_KEY and DEEPSEEK_API_KEY != 'your-deepseek-api-key'),
        'model_name': MODEL_NAME,
        'test_result': None,
        'error': None
    }

    if USE_FALLBACK:
        result['test_result'] = (
            '当前为降级模式(USE_FALLBACK=True)，所有AI调用返回模拟数据。'
            '如需真实调用，请在.env中设置USE_FALLBACK=False并填入有效的DEEPSEEK_API_KEY。'
        )
        return jsonify(result)

    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == 'your-deepseek-api-key':
        result['error'] = 'DEEPSEEK_API_KEY 未配置或为默认值，请在.env中填入有效的API Key'
        return jsonify(result)

    try:
        response = _call_deepseek("请用一句话回答：1+1等于几？", temperature=0.0)
        result['test_result'] = response[:200]
    except Exception as e:
        result['error'] = str(e)

    return jsonify(result)


# 3. POST /api/reset - 重置数据
@app.route('/api/reset', methods=['POST'])
def reset_farm():
    """重置所有农场数据 - 清空地块、背包和知识点"""
    try:
        user_id = DEMO_USER_ID

        Plot.query.filter_by(user_id=user_id).update({
            'item_id': None,
            'growth_value': 0,
            'is_harvestable': False,
            'crop_variant': 'normal',
            'planted_at': None,
            'error_plot_correct': 0
        })

        BackpackItem.query.filter_by(user_id=user_id).delete()

        StudySession.query.filter_by(user_id=user_id).delete()
        ExamSession.query.filter_by(user_id=user_id).delete()

        KnowledgeItem.query.filter_by(user_id=user_id).delete()

        user = User.query.get(user_id)
        if user:
            user.knowledge_coins = 0

        db.session.commit()

        logger.info("[reset] 农场已重置: user=%d", user_id)
        return jsonify({'status': 'ok', 'message': 'Farm reset successfully'})

    except Exception as e:
        db.session.rollback()
        logger.error("[reset] 重置失败: %s", str(e), exc_info=True)
        return jsonify({'error': str(e)}), 500


# 4. POST /api/extract - 提取知识点
@app.route('/api/extract', methods=['POST'])
def extract_knowledge():
    """从对话中提取知识点并保存到数据库"""
    _start = time.time()
    try:
        data = request.get_json()
        conversation = data.get('conversation', '') or data.get('text', '')

        logger.info("[extract] 请求参数: %s...", conversation[:200] if conversation else "(空)")

        # 文本长度上限控制：优先摘要压缩，失败则截断
        if len(conversation) > MAX_PROMPT_LEN:
            if len(conversation) > SUMMARY_THRESHOLD and ENABLE_SUMMARY_COMPRESS:
                conversation = summarize_long_text(conversation)
            if len(conversation) > MAX_PROMPT_LEN:
                logger.warning("[extract] 文本过长(%d)，已截断至%d字符", len(conversation), MAX_PROMPT_LEN)
                conversation = conversation[:MAX_PROMPT_LEN]

        knowledge_points = extract_knowledge_from_conversation(conversation)

        t_elapsed = time.time() - _start
        logger.info("[PERF] extract 完成: 文本长度=%d, 知识点=%d, 耗时=%.2fs", len(conversation), len(knowledge_points or []), t_elapsed)
        if t_elapsed > 10:
            logger.warning("[PERF] extract 耗时异常(>10s): 文本长度=%d, 知识点=%d, 耗时=%.2fs", len(conversation), len(knowledge_points or []), t_elapsed)

        if not knowledge_points:
            logger.warning("[extract] AI 服务返回空结果，使用降级数据")
            return jsonify({'knowledge_points': [], 'extended_points': []})

        logger.info("[extract] 提取到 %d 个知识点", len(knowledge_points))

        user_id = DEMO_USER_ID
        saved_points = []
        extended_points = []

        for point in knowledge_points:
            item_type = point.get('type', 'fact')
            title = point.get('title', '').strip()
            content = point.get('content', '').strip()

            if not title and content:
                title = content[:50].rsplit('，', 1)[0].rsplit('。', 1)[0] or content[:50]
            if not title:
                title = f"知识点_{len(saved_points) + 1}"
            if not content:
                content = title
            if not item_type or item_type not in ('fact', 'concept'):
                item_type = auto_classify(content) if content else 'fact'

            raw_difficulty = point.get('difficulty', 2)
            if isinstance(raw_difficulty, float) and raw_difficulty <= 1.0:
                difficulty = max(1, min(5, round(raw_difficulty * 5)))
            else:
                difficulty = int(raw_difficulty) if raw_difficulty else 2

            tags = point.get('tags', [])
            domain = point.get('domain')
            depth = point.get('depth', 'basic')
            is_extension = point.get('extension', False)
            formula = point.get('formula', '')
            derivation_steps = point.get('derivation_steps', [])
            common_mistakes = point.get('common_mistakes', [])
            application_examples = point.get('application_examples', [])

            try:
                prereq_ids = analyze_prerequisites(content)
            except Exception:
                prereq_ids = []

            if not isinstance(prereq_ids, list):
                prereq_ids = []
            if not isinstance(tags, list):
                tags = []
            if not isinstance(derivation_steps, list):
                derivation_steps = []
            if not isinstance(common_mistakes, list):
                common_mistakes = []
            if not isinstance(application_examples, list):
                application_examples = []

            knowledge_item = KnowledgeItem(
                user_id=user_id,
                type=item_type,
                title=title,
                content=content,
                difficulty=difficulty,
                srs_level=0,
                mastery=0.0,
                prerequisite_ids=prereq_ids,
                next_review_at=datetime.utcnow(),
                tags=tags,
                domain=domain,
                depth=depth,
                formula=formula,
                derivation_steps=derivation_steps,
                common_mistakes=common_mistakes,
                application_examples=application_examples
            )
            db.session.add(knowledge_item)
            db.session.flush()

            if not is_extension:
                backpack_item = BackpackItem.query.filter_by(
                    user_id=user_id,
                    item_id=knowledge_item.id
                ).first()

                if backpack_item:
                    backpack_item.quantity += 1
                else:
                    backpack_item = BackpackItem(
                        user_id=user_id,
                        item_id=knowledge_item.id,
                        quantity=1
                    )
                    db.session.add(backpack_item)

                saved_points.append({
                    'id': knowledge_item.id,
                    'title': title,
                    'content': content,
                    'type': item_type,
                    'difficulty': difficulty,
                    'tags': tags,
                    'domain': domain,
                    'depth': depth,
                    'formula': formula or '',
                    'derivation_steps': derivation_steps,
                    'common_mistakes': common_mistakes,
                    'application_examples': application_examples
                })
            else:
                extended_points.append({
                    'id': knowledge_item.id,
                    'title': title,
                    'content': content,
                    'type': item_type,
                    'difficulty': difficulty,
                    'tags': tags,
                    'domain': domain,
                    'depth': depth,
                    'formula': formula or '',
                    'derivation_steps': derivation_steps,
                    'common_mistakes': common_mistakes,
                    'application_examples': application_examples
                })

        db.session.commit()

        response = {
            'knowledge_points': saved_points,
            'extended_points': extended_points
        }
        return jsonify(response)

    except Exception as e:
        db.session.rollback()
        logger.error("[extract] 提取失败: %s", str(e), exc_info=True)
        return jsonify({'error': str(e), 'knowledge_points': [], 'extended_points': []}), 500


# 5. GET /api/farm - 获取农场数据
@app.route('/api/farm', methods=['GET'])
def get_farm():
    """获取默认用户的所有地块数据"""
    try:
        user_id = DEMO_USER_ID
        plots = Plot.query.filter_by(user_id=user_id).order_by(Plot.plot_index).all()

        result = []
        for plot in plots:
            plot_data = {
                'id': plot.id,
                'plot_index': plot.plot_index,
                'item_id': plot.item_id,
                'growth_value': plot.growth_value or 0,
                'is_harvestable': plot.is_harvestable,
                'crop_variant': plot.crop_variant or 'normal',
                'is_paired': False,
                'paired_with': None,
                'title': None,
                'type': None,
                'content': None,
                'difficulty': None,
                'mastery': None,
                'tags': None,
                'domain': None,
                'depth': None,
            }

            if plot.item_id is not None:
                knowledge_item = KnowledgeItem.query.get(plot.item_id)
                if knowledge_item:
                    plot_data['title'] = knowledge_item.title
                    plot_data['type'] = knowledge_item.type
                    plot_data['content'] = knowledge_item.content
                    plot_data['difficulty'] = knowledge_item.difficulty
                    plot_data['mastery'] = knowledge_item.mastery
                    plot_data['tags'] = knowledge_item.tags
                    plot_data['domain'] = knowledge_item.domain
                    plot_data['depth'] = knowledge_item.depth

                    if knowledge_item.paired_with_id:
                        paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
                        if paired_item:
                            plot_data['is_paired'] = True
                            plot_data['paired_with'] = paired_item.title

            result.append(plot_data)

        return jsonify({'plots': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 6. GET /api/farm_summary - 农场概要
@app.route('/api/farm_summary', methods=['GET'])
def get_farm_summary():
    """获取农场概要统计信息"""
    try:
        user_id = DEMO_USER_ID

        total_plots = Plot.query.filter_by(user_id=user_id).count()
        occupied_plots = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.isnot(None)
        ).count()
        empty_plots = total_plots - occupied_plots

        harvestable_plots = Plot.query.filter_by(
            user_id=user_id, is_harvestable=True
        ).count()

        total_items = KnowledgeItem.query.filter_by(user_id=user_id).count()
        backpack_count = BackpackItem.query.filter_by(user_id=user_id).count()

        user = User.query.get(user_id)
        coins = user.knowledge_coins if user else 0

        return jsonify({
            'total_plots': total_plots,
            'occupied_plots': occupied_plots,
            'empty_plots': empty_plots,
            'harvestable_plots': harvestable_plots,
            'total_knowledge_items': total_items,
            'backpack_count': backpack_count,
            'knowledge_coins': coins,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 7. GET /api/backpack - 背包数据
@app.route('/api/backpack', methods=['GET'])
def get_backpack():
    """获取用户背包中的所有物品"""
    try:
        user_id = DEMO_USER_ID
        backpack_items = BackpackItem.query.filter_by(user_id=user_id).all()

        result = []
        for item in backpack_items:
            knowledge_item = KnowledgeItem.query.get(item.item_id)
            if knowledge_item:
                is_paired = False
                paired_title = None
                if knowledge_item.paired_with_id:
                    paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
                    if paired_item:
                        is_paired = True
                        paired_title = paired_item.title

                result.append({
                    'id': knowledge_item.id,
                    'item_id': knowledge_item.id,
                    'title': knowledge_item.title,
                    'content': knowledge_item.content[:200],
                    'type': knowledge_item.type,
                    'difficulty': knowledge_item.difficulty,
                    'quantity': item.quantity,
                    'is_paired': is_paired,
                    'paired_title': paired_title,
                    'tags': knowledge_item.tags or [],
                    'domain': knowledge_item.domain or '',
                    'depth': knowledge_item.depth or 'basic',
                    'mastery': knowledge_item.mastery or 0.0,
                })

        return jsonify({'items': result})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 8. POST /api/plant - 种植
@app.route('/api/plant', methods=['POST'])
def plant_seed():
    """将背包中的种子种植到空闲地块"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')
        user_id = DEMO_USER_ID

        # 检查背包中是否有该物品
        backpack_item = BackpackItem.query.filter_by(
            user_id=user_id,
            item_id=item_id
        ).first()

        if not backpack_item or backpack_item.quantity <= 0:
            return jsonify({'error': 'Item not in backpack'}), 400

        # 查找第一个空闲地块
        empty_plot = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.is_(None)
        ).order_by(Plot.id).first()

        total_plots = Plot.query.filter_by(user_id=user_id).count()
        occupied_plots = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.isnot(None)
        ).count()
        empty_plots = total_plots - occupied_plots
        logger.debug(
            "[plant] user=%d Total=%d, Occupied=%d, Empty=%d",
            user_id, total_plots, occupied_plots, empty_plots,
        )

        if not empty_plot:
            return jsonify({
                'error': f'农场上限{total_plots}块，已用{occupied_plots}块，无空闲地块',
                'debug': {'total': total_plots, 'occupied': occupied_plots, 'empty': 0},
            }), 400

        empty_plot.item_id = item_id
        empty_plot.growth_value = 0
        empty_plot.is_harvestable = False
        empty_plot.crop_variant = 'normal'
        empty_plot.planted_at = datetime.utcnow()

        # 减少背包数量
        backpack_item.quantity -= 1
        if backpack_item.quantity <= 0:
            db.session.delete(backpack_item)

        db.session.commit()

        return jsonify({'status': 'ok', 'plot_id': empty_plot.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 9. POST /api/water_submit - 浇水提交
@app.route('/api/water_submit', methods=['POST'])
def submit_water_answer():
    """提交浇水答案，更新成长值和掌握度"""
    try:
        data = request.get_json()
        plot_id = data.get('plot_id')
        answer = data.get('answer')
        verify_type = data.get('verify_type', 'recite')
        print(f"[DIAG] /api/water_submit: plot_id={plot_id}, verify_type={verify_type}, answer_preview={str(answer)[:80] if answer else 'None'}")

        # 获取地块
        plot = Plot.query.get(plot_id)
        if not plot:
            return jsonify({'error': 'Plot not found'}), 400

        if plot.item_id is None:
            return jsonify({'error': 'No plant in this plot'}), 400

        # 获取知识点
        knowledge_item = KnowledgeItem.query.get(plot.item_id)
        if not knowledge_item:
            return jsonify({'error': 'Knowledge item not found'}), 400

        result_data = {
            'score': 0,
            'growth_increase': 0,
            'mastery_change': 0,
            'feedback': None,
            'paired_growth': None
        }

        if knowledge_item.type == 'fact':
            is_remembered = answer and answer.strip() == "记得"
            score = 100.0 if is_remembered else 30.0
            growth_increase = 20 if is_remembered else 10

            old_mastery = knowledge_item.mastery or 0.0
            if is_remembered:
                knowledge_item.mastery = old_mastery + (1.0 - old_mastery) * 0.25
                knowledge_item.srs_level += 1
                days_to_next = 2 ** (knowledge_item.srs_level + 1) - 1
                if days_to_next < 1:
                    days_to_next = 1
            else:
                knowledge_item.mastery = max(0.0, old_mastery - old_mastery * 0.2)
                knowledge_item.srs_level = max(0, knowledge_item.srs_level - 1)
                days_to_next = 1

            knowledge_item.next_review_at = datetime.utcnow() + timedelta(days=days_to_next)
            result_data['score'] = score
            result_data['growth_increase'] = growth_increase
            result_data['mastery_change'] = round(knowledge_item.mastery - old_mastery, 4)
            result_data['feedback'] = None

        elif knowledge_item.type == 'concept':
            try:
                evaluation = ai_evaluate_concept_answer(knowledge_item, verify_type, answer)
                score = evaluation.get('score', 0.6)
            except Exception as eval_err:
                logging.warning("AI评估失败，使用默认分数: %s", eval_err)
                score = 0.6
                evaluation = {
                    'score': 0.6,
                    'feedback': {
                        'correct_parts': [], 'missing_parts': ['评估暂不可用'],
                        'mistakes': [], 'correct_derivation': '', 'reference_answer': '',
                        'further_study': [], 'summary': 'AI评估暂时不可用，已给予默认分数。你的回答已记录',
                        'error_type': None,
                    },
                }

            growth_increase = int(score * 30)

            # 检查是否是配对知识点
            is_paired = knowledge_item.paired_with_id is not None

            if plot.crop_variant == 'error':
                if score >= 0.4:
                    plot.error_plot_correct += 1
                    if plot.error_plot_correct >= 2:
                        plot.is_harvestable = True
                        plot.growth_value = 100
                else:
                    plot.error_plot_correct = 0
            else:
                old_mastery = knowledge_item.mastery
                knowledge_item.mastery = knowledge_item.mastery + (score - knowledge_item.mastery) * 0.3
                if knowledge_item.mastery > 1.0:
                    knowledge_item.mastery = 1.0
                elif knowledge_item.mastery < 0:
                    knowledge_item.mastery = 0.0
                result_data['mastery_change'] = knowledge_item.mastery - old_mastery

                # 如果有配对关系，同时更新配对知识点的掌握度
                if is_paired:
                    paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
                    if paired_item:
                        old_paired_mastery = paired_item.mastery
                        paired_item.mastery = paired_item.mastery + (score - paired_item.mastery) * 0.3
                        if paired_item.mastery > 1.0:
                            paired_item.mastery = 1.0
                        elif paired_item.mastery < 0:
                            paired_item.mastery = 0.0

            result_data['score'] = score
            result_data['growth_increase'] = growth_increase
            result_data['feedback'] = evaluation.get('feedback', None)

        # 更新成长值
        plot.growth_value += growth_increase
        if plot.growth_value > 100:
            plot.growth_value = 100

        # 如果是配对知识点，同时更新配对知识点所在地块的成长值
        if knowledge_item.paired_with_id:
            paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
            if paired_item:
                # 找到配对知识点所在的所有地块
                paired_plots = Plot.query.filter_by(
                    user_id=DEMO_USER_ID,
                    item_id=paired_item.id
                ).all()

                for p_plot in paired_plots:
                    if p_plot.id != plot.id:  # 跳过当前地块
                        p_plot.growth_value += growth_increase
                        if p_plot.growth_value > 100:
                            p_plot.growth_value = 100

                        # 检查配对地块是否可收获
                        if paired_item.type == 'fact':
                            p_plot.is_harvestable = p_plot.growth_value >= 100
                        elif paired_item.type == 'concept':
                            p_plot.is_harvestable = p_plot.growth_value >= 100 and paired_item.mastery >= 0.8

                    result_data['paired_growth'] = {
                        'item_id': paired_item.id,
                        'title': paired_item.title,
                        'growth_increase': growth_increase
                    }

        # 检查是否可收获
        if knowledge_item.type == 'fact':
            plot.is_harvestable = (plot.growth_value >= 100 and
                                   knowledge_item.mastery >= 0.6)
        elif knowledge_item.type == 'concept':
            if plot.crop_variant != 'error':
                plot.is_harvestable = plot.growth_value >= 100 and knowledge_item.mastery >= 0.8

        # 低分时创建错误变体地块
        if knowledge_item.type == 'concept' and score < 0.4:
            user_id = DEMO_USER_ID
            existing_error = Plot.query.filter_by(
                user_id=user_id,
                item_id=knowledge_item.id,
                crop_variant='error'
            ).first()

            if not existing_error:
                empty_plot = Plot.query.filter(
                    Plot.user_id == user_id,
                    Plot.item_id.is_(None)
                ).first()

                if empty_plot:
                    empty_plot.item_id = knowledge_item.id
                    empty_plot.growth_value = 0
                    empty_plot.is_harvestable = False
                    empty_plot.crop_variant = 'error'
                    empty_plot.planted_at = datetime.utcnow()
                    empty_plot.error_plot_correct = 0

        study = StudySession(
            user_id=DEMO_USER_ID,
            item_id=knowledge_item.id,
            verify_type=verify_type if knowledge_item.type == 'concept' else 'recite',
            score=score / 100.0 if knowledge_item.type == 'fact' else score,
        )
        db.session.add(study)

        db.session.commit()

        error_type = None
        assistant_tip = None

        if isinstance(result_data.get('feedback'), dict):
            error_type = result_data['feedback'].get('error_type')

        if knowledge_item.type == 'concept' and score < 0.5:
            recent_sessions = StudySession.query.filter_by(
                user_id=DEMO_USER_ID,
                item_id=knowledge_item.id
            ).order_by(StudySession.created_at.desc()).limit(5).all()

            recent_low_scores = [s for s in recent_sessions if (s.score or 0) < 0.5]
            if len(recent_low_scores) >= 2:
                assistant_tip = "需要我换个角度解释「" + knowledge_item.title + "」吗？连续答错说明可能需要不同的理解方式。"
                prereq = knowledge_item.prerequisite_ids
                if isinstance(prereq, list) and len(prereq) > 0:
                    assistant_tip += " 也可以先复习相关前置知识点。"

        response = {
            'score': result_data['score'],
            'growth': plot.growth_value,
            'growth_increase': growth_increase,
            'harvestable': plot.is_harvestable,
            'new_mastery': knowledge_item.mastery,
            'feedback': result_data['feedback'],
            'reference_answer': None,
            'paired_growth': result_data['paired_growth'],
            'error_type': error_type,
            'assistant_tip': assistant_tip,
        }

        if isinstance(result_data['feedback'], dict):
            response['reference_answer'] = result_data['feedback'].get('reference_answer', None)
        elif knowledge_item.type == 'fact':
            response['reference_answer'] = knowledge_item.content

        return jsonify(response)

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 10. POST /api/finish_learning/<id> - 完成学习
@app.route('/api/finish_learning/<int:plot_id>', methods=['POST'])
def finish_learning(plot_id: int):
    """完成一次浇水学习，更新复习时间"""
    try:
        data = request.get_json()
        understood = data.get('understood', True)

        plot = Plot.query.get(plot_id)
        if not plot or not plot.item_id:
            return jsonify({'error': 'Plot not found or empty'}), 400

        knowledge_item = KnowledgeItem.query.get(plot.item_id)
        if knowledge_item:
            if understood:
                knowledge_item.srs_level += 1
            else:
                knowledge_item.srs_level = max(0, knowledge_item.srs_level - 1)

            days_to_next = 2 ** (knowledge_item.srs_level + 1) - 1
            if days_to_next < 1:
                days_to_next = 1
            knowledge_item.next_review_at = datetime.utcnow() + timedelta(days=days_to_next)

            # fact类型知识点：用户确认理解后增加成长值
            if knowledge_item.type == 'fact' and understood:
                plot.growth_value = (plot.growth_value or 0) + 20
                if plot.growth_value > 100:
                    plot.growth_value = 100
                plot.is_harvestable = plot.growth_value >= 100 and knowledge_item.mastery >= 0.6
                logger.info("finish_learning: fact类型增长, plot=%d, growth=%d, harvestable=%s", plot_id, plot.growth_value, plot.is_harvestable)

        db.session.commit()

        return jsonify({
            'status': 'ok',
            'plot_id': plot_id,
            'growth': plot.growth_value,
            'next_review_at': knowledge_item.next_review_at.isoformat() if knowledge_item else None,
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 11. POST /api/pair - 配对
@app.route('/api/pair', methods=['POST'])
def pair_concepts():
    """建立两个知识点之间的配对关系"""
    try:
        data = request.get_json()
        item_id1 = data.get('item_id1')
        item_id2 = data.get('item_id2')

        if not item_id1 or not item_id2:
            return jsonify({'error': 'Both item IDs are required'}), 400

        if item_id1 == item_id2:
            return jsonify({'error': 'Cannot pair an item with itself'}), 400

        item1 = KnowledgeItem.query.get(item_id1)
        item2 = KnowledgeItem.query.get(item_id2)

        if not item1 or not item2:
            return jsonify({'error': 'One or both items not found'}), 404

        # 检查是否已配对
        if item1.paired_with_id or item2.paired_with_id:
            return jsonify({'error': 'One or both items are already paired'}), 400

        # 建立双向配对关系
        item1.paired_with_id = item_id2
        item2.paired_with_id = item_id1
        item1.paired_at = datetime.utcnow()
        item2.paired_at = datetime.utcnow()

        db.session.commit()

        return jsonify({
            'status': 'ok',
            'message': f'已将 "{item1.title}" 和 "{item2.title}" 配对'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 12. POST /api/unpair - 解除配对
@app.route('/api/unpair', methods=['POST'])
def unpair_concepts():
    """解除知识点的配对关系"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')

        if not item_id:
            return jsonify({'error': 'Item ID is required'}), 400

        item = KnowledgeItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Item not found'}), 404

        if not item.paired_with_id:
            return jsonify({'error': 'Item is not paired'}), 400

        # 找到配对的另一个知识点并解除配对
        paired_item = KnowledgeItem.query.get(item.paired_with_id)

        item.paired_with_id = None
        item.paired_at = None

        if paired_item:
            paired_item.paired_with_id = None
            paired_item.paired_at = None

        db.session.commit()

        return jsonify({
            'status': 'ok',
            'message': '配对已解除'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 13. POST /api/coding_challenge - 编程挑战
@app.route('/api/coding_challenge', methods=['POST'])
def coding_challenge():
    """获取编程挑战题目"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')

        if not item_id:
            return jsonify({'error': 'item_id is required'}), 400

        knowledge_item = KnowledgeItem.query.get(item_id)
        if not knowledge_item:
            return jsonify({'error': 'Knowledge item not found'}), 404

        question = generate_coding_question(knowledge_item)

        return jsonify({
            'type': 'coding',
            'question': question,
            'language': 'python',
            'verify_type': 'coding'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 14. POST /api/evaluate_code - 评估代码
@app.route('/api/evaluate_code', methods=['POST'])
def evaluate_code():
    """评估用户提交的编程代码"""
    try:
        data = request.get_json()
        problem = data.get('problem', '')
        code = data.get('code', '')

        if not code:
            return jsonify({'error': 'Code is required'}), 400

        result = evaluate_coding_code(problem, code)

        return jsonify({
            'score': result['score'],
            'feedback': result['feedback'],
            'suggestion': result.get('suggestion', ''),
            'growth_increment': result['growth_increment']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 15. POST /api/pair_challenge - 配对挑战
@app.route('/api/pair_challenge', methods=['POST'])
def pair_challenge():
    """配对知识点挑战 - 比较两个配对知识点的异同"""
    try:
        data = request.get_json()
        item_id = data.get('item_id')

        if not item_id:
            return jsonify({'error': 'item_id is required'}), 400

        knowledge_item = KnowledgeItem.query.get(item_id)
        if not knowledge_item:
            return jsonify({'error': 'Knowledge item not found'}), 404

        if not knowledge_item.paired_with_id:
            return jsonify({'error': 'This item is not paired'}), 400

        paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
        if not paired_item:
            return jsonify({'error': 'Paired item not found'}), 404

        question = f'请比较「{knowledge_item.title}」和「{paired_item.title}」的异同，并说明各自适用场景'

        return jsonify({
            'type': 'concept_verify',
            'question': question,
            'verify_type': 'compare',
            'paired_item_id': paired_item.id,
            'paired_title': paired_item.title
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 16. POST /api/ask_assistant - AI助手
@app.route('/api/ask_assistant', methods=['POST'])
def ask_assistant():
    """向AI助手提问"""
    try:
        data = request.get_json()
        question = data.get('question', '')

        if not question or len(question.strip()) == 0:
            return jsonify({'error': '问题内容不能为空'}), 400

        # 获取当前学习的相关知识点
        user_id = DEMO_USER_ID
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()
        related_items = [
            {'id': item.id, 'title': item.title, 'content': item.content}
            for item in items[:5]
        ]

        # 评估和回答
        result = evaluate_and_answer_question(question, related_items)

        return jsonify(result)

    except Exception as e:
        logger.error("ask_assistant 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 17. POST /api/evaluate_question - 评估问题
@app.route('/api/evaluate_question', methods=['POST'])
def evaluate_question():
    """评估用户提问的质量并给出回答"""
    try:
        data = request.get_json()
        question = data.get('question', '')

        if not question or len(question.strip()) == 0:
            return jsonify({'error': '问题内容不能为空'}), 400

        # 获取相关知识点
        user_id = DEMO_USER_ID
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()
        related_items = [
            {'id': item.id, 'title': item.title, 'content': item.content}
            for item in items[:5]
        ]

        result = evaluate_and_answer_question(question, related_items)

        return jsonify(result)

    except Exception as e:
        logger.error("evaluate_question 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 18. GET /api/review_plan - 复习计划
@app.route('/api/review_plan', methods=['GET'])
def get_review_plan():
    """获取今天需要复习的知识点列表"""
    try:
        user_id = DEMO_USER_ID
        now = datetime.utcnow()
        due_items = KnowledgeItem.query.filter(
            KnowledgeItem.user_id == user_id,
            KnowledgeItem.next_review_at <= now
        ).all()

        result = []
        for item in due_items:
            plots = Plot.query.filter_by(user_id=user_id, item_id=item.id).all()
            for plot in plots:
                result.append({
                    'plot_id': plot.id,
                    'title': item.title,
                    'type': item.type,
                    'depth': item.depth or 'basic',
                    'mastery': round(item.mastery * 100),
                    'growth': plot.growth_value,
                    'overdue_days': max(0, (now - (item.next_review_at or now)).days)
                })

        return jsonify({'due_items': result, 'total': len(result)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 19. GET /api/learning_stats - 学习统计
@app.route('/api/learning_stats', methods=['GET'])
def get_learning_stats():
    """获取学习统计信息"""
    try:
        user_id = DEMO_USER_ID

        # 获取所有知识点
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()

        total_items = len(items)
        total_mastery = sum(item.mastery for item in items) if items else 0
        avg_mastery = total_mastery / total_items if total_items > 0 else 0

        # 根据掌握度计算等级
        if avg_mastery >= 0.8:
            level = '博士'
        elif avg_mastery >= 0.6:
            level = '硕士'
        elif avg_mastery >= 0.4:
            level = '学士'
        elif avg_mastery >= 0.2:
            level = '学徒'
        else:
            level = '初学'

        return jsonify({
            'level': level,
            'total_mastery': round(avg_mastery * 100, 1),
            'learned_items': total_items
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 20. GET /api/available_topics - 可用专题
@app.route('/api/available_topics', methods=['GET'])
def get_available_topics():
    """获取有3个以上知识点的专题标签"""
    try:
        user_id = DEMO_USER_ID

        # 获取所有用户知识点
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()

        # 统计标签出现次数
        tag_counts = {}
        for item in items:
            for tag in (item.tags or []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # 筛选有3个以上知识点的标签
        available_topics = []
        for tag, count in tag_counts.items():
            if count >= 2:
                # 获取该标签相关的知识
                related_items = [
                    {'id': item.id, 'title': item.title, 'content': item.content}
                    for item in items
                    if tag in (item.tags or [])
                ]
                available_topics.append({
                    'tag': tag,
                    'count': count,
                    'related_items': related_items
                })

        return jsonify({
            'available_topics': available_topics
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 21. POST /api/generate_summary - 生成专题总结
@app.route('/api/generate_summary', methods=['POST'])
def generate_summary():
    """为有3个以上知识点的标签生成专题总结"""
    try:
        data = request.get_json()
        tags = data.get('tags', [])
        user_id = DEMO_USER_ID

        # 获取相关知识点
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()
        related_items = []
        for item in items:
            # 检查是否包含任一标签
            for tag in tags:
                if tag in (item.tags or []):
                    related_items.append({
                        'id': item.id,
                        'title': item.title,
                        'content': item.content
                    })
                    break

        if len(related_items) < 3:
            return jsonify({'error': '该标签下知识点不足'}), 400

        # 生成总结
        summary = generate_topic_summary(tags, related_items)

        return jsonify({
            'summary': summary,
            'tags': tags,
            'item_count': len(related_items)
        })

    except Exception as e:
        logger.error("生成专题总结失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 22. GET /api/knowledge_graph - 知识图谱
@app.route('/api/knowledge_graph', methods=['GET'])
def get_knowledge_graph():
    """获取知识图谱数据用于可视化"""
    try:
        user_id = DEMO_USER_ID

        # 获取所有知识点
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()

        # 构建节点列表
        nodes = []
        for item in items:
            nodes.append({
                'id': item.id,
                'title': item.title,
                'content': item.content,
                'mastery': item.mastery,
                'depth': item.depth,
                'tags': item.tags or [],
                'type': item.type
            })

        # 计算标签共现频率（构建连线）
        tag_cooccurrence = {}
        for i, item1 in enumerate(items):
            tags1 = set(item1.tags or [])
            for j in range(i + 1, len(items)):
                item2 = items[j]
                tags2 = set(item2.tags or [])
                common_tags = tags1.intersection(tags2)
                if len(common_tags) > 0:
                    key = tuple(sorted([item1.id, item2.id]))
                    tag_cooccurrence[key] = tag_cooccurrence.get(key, 0) + len(common_tags)

        # 构建连线列表
        links = []
        for (id1, id2), weight in tag_cooccurrence.items():
            links.append({
                'source': id1,
                'target': id2,
                'weight': weight
            })

        # 获取所有标签及其出现次数
        tag_counts = {}
        for item in items:
            for tag in (item.tags or []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        return jsonify({
            'nodes': nodes,
            'links': links,
            'tag_counts': tag_counts
        })

    except Exception as e:
        logger.error("获取知识图谱数据失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 23. POST /api/import_content - B站导入
@app.route('/api/import_content', methods=['POST'])
def import_content():
    """从B站视频导入学习内容"""
    try:
        data = request.get_json()
        source_url = data.get('source_url', '').strip()
        learning_mode = data.get('learning_mode', 'normal')
        logger.info("[DEBUG] /api/import_content called, source_url=%s, mode=%s", source_url[:50], learning_mode)
        print(f"[DIAG] /api/import_content called, source_url={source_url[:80]}, mode={learning_mode}")

        if not source_url:
            return jsonify({'error': '请提供视频链接'}), 400

        if learning_mode not in ('sprint', 'normal'):
            learning_mode = 'normal'

        use_fallback = os.getenv('USE_FALLBACK', 'True').lower() == 'true'
        print(f"[DIAG] /api/import_content: use_fallback={use_fallback} (from os.getenv directly)")

        if use_fallback:
            bilibili_data = mock_bilibili_import(source_url)
        else:
            import time as _time
            max_retries = 2
            bilibili_data = None
            for attempt in range(max_retries + 1):
                try:
                    bilibili_data = get_video_full_text(source_url)
                    if isinstance(bilibili_data, dict) and 'error' not in bilibili_data and bilibili_data.get('full_text', '').strip():
                        if attempt > 0:
                            logger.info("import_content: 第%d次重试成功", attempt)
                        break
                    if attempt < max_retries:
                        logger.warning("import_content: 第%d次尝试失败，0.5秒后重试", attempt + 1)
                        _time.sleep(0.5)
                except Exception as bili_err:
                    logger.error("get_video_full_text 第%d次异常: %s", attempt + 1, bili_err)
                    if attempt < max_retries:
                        _time.sleep(0.5)
                    else:
                        bilibili_data = {"error": f"获取B站视频信息失败: {str(bili_err)}"}

            if not isinstance(bilibili_data, dict):
                bilibili_data = {"error": "B站视频数据格式异常，请检查链接或重试"}

        video_info = bilibili_data.get('video_info', {})
        video_title = video_info.get('title', '未知视频')

        # 降级处理：当所有重试都失败时，尝试使用标题+简介降级
        if 'error' in bilibili_data:
            logger.warning("import_content: 所有重试均失败，尝试标题简介降级, video=%s", video_title)
            desc = video_info.get('description', '')
            if desc:
                full_text = f"视频标题：{video_title}\n\n视频简介：{desc}"
                bilibili_data = {
                    "video_info": video_info,
                    "full_text": full_text,
                    "source": "description_fallback",
                }
                logger.info("import_content: 已使用标题简介作为降级文本, len=%d", len(full_text))
            else:
                return jsonify({
                    'warning': True,
                    'error': f'视频 "{video_title}" 无可用CC字幕且无简介。请尝试手动粘贴对话文本到输入框进行知识点提取。',
                    'video_info': video_info,
                }), 400

        full_text = bilibili_data.get('full_text', '')

        if not full_text or len(full_text.strip()) < 20:
            logger.warning("import_content: 视频内容过短或为空, video=%s, 尝试使用标题简介降级", video_title)
            desc = video_info.get('description', '')
            if desc:
                full_text = f"视频标题：{video_title}\n\n视频简介：{desc}"
                logger.info("import_content: 已使用标题简介作为降级文本, len=%d", len(full_text))
            else:
                return jsonify({
                    'warning': True,
                    'error': f'视频 "{video_title}" 无可用CC字幕且无简介。请尝试手动粘贴对话文本到输入框进行知识点提取。',
                    'video_info': video_info,
                }), 400

        # 文本长度上限控制：字幕过长时优先摘要压缩，失败则截断
        if len(full_text) > MAX_PROMPT_LEN:
            if len(full_text) > SUMMARY_THRESHOLD and ENABLE_SUMMARY_COMPRESS:
                logger.info("import_content: 字幕过长(%d)，尝试摘要压缩", len(full_text))
                full_text = summarize_long_text(full_text, target_length=800)
            if len(full_text) > MAX_PROMPT_LEN:
                logger.warning("import_content: 字幕过长(%d)，已截断至%d字符", len(full_text), MAX_PROMPT_LEN)
                full_text = full_text[:MAX_PROMPT_LEN]

        try:
            structured = structure_video_content(full_text, video_title)
        except Exception as ai_err:
            logger.error("import_content: AI结构化视频内容失败: %s\n%s", ai_err, traceback.format_exc())
            return jsonify({'error': f'AI分析视频内容失败: {str(ai_err)}。请稍后重试或手动粘贴对话文本。'}), 500

        if not structured or not structured.get('knowledge_points'):
            logger.warning("import_content: AI未能提取出知识点, video=%s", video_title)
            return jsonify({
                'video_info': video_info,
                'knowledge_points': [],
                'saved_items': [],
                'saved_backpack': [],
                'warning': True,
                'warning_text': f'未能从视频 "{video_title}" 中提取知识点。视频内容可能过于概括或与学习主题无关。',
            })

        user_id = DEMO_USER_ID

        knowledge_points = structured.get('knowledge_points', [])

        if learning_mode == 'sprint':
            knowledge_points = knowledge_points[:5]

        saved_items = []
        saved_backpack = []

        for point in knowledge_points:
            item_type = point.get('type', 'concept')
            title = point.get('title', '').strip()
            content = point.get('content', '').strip()

            if not title and content:
                title = content[:50].rsplit('，', 1)[0].rsplit('。', 1)[0] or content[:50]
            if not title:
                continue
            if not content:
                content = title

            item = KnowledgeItem(
                user_id=user_id,
                title=title,
                content=content,
                type=item_type if item_type in ('fact', 'concept') else 'concept',
                difficulty=point.get('difficulty', 2),
                tags=point.get('tags', []),
                domain=point.get('domain', '通用'),
                depth=point.get('depth', 'basic'),
            )
            db.session.add(item)
            db.session.flush()

            bp_item = BackpackItem(
                user_id=user_id,
                item_id=item.id,
                quantity=1
            )
            db.session.add(bp_item)

            logger.info("[import_content] 知识点已保存: title=%s, id=%d, mode=%s",
                        item.title, item.id, learning_mode)

            plot_id = None
            if learning_mode != 'sprint':
                empty_plot = Plot.query.filter(
                    Plot.user_id == user_id,
                    Plot.item_id.is_(None)
                ).order_by(Plot.id).first()

                total_plots = Plot.query.filter_by(user_id=user_id).count()
                occupied_plots = Plot.query.filter(
                    Plot.user_id == user_id,
                    Plot.item_id.isnot(None)
                ).count()
                empty_plots = total_plots - occupied_plots
                logger.debug(
                    "[import_content] user=%d Total=%d, Occupied=%d, Empty=%d",
                    user_id, total_plots, occupied_plots, empty_plots,
                )
                if empty_plot:
                    empty_plot.item_id = item.id
                    empty_plot.growth_value = 0
                    empty_plot.is_harvestable = False
                    empty_plot.planted_at = datetime.utcnow()
                    plot_id = empty_plot.id
                    logger.info("[import_content] 自动种植成功: title=%s -> plot=%d", item.title, plot_id)
                else:
                    logger.warning("[import_content] 无空闲地块，跳过自动种植: title=%s", item.title)

            saved_items.append({
                'id': item.id,
                'title': item.title,
                'type': item.type,
                'timestamp': point.get('timestamp', ''),
                'plot_id': plot_id,
            })
            saved_backpack.append({
                'item_id': item.id,
                'title': item.title,
                'type': item.type,
                'quantity': 1,
            })

        db.session.commit()

        planted_count = sum(1 for s in saved_items if s.get('plot_id'))
        total_count = len(saved_items)
        warning_msg = None

        if learning_mode == 'sprint':
            logger.info("[import_content] Sprint模式完成: 共%d个知识点已存入背包，等待用户手动种植", total_count)
            return jsonify({
                'learning_mode': 'sprint',
                'video_info': {
                    'title': video_title,
                    'owner': video_info.get('owner', ''),
                    'duration': video_info.get('duration', 0),
                    'bvid': video_info.get('bvid', ''),
                },
                'source': bilibili_data.get('source', ''),
                'summary': structured.get('summary', ''),
                'knowledge_points': [],
                'timestamp_index': (structured.get('timestamp_index', []) or [])[:5],
                'qa_pairs': structured.get('qa_pairs', []),
                'saved_items': saved_items,
                'saved_backpack': saved_backpack,
                'planted_count': 0,
                'total_count': total_count,
                'message': f'已保存 {total_count} 个知识点到背包，请从背包手动种植',
            })

        if planted_count < total_count:
            no_plot_items = [s['title'] for s in saved_items if not s.get('plot_id')]
            total_plots = Plot.query.filter_by(user_id=user_id).count()
            occupied_plots = Plot.query.filter(
                Plot.user_id == user_id,
                Plot.item_id.isnot(None)
            ).count()
            warning_msg = f'农场上限{total_plots}块，已用{occupied_plots}块，无空闲地块。未种植: ' + '、'.join(no_plot_items)

        return jsonify({
            'learning_mode': learning_mode,
            'video_info': {
                'title': video_title,
                'owner': video_info.get('owner', ''),
                'duration': video_info.get('duration', 0),
                'bvid': video_info.get('bvid', ''),
            },
            'source': bilibili_data.get('source', ''),
            'summary': structured.get('summary', ''),
            'knowledge_points': knowledge_points,
            'timestamp_index': structured.get('timestamp_index', []),
            'qa_pairs': structured.get('qa_pairs', []),
            'saved_items': saved_items,
            'saved_backpack': saved_backpack,
            'warning': warning_msg,
            'planted_count': planted_count,
            'total_count': total_count,
        })

    except Exception as e:
        db.session.rollback()
        logging.error("import_content 失败: %s\n%s", e, traceback.format_exc())
        print("[DIAG] import_content EXCEPTION:", traceback.format_exc())
        return jsonify({'error': f'导入失败: {str(e)}. 该视频可能无CC字幕或内容格式异常。请尝试手动粘贴对话文本。'}), 500


# 24. GET /api/card/<id> - 知识卡片
@app.route('/api/card/<int:item_id>', methods=['GET'])
def get_card(item_id: int):
    """获取知识卡片的结构化数据"""
    try:
        item = KnowledgeItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Knowledge item not found'}), 404

        mastery_pct = round(item.mastery * 100)

        if mastery_pct >= 80:
            quote = "你已超越80%的学习者，继续加油！"
        elif mastery_pct >= 60:
            quote = "坚持就是胜利，你正在进步！"
        elif mastery_pct >= 40:
            quote = "每一步都在积累，未来可期！"
        else:
            quote = "知识的种子已经播下，静待花开！"

        stars = "★" * min(5, max(1, round(mastery_pct / 20))) + "☆" * (5 - min(5, max(1, round(mastery_pct / 20))))

        card_data = {
            'title': item.title or '知识',
            'content': item.content[:120] if item.content else '',
            'type': item.type or 'concept',
            'mastery': mastery_pct,
            'stars': stars,
            'domain': item.domain or '通用',
            'depth': item.depth or 'basic',
            'tags': item.tags[:5] if item.tags else [],
            'quote': quote,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'difficulty': item.difficulty or 2,
            'formula': item.formula or '',
            'derivation_steps': item.derivation_steps if isinstance(item.derivation_steps, list) else [],
            'common_mistakes': item.common_mistakes if isinstance(item.common_mistakes, list) else [],
            'application_examples': item.application_examples if isinstance(item.application_examples, list) else [],
        }

        return jsonify({'card': card_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# 25. POST /api/auto_plant - 自动种植
@app.route('/api/auto_plant', methods=['POST'])
def auto_plant():
    """自动种植：将背包第一个可用种子种到第一个空闲地块"""
    try:
        user_id = DEMO_USER_ID

        backpack_items = BackpackItem.query.filter(
            BackpackItem.user_id == user_id,
            BackpackItem.quantity > 0
        ).order_by(BackpackItem.id).all()

        if not backpack_items:
            return jsonify({'status': 'empty', 'message': '背包中没有种子'}), 200

        empty_plot = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.is_(None)
        ).order_by(Plot.id).first()

        total_plots = Plot.query.filter_by(user_id=user_id).count()
        occupied_plots = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.isnot(None)
        ).count()
        empty_plots = total_plots - occupied_plots
        logger.debug(
            "[auto_plant] user=%d Total=%d, Occupied=%d, Empty=%d",
            user_id, total_plots, occupied_plots, empty_plots,
        )

        if not empty_plot:
            return jsonify({
                'status': 'full',
                'message': f'农场上限{total_plots}块，已用{occupied_plots}块，无空闲地块',
                'debug': {'total': total_plots, 'occupied': occupied_plots, 'empty': 0},
            }), 200

        first_seed = backpack_items[0]
        knowledge_item = KnowledgeItem.query.get(first_seed.item_id)

        empty_plot.item_id = first_seed.item_id
        empty_plot.growth_value = 0
        empty_plot.is_harvestable = False
        empty_plot.crop_variant = 'normal'
        empty_plot.planted_at = datetime.utcnow()

        first_seed.quantity -= 1
        if first_seed.quantity <= 0:
            db.session.delete(first_seed)

        db.session.commit()

        return jsonify({
            'status': 'ok',
            'plot_id': empty_plot.id,
            'title': knowledge_item.title if knowledge_item else '未知',
            'remaining_backpack': [{
                'id': bi.item_id,
                'title': KnowledgeItem.query.get(bi.item_id).title if KnowledgeItem.query.get(bi.item_id) else '',
                'quantity': bi.quantity
            } for bi in BackpackItem.query.filter_by(user_id=user_id).all() if bi.quantity > 0]
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 26. POST /api/harvest - 收获
@app.route('/api/harvest', methods=['POST'])
def harvest_plot():
    """收获成熟的地块并获得果实奖励"""
    try:
        data = request.get_json()
        plot_id = data.get('plot_id')
        logger.info("[harvest] 收到收获请求: plot_id=%s", plot_id)

        if not plot_id:
            logger.warning("[harvest] 缺少 plot_id")
            return jsonify({'error': 'plot_id is required'}), 400

        plot = Plot.query.get(plot_id)
        if not plot:
            logger.warning("[harvest] 地块不存在: plot_id=%s", plot_id)
            return jsonify({'error': 'Plot not found'}), 400

        knowledge_item = KnowledgeItem.query.get(plot.item_id) if plot.item_id else None

        logger.info(
            "[harvest] 地块状态: plot_id=%d, item_id=%s, growth=%d, "
            "harvestable=%s, variant=%s, item_type=%s, mastery=%.2f",
            plot.id, plot.item_id, plot.growth_value or 0,
            plot.is_harvestable, plot.crop_variant,
            knowledge_item.type if knowledge_item else 'N/A',
            knowledge_item.mastery if knowledge_item else 0.0,
        )

        if not plot.is_harvestable:
            reason_parts = []
            if not plot.item_id:
                reason_parts.append("地块为空")
            else:
                if (plot.growth_value or 0) < 100:
                    reason_parts.append(f"生长值不足({plot.growth_value or 0}/100)")
                if knowledge_item:
                    if knowledge_item.type == 'concept' and knowledge_item.mastery < 0.8:
                        reason_parts.append(f"掌握度不足({knowledge_item.mastery*100:.0f}%/80%)")
                    if knowledge_item.type == 'fact' and knowledge_item.mastery < 0.6:
                        reason_parts.append(f"掌握度不足({knowledge_item.mastery*100:.0f}%/60%)")
            reason = "，".join(reason_parts) if reason_parts else "未知原因"
            logger.warning("[harvest] 地块不可收获: plot_id=%d, 原因: %s", plot.id, reason)
            return jsonify({'error': f'地块不可收获：{reason}'}), 400

        if not knowledge_item:
            logger.warning("[harvest] 知识点不存在: item_id=%s", plot.item_id)
            return jsonify({'error': 'Associated knowledge item not found'}), 400

        actual_harvestable = False
        if knowledge_item.type == 'fact':
            actual_harvestable = (plot.growth_value or 0) >= 100 and knowledge_item.mastery >= 0.6
        elif knowledge_item.type == 'concept':
            actual_harvestable = (plot.growth_value or 0) >= 100 and knowledge_item.mastery >= 0.8

        if not actual_harvestable:
            plot.is_harvestable = False
            db.session.commit()
            reason_parts = []
            if (plot.growth_value or 0) < 100:
                reason_parts.append(f"生长值不足({plot.growth_value or 0}/100)")
            if knowledge_item.type == 'concept' and knowledge_item.mastery < 0.8:
                reason_parts.append(f"掌握度不足({knowledge_item.mastery*100:.0f}%/80%)")
            if knowledge_item.type == 'fact' and knowledge_item.mastery < 0.6:
                reason_parts.append(f"掌握度不足({knowledge_item.mastery*100:.0f}%/60%)")
            reason = "，".join(reason_parts) if reason_parts else "条件未满足"
            logger.warning(
                "[harvest] is_harvestable与实际条件不一致，已修正: plot_id=%d, mastery=%.2f, 原因: %s",
                plot.id, knowledge_item.mastery, reason,
            )
            return jsonify({'error': f'地块不可收获：{reason}'}), 400

        base_reward = int(1 + (knowledge_item.difficulty or 2) * 99)
        if base_reward < 1:
            base_reward = 50
        logger.info("[harvest] 奖励计算: title=%s, difficulty=%d, reward=%d",
                    knowledge_item.title, knowledge_item.difficulty, base_reward)

        if knowledge_item.paired_with_id:
            paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
            if paired_item:
                paired_item.mastery = min(1.0, paired_item.mastery + 0.1)
                logger.info("[harvest] 配对知识点掌握度提升: %s -> %.2f", paired_item.title, paired_item.mastery)

        fruit = Fruit(
            user_id=DEMO_USER_ID,
            item_id=knowledge_item.id,
            title=knowledge_item.title,
            value=base_reward
        )
        db.session.add(fruit)

        user = User.query.get(DEMO_USER_ID)
        user.knowledge_coins += base_reward

        plot.item_id = None
        plot.growth_value = 0
        plot.is_harvestable = False
        plot.crop_variant = 'normal'
        plot.planted_at = None
        plot.error_plot_correct = 0

        db.session.commit()

        logger.info("[harvest] 收获成功: plot_id=%d, title=%s, fruit=%d, coins=%d",
                    plot_id, knowledge_item.title, base_reward, user.knowledge_coins)

        return jsonify({
            'fruit_value': base_reward,
            'total_coins': user.knowledge_coins,
            'message': f'收获成功！「{knowledge_item.title}」产生 {base_reward} 金币果实'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# 27. POST /api/exam/start - 考试开始
@app.route('/api/exam/start', methods=['POST'])
def exam_start():
    """开始考试会话"""
    if not ENABLE_EXAM_MODE:
        return jsonify({'error': '考试模式未启用'}), 403

    try:
        data = request.get_json()
        tags = data.get('tags', [])
        count = min(int(data.get('count', 5)), 20)
        use_adaptive = data.get('use_adaptive', False)
        user_id = DEMO_USER_ID

        query = KnowledgeItem.query.filter_by(user_id=user_id)
        items = query.all()

        if tags:
            items = [item for item in items if any(t in (item.tags or []) for t in tags)]

        if not items:
            return jsonify({'error': '没有找到匹配的知识点，请先提取并种植知识点'}), 404

        selected = random.sample(items, min(count, len(items)))

        session = ExamSession(
            user_id=user_id,
            tags=tags,
            total_questions=len(selected),
        )
        db.session.add(session)
        db.session.flush()

        questions = []
        for item in selected:
            offset = 0.0
            if use_adaptive and ENABLE_ADAPTIVE:
                offset = item.difficulty_offset or 0.0

            try:
                result = generate_concept_question(item, verify_type='auto')
                if isinstance(result, dict):
                    question_text = result.get('question_text', result.get('question', ''))
                    if not question_text:
                        question_text = str(result)
                else:
                    question_text = str(result)
            except Exception:
                question_text = f"请解释「{item.title}」的核心概念和应用场景。"

            answer_record = ExamAnswer(
                session_id=session.id,
                knowledge_item_id=item.id,
                question_text=question_text,
                verify_type='auto',
            )
            db.session.add(answer_record)
            db.session.flush()

            questions.append({
                'id': answer_record.id,
                'text': question_text,
                'title': item.title,
                'type': item.type,
                'difficulty_offset': offset,
            })

        db.session.commit()
        return jsonify({
            'exam_id': session.id,
            'session_id': session.id,
            'questions': questions,
            'total': len(questions),
        })

    except Exception as e:
        db.session.rollback()
        logger.error("exam_start 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 28. POST /api/exam/submit - 考试提交
@app.route('/api/exam/submit', methods=['POST'])
def exam_submit():
    """提交考试答案"""
    if not ENABLE_EXAM_MODE:
        return jsonify({'error': '考试模式未启用'}), 403

    try:
        data = request.get_json()
        session_id = data.get('session_id')
        answers = data.get('answers', [])

        session = ExamSession.query.get(session_id)
        if not session:
            return jsonify({'error': '考试会话不存在'}), 404

        total_score = 0.0
        correct_count = 0

        for ans_data in answers:
            answer_id = ans_data.get('question_id')
            user_answer = ans_data.get('user_answer', '')

            answer_record = ExamAnswer.query.get(answer_id)
            if not answer_record or answer_record.session_id != session_id:
                continue

            item = KnowledgeItem.query.get(answer_record.knowledge_item_id)
            score = 0.0
            correct_answer = ''

            if item and user_answer.strip():
                try:
                    score = ai_evaluate_concept_answer(
                        item, answer_record.verify_type, user_answer
                    )
                    score = max(0.0, min(1.0, float(score)))
                except Exception:
                    score = 0.3

                correct_answer = item.content[:200] if item.content else ''

            answer_record.user_answer = user_answer
            answer_record.score = score
            answer_record.is_correct = score >= 0.6
            answer_record.correct_answer = correct_answer

            total_score += score
            if score >= 0.6:
                correct_count += 1

            study = StudySession(
                user_id=session.user_id,
                item_id=answer_record.knowledge_item_id,
                verify_type=answer_record.verify_type,
                score=score,
            )
            db.session.add(study)

        n = len(answers) if answers else 1
        session.correct_count = correct_count
        session.avg_score = total_score / n
        session.finished_at = datetime.utcnow()

        db.session.commit()

        correct_rate = correct_count / n if n > 0 else 0
        return jsonify({
            'session_id': session_id,
            'correct_rate': round(correct_rate, 3),
            'avg_score': round(session.avg_score, 3),
            'total_questions': session.total_questions,
            'correct_count': correct_count,
            'detail_url': f'/api/exam/result/{session_id}',
        })

    except Exception as e:
        db.session.rollback()
        logger.error("exam_submit 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 29. GET /api/exam/result/<id> - 考试结果
@app.route('/api/exam/result/<int:session_id>', methods=['GET'])
def exam_result(session_id: int):
    """获取考试结果详情"""
    if not ENABLE_EXAM_MODE:
        return jsonify({'error': '考试模式未启用'}), 403

    try:
        session = ExamSession.query.get(session_id)
        if not session:
            return jsonify({'error': '考试会话不存在'}), 404

        answers = ExamAnswer.query.filter_by(session_id=session_id).all()
        weak_points = []
        detail = []

        for a in answers:
            item = KnowledgeItem.query.get(a.knowledge_item_id) if a.knowledge_item_id else None
            detail.append({
                'question_id': a.id,
                'title': item.title if item else '未知',
                'question_text': a.question_text,
                'user_answer': a.user_answer,
                'score': round(a.score, 3),
                'is_correct': a.is_correct,
                'correct_answer': a.correct_answer,
                'verify_type': a.verify_type,
            })

            if a.score < 0.6 and item:
                weak_points.append({
                    'id': item.id,
                    'title': item.title,
                    'score': round(a.score, 3),
                    'mastery': item.mastery,
                })

        return jsonify({
            'session_id': session_id,
            'tags': session.tags,
            'total_questions': session.total_questions,
            'correct_count': session.correct_count,
            'avg_score': round(session.avg_score, 3),
            'correct_rate': round(session.correct_count / max(1, session.total_questions), 3),
            'created_at': session.created_at.isoformat() if session.created_at else None,
            'finished_at': session.finished_at.isoformat() if session.finished_at else None,
            'detail': detail,
            'weak_points': weak_points,
        })

    except Exception as e:
        logger.error("exam_result 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 30. GET /api/exam/history - 考试历史
@app.route('/api/exam/history', methods=['GET'])
def exam_history():
    """获取考试历史记录"""
    if not ENABLE_EXAM_MODE:
        return jsonify({'error': '考试模式未启用'}), 403

    try:
        user_id = DEMO_USER_ID
        sessions = ExamSession.query.filter_by(user_id=user_id).order_by(ExamSession.created_at.desc()).limit(20).all()
        result = []
        for s in sessions:
            result.append({
                'session_id': s.id,
                'tags': s.tags,
                'total_questions': s.total_questions,
                'correct_count': s.correct_count,
                'avg_score': round(s.avg_score, 3),
                'created_at': s.created_at.isoformat() if s.created_at else None,
            })
        return jsonify({'history': result})

    except Exception as e:
        logger.error("exam_history 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 31. GET /api/report/weekly - 周报
@app.route('/api/report/weekly', methods=['GET'])
def report_weekly():
    """获取每周学习报告，包含每日统计和薄弱知识点"""
    if not ENABLE_REPORT:
        return jsonify({'error': '学习报告未启用'}), 403

    try:
        user_id = DEMO_USER_ID
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        all_items = KnowledgeItem.query.filter_by(user_id=user_id).all()

        study_sessions = StudySession.query.filter(
            StudySession.user_id == user_id,
            StudySession.created_at >= week_ago,
        ).all()

        review_count = len(study_sessions)
        total_score = sum(s.score for s in study_sessions)
        avg_accuracy = total_score / review_count if review_count > 0 else 0.0

        new_knowledge_count = KnowledgeItem.query.filter(
            KnowledgeItem.user_id == user_id,
            KnowledgeItem.created_at >= week_ago,
        ).count()

        daily_timeline = []
        for i in range(7):
            day = week_ago + timedelta(days=i)
            day_end = day + timedelta(days=1)

            day_sessions = [s for s in study_sessions if day <= (s.created_at or day) < day_end]
            day_watering_count = len(day_sessions)

            day_new_items = [it for it in all_items if day <= (it.created_at or day) < day_end]
            day_new_count = len(day_new_items)

            day_avg_score = sum(s.score for s in day_sessions) / len(day_sessions) if day_sessions else 0.0

            day_avg_mastery = sum(it.mastery or 0.0 for it in all_items) / len(all_items) if all_items else 0.0

            daily_timeline.append({
                'date': day.strftime('%m-%d'),
                'watering_count': day_watering_count,
                'new_knowledge_count': day_new_count,
                'avg_score': round(day_avg_score, 3),
                'avg_mastery': round(day_avg_mastery, 3),
            })

        reviewed_item_ids = set()
        for s in study_sessions:
            if s.item_id:
                reviewed_item_ids.add(s.item_id)

        weak_items = [it for it in all_items if it.id in reviewed_item_ids]
        weak_items.sort(key=lambda x: x.mastery or 0.0)
        weak_points = [
            {'id': it.id, 'title': it.title, 'mastery': round(it.mastery or 0.0, 3), 'type': it.type}
            for it in weak_items[:5]
        ]

        now_utc = now
        recommended = KnowledgeItem.query.filter(
            KnowledgeItem.user_id == user_id,
            KnowledgeItem.next_review_at <= now_utc,
        ).order_by(KnowledgeItem.next_review_at.asc()).limit(10).all()
        recommended_reviews = [{'id': i.id, 'title': i.title, 'next_review_at': i.next_review_at.isoformat() if i.next_review_at else None} for i in recommended]

        total_mastery = sum(it.mastery or 0.0 for it in all_items) / len(all_items) if all_items else 0.0

        return jsonify({
            'review_count': review_count,
            'new_knowledge_count': new_knowledge_count,
            'avg_accuracy': round(avg_accuracy, 3),
            'total_mastery': round(total_mastery, 3),
            'total_items': len(all_items),
            'daily_timeline': daily_timeline,
            'weak_points': weak_points,
            'recommended_reviews': recommended_reviews,
        })

    except Exception as e:
        logger.error("report_weekly 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 32. GET /api/difficulty/offset - 难度偏移
@app.route('/api/difficulty/offset', methods=['GET'])
def difficulty_offset():
    """获取知识点的难度自适应偏移量"""
    if not ENABLE_ADAPTIVE:
        return jsonify({'error': '难度自适应未启用'}), 403

    try:
        item_id = request.args.get('item_id', type=int)
        if not item_id:
            return jsonify({'error': '请提供 item_id 参数'}), 400

        recent = StudySession.query.filter_by(
            item_id=item_id
        ).order_by(StudySession.created_at.desc()).limit(5).all()

        if not recent:
            return jsonify({'item_id': item_id, 'offset': 0.0, 'avg_score': None})

        avg = sum(s.score for s in recent) / len(recent)
        if avg > 0.8:
            offset = 0.2
        elif avg < 0.4:
            offset = -0.2
        else:
            offset = 0.0

        item = KnowledgeItem.query.get(item_id)
        if item:
            item.difficulty_offset = offset
            db.session.commit()

        return jsonify({
            'item_id': item_id,
            'offset': offset,
            'avg_score': round(avg, 3),
            'sample_size': len(recent),
        })

    except Exception as e:
        db.session.rollback()
        logger.error("difficulty_offset 失败: %s", e)
        return jsonify({'error': str(e)}), 500


# 33. DELETE /api/plot/<plot_id> - 铲除作物
@app.route('/api/plot/<int:plot_id>', methods=['DELETE'])
def remove_plot(plot_id: int):
    """铲除地块上的作物，重置地块为空地，不删除知识点"""
    try:
        user_id = DEMO_USER_ID
        plot = Plot.query.filter_by(id=plot_id, user_id=user_id).first()

        if not plot:
            return jsonify({'error': 'Plot not found'}), 404

        if plot.item_id is None:
            return jsonify({'status': 'ok', 'message': '地块已经是空的'})

        plot.item_id = None
        plot.growth_value = 0
        plot.is_harvestable = False
        plot.crop_variant = 'normal'
        plot.planted_at = None
        plot.error_plot_correct = 0

        db.session.commit()

        logger.info("[remove_plot] 地块 %d 已铲除", plot_id)
        return jsonify({'status': 'ok', 'message': '作物已铲除，地块恢复为空地'})

    except Exception as e:
        db.session.rollback()
        logger.error("[remove_plot] 铲除失败: %s", str(e), exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================
# 果实与商城 API
# ============================================

@app.route('/api/fruits', methods=['GET'])
def get_fruits():
    """获取用户的果实列表"""
    fruits = Fruit.query.filter_by(user_id=DEMO_USER_ID).order_by(Fruit.harvested_at.desc()).all()
    return jsonify({
        'fruits': [{'id': f.id, 'item_id': f.item_id, 'title': f.title, 'value': f.value,
                     'harvested_at': f.harvested_at.isoformat() if f.harvested_at else None} for f in fruits]
    })


@app.route('/api/exchange_fruit', methods=['POST'])
def exchange_fruit():
    """兑换果实为金币"""
    try:
        data = request.get_json()
        fruit_id = data.get('fruit_id')
        if not fruit_id:
            return jsonify({'error': 'fruit_id is required'}), 400

        fruit = Fruit.query.get(fruit_id)
        if not fruit or fruit.user_id != DEMO_USER_ID:
            return jsonify({'error': 'Fruit not found'}), 404

        user = User.query.get(DEMO_USER_ID)
        if not user:
            return jsonify({'error': 'User not found'}), 400

        user.knowledge_coins += fruit.value
        db.session.delete(fruit)
        db.session.commit()

        return jsonify({
            'coins_earned': fruit.value,
            'total_coins': user.knowledge_coins
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/shop', methods=['GET'])
def get_shop():
    """获取商城装饰列表"""
    decos = Decoration.query.all()
    owned_ids = [ud.decoration_id for ud in
                  UserDecoration.query.filter_by(user_id=DEMO_USER_ID).all()]
    user = User.query.get(DEMO_USER_ID)
    return jsonify({
        'coins': user.knowledge_coins if user else 0,
        'items': [{'id': d.id, 'name': d.name, 'key': d.key, 'price': d.price,
                    'category': d.category, 'owned': d.id in owned_ids} for d in decos]
    })


@app.route('/api/shop/buy', methods=['POST'])
def buy_decoration():
    """购买装饰"""
    try:
        data = request.get_json()
        deco_id = data.get('decoration_id')
        if not deco_id:
            return jsonify({'error': 'decoration_id is required'}), 400

        deco = Decoration.query.get(deco_id)
        if not deco:
            return jsonify({'error': 'Decoration not found'}), 404

        existing = UserDecoration.query.filter_by(
            user_id=DEMO_USER_ID, decoration_id=deco_id
        ).first()
        if existing:
            return jsonify({'error': 'Already owned'}), 400

        user = User.query.get(DEMO_USER_ID)
        if not user or user.knowledge_coins < deco.price:
            return jsonify({'error': 'Insufficient coins'}), 400

        user.knowledge_coins -= deco.price
        db.session.add(UserDecoration(user_id=DEMO_USER_ID, decoration_id=deco_id, is_active=True))
        db.session.commit()

        return jsonify({'total_coins': user.knowledge_coins, 'decoration_name': deco.name})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/api/shop/activate', methods=['POST'])
def activate_decoration():
    """切换激活装饰"""
    try:
        data = request.get_json()
        deco_id = data.get('decoration_id')

        if deco_id:
            UserDecoration.query.filter_by(user_id=DEMO_USER_ID).update({'is_active': False})
            ud = UserDecoration.query.filter_by(
                user_id=DEMO_USER_ID, decoration_id=deco_id
            ).first()
            if not ud:
                return jsonify({'error': 'Decoration not owned'}), 404
            ud.is_active = True

        db.session.commit()

        active = UserDecoration.query.filter_by(
            user_id=DEMO_USER_ID, is_active=True
        ).all()
        css = ''
        for a in active:
            d = Decoration.query.get(a.decoration_id)
            if d and d.css_rule:
                css += d.css_rule + '\n'
        return jsonify({'active_css': css})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ============================================
# 兼容旧版前端的路由（保持向后兼容）
# ============================================

@app.route('/api/water', methods=['POST'])
@app.route('/api/water/<int:plot_id>', methods=['GET'])
def water_plot(plot_id=None):
    """浇水 - 获取验证题目"""
    try:
        if plot_id:
            data = {'plot_id': plot_id}
        else:
            data = request.get_json()
        plot_id_val = data.get('plot_id')
        verify_type = data.get('verify_type', 'auto')

        plot = Plot.query.get(plot_id_val)
        if not plot:
            return jsonify({'error': 'Plot not found'}), 400

        if plot.item_id is None:
            return jsonify({'error': 'No plant in this plot'}), 400

        knowledge_item = KnowledgeItem.query.get(plot.item_id)
        if not knowledge_item:
            return jsonify({'error': 'Knowledge item not found'}), 400

        # 配对知识点比较题
        if knowledge_item.paired_with_id:
            paired_item = KnowledgeItem.query.get(knowledge_item.paired_with_id)
            if paired_item:
                return jsonify({
                    'type': 'concept_verify',
                    'question': f'请比较「{knowledge_item.title}」和「{paired_item.title}」的异同，并说明各自适用场景',
                    'verify_type': 'compare',
                    'paired_item_id': paired_item.id,
                    'paired_title': paired_item.title
                })

        # fact类型 - 返回复习卡片
        if knowledge_item.type == 'fact':
            card = generate_fact_card(knowledge_item)
            card['formula'] = knowledge_item.formula or ''
            card['derivation_steps'] = knowledge_item.derivation_steps if isinstance(knowledge_item.derivation_steps, list) else []
            card['common_mistakes'] = knowledge_item.common_mistakes if isinstance(knowledge_item.common_mistakes, list) else []
            card['application_examples'] = knowledge_item.application_examples if isinstance(knowledge_item.application_examples, list) else []
            return jsonify({
                'type': 'fact_review',
                'card': card
            })

        # concept类型
        elif knowledge_item.type == 'concept':
            if verify_type == 'auto':
                base_types = ['recite', 'variant', 'debug', 'calc', 'coding']
                base_type = base_types[plot.growth_value // 20 % 5]

                if base_type == 'coding':
                    question = generate_coding_question(knowledge_item)
                    return jsonify({
                        'type': 'coding',
                        'question': question,
                        'language': 'python',
                        'verify_type': 'coding'
                    })
                else:
                    question_result = generate_concept_question(knowledge_item, 'auto')
                    return jsonify({
                        'type': 'concept_verify',
                        'question': question_result['question_text'],
                        'verify_type': question_result['verify_type']
                    })
            else:
                if verify_type == 'coding':
                    question = generate_coding_question(knowledge_item)
                    return jsonify({
                        'type': 'coding',
                        'question': question,
                        'language': 'python',
                        'verify_type': 'coding'
                    })
                else:
                    question_result = generate_concept_question(knowledge_item, verify_type)
                    return jsonify({
                        'type': 'concept_verify',
                        'question': question_result['question_text'],
                        'verify_type': question_result['verify_type']
                    })

        return jsonify({'error': 'Unknown knowledge type'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/verify_coding', methods=['POST'])
def verify_coding():
    """验证编程提交"""
    try:
        data = request.get_json()
        plot_id = data.get('plot_id')
        code = data.get('code', '')
        problem = data.get('problem', '')

        if not code:
            return jsonify({'error': 'Code is required'}), 400

        result = evaluate_coding_code(problem, code)

        return jsonify({
            'score': result['score'],
            'feedback': result['feedback'],
            'suggestion': result.get('suggestion', ''),
            'growth_increment': result['growth_increment']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/similar_concepts', methods=['GET'])
def get_similar_concepts():
    """获取当前用户所有可配对的相似知识点"""
    try:
        user_id = DEMO_USER_ID
        similar_pairs = find_similar_concepts(user_id, threshold=0.4)

        # 获取所有可配对的知识点（用于前端高亮显示）
        pairable_ids = set()
        for pair in similar_pairs:
            pairable_ids.add(pair['item1']['id'])
            pairable_ids.add(pair['item2']['id'])

        return jsonify({
            'pairs': similar_pairs,
            'pairable_ids': list(pairable_ids)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/pair_concepts', methods=['POST'])
def pair_concepts_compat():
    """建立配对关系（兼容旧路由）"""
    return pair_concepts()


@app.route('/api/unpair_concepts', methods=['POST'])
def unpair_concepts_compat():
    """解除配对关系（兼容旧路由）"""
    return unpair_concepts()


@app.route('/api/assistant_message', methods=['GET'])
def get_assistant_message():
    """获取AI助教消息"""
    try:
        user_id = DEMO_USER_ID

        # 查询用户所有知识点的平均掌握度
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()

        if items:
            avg_score = sum(item.mastery for item in items) / len(items)
        else:
            avg_score = 0.0

        # 计算新学习的知识点数量（掌握度 < 0.5 的视为新学习）
        new_count = sum(1 for item in items if item.mastery < 0.5)

        # 生成助教消息
        message = generate_assistant_message(avg_score, new_count)

        return jsonify({'message': message})

    except Exception as e:
        logger.error("获取助教消息失败: %s", e)
        return jsonify({'message': random.choice(DEFAULT_MESSAGES)})


@app.route('/api/ask_question', methods=['POST'])
def ask_question():
    """提问并获取质量评估和回答"""
    try:
        data = request.get_json()
        question = data.get('question', '')

        if not question or len(question.strip()) == 0:
            return jsonify({'error': '问题内容不能为空'}), 400

        user_id = DEMO_USER_ID
        items = KnowledgeItem.query.filter_by(user_id=user_id).all()
        related_items = [
            {'id': item.id, 'title': item.title, 'content': item.content}
            for item in items[:5]
        ]

        result = evaluate_and_answer_question(question, related_items)

        return jsonify(result)

    except Exception as e:
        logger.error("提问功能失败: %s", e)
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate_card', methods=['POST'])
def generate_card():
    """生成知识卡片的结构化数据，供前端 html2canvas 截图"""
    try:
        data = request.get_json()
        item_id = data.get('knowledge_item_id')
        if not item_id:
            return jsonify({'error': 'knowledge_item_id is required'}), 400

        item = KnowledgeItem.query.get(item_id)
        if not item:
            return jsonify({'error': 'Knowledge item not found'}), 404

        mastery_pct = round(item.mastery * 100)

        if mastery_pct >= 80:
            quote = "你已超越80%的学习者，继续加油！"
        elif mastery_pct >= 60:
            quote = "坚持就是胜利，你正在进步！"
        elif mastery_pct >= 40:
            quote = "每一步都在积累，未来可期！"
        else:
            quote = "知识的种子已经播下，静待花开！"

        stars = "★" * min(5, max(1, round(mastery_pct / 20))) + "☆" * (5 - min(5, max(1, round(mastery_pct / 20))))

        card_data = {
            'title': item.title or '知识',
            'content': item.content[:120] if item.content else '',
            'type': item.type or 'concept',
            'mastery': mastery_pct,
            'stars': stars,
            'domain': item.domain or '通用',
            'depth': item.depth or 'basic',
            'tags': item.tags[:5] if item.tags else [],
            'quote': quote,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'difficulty': item.difficulty or 2,
            'formula': item.formula or '',
            'derivation_steps': item.derivation_steps if isinstance(item.derivation_steps, list) else [],
            'common_mistakes': item.common_mistakes if isinstance(item.common_mistakes, list) else [],
            'application_examples': item.application_examples if isinstance(item.application_examples, list) else [],
        }

        return jsonify({'card': card_data})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/farm/empty_plots_count', methods=['GET'])
def get_empty_plots_count():
    """返回当前用户的空闲地块数量"""
    try:
        user_id = DEMO_USER_ID
        total_plots = Plot.query.filter_by(user_id=user_id).count()
        empty_plots = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.is_(None)
        ).count()
        used_plots = total_plots - empty_plots

        return jsonify({
            'total': total_plots,
            'used': used_plots,
            'empty': empty_plots,
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/batch_water_info', methods=['GET'])
def batch_water_info():
    """获取所有可浇水地块的信息（未收获且非空地）"""
    try:
        user_id = DEMO_USER_ID
        plots = Plot.query.filter(
            Plot.user_id == user_id,
            Plot.item_id.isnot(None)
        ).filter(Plot.is_harvestable == False).all()

        result = []
        for plot in plots:
            item = KnowledgeItem.query.get(plot.item_id)
            if item:
                result.append({
                    'plot_id': plot.id,
                    'title': item.title,
                    'type': item.type,
                    'growth': plot.growth_value,
                    'mastery': round(item.mastery * 100),
                    'planted_at': plot.planted_at.isoformat() if plot.planted_at else None
                })

        return jsonify({'waterable_plots': result, 'total': len(result)})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/user', methods=['GET'])
def get_user():
    """获取用户信息"""
    try:
        user = User.query.get(DEMO_USER_ID)
        if not user:
            return jsonify({'error': 'User not found'}), 404

        return jsonify({
            'id': user.id,
            'knowledge_coins': user.knowledge_coins
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning/path', methods=['GET'])
def get_learning_path():
    """获取推荐学习路径"""
    try:
        user_id = DEMO_USER_ID
        items = KnowledgeItem.query.filter_by(user_id=user_id).filter(KnowledgeItem.mastery < 0.5).all()

        recommendations = []
        for item in items[:3]:
            recommendations.append({
                'id': item.id,
                'title': item.title,
                'type': item.type,
                'mastery': item.mastery,
                'reason': '需要加强学习'
            })

        return jsonify(recommendations)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/learning/stats', methods=['GET'])
def get_learning_stats_compat():
    """获取学习统计（兼容旧路由）"""
    return get_learning_stats()


# ============================================
# 启动入口
# ============================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)
