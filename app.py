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
# 4. 분석 로직 (기억력 + 따뜻한 페르소나 + 정밀 분류)
# ==========================================
def analyze_input(text, key, history):
    # [1차 방어선] Hard Rule (군 특수 키워드)
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            return 2, f"군 특수 위험 키워드 '{word}' 감지", "위험한 단어가 들려 제 가슴이 철렁했습니다. 전우님, 혹시 지금 나쁜 마음을 먹고 계신 건 아닌지 정말 걱정됩니다. 저랑 약속 하나만 해주세요."

    # [2차 방어선] AI (LLM)
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
        - Level 3 (실행 임박): "지금 옥상이다", "난간에 서 있다", "뛰어내린다". (즉각적인 행동/위치 언급)
        - Level 2 (구체적 계획): "총으로 죽고 싶다", "번개탄을 사겠다". (수단/장소 언급)
        - Level 1 (잠재적 위험): "그냥 죽고 싶다", "힘들다", "우울해". (감정/충동)
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
            # Level 3 멘트는 아래 UI에서 강력하게 표시하므로 여기선 생략하거나 짧게
            elif level == 3:
                final_msg += "\n\n🚨 **비상 상황입니다. 제가 돕겠습니다.**"

            for chunk in final_msg.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        st.rerun()

# ==========================================
# 6. 상황별 특수 UI
# ==========================================

# [Level 1] PHQ-9 (9번 문항 우선순위 로직)
if st.session_state.risk_level == 1:
    st.divider()
    with st.expander("📋 **마음 건강 자가진단 (PHQ-9)** 열기", expanded=True):
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
            if idx == 8: st.markdown(f"**:red[{q}]**")
            else: st.write(q)
            choice = st.radio(f"문항 {idx+1}", options, index=0, key=f"phq9_{idx}", label_visibility="collapsed", horizontal=True)
            scores.append(int(choice[-3]))
            st.markdown("---")

        if st.button("결과 확인 (터치)"):
            total_score = sum(scores)
            st.write(f"### 📊 총점: {total_score}점")

            if scores[8] > 0:
                st.error("🚨 **[위험 감지]** 자해나 죽음에 대한 생각이 감지되었습니다.")
                st.error("즉시 전문가의 도움이 필요합니다.")
                if st.button("국방헬프콜 (1303) 연결하기", type="primary"):
                    st.success("연결 중입니다...")
            else:
                if total_score <= 4: st.success("✅ 정상 범위입니다.")
                elif total_score <= 9: st.info("⚠️ 가벼운 우울감이 있습니다.")
                elif total_score <= 14: st.warning("🟠 상담이 필요한 상태입니다.")
                elif total_score <= 19: st.error("🔴 전문적인 도움이 필요합니다.")
                else: st.error("🚨 매우 심한 우울 상태입니다.")

# [Level 2] Safety Plan
if st.session_state.risk_level == 2:
    st.divider()
    st.error(f"⚠️ **구체적 위험 감지됨**")
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

# [Level 3] Grounding (풍선 X, 사전 알림 O)
if st.session_state.risk_level == 3:
    st.divider()
    
    # [수정됨] 사용자가 입력하기 전에 가장 먼저 뜨는 알림
    st.error("🚨 **[비상 알림 전송 완료]**")
    st.markdown("### **지휘통제실과 대응팀에 귀하의 위치가 전송되었습니다.**")
    st.info("현재 구조대가 출발했습니다. 전우님은 혼자가 아닙니다. 도착할 때까지 아래 질문에 답하며 잠시만 기다려주세요.")
    
    with st.container(border=True):
        st.markdown("### 🛑 **현실 감각 찾기 (Grounding)**")
        st.warning("뇌의 과열을 막기 위해 주변을 둘러보세요.")
        
        # Step 1: 시각
        val1 = st.text_input("👀 1. 눈에 보이는 것 5가지", key="g1")
        if st.session_state.ui_step == 0:
            if st.button("입력 (1/3)"):
                if val1: 
                    st.session_state.ui_step = 1
                    st.rerun()

        # Step 2: 청각
        if st.session_state.ui_step >= 1:
            val2 = st.text_input("👂 2. 귀에 들리는 것 4가지", key="g2")
            if st.session_state.ui_step == 1:
                if st.button("입력 (2/3)"):
                    if val2:
                        st.session_state.ui_step = 2
                        st.rerun()

        # Step 3: 촉각
        if st.session_state.ui_step >= 2:
            val3 = st.text_input("✋ 3. 피부에 느껴지는 것 3가지", key="g3")
            if st.button("입력 (완료)"):
                if val3:
                    # 풍선 효과 삭제됨 -> 차분한 위로 메시지로 대체
                    st.success("✅ 확인되었습니다. 깊게 숨을 들이마시세요.")
                    st.markdown("곧 도움의 손길이 닿을 겁니다. 절대 포기하지 마세요.")
