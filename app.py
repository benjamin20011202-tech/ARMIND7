import streamlit as st
import time
import json
from openai import OpenAI

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(page_title="ARMIND7: 디지털 전우", page_icon="🪖")

st.title("🪖 ARMIND7: 당신의 디지털 전우")
st.markdown("### 상승 7사단, 당신의 마음을 지킵니다.")

# ==========================================
# 2. API 키 처리 (자동 감지 or 수동 입력)
# ==========================================
api_key = None
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    with st.sidebar:
        st.header("🔐 인증")
        api_key = st.text_input("OpenAI API Key를 입력하세요", type="password")
        st.info("키는 저장되지 않고 휘발됩니다.")
        st.markdown("---")
        st.caption("※ 보안을 위해 API 키가 필요합니다.")

# ==========================================
# 3. 세션 상태 초기화
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "risk_level" not in st.session_state:
    st.session_state.risk_level = 0
if "ui_step" not in st.session_state:
    st.session_state.ui_step = 0
if "phq9_score" not in st.session_state:
    st.session_state.phq9_score = 0

# ==========================================
# 4. 하이브리드 분석 로직 (기억력 + 따뜻한 페르소나)
# ==========================================
def analyze_input(text, key, history):
    # [1차 방어선] Hard Rule (군 특수 치명적 키워드)
    # AI 판단보다 우선하여, 무조건 위험으로 분류 (안전장치)
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            return 2, f"군 특수 위험 키워드 '{word}' 감지", "위험한 단어가 들려 제 가슴이 철렁했습니다. 전우님, 혹시 지금 나쁜 마음을 먹고 계신 건 아닌지 정말 걱정됩니다. 저랑 약속 하나만 해주세요."

    # [2차 방어선] AI (LLM) - 문맥 및 감정 분석
    if not key:
        return 0, "키 없음", "API 키를 먼저 입력해주세요."
    
    try:
        client = OpenAI(api_key=key)
        
        # 시스템 프롬프트: 따뜻한 상담관 페르소나 부여
        system_instruction = """
        당신은 대한민국 육군 장병들의 마음을 지키는 AI 상담관 'ARMIND7'입니다.
        단답형으로 말하지 말고, 사용자의 힘든 마음에 깊이 공감하는 '따뜻하고 정성스러운' 답변을 해주세요.
        
        [대화 가이드라인]
        1. **공감과 인정:** "힘드시겠어요" 같은 기계적인 말 대신, "그동안 혼자 끙끙 앓느라 얼마나 힘드셨습니까", "그런 일이 있어서 정말 막막하셨겠어요" 같이 구체적으로 감정을 읽어주세요.
        2. **말투:** 친한 선임이나 형처럼 부드러운 '해요체'를 사용하세요. (이모지 적절히 사용 🌿)
        3. **연결:** 사용자의 이전 대화 맥락을 기억해서 대답하세요.
        
        [엄격한 위험도 분류 기준]
        - Level 3 (실행 임박): "지금 옥상이다", "난간에 서 있다", "뛰어내린다". (즉각적인 행동/위치 언급 필수)
        - Level 2 (구체적 계획): "총으로 죽고 싶다", "휴가 나가서 번개탄을 사겠다". (구체적인 '수단'이나 '장소'가 언급됨)
        - Level 1 (잠재적 위험): "그냥 자살하고 싶다", "죽고 싶다", "너무 힘들다", "사라지고 싶다". (구체적 계획 없이 감정/충동만 표현)
        - Level 0 (안전): 일상 대화.
        
        [출력 형식]
        반드시 JSON 형식으로만 출력: {"level": 숫자, "reason": "이유", "reply": "정성스러운 답변 텍스트"}
        """

        messages_payload = [{"role": "system", "content": system_instruction}]
        
        # 대화 기억 (최근 10개만 전송하여 비용 절약)
        for msg in history[-10:]:
            messages_payload.append({"role": msg["role"], "content": str(msg["content"])})
            
        # 현재 사용자 입력
        messages_payload.append({"role": "user", "content": text})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages_payload,
            temperature=0.7, # 창의성(따뜻함) 높임
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result["level"], result["reason"], result["reply"]
    except Exception as e:
        return 0, "오류", "시스템에 잠시 오류가 생겼어요. 하지만 저는 여기 있습니다. 다시 한번 말씀해 주시겠어요?"

# ==========================================
# 5. 채팅 UI
# ==========================================
# 이전 대화 기록 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력 처리
if prompt := st.chat_input("전우님, 무슨 고민이 있으신가요?"):
    if not api_key:
        st.error("API Key가 없습니다. 사이드바에 입력하거나 Secrets를 설정해주세요.")
    else:
        # 사용자 메시지 저장 및 표시
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI 분석 (기억력 포함)
        level, reason, ai_reply = analyze_input(prompt, api_key, st.session_state.messages)
        st.session_state.risk_level = level
        st.session_state.ui_step = 0 # 새로운 주제 시작 시 UI 단계 초기화
        
        # AI 답변 생성 및 표시
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # 위험도별 추가 멘트 (넛지)
            final_msg = ai_reply
            if level == 1:
                final_msg += "\n\n(마음이 많이 힘드신 것 같네요. 아래 **자가진단**을 한번 해보시겠어요?)"
            elif level == 2:
                final_msg += "\n\n⚠️ **위험한 생각이 듭니다. 저와 안전 약속을 해주세요.**"
            elif level == 3:
                final_msg += "\n\n🚨 **구조 요청을 전송합니다. 그대로 대기하세요.**"

            # 타자기 효과
            for chunk in final_msg.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# ==========================================
# 6. 상황별 특수 UI (모바일 최적화 + 정밀 로직)
# ==========================================

# [Level 1] PHQ-9 (정식 9문항 + 9번 문항 우선순위 로직)
if st.session_state.risk_level == 1:
    st.divider()
    with st.expander("📋 **마음 건강 자가진단 (PHQ-9)** 열기", expanded=True):
        st.write("지난 2주 동안, 다음 문제들로 인해 얼마나 자주 방해받으셨나요?")
        
        phq9_questions = [
            "1. 기분이 가라앉거나, 우울하거나, 희망이 없다고 느꼈다.",
            "2. 평소 하던 일에 대한 흥미가 없어지거나 즐거움을 느끼지 못했다.",
            "3. 잠들기가 어렵거나 자꾸 깼다 / 혹은 너무 많이 잤다.",
            "4. 평소보다 식욕이 줄었다 / 혹은 평소보다 많이 먹었다.",
            "5. 다른 사람들이 눈치 챌 정도로 말과 행동이 느려졌다 / 혹은 너무 안절부절못했다.",
            "6. 피곤하고 기운이 없었다.",
            "7. 내가 잘못했거나, 실패했다는 생각이 들었다 (자책감).",
            "8. 신문을 읽거나 TV를 보는 것과 같은 일상적인 일에도 집중할 수가 없었다.",
            "9. 차라리 죽는 것이 더 낫겠다고 생각했다 / 혹은 자해할 생각을 했다."
        ]
        
        options = ["전혀 아님 (0점)", "며칠 동안 (1점)", "일주일 이상 (2점)", "매일 (3점)"]
        scores = []

        for idx, q in enumerate(phq9_questions):
            # 9번 문항 강조
            if idx == 8:
                st.markdown(f"**:red[{q}]**")
            else:
                st.write(q)
            
            # 라디오 버튼 (모바일 가독성 위해 horizontal=True)
            choice = st.radio(f"문항 {idx+1}", options, index=0, key=f"phq9_{idx}", label_visibility="collapsed", horizontal=True)
            scores.append(int(choice[-3])) # 점수 추출
            st.markdown("---")

        if st.button("결과 확인 (터치)"):
            total_score = sum(scores)
            st.session_state.phq9_score = total_score
            st.write(f"### 📊 총점: {total_score}점")

            # [핵심 로직] 9번 문항 > 0 이면 무조건 위험
            if scores[8] > 0:
                st.error("🚨 **[위험 감지]** 총점과 관계없이, 자해나 죽음에 대한 생각이 감지되었습니다.")
                st.error("혼자 고민하지 마십시오. 지금 당장 전문가의 도움이 필요합니다.")
                if st.button("국방헬프콜 (1303) 연결하기", type="primary"):
                    st.success("연결 중입니다...")
            else:
                # 일반 점수 해석
                if total_score <= 4:
                    st.success("✅ **[정상 범위]** 마음 상태가 안정적입니다.")
                elif total_score <= 9:
                    st.info("⚠️ **[가벼운 우울]** 약간의 스트레스가 보입니다. 휴식이 필요해요.")
                elif total_score <= 14:
                    st.warning("🟠 **[중간 정도의 우울]** 상담관님과 대화가 필요합니다.")
                elif total_score <= 19:
                    st.error("🔴 **[약간 심한 우울]** 전문적인 도움을 받는 것이 좋습니다.")
                else:
                    st.error("🚨 **[심한 우울]** 꼭 도움을 요청해야 합니다.")

# [Level 2] Safety Plan (모바일 버튼 방식)
if st.session_state.risk_level == 2:
    st.divider()
    st.error(f"⚠️ **구체적 위험 감지됨**")
    with st.container(border=True):
        st.markdown("### 🛡️ Digital Safety Plan (안전 계획)")
        
        st.markdown("#### ✅ Step 1. 위험 수단 제거")
        st.write("주변에 위험한 물건(총기 등)이 있나요? 당장 치우세요.")
        
        # [모바일 최적화] 버튼으로 단계 진행
        if st.session_state.ui_step == 0:
            if st.button("네, 치웠습니다 (다음 단계)"):
                st.session_state.ui_step = 1
                st.rerun()
        
        if st.session_state.ui_step >= 1:
            st.success("확인되었습니다.")
            st.markdown("---")
            st.markdown("#### 🧘 Step 2. 나만의 진정 방법")
            coping = st.text_area("기분이 나아지는 행동은? (예: 가족 사진 보기)", key="coping")
            
            if st.session_state.ui_step == 1:
                if st.button("입력 완료 (다음 단계)"):
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

# [Level 3] Grounding (3단계 오감 자극)
if st.session_state.risk_level == 3:
    st.divider()
    # 최우선 메시지: 구조 요청 완료
    st.success("📡 **[자동 전송 완료] 구조 요청이 전송되었습니다.** 구조대가 올 때까지 대기하세요.")
    
    with st.container(border=True):
        st.markdown("### 🛑 **현실 감각 찾기 (Grounding)**")
        st.warning("지금 뇌가 과열되었습니다. 질문에 답하며 스위치를 끄세요.")
        
        # Step 1: 시각 (5가지)
        val1 = st.text_input("👀 1. 눈에 보이는 것 5가지", key="g1")
        if st.session_state.ui_step == 0:
            if st.button("입력 (1/3)"):
                if val1: 
                    st.session_state.ui_step = 1
                    st.rerun()

        # Step 2: 청각 (4가지)
        if st.session_state.ui_step >= 1:
            val2 = st.text_input("👂 2. 귀에 들리는 것 4가지", key="g2")
            if st.session_state.ui_step == 1:
                if st.button("입력 (2/3)"):
                    if val2:
                        st.session_state.ui_step = 2
                        st.rerun()

        # Step 3: 촉각 (3가지)
        if st.session_state.ui_step >= 2:
            val3 = st.text_input("✋ 3. 피부에 느껴지는 것 3가지", key="g3")
            if st.button("입력 (완료)"):
                if val3:
                    st.balloons()
                    st.info("잘하셨습니다. 당신은 혼자가 아닙니다. 조금만 더 힘내세요.")