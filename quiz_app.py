import streamlit as st
import json
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

# --- 页面配置 ---
st.set_page_config(page_title="飞机人电子系统刷题系统 (云端版)", page_icon="✈️", layout="centered")

# --- 自定义CSS ---
st.markdown("""
<style>
    div[data-baseweb="radio"] { display: flex; flex-direction: column; gap: 0.5rem; }
    div[data-baseweb="radio"] > div { display: flex; align-items: center; width: 100% !important; padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; background-color: #f9fafb; transition: all 0.2s ease; cursor: pointer; }
    div[data-baseweb="radio"] > div[aria-checked="true"] { border-color: #2563eb; background-color: #eff6ff; font-weight: bold; }
    div[data-baseweb="radio"] > div:hover { border-color: #93c5fd; background-color: #dbeafe; }
    div[data-baseweb="radio"] > div > div:first-child { display: none; }
    div[data-baseweb="radio"] > div > div:last-child { flex-grow: 1; text-align: left; font-size: 0.9rem; }
    .stButton > button { width: 100%; font-size: 0.9rem; padding-top: 0.5rem; padding-bottom: 0.5rem; }
    .stSuccess, .stError, .stWarning { padding: 0.75rem; border-radius: 0.5rem; font-size: 1rem; }
    .stCaption { font-size: 0.85rem; line-height: 1.5; }
    .sidebar .stHeader { font-size: 1.1rem; }
    .sidebar .stMarkdown, .sidebar .stText { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# --- 【核心修改】使用 Streamlit Secrets 进行云端认证 ---
# 2. 替换为你的 Google Sheets 表格标题
SPREADSHEET_TITLE = '飞机人刷题系统-用户进度' 

def get_google_sheets_client():
    """
    从 Streamlit Secrets 获取并返回一个已授权的 Google Sheets 客户端。
    这是最安全的方式，避免了将密钥文件上传到 GitHub。
    """
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # 从 st.secrets 中获取凭证字符串并解析为 JSON 字典
        creds_dict = json.loads(st.secrets["google_credentials"])
        # 使用 from_json_keyfile_dict 方法从字典创建凭证
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except KeyError:
        st.error("错误：在 Streamlit Secrets 中未找到 'google_credentials'。请检查你的 Streamlit Cloud 应用设置。")
        st.stop()
    except Exception as e:
        st.error(f"连接 Google Sheets 失败: {e}")
        st.stop()

def load_progress(user_id):
    """从 Google Sheets 加载指定用户的进度"""
    client = get_google_sheets_client()
   # 替换规则：把 "你的表格ID" 换成你刚复制的ID，保留引号
sheet = client.open_by_key("13d6icf3wTSEidLWBbgEKZJcae_kYzTT3zO8WcMtoUts").sheet1
    try:
        cell = sheet.find(user_id)
        row = sheet.row_values(cell.row)
        progress_data = {
            "correct_ids": set(json.loads(row[1])) if row[1] else set(),
            "incorrect_ids": set(json.loads(row[2])) if row[2] else set(),
            "error_counts": json.loads(row[3]) if row[3] else {},
            "last_wrong_answers": json.loads(row[4]) if row[4] else {}
        }
        st.success(f"✅ 欢迎回来, {user_id}！已加载你的学习进度。")
        return progress_data, cell.row
    except gspread.exceptions.CellNotFound:
        st.info(f"👋 欢迎新用户 {user_id}！将为你创建新的学习记录。")
        default_data = {"correct_ids": set(), "incorrect_ids": set(), "error_counts": {}, "last_wrong_answers": {}}
        return default_data, None
    except Exception as e:
        st.error(f"加载进度时发生错误: {e}")
        return None, None

def save_progress(user_id, progress_data, row_to_update=None):
    """将用户进度保存到 Google Sheets"""
    client = get_google_sheets_client()
    sheet = client.open(SPREADSHEET_TITLE).sheet1
    row_data = [
        user_id,
        json.dumps(list(progress_data["correct_ids"])),
        json.dumps(list(progress_data["incorrect_ids"])),
        json.dumps(progress_data["error_counts"]),
        json.dumps(progress_data["last_wrong_answers"])
    ]
    try:
        if row_to_update:
            sheet.update(f'A{row_to_update}:E{row_to_update}', [row_data])
        else:
            sheet.append_row(row_data)
    except Exception as e:
        st.error(f"保存进度时发生错误: {e}")

# --- 加载题库 (不变) ---
@st.cache_data
def load_questions():
    try:
        with open("question_bank.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            st.error("错误：JSON 文件根结构必须是数组 [ ]。")
            st.stop()
        normalized_questions = []
        for i, item in enumerate(data):
            q_text = item.get('question') or item.get('题干')
            options = item.get('options') or item.get('选项')
            answer = item.get('answer') or item.get('正确答案')
            if not q_text or not options or not answer or not isinstance(options, list) or len(options) == 0: continue
            explanation = item.get('explanation') or item.get('解析') or ''
            normalized_questions.append({'id': i, 'question': str(q_text), 'options': [str(opt) for opt in options], 'answer': str(answer).strip().upper(), 'explanation': str(explanation)})
        if not normalized_questions:
            st.error("错误：未能加载任何有效题目。")
            st.stop()
        return normalized_questions
    except FileNotFoundError:
        st.error("错误：未找到 question_bank.json 文件。")
        st.stop()
    except Exception as e:
        st.error(f"加载题库时发生未知错误: {str(e)}")
        st.stop()

# --- 功能函数 ---
def start_new_attempt():
    keys_to_reset = ['current_batch', 'current_question_idx', 'submitted_answers', 'quiz_finished']
    for key in keys_to_reset:
        if key in st.session_state: del st.session_state[key]
    st.session_state.quiz_started = True
    generate_new_batch()

def reset_user_progress():
    empty_data = {"correct_ids": set(), "incorrect_ids": set(), "error_counts": {}, "last_wrong_answers": {}}
    save_progress(st.session_state.user_id, empty_data, st.session_state.user_row_id)
    st.success("🗑️ 你的所有学习进度已成功重置！")
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

def generate_new_batch():
    batch_size = 100
    new_batch = []
    incorrect_questions = [q for q in st.session_state.all_questions if q['id'] in st.session_state.incorrect_ids]
    new_batch.extend(incorrect_questions)
    correct_questions = [q for q in st.session_state.all_questions if q['id'] in st.session_state.correct_ids]
    if correct_questions:
        num_review = min(20, len(correct_questions))
        new_batch.extend(random.sample(correct_questions, num_review))
    remaining_questions = [q for q in st.session_state.all_questions if q['id'] not in st.session_state.correct_ids and q['id'] not in st.session_state.incorrect_ids]
    needed = batch_size - len(new_batch)
    if needed > 0 and remaining_questions:
        new_batch.extend(random.sample(remaining_questions, min(needed, len(remaining_questions))))
    random.shuffle(new_batch)
    st.session_state.current_batch = new_batch
    st.session_state.current_question_idx = 0
    st.session_state.submitted_answers = {}
    st.session_state.quiz_finished = not new_batch

# --- 主应用逻辑 ---
def main():
    st.title("✈️ 飞机人电子系统刷题系统 (云端安全版)")
    st.markdown("### 手机和电脑用户均可独立保存进度！")
    st.divider()

    if 'user_id' not in st.session_state:
        with st.sidebar.form("user_form"):
            st.header("👤 用户登录")
            user_id = st.text_input("请输入你的昵称或ID", placeholder="例如：张三123")
            submitted = st.form_submit_button("登录")
            if submitted and user_id:
                st.session_state.user_id = user_id
                st.rerun()
            elif submitted:
                st.warning("请输入昵称或ID！")
        return

    if 'all_questions' not in st.session_state:
        progress_data, row_id = load_progress(st.session_state.user_id)
        if progress_data is None: return
        all_questions = load_questions()
        random.shuffle(all_questions)
        st.session_state.all_questions = all_questions
        st.session_state.correct_ids = progress_data["correct_ids"]
        st.session_state.incorrect_ids = progress_data["incorrect_ids"]
        st.session_state.error_counts = progress_data["error_counts"]
        st.session_state.last_wrong_answers = progress_data["last_wrong_answers"]
        st.session_state.user_row_id = row_id
        start_new_attempt()

    with st.sidebar:
        st.header(f"你好, {st.session_state.user_id}!")
        st.button("🔄 开始新一轮答题", type="primary", on_click=start_new_attempt)
        st.markdown("---")
        st.subheader("⚠️ 危险操作")
        if not st.session_state.get('show_reset_confirmation', False):
            if st.button("🗑️ 重置我的所有进度", type="secondary"):
                st.session_state.show_reset_confirmation = True
                st.rerun()
        else:
            st.error("**此操作不可恢复！**\n\n确定要清空你的所有学习记录吗？")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🚨 确认重置", type="primary"): reset_user_progress()
            with col2:
                if st.button("❌ 取消"):
                    st.session_state.show_reset_confirmation = False
                    st.rerun()
        st.divider()
        st.header("📊 总进度")
        total_q, correct_q, incorrect_q = len(st.session_state.all_questions), len(st.session_state.correct_ids), len(st.session_state.incorrect_ids)
        if total_q > 0: st.progress(correct_q / total_q, text=f"已掌握: {correct_q} / {total_q}")
        st.write(f"未掌握: {incorrect_q}")
        st.divider()
        st.header("📋 错题库")
        num_wrong = len(st.session_state.error_counts)
        st.metric("需重点复习", num_wrong)
        with st.expander("点击展开/收起错题库", expanded=False):
            if num_wrong == 0: st.info("暂无错题。")
            else:
                for i, (q_id, error_count) in enumerate(st.session_state.error_counts.items(), 1):
                    q = next((q for q in st.session_state.all_questions if q['id'] == q_id), None)
                    if not q: continue
                    with st.expander(f"第 {i} 题: {q['question'][:30]}... (错 {error_count} 次)"):
                        st.write(f"**题干:** {q['question']}")
                        st.write("**选项:**")
                        for opt in q['options']: st.write(f"- {opt}")
                        last_wrong = st.session_state.last_wrong_answers.get(q_id)
                        if last_wrong: st.markdown(f"**上次答错:** <span style='color:red'>{last_wrong}</span>", unsafe_allow_html=True)
                        correct_answer_text = next((opt for opt in q["options"] if opt.strip().startswith(q["answer"])), "【未找到】")
                        st.markdown(f"**正确答案:** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
                        if q.get("explanation"): st.caption(f"**解析:** {q['explanation']}")

    if st.session_state.quiz_finished:
        st.balloons()
        st.success("🎉 恭喜你！本轮练习完成！")
        st.button("🏁 返回", on_click=start_new_attempt)
        return

    current_batch, current_idx = st.session_state.current_batch, st.session_state.current_question_idx
    if current_idx >= len(current_batch):
        st.success("✅ 本轮练习完成！正在生成下一批题目...")
        generate_new_batch()
        st.rerun()

    current_question = current_batch[current_idx]
    question_id = current_question['id']
    st.subheader(f"本轮: 第 {current_idx + 1}/{len(current_batch)} 题")
    st.write(f"**{current_question['question']}**")
    is_submitted = question_id in st.session_state.submitted_answers
    user_answer_text = st.session_state.submitted_answers.get(question_id)
    user_answer = st.radio("请选择你的答案：", current_question["options"], key=f"q_{question_id}", index=current_question["options"].index(user_answer_text) if user_answer_text else None, disabled=is_submitted)

    if not is_submitted:
        if st.button("✅ 提交答案", type="primary"):
            if user_answer is None:
                st.warning("⚠️ 请至少选择一个选项后再提交！")
            else:
                st.session_state.submitted_answers[question_id] = user_answer
                user_answer_letter = user_answer.split(".")[0].strip().upper()
                is_correct = user_answer_letter == current_question["answer"]
                if is_correct:
                    st.session_state.correct_ids.add(question_id)
                    st.session_state.incorrect_ids.discard(question_id)
                    st.session_state.error_counts.pop(question_id, None)
                    st.session_state.last_wrong_answers.pop(question_id, None)
                else:
                    st.session_state.incorrect_ids.add(question_id)
                    st.session_state.correct_ids.discard(question_id)
                    st.session_state.error_counts[question_id] = st.session_state.error_counts.get(question_id, 0) + 1
                    st.session_state.last_wrong_answers[question_id] = user_answer
                progress_to_save = {
                    "correct_ids": st.session_state.correct_ids,
                    "incorrect_ids": st.session_state.incorrect_ids,
                    "error_counts": st.session_state.error_counts,
                    "last_wrong_answers": st.session_state.last_wrong_answers
                }
                save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id)
                st.rerun()
    else:
        st.divider()
        user_answer_letter = user_answer_text.split(".")[0].strip().upper()
        correct_answer_letter = current_question["answer"]
        is_correct = user_answer_letter == correct_answer_letter
        if is_correct: st.success("🎉 回答正确！")
        else:
            st.error("❌ 回答错误。")
            st.markdown(f"**你选择了：** <span style='color:red'>{user_answer_text}</span>", unsafe_allow_html=True)
        correct_answer_text = next((opt for opt in current_question["options"] if opt.strip().startswith(correct_answer_letter)), "【未找到】")
        st.markdown(f"**正确答案是：** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
        if current_question.get("explanation"): st.caption(f"**解析:** {current_question['explanation']}")
        st.button("➡️ 下一题", on_click=lambda: st.session_state.update({"current_question_idx": current_idx + 1}))

if __name__ == "__main__":
    main()

