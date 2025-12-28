import streamlit as st
import json
import random

# --- 页面配置 ---
st.set_page_config(page_title="智能刷题软件 (UI优化版)", page_icon="🎨", layout="centered")

# --- 加载题库 (此部分保持不变) ---
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
            explanation = item.get('explanation') or item.get('解析') or ''
            if not q_text or not options or not answer: continue
            if not isinstance(options, list): options = [str(options)]
            normalized_questions.append({
                'id': i, 'question': str(q_text), 'options': [str(opt) for opt in options],
                'answer': str(answer).strip().upper(), 'explanation': str(explanation)
            })
        if not normalized_questions: st.error("错误：未能加载任何有效题目。"); st.stop()
        return normalized_questions
    except Exception as e: st.error(f"加载题库失败: {e}"); st.stop()

# --- 重置/生成批次函数 (此部分保持不变) ---
def reset_quiz_state():
    all_questions = load_questions()
    random.shuffle(all_questions)
    st.session_state.all_questions = all_questions
    st.session_state.correct_ids = set()
    st.session_state.incorrect_ids = set()
    st.session_state.current_batch = []
    st.session_state.current_question_idx = 0
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False
    st.session_state.submitted_answers = {}
    st.session_state.error_counts = {} 
    st.session_state.last_wrong_answers = {}
    st.session_state.wrong_question_list = []

def generate_new_batch():
    batch_size = 100
    new_batch = []
    incorrect_questions = [q for q in st.session_state.all_questions if q['id'] in st.session_state.incorrect_ids]
    new_batch.extend(incorrect_questions)
    correct_questions = [q for q in st.session_state.all_questions if q['id'] in st.session_state.correct_ids]
    if correct_questions: new_batch.extend(random.sample(correct_questions, min(20, len(correct_questions))))
    remaining_questions = [q for q in st.session_state.all_questions if q['id'] not in st.session_state.correct_ids and q['id'] not in st.session_state.incorrect_ids]
    needed = batch_size - len(new_batch)
    if needed > 0 and remaining_questions: new_batch.extend(random.sample(remaining_questions, min(needed, len(remaining_questions))))
    random.shuffle(new_batch)
    st.session_state.current_batch = new_batch
    st.session_state.current_question_idx = 0
    st.session_state.submitted_answers = {}
    st.session_state.quiz_finished = not new_batch

# --- 主应用逻辑 (已更新) ---
def main():
    st.title("🎨 智能刷题软件 (UI优化版)")
    st.markdown("提交答案后，选项会保留并高亮显示对错，体验更流畅！")
    st.divider()

    if "all_questions" not in st.session_state:
        reset_quiz_state()

    # --- 侧边栏 (此部分保持不变) ---
    with st.sidebar:
        st.header("⚙️ 设置")
        if st.button("🔄 重新开始", type="primary"):
            reset_quiz_state()
            st.rerun()
        st.divider()
        st.header("📊 总进度")
        total, correct, incorrect = len(st.session_state.all_questions), len(st.session_state.correct_ids), len(st.session_state.incorrect_ids)
        if total > 0: st.progress(correct / total, text=f"已掌握: {correct} / {total}")
        st.write(f"未掌握 (本轮): {incorrect}")
        st.divider()
        st.header("📋 错题库 (错2次以上)")
        num_wrong_to_review = len(st.session_state.wrong_question_list)
        st.metric("需重点复习", num_wrong_to_review)
        with st.expander("点击展开/收起错题库", expanded=False):
            if num_wrong_to_review == 0:
                st.info("暂无需要重点复习的错题。")
            else:
                for i, q in enumerate(st.session_state.wrong_question_list):
                    error_count = st.session_state.error_counts[q['id']]
                    with st.expander(f"第 {i+1} 题: {q['question'][:20]}... (错 {error_count} 次)"):
                        st.write(f"**题干:** {q['question']}")
                        st.write("**选项:**")
                        for opt in q['options']: st.write(f"- {opt}")
                        last_wrong_answer = st.session_state.last_wrong_answers.get(q['id'])
                        if last_wrong_answer: st.markdown(f"**你上次答错的是：** <span style='color:red'>{last_wrong_answer}</span>", unsafe_allow_html=True)
                        correct_answer_text = next((opt for opt in q["options"] if opt.strip().startswith(q["answer"])), "【未找到】")
                        st.markdown(f"**正确答案是：** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
                        if q.get("explanation"): st.caption(f"**解析:** {q['explanation']}")

    # --- 开始/结束逻辑 (此部分保持不变) ---
    if not st.session_state.quiz_started:
        st.info(f"题库已加载，共 **{total}** 道题。")
        if st.button("🚀 开始答题", type="primary"):
            st.session_state.quiz_started = True
            generate_new_batch()
            st.rerun()
        return
    if st.session_state.quiz_finished:
        st.balloons()
        st.success("🎉 恭喜你！你已经掌握了所有题目！")
        return

    # --- 答题逻辑 (已更新) ---
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
    
    # 【核心改动】始终显示选项
    user_answer_text = st.session_state.submitted_answers.get(question_id)
    
    # 如果已提交，根据答案禁用并高亮；如果未提交，则正常显示
    user_answer = st.radio(
        "请选择你的答案：",
        current_question["options"],
        key=f"q_{question_id}",
        index=current_question["options"].index(user_answer_text) if user_answer_text else None,
        disabled=is_submitted # 提交后禁用选择
    )

    # 如果已提交，显示结果和高亮
    if is_submitted:
        user_answer_letter = user_answer_text.split(".")[0].strip().upper()
        correct_answer_letter = current_question["answer"]
        is_correct = user_answer_letter == correct_answer_letter

        st.divider() # 用分割线将选项和结果分开

        if is_correct:
            st.success("🎉 回答正确！")
            correct_answer_text = next((opt for opt in current_question["options"] if opt.strip().startswith(correct_answer_letter)), "【未找到】")
            st.markdown(f"**正确答案是：** <span style='background-color: #caffbf; color: black; padding: 2px 6px; border-radius: 3px;'>{correct_answer_text}</span>", unsafe_allow_html=True)
        else:
            st.error("❌ 回答错误。")
            st.markdown(f"**你选择了：** <span style='background-color: #ffadad; color: black; padding: 2px 6px; border-radius: 3px;'>{user_answer_text}</span>", unsafe_allow_html=True)
            correct_answer_text = next((opt for opt in current_question["options"] if opt.strip().startswith(correct_answer_letter)), "【未找到】")
            st.markdown(f"**正确答案是：** <span style='background-color: #caffbf; color: black; padding: 2px 6px; border-radius: 3px;'>{correct_answer_text}</span>", unsafe_allow_html=True)
        
        if current_question.get("explanation"):
            st.caption(f"**解析:** {current_question['explanation']}")

        if st.button("➡️ 下一题"):
            st.session_state.current_question_idx += 1
            st.rerun()

    # 如果未提交，显示提交按钮
    else:
        if st.button("✅ 提交答案"):
            if user_answer is None:
                st.warning("请先选择一个答案！")
            else:
                st.session_state.submitted_answers[question_id] = user_answer
                user_answer_letter = user_answer.split(".")[0].strip().upper()
                is_correct = user_answer_letter == current_question["answer"]

                if is_correct:
                    st.session_state.correct_ids.add(question_id)
                    st.session_state.incorrect_ids.discard(question_id)
                    if question_id in st.session_state.error_counts:
                        del st.session_state.error_counts[question_id]
                        if question_id in st.session_state.last_wrong_answers: del st.session_state.last_wrong_answers[question_id]
                    st.session_state.wrong_question_list = [q for q in st.session_state.all_questions if q['id'] in st.session_state.error_counts and st.session_state.error_counts[q['id']] >= 2]
                else:
                    st.session_state.incorrect_ids.add(question_id)
                    st.session_state.correct_ids.discard(question_id)
                    st.session_state.error_counts[question_id] = st.session_state.error_counts.get(question_id, 0) + 1
                    st.session_state.last_wrong_answers[question_id] = user_answer
                    st.session_state.wrong_question_list = [q for q in st.session_state.all_questions if q['id'] in st.session_state.error_counts and st.session_state.error_counts[q['id']] >= 2]

                st.rerun()

if __name__ == "__main__":
    main()