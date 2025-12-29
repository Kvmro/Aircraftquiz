import streamlit as st
import json
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pathlib import Path

# --- 页面配置 ---
st.set_page_config(
    page_title="飞机人电子系统刷题系统 (云端版)",
    page_icon="✈️",
    layout="wide",  # 宽布局适配海量错题展示
    initial_sidebar_state="collapsed"  # 侧边栏默认折叠，节省空间
)

# --- 自定义CSS ---
st.markdown("""
<style>
    /* 基础样式优化 */
    div[data-baseweb="radio"] { display: flex; flex-direction: column; gap: 0.5rem; }
    div[data-baseweb="radio"] > div { 
        display: flex; align-items: center; width: 100% !important; 
        padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; 
        background-color: #f9fafb; transition: all 0.2s ease; cursor: pointer; 
    }
    div[data-baseweb="radio"] > div[aria-checked="true"] { 
        border-color: #2563eb; background-color: #eff6ff; font-weight: bold; 
    }
    div[data-baseweb="radio"] > div:hover { 
        border-color: #93c5fd; background-color: #dbeafe; 
    }
    div[data-baseweb="radio"] > div > div:first-child { display: none; }
    div[data-baseweb="radio"] > div > div:last-child { 
        flex-grow: 1; text-align: left; font-size: 0.9rem; 
    }
    .stButton > button { 
        width: 100%; font-size: 0.9rem; padding-top: 0.5rem; padding-bottom: 0.5rem; 
    }
    .stSuccess, .stError, .stWarning { 
        padding: 0.75rem; border-radius: 0.5rem; font-size: 1rem; 
    }
    .stCaption { font-size: 0.85rem; line-height: 1.5; }
    
    /* 分页按钮样式 */
    .pagination-btn { width: auto !important; margin: 0 0.2rem; }
    
    /* 标签页样式优化 */
    div[data-baseweb="tabs"] { margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- 核心配置（已替换为你的表格ID）---
SPREADSHEET_ID = '13d6icf3wTSEidLWBbgEKZJcae_kYzTT3zO8WcMtoUts'  

# --- Google Sheets 连接函数 ---
def get_google_sheets_client():
    """从 Streamlit Secrets 获取授权的 Google Sheets 客户端"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = json.loads(st.secrets["google_credentials"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except KeyError:
        st.error("错误：Streamlit Secrets 中未找到 'google_credentials'，请检查配置！")
        st.stop()
    except Exception as e:
        st.error(f"连接 Google Sheets 失败: {str(e)}")
        st.stop()

# --- 进度加载/保存函数 ---
def load_progress(user_id):
    """加载用户进度（兼容海量题库，优化空值处理）"""
    client = get_google_sheets_client()
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    try:
        cell = sheet.find(user_id)
        if cell is None:
            st.info(f"👋 欢迎新用户 {user_id}！将为你创建新的学习记录。")
            default_data = {
                "correct_ids": set(), 
                "incorrect_ids": set(), 
                "error_counts": {}, 
                "last_wrong_answers": {}
            }
            return default_data, None
        
        row = sheet.row_values(cell.row)
        # 兼容空数据解析（海量题库下避免JSON解析错误）
        progress_data = {
            "correct_ids": set(json.loads(row[1])) if row[1] and row[1] != "[]" else set(),
            "incorrect_ids": set(json.loads(row[2])) if row[2] and row[2] != "[]" else set(),
            "error_counts": json.loads(row[3]) if row[3] and row[3] != "{}" else {},
            "last_wrong_answers": json.loads(row[4]) if row[4] and row[4] != "{}" else {}
        }
        st.success(f"✅ 欢迎回来, {user_id}！已加载你的学习进度（累计错题 {len(progress_data['error_counts'])} 道）。")
        return progress_data, cell.row
    
    except Exception as e:
        st.error(f"加载进度时发生错误: {str(e)}")
        return None, None

def save_progress(user_id, progress_data, row_to_update=None):
    """保存用户进度（优化海量数据写入性能）"""
    client = get_google_sheets_client()
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    row_data = [
        user_id,
        json.dumps(list(progress_data["correct_ids"])),
        json.dumps(list(progress_data["incorrect_ids"])),
        json.dumps(progress_data["error_counts"]),
        json.dumps(progress_data["last_wrong_answers"])
    ]
    try:
        if row_to_update:
            sheet.update(f'A{row_to_update}:E{row_to_update}', [row_data], value_input_option='USER_ENTERED')
        else:
            sheet.append_row(row_data, value_input_option='USER_ENTERED')
    except Exception as e:
        st.error(f"保存进度时发生错误: {str(e)}")

# --- 题库加载函数 ---
@st.cache_data(ttl=3600)  # 缓存1小时，避免重复加载海量题库
def load_questions():
    """加载题库（兼容海量题目，优化解析性能）"""
    try:
        with open("question_bank.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            st.error("错误：题库文件必须是JSON数组格式！")
            st.stop()
        
        normalized_questions = []
        for i, item in enumerate(data):
            # 基础字段校验（海量题库下跳过无效题目）
            q_text = item.get('question') or item.get('题干')
            options = item.get('options') or item.get('选项')
            answer = item.get('answer') or item.get('正确答案')
            
            if not q_text or not options or not answer or not isinstance(options, list) or len(options) == 0:
                continue
            
            explanation = item.get('explanation') or item.get('解析') or ''
            normalized_questions.append({
                'id': i,
                'question': str(q_text),
                'options': [str(opt) for opt in options],
                'answer': str(answer).strip().upper(),
                'explanation': str(explanation)
            })
        
        if not normalized_questions:
            st.error("错误：未加载到有效题目，请检查题库文件！")
            st.stop()
        
        st.success(f"✅ 题库加载完成（共 {len(normalized_questions)} 道有效题目）")
        return normalized_questions
    except FileNotFoundError:
        st.error("错误：未找到 question_bank.json 文件，请确认文件路径！")
        st.stop()
    except Exception as e:
        st.error(f"加载题库时发生错误: {str(e)}")
        st.stop()

# --- 答题批次生成函数 ---
def generate_new_batch():
    """生成常规答题批次（优化海量题库的批次生成逻辑）"""
    batch_size = 50  # 常规批次缩小为50题，适配海量题库
    new_batch = []
    all_questions = st.session_state.all_questions
    
    # 1. 优先加入未掌握题目
    incorrect_questions = [q for q in all_questions if q['id'] in st.session_state.incorrect_ids]
    new_batch.extend(incorrect_questions[:batch_size//2])  # 占批次50%
    
    # 2. 加入少量已掌握题目复习
    correct_questions = [q for q in all_questions if q['id'] in st.session_state.correct_ids]
    if correct_questions:
        num_review = min(batch_size//4, len(correct_questions))
        new_batch.extend(random.sample(correct_questions, num_review))
    
    # 3. 加入未做过的题目
    remaining_questions = [q for q in all_questions if q['id'] not in st.session_state.correct_ids and q['id'] not in st.session_state.incorrect_ids]
    needed = batch_size - len(new_batch)
    if needed > 0 and remaining_questions:
        new_batch.extend(random.sample(remaining_questions, min(needed, len(remaining_questions))))
    
    # 打乱并限制批次大小
    random.shuffle(new_batch)
    new_batch = new_batch[:batch_size]
    
    # 更新session状态
    st.session_state.current_batch = new_batch
    st.session_state.current_question_idx = 0
    st.session_state.submitted_answers = {}
    st.session_state.quiz_finished = not new_batch
    st.session_state.current_mode = "normal"  # 标记当前为常规答题模式

def generate_error_batch():
    """生成错题专项练习批次（核心新增功能）"""
    all_questions = st.session_state.all_questions
    error_ids = list(st.session_state.error_counts.keys())
    
    if not error_ids:
        st.warning("⚠️ 暂无错题，无法生成错题练习！")
        return
    
    # 转换为数字ID并筛选有效错题
    error_ids_int = [int(q_id) for q_id in error_ids if q_id.isdigit()]
    error_questions = [q for q in all_questions if q['id'] in error_ids_int]
    
    if not error_questions:
        st.warning("⚠️ 未找到有效错题，请检查进度数据！")
        return
    
    # 错题批次大小（最多100题，适配海量错题）
    batch_size = min(100, len(error_questions))
    error_batch = random.sample(error_questions, batch_size)
    
    # 更新session状态
    st.session_state.current_batch = error_batch
    st.session_state.current_question_idx = 0
    st.session_state.submitted_answers = {}
    st.session_state.quiz_finished = False
    st.session_state.current_mode = "error"  # 标记当前为错题练习模式

# --- 辅助函数 ---
def reset_user_progress():
    """重置用户进度（优化海量数据清理）"""
    empty_data = {
        "correct_ids": set(), 
        "incorrect_ids": set(), 
        "error_counts": {}, 
        "last_wrong_answers": {}
    }
    save_progress(st.session_state.user_id, empty_data, st.session_state.user_row_id)
    st.success("🗑️ 所有进度已重置！")
    # 重置session状态
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def paginate_list(data, page_num, page_size):
    """通用分页函数（适配海量错题分页）"""
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    return data[start_idx:end_idx], len(data)

# --- 主应用逻辑 ---
def main():
    st.title("✈️ 飞机人电子系统刷题系统")
    st.markdown("### 适配1356道海量题库 | 错题本独立管理")
    st.divider()

    # === 第一步：用户登录 ===
    if 'user_id' not in st.session_state:
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            with st.form("login_form"):
                st.header("👤 用户登录")
                user_id = st.text_input("请输入你的昵称/ID", placeholder="例如：张三123", label_visibility="collapsed")
                submitted = st.form_submit_button("登录", type="primary")
                if submitted and user_id:
                    st.session_state.user_id = user_id
                    st.rerun()
                elif submitted:
                    st.warning("请输入昵称/ID后登录！")
        return

    # === 第二步：初始化数据 ===
    if 'all_questions' not in st.session_state:
        # 加载进度和题库
        progress_data, row_id = load_progress(st.session_state.user_id)
        if progress_data is None:
            return
        all_questions = load_questions()
        
        # 初始化session状态
        st.session_state.all_questions = all_questions
        st.session_state.correct_ids = progress_data["correct_ids"]
        st.session_state.incorrect_ids = progress_data["incorrect_ids"]
        st.session_state.error_counts = progress_data["error_counts"]
        st.session_state.last_wrong_answers = progress_data["last_wrong_answers"]
        st.session_state.user_row_id = row_id
        st.session_state.current_mode = "normal"  # 默认常规答题模式
        
        # 生成首个答题批次
        generate_new_batch()

    # === 第三步：主页面标签页 ===
    tab1, tab2 = st.tabs(["📝 答题练习", "📚 错题本"])

    # --- 标签页1：答题练习 ---
    with tab1:
        # 侧边栏（折叠式，只保留核心功能）
        with st.sidebar:
            st.header(f"你好, {st.session_state.user_id}!")
            
            # 模式显示
            mode_text = "常规练习" if st.session_state.current_mode == "normal" else "错题专项练习"
            st.info(f"当前模式：{mode_text}")
            
            # 控制按钮
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 刷新批次", type="primary"):
                    if st.session_state.current_mode == "normal":
                        generate_new_batch()
                    else:
                        generate_error_batch()
                    st.rerun()
            with col_btn2:
                if st.button("📚 去错题本", type="secondary"):
                    tab2.select()  # 切换到错题本标签页
            
            # 进度统计
            st.markdown("---")
            st.subheader("📊 学习进度")
            total_q = len(st.session_state.all_questions)
            correct_q = len(st.session_state.correct_ids)
            incorrect_q = len(st.session_state.incorrect_ids)
            error_q = len(st.session_state.error_counts)
            
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                st.metric("总题数", total_q)
            with col_stat2:
                st.metric("已掌握", correct_q)
            with col_stat3:
                st.metric("错题数", error_q)
            
            if total_q > 0:
                st.progress(correct_q / total_q, text=f"掌握率：{round(correct_q/total_q*100, 1)}%")
            
            # 重置进度
            st.markdown("---")
            st.subheader("⚠️ 高级操作")
            if not st.session_state.get('show_reset_confirm', False):
                if st.button("🗑️ 重置所有进度", type="secondary"):
                    st.session_state.show_reset_confirm = True
                    st.rerun()
            else:
                st.error("此操作不可恢复！确定要重置？")
                col_reset1, col_reset2 = st.columns(2)
                with col_reset1:
                    if st.button("✅ 确认重置"):
                        reset_user_progress()
                with col_reset2:
                    if st.button("❌ 取消"):
                        st.session_state.show_reset_confirm = False
                        st.rerun()

        # 答题逻辑
        if st.session_state.quiz_finished:
            st.balloons()
            st.success("🎉 本轮练习完成！")
            
            col_fin1, col_fin2 = st.columns(2)
            with col_fin1:
                if st.button("🔄 继续练习", type="primary"):
                    if st.session_state.current_mode == "normal":
                        generate_new_batch()
                    else:
                        generate_error_batch()
                    st.rerun()
            with col_fin2:
                if st.button("📚 去错题本", type="secondary"):
                    tab2.select()
            return

        # 加载当前批次和题目
        current_batch = st.session_state.current_batch
        current_idx = st.session_state.current_question_idx

        # 批次完成处理
        if current_idx >= len(current_batch):
            st.success("✅ 本轮批次完成！正在生成新批次...")
            if st.session_state.current_mode == "normal":
                generate_new_batch()
            else:
                generate_error_batch()
            st.rerun()

        # 显示当前题目
        current_question = current_batch[current_idx]
        question_id = current_question['id']
        
        st.subheader(f"本轮进度：{current_idx + 1}/{len(current_batch)} 题")
        st.write(f"### {current_question['question']}")

        # 答题交互
        is_submitted = question_id in st.session_state.submitted_answers
        user_answer_text = st.session_state.submitted_answers.get(question_id)
        user_answer = st.radio(
            "请选择答案：",
            current_question["options"],
            key=f"q_{question_id}",
            index=current_question["options"].index(user_answer_text) if user_answer_text else None,
            disabled=is_submitted
        )

        # 提交答案逻辑
        if not is_submitted:
            if st.button("✅ 提交答案", type="primary"):
                if user_answer is None:
                    st.warning("⚠️ 请选择答案后提交！")
                else:
                    st.session_state.submitted_answers[question_id] = user_answer
                    
                    # 判断答案对错
                    user_answer_letter = user_answer.split(".")[0].strip().upper()
                    is_correct = user_answer_letter == current_question["answer"]
                    
                    # 更新进度
                    if is_correct:
                        st.session_state.correct_ids.add(question_id)
                        st.session_state.incorrect_ids.discard(question_id)
                        st.session_state.error_counts.pop(str(question_id), None)
                        st.session_state.last_wrong_answers.pop(str(question_id), None)
                    else:
                        st.session_state.incorrect_ids.add(question_id)
                        st.session_state.correct_ids.discard(question_id)
                        st.session_state.error_counts[str(question_id)] = st.session_state.error_counts.get(str(question_id), 0) + 1
                        st.session_state.last_wrong_answers[str(question_id)] = user_answer
                    
                    # 保存进度
                    progress_to_save = {
                        "correct_ids": st.session_state.correct_ids,
                        "incorrect_ids": st.session_state.incorrect_ids,
                        "error_counts": st.session_state.error_counts,
                        "last_wrong_answers": st.session_state.last_wrong_answers
                    }
                    save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id)
                    st.rerun()
        else:
            # 显示答题结果
            st.divider()
            user_answer_letter = user_answer_text.split(".")[0].strip().upper()
            correct_answer_letter = current_question["answer"]
            is_correct = user_answer_letter == correct_answer_letter
            
            if is_correct:
                st.success("🎉 回答正确！")
            else:
                st.error("❌ 回答错误！")
                st.markdown(f"**你的答案：** <span style='color:red'>{user_answer_text}</span>", unsafe_allow_html=True)
            
            # 显示正确答案
            correct_answer_text = next((opt for opt in current_question["options"] if opt.strip().startswith(correct_answer_letter)), "【未找到】")
            st.markdown(f"**正确答案：** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
            
            # 显示解析
            if current_question.get("explanation"):
                st.markdown("---")
                st.info(f"📖 解析：{current_question['explanation']}")
            
            # 下一题按钮
            st.button("➡️ 下一题", on_click=lambda: st.session_state.update({"current_question_idx": current_idx + 1}), type="primary")

    # --- 标签页2：错题本（核心优化功能）---
    with tab2:
        st.header("📚 错题本管理")
        st.markdown("---")
        
        # 加载错题数据
        error_ids = list(st.session_state.error_counts.keys())
        error_ids_int = [int(q_id) for q_id in error_ids if q_id.isdigit()]
        all_questions = st.session_state.all_questions
        error_questions = [q for q in all_questions if q['id'] in error_ids_int]
        
        # 错题统计
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("总错题数", len(error_questions))
        with col_stat2:
            max_error = max(st.session_state.error_counts.values()) if error_ids else 0
            st.metric("最高错误次数", max_error)
        with col_stat3:
            mastered_error = len([q for q in error_questions if q['id'] in st.session_state.correct_ids])
            st.metric("已订正错题", mastered_error)
        
        # 错题操作按钮
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🚀 专项练习错题", type="primary", disabled=len(error_questions)==0):
                generate_error_batch()
                tab1.select()  # 切换到答题标签页
                st.rerun()
        with col_btn2:
            if st.button("🧹 清空已订正错题", type="secondary", disabled=mastered_error==0):
                # 只保留未订正的错题
                new_error_counts = {}
                new_last_wrong = {}
                for q_id in error_ids:
                    q_id_int = int(q_id) if q_id.isdigit() else -1
                    if q_id_int not in st.session_state.correct_ids:
                        new_error_counts[q_id] = st.session_state.error_counts[q_id]
                        new_last_wrong[q_id] = st.session_state.last_wrong_answers.get(q_id, "")
                
                # 更新进度
                st.session_state.error_counts = new_error_counts
                st.session_state.last_wrong_answers = new_last_wrong
                progress_to_save = {
                    "correct_ids": st.session_state.correct_ids,
                    "incorrect_ids": st.session_state.incorrect_ids,
                    "error_counts": new_error_counts,
                    "last_wrong_answers": new_last_wrong
                }
                save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id)
                st.success("✅ 已清空已订正的错题！")
                st.rerun()
        with col_btn3:
            if st.button("📝 返回答题练习", type="secondary"):
                tab1.select()
        
        st.markdown("---")
        
        # 错题分页展示（核心优化：适配海量错题）
        if error_questions:
            # 分页配置
            page_size = 10  # 每页显示10道错题
            total_pages = (len(error_questions) + page_size - 1) // page_size
            
            # 分页控件
            col_page1, col_page2 = st.columns([8,2])
            with col_page1:
                page_num = st.selectbox("选择页码", range(1, total_pages+1), label_visibility="collapsed")
            with col_page2:
                st.write(f"第 {page_num}/{total_pages} 页")
            
            # 获取当前页错题
            current_page_errors, total_errors = paginate_list(error_questions, page_num, page_size)
            
            # 展示当前页错题
            for idx, q in enumerate(current_page_errors):
                q_id_str = str(q['id'])
                error_count = st.session_state.error_counts.get(q_id_str, 0)
                last_wrong = st.session_state.last_wrong_answers.get(q_id_str, "")
                
                # 错题卡片
                with st.expander(f"📌 错题 {page_size*(page_num-1)+idx+1} | 错误 {error_count} 次 | 题干：{q['question'][:50]}..."):
                    st.write(f"### 题干：{q['question']}")
                    
                    st.write("#### 选项：")
                    for opt in q['options']:
                        # 标记上次答错的选项
                        if opt == last_wrong:
                            st.markdown(f"- ❌ {opt}", unsafe_allow_html=True)
                        else:
                            st.write(f"- {opt}")
                    
                    # 正确答案
                    correct_answer_text = next((opt for opt in q["options"] if opt.strip().startswith(q["answer"])), "【未找到】")
                    st.markdown(f"#### ✅ 正确答案：<span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
                    
                    # 解析
                    if q.get("explanation"):
                        st.markdown(f"#### 📖 解析：{q['explanation']}", unsafe_allow_html=True)
                    
                    # 快速订正按钮
                    if st.button(f"✅ 标记为已掌握", key=f"master_{q['id']}"):
                        st.session_state.correct_ids.add(q['id'])
                        st.session_state.incorrect_ids.discard(q['id'])
                        st.session_state.error_counts.pop(q_id_str, None)
                        st.session_state.last_wrong_answers.pop(q_id_str, None)
                        
                        # 保存进度
                        progress_to_save = {
                            "correct_ids": st.session_state.correct_ids,
                            "incorrect_ids": st.session_state.incorrect_ids,
                            "error_counts": st.session_state.error_counts,
                            "last_wrong_answers": st.session_state.last_wrong_answers
                        }
                        save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id)
                        st.success(f"✅ 已标记错题 {q['id']} 为已掌握！")
                        st.rerun()
                
                st.markdown("---")
        else:
            st.info("🎉 暂无错题！继续保持优秀的答题状态～")

if __name__ == "__main__":
    main()
