"""
AI学伴后端服务
启动：python server.py
依赖：pip install openai flask flask-cors
"""

import json
import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return send_from_directory('templates', 'index.html')

@app.route('/profile.html')
def profile():
    return send_from_directory('templates', 'profile.html')

@app.route('/feed.html')
def feed():
    return send_from_directory('templates', 'feed.html')

# Kimi API（兼容 OpenAI 格式）
# 从环境变量读取，也可直接替换为字符串：api_key="sk-..."
client = OpenAI(
    api_key=" ",
    base_url="https://api.moonshot.cn/v1",
)

SYSTEM_PROMPT = """你是一位专业、细致、有耐心的义务教育阶段AI辅导老师，专门帮助小学、初中学生梳理每日学习内容。你需要根据学生输入的“今天学了什么”和“哪里不懂”，给出分析。你的目标是帮助学生（尤其是乡村学生和学困生）理解知识点、找到免费的学习资源、制定学习计划。

规则：
1. 知识点必须具体到课本级、小节级，不要说“数学知识”“英语单词”这种空话。
2. 学习建议针对学生不懂的地方精准给出。如果学生没有提出不懂的地方，就予以鼓励。
3. 资源必须真实！！优先提供国家中小学智慧教育平台的资源，不要外网资源（B站教育区、网易公开课、人教版电子课本（pep.com.cn）、学而思网校免费课等也可以）。
4. 学习计划合理，考虑学生实际情况，不要安排太多书写性质的任务。
5. 语言亲切、简单，符合学生年龄。
6. 只返回标准JSON，不要任何多余文字、代码块、解释。"""


def build_user_message(profile, entries):
    grade = profile.get("grade", "未知年级")
    name = profile.get("nickname", "同学")
    region = profile.get("region", "")
    region_note = f"（来自{region}）" if region else ""

    subject_lines = []
    for e in entries:
        subject = e.get("subjectLabel", e.get("subjectId", ""))
        learned = e.get("learned", "").strip()
        confused = e.get("confused", "").strip()
        if not learned and not confused:
            continue
        lines = [f"【{subject}】"]
        if learned:
            lines.append(f"  今天学了：{learned}")
        if confused:
            lines.append(f"  不懂的地方：{confused}")
        subject_lines.append("\n".join(lines))

    subjects_text = "\n\n".join(subject_lines) if subject_lines else "（未填写具体内容）"

    return f"""学生信息：{name}，{grade}{region_note}

今日学习内容：
{subjects_text}

请根据以上信息，以JSON格式返回分析结果，结构如下：
{{
  "summary": [
    {{
      "subject": "科目名称",
      "points": ["知识点1", "知识点2"],
      "tips": "针对不懂的地方的具体建议"
    }}
  ],
  "resources": [
    {{
      "title": "资源名称（具体到章节）",
      "url": "资源链接",
      "desc": "简短描述，说明为什么推荐"
    }}
  ],
  "plan": {{
    "today": "今天还能做的事（1-2条）",
    "week": "本周学习建议（2-3条）",
    "encouragement": "一句鼓励的话"
  }}
}}

只输出JSON本身，不要加```代码块，不要有任何其他文字。"""


@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json(force=True)
    profile = data.get("profile", {})
    entries = data.get("entries", [])

    if not entries:
        return jsonify({"error": "entries 不能为空"}), 400

    if not client.api_key:
        return jsonify({"error": "未配置 KIMI_API_KEY，请在环境变量中设置"}), 500

    text = ""
    try:
        response = client.chat.completions.create(
            model="moonshot-v1-8k",
            temperature=0.3,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": build_user_message(profile, entries)},
            ],
        )
        text = response.choices[0].message.content.strip()
        print("=== Kimi raw response ===")
        print(text)
        print("=========================")

        # 去掉模型可能包裹的代码块（支持 ```json 或 ``` 开头）
        if text.startswith("```"):
            lines = text.split("\n")
            # 跳过第一行（```json 或 ```），去掉末尾的 ```
            start = 1
            end = len(lines)
            if lines[-1].strip() == "```":
                end -= 1
            text = "\n".join(lines[start:end]).strip()

        result = json.loads(text)
        return jsonify({"ok": True, "data": result})

    except json.JSONDecodeError as e:
        return jsonify({"error": f"AI返回格式异常：{str(e)}", "raw": text}), 500
    except Exception as e:
        return jsonify({"error": f"API调用失败：{str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


