from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, session, render_template_string
from flask_cors import CORS
import os
import json
import time
import uuid
import threading
import secrets
from functools import wraps
import openai
import re
import requests
from bs4 import BeautifulSoup
import urllib.parse

# 创建Flask应用
app = Flask(__name__, static_folder='static')
app.secret_key = secrets.token_hex(16)  # 为session设置密钥
CORS(app)  # 启用跨域支持

# 访问密码
ACCESS_PASSWORD = "xiechunqiu"

# 数据存储
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
CASES_DIR = os.path.join(DATA_DIR, 'cases')
TAGS_FILE = os.path.join(DATA_DIR, 'tags.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

# 确保数据目录存在
os.makedirs(CASES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# 初始化数据文件
if not os.path.exists(TAGS_FILE):
    with open(TAGS_FILE, 'w') as f:
        json.dump({"categories": {
            "行业": ["制造业", "金融业", "互联网", "零售业", "医疗健康"],
            "规模": ["大型企业", "中型企业", "小型企业", "创业公司"],
            "主题": ["战略规划", "组织变革", "流程优化", "数字化转型", "人才管理"]
        }}, f)

if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump({
            "company": {
                "name": "写春秋企业管理咨询",
                "description": "专注于企业战略规划与管理咨询的专业服务机构"
            },
            "ai": {
                "provider": "deepseek",
                "api_key": "",
                "temperature": 0.7
            }
        }, f)

# 登录页面HTML模板
LOGIN_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>写春秋企业管理咨询 - 登录</title>
    <style>
        body {
            font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            height: 100vh;
            margin: 0;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background-color: white;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
            width: 90%;
            max-width: 400px;
            text-align: center;
        }
        .logo {
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin-bottom: 30px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
            box-sizing: border-box;
        }
        button {
            background-color: #4a6bdf;
            color: white;
            border: none;
            padding: 12px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
            transition: background-color 0.3s;
        }
        button:hover {
            background-color: #3a56b7;
        }
        .error-message {
            color: #e74c3c;
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">写春秋企业管理咨询</div>
        <form method="post" action="/login">
            <div class="form-group">
                <input type="password" name="password" placeholder="请输入访问密码" required>
            </div>
            <button type="submit">登录</button>
            {% if error %}
            <div class="error-message">{{ error }}</div>
            {% endif %}
        </form>
    </div>
</body>
</html>
"""

# 密码保护装饰器
def password_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 加载所有案例详细内容
def load_all_cases():
    cases = []
    if os.path.exists(CASES_DIR):
        for filename in os.listdir(CASES_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(CASES_DIR, filename), 'r', encoding='utf-8') as f:
                        case = json.load(f)
                        cases.append(case)
                except Exception as e:
                    print(f"加载案例文件 {filename} 时出错: {str(e)}")
    return cases

# 根据关键词匹配相关案例
def find_relevant_cases(message, cases, max_cases=3):
    if not cases:
        return []
    
    # 提取关键词
    keywords = extract_keywords(message)
    
    # 计算每个案例的相关性得分
    scored_cases = []
    for case in cases:
        score = calculate_relevance_score(case, keywords)
        scored_cases.append((case, score))
    
    # 按相关性得分排序并返回前N个案例
    scored_cases.sort(key=lambda x: x[1], reverse=True)
    return [case for case, score in scored_cases[:max_cases]]

# 提取关键词
def extract_keywords(message):
    # 行业关键词
    industry_keywords = ["制造业", "金融业", "互联网", "零售业", "医疗健康", "教育", "物流", "能源", "房地产"]
    
    # 企业规模关键词
    size_keywords = ["大型企业", "中型企业", "小型企业", "创业公司", "跨国公司", "国企", "民营企业"]
    
    # 管理主题关键词
    topic_keywords = [
        "战略规划", "组织变革", "流程优化", "数字化转型", "人才管理", "绩效管理", "企业文化",
        "领导力", "创新", "市场营销", "供应链", "财务管理", "风险管理", "质量管理",
        "成本控制", "客户关系", "并购", "国际化", "产品开发", "技术创新"
    ]
    
    # 提取所有可能的关键词
    all_keywords = industry_keywords + size_keywords + topic_keywords
    
    # 找出消息中包含的关键词
    found_keywords = []
    for keyword in all_keywords:
        if keyword in message:
            found_keywords.append(keyword)
    
    # 如果没有找到预定义关键词，则提取消息中的名词和形容词作为关键词
    if not found_keywords:
        # 简单分词，提取2-4字词语作为可能的关键词
        words = []
        for i in range(len(message)):
            for j in range(2, 5):  # 提取2-4字词
                if i + j <= len(message):
                    words.append(message[i:i+j])
        
        # 过滤掉常见的停用词
        stopwords = ["什么", "如何", "为什么", "怎么", "请问", "谢谢", "帮我", "我想", "可以", "需要"]
        words = [w for w in words if w not in stopwords]
        
        found_keywords = words[:5]  # 限制关键词数量
    
    return found_keywords

# 计算案例与关键词的相关性得分
def calculate_relevance_score(case, keywords):
    score = 0
    
    # 检查标题
    title = case.get('title', '')
    for keyword in keywords:
        if keyword in title:
            score += 3  # 标题匹配权重高
    
    # 检查描述
    description = case.get('description', '')
    for keyword in keywords:
        if keyword in description:
            score += 2  # 描述匹配权重中等
    
    # 检查内容
    content = case.get('content', '')
    for keyword in keywords:
        if keyword in content:
            score += 1  # 内容匹配权重低
    
    # 检查标签
    tags = case.get('tags', [])
    for keyword in keywords:
        if keyword in tags:
            score += 3  # 标签匹配权重高
    
    return score

# 格式化案例为AI可读格式
def format_cases_for_ai(cases):
    if not cases:
        return "目前没有找到相关案例。"
    
    formatted_text = "以下是与您咨询问题相关的案例详情：\n\n"
    
    for i, case in enumerate(cases, 1):
        formatted_text += f"案例{i}：{case.get('title', '无标题')}\n"
        formatted_text += f"描述：{case.get('description', '无描述')}\n"
        formatted_text += f"标签：{', '.join(case.get('tags', []))}\n"
        formatted_text += f"详细内容：{case.get('content', '无内容')}\n\n"
    
    return formatted_text

# 网络搜索功能
def web_search(query, num_results=3):
    try:
        # 构建搜索URL
        search_url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        
        # 设置请求头，模拟浏览器访问
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 发送请求
        response = requests.get(search_url, headers=headers)
        response.raise_for_status()
        
        # 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 提取搜索结果
        search_results = []
        result_elements = soup.select('.b_algo')[:num_results]
        
        for element in result_elements:
            title_element = element.select_one('h2 a')
            if not title_element:
                continue
                
            title = title_element.get_text()
            link = title_element.get('href', '')
            
            # 提取摘要
            snippet_element = element.select_one('.b_caption p')
            snippet = snippet_element.get_text() if snippet_element else "无摘要"
            
            search_results.append({
                'title': title,
                'link': link,
                'snippet': snippet
            })
        
        return search_results
    except Exception as e:
        print(f"网络搜索出错: {str(e)}")
        return []

# 格式化搜索结果为AI可读格式
def format_search_results_for_ai(results, query):
    if not results:
        return f"未能找到关于\"{query}\"的搜索结果。"
    
    formatted_text = f"以下是关于\"{query}\"的网络搜索结果：\n\n"
    
    for i, result in enumerate(results, 1):
        formatted_text += f"结果{i}：{result['title']}\n"
        formatted_text += f"链接：{result['link']}\n"
        formatted_text += f"摘要：{result['snippet']}\n\n"
    
    return formatted_text

# 使用DeepSeek API进行对话，并结合案例库分析和网络搜索
def get_ai_response(message, cases, settings):
    try:
        # 获取API设置
        api_key = settings.get('ai', {}).get('api_key', '')
        temperature = float(settings.get('ai', {}).get('temperature', 0.7))
        
        # 如果没有API密钥，返回模拟响应
        if not api_key:
            return simulate_ai_response(message, cases)
        
        # 查找相关案例
        relevant_cases = find_relevant_cases(message, cases)
        
        # 格式化案例内容
        case_content = format_cases_for_ai(relevant_cases)
        
        # 判断是否需要网络搜索
        need_search = should_perform_web_search(message)
        search_results = []
        search_content = ""
        
        if need_search:
            # 提取搜索关键词
            search_query = extract_search_query(message)
            # 执行网络搜索
            search_results = web_search(search_query)
            # 格式化搜索结果
            search_content = format_search_results_for_ai(search_results, search_query)
        
        # 初始化OpenAI客户端（DeepSeek使用OpenAI兼容接口）
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        
        # 准备系统提示和用户消息
        system_prompt = f"""你是写春秋企业管理咨询的AI助手，专注于为企业提供专业的管理咨询建议。
        你可以访问并分析公司的案例库，为用户提供基于实际案例的专业建议。
        你还具备深度思考能力，可以进行多步骤推理和全面分析，并能通过网络搜索获取最新信息。
        
        在回答用户问题时，请遵循以下原则：
        1. 分析用户问题，提取关键需求和管理主题
        2. 参考相关案例库内容，提供有针对性的建议
        3. 引用案例中的具体经验和数据支持你的建议
        4. 进行深度思考，从多个角度分析问题
        5. 当需要最新信息时，参考网络搜索结果
        6. 提供结构化的分析框架和实施步骤
        7. 保持专业、严谨的咨询顾问语气
        
        案例库内容：
        {case_content}
        
        {search_content if need_search else ""}
        
        如果用户询问特定行业或管理问题，请基于上述案例和搜索结果提供详细分析。如果案例库中没有完全匹配的案例，可以基于管理理论和最佳实践提供建议，但要明确说明这是基于理论而非具体案例。
        
        在回答时，请采用以下结构：
        1. 问题分析：简要概述用户问题的核心需求和关键点
        2. 案例参考：引用相关案例中的经验和数据
        3. 深度思考：从多个角度分析问题，考虑不同因素和可能的影响
        4. 行业洞察：结合最新行业趋势和数据（如有网络搜索结果）
        5. 建议方案：提供具体、可操作的解决方案和实施步骤
        6. 预期效果：分析方案可能带来的效果和潜在风险
        """
        
        # 调用DeepSeek API
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            temperature=temperature,
            stream=False
        )
        
        # 返回结果
        return {
            "text": response.choices[0].message.content,
            "referenced_cases": relevant_cases,
            "search_results": search_results if need_search else []
        }
    except Exception as e:
        print(f"AI API调用错误: {str(e)}")
        # 出错时返回模拟响应
        return simulate_ai_response(message, cases)

# 判断是否应该执行网络搜索
def should_perform_web_search(message):
    # 检查是否包含需要最新信息的关键词
    search_indicators = [
        "最新", "趋势", "现状", "数据", "统计", "报告", "研究", "调查",
        "市场", "行业", "发展", "前景", "预测", "政策", "法规",
        "新闻", "近期", "最近", "今年", "未来"
    ]
    
    for indicator in search_indicators:
        if indicator in message:
            return True
    
    # 检查是否是明确的搜索请求
    search_requests = [
        "搜索", "查询", "查找", "了解", "获取信息", "查一下",
        "网上", "互联网", "资料", "信息", "查询一下"
    ]
    
    for request in search_requests:
        if request in message:
            return True
    
    return False

# 从用户消息中提取搜索查询
def extract_search_query(message):
    # 移除常见的搜索请求词
    search_prefixes = [
        "请搜索", "帮我搜索", "查询", "查找", "了解", "获取信息关于",
        "查一下", "搜一下", "查询一下", "我想知道关于", "告诉我关于"
    ]
    
    query = message
    for prefix in search_prefixes:
        if message.startswith(prefix):
            query = message[len(prefix):].strip()
            break
    
    # 如果消息太长，提取关键部分作为搜索查询
    if len(query) > 100:
        # 提取关键词
        keywords = extract_keywords(message)
        if keywords:
            query = " ".join(keywords)
    
    # 添加"企业管理咨询"相关上下文，使搜索结果更相关
    if not any(term in query for term in ["企业", "管理", "咨询", "商业", "战略"]):
        query += " 企业管理"
    
    return query

# 模拟AI对话（作为备用）
def simulate_ai_response(message, cases):
    # 模拟AI思考时间
    time.sleep(1.5)
    
    # 查找相关案例
    relevant_cases = find_relevant_cases(message, cases)
    
    # 根据用户输入生成相关回复
    if "战略" in message:
        return {
            "text": "基于您提到的战略问题，我建议从以下几个方面考虑：\n\n1. 明确企业核心竞争力\n2. 分析行业发展趋势\n3. 评估市场机会与威胁\n4. 制定差异化战略\n\n我们有多个类似案例可供参考，特别是在制造业数字化转型方面的成功经验。",
            "referenced_cases": relevant_cases,
            "search_results": []
        }
    elif "组织" in message or "架构" in message:
        return {
            "text": "关于组织架构优化，建议考虑：\n\n1. 业务流程与组织结构匹配度\n2. 决策链条长度与效率\n3. 跨部门协作机制\n4. 绩效考核与激励机制\n\n根据我们的经验，扁平化管理结构通常能提高中型企业的运营效率。",
            "referenced_cases": relevant_cases,
            "search_results": []
        }
    elif "人才" in message or "招聘" in message:
        return {
            "text": "人才管理是企业发展的关键因素。建议从以下方面着手：\n\n1. 建立完善的人才招聘体系\n2. 设计有竞争力的薪酬结构\n3. 提供清晰的职业发展路径\n4. 营造积极的企业文化\n\n我们曾帮助多家企业解决人才流失问题，提高员工满意度和生产力。",
            "referenced_cases": relevant_cases,
            "search_results": []
        }
    else:
        return {
            "text": "感谢您的咨询。作为写春秋企业管理咨询的AI助手，我可以帮助您解决企业管理中的各类问题，包括战略规划、组织变革、流程优化、数字化转型和人才管理等。请详细描述您的具体需求，我将结合我们的案例库为您提供专业建议。",
            "referenced_cases": relevant_cases,
            "search_results": []
        }

# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['password'] == ACCESS_PASSWORD:
            session['authenticated'] = True
            return redirect('/')
        else:
            error = '密码错误，请重试'
    return render_template_string(LOGIN_HTML, error=error)

# 路由定义
@app.route('/')
@password_required
def index():
    return send_from_directory('static', 'index.html')

@app.route('/<path:path>')
@password_required
def static_files(path):
    return send_from_directory('static', path)

@app.route('/api/settings', methods=['GET', 'PUT'])
@password_required
def handle_settings():
    if request.method == 'GET':
        with open(SETTINGS_FILE, 'r') as f:
            return jsonify(json.load(f))
    else:  # PUT
        settings = request.json
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)
        return jsonify({"status": "success"})

@app.route('/api/tags', methods=['GET', 'POST', 'PUT', 'DELETE'])
@password_required
def handle_tags():
    if request.method == 'GET':
        with open(TAGS_FILE, 'r') as f:
            return jsonify(json.load(f))
    elif request.method == 'POST':
        tag_data = request.json
        with open(TAGS_FILE, 'r') as f:
            tags = json.load(f)
        
        category = tag_data.get('category', '其他')
        tag_name = tag_data.get('name')
        
        if category not in tags['categories']:
            tags['categories'][category] = []
        
        if tag_name not in tags['categories'][category]:
            tags['categories'][category].append(tag_name)
        
        with open(TAGS_FILE, 'w') as f:
            json.dump(tags, f)
        
        return jsonify({"status": "success", "tags": tags})
    elif request.method == 'PUT':
        tag_data = request.json
        with open(TAGS_FILE, 'r') as f:
            tags = json.load(f)
        
        old_category = tag_data.get('old_category')
        old_name = tag_data.get('old_name')
        new_category = tag_data.get('new_category', old_category)
        new_name = tag_data.get('new_name')
        
        # 删除旧标签
        if old_category in tags['categories'] and old_name in tags['categories'][old_category]:
            tags['categories'][old_category].remove(old_name)
        
        # 添加新标签
        if new_category not in tags['categories']:
            tags['categories'][new_category] = []
        
        if new_name not in tags['categories'][new_category]:
            tags['categories'][new_category].append(new_name)
        
        with open(TAGS_FILE, 'w') as f:
            json.dump(tags, f)
        
        return jsonify({"status": "success", "tags": tags})
    else:  # DELETE
        tag_data = request.json
        with open(TAGS_FILE, 'r') as f:
            tags = json.load(f)
        
        category = tag_data.get('category')
        name = tag_data.get('name')
        
        if category in tags['categories'] and name in tags['categories'][category]:
            tags['categories'][category].remove(name)
        
        with open(TAGS_FILE, 'w') as f:
            json.dump(tags, f)
        
        return jsonify({"status": "success", "tags": tags})

@app.route('/api/cases', methods=['GET', 'POST'])
@password_required
def handle_cases():
    if request.method == 'GET':
        cases = []
        for filename in os.listdir(CASES_DIR):
            if filename.endswith('.json'):
                with open(os.path.join(CASES_DIR, filename), 'r') as f:
                    case = json.load(f)
                    cases.append(case)
        return jsonify(cases)
    else:  # POST
        case_data = request.json
        case_id = str(uuid.uuid4())
        case_data['id'] = case_id
        case_data['created_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        with open(os.path.join(CASES_DIR, f"{case_id}.json"), 'w') as f:
            json.dump(case_data, f)
        
        return jsonify({"status": "success", "case": case_data})

@app.route('/api/cases/<case_id>', methods=['GET', 'PUT', 'DELETE'])
@password_required
def handle_case(case_id):
    case_file = os.path.join(CASES_DIR, f"{case_id}.json")
    
    if request.method == 'GET':
        if os.path.exists(case_file):
            with open(case_file, 'r') as f:
                return jsonify(json.load(f))
        else:
            return jsonify({"error": "Case not found"}), 404
    elif request.method == 'PUT':
        case_data = request.json
        case_data['updated_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        with open(case_file, 'w') as f:
            json.dump(case_data, f)
        
        return jsonify({"status": "success", "case": case_data})
    else:  # DELETE
        if os.path.exists(case_file):
            os.remove(case_file)
            return jsonify({"status": "success"})
        else:
            return jsonify({"error": "Case not found"}), 404

@app.route('/api/chat', methods=['POST'])
@password_required
def handle_chat():
    message = request.json.get('message', '')
    
    # 获取所有案例数据
    cases = load_all_cases()
    
    # 获取设置
    with open(SETTINGS_FILE, 'r') as f:
        settings = json.load(f)
    
    # 调用AI响应
    response = get_ai_response(message, cases, settings)
    
    return jsonify(response)

# 健康检查端点
@app.route('/health')
def health_check():
    return jsonify({"status": "healthy", "timestamp": time.time()})

# 添加一些示例案例
def add_sample_cases():
    sample_cases = [
        {
            "title": "某制造业企业战略转型",
            "description": "帮助一家传统制造企业实现数字化转型，提升市场竞争力。",
            "content": "客户是一家有30年历史的传统制造企业，面临数字化浪潮的冲击和新兴竞争对手的挑战。我们通过深入分析企业现状和行业趋势，制定了分阶段的数字化转型战略，包括生产自动化、供应链优化和客户关系管理系统升级。实施一年后，企业生产效率提升35%，运营成本降低20%，客户满意度显著提高。",
            "tags": ["制造业", "大型企业", "数字化转型", "战略规划"]
        },
        {
            "title": "金融科技公司组织架构优化",
            "description": "为快速发展的金融科技公司重新设计组织架构，提高运营效率。",
            "content": "客户是一家成立3年的金融科技公司，在快速扩张过程中出现了部门职责不清、沟通效率低下等问题。我们通过组织诊断，发现了决策链条过长、汇报关系复杂等核心问题。通过重新设计组织架构，明确岗位职责，优化业务流程，建立了更扁平化的管理结构和敏捷的项目制团队。改革后，公司决策效率提高50%，新产品上市周期缩短40%。",
            "tags": ["金融业", "中型企业", "组织变革"]
        },
        {
            "title": "互联网企业人才管理体系构建",
            "description": "帮助互联网企业建立完善的人才招聘、培养和保留体系。",
            "content": "客户是一家发展迅速的互联网企业，面临人才流失率高、核心岗位难以招聘到合适人选等问题。我们通过员工访谈和行业对标，设计了全新的人才管理体系，包括优化招聘流程、建立能力模型、设计有竞争力的薪酬结构和明确的职业发展路径。实施后，公司人才流失率从25%降至10%，关键岗位招聘周期缩短30%，员工满意度提升40%。",
            "tags": ["互联网", "大型企业", "人才管理"]
        }
    ]
    
    for case in sample_cases:
        case_id = str(uuid.uuid4())
        case['id'] = case_id
        case['created_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
        
        with open(os.path.join(CASES_DIR, f"{case_id}.json"), 'w') as f:
            json.dump(case, f)

# 启动时添加示例案例
if len(os.listdir(CASES_DIR)) == 0:
    add_sample_cases()

if __name__ == '__main__':
    # 生产环境配置
    app.run(host='0.0.0.0', port=5000, debug=False)
