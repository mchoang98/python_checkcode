import os
import json
import subprocess
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
CORS(app)

# Khởi tạo Firebase Admin SDK từ biến môi trường chứa JSON key
firebase_key_json = os.getenv('FIREBASE_SERVICE_ACCOUNT')
if not firebase_key_json:
    raise RuntimeError("Thiếu biến môi trường FIREBASE_SERVICE_ACCOUNT")

firebase_key_dict = json.loads(firebase_key_json)

cred = credentials.Certificate(firebase_key_dict)


# cred = credentials.Certificate('serviceAccountKey.json')  # Đường dẫn tới file JSON của bạn
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://letscode-python-default-rtdb.firebaseio.com/'  # Thay bằng URL Realtime Database của bạn
})

# Hàm load toàn bộ dữ liệu problems từ node 'basic_problems'
def load_all_problems():
    ref = db.reference('basic_problems')
    data = ref.get()
    if not data:
        raise FileNotFoundError("Không tìm thấy dữ liệu bài tập từ Firebase.")
    # data là dict có dạng { someKey: {"problems": [...] } } hoặc trực tiếp dict có key 'problems'
    # Theo bạn, data lưu dạng:
    # {
    #    "problems": [ {...}, {...}, ... ]
    # }
    # Nếu đúng vậy, ta lấy data['problems']:
    if isinstance(data, dict) and "problems" in data:
        return data["problems"]
    else:
        raise ValueError("Dữ liệu từ Firebase không đúng định dạng, thiếu key 'problems'.")

def load_problem_by_id(problem_id):
    problems = load_all_problems()
    for problem in problems:
        if problem.get("id") == problem_id:
            return problem
    raise ValueError(f"Không tìm thấy bài tập với id: {problem_id}")

def generate_test_code(func_name, tests):
    test_code = f"def test_{func_name}():\n"
    test_code += f"    from user_code import {func_name}\n\n"
    for i, case in enumerate(tests, 1):
        input_repr = repr(case['input'])
        expected_repr = repr(case['expected'])
        test_code += f"    result = {func_name}(*{input_repr})\n"
        test_code += f'    print("Case #{i}: Input={input_repr} => Output=" + str(result) + ", Expected={expected_repr}")\n'
        test_code += f"    assert result == {expected_repr}\n\n"
    return test_code

@app.route('/list_problems', methods=['GET'])
def list_problems():
    try:
        problems = load_all_problems()
        simple_list = [{"id": p.get("id"), "title": p.get("title")} for p in problems]
        return jsonify(simple_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_problem', methods=['POST'])
def get_problem():
    data = request.get_json()
    problem_id = data.get('id')
    if not problem_id:
        return jsonify({"error": "Thiếu tham số id"}), 400
    try:
        problem = load_problem_by_id(problem_id)
        description = problem.get("description", "").replace('\n', '<br>')
        return jsonify({
            "function": problem.get("function"),
            "description": description,
            "params": problem.get("params"),
            "problem": {
                "title": problem.get("title"),
                "example": problem.get("example", "")
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route('/run_pytest', methods=['POST'])
def run_pytest():
    try:
        data = request.get_json()
        user_code = data.get('code', '')
        problem_id = data.get('id')

        if not problem_id:
            return jsonify({'error': 'Thiếu tham số id'}), 400

        problem = load_problem_by_id(problem_id)
        # Lấy tên hàm trong chuỗi "def function_name(...):"
        func_def = problem.get('function')
        func_name = func_def.split()[1].split('(')[0]
        tests = problem.get('tests', [])

        test_code = generate_test_code(func_name, tests)

        with tempfile.TemporaryDirectory() as tmpdir:
            user_code_file = os.path.join(tmpdir, 'user_code.py')
            with open(user_code_file, 'w', encoding='utf-8') as f:
                f.write(user_code)

            test_code_file = os.path.join(tmpdir, 'test_user_code.py')
            with open(test_code_file, 'w', encoding='utf-8') as f:
                f.write(test_code)

            result = subprocess.run(
                ['pytest', test_code_file, '--maxfail=1', '--disable-warnings', '-q'],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=10
            )

        return jsonify({
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })

    except FileNotFoundError as e:
        return jsonify({'error': str(e)}), 404
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Quá thời gian cho phép khi chạy test'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
