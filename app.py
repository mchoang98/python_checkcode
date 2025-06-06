# This file is part of Python checkcode by mchoang98.
# Copyright (c) 2025 mchoang98
#
# This code is licensed under the GNU General Public License v3.0.
# See: https://www.gnu.org/licenses/gpl-3.0.en.html


from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import tempfile
import os
import json

app = Flask(__name__)
CORS(app)  # Cho phép frontend gọi cross-origin

TEST_CASES_FOLDER = 'test_cases'

def load_test_cases(date):
    """Tải test case theo ngày từ thư mục test_cases"""
    path = os.path.join(TEST_CASES_FOLDER, f"{date}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Không tìm thấy file test case cho ngày: {date}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_test_code(func_name, tests):
    """Tạo mã test Python dựa trên danh sách test case"""
    test_code = f"def test_{func_name}():\n"
    test_code += f"    from user_code import {func_name}\n\n"
    for i, case in enumerate(tests, 1):
        input_repr = repr(case['input'])  # ví dụ: [2, 3, 1]
        expected_repr = repr(case['expected'])
        test_code += f"    result = {func_name}(*{input_repr})\n"
        test_code += f'    print("Case #{i}: Input={input_repr} => Output=" + str(result) + ", Expected={expected_repr}")\n'
        test_code += f"    assert result == {expected_repr}\n\n"
    return test_code

@app.route('/get_function_name', methods=['POST'])
def get_function_name():
    data = request.get_json()
    date = data.get('date')

    if not date:
        return jsonify({"error": "Thiếu tham số ngày (date)"}), 400

    file_path = os.path.join('test_cases', f"{date}.json")
    if not os.path.exists(file_path):
        return jsonify({
            "function": "unknown",
            "description": "Không tìm thấy bài tập tương ứng.",
            "params": [],
            "problem": {}
        })

    with open(file_path, 'r', encoding='utf-8') as f:
        test_data = json.load(f)
        return jsonify({
            "function": test_data.get("function", "unknown"),
            "description": test_data.get("description", ""),
            "params": test_data.get("params", []),
            "problem": test_data.get("problem", {})
        })

@app.route('/run_pytest', methods=['POST'])
def run_pytest():
    """Chạy kiểm thử code người dùng bằng pytest"""
    try:
        data = request.json
        user_code = data.get('code', '')
        date = data.get('date')

        if not date:
            return jsonify({'error': 'Thiếu tham số ngày (date)'}), 400

        test_data = load_test_cases(date)
        func_name = test_data.get('function')
        tests = test_data.get('tests', [])

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
