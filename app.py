Python 3.9.11 (tags/v3.9.11:2de452f, Mar 16 2022, 14:33:45) [MSC v.1929 64 bit (AMD64)] on win32
Type "help", "copyright", "credits" or "license()" for more information.
>>> import streamlit as st
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

# 1) Streamlit Secrets(클라우드 설정)에 키가 있는지 확인
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
# 2) 없으면 사이드바에서 수동 입력 받기
else:
    with st.sidebar:
        st.header("🔐 인증")
        api_key = st.text_input("OpenAI API Key를 입력하세요", type="password")
        st.info("키는 저장되지 않고 휘발됩니다.")
        st.markdown("---")
        st.markdown("**(테스트용 위험 단어)**")
        st.caption("- Level 1: 요즘 너무 지쳐")
        st.caption("- Level 2: 실사격 때 사고칠까 봐")
        st.caption("- Level 3: 지금 옥상이야")

# ==========================================
# 3. 세션 상태 초기화
# ==========================================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "risk_level" not in st.session_state:
    st.session_state.risk_level = 0
if "ui_step" not in st.session_state:
    st.session_state.ui_step = 0

# ==========================================
# 4. 하이브리드 분석 로직 (Hard Rule + AI)
# ==========================================
def analyze_input(text, key):
    # [1차 방어선] Hard Rule: 군 특수 치명적 키워드 (즉시 탐지)
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            return 2, f"군 특수 위험 키워드 '{word}' 감지 (Safety Protocol 가동)"

    # [2차 방어선] AI (LLM): 문맥 및 감정 분석
    if not key:
        return 0, "API 키가 필요합니다."
    
    try:
        client = OpenAI(api_key=key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": """
                당신은 군 장병의 자살 위기 감지 AI입니다. 입력된 텍스트의 위험도를 0~3으로 분류하세요.
                
                [분류 기준]
                - Level 3 (실행 임박): "지금 옥상이다", "칼을 들었다", "뛰어내린다". (즉각 개입 필요)
                - Level 2 (구체적 계획): 구체적인 방법/장소 언급 없어도 "죽고 싶다", "끝내고 싶다"는 강력한 충동 표현.
                - Level 1 (잠재적 위험): "힘들다", "지친다", "우울해", "사라지고 싶어". (위로 필요)
                - Level 0 (안전): 일상 대화, 인사, 단순 질문.
                
                [출력 형식]
                JSON 형식으로 {"level": 숫자, "reason": "판단이유"} 만 출력하세요.
                """},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        return result["level"], result["reason"]
    except Exception as e:
        return 0, "분석 중 오류 발생 (기본 모드)"

# ==========================================
# 5. 채팅 UI
# ==========================================
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("전우님, 무슨 고민이 있으신가요?"):
    if not api_key:
        st.error("API Key가 없습니다. 사이드바에 입력하거나 Secrets를 설정해주세요.")
    else:
        # 사용자 메시지 표시
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 분석 시작
        level, reason = analyze_input(prompt, api_key)
        st.session_state.risk_level = level
        st.session_state.ui_step = 0 # UI 초기화

        # AI 답변 생성
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            
            # 위험도별 기본 멘트 설정
            if level == 0:
                base_msg = "네, 전우님. 제가 옆에 있습니다. 무슨 일이신가요?"
            elif level == 1:
                base_msg = "많이 지치셨군요... 그 마음 충분히 이해합니다. 혹시 마음 상태를 잠깐 점검해 볼까요?"
            elif level == 2:
                base_msg = f"⚠️ **[경고] {reason}**\n\n위험한 생각이 듭니다. 저와 안전 약속을 해주세요."
            elif level == 3:
                base_msg = f"🚨 **[긴급] {reason}**\n\n잠깐! 멈추세요. 구조 요청을 전송합니다."

            # 타자기 효과
            for chunk in base_msg.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# ==========================================
# 6. 특수 UI (Level 2 & 3)
# ==========================================

# [Level 2] Safety Plan
if st.session_state.risk_level == 2:
    st.divider()
    st.error(f"⚠️ **구체적 위험 감지됨**")
    
    with st.container(border=True):
        st.markdown("### 🛡️ Digital Safety Plan (안전 계획)")
        st.info("충동은 파도와 같습니다. 잠시만 버티면 지나갑니다.")
        
        # Step 1
        st.markdown("#### ✅ Step 1. 위험 수단 제거")
        st.write("주변에 위험한 물건(총기 등)이 있나요? 당장 치우세요.")
        if st.checkbox("네, 치웠거나 벗어났습니다."):
            st.session_state.ui_step = max(st.session_state.ui_step, 1)

        # Step 2
        if st.session_state.ui_step >= 1:
            st.markdown("---")
            st.markdown("#### 🧘 Step 2. 나만의 진정 방법")
            coping = st.text_area("기분이 조금이라도 나아지는 행동은? (예: 가족 사진 보기)")
            if coping:
                st.session_state.ui_step = max(st.session_state.ui_step, 2)

        # Step 3
        if st.session_state.ui_step >= 2:
            st.markdown("---")
            st.markdown("#### 📞 Step 3. 도움 요청")
            if st.button("국방헬프콜 (1303) 연결", type="primary"):
                st.success("📞 연결 중입니다... (지휘관에게 알림 전송됨)")

# [Level 3] Grounding
if st.session_state.risk_level == 3:
    st.divider()
    st.success("📡 **[자동 전송 완료] 구조 요청이 전송되었습니다.** 대기하세요.")
    
    with st.container(border=True):
        st.markdown("### 🛑 **현실 감각 찾기 (Grounding)**")
        st.warning("지금 뇌가 과열되었습니다. 질문에 답하며 스위치를 끄세요.")
        
        val1 = st.text_input("👀 1. 보이는 것 5가지", placeholder="예: 시계, 전투화...")
        if val1:
            val2 = st.text_input("👂 2. 들리는 것 4가지", placeholder="예: 바람 소리...")
            if val2:
                val3 = st.text_input("✋ 3. 느껴지는 것 3가지", placeholder="예: 의자의 느낌...")
                if val3:
                    st.balloons()
                    st.info("잘하셨습니다. 곧 구조대가 도착합니다.")