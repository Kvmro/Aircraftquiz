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
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 自定义CSS ---
st.markdown("""
<style>
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
    /* 多选框样式优化 */
    div[data-baseweb="checkbox"] { display: flex; flex-direction: column; gap: 0.5rem; }
    div[data-baseweb="checkbox"] > div { 
        display: flex; align-items: center; width: 100% !important; 
        padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; 
        background-color: #f9fafb; transition: all 0.2s ease; cursor: pointer; 
    }
    div[data-baseweb="checkbox"] > div[data-checked="true"] { 
        border-color: #2563eb; background-color: #eff6ff; font-weight: bold; 
    }
    div[data-baseweb="checkbox"] > div:hover { 
        border-color: #93c5fd; background-color: #dbeafe; 
    }
    div[data-baseweb="checkbox"] > div > div:first-child { display: none; }
    div[data-baseweb="checkbox"] > div > div:last-child { 
        flex-grow: 1; text-align: left; font-size: 0.9rem; 
    }
    .stButton > button { 
        width: 100%; font-size: 0.9rem; padding-top: 0.5rem; padding-bottom: 0.5rem; 
    }
    .stSuccess, .stError, .stWarning { 
        padding: 0.75rem; border-radius: 0.5rem; font-size: 1rem; 
    }
    .stCaption { font-size: 0.85rem; line-height: 1.5; }
    div[data-baseweb="tabs"] { margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# --- 核心配置 ---
SPREADSHEET_ID = '13d6icf3wTSEidLWBbgEKZJcae_kYzTT3zO8WcMtoUts'  
TOTAL_QUESTIONS = 1330  # 固定总题数为1330道

# --- Google Sheets 连接函数 ---
def get_google_sheets_client():
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
    "加载进度"
    try:
        # 从Google Sheets加载最新数据
        client = get_google_sheets_client()
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        cell = sheet.find(user_id)
        
        if cell is None:
            # 新用户
            st.info(f"👋 欢迎新用户 {user_id}！将为你创建新的学习记录。")
            default_data = {
                "correct_ids": set(), 
                "incorrect_ids": set(), 
                "error_counts": {}, 
                "last_wrong_answers": {}
            }
            return default_data, None
        
        # 现有用户，获取云端数据
        row = sheet.row_values(cell.row)
        cloud_data = {
            "correct_ids": set(json.loads(row[1])) if row[1] and row[1] != "[]" else set(),
            "incorrect_ids": set(json.loads(row[2])) if row[2] and row[2] != "[]" else set(),
            "error_counts": json.loads(row[3]) if row[3] and row[3] != "{}" else {},
            "last_wrong_answers": json.loads(row[4]) if row[4] and row[4] != "{}" else {}
        }
        
        st.success(f"✅ 欢迎回来, {user_id}！已加载你的学习进度（累计错题 {len(cloud_data['error_counts'])} 道）。")
        return cloud_data, cell.row
    
    except Exception as e:
        st.error(f"加载进度时发生错误: {str(e)}")
        return None, None
def save_progress(user_id, progress_data, row_to_update=None, force_save=False):
    "保存进度"
    # 检查是否需要保存到云端（默认每10题保存一次，或强制保存）
    answer_count = st.session_state.get('answer_count', 0)
    if not force_save and answer_count % 10 != 0:
        return
    
    # 检查数据是否有变化
    last_saved_data = st.session_state.get('last_saved_data', {})
    data_changed = False
    
    # 比较关键数据是否变化
    if last_saved_data.get('correct_ids') != progress_data['correct_ids']:
        data_changed = True
    elif last_saved_data.get('incorrect_ids') != progress_data['incorrect_ids']:
        data_changed = True
    elif last_saved_data.get('error_counts') != progress_data['error_counts']:
        data_changed = True
    elif last_saved_data.get('last_wrong_answers') != progress_data['last_wrong_answers']:
        data_changed = True
    
    if not data_changed and not force_save:
        return  # 数据未变化，不需要保存到云端
    
    # 保存到Google Sheets
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
        
        # 保存成功后更新上次保存的数据
        st.session_state['last_saved_data'] = {
            'correct_ids': progress_data['correct_ids'].copy(),
            'incorrect_ids': progress_data['incorrect_ids'].copy(),
            'error_counts': progress_data['error_counts'].copy(),
            'last_wrong_answers': progress_data['last_wrong_answers'].copy()
        }
    except Exception as e:

# --- 题库加载函数（优化：改进缓存策略，预计算题型分类）---
        st.warning(f"保存到云端失败: {str(e)}")

# --- 题库加载函数（优化：改进缓存策略，预计算题型分类）---
def load_questions():
    try:
        with open("question_bank.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            st.error("错误：题库文件必须是JSON数组格式！")
            st.stop()
        
        normalized_questions = []
        # 预计算不同题型的题目列表
        all_questions = []
        single_choice = []
        multiple_choice = []
        
        for i, item in enumerate(data):
            q_text = item.get('question') or item.get('题干')
            options = item.get('options') or item.get('选项')
            answer = item.get('answer') or item.get('正确答案')
            
            if not q_text or not options or not answer or not isinstance(options, list) or len(options) == 0:
                continue
            
            # 判断是否为多选题（答案为数组格式或包含"|"分隔符）
            is_multiple = isinstance(answer, list) or (isinstance(answer, str) and "|" in answer)
            
            # 标准化答案格式，多选题转集合，单选题转字符串
            if isinstance(answer, list):
                # 数组格式答案，如 ["B", "C", "D"]
                standard_answer = set([str(a).strip().upper() for a in answer if str(a).strip().upper()])
            elif "|" in str(answer):
                # "|"分隔符格式，如 "A|B|C"
                standard_answer = set([a.strip().upper() for a in str(answer).split("|") if a.strip().upper()])
            else:
                # 单选题，如 "A" 或 "B"
                standard_answer = str(answer).strip().upper()
            
            explanation = item.get('explanation') or item.get('解析') or ''
            question = {
                'id': i,
                'question': str(q_text),
                'options': [str(opt) for opt in options],
                'answer': standard_answer,  # 多选题存集合，单选题存字符串
                'is_multiple': is_multiple,  # 标记是否为多选题
                'original_answer': str(answer),  # 保留原始答案字符串（用于展示）
                'explanation': str(explanation)
            }
            
            normalized_questions.append(question)
            all_questions.append(question)
            if is_multiple:
                multiple_choice.append(question)
            else:
                single_choice.append(question)
        
        if not normalized_questions:
            st.error("错误：未加载到有效题目，请检查题库文件！")
            st.stop()
        
        # 返回包含所有题型分类的结果
        return {
            'all': all_questions,
            'single_choice': single_choice,
            'multiple_choice': multiple_choice,
            'total': len(all_questions),
            'total_single': len(single_choice),
            'total_multiple': len(multiple_choice)
        }
    except FileNotFoundError:
        st.error("错误：未找到 question_bank.json 文件，请确认文件路径！")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"错误：题库文件格式错误，无法解析 JSON: {str(e)}")
        st.stop()
    except Exception as e:
        st.error(f"加载题库时发生错误: {str(e)}")
        st.stop()

# --- 答题批次生成函数 ---
def generate_new_batch():
    """优化批次生成：减少重复计算，缓存过滤结果"""
    batch_size = 50
    new_batch = []
    
    # 从会话状态获取预计算数据，避免重复计算
    questions_data = st.session_state.questions_data
    all_questions = st.session_state.all_questions
    
    # 获取用户选择的题目类型
    question_type = st.session_state.get('question_type_select', '全部题目')
    
    # 缓存键，用于存储过滤结果
    filter_cache_key = f"filtered_questions_{question_type}"
    
    # 优先使用缓存的过滤结果
    if filter_cache_key not in st.session_state or st.session_state.get('filter_cache_invalid', False):
        # 根据题目类型直接获取对应的题目列表
        if question_type == '全部题目':
            filtered_questions = all_questions
        elif question_type == '仅单选题':
            filtered_questions = questions_data['single_choice']
        elif question_type == '仅多选题':
            filtered_questions = questions_data['multiple_choice']
        else:
            filtered_questions = all_questions
        
        # 缓存过滤结果
        st.session_state[filter_cache_key] = filtered_questions
        st.session_state['filter_cache_invalid'] = False
    else:
        filtered_questions = st.session_state[filter_cache_key]
    
    if not filtered_questions:
        st.warning(f"⚠️ 没有找到符合条件的题目！")
        st.session_state.current_batch = []
        st.session_state.current_question_idx = 0
        st.session_state.submitted_answers = {}
        st.session_state.quiz_finished = True
        st.session_state.current_mode = "normal"
        return
    
    # 从会话状态获取ID集合，避免重复创建
    incorrect_ids = st.session_state.incorrect_ids
    correct_ids = st.session_state.correct_ids
    
    # 分类题目 - 优化：使用更高效的过滤方式
    incorrect_questions = []
    correct_questions = []
    remaining_questions = []
    
    # 一次性遍历过滤后的题目，避免多次遍历
    for q in filtered_questions:
        q_id = q['id']
        if q_id in incorrect_ids:
            incorrect_questions.append(q)
        elif q_id in correct_ids:
            correct_questions.append(q)
        else:
            remaining_questions.append(q)
    
    # 生成批次 - 优化：避免不必要的extend操作
    new_batch = []
    
    # 添加错题（最多占一半）
    wrong_count = min(batch_size // 2, len(incorrect_questions))
    if wrong_count > 0:
        new_batch.extend(random.sample(incorrect_questions, wrong_count))
    
    # 添加已做对的题目（最多占四分之一）
    review_count = min(batch_size // 4, len(correct_questions))
    if review_count > 0:
        new_batch.extend(random.sample(correct_questions, review_count))
    
    # 添加新题目
    needed = batch_size - len(new_batch)
    if needed > 0 and remaining_questions:
        new_batch.extend(random.sample(remaining_questions, min(needed, len(remaining_questions))))
    
    # 洗牌并限制批次大小
    random.shuffle(new_batch)
    new_batch = new_batch[:batch_size]
    
    # 更新会话状态
    st.session_state.current_batch = new_batch
    st.session_state.current_question_idx = 0
    st.session_state.submitted_answers = {}
    st.session_state.quiz_finished = not new_batch
    st.session_state.current_mode = "normal"

def generate_error_batch():
    """优化错题批次生成：减少重复计算"""
    # 从会话状态获取预计算数据
    questions_data = st.session_state.questions_data
    all_questions = st.session_state.all_questions
    error_counts = st.session_state.error_counts
    
    # 获取错题ID并转换为整数
    error_ids_int = [int(q_id) for q_id in error_counts.keys() if q_id.isdigit()]
    
    # 无错题时，自动切换到常规模式
    if not error_ids_int:
        st.info("📌 错题已全部掌握！已自动切换到常规答题练习，请在上方标签页选择「答题练习」继续。")
        st.session_state.current_mode = "normal"
        generate_new_batch()
        return
    
    # 缓存错题集合
    error_ids_set = set(error_ids_int)
    
    # 获取用户选择的题目类型
    question_type = st.session_state.get('question_type_select', '全部题目')
    
    # 错题缓存键
    error_cache_key = f"error_questions_{question_type}"
    
    # 优先使用缓存的错题结果
    if error_cache_key not in st.session_state or st.session_state.get('error_cache_invalid', False):
        # 根据题目类型直接获取对应的题目列表，然后过滤错题
        if question_type == '全部题目':
            # 全部题目，直接过滤错题
            error_questions = [q for q in all_questions if q['id'] in error_ids_set]
        elif question_type == '仅单选题':
            # 仅单选题，先获取单选题列表，再过滤错题
            single_choice = questions_data['single_choice']
            error_questions = [q for q in single_choice if q['id'] in error_ids_set]
        elif question_type == '仅多选题':
            # 仅多选题，先获取多选题列表，再过滤错题
            multiple_choice = questions_data['multiple_choice']
            error_questions = [q for q in multiple_choice if q['id'] in error_ids_set]
        else:
            # 默认全部题目
            error_questions = [q for q in all_questions if q['id'] in error_ids_set]
        
        # 缓存错题结果
        st.session_state[error_cache_key] = error_questions
        st.session_state['error_cache_invalid'] = False
    else:
        error_questions = st.session_state[error_cache_key]
    
    if not error_questions:
        st.info("📌 无符合条件的有效错题！已自动切换到常规答题练习，请在上方标签页选择「答题练习」继续。")
        st.session_state.current_mode = "normal"
        generate_new_batch()
        return
    
    # 生成错题批次
    batch_size = min(100, len(error_questions))
    error_batch = random.sample(error_questions, batch_size)
    
    # 更新会话状态
    st.session_state.current_batch = error_batch
    st.session_state.current_question_idx = 0
    st.session_state.submitted_answers = {}
    st.session_state.quiz_finished = False
    st.session_state.current_mode = "error"

# --- 辅助函数 ---
def reset_user_progress():
    empty_data = {
        "correct_ids": set(), 
        "incorrect_ids": set(), 
        "error_counts": {}, 
        "last_wrong_answers": {}
    }
    save_progress(st.session_state.user_id, empty_data, st.session_state.user_row_id)
    st.success("🗑️ 所有进度已重置！")
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def paginate_list(data, page_num, page_size):
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    return data[start_idx:end_idx], len(data)

# --- 主应用逻辑 ---
def main():
    st.title("✈️ 飞机人电子系统刷题系统")
    st.markdown(f"### 适配{TOTAL_QUESTIONS}道海量题库 | 错题本独立管理 | 支持单选/多选")
    st.divider()

    # 用户登录
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

    # 初始化数据
    if 'all_questions' not in st.session_state:
        progress_data, row_id = load_progress(st.session_state.user_id)
        if progress_data is None:
            return
        
        # 加载题库数据（包含预计算的题型分类）
        questions_data = load_questions()
        all_questions = questions_data['all']
        
        # 保存完整题库和预计算的题型分类到会话状态
        st.session_state.all_questions = all_questions
        st.session_state.questions_data = questions_data  # 保存预计算的题型分类
        st.session_state.correct_ids = progress_data["correct_ids"]
        st.session_state.incorrect_ids = progress_data["incorrect_ids"]
        st.session_state.error_counts = progress_data["error_counts"]
        st.session_state.last_wrong_answers = progress_data["last_wrong_answers"]
        st.session_state.user_row_id = row_id
        st.session_state.current_mode = "normal"
        
        # 初始化上次保存的数据，用于增量更新检测
        st.session_state['last_saved_data'] = {
            'correct_ids': progress_data['correct_ids'].copy(),
            'incorrect_ids': progress_data['incorrect_ids'].copy(),
            'error_counts': progress_data['error_counts'].copy(),
            'last_wrong_answers': progress_data['last_wrong_answers'].copy()
        }
        
        # 显示加载成功信息
        st.success(f"✅ 题库加载完成（共 {questions_data['total']} 道有效题目，包含单选题 {questions_data['total_single']} 道，多选题 {questions_data['total_multiple']} 道）")
        
        generate_new_batch()

    # 主标签页
    tab1, tab2 = st.tabs(["📝 答题练习", "📚 错题本"])

    # 答题练习标签页
    with tab1:
        with st.sidebar:
            st.header(f"你好, {st.session_state.user_id}!")
            
            mode_text = "常规练习" if st.session_state.current_mode == "normal" else "错题专项练习"
            st.info(f"当前模式：{mode_text}")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("🔄 刷新批次", type="primary"):
                    if st.session_state.current_mode == "normal":
                        generate_new_batch()
                    else:
                        generate_error_batch()
                    st.rerun()
            with col_btn2:
                st.button("📚 去错题本", type="secondary", help="点击上方「错题本」标签页查看")
            
            # 题目类型选择
            st.markdown("---")
            st.subheader("🎯 题目类型")
            question_type = st.radio(
                "选择题目类型：",
                ["全部题目", "仅单选题", "仅多选题"],
                key="question_type_select",
                help="选择你想要练习的题目类型",
                on_change=lambda: (
                    # 使缓存失效
                    st.session_state.update({'filter_cache_invalid': True, 'error_cache_invalid': True}),
                    # 生成新批次
                    generate_new_batch() if st.session_state.current_mode == "normal" else generate_error_batch()
                )
            )
            
            # 学习进度显示
            st.markdown("---")
            st.subheader("📊 学习进度")
            total_q = TOTAL_QUESTIONS
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
            
            # 高级操作
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
                st.button("📚 去错题本", type="secondary", help="点击上方「错题本」标签页查看")
            return

        current_batch = st.session_state.current_batch
        current_idx = st.session_state.current_question_idx

        # 批次完成处理
        if current_idx >= len(current_batch):
            # 强制保存当前批次的所有进度
            progress_to_save = {
                "correct_ids": st.session_state.correct_ids,
                "incorrect_ids": st.session_state.incorrect_ids,
                "error_counts": st.session_state.error_counts,
                "last_wrong_answers": st.session_state.last_wrong_answers
            }
            save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id, force_save=True)
            
            st.success("✅ 本轮批次完成！正在生成新批次...")
            if st.session_state.current_mode == "normal":
                generate_new_batch()
            else:
                generate_error_batch()  # 自动处理无错题的情况
            st.rerun()

        current_question = current_batch[current_idx]
        question_id = current_question['id']
        is_multiple = current_question['is_multiple']  # 获取是否为多选题
        
        st.subheader(f"本轮进度：{current_idx + 1}/{len(current_batch)} 题")
        st.write(f"### {current_question['question']}")
        
        # 显示题型提示
        if is_multiple:
            st.warning("📌 本题为多选题：请选择所有正确答案（支持多选）")
        else:
            st.info("📌 本题为单选题：请选择唯一正确答案")

        is_submitted = question_id in st.session_state.submitted_answers
        user_answer_data = st.session_state.submitted_answers.get(question_id)

        # 自适应渲染单选/多选组件
        if not is_submitted:
            # 提交答案的通用函数
            def submit_answer():
                # 检查答案是否已经提交，避免重复提交
                if question_id in st.session_state.submitted_answers:
                    return
                    
                if is_multiple:
                    # 收集多选题用户选择
                    selected_options = []
                    for opt in current_question["options"]:
                        key = f"q_{question_id}_opt_{opt[:5]}"
                        if key in st.session_state and st.session_state[key]:
                            selected_options.append(opt)
                    user_answer = selected_options
                    
                    # 空答案校验
                    if len(user_answer) == 0:
                        st.warning("⚠️ 请选择至少一个答案后提交！")
                        return
                else:
                    # 获取单选题用户选择
                    key = f"q_{question_id}"
                    user_answer = st.session_state.get(key, None)
                    
                    # 空答案校验
                    if user_answer is None:
                        return  # 单选题空答案不提交
                
                st.session_state.submitted_answers[question_id] = user_answer
                
                # 答案正确性校验
                if is_multiple:
                    # 多选题：提取用户选择的字母集合 vs 正确答案集合
                    user_answer_letters = set([opt.split(".")[0].strip().upper() for opt in user_answer])
                    correct_letters = current_question["answer"]
                    is_correct = user_answer_letters == correct_letters
                else:
                    # 单选题：原有校验逻辑
                    user_answer_letter = user_answer.split(".")[0].strip().upper()
                    is_correct = user_answer_letter == current_question["answer"]
                
                # 更新学习进度
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
                
                # 更新答题计数
                st.session_state['answer_count'] = st.session_state.get('answer_count', 0) + 1
                
                # 保存进度（使用批量保存机制）
                progress_to_save = {
                    "correct_ids": st.session_state.correct_ids,
                    "incorrect_ids": st.session_state.incorrect_ids,
                    "error_counts": st.session_state.error_counts,
                    "last_wrong_answers": st.session_state.last_wrong_answers
                }
                save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id)
                
                # 使缓存失效，下次生成批次时重新过滤
                st.session_state.update({'filter_cache_invalid': True, 'error_cache_invalid': True})
            
            if is_multiple:
                # 多选题：使用复选框组件，选择后不立即提交
                for opt in current_question["options"]:
                    st.checkbox(
                        opt,
                        key=f"q_{question_id}_opt_{opt[:5]}"
                    )
                # 多选题添加提交按钮
                st.button(
                    "📤 提交答案",
                    on_click=submit_answer,
                    type="primary"
                )
            else:
                # 单选题：使用单选组件，选择后直接提交
                user_answer = st.radio(
                    "请选择答案：",
                    current_question["options"],
                    key=f"q_{question_id}",
                    index=None
                )
                # 单选题直接检查答案变化
                if user_answer is not None:
                    # 直接执行提交（单选只有一个选择，不需要防抖）
                    if question_id not in st.session_state.submitted_answers:
                        st.session_state.submitted_answers[question_id] = user_answer
                        
                        # 答案正确性校验
                        user_answer_letter = user_answer.split(".")[0].strip().upper()
                        is_correct = user_answer_letter == current_question["answer"]
                        
                        # 更新学习进度
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
                        
                        # 更新答题计数
                        st.session_state['answer_count'] = st.session_state.get('answer_count', 0) + 1
                        
                        # 保存进度
                        progress_to_save = {
                            "correct_ids": st.session_state.correct_ids,
                            "incorrect_ids": st.session_state.incorrect_ids,
                            "error_counts": st.session_state.error_counts,
                            "last_wrong_answers": st.session_state.last_wrong_answers
                        }
                        save_progress(st.session_state.user_id, progress_to_save, st.session_state.user_row_id)
                        
                        # 使缓存失效，下次生成批次时重新过滤
                        st.session_state.update({'filter_cache_invalid': True, 'error_cache_invalid': True})
                        
                        # 使用st.rerun()刷新页面，显示结果
                        st.rerun()
        else:# 已提交：禁用组件，显示用户之前的选择
            if is_multiple:
                for opt in current_question["options"]:
                    is_checked = opt in user_answer_data
                    st.checkbox(
                        opt,
                        value=is_checked,
                        disabled=True,
                        key=f"q_{question_id}_opt_{opt[:5]}"
                    )
            else:
                st.radio(
                    "你的答案：",
                    current_question["options"],
                    key=f"q_{question_id}",
                    index=current_question["options"].index(user_answer_data) if user_answer_data else None,
                    disabled=True
                )
            
            # 核心修改5：提交后展示正确/错误结果（适配单选/多选）
            st.divider()
            if is_multiple:
                # 多选题结果展示
                user_answer_letters = set([opt.split(".")[0].strip().upper() for opt in user_answer_data])
                correct_letters = current_question["answer"]
                is_correct = user_answer_letters == correct_letters
                
                if is_correct:
                    st.success("🎉 回答正确！")
                else:
                    st.error("❌ 回答错误！")
                
                # 拼接多选题正确答案文本
                correct_answer_texts = [opt for opt in current_question["options"] 
                                        if opt.split(".")[0].strip().upper() in correct_letters]
                st.markdown(f"**正确答案：** <span style='color:green'>{', '.join(correct_answer_texts)}</span>", unsafe_allow_html=True)
            else:
                # 单选题结果展示（原有逻辑）
                user_answer_letter = user_answer_data.split(".")[0].strip().upper()
                correct_answer_letter = current_question["answer"]
                is_correct = user_answer_letter == correct_answer_letter
                
                if is_correct:
                    st.success("🎉 回答正确！")
                else:
                    st.error("❌ 回答错误！")
                
                correct_answer_text = next((opt for opt in current_question["options"] if opt.strip().startswith(correct_answer_letter)), "【未找到】")
                st.markdown(f"**正确答案：** <span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
            
            # 显示解析
            if current_question.get("explanation"):
                st.markdown("---")
                st.info(f"📖 解析：{current_question['explanation']}")
            
            # 下一题按钮
            st.button("➡️ 下一题", on_click=lambda: st.session_state.update({"current_question_idx": current_idx + 1}), type="primary")

    # 错题本标签页（核心修改6：适配多选题错题展示）
    with tab2:
        st.header("📚 错题本管理")
        st.markdown("---")
        
        error_ids = list(st.session_state.error_counts.keys())
        error_ids_int = [int(q_id) for q_id in error_ids if q_id.isdigit()]
        all_questions = st.session_state.all_questions
        error_questions = [q for q in all_questions if q['id'] in error_ids_int]
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("总错题数", len(error_questions))
        with col_stat2:
            max_error = max(st.session_state.error_counts.values()) if error_ids else 0
            st.metric("最高错误次数", max_error)
        with col_stat3:
            mastered_error = len([q for q in error_questions if q['id'] in st.session_state.correct_ids])
            st.metric("已订正错题", mastered_error)
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            if st.button("🚀 专项练习错题", type="primary", disabled=len(error_questions)==0):
                generate_error_batch()
                st.success("✅ 错题练习批次已生成！请切换到「答题练习」标签页开始练习～")
        with col_btn2:
            if st.button("🧹 清空已订正错题", type="secondary", disabled=mastered_error==0):
                new_error_counts = {}
                new_last_wrong = {}
                for q_id in error_ids:
                    q_id_int = int(q_id) if q_id.isdigit() else -1
                    if q_id_int not in st.session_state.correct_ids:
                        new_error_counts[q_id] = st.session_state.error_counts[q_id]
                        new_last_wrong[q_id] = st.session_state.last_wrong_answers.get(q_id, "")
                
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
            st.button("📝 返回答题练习", type="secondary", help="点击上方「答题练习」标签页继续")
        
        st.markdown("---")
        
        if error_questions:
            page_size = 10
            total_pages = (len(error_questions) + page_size - 1) // page_size
            
            col_page1, col_page2 = st.columns([8,2])
            with col_page1:
                page_num = st.selectbox("选择页码", range(1, total_pages+1), label_visibility="collapsed")
            with col_page2:
                st.write(f"第 {page_num}/{total_pages} 页")
            
            current_page_errors, total_errors = paginate_list(error_questions, page_num, page_size)
            
            for idx, q in enumerate(current_page_errors):
                q_id_str = str(q['id'])
                error_count = st.session_state.error_counts.get(q_id_str, 0)
                last_wrong = st.session_state.last_wrong_answers.get(q_id_str, "")
                is_multiple = q['is_multiple']
                
                with st.expander(f"📌 错题 {page_size*(page_num-1)+idx+1} | 错误 {error_count} 次 | 题干：{q['question'][:50]}..."):
                    st.write(f"### 题干：{q['question']}")
                    
                    st.write("#### 选项：")
                    for opt in q['options']:
                        # 适配多选题错误答案展示
                        if is_multiple:
                            if isinstance(last_wrong, list) and opt in last_wrong:
                                st.markdown(f"- ❌ {opt}", unsafe_allow_html=True)
                            else:
                                st.write(f"- {opt}")
                        else:
                            if opt == last_wrong:
                                st.markdown(f"- ❌ {opt}", unsafe_allow_html=True)
                            else:
                                st.write(f"- {opt}")
                    
                    # 适配多选题正确答案展示
                    if is_multiple:
                        correct_answer_texts = [opt for opt in q["options"] 
                                                if opt.split(".")[0].strip().upper() in q["answer"]]
                        st.markdown(f"#### ✅ 正确答案：<span style='color:green'>{', '.join(correct_answer_texts)}</span>", unsafe_allow_html=True)
                    else:
                        correct_answer_text = next((opt for opt in q["options"] if opt.strip().startswith(q["answer"])), "【未找到】")
                        st.markdown(f"#### ✅ 正确答案：<span style='color:green'>{correct_answer_text}</span>", unsafe_allow_html=True)
                    
                    if q.get("explanation"):
                        st.markdown(f"#### 📖 解析：{q['explanation']}", unsafe_allow_html=True)
                    
                    if st.button(f"✅ 标记为已掌握", key=f"master_{q['id']}"):
                        st.session_state.correct_ids.add(q['id'])
                        st.session_state.incorrect_ids.discard(q['id'])
                        st.session_state.error_counts.pop(q_id_str, None)
                        st.session_state.last_wrong_answers.pop(q_id_str, None)
                        
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
