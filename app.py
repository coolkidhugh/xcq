from flask import Flask, jsonify, request, send_from_directory, redirect, url_for, session, render_template_string
from flask_cors import CORS
import os
import json
import time
import uuid
import threading
import secrets
from functools import wraps

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

# 模拟AI对话
def simulate_ai_response(message, cases):
    # 模拟AI思考时间
    time.sleep(1.5)
    
    # 根据用户输入生成相关回复
    if "战略" in message:
        return {
            "text": "基于您提到的战略问题，我建议从以下几个方面考虑：\n\n1. 明确企业核心竞争力\n2. 分析行业发展趋势\n3. 评估市场机会与威胁\n4. 制定差异化战略\n\n我们有多个类似案例可供参考，特别是在制造业数字化转型方面的成功经验。",
            "referenced_cases": [case for case in cases if "战略" in case.get("title", "")][:2]
        }
    elif "组织" in message or "架构" in message:
        return {
            "text": "关于组织架构优化，建议考虑：\n\n1. 业务流程与组织结构匹配度\n2. 决策链条长度与效率\n3. 跨部门协作机制\n4. 绩效考核与激励机制\n\n根据我们的经验，扁平化管理结构通常能提高中型企业的运营效率。",
            "referenced_cases": [case for case in cases if "组织" in case.get("title", "")][:2]
        }
    elif "人才" in message or "招聘" in message:
        return {
            "text": "人才管理是企业发展的关键因素。建议从以下方面着手：\n\n1. 建立完善的人才招聘体系\n2. 设计有竞争力的薪酬结构\n3. 提供清晰的职业发展路径\n4. 营造积极的企业文化\n\n我们曾帮助多家企业解决人才流失问题，提高员工满意度和生产力。",
            "referenced_cases": [case for case in cases if "人才" in case.get("title", "")][:2]
        }
    else:
        return {
            "text": "感谢您的咨询。作为写春秋企业管理咨询的AI助手，我可以帮助您解决企业管理中的各类问题，包括战略规划、组织变革、流程优化、数字化转型和人才管理等。请详细描述您的具体需求，我将结合我们的案例库为您提供专业建议。",
            "referenced_cases": cases[:2] if cases else []
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
    
    # 获取案例数据用于推荐
    cases = []
    for filename in os.listdir(CASES_DIR):
        if filename.endswith('.json'):
            with open(os.path.join(CASES_DIR, filename), 'r') as f:
                case = json.load(f)
                cases.append(case)
    
    # 模拟AI响应
    response = simulate_ai_response(message, cases)
    
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
