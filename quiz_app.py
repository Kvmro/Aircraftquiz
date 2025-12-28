import streamlit as st
import json
import random

# --- 页面配置 ---
st.set_page_config(page_title="飞机人电子系统刷题系统", page_icon="✈️", layout="centered")

# --- 自定义CSS (不变) ---
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
            
            if not q_text or not options or not answer or not isinstance(options, list) or len(options) == 0:
                st.warning(f"警告：跳过一道不完整的题目 (ID: {i})。")
                continue
                
            explanation = item.get('explanation') or item.get('解析') or ''
            
            normalized_questions.append({
                'id': i, 'question': str(q_text), 'options': [str(opt) for opt in options],
                'answer': str(answer).strip().upper(), 'explanation': str(explanation)
            })
        if not normalized_questions:
            st.error("错误：未能加载任何有效题目。")
            st.stop()
        return normalized_questions
    except FileNotFoundError:
        st.error("错误：未找到 question_bank.json 文件。")
        st.stop()
    except json.JSONDecodeError:
        st.error("错误：question_bank.json 文件格式不正确。")
        st.stop()
    except Exception as e:
        st.error(f"加载题库时发生未知错误: {str(e)}")
        st.stop()

# --- 【新增】开始新一轮答题 (不清空历史记录) ---
def start_new_attempt():
    # 只重置与本轮答题相关的状态
    keys_to_reset_for_new_attempt = [
        'current_batch', 'current_question_idx', 'submitted_answers', 'quiz_finished'
    ]
    for key in keys_to_reset_for_new_attempt:
        if key in st.session_state:
            del st.session_state[key]
    
    # 确保刷题状态是开启的
    st.session_state.quiz_started = True
    
    # 生成新的题目批次
    generate_new_batch()

# --- 【新增】重置所有学习进度 (清空一切) ---
def reset_all_progress():
    # 清除所有状态，包括历史记录
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    
    # 重新初始化应用
    initialize_app()

# --- 【重构】初始化应用状态 ---
def initialize_app():
    all_questions = load_questions()
    random.shuffle(all_questions)
    
    # 初始化持久化数据
    st.session_state.all_questions = all_questions
    st.session_state.correct_ids = set()
    st.session_state.incorrect_ids = set()
    st.session_state.error_counts = {}  # {question_id: count}
    st.session_state.last_wrong_answers = {} # {question_id: answer_text}

    # 初始化本轮答题状态
    st.session_state.current_batch = []
    st.session_state.current_question_idx = 0
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False
    st.session_state.submitted_answers = {}

def generate_new_batch():
    batch_size = 100
    new_batch = []
    
    # 优先加入错题
    incorrect_questions = [q for q in st.session_state.all_questions if q['id'] in st.session_state.incorrect_ids]
    new_batch.extend(incorrect_questions)
    
    # 加入少量已掌握的题目用于复习
    correct_questions = [q for q in st.session_state.all_questions if q['id'] in st.session_state.correct_ids]
    if correct_questions:
        num_review = min(20, len(correct_questions))
        new_batch.extend(random.sample(correct_questions, num_review))
        
    # 加入新题
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
    # 初始化应用状态
    if "all_questions" not in st.session_state:
        initialize_app()

    st.title("✈️ 飞机人电子系统刷题系统")
    st.markdown("### 专为飞机人提供")
    st.divider()

    # --- 侧边栏 ---
    with st.sidebar:
        st.header("⚙️ 设置")
        
        # 重新开始按钮
        if st.button("🔄 开始新一轮答题", type="primary", on_click=start_new_attempt):
            st.rerun()

        # 重置所有进度按钮
        st.warning("⚠️ 以下操作将清空所有学习记录！")
        if st.button("🗑️ 重置所有学习进度", type="secondary", on_click=reset_all_progress):
            st.rerun()

        st.divider()
        st.header("📊 总进度")
        total_q = len(st.session_state.all_questions)
        correct_q = len(st.session_state.correct_ids)
        incorrect_q = len(st.session_state.incorrect_ids)
        if total_q > 0:
            st.progress(correct_q / total_q, text=f"已掌握: {correct_q} / {total_q}")
        st.write(f"未掌握: {incorrect_q}")

        st.divider()
        st.header("📋 错题库")
        num_wrong_to_review = len(st.session_state.error_counts)
        st.metric("需重点复习", num_wrong_to_review)
        with st.expander("点击展开/收起错题库", expanded=False):
            if num_wrong_to_review == 0:
                st.info("暂无错题。")
            else:
                # 【核心修复】遍历 error_counts 字典来实现去重
                for i, (q_id, error_count) in enumerate(st.session_state.error_counts.items(), 1):
                    # 找到对应的题目
                    q = next((q for q in st.session_state.all_questions if q['id'] == q_id), None)
                    if not q: continue
                    
                    with st.expander(f"第 {i} 题: {q['question'][:30]}... (错 {error_count} 次)"):
                        st.write(f"**题干:** {q['question']}")
                        st.write("**选项:**")
                        for opt in q['options']:
                            st.write(f"- {opt}")
                        last_wrong_answer = st.session_state.last_wrong_answers.get(q_id)
                        if last_wrong_answer:
                            st.markdown(f"**上次答错:** <span style='color:red'>{last_wrong_answer}</span>", unsafe_allow_html=True)
                        correct_answer_text = next((opt for opt in q["options"] if opt.strip().startswith(q["answer"])), "【未找到】")
                        st.markdown(f"**正确答案:** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
                        if q.get("explanation"):
                            st.caption(f"**解析:** {q['explanation']}")

    # --- 主答题区 ---
    if not st.session_state.quiz_started:
        st.info(f"题库已加载，共 **{len(st.session_state.all_questions)}** 道题。")
        if st.button("🚀 开始答题", type="primary", on_click=start_new_attempt):
            st.rerun()
        return

    if "quiz_finished" not in st.session_state or st.session_state.quiz_finished:
        st.balloons()
        st.success("🎉 恭喜你！本轮练习完成！")
        if st.button("🏁 查看本轮结果", type="primary"):
            st.rerun() # 可以在这里添加查看本轮结果的逻辑
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

    user_answer = st.radio(
        "请选择你的答案：",
        current_question["options"],
        key=f"q_{question_id}",
        index=current_question["options"].index(user_answer_text) if user_answer_text else None,
        disabled=is_submitted
    )

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
                    # 如果做对了，从错题库中移除
                    if question_id in st.session_state.error_counts:
                        del st.session_state.error_counts[question_id]
                    if question_id in st.session_state.last_wrong_answers:
                        del st.session_state.last_wrong_answers[question_id]
                else:
                    st.session_state.incorrect_ids.add(question_id)
                    st.session_state.correct_ids.discard(question_id)
                    # 如果做错了，更新错题库
                    st.session_state.error_counts[question_id] = st.session_state.error_counts.get(question_id, 0) + 1
                    st.session_state.last_wrong_answers[question_id] = user_answer
                
                st.rerun()
    else:
        st.divider()
        user_answer_letter = user_answer_text.split(".")[0].strip().upper()
        correct_answer_letter = current_question["answer"]
        is_correct = user_answer_letter == correct_answer_letter

        if is_correct:
            st.success("🎉 回答正确！")
        else:
            st.error("❌ 回答错误。")
            st.markdown(f"**你选择了：** <span style='color:red'>{user_answer_text}</span>", unsafe_allow_html=True)
        
        correct_answer_text = next((opt for opt in current_question["options"] if opt.strip().startswith(correct_answer_letter)), "【未找到】")
        st.markdown(f"**正确答案是：** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
        
        if current_question.get("explanation"):
            st.caption(f"**解析:** {current_question['explanation']}")

        if st.button("➡️ 下一题", type="primary"):
            st.session_state.current_question_idx += 1
            st.rerun()

if __name__ == "__main__":
    main()
