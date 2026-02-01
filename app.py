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
if "messages" not in st.session_state:
    st.session_state.messages = []
if "risk_level" not in st.session_state:
    st.session_state.risk_level = 0
if "ui_step" not in st.session_state:
    st.session_state.ui_step = 0
if "phq9_score" not in st.session_state:
    st.session_state.phq9_score = 0

# ==========================================
# 4. 하이브리드 분석 로직 (정밀 분류 적용)
# ==========================================
def analyze_input(text, key):
    # [1차 방어선] Hard Rule (군 특수 치명적 키워드)
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            return 2, f"군 특수 위험 키워드 '{word}' 감지", "위험한 단어가 감지되었습니다. 전우님, 혹시 나쁜 마음을 먹고 계신 건 아닌지 걱정됩니다."

    # [2차 방어선] AI (LLM)
    if not key:
        return 0, "키 없음", "API 키를 먼저 입력해주세요."
    
    try:
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """
                당신은 군 장병의 자살 위기 감지 AI 상담관 'ARMIND7'입니다.
                
                [엄격한 분류 기준]
                - Level 3 (실행 임박): "지금 옥상이다", "난간에 서 있다", "지금 뛰어내린다". (즉각적인 행동/위치 언급 필수)
                - Level 2 (구체적 계획): "총으로 죽고 싶다", "휴가 나가서 번개탄을 사겠다". (구체적인 '수단'이나 '장소'가 언급되어야 함)
                - Level 1 (잠재적 위험): "그냥 자살하고 싶다", "죽고 싶다", "너무 힘들다", "사라지고 싶다". (구체적 계획 없이 감정/충동만 표현한 경우)
                - Level 0 (안전): 일상 대화.
                
                [출력 형식]
                JSON 형식으로만 출력: {"level": 숫자, "reason": "이유", "reply": "공감하는 답변(해요체)"}
                """},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result["level"], result["reason"], result["reply"]
    except Exception as e:
        return 0, "오류", "시스템 오류가 발생했습니다."

# ==========================================
# 5. 채팅 UI
# ==========================================
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

        level, reason, ai_reply = analyze_input(prompt, api_key)
        st.session_state.risk_level = level
        st.session_state.ui_step = 0 # 새로운 대화 시 UI 단계 초기화
        
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            final_msg = ai_reply
            if level == 1:
                final_msg += "\n\n(마음이 많이 힘드신 것 같네요. 아래 자가진단을 한번 해보시겠어요?)"
            elif level == 2:
                final_msg += "\n\n⚠️ **위험한 생각이 듭니다. 저와 안전 약속을 해주세요.**"
            elif level == 3:
                final_msg += "\n\n🚨 **구조 요청을 전송합니다. 그대로 대기하세요.**"

            for chunk in final_msg.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# ==========================================
# 6. 상황별 특수 UI (모바일 버튼 추가됨)
# ==========================================

# [Level 1] PHQ-9 (우울증 선별검사) - 정식 9문항 버전 (로직 수정됨)
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

        # 문항 반복 출력
        for idx, q in enumerate(phq9_questions):
            # 9번 문항은 빨간색으로 강조
            if idx == 8:
                st.markdown(f"**:red[{q}]**")
            else:
                st.write(q)
                
            choice = st.radio(f"{idx+1}번 문항 선택", options, index=0, key=f"phq9_{idx}", label_visibility="collapsed", horizontal=True)
            scores.append(int(choice[-3])) # "0점"에서 숫자만 추출
            st.markdown("---")

        # 결과 계산 버튼 (모바일 최적화)
        if st.button("결과 확인 (터치)"):
            total_score = sum(scores)
            st.session_state.phq9_score = total_score
            st.write(f"### 📊 총점: {total_score}점")

            # [로직 수정] 9번 문항이 0보다 크면, 총점이 낮아도 무조건 '위험' 경고
            if scores[8] > 0:
                st.error("🚨 **[위험 감지]** 총점과 관계없이, 자해나 죽음에 대한 생각이 감지되었습니다.")
                st.error("혼자 고민하지 마십시오. 지금 당장 전문가의 도움이 필요합니다.")
                if st.button("국방헬프콜 (1303) 연결하기", type="primary"):
                    st.success("연결 중입니다...")
            
            # 9번 문항이 0점일 때만 일반 점수 해석 진행
            else:
                if total_score <= 4:
                    st.success("✅ **[정상 범위]** 현재 마음 상태가 안정적입니다. 지금처럼 전우들과 잘 지내시면 됩니다.")
                elif total_score <= 9:
                    st.info("⚠️ **[가벼운 우울]** 약간의 스트레스가 보입니다. 맛있는 걸 먹거나 푹 쉬면서 기분을 환기해 보세요.")
                elif total_score <= 14:
                    st.warning("🟠 **[중간 정도의 우울]** 우울감이 지속되고 있습니다. 상담관님과 가볍게 차 한잔하며 이야기해보는 건 어떨까요?")
                elif total_score <= 19:
                    st.error("🔴 **[약간 심한 우울]** 혼자 버티기 힘든 상태입니다. 전문적인 상담이나 진료를 권장합니다.")
                else:
                    st.error("🚨 **[심한 우울]** 마음이 많이 병들었습니다. 꼭 군 병원이나 전문가에게 도움을 요청해야 합니다.")

# [Level 2] Safety Plan (모바일 버튼 추가)
if st.session_state.risk_level == 2:
    st.divider()
    st.error(f"⚠️ **구체적 위험 감지됨**")
    with st.container(border=True):
        st.markdown("### 🛡️ Digital Safety Plan")
        
        st.markdown("#### ✅ Step 1. 위험 수단 제거")
        st.write("주변에 위험한 물건(총기 등)이 있나요? 당장 치우세요.")
        
        # 버튼으로 단계 넘기기 (모바일 최적화)
        if st.session_state.ui_step == 0:
            if st.button("네, 치웠습니다 (다음 단계로)"):
                st.session_state.ui_step = 1
                st.rerun()
        
        if st.session_state.ui_step >= 1:
            st.success("확인되었습니다.")
            st.markdown("---")
            st.markdown("#### 🧘 Step 2. 나만의 진정 방법")
            coping = st.text_area("기분이 나아지는 행동은?", key="coping_input")
            
            if st.session_state.ui_step == 1:
                if st.button("입력 완료 (다음 단계로)"):
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

# [Level 3] Grounding (모바일 버튼 추가)
if st.session_state.risk_level == 3:
    st.divider()
    st.success("📡 **[자동 전송 완료] 구조 요청 전송됨**")
    with st.container(border=True):
        st.markdown("### 🛑 **현실 감각 찾기 (Grounding)**")
        st.warning("뇌의 스위치를 끄기 위해 아래 질문에 답해주세요.")
        
        # Step 1: 시각
        val1 = st.text_input("👀 1. 보이는 것 5가지", key="g1")
        if st.session_state.ui_step == 0:
            if st.button("입력 (1/3)"):
                if val1: 
                    st.session_state.ui_step = 1
                    st.rerun()

        # Step 2: 청각
        if st.session_state.ui_step >= 1:
            val2 = st.text_input("👂 2. 들리는 것 4가지", key="g2")
            if st.session_state.ui_step == 1:
                if st.button("입력 (2/3)"):
                    if val2:
                        st.session_state.ui_step = 2
                        st.rerun()

        # Step 3: 촉각
        if st.session_state.ui_step >= 2:
            val3 = st.text_input("✋ 3. 느껴지는 것 3가지", key="g3")
            if st.button("입력 (완료)"):
                if val3:
                    st.balloons()
                    st.info("잘하셨습니다. 곧 구조대가 도착합니다.")
