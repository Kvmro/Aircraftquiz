import streamlit as st
import json
import random

# --- 页面配置 ---
st.set_page_config(page_title="智能刷题软件", page_icon="🧠", layout="centered")

# --- 加载题库 ---
@st.cache_data
def load_questions():
    """加载并缓存题库"""
    try:
        with open("question_bank.0.1.json", "r", encoding="utf-8") as f:
            text = f.read()

        # 先尝试正常解析
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # 如果不是标准 JSON 数组，尝试从文本中逐个提取 JSON 对象（容错处理）
            objs = []
            i = 0
            n = len(text)
            while i < n:
                if text[i] == '{':
                    start = i
                    depth = 0
                    while i < n:
                        if text[i] == '{':
                            depth += 1
                        elif text[i] == '}':
                            depth -= 1
                            if depth == 0:
                                end = i + 1
                                snippet = text[start:end]
                                try:
                                    objs.append(json.loads(snippet))
                                except Exception:
                                    pass
                                break
                        i += 1
                else:
                    i += 1

            if objs:
                data = objs
            else:
                raise json.JSONDecodeError("无法解析 JSON 对象", text, 0)

        # 规范化字段名，支持中文题库结构
        questions = []
        for item in data:
            q_text = item.get('question') or item.get('题干') or item.get('题目') or item.get('stem') or ''
            options = item.get('options') or item.get('选项') or []
            answer = item.get('answer') or item.get('正确答案') or ''
            explanation = item.get('explanation') or item.get('解析') or ''

            # 如果答案为多项（使用竖线分隔），取第一个选项作为主要答案以兼容单选模式
            if isinstance(answer, str) and '|' in answer:
                answer = answer.split('|')[0]

            if not isinstance(options, list):
                options = [options]

            questions.append({
                'question': q_text,
                'options': options,
                'answer': answer.strip(),
                'explanation': explanation
            })

        return questions
    except FileNotFoundError:
        st.error("错误：未找到 'question_bank.0.1.json' 文件。请确保该文件与脚本在同一目录下。")
        st.stop()
    except Exception as e:
        st.error(f"错误：无法解析 'question_bank.0.1.json'：{e}")
        st.stop()

# --- 重置测验状态 ---
def reset_quiz_state():
    """重置所有与测验相关的会话状态"""
    all_questions = load_questions()
    random.shuffle(all_questions) # 每次开始都打乱题目顺序
    st.session_state.all_questions = all_questions
    st.session_state.remaining_questions = all_questions.copy() # 待答题队列
    st.session_state.mastered_questions = [] # 已掌握题队列
    st.session_state.user_answers = {}
    st.session_state.current_question_index = 0
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False

# --- 主应用逻辑 ---
def main():
    st.title("🧠 智能刷题软件 (记忆模式)")
    st.markdown("答错的题目将在本轮中重新出现，直到你全部掌握！")
    st.divider()

    # 初始化会话状态
    if "all_questions" not in st.session_state:
        reset_quiz_state()

    # --- 侧边栏 ---
    with st.sidebar:
        st.header("⚙️ 设置")
        if st.button("🔄 重新开始", type="primary"):
            reset_quiz_state()
            st.rerun()

        st.divider()
        st.header("📊 进度")
        total = len(st.session_state.all_questions)
        mastered = len(st.session_state.mastered_questions)
        remaining = len(st.session_state.remaining_questions)
        
        # 显示进度条
        if total > 0:
            progress = mastered / total
            st.progress(progress, text=f"已掌握: {mastered} / 总题数: {total}")
        st.write(f"待答题: {remaining}")


    # --- 开始/答题逻辑 ---
    if not st.session_state.quiz_started:
        if not st.session_state.all_questions:
            st.warning("题库中没有题目，请先在 'question_bank.0.1.json' 中添加题目。")
            return
            
        st.info(f"题库已加载，共 **{len(st.session_state.all_questions)}** 道题。")
        if st.button("🚀 开始答题", type="primary"):
            st.session_state.quiz_started = True
            st.rerun()
        return

    # --- 答题循环 ---
    if not st.session_state.quiz_finished:
        current_index = st.session_state.current_question_index
        remaining_questions = st.session_state.remaining_questions

        if not remaining_questions:
            st.session_state.quiz_finished = True
            st.rerun()

        # 防止索引越界
        if current_index >= len(remaining_questions):
            current_index = 0
            st.session_state.current_question_index = 0

        current_question = remaining_questions[current_index]
        
        st.subheader(f"第 {current_index + 1}/{len(remaining_questions)} 题 (本轮)")
        st.write(f"**{current_question['question']}**")
        
        # 显示选项
        user_answer_key = f"q_{id(current_question)}" # 使用唯一key
        user_answer = st.radio(
            "请选择你的答案：",
            current_question["options"],
            key=user_answer_key,
            index=None # 默认不选中
        )

        # 提交答案
        if st.button("✅ 提交答案"):
            if user_answer is None:
                st.warning("请先选择一个答案！")
            else:
                # 记录答案
                user_answer_letter = user_answer.split(".")[0]
                st.session_state.user_answers[id(current_question)] = user_answer_letter

                # 检查答案
                is_correct = user_answer_letter == current_question["answer"]

                if is_correct:
                    st.success("🎉 回答正确！")
                    # 从待答题队列移除，加入已掌握队列
                    st.session_state.mastered_questions.append(remaining_questions.pop(current_index))
                else:
                    st.error("❌ 回答错误，这道题稍后会再次出现。")
                    st.info(f"正确答案是：**{current_question['answer']}**")
                    if "explanation" in current_question and current_question["explanation"]:
                        st.caption(f"解析：{current_question['explanation']}")
                    # 答错了，索引不增加，下一轮继续显示这道题
                    # 为了避免连续答错卡在同一题，可以将其移到队尾
                    remaining_questions.append(remaining_questions.pop(current_index))

                # 准备下一题
                st.session_state.current_question_index = 0 # 回答后，从新队列的第一题开始
                st.rerun() # 立即刷新以显示下一题

    # --- 测验结束 ---
    else:
        st.balloons()
        st.success("🎉 恭喜你！你已经掌握了所有题目！")
        st.divider()

        st.subheader("📊 最终成绩")
        total = len(st.session_state.all_questions)
        mastered = len(st.session_state.mastered_questions)
        st.metric(label="得分", value=f"{mastered}/{total}", delta=f"{(mastered/total)*100:.1f}%")
        
        st.divider()
        st.subheader("💡 想再挑战一次吗？")
        if st.button("🔄 再来一次", type="primary"):
            reset_quiz_state()
            st.rerun()

if __name__ == "__main__":
    main()