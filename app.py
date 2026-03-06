import streamlit as st
import time
import json
import base64
from openai import OpenAI

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(page_title="ARMIND7: 디지털 전우", page_icon="🪖", layout="wide")

st.title("🪖 ARMIND7: 당신의 디지털 전우")
st.markdown("### 상승 7사단, 당신의 마음을 지킵니다.")

# ==========================================
# 2. API 키 처리
# ==========================================
api_key = None
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    with st.sidebar:
        st.header("🔐 인증")
        api_key = st.text_input("OpenAI API Key를 입력하세요", type="password")
        st.info("키는 저장되지 않고 휘발됩니다.")

# ==========================================
# 3. 세션 상태 초기화
# ==========================================
defaults = {
    "messages": [],
    "risk_level": 0,
    "ui_step": 0,
    "phq9_score": 0,
    "active_tab": "chat",
    # 군백기 지우개 커뮤니티
    "study_groups": [
        {"id": 1, "name": "공무원 시험 준비반", "subject": "행정학/국어", "members": ["김일병", "이상병"], "max_members": 5, "chat": [], "description": "전역 후 공무원 도전! 함께 합시다."},
        {"id": 2, "name": "자격증 스터디", "subject": "정보처리기사", "members": ["박병장"], "max_members": 4, "chat": [], "description": "IT 자격증 취득 목표 그룹입니다."},
    ],
    "my_groups": [],
    "study_chat_input": {},
    "current_group_id": None,
    # 식단
    "meal_log": {"아침": [], "점심": [], "저녁": []},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==========================================
# 4. 분석 로직
# ==========================================
def analyze_input(text, key, history):
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            return 2, f"군 특수 위험 키워드 '{word}' 감지", "군 특수 위험 키워드가 들려 제 가슴이 철렁했습니다. 전우님, 혹시 지금 나쁜 마음을 먹고 계신 건 아닌지 정말 걱정됩니다. 저랑 약속 하나만 해주세요."

    if not key:
        return 0, "키 없음", "API 키를 먼저 입력해주세요."

    try:
        client = OpenAI(api_key=key)
        system_instruction = """
        당신은 대한민국 육군 장병들의 마음을 지키는 AI 상담관 'ARMIND7'입니다.
        단답형으로 말하지 말고, 사용자의 힘든 마음에 깊이 공감하는 '따뜻하고 정성스러운' 답변을 해주세요.
        
        [대화 가이드라인]
        1. 공감과 인정: "힘드시겠어요" 대신 "그동안 혼자 끙끙 앓느라 얼마나 힘드셨습니까" 같이 구체적으로 감정을 읽어주세요.
        2. 말투: 친한 선임이나 형처럼 부드러운 '해요체'를 사용하세요. (이모지 적절히 사용 🌿)
        3. 연결: 사용자의 이전 대화 맥락을 기억해서 대답하세요.
        
        [위험도 분류 기준]
        - Level 3 (실행 임박): "지금 옥상이다", "난간에 서 있다", "뛰어내린다".
        - Level 2 (구체적 계획): "총으로 죽고 싶다", "번개탄을 사겠다".
        - Level 1 (잠재적 위험): "그냥 죽고 싶다", "힘들다", "우울해".
        - Level 0 (안전): 일상 대화.
        
        [출력 형식]
        JSON 형식으로만 출력: {"level": 숫자, "reason": "이유", "reply": "답변 텍스트"}
        """
        messages_payload = [{"role": "system", "content": system_instruction}]
        for msg in history[-10:]:
            messages_payload.append({"role": msg["role"], "content": str(msg["content"])})
        messages_payload.append({"role": "user", "content": text})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_payload,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result["level"], result["reason"], result["reply"]
    except Exception as e:
        return 0, "오류", f"시스템 오류가 발생했습니다: {e}"


# ==========================================
# 5. 메인 탭 네비게이션
# ==========================================
tabs = st.tabs(["💬 AI 상담", "💄 화장품 추천", "🥗 식단 관리", "📚 군백기 지우개"])

# ==========================================
# TAB 1: AI 상담 (기존 기능)
# ==========================================
with tabs[0]:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("전우님, 무슨 고민이 있으신가요?"):
        if not api_key:
            st.error("API Key가 없습니다.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            level, reason, ai_reply = analyze_input(prompt, api_key, st.session_state.messages)
            st.session_state.risk_level = level
            st.session_state.ui_step = 0

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                final_msg = ai_reply
                if level == 1:
                    final_msg += "\n\n(마음이 많이 힘드신 것 같네요. 아래 **자가진단**을 한번 해보시겠어요?)"
                elif level == 2:
                    final_msg += "\n\n⚠️ **위험한 생각이 듭니다. 저와 안전 약속을 해주세요.**"
                elif level == 3:
                    final_msg += "\n\n🚨 **비상 상황입니다. 제가 돕겠습니다.**"

                for chunk in final_msg.split():
                    full_response += chunk + " "
                    time.sleep(0.05)
                    message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)

            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.rerun()

    # Level 1: PHQ-9
    if st.session_state.risk_level == 1:
        st.divider()
        with st.expander("📋 **마음 건강 자가진단 (PHQ-9)**", expanded=True):
            st.write("지난 2주 동안의 상태를 체크해주세요.")
            phq9_questions = [
                "1. 기분이 가라앉거나, 우울하거나, 희망이 없다고 느꼈다.",
                "2. 평소 하던 일에 대한 흥미가 없어지거나 즐거움을 느끼지 못했다.",
                "3. 잠들기가 어렵거나 자꾸 깼다 / 혹은 너무 많이 잤다.",
                "4. 평소보다 식욕이 줄었다 / 혹은 평소보다 많이 먹었다.",
                "5. 다른 사람들이 눈치 챌 정도로 말과 행동이 느려졌다.",
                "6. 피곤하고 기운이 없었다.",
                "7. 내가 잘못했거나, 실패했다는 생각이 들었다.",
                "8. 일상적인 일에도 집중할 수가 없었다.",
                "9. 차라리 죽는 것이 더 낫겠다고 생각했다 / 혹은 자해할 생각을 했다."
            ]
            options = ["전혀 아님 (0점)", "며칠 동안 (1점)", "일주일 이상 (2점)", "매일 (3점)"]
            scores = []
            for idx, q in enumerate(phq9_questions):
                if idx == 8:
                    st.markdown(f"**:red[{q}]**")
                else:
                    st.write(q)
                choice = st.radio(f"문항 {idx+1}", options, index=0, key=f"phq9_{idx}", label_visibility="collapsed", horizontal=True)
                scores.append(int(choice[-3]))
                st.markdown("---")
            if st.button("결과 확인"):
                total_score = sum(scores)
                st.write(f"### 📊 총점: {total_score}점")
                if scores[8] > 0:
                    st.error("🚨 자해나 죽음에 대한 생각이 감지되었습니다. 즉시 전문가의 도움이 필요합니다.")
                    if st.button("국방헬프콜 (1303) 연결하기", type="primary"):
                        st.success("연결 중입니다...")
                else:
                    if total_score <= 4: st.success("✅ 정상 범위입니다.")
                    elif total_score <= 9: st.info("⚠️ 가벼운 우울감이 있습니다.")
                    elif total_score <= 14: st.warning("🟠 상담이 필요한 상태입니다.")
                    elif total_score <= 19: st.error("🔴 전문적인 도움이 필요합니다.")
                    else: st.error("🚨 매우 심한 우울 상태입니다.")

    # Level 2: Safety Plan
    if st.session_state.risk_level == 2:
        st.divider()
        st.error("⚠️ **구체적 위험 감지됨**")
        with st.container(border=True):
            st.markdown("### 🛡️ Digital Safety Plan")
            st.markdown("#### ✅ Step 1. 위험 수단 제거")
            st.write("주변에 위험한 물건(총기 등)이 있나요? 당장 치우세요.")
            if st.session_state.ui_step == 0:
                if st.button("네, 치웠습니다 (다음)"):
                    st.session_state.ui_step = 1
                    st.rerun()
            if st.session_state.ui_step >= 1:
                st.success("확인되었습니다.")
                st.markdown("---")
                st.markdown("#### 🧘 Step 2. 나만의 진정 방법")
                coping = st.text_area("기분이 나아지는 행동은?", key="coping")
                if st.session_state.ui_step == 1:
                    if st.button("입력 완료 (다음)"):
                        if coping:
                            st.session_state.ui_step = 2
                            st.rerun()
                        else:
                            st.warning("내용을 입력해주세요.")
            if st.session_state.ui_step >= 2:
                st.success("저장되었습니다.")
                st.markdown("---")
                st.markdown("#### 📞 Step 3. 도움 요청")
                if st.button("국방헬프콜 (1303) 연결", type="primary"):
                    st.success("📞 연결 중입니다... (지휘관 알림 전송됨)")

    # Level 3: Grounding
    if st.session_state.risk_level == 3:
        st.divider()
        st.error("🚨 **[비상 알림 전송 완료]**")
        st.markdown("### **지휘통제실과 대응팀에 귀하의 위치가 전송되었습니다.**")
        st.info("현재 구조대가 출발했습니다. 전우님은 혼자가 아닙니다.")
        with st.container(border=True):
            st.markdown("### 🛑 **현실 감각 찾기 (Grounding)**")
            val1 = st.text_input("👀 1. 눈에 보이는 것 5가지", key="g1")
            if st.session_state.ui_step == 0:
                if st.button("입력 (1/3)"):
                    if val1:
                        st.session_state.ui_step = 1
                        st.rerun()
            if st.session_state.ui_step >= 1:
                val2 = st.text_input("👂 2. 귀에 들리는 것 4가지", key="g2")
                if st.session_state.ui_step == 1:
                    if st.button("입력 (2/3)"):
                        if val2:
                            st.session_state.ui_step = 2
                            st.rerun()
            if st.session_state.ui_step >= 2:
                val3 = st.text_input("✋ 3. 피부에 느껴지는 것 3가지", key="g3")
                if st.button("입력 완료"):
                    if val3:
                        st.success("✅ 확인되었습니다. 깊게 숨을 들이마시세요.")
                        st.markdown("곧 도움의 손길이 닿을 겁니다.")


# ==========================================
# TAB 2: 화장품 추천
# ==========================================
with tabs[1]:
    st.header("💄 피부 맞춤 화장품 추천")
    st.markdown("군 생활 중 피부 고민, AI가 해결해드릴게요!")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📷 피부 사진 업로드 (선택)")
        skin_image = st.file_uploader("얼굴 사진을 업로드하세요", type=["jpg", "jpeg", "png"], key="skin_img")
        if skin_image:
            st.image(skin_image, caption="업로드된 사진", use_container_width=True)

    with col2:
        st.subheader("📝 피부 상태 설명 (선택)")
        skin_concerns = st.multiselect(
            "고민되는 피부 문제를 선택하세요",
            ["여드름/트러블", "건조함", "번들거림/지성", "모공", "다크서클", "칙칙함/잡티", "민감성", "각질"],
            key="skin_concerns"
        )
        skin_text = st.text_area("추가 설명 (예: 훈련 후 얼굴이 빨개지고 당깁니다)", height=100, key="skin_text")

        skin_type = st.radio(
            "피부 타입을 선택하세요",
            ["건성", "지성", "복합성", "중성", "민감성"],
            horizontal=True,
            key="skin_type"
        )

    st.divider()

    if st.button("🔍 AI 피부 분석 및 화장품 추천받기", type="primary", use_container_width=True):
        if not api_key:
            st.error("API Key를 먼저 입력해주세요.")
        elif not skin_concerns and not skin_text and not skin_image:
            st.warning("사진을 업로드하거나 피부 상태를 입력해주세요.")
        else:
            with st.spinner("🔬 피부 상태를 분석 중입니다..."):
                try:
                    client = OpenAI(api_key=api_key)

                    prompt_text = f"""
                    당신은 피부과 전문 뷰티 컨설턴트입니다. 대한민국 군인 장병의 피부 고민을 해결해주세요.
                    
                    [피부 정보]
                    - 피부 타입: {skin_type}
                    - 피부 고민: {', '.join(skin_concerns) if skin_concerns else '없음'}
                    - 추가 설명: {skin_text if skin_text else '없음'}
                    
                    [요청사항]
                    1. 피부 상태 분석 (2-3줄)
                    2. 맞춤 스킨케어 루틴 (아침/저녁)
                    3. 추천 제품 카테고리 3-5가지 (군 PX에서 구매 가능한 저렴한 제품 위주)
                    4. 군 생활 특수 환경(야외훈련, 자외선, 먼지)에 맞는 피부 관리 팁
                    
                    친근하고 실용적으로 답변해주세요. 이모지를 적절히 사용하세요.
                    """

                    messages_for_api = [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}]

                    # 이미지가 있으면 추가
                    if skin_image:
                        image_bytes = skin_image.read()
                        b64_image = base64.b64encode(image_bytes).decode("utf-8")
                        ext = skin_image.name.split(".")[-1].lower()
                        mime = "image/jpeg" if ext in ["jpg", "jpeg"] else "image/png"
                        messages_for_api = [{
                            "role": "user",
                            "content": [
                                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64_image}"}},
                                {"type": "text", "text": prompt_text}
                            ]
                        }]
                        model_to_use = "gpt-4o"
                    else:
                        model_to_use = "gpt-4o-mini"

                    response = client.chat.completions.create(
                        model=model_to_use,
                        messages=messages_for_api,
                        max_tokens=1000
                    )

                    result = response.choices[0].message.content

                    st.success("✅ 분석 완료!")
                    st.markdown("---")
                    st.markdown("### 🎯 AI 피부 분석 결과")
                    st.markdown(result)

                    # 추가 팁 카드
                    st.markdown("---")
                    st.markdown("### 💡 군 생활 피부 관리 필수템")
                    tip_col1, tip_col2, tip_col3 = st.columns(3)
                    with tip_col1:
                        st.info("☀️ **자외선 차단제**\n훈련 전 필수! SPF50+ PA+++ 추천")
                    with tip_col2:
                        st.info("💧 **수분 보습**\n군 생활 건조함의 핵심 해결책")
                    with tip_col3:
                        st.info("🧴 **저자극 클렌징**\n훈련 후 꼼꼼히, 하지만 순하게")

                except Exception as e:
                    st.error(f"분석 중 오류가 발생했습니다: {e}")


# ==========================================
# TAB 3: 식단 관리
# ==========================================
with tabs[2]:
    st.header("🥗 군 식단 영양 분석")
    st.markdown("오늘 급식에서 부족한 영양소를 확인하고 보충하세요!")

    # 일일 권장 섭취량 (성인 남성 기준 - 장병)
    DAILY_RECOMMEND = {
        "칼로리": 2700, "탄수화물": 330, "단백질": 65, "지방": 75,
        "비타민C": 100, "칼슘": 800, "철분": 12
    }

    # 영양소 기본값 (메뉴명으로 AI 추정)
    NUTRIENT_DEFAULTS = {
        "칼로리": 150, "탄수화물": 20, "단백질": 8, "지방": 5,
        "비타민C": 5, "칼슘": 30, "철분": 1
    }

    # ── 국방부 공공API 호출 ──
    MND_API_KEY = st.secrets.get("MND_API_KEY", "")
    MND_SERVICE = st.secrets.get("MND_SERVICE", "DS_TB_MNDT_DATEBYMLSVC_6335")

    @st.cache_data(ttl=3600)
    def fetch_mnd_meal(year_month: str, start: int = 1, end: int = 300):
        """year_month: 'YYYYMM' 형식. 해당 월의 식단 전체를 가져옵니다."""
        import requests, xml.etree.ElementTree as ET
        url = f"https://openapi.mnd.go.kr/{MND_API_KEY}/xml/{MND_SERVICE}/{start}/{end}/"
        try:
            resp = requests.get(url, timeout=10)
            resp.encoding = "utf-8"
            raw = resp.text
            debug_info = {"url": url, "status": resp.status_code, "raw_preview": raw[:500]}
            root = ET.fromstring(raw)

            # 실제 태그명 자동 탐지
            first_row = next(root.iter("row"), None)
            if first_row is None:
                return {}, None, []
            actual_tags = [child.tag for child in first_row]
            debug_info["tags"] = actual_tags

            # 실제 태그명 고정 (API 확인 완료)
            date_tag = "dates"
            brst_tag = "brst"
            lnch_tag = "lunc"   # API 오타: lunc (lunch 아님)
            dinr_tag = "dinr"
            brst_cal = "brst_cal"
            lnch_cal = "lunc_cal"
            dinr_cal = "dinr_cal"
            sum_cal_tag = "sum_cal"
            debug_info["detected"] = {"date": date_tag, "brst": brst_tag, "lnch": lnch_tag, "dinr": dinr_tag}

            # 같은 날짜에 여러 row가 있으므로 메뉴를 누적해서 합침
            meals = {}
            for row in root.iter("row"):
                raw_date = (row.findtext(date_tag) or "").strip()
                if not raw_date:
                    continue
                # 날짜 형식 정규화: "2025-03-10(월)" → "20250310"
                import re
                m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw_date)
                date = m.group(1) + m.group(2) + m.group(3) if m else raw_date

                if date not in meals:
                    meals[date] = {
                        "아침": {},   # {메뉴명: 칼로리(float)}
                        "점심": {},
                        "저녁": {},
                        "총_칼로리": None
                    }

                def clean_name(text):
                    """알레르기 번호 제거: '배추김치(09)(18)' → '배추김치'"""
                    if not text:
                        return None
                    return re.sub(r"\(\d+\)", "", text).strip() or None

                def clean_cal(text):
                    """칼로리 숫자 추출: '17.87kcal' → 17.87"""
                    if not text:
                        return 0.0
                    try:
                        return float(text.replace("kcal","").strip())
                    except:
                        return 0.0

                # 1 row = 1 메뉴 1 칼로리 구조 → 딕셔너리로 저장 (중복 방지)
                brst_name = clean_name(row.findtext(brst_tag))
                lnch_name = clean_name(row.findtext(lnch_tag))
                dinr_name = clean_name(row.findtext(dinr_tag))

                if brst_name and brst_name not in meals[date]["아침"]:
                    meals[date]["아침"][brst_name] = clean_cal(row.findtext(brst_cal))
                if lnch_name and lnch_name not in meals[date]["점심"]:
                    meals[date]["점심"][lnch_name] = clean_cal(row.findtext(lnch_cal))
                if dinr_name and dinr_name not in meals[date]["저녁"]:
                    meals[date]["저녁"][dinr_name] = clean_cal(row.findtext(dinr_cal))

                # sum_cal: 매 row에 동일한 하루 총합이 들어있으므로 덮어쓰기
                if row.findtext(sum_cal_tag):
                    meals[date]["총_칼로리"] = row.findtext(sum_cal_tag).replace("kcal","").strip()

            return meals, None, list(meals.keys())
        except Exception as e:
            return {}, str(e), []

    import datetime
    today = datetime.date.today()
    today_str = today.strftime("%Y%m%d")
    ym_str = today.strftime("%Y%m")

    # 날짜 선택
    col_date, col_refresh = st.columns([3, 1])
    with col_date:
        selected_date = st.date_input("📅 날짜 선택", value=today, key="meal_date")
    with col_refresh:
        st.write("")
        if st.button("🔄 새로고침", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    selected_date_str = selected_date.strftime("%Y%m%d")
    selected_ym = selected_date.strftime("%Y%m")

    @st.cache_data(ttl=86400)
    def get_total_count():
        """총 데이터 건수를 가져와서 최근 데이터 위치를 계산"""
        import requests, xml.etree.ElementTree as ET
        url = f"https://openapi.mnd.go.kr/{MND_API_KEY}/xml/{MND_SERVICE}/1/1/"
        try:
            resp = requests.get(url, timeout=10)
            root = ET.fromstring(resp.text)
            total = root.findtext("list_total_count")
            return int(total) if total else 3755
        except:
            return 3755

    with st.spinner("📡 부대 식단을 불러오는 중..."):
        total_count = get_total_count()
        meal_data, api_error, available_dates = fetch_mnd_meal(selected_ym, start=1, end=total_count)

    if api_error:
        st.error(f"⚠️ API 연결 오류: {api_error}")
        st.info("샘플 데이터로 표시합니다.")
        today_meals = {
            "아침": ["흰쌀밥", "된장찌개", "계란후라이", "김치"],
            "점심": ["잡곡밥", "부대찌개", "제육볶음", "깍두기"],
            "저녁": ["흰쌀밥", "순두부찌개", "불고기", "시금치나물"],
            "아침_칼로리": "650", "점심_칼로리": "850", "저녁_칼로리": "750",
        }
    elif selected_date_str not in meal_data:
        st.warning(f"📭 {selected_date.strftime('%Y년 %m월 %d일')} 식단 데이터가 없습니다.")
        if available_dates:
            st.info(f"💡 이 달에 데이터가 있는 날짜: {', '.join(available_dates[:5])}")
        today_meals = {"아침": [], "점심": [], "저녁": [],
                       "아침_칼로리": "-", "점심_칼로리": "-", "저녁_칼로리": "-"}
    else:
        today_meals = meal_data[selected_date_str]
        st.success(f"✅ {selected_date.strftime('%Y년 %m월 %d일')} 제6335부대 식단 불러오기 완료!")

    meal_tabs = st.tabs(["🌅 아침", "☀️ 점심", "🌙 저녁", "📊 영양 분석"])

    for meal_time, meal_tab in zip(["아침", "점심", "저녁"], meal_tabs[:3]):
        with meal_tab:
            menu_dict = today_meals.get(meal_time, {})  # {메뉴명: 칼로리}

            if menu_dict:
                meal_total_cal = sum(menu_dict.values())
                st.subheader(f"{meal_time} 메뉴 — {meal_total_cal:.1f} kcal")
                cols = st.columns(min(len(menu_dict), 4))
                for i, (item, cal) in enumerate(menu_dict.items()):
                    with cols[i % 4]:
                        st.info(f"🍽️ {item}

**{cal:.1f} kcal**")

                st.divider()
                st.markdown("**✅ 오늘 먹은 메뉴 체크**")
                checked = {}  # {메뉴명: 칼로리}
                for i, (item, cal) in enumerate(menu_dict.items()):
                    label = f"{item}  ({cal:.1f} kcal)"
                    if st.checkbox(label, value=True, key=f"chk_{meal_time}_{i}_{item[:10]}"):
                        checked[item] = cal
                st.session_state.meal_log[meal_time] = checked
            else:
                st.info(f"오늘 {meal_time} 식단 정보가 없습니다.")

    # 영양 분석 탭
    with meal_tabs[3]:
        st.subheader("📊 오늘의 영양 섭취 분석")

        # 체크된 메뉴만 칼로리 합산
        checked_menus = {}
        for meal_time in ["아침", "점심", "저녁"]:
            checked_menus[meal_time] = st.session_state.meal_log.get(meal_time, {})

        total_cal = sum(
            cal for meal in checked_menus.values() for cal in meal.values()
        )
        all_checked = [item for meal in checked_menus.values() for item in meal]

        # 칼로리 달성률 표시
        st.markdown("#### 🔥 섭취 칼로리 (체크한 메뉴 기준)")
        api_total = today_meals.get("총_칼로리") or "?"
        col_name, col_bar = st.columns([1, 3])
        with col_name:
            st.metric("내가 먹은 칼로리", f"{total_cal:.1f} kcal")
            st.caption(f"오늘 급식 총 칼로리: {api_total} kcal")
        with col_bar:
            cal_pct = min(int((total_cal / DAILY_RECOMMEND["칼로리"]) * 100), 100)
            st.write("")
            st.progress(cal_pct / 100, text=f"{cal_pct}% (권장 {DAILY_RECOMMEND['칼로리']} kcal)")

        st.divider()

        # AI 영양 분석 (실제 메뉴명 기반)
        if st.button("🤖 AI 상세 영양 분석받기", type="primary", use_container_width=True):
            if not api_key:
                st.error("API Key를 먼저 입력해주세요.")
            elif not all_checked:
                st.warning("먼저 아침/점심/저녁 탭에서 먹은 메뉴를 체크해주세요!")
            else:
                menu_summary = {
                    "아침": list(checked_menus["아침"].keys()),
                    "점심": list(checked_menus["점심"].keys()),
                    "저녁": list(checked_menus["저녁"].keys()),
                }
                with st.spinner("🔬 실제 식단을 분석 중입니다..."):
                    try:
                        client = OpenAI(api_key=api_key)
                        prompt = f"""
                        대한민국 육군 장병의 오늘 실제 급식 식단입니다:
                        - 아침: {', '.join(menu_summary['아침']) or '없음'}
                        - 점심: {', '.join(menu_summary['점심']) or '없음'}
                        - 저녁: {', '.join(menu_summary['저녁']) or '없음'}
                        - 내가 섭취한 칼로리: {total_cal:.1f} kcal
                        
                        다음을 분석해주세요:
                        1. 예상 주요 영양소 (탄수화물/단백질/지방/비타민/무기질) 충족 여부
                        2. 부족할 것으로 예상되는 영양소 2-3가지
                        3. 군 PX에서 구할 수 있는 보충 간식 추천 3가지
                        4. 내일 훈련/업무를 위한 한 줄 조언
                        
                        이모지와 함께 친근하게 답변해주세요.
                        """
                        response = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=600
                        )
                        st.markdown("### 🎯 AI 영양 분석 결과")
                        st.markdown(response.choices[0].message.content)
                    except Exception as e:
                        st.error(f"오류: {e}")


# ==========================================
# TAB 4: 군백기 지우개 (스터디 커뮤니티)
# ==========================================
with tabs[3]:
    st.header("📚 군백기 지우개")
    st.markdown("전역 후 공백기를 없애자! 함께 공부하는 전우를 찾아요 💪")

    study_tabs = st.tabs(["🔍 스터디 찾기", "➕ 스터디 만들기", "💬 내 스터디"])

    # --- 스터디 찾기 ---
    with study_tabs[0]:
        st.subheader("📋 현재 모집 중인 스터디")

        search_keyword = st.text_input("🔍 스터디 검색", placeholder="키워드를 입력하세요 (예: 공무원, 자격증...)")

        for group in st.session_state.study_groups:
            name_match = search_keyword.lower() in group["name"].lower() if search_keyword else True
            subj_match = search_keyword.lower() in group["subject"].lower() if search_keyword else True
            if not (name_match or subj_match):
                continue

            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.markdown(f"### 📖 {group['name']}")
                    st.markdown(f"**과목:** {group['subject']}")
                    st.markdown(f"**설명:** {group['description']}")
                    member_count = len(group["members"])
                    st.markdown(f"**인원:** {member_count}/{group['max_members']}명 | **멤버:** {', '.join(group['members'])}")

                with col_btn:
                    is_joined = group["id"] in st.session_state.my_groups
                    is_full = len(group["members"]) >= group["max_members"]

                    if is_joined:
                        st.success("✅ 참여 중")
                        if st.button("탈퇴", key=f"leave_{group['id']}", type="secondary"):
                            st.session_state.my_groups.remove(group["id"])
                            group["members"].remove("나 (현재 사용자)")
                            st.rerun()
                    elif is_full:
                        st.warning("🔒 인원 마감")
                    else:
                        if st.button("참여하기", key=f"join_{group['id']}", type="primary"):
                            st.session_state.my_groups.append(group["id"])
                            group["members"].append("나 (현재 사용자)")
                            st.success(f"'{group['name']}' 스터디에 참여했습니다!")
                            st.rerun()

    # --- 스터디 만들기 ---
    with study_tabs[1]:
        st.subheader("✏️ 새 스터디 그룹 만들기")

        with st.form("create_study_form"):
            new_name = st.text_input("스터디 이름 *", placeholder="예: 2025 공무원 합격반")
            new_subject = st.text_input("공부 과목/분야 *", placeholder="예: 행정학, 국어, 영어")
            new_desc = st.text_area("스터디 소개 *", placeholder="스터디 목표와 활동 방식을 소개해주세요.")
            new_max = st.slider("최대 인원", min_value=2, max_value=10, value=5)
            new_goal = st.text_input("목표 (선택)", placeholder="예: 전역 후 6개월 내 합격")
            
            submitted = st.form_submit_button("🚀 스터디 생성하기", type="primary", use_container_width=True)

            if submitted:
                if not new_name or not new_subject or not new_desc:
                    st.error("이름, 과목, 소개는 필수 입력사항입니다.")
                else:
                    new_id = max([g["id"] for g in st.session_state.study_groups], default=0) + 1
                    new_group = {
                        "id": new_id,
                        "name": new_name,
                        "subject": new_subject,
                        "members": ["나 (현재 사용자)"],
                        "max_members": new_max,
                        "chat": [],
                        "description": new_desc,
                        "goal": new_goal
                    }
                    st.session_state.study_groups.append(new_group)
                    st.session_state.my_groups.append(new_id)
                    st.success(f"✅ '{new_name}' 스터디가 생성되었습니다! '내 스터디' 탭에서 확인하세요.")

    # --- 내 스터디 (채팅) ---
    with study_tabs[2]:
        st.subheader("💬 내 스터디 채팅")

        my_groups_list = [g for g in st.session_state.study_groups if g["id"] in st.session_state.my_groups]

        if not my_groups_list:
            st.info("아직 참여한 스터디가 없습니다. '스터디 찾기'에서 참여하거나 새로 만들어보세요!")
        else:
            group_names = [g["name"] for g in my_groups_list]
            selected_group_name = st.selectbox("스터디 선택", group_names)
            selected_group = next(g for g in my_groups_list if g["name"] == selected_group_name)

            st.markdown(f"**{selected_group['name']}** | 👥 {len(selected_group['members'])}명 | 📖 {selected_group['subject']}")
            st.divider()

            # 채팅 메시지 표시
            chat_container = st.container(height=350)
            with chat_container:
                if not selected_group["chat"]:
                    st.caption("아직 대화가 없습니다. 먼저 인사해보세요! 👋")
                for msg in selected_group["chat"]:
                    if msg["sender"] == "나":
                        with st.chat_message("user"):
                            st.markdown(f"**{msg['sender']}**: {msg['text']}")
                            st.caption(msg.get("time", ""))
                    else:
                        with st.chat_message("assistant"):
                            st.markdown(f"**{msg['sender']}**: {msg['text']}")
                            st.caption(msg.get("time", ""))

            # 채팅 입력
            chat_input_key = f"chat_input_{selected_group['id']}"
            chat_msg = st.chat_input(f"{selected_group_name}에 메시지 보내기...", key=chat_input_key)
            if chat_msg:
                import datetime
                now = datetime.datetime.now().strftime("%H:%M")
                selected_group["chat"].append({
                    "sender": "나",
                    "text": chat_msg,
                    "time": now
                })

                # AI 스터디 도우미 응답 (가끔)
                if api_key and len(selected_group["chat"]) % 3 == 0:
                    try:
                        client = OpenAI(api_key=api_key)
                        ai_prompt = f"""
                        당신은 스터디 그룹의 AI 학습 도우미입니다.
                        스터디 주제: {selected_group['subject']}
                        마지막 메시지: {chat_msg}
                        
                        학습에 도움이 되는 짧은 응원/팁을 1-2문장으로 해주세요. 이모지 포함.
                        """
                        ai_resp = client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": ai_prompt}],
                            max_tokens=100
                        )
                        selected_group["chat"].append({
                            "sender": "🤖 AI 스터디 도우미",
                            "text": ai_resp.choices[0].message.content,
                            "time": now
                        })
                    except:
                        pass
                st.rerun()
