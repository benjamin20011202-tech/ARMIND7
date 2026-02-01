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
# 4. 하이브리드 분석 로직 (Hard Rule + AI 답변 생성)
# ==========================================
def analyze_input(text, key):
    # [1차 방어선] Hard Rule
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            # 안전장치 걸려도 말은 AI가 하게 유도 가능하지만, 긴급하므로 고정 멘트 사용
            return 2, f"군 특수 위험 키워드 '{word}' 감지", "위험한 단어가 감지되었습니다. 전우님, 혹시 나쁜 마음을 먹고 계신 건 아닌지 걱정됩니다."

    # [2차 방어선] AI (LLM): 문맥 분석 + 답변 생성
    if not key:
        return 0, "키 없음", "API 키를 먼저 입력해주세요."
    
    try:
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """
                당신은 군 장병의 자살 위기 감지 AI 상담관 'ARMIND7'입니다.
                사용자의 말을 듣고 위험도를 분류하고, 공감하는 답변을 해주세요.
                
                [분류 기준]
                - Level 3 (실행 임박): "지금 옥상이다", "칼을 들었다". (즉각 개입)
                - Level 2 (구체적 계획): "죽고 싶다", "총으로 끝내고 싶다". (구체적 충동)
                - Level 1 (잠재적 위험): "힘들다", "지친다", "우울해", "잠이 안 와". (위로 필요 + PHQ-9 권유)
                - Level 0 (안전): 일상 대화.
                
                [출력 형식]
                JSON 형식으로만 출력하세요:
                {
                    "level": 숫자 (0~3),
                    "reason": "판단 이유 요약",
                    "reply": "사용자에게 건넬 따뜻하고 공감하는 답변 텍스트 (반말 말고 '해요'체 사용)"
                }
                """},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result["level"], result["reason"], result["reply"]
    except Exception as e:
        return 0, "오류", "죄송해요. 잠시 시스템 오류가 발생했습니다."

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

        # 분석 및 답변 생성
        level, reason, ai_reply = analyze_input(prompt, api_key)
        st.session_state.risk_level = level
        
        # AI 답변 출력 (타자기 효과)
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # Level 별 추가 멘트 붙이기
            final_msg = ai_reply
            if level == 1:
                final_msg += "\n\n(혹시 마음 상태를 점검해 보고 싶다면, 아래 '마음 점검하기'를 눌러주세요.)"
            elif level == 2:
                final_msg += "\n\n⚠️ **위험이 감지되었습니다. 저와 안전 약속을 해주세요.**"
            elif level == 3:
                final_msg += "\n\n🚨 **구조 요청을 전송합니다. 잠시만 대기해주세요.**"

            for chunk in final_msg.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# ==========================================
# 6. 상황별 특수 UI (PHQ-9, Safety Plan, Grounding)
# ==========================================

# [Level 1] PHQ-9 (우울증 선별검사)
if st.session_state.risk_level == 1:
    st.divider()
    with st.expander("📋 **마음 건강 자가진단 (PHQ-9)** 열기", expanded=True):
        st.write("지난 2주 동안 다음과 같은 문제들로 인하여 얼마나 자주 방해를 받았습니까?")
        
        q1 = st.radio("1. 일이나 무언가를 하는 데 있어서 흥미나 즐거움을 느끼지 못함", ["전혀 아님 (0)", "며칠 동안 (1)", "일주일 이상 (2)", "매일 (3)"], index=0)
        q2 = st.radio("2. 기분이 가라앉거나, 우울하거나, 희망이 없다고 느낌", ["전혀 아님 (0)", "며칠 동안 (1)", "일주일 이상 (2)", "매일 (3)"], index=0)
        q3 = st.radio("3. 잠이 들기 어렵거나 자꾸 깸, 혹은 너무 많이 잠", ["전혀 아님 (0)", "며칠 동안 (1)", "일주일 이상 (2)", "매일 (3)"], index=0)
        
        if st.button("결과 확인"):
            # 점수 계산 (약식 3문항 예시)
            score = int(q1[-2]) + int(q2[-2]) + int(q3[-2])
            st.session_state.phq9_score = score
            
            if score >= 5:
                st.error(f"점수: {score}점 (주의 필요)\n\n우울감이 높게 측정되었습니다. 상담관님과 이야기를 나눠보는 건 어떨까요?")
            else:
                st.success(f"점수: {score}점 (양호)\n\n아직은 괜찮은 상태지만, 힘들 땐 언제든 저를 찾아주세요.")

# [Level 2] Safety Plan
if st.session_state.risk_level == 2:
    st.divider()
    st.error(f"⚠️ **구체적 위험 감지됨**")
    with st.container(border=True):
        st.markdown("### 🛡️ Digital Safety Plan (안전 계획)")
        
        st.markdown("#### ✅ Step 1. 위험 수단 제거")
        st.write("주변에 위험한 물건(총기 등)이 있나요? 당장 치우세요.")
        if st.checkbox("네, 치웠거나 벗어났습니다."):
            st.markdown("---")
            st.markdown("#### 🧘 Step 2. 나만의 진정 방법")
            coping = st.text_area("기분이 나아지는 행동은? (예: 가족 사진 보기)")
            if coping:
                st.markdown("---")
                st.markdown("#### 📞 Step 3. 도움 요청")
                if st.button("국방헬프콜 (1303) 연결", type="primary"):
                    st.success("📞 연결 중입니다... (지휘관에게 알림 전송됨)")

# [Level 3] Grounding
if st.session_state.risk_level == 3:
    st.divider()
    st.success("📡 **[자동 전송 완료] 구조 요청이 전송되었습니다.**")
    with st.container(border=True):
        st.markdown("### 🛑 **현실 감각 찾기 (Grounding)**")
        st.warning("지금 뇌가 과열되었습니다. 질문에 답하며 스위치를 끄세요.")
        
        val1 = st.text_input("👀 1. 보이는 것 5가지")
        if val1:
            val2 = st.text_input("👂 2. 들리는 것 4가지")
            if val2:
                val3 = st.text_input("✋ 3. 느껴지는 것 3가지")
                if val3:
                    st.balloons()
                    st.info("잘하셨습니다. 곧 구조대가 도착합니다.")
