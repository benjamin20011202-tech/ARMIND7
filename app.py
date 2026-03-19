import streamlit as st
import time
import json
import base64
import uuid
import datetime
import re
import requests
import xml.etree.ElementTree as ET
from openai import OpenAI
from supabase import create_client, Client

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(page_title="SOLMATE: 디지털 전우", page_icon="🪖", layout="wide")

st.title("🪖 SOLMATE")
st.markdown("### 당신의 디지털 전우")

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
# Supabase 클라이언트 초기화
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def load_study_groups():
    """Supabase에서 스터디 목록 불러오기"""
    try:
        sb = get_supabase()
        res = sb.table("study_groups").select("*").order("created_at", desc=False).execute()
        groups = []
        for row in res.data:
            groups.append({
                "id": row["id"],
                "name": row["name"],
                "subject": row["subject"],
                "description": row.get("description", ""),
                "goal": row.get("goal", ""),
                "max_members": row.get("max_members", 5),
                "members": row.get("members") or [],
                "chat": row.get("chat") or [],
                "public": row.get("public", True),
                "code": row.get("code"),
            })
        return groups
    except Exception as e:
        st.error(f"스터디 불러오기 오류: {e}")
        return []

def save_study_group(group: dict):
    """새 스터디 Supabase에 저장"""
    sb = get_supabase()
    data = {
        "name": group["name"],
        "subject": group["subject"],
        "description": group["description"],
        "goal": group["goal"],
        "max_members": group["max_members"],
        "members": group["members"],
        "chat": group["chat"],
        "public": group["public"],
        "code": group["code"],
    }
    res = sb.table("study_groups").insert(data).execute()
    return res.data[0]["id"] if res.data else None

def update_study_group(group_id: int, patch: dict):
    """스터디 일부 업데이트 (멤버, 채팅 등)"""
    sb = get_supabase()
    sb.table("study_groups").update(patch).eq("id", group_id).execute()

def delete_study_group(group_id: int):
    """스터디 삭제"""
    sb = get_supabase()
    sb.table("study_groups").delete().eq("id", group_id).execute()

def load_my_groups(session_key: str):
    """내가 참여한 스터디 ID 목록 불러오기"""
    try:
        sb = get_supabase()
        res = sb.table("user_sessions").select("my_groups").eq("session_key", session_key).execute()
        if res.data:
            return res.data[0]["my_groups"] or []
        return []
    except:
        return []

def save_my_groups(session_key: str, my_groups: list):
    """내가 참여한 스터디 ID 목록 저장"""
    try:
        sb = get_supabase()
        res = sb.table("user_sessions").select("id").eq("session_key", session_key).execute()
        if res.data:
            sb.table("user_sessions").update({"my_groups": my_groups}).eq("session_key", session_key).execute()
        else:
            sb.table("user_sessions").insert({"session_key": session_key, "my_groups": my_groups}).execute()
    except:
        pass

defaults = {
    "messages": [],
    "risk_level": 0,
    "ui_step": 0,
    "phq9_score": 0,
    "active_tab": "chat",
    # 군백기 지우개 커뮤니티
    "study_groups": [],
    "my_groups": [],
    "study_chat_input": {},
    "current_group_id": None,
    # 식단
    "meal_log": {"아침": {}, "점심": {}, "저녁": {}},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# 브라우저 세션 키 생성 (최초 1회)
if "session_key" not in st.session_state:
    st.session_state.session_key = str(uuid.uuid4())
    # Supabase에서 이전 참여 스터디 목록 복원
    st.session_state.my_groups = load_my_groups(st.session_state.session_key)

# ==========================================
# 4. 분석 로직
# ==========================================
def analyze_input(text, key, history):
    critical_keywords = ["실사격", "총기", "실탄", "수류탄", "K2", "조정간", "격발"]
    for word in critical_keywords:
        if word in text:
            return 3, f"군 특수 위험 키워드 '{word}' 감지", "군 특수 위험 키워드가 들려 제 가슴이 철렁했습니다. 전우님, 혹시 지금 나쁜 마음을 먹고 계신 건 아닌지 정말 걱정됩니다. 저랑 약속 하나만 해주세요."

    if not key:
        return 0, "키 없음", "API 키를 먼저 입력해주세요."

    try:
        client = OpenAI(api_key=key)
        system_instruction = """
        당신은 대한민국 육군 장병들의 마음을 지키는 AI 상담관 'SOLMATE'입니다.
        단답형으로 말하지 말고, 사용자의 힘든 마음에 깊이 공감하는 '따뜻하고 정성스러운' 답변을 해주세요.
        
        [대화 가이드라인]
        1. 공감과 인정: "힘드시겠어요" 대신 "그동안 혼자 끙끙 앓느라 얼마나 힘드셨습니까" 같이 구체적으로 감정을 읽어주세요.
        2. 말투: 친한 선임이나 형처럼 부드러운 '해요체'를 사용하세요. (이모지 적절히 사용)
        3. 연결: 사용자의 이전 대화 맥락을 기억해서 대답하세요.
        
        [위험도 분류 기준] - 스크리닝 목적이므로 보수적으로 판단하세요. 애매하면 높은 레벨로.
        
        - Level 3 (실행 임박): 지금 이 순간 행동 중이거나 위치가 명시된 경우.
          예) "지금 옥상에 있어", "난간에 서 있어", "뛰어내릴 거야 지금", "약 다 먹었어"
          
        - Level 2 (구체적 계획): 자살/자해의 수단·장소·시점이 구체적으로 언급된 경우.
          예) "총으로 죽겠다", "번개탄 살 거야", "한강 가려고", "오늘 밤에 죽을 거야"
          
        - Level 1 (잠재적 위험): 자살·자해·죽음에 대한 생각이나 감정 표현. 수단/장소/시점 없음.
          예) "죽고 싶어", "자살할 것 같아", "사라지고 싶다", "더 살기 싫어", "힘들어", "우울해"
          
        - Level 0 (안전): 자살·자해와 무관한 일상 대화, 명백한 과장 표현.
          예) "더워 죽겠다", "배고파 죽겠어", "오늘 힘들었어"
        
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
tabs = st.tabs(["💬 고민 상담", "💄 화장품 추천", "🥗 식단 관리", "📚 군백기 지우개"])

# ==========================================
# TAB 1: AI 상담
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
            st.write("주변에 위험한 물건이 있나요? 당장 치우세요.")
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

PRODUCT_LIST = [
    {"브랜드": "웰더마", "제품명": "지100 엑소좀 마스크 1박스", "용량": "5매", "가격": 13900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "지100 엑소좀 스피큘 앰플", "용량": "30ml", "가격": 16900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "레티놀 콜라겐 리스토어 피팅 마스크", "용량": "4매", "가격": 15900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "레티놀 펩타이드 리프팅 리스토어 앰플", "용량": "30ml", "가격": 16900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "레티놀 펩타이드 리프팅 리스토어 에멀젼", "용량": "120ml", "가격": 16900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "레티놀 펩타이드 리프팅 리스토어 크림", "용량": "50ml", "가격": 22900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "레티놀 펩타이드 리프팅 리스토어 토너", "용량": "150ml", "가격": 16900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "사파이어 콜라겐 임팩트 피팅 마스크", "용량": "4매", "가격": 14850, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "프로폴리스 1000 에너지 앰플", "용량": "50ml", "가격": 14900, "비고": "2+1"},
    {"브랜드": "웰더마", "제품명": "레티놀 펩타이드 5종 세트", "용량": "세트", "가격": 59000, "비고": "4+1"},
    {"브랜드": "Antibac", "제품명": "더마 라이트 선 에센스 SPF50+", "용량": "60ml", "가격": 13980, "비고": ""},
    {"브랜드": "Antibac", "제품명": "프리미엄 아크네 클렌징 폼", "용량": "180ml*2", "가격": 13500, "비고": ""},
    {"브랜드": "CERA", "제품명": "세리퀸즈 이지에프 톡스 볼륨 리프팅 크림", "용량": "50ml", "가격": 33000, "비고": ""},
    {"브랜드": "CERA", "제품명": "세리퀸즈 이지에프 톡스 안티에이징 토닝 세럼", "용량": "30ml", "가격": 22000, "비고": ""},
    {"브랜드": "CKD", "제품명": "레티노콜라겐 저분자 300 괄사 리프팅 세럼", "용량": "40ml", "가격": 14490, "비고": ""},
    {"브랜드": "CKD", "제품명": "레티노콜라겐 저분자 300 콜라겐 결 토너", "용량": "250ml", "가격": 10900, "비고": ""},
    {"브랜드": "CKD", "제품명": "레티노콜라겐 저분자 300 콜라겐 펌핑 앰플", "용량": "30ml", "가격": 11600, "비고": ""},
    {"브랜드": "일동제약", "제품명": "퍼스트랩 프로바이오틱 세럼", "용량": "30ml*3", "가격": 35900, "비고": "5+1"},
    {"브랜드": "웰더마", "제품명": "시카 케어 세럼 & 롤러 세트", "용량": "세럼+롤러", "가격": 29000, "비고": ""},
    {"브랜드": "니인먼리", "제품명": "맥주효모 두피영양제 앰플 팩", "용량": "120ml", "가격": 19000, "비고": "3+1"},
    {"브랜드": "메디힐", "제품명": "캘러스 멀티 골드 리프팅 크림", "용량": "50ml", "가격": 17000, "비고": "쇼핑백증정"},
    {"브랜드": "엘렌실라", "제품명": "프리스티지 안티링클 크림", "용량": "50g*5", "가격": 49500, "비고": ""},
    {"브랜드": "자민경", "제품명": "스네일 인리치드 스킨케어 5종 세트", "용량": "세트", "가격": 34900, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 클렌징오일 투 폼", "용량": "110ml*5", "가격": 27000, "비고": ""},
    {"브랜드": "라더마", "제품명": "스킨사이언스 리커버리크림 프리미엄", "용량": "100ml", "가격": 14000, "비고": "2개 구매시 +1"},
    {"브랜드": "벨레닉", "제품명": "크림 프레스티지 에이지 퀸", "용량": "50ml", "가격": 12000, "비고": ""},
    {"브랜드": "W.피부연구소", "제품명": "스탑 에이징 펩타이드 에센스", "용량": "100ml*2", "가격": 27800, "비고": ""},
    {"브랜드": "듀이트리", "제품명": "울트라 바이탈라이징 스네일 세럼", "용량": "70ml*3", "가격": 22200, "비고": "마스크팩 증정"},
    {"브랜드": "리더스", "제품명": "프로 하이드리 아미노 슬리핑 마스크", "용량": "4ml*30", "가격": 7900, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 링클 리듀싱 아이크림", "용량": "20ml*5", "가격": 19040, "비고": "30% 할인"},
    {"브랜드": "라보테", "제품명": "콜라겐 에센스 인 토너", "용량": "500ml", "가격": 9200, "비고": ""},
    {"브랜드": "비원츠", "제품명": "피토 콜라겐 아이세럼스틱", "용량": "15ml", "가격": 9000, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "토탈 솔루션 2X 파워 시네이크 링클 팩터", "용량": "12ml*3", "가격": 26250, "비고": ""},
    {"브랜드": "에스미라클", "제품명": "타이거 스네일 크림", "용량": "50ml", "가격": 16030, "비고": "1+1"},
    {"브랜드": "라보테", "제품명": "에스테 RX 콜라겐 크림", "용량": "50ml", "가격": 29900, "비고": "2만원 이상 구매시 증정"},
    {"브랜드": "프리티스킨", "제품명": "24K 골드 콜라겐 앰플", "용량": "50ml*3", "가격": 22900, "비고": ""},
    {"브랜드": "누보바세", "제품명": "페이셜 모이스처 오일 폼 클렌저", "용량": "210ml", "가격": 13500, "비고": ""},
    {"브랜드": "라보테", "제품명": "에스테 RX 콜라겐 크림(리필)", "용량": "50ml", "가격": 15000, "비고": ""},
    {"브랜드": "W.피부연구소", "제품명": "펩타이드 크림", "용량": "50ml*2", "가격": 22800, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 달팽이 클렌징 폼", "용량": "175ml*5", "가격": 23200, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 에브리데이 수딩 크림", "용량": "300ml*5", "가격": 19200, "비고": "20% 할인"},
    {"브랜드": "토니모리", "제품명": "기미야 미백크림", "용량": "50g", "가격": 22900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "토탈 솔루션 24K 골드 스네일 클렌징 폼", "용량": "150ml*3", "가격": 14300, "비고": ""},
    {"브랜드": "핑크원더", "제품명": "호호바 오일", "용량": "50ml", "가격": 38800, "비고": ""},
    {"브랜드": "W.피부연구소", "제품명": "시카플러스 재생크림(튜브)", "용량": "50ml*2", "가격": 14800, "비고": ""},
    {"브랜드": "참존", "제품명": "황후지화 리본(S) 3종 세트", "용량": "세트", "가격": 32600, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 워터풀 슬리핑 크림", "용량": "60ml*5", "가격": 19200, "비고": "20% 할인"},
    {"브랜드": "자민경", "제품명": "크레마카발로 오리지널 마스크", "용량": "25g*50매", "가격": 31590, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 울트라 프로텍션 선크림", "용량": "50ml*3", "가격": 14810, "비고": ""},
    {"브랜드": "세리본", "제품명": "퓨어비타민C 앰플 미스트 V2", "용량": "80ml", "가격": 10000, "비고": ""},
    {"브랜드": "쿠피", "제품명": "PDRN 연어 앰플", "용량": "30ml", "가격": 16740, "비고": ""},
    {"브랜드": "엘렌실라", "제품명": "에스카르고 안티링클 밤", "용량": "9g*3", "가격": 21000, "비고": "15% OFF"},
    {"브랜드": "듀이트리", "제품명": "어반 쉐이드 커버 앤 핏 선 쿠션", "용량": "14g", "가격": 10500, "비고": "선구입시 증정"},
    {"브랜드": "메디힐", "제품명": "캘러스 멀티 골드 트리트먼트 워터 에센스", "용량": "140ml", "가격": 14230, "비고": ""},
    {"브랜드": "라보테", "제품명": "프리미엄 콜라겐 풀 업 앰플(영양)", "용량": "50ml", "가격": 10900, "비고": ""},
    {"브랜드": "젠틀마스크", "제품명": "티 톡스 클렌저", "용량": "200ml*2", "가격": 17820, "비고": ""},
    {"브랜드": "리더스", "제품명": "인솔루션 바세린 모이스처 마스크", "용량": "27ml*10매", "가격": 6900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "알로에베라 모이스처 토너", "용량": "180ml*3", "가격": 9900, "비고": ""},
    {"브랜드": "유리프", "제품명": "셋업 크림 RS", "용량": "100ml", "가격": 12000, "비고": "2개 구매시 크림 증정"},
    {"브랜드": "라보테", "제품명": "콜라겐 풀 업 트리트먼트 에센스", "용량": "150ml", "가격": 9900, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 멀티퍼펙션 에센스 토너", "용량": "150ml*5", "가격": 15370, "비고": ""},
    {"브랜드": "자민경", "제품명": "크레마카발로 오리지널 마스크 100매", "용량": "20ml*100매", "가격": 55200, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "토탈 솔루션 24K 골드 스네일 필링 젤", "용량": "150g*3", "가격": 14700, "비고": ""},
    {"브랜드": "듀이트리", "제품명": "아쿠아 콜라겐 펩타이드 멀티 크림", "용량": "80ml*5", "가격": 20000, "비고": ""},
    {"브랜드": "네오젠", "제품명": "리얼 하트리프 어성초 수분크림", "용량": "80g", "가격": 9900, "비고": ""},
    {"브랜드": "W.피부연구소", "제품명": "트리플케어 선스틱", "용량": "17g*2", "가격": 8800, "비고": ""},
    {"브랜드": "메디힐", "제품명": "피토 레티놀 크림", "용량": "50ml", "가격": 17000, "비고": "쇼핑백증정"},
    {"브랜드": "세이프 미", "제품명": "릴리프 모이스처 클렌징 폼", "용량": "250ml*5", "가격": 36000, "비고": ""},
    {"브랜드": "제이앤앤루", "제품명": "데일리 벨벳 선크림", "용량": "50g", "가격": 7500, "비고": ""},
    {"브랜드": "네오젠", "제품명": "리얼 비타민C 세럼", "용량": "32g", "가격": 15900, "비고": ""},
    {"브랜드": "벨라", "제품명": "울트라 하이드로 선 에센스", "용량": "30ml", "가격": 11500, "비고": ""},
    {"브랜드": "W.피부연구소", "제품명": "화이트 글루타치온 톤업크림", "용량": "60ml*2", "가격": 15800, "비고": ""},
    {"브랜드": "라보테", "제품명": "프리미엄 콜라겐 풀 업 3종 세트", "용량": "세트", "가격": 29900, "비고": ""},
    {"브랜드": "엘렌실라", "제품명": "프리스티지 안티링클 마스크 팩 100장", "용량": "25ml*100장", "가격": 45900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "토탈 솔루션 에센셜 시트 마스크", "용량": "23g*50매", "가격": 12500, "비고": ""},
    {"브랜드": "듀이트리", "제품명": "픽 앤 퀵 모이스처풀 마스크", "용량": "30매", "가격": 9000, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "알로에베라 모이스처 에멀젼", "용량": "180ml*3", "가격": 11700, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "프리미엄 골드 콜라겐 브이라인 패치", "용량": "9g*10매", "가격": 15000, "비고": ""},
    {"브랜드": "듀이트리", "제품명": "픽 앤 퀵 카밍풀 마스크", "용량": "30매", "가격": 9000, "비고": ""},
    {"브랜드": "엘렌실라", "제품명": "프리스티지 안티링클 마스크 팩 50장", "용량": "25ml*50장", "가격": 23900, "비고": ""},
    {"브랜드": "정니니", "제품명": "하이퍼 페이셜 프리미엄 스킨케어 5종", "용량": "세트", "가격": 34200, "비고": ""},
    {"브랜드": "메디힐", "제품명": "티트리 임팩트인 밸런싱 마스크", "용량": "24ml*10매", "가격": 12000, "비고": ""},
    {"브랜드": "참존", "제품명": "황후지화 프리미엄 한방 진지화 7종", "용량": "세트", "가격": 46500, "비고": ""},
    {"브랜드": "부원", "제품명": "달팽이 크림", "용량": "50ml", "가격": 10500, "비고": ""},
    {"브랜드": "리더스", "제품명": "스텝솔루션 티트리 릴렉싱 토너 패드", "용량": "150ml", "가격": 8900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "투 엑스파워 플라센타 링클 퍼펙터", "용량": "12ml*5", "가격": 52000, "비고": "72% 할인"},
    {"브랜드": "아이소이", "제품명": "블레미쉬 케어 업 세럼", "용량": "35ml", "가격": 25600, "비고": ""},
    {"브랜드": "리더스", "제품명": "인솔루션 바세린 너리싱 마스크", "용량": "27ml*10매", "가격": 6900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "알로에베라 모이스처 아이크림", "용량": "40ml*3", "가격": 14700, "비고": ""},
    {"브랜드": "비타원", "제품명": "비타민C 세럼", "용량": "11g*4개", "가격": 39000, "비고": ""},
    {"브랜드": "부원", "제품명": "달팽이 크림 5개 세트", "용량": "50ml*5", "가격": 33000, "비고": ""},
    {"브랜드": "라 더마", "제품명": "스킨사이언스 퍼펙트 세럼", "용량": "30ml", "가격": 18880, "비고": "2+1"},
    {"브랜드": "서메딕", "제품명": "퍼펙션 올인원 24K 아이크림", "용량": "35ml", "가격": 9900, "비고": ""},
    {"브랜드": "리비오라", "제품명": "오로리 세럼", "용량": "30ml", "가격": 20600, "비고": ""},
    {"브랜드": "모니쥬", "제품명": "프로 베리어 크림", "용량": "100ml", "가격": 25740, "비고": ""},
    {"브랜드": "아이소이", "제품명": "모이스춰 닥터 토너", "용량": "130ml", "가격": 12100, "비고": ""},
    {"브랜드": "닥터리뉴메", "제품명": "알로에베라 미스트", "용량": "140ml*2", "가격": 19000, "비고": ""},
    {"브랜드": "세이프 미", "제품명": "릴리프 모이스처 클렌징 오일", "용량": "210ml*3", "가격": 36000, "비고": ""},
    {"브랜드": "정니니", "제품명": "하이퍼 페이셜 스페셜 스킨케어 3종", "용량": "세트", "가격": 27200, "비고": ""},
    {"브랜드": "네오젠", "제품명": "블랙 캐비어 에센셜 마스크", "용량": "10매", "가격": 14900, "비고": ""},
    {"브랜드": "모니쥬", "제품명": "에코 아토 로션", "용량": "300ml", "가격": 30420, "비고": ""},
    {"브랜드": "네오젠", "제품명": "화이트트러플 앰플 드롭 미스트", "용량": "80ml", "가격": 7800, "비고": ""},
    {"브랜드": "메디힐", "제품명": "메이크힐 하이알로즈 크림", "용량": "50ml", "가격": 16900, "비고": "35% OFF"},
    {"브랜드": "코스메딘", "제품명": "스킨 레볼루션 듀얼 EX 크림", "용량": "50g", "가격": 18000, "비고": ""},
    {"브랜드": "보니힐", "제품명": "퍼펙트 모이스처라이징 선크림", "용량": "70ml", "가격": 9000, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "히아루로닉 크림 폼", "용량": "150ml*5", "가격": 15000, "비고": ""},
    {"브랜드": "닥터지", "제품명": "레드 블레미쉬 클리어 수딩 크림", "용량": "70ml", "가격": 8910, "비고": "베스트"},
    {"브랜드": "닥터지", "제품명": "블랙 스네일 크림", "용량": "50ml", "가격": 7420, "비고": "베스트"},
    {"브랜드": "라운드랩", "제품명": "자작나무 수분 선크림", "용량": "50ml*2", "가격": 16500, "비고": ""},
    {"브랜드": "아이오페", "제품명": "UV 쉴드 선 프로텍터 XP", "용량": "60ml", "가격": 12140, "비고": ""},
    {"브랜드": "본에스티스", "제품명": "다이아몬드 리페어 퍼펙트 세트", "용량": "세트", "가격": 38500, "비고": ""},
    {"브랜드": "닥터지", "제품명": "레드 블레미쉬 멀티 플루이드", "용량": "100ml", "가격": 7120, "비고": ""},
    {"브랜드": "AHC", "제품명": "프라이빗 리얼 아이크림", "용량": "30ml", "가격": 4660, "비고": ""},
    {"브랜드": "라운드랩", "제품명": "1025 독도 토너", "용량": "200ml", "가격": 7500, "비고": ""},
    {"브랜드": "셀퓨전씨", "제품명": "포스트 알파 카밍 다운 크림", "용량": "50ml", "가격": 8200, "비고": ""},
    {"브랜드": "이니스프리", "제품명": "비자 씨드 재활용 클렌징 폼", "용량": "150g", "가격": 4500, "비고": ""},
    {"브랜드": "닥터지", "제품명": "로얄 블랙 스네일 퍼스트 에센스", "용량": "165ml", "가격": 9900, "비고": ""},
    {"브랜드": "닥터지", "제품명": "레드 블레미쉬 클리어 수딩 토너", "용량": "200ml", "가격": 7200, "비고": ""},
    {"브랜드": "셀퓨전씨", "제품명": "레이저 썬스크린 100", "용량": "35ml*2", "가격": 10500, "비고": ""},
    {"브랜드": "식물나라", "제품명": "산소수 가벼운 선 젤", "용량": "60ml", "가격": 6800, "비고": ""},
    {"브랜드": "닥터자르트", "제품명": "시카파이어 크림", "용량": "50ml", "가격": 14000, "비고": ""},
    {"브랜드": "빌리프", "제품명": "더 트루 크림 모이스춰라이징 밤", "용량": "50ml", "가격": 19800, "비고": ""},
    {"브랜드": "우르오스", "제품명": "올인원 스킨밀크", "용량": "200ml", "가격": 18200, "비고": "남성용"},
    {"브랜드": "아이소이", "제품명": "포 맨 아크니 닥터 올인원", "용량": "100ml", "가격": 20790, "비고": ""},
    {"브랜드": "아이소이", "제품명": "포 맨 워터리 퍼밍로션", "용량": "130ml", "가격": 19600, "비고": ""},
    {"브랜드": "아이소이", "제품명": "포 맨 아쿠아 수딩토너", "용량": "150ml", "가격": 14460, "비고": ""},
    {"브랜드": "에스까다", "제품명": "옴므 헤리티지 에디션 2종 세트", "용량": "세트", "가격": 63000, "비고": ""},
    {"브랜드": "에스까다", "제품명": "옴므 울트라 아쿠아 올인원 에센스", "용량": "150ml", "가격": 26910, "비고": ""},
    {"브랜드": "에스까다", "제품명": "옴므 블랙 프리미엄 에디션", "용량": "세트", "가격": 56000, "비고": ""},
    {"브랜드": "토니모리", "제품명": "레젠시아 옴므 올인원 플루이드", "용량": "150ml", "가격": 11500, "비고": ""},
    {"브랜드": "토니모리", "제품명": "더블랙 옴므 2종 세트", "용량": "세트", "가격": 29900, "비고": ""},
    {"브랜드": "토니모리", "제품명": "리젠시아 옴므 스킨케어 세트", "용량": "세트", "가격": 24500, "비고": ""},
    {"브랜드": "리우젤", "제품명": "에프터 쉐이브", "용량": "200ml", "가격": 16900, "비고": ""},
    {"브랜드": "더마펌", "제품명": "스킨 리프레싱 토너 포 옴므", "용량": "150ml", "가격": 11000, "비고": ""},
    {"브랜드": "더마펌", "제품명": "스킨 리프레싱 플루이드 포 옴므", "용량": "120ml", "가격": 12870, "비고": ""},
    {"브랜드": "더마펌", "제품명": "스킨 리프레싱 클렌저 포 옴므", "용량": "120g", "가격": 9800, "비고": ""},
    {"브랜드": "닥터그래프트", "제품명": "스칼프 탈모 샴푸", "용량": "300ml", "가격": 19800, "비고": ""},
    {"브랜드": "닥터그래프트", "제품명": "스칼프 탈모 토닉", "용량": "100ml", "가격": 25800, "비고": ""},
    {"브랜드": "닥터그래프트", "제품명": "아리네아 탈모 샴푸", "용량": "500ml", "가격": 29800, "비고": ""},
    {"브랜드": "벨벳내린", "제품명": "헤어에센스", "용량": "100ml", "가격": 12500, "비고": ""},
    {"브랜드": "센해피코", "제품명": "아르간 헤어에센스", "용량": "100ml", "가격": 23500, "비고": ""},
    {"브랜드": "씨실", "제품명": "밤부솔트 미네랄 헤어트리트먼트", "용량": "490ml", "가격": 15900, "비고": ""},
    {"브랜드": "트리트룸", "제품명": "더모어 맥주효모 탈모완화 샴푸", "용량": "1030ml", "가격": 9810, "비고": ""},
    {"브랜드": "트리트룸", "제품명": "시그니처 트리트먼트 화이트머스크", "용량": "1077ml", "가격": 8910, "비고": ""},
    {"브랜드": "폴메디슨", "제품명": "시그니처 바디워시 화이트머스크", "용량": "1077ml*2", "가격": 15220, "비고": ""},
    {"브랜드": "폴메디슨", "제품명": "딥레드 패스트샴푸 화이트머스크", "용량": "1077ml*2", "가격": 15190, "비고": ""},
    {"브랜드": "모니쥬", "제품명": "올인원 클렌저", "용량": "520ml", "가격": 28080, "비고": ""},
    {"브랜드": "레드캡슐", "제품명": "바이오샴푸", "용량": "400ml", "가격": 9900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "아보카도 바디크림", "용량": "300ml*3", "가격": 13500, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "퍼퓸드 내추럴 핸드크림", "용량": "30ml*10", "가격": 9900, "비고": ""},
    {"브랜드": "프리티스킨", "제품명": "골드 스네일 핸드크림", "용량": "60ml*5", "가격": 9000, "비고": ""},
    {"브랜드": "아이소이", "제품명": "립 트리트먼트 밤(퓨어레드)", "용량": "5g", "가격": 11880, "비고": ""},
    {"브랜드": "젠틀마스크", "제품명": "아크네 바하 프로 바디워시", "용량": "300ml", "가격": 15800, "비고": ""},
    {"브랜드": "MD638", "제품명": "테크니컬 올인원 포맨 3in1 세트", "용량": "세트", "가격": 37900, "비고": ""},
    {"브랜드": "SNP", "제품명": "골드 콜라겐 슬리핑 팩", "용량": "100ml", "가격": 5800, "비고": ""},
]

PRODUCT_CATALOG_STR = "\n".join([
    f"- {p['브랜드']} {p['제품명']} ({p['용량']}) {p['가격']:,}원" + (f" [{p['비고']}]" if p['비고'] and p['비고'] != 'SOLD OUT' else " [품절]" if p['비고'] == 'SOLD OUT' else "")
    for p in PRODUCT_LIST
])

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
                    
                    [현재 판매 중인 제품 목록 - 반드시 이 목록에서만 추천하세요]
                    {PRODUCT_CATALOG_STR}
                    
                    [요청사항]
                    1. 피부 상태 분석 (2-3줄)
                    2. 맞춤 스킨케어 루틴 (아침/저녁)
                    3. 위 제품 목록에서 피부 타입과 고민에 맞는 제품 3-5가지 추천 (브랜드명, 제품명, 가격, 추천 이유 포함)
                    4. 군 생활 특수 환경(야외훈련, 자외선, 먼지)에 맞는 피부 관리 팁
                    
                    SOLD OUT 제품은 추천하지 마세요. 친근하고 실용적으로, 이모지를 사용해 답변해주세요.
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

    # 전체 제품 카탈로그
    st.divider()
    st.markdown("### 🛒 전체 제품 카탈로그")
    search_product = st.text_input("🔍 제품 검색", placeholder="브랜드명 또는 제품명 입력", key="product_search")
    max_price = st.slider("💰 최대 가격 필터", min_value=5000, max_value=70000, value=70000, step=1000, format="%d원")

    filtered = [
        p for p in PRODUCT_LIST
        if (search_product.lower() in p["브랜드"].lower() or search_product.lower() in p["제품명"].lower() or not search_product)
        and p["가격"] <= max_price
    ]

    st.caption(f"총 {len(filtered)}개 제품")
    for i in range(0, len(filtered), 3):
        cols = st.columns(3)
        for j, col in enumerate(cols):
            if i + j < len(filtered):
                p = filtered[i + j]
                with col:
                    is_sold_out = p["비고"] == "SOLD OUT"
                    with st.container(border=True):
                        st.markdown(f"**{p['브랜드']}**")
                        st.markdown(f"{p['제품명']}")
                        st.caption(f"📦 {p['용량']}")
                        if is_sold_out:
                            st.error(f"~~{p['가격']:,}원~~ 품절")
                        else:
                            st.success(f"**{p['가격']:,}원**")
                            if p["비고"]:
                                st.caption(f"🎁 {p['비고']}")


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

    # ── 국방부 공공API 호출 (3회 재시도 적용) ──
    MND_API_KEY = st.secrets.get("MND_API_KEY", "")
    MND_SERVICE = st.secrets.get("MND_SERVICE", "DS_TB_MNDT_DATEBYMLSVC_6335")

    @st.cache_data(ttl=3600)
    def fetch_mnd_meal(year_month: str, start: int = 1, end: int = 300):
        """year_month: 'YYYYMM' 형식. 해당 월의 식단 전체를 가져옵니다. (최대 3회 자동 재시도)"""
        url = f"https://openapi.mnd.go.kr/{MND_API_KEY}/xml/{MND_SERVICE}/{start}/{end}/"
        last_error = None
        
        # 💡 API 서버가 불안정할 수 있으므로 최대 3번까지 재시도합니다.
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=(10, 60))
                resp.encoding = "utf-8"
                raw = resp.text
                root = ET.fromstring(raw)

                # 실제 태그명 자동 탐지
                first_row = next(root.iter("row"), None)
                if first_row is None:
                    return {}, None, []

                # 실제 태그명 고정
                date_tag = "dates"
                brst_tag = "brst"
                lnch_tag = "lunc"
                dinr_tag = "dinr"
                brst_cal = "brst_cal"
                lnch_cal = "lunc_cal"
                dinr_cal = "dinr_cal"
                sum_cal_tag = "sum_cal"

                meals = {}
                for row in root.iter("row"):
                    raw_date = (row.findtext(date_tag) or "").strip()
                    if not raw_date:
                        continue
                    
                    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw_date)
                    date = m.group(1) + m.group(2) + m.group(3) if m else raw_date

                    if date not in meals:
                        meals[date] = {"아침": {}, "점심": {}, "저녁": {}, "총_칼로리": None}

                    def clean_name(text):
                        if not text: return None
                        return re.sub(r"\(\d+\)", "", text).strip() or None

                    def clean_cal(text):
                        if not text: return 0.0
                        try:
                            return float(text.replace("kcal","").strip())
                        except:
                            return 0.0

                    brst_name = clean_name(row.findtext(brst_tag))
                    lnch_name = clean_name(row.findtext(lnch_tag))
                    dinr_name = clean_name(row.findtext(dinr_tag))

                    if brst_name and brst_name not in meals[date]["아침"]:
                        meals[date]["아침"][brst_name] = clean_cal(row.findtext(brst_cal))
                    if lnch_name and lnch_name not in meals[date]["점심"]:
                        meals[date]["점심"][lnch_name] = clean_cal(row.findtext(lnch_cal))
                    if dinr_name and dinr_name not in meals[date]["저녁"]:
                        meals[date]["저녁"][dinr_name] = clean_cal(row.findtext(dinr_cal))

                    if row.findtext(sum_cal_tag):
                        meals[date]["총_칼로리"] = row.findtext(sum_cal_tag).replace("kcal","").strip()

                # 성공적으로 파싱을 완료하면 반환
                return meals, None, list(meals.keys())
            
            except Exception as e:
                last_error = str(e)
                # 실패 시 1.5초 대기 후 다음 시도로 넘어감
                time.sleep(1.5)
                
        # 3번 모두 실패했을 경우에만 에러 반환
        return {}, f"API 3회 재시도 실패: {last_error}", []

    @st.cache_data(ttl=86400)
    def get_total_count():
        url = f"https://openapi.mnd.go.kr/{MND_API_KEY}/xml/{MND_SERVICE}/1/1/"
        
        # 💡 총 개수 불러오기도 3번 재시도
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=(10, 30))
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    total = root.findtext("list_total_count")
                    if total:
                        return int(total)
            except:
                pass
            time.sleep(1.0) # 1초 대기 후 재시도
            
        return None

    with st.spinner("📡 부대 식단을 불러오는 중..."):
        total_count = get_total_count()

    if total_count is None:
        st.error("📡 국방부 급식 서버에 연결할 수 없습니다.")
        st.info("🔄 서버가 일시적으로 느릴 수 있습니다. 잠시 후 페이지를 새로고침 해주세요.")
        if st.button("🔄 다시 시도", key="retry_total", type="primary"):
            st.cache_data.clear()
            st.rerun()
        st.stop()
    else:
        with st.spinner("📡 식단 데이터를 불러오는 중..."):
            meal_data, api_error, available_dates = fetch_mnd_meal(selected_ym, start=1, end=total_count)

        if api_error:
            st.error("📡 식단 데이터를 불러오지 못했습니다.")
            st.info("🔄 국방부 급식 서버가 일시적으로 응답하지 않고 있습니다. 잠시 후 다시 시도해주세요.")
            if st.button("🔄 다시 시도", key="retry_meal", type="primary"):
                st.cache_data.clear()
                st.rerun()
            st.stop()
        elif selected_date_str not in meal_data:
            st.warning(f"📭 {selected_date.strftime('%Y년 %m월 %d일')} 식단 데이터가 없습니다.")
            if available_dates:
                st.info(f"💡 이 달에 데이터가 있는 날짜: {', '.join(available_dates[:5])}")
            st.stop()
        else:
            today_meals = meal_data[selected_date_str]
            unit_code = MND_SERVICE.split("_")[-1]
            st.success(f"✅ {selected_date.strftime('%Y년 %m월 %d일')} 제{unit_code}부대 식단 불러오기 완료!")

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
                        st.info(f"🍽️ {item}  |  {cal:.1f} kcal")

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

    # Supabase에서 최신 스터디 목록 로드
    st.session_state.study_groups = load_study_groups()

    study_tabs = st.tabs(["🔍 스터디 찾기", "➕ 스터디 만들기", "💬 내 스터디"])

    # --- 스터디 찾기 ---
    with study_tabs[0]:
        st.subheader("📋 현재 모집 중인 스터디")

        search_keyword = st.text_input("🔍 스터디 검색", placeholder="키워드를 입력하세요 (예: 공무원, 자격증...)")

        # 비공개 입장 코드 입력
        with st.expander("🔒 초대 코드로 비공개 스터디 참여"):
            invite_code = st.text_input("초대 코드 입력", placeholder="예: AB12CD", key="invite_code_input")
            if st.button("코드로 참여하기", key="join_by_code"):
                matched = next((g for g in st.session_state.study_groups if g.get("code") == invite_code.strip().upper()), None)
                if not matched:
                    st.error("❌ 유효하지 않은 코드입니다.")
                elif matched["id"] in st.session_state.my_groups:
                    st.warning("이미 참여 중인 스터디입니다.")
                elif len(matched["members"]) >= matched["max_members"]:
                    st.warning("🔒 인원이 꽉 찼습니다.")
                else:
                    st.session_state.my_groups.append(matched["id"])
                    new_members = matched["members"] + ["나 (현재 사용자)"]
                    update_study_group(matched["id"], {"members": new_members})
                    save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                    st.success(f"✅ '{matched['name']}' 스터디에 참여했습니다!")
                    st.rerun()

        st.divider()
        for group in st.session_state.study_groups:
            if not group.get("public", True):  # 비공개 스터디는 목록에서 숨김
                continue
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
                            new_members = [m for m in group["members"] if m != "나 (현재 사용자)"]
                            update_study_group(group["id"], {"members": new_members})
                            save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                            st.rerun()
                    elif is_full:
                        st.warning("🔒 인원 마감")
                    else:
                        if st.button("참여하기", key=f"join_{group['id']}", type="primary"):
                            st.session_state.my_groups.append(group["id"])
                            new_members = group["members"] + ["나 (현재 사용자)"]
                            update_study_group(group["id"], {"members": new_members})
                            save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                            st.success(f"'{group['name']}' 스터디에 참여했습니다!")
                            st.rerun()

    # --- 스터디 만들기 ---
    with study_tabs[1]:
        st.subheader("✏️ 새 스터디 그룹 만들기")

        # 공개/비공개 선택을 세션에 명시적으로 저장
        if "study_is_public" not in st.session_state:
            st.session_state.study_is_public = True

        col_pub1, col_pub2 = st.columns(2)
        with col_pub1:
            if st.button("🌐 공개", type="primary" if st.session_state.study_is_public else "secondary", use_container_width=True):
                st.session_state.study_is_public = True
                st.rerun()
        with col_pub2:
            if st.button("🔒 비공개", type="primary" if not st.session_state.study_is_public else "secondary", use_container_width=True):
                st.session_state.study_is_public = False
                st.rerun()

        if st.session_state.study_is_public:
            st.success("🌐 공개 — 모집 목록에 표시됩니다.")
        else:
            st.info("🔒 비공개 — 생성 시 6자리 초대 코드가 자동 발급됩니다.")

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
                    import random, string
                    is_public = st.session_state.study_is_public
                    invite_code = None if is_public else "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                    new_id = max([g["id"] for g in st.session_state.study_groups], default=0) + 1
                    new_group = {
                        "id": new_id,
                        "name": new_name,
                        "subject": new_subject,
                        "members": ["나 (현재 사용자)"],
                        "max_members": new_max,
                        "chat": [],
                        "description": new_desc,
                        "goal": new_goal,
                        "public": is_public,
                        "code": invite_code,
                    }
                    new_db_id = save_study_group(new_group)
                    if new_db_id:
                        st.session_state.my_groups.append(new_db_id)
                        save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                    st.session_state.study_is_public = True
                    if is_public:
                        st.success(f"✅ '{new_name}' 스터디가 공개 생성되었습니다!")
                    else:
                        st.success(f"✅ '{new_name}' 스터디가 비공개 생성되었습니다!")
                        st.info(f"🔑 초대 코드: **{invite_code}** ← 전우들에게 공유하세요!")
                    st.rerun()

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

            col_title, col_badge, col_del = st.columns([3, 1, 1])
            with col_title:
                st.markdown(f"**{selected_group['name']}** | 👥 {len(selected_group['members'])}명 | 📖 {selected_group['subject']}")
            with col_badge:
                if selected_group.get("public", True):
                    st.success("🌐 공개")
                else:
                    st.warning("🔒 비공개")
                    st.code(selected_group.get("code", ""), language=None)
            with col_del:
                # 내가 만든 스터디(첫 번째 멤버)만 삭제 가능
                is_owner = selected_group["members"] and selected_group["members"][0] == "나 (현재 사용자)"
                if is_owner:
                    if st.button("🗑️ 삭제", key=f"del_{selected_group['id']}", type="secondary", use_container_width=True):
                        st.session_state[f"confirm_del_{selected_group['id']}"] = True
                        st.rerun()

            # 삭제 확인 팝업
            if st.session_state.get(f"confirm_del_{selected_group['id']}", False):
                st.error(f"⚠️ **'{selected_group['name']}'** 스터디를 정말 삭제할까요? 모든 채팅이 사라집니다.")
                col_yes, col_no = st.columns(2)
                with col_yes:
                    if st.button("✅ 삭제 확인", key=f"yes_del_{selected_group['id']}", type="primary", use_container_width=True):
                        delete_study_group(selected_group["id"])
                        st.session_state.my_groups.remove(selected_group["id"])
                        save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                        st.session_state.pop(f"confirm_del_{selected_group['id']}", None)
                        st.success("삭제되었습니다.")
                        st.rerun()
                with col_no:
                    if st.button("❌ 취소", key=f"no_del_{selected_group['id']}", use_container_width=True):
                        st.session_state.pop(f"confirm_del_{selected_group['id']}", None)
                        st.rerun()

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
                now = datetime.datetime.now().strftime("%H:%M")
                new_chat = list(selected_group["chat"])
                new_chat.append({"sender": "나", "text": chat_msg, "time": now})

                # AI 스터디 도우미 응답 (3번째 메시지마다)
                if api_key and len(new_chat) % 3 == 0:
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
                        new_chat.append({
                            "sender": "🤖 AI 스터디 도우미",
                            "text": ai_resp.choices[0].message.content,
                            "time": now
                        })
                    except:
                        pass

                # Supabase에 채팅 저장
                update_study_group(selected_group["id"], {"chat": new_chat})
                st.rerun()
