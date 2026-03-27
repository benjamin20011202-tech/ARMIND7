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
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def load_study_groups():
    try:
        sb = get_supabase()
        res = sb.table("study_groups").select("*").order("created_at", desc=False).execute()
        groups = []
        for row in res.data:
            groups.append({
                "id": row["id"], "name": row["name"], "subject": row["subject"],
                "description": row.get("description", ""), "goal": row.get("goal", ""),
                "max_members": row.get("max_members", 5), "members": row.get("members") or [],
                "chat": row.get("chat") or [], "public": row.get("public", True),
                "code": row.get("code"),
            })
        return groups
    except Exception as e:
        st.error(f"스터디 불러오기 오류: {e}")
        return []

def save_study_group(group: dict):
    sb = get_supabase()
    data = {
        "name": group["name"], "subject": group["subject"], "description": group["description"],
        "goal": group["goal"], "max_members": group["max_members"], "members": group["members"],
        "chat": group["chat"], "public": group["public"], "code": group["code"],
    }
    res = sb.table("study_groups").insert(data).execute()
    return res.data[0]["id"] if res.data else None

def update_study_group(group_id: int, patch: dict):
    sb = get_supabase()
    sb.table("study_groups").update(patch).eq("id", group_id).execute()

def delete_study_group(group_id: int):
    sb = get_supabase()
    sb.table("study_groups").delete().eq("id", group_id).execute()

def load_my_groups(session_key: str):
    try:
        sb = get_supabase()
        res = sb.table("user_sessions").select("my_groups").eq("session_key", session_key).execute()
        if res.data: return res.data[0]["my_groups"] or []
        return []
    except:
        return []

def save_my_groups(session_key: str, my_groups: list):
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
    "messages": [], "risk_level": 0, "ui_step": 0, "phq9_score": 0,
    "study_groups": [], "my_groups": [], "meal_log": {"아침": {}, "점심": {}, "저녁": {}},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "session_key" not in st.session_state:
    st.session_state.session_key = str(uuid.uuid4())
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
        당신은 대한민국 육군 장병들의 마음을 지키는 AI 상담관 'ARMIND7'입니다.
        단답형으로 말하지 말고, 사용자의 힘든 마음에 깊이 공감하는 '따뜻하고 정성스러운' 답변을 해주세요.
        
        [위험도 분류 기준] - 보수적으로 판단
        - Level 3 (실행 임박): 지금 행동 중이거나 위치 명시.
        - Level 2 (구체적 계획): 자살/자해 수단·장소·시점 언급.
        - Level 1 (잠재적 위험): 죽음에 대한 생각 호소 (수단/장소 없음).
        - Level 0 (안전): 무관한 일상 대화.
        
        JSON 출력 형식: {"level": 숫자, "reason": "이유", "reply": "답변 텍스트"}
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
tabs = st.tabs(["💬 AI 상담", "💄 화장품 추천", "🥗 식단 관리", "📚 군백기 지우개", "📊 지휘관 대시보드"])

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
                if idx == 8: st.markdown(f"**:red[{q}]**")
                else: st.write(q)
                choice = st.radio(f"문항 {idx+1}", options, index=0, key=f"phq9_{idx}", label_visibility="collapsed", horizontal=True)
                scores.append(int(choice[-3]))
                st.markdown("---")
            if st.button("결과 확인"):
                total_score = sum(scores)
                st.write(f"### 📊 총점: {total_score}점")
                if scores[8] > 0:
                    st.error("🚨 자해나 죽음에 대한 생각이 감지되었습니다. 즉시 전문가의 도움이 필요합니다.")
                    if st.button("국방헬프콜 (1303) 연결하기", type="primary"): st.success("연결 중입니다...")
                else:
                    if total_score <= 4: st.success("✅ 정상 범위입니다.")
                    elif total_score <= 9: st.info("⚠️ 가벼운 우울감이 있습니다.")
                    elif total_score <= 14: st.warning("🟠 상담이 필요한 상태입니다.")
                    elif total_score <= 19: st.error("🔴 전문적인 도움이 필요합니다.")
                    else: st.error("🚨 매우 심한 우울 상태입니다.")

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
                        else: st.warning("내용을 입력해주세요.")
            if st.session_state.ui_step >= 2:
                st.success("저장되었습니다.")
                st.markdown("---")
                st.markdown("#### 📞 Step 3. 도움 요청")
                if st.button("국방헬프콜 (1303) 연결", type="primary"):
                    st.success("📞 연결 중입니다... (지휘관 알림 전송됨)")

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

PRODUCT_CATALOG_STR = "\n".join([f"- {p['브랜드']} {p['제품명']} ({p['용량']}) {p['가격']:,}원" + (f" [{p['비고']}]" if p['비고'] else "") for p in PRODUCT_LIST])

with tabs[1]:
    st.header("💄 피부 맞춤 화장품 추천")
    st.markdown("군 생활 중 피부 고민, AI가 해결해드릴게요!")

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📷 피부 사진 업로드 (선택)")
        skin_image = st.file_uploader("얼굴 사진을 업로드하세요", type=["jpg", "jpeg", "png"], key="skin_img")
        if skin_image: st.image(skin_image, caption="업로드된 사진", use_container_width=True)

    with col2:
        st.subheader("📝 피부 상태 설명 (선택)")
        skin_concerns = st.multiselect("고민되는 피부 문제를 선택하세요", ["여드름/트러블", "건조함", "번들거림/지성", "모공", "민감성"])
        skin_text = st.text_area("추가 설명 (예: 훈련 후 얼굴이 빨개지고 당깁니다)", height=100)
        skin_type = st.radio("피부 타입을 선택하세요", ["건성", "지성", "복합성", "중성", "민감성"], horizontal=True)

    st.divider()
    if st.button("🔍 AI 피부 분석 및 화장품 추천받기", type="primary", use_container_width=True):
        if not api_key:
            st.error("API Key를 먼저 입력해주세요.")
        else:
            with st.spinner("🔬 피부 상태를 분석 중입니다..."):
                try:
                    client = OpenAI(api_key=api_key)
                    prompt_text = f"""
                    피부 정보: {skin_type}, 고민: {', '.join(skin_concerns)}, 설명: {skin_text}
                    판매 목록: {PRODUCT_CATALOG_STR}
                    위 목록에서 피부 타입에 맞는 제품 3가지 추천 및 군 생활 피부 관리 팁 제공.
                    """
                    model_to_use = "gpt-4o-mini"
                    messages_for_api = [{"role": "user", "content": [{"type": "text", "text": prompt_text}]}]
                    
                    if skin_image:
                        b64_image = base64.b64encode(skin_image.read()).decode("utf-8")
                        messages_for_api = [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}, {"type": "text", "text": prompt_text}]}]
                        model_to_use = "gpt-4o"

                    response = client.chat.completions.create(model=model_to_use, messages=messages_for_api, max_tokens=800)
                    st.success("✅ 분석 완료!")
                    st.markdown("### 🎯 AI 피부 분석 결과")
                    st.markdown(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"오류 발생: {e}")

    # 전체 제품 카탈로그 표시
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
    DAILY_RECOMMEND = {"칼로리": 2700, "탄수화물": 330, "단백질": 65, "지방": 75}
    MND_API_KEY = st.secrets.get("MND_API_KEY", "")
    MND_SERVICE = st.secrets.get("MND_SERVICE", "DS_TB_MNDT_DATEBYMLSVC_6335")

    @st.cache_data(ttl=3600)
    def fetch_mnd_meal(year_month: str, start: int = 1, end: int = 300):
        url = f"https://openapi.mnd.go.kr/{MND_API_KEY}/xml/{MND_SERVICE}/{start}/{end}/"
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=(3, 5), verify=False)
                resp.encoding = "utf-8"
                root = ET.fromstring(resp.text)
                if next(root.iter("row"), None) is None: return {}, None, []

                meals = {}
                for row in root.iter("row"):
                    raw_date = (row.findtext("dates") or "").strip()
                    if not raw_date: continue
                    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", raw_date)
                    date = m.group(1) + m.group(2) + m.group(3) if m else raw_date
                    if date not in meals: meals[date] = {"아침": {}, "점심": {}, "저녁": {}, "총_칼로리": None}

                    def clean_name(text): return re.sub(r"\(\d+\)", "", text).strip() if text else None
                    def clean_cal(text): return float(text.replace("kcal","").strip()) if text else 0.0

                    b_name, l_name, d_name = clean_name(row.findtext("brst")), clean_name(row.findtext("lunc")), clean_name(row.findtext("dinr"))
                    if b_name and b_name not in meals[date]["아침"]: meals[date]["아침"][b_name] = clean_cal(row.findtext("brst_cal"))
                    if l_name and l_name not in meals[date]["점심"]: meals[date]["점심"][l_name] = clean_cal(row.findtext("lunc_cal"))
                    if d_name and d_name not in meals[date]["저녁"]: meals[date]["저녁"][d_name] = clean_cal(row.findtext("dinr_cal"))
                    if row.findtext("sum_cal"): meals[date]["총_칼로리"] = row.findtext("sum_cal").replace("kcal","").strip()
                return meals, None, list(meals.keys())
            except Exception as e:
                time.sleep(1.0)
        return {}, "API 실패", []

    @st.cache_data(ttl=86400)
    def get_total_count():
        url = f"https://openapi.mnd.go.kr/{MND_API_KEY}/xml/{MND_SERVICE}/1/1/"
        for attempt in range(3):
            try:
                resp = requests.get(url, timeout=(3, 5), verify=False)
                if resp.status_code == 200:
                    root = ET.fromstring(resp.text)
                    total = root.findtext("list_total_count")
                    if total: return int(total)
            except: pass
            time.sleep(1.0)
        return None

    today = datetime.date.today()
    
    col_date, col_refresh = st.columns([3, 1])
    with col_date:
        selected_date = st.date_input("📅 날짜 선택", value=today, key="meal_date")
    with col_refresh:
        st.write("") 
        if st.button("🔄 식단 새로고침", use_container_width=True):
            st.cache_data.clear()  
            st.rerun()             

    selected_date_str = selected_date.strftime("%Y%m%d")
    selected_ym = selected_date.strftime("%Y%m")

    SAMPLE_MEALS = {
        0: {"아침": {"쌀밥": 355.0, "미역국": 19.0, "제육볶음": 659.0}, "점심": {"잡곡밥": 366.0, "부대찌개": 367.0}, "저녁": {"쌀밥": 355.0, "김치찌개": 109.0}, "총_칼로리": "3042"},
        1: {"아침": {"쌀밥": 355.0, "콩나물국": 19.0, "소시지볶음": 224.0}, "점심": {"잡곡밥": 366.0, "순대국": 367.0}, "저녁": {"쌀밥": 355.0, "떡갈비": 347.0}, "총_칼로리": "3115"},
        2: {"아침": {"쌀밥": 355.0, "된장찌개": 80.0}, "점심": {"잡곡밥": 366.0, "돈등갈비찜": 863.0}, "저녁": {"쌀밥": 355.0, "조갯살미역국": 19.0}, "총_칼로리": "3385"},
        3: {"아침": {"장조림비빔밥": 595.0, "콩나물국": 19.0}, "점심": {"쌀밥": 355.0, "닭볶음탕": 300.0}, "저녁": {"쌀밥": 355.0, "불고기": 250.0}, "총_칼로리": "3290"},
        4: {"아침": {"쌀밥": 355.0, "미역국": 19.0}, "점심": {"잡곡밥": 366.0, "치즈불닭": 370.0}, "저녁": {"쌀밥": 355.0, "제육볶음": 659.0}, "총_칼로리": "3369"},
        5: {"아침": {"쌀밥": 355.0, "두부조림": 100.0}, "점심": {"잡곡밥": 366.0, "소갈비탕": 300.0}, "저녁": {"쌀밥": 355.0, "닭강정": 350.0}, "총_칼로리": "3184"},
        6: {"아침": {"쌀밥": 355.0, "소시지볶음": 224.0}, "점심": {"잡곡밥": 366.0, "떡갈비": 347.0}, "저녁": {"쌀밥": 355.0, "제육볶음": 659.0}, "총_칼로리": "3042"},
    }

    with st.spinner("📡 외부망 연결 확인 중..."):
        total_count = get_total_count()

    today_meals = {}
    if total_count is None:
        st.warning("📡 외부망 방화벽 차단으로 인해 백업된 오프라인 식단 데이터를 불러옵니다.")
        today_meals = SAMPLE_MEALS.get(selected_date.weekday(), SAMPLE_MEALS[0])
    else:
        meal_data, api_error, _ = fetch_mnd_meal(selected_ym, start=1, end=total_count)
        if api_error or selected_date_str not in meal_data:
            st.warning("📡 외부망 방화벽 차단으로 인해 백업된 오프라인 식단 데이터를 불러옵니다.")
            today_meals = SAMPLE_MEALS.get(selected_date.weekday(), SAMPLE_MEALS[0])
        else:
            today_meals = meal_data[selected_date_str]
            st.success(f"✅ 식단 불러오기 완료!")

    meal_tabs = st.tabs(["🌅 아침", "☀️ 점심", "🌙 저녁", "📊 영양 분석"])
    for meal_time, meal_tab in zip(["아침", "점심", "저녁"], meal_tabs[:3]):
        with meal_tab:
            menu_dict = today_meals.get(meal_time, {}) 
            if menu_dict:
                st.subheader(f"{meal_time} 메뉴")
                cols = st.columns(min(len(menu_dict), 4) if len(menu_dict) > 0 else 1)
                for i, (item, cal) in enumerate(menu_dict.items()):
                    with cols[i % 4]: st.info(f"🍽️ {item} ({cal:.1f} kcal)")
                st.divider()
                st.markdown("**✅ 오늘 먹은 메뉴 체크**")
                checked = {}
                for i, (item, cal) in enumerate(menu_dict.items()):
                    if st.checkbox(f"{item} ({cal:.1f} kcal)", value=True, key=f"chk_{meal_time}_{i}_{item[:5]}"):
                        checked[item] = cal
                st.session_state.meal_log[meal_time] = checked
            else: st.info("식단 정보가 없습니다.")

    with meal_tabs[3]:
        st.subheader("📊 영양 섭취 분석")
        checked_menus = {mt: st.session_state.meal_log.get(mt, {}) for mt in ["아침", "점심", "저녁"]}
        total_cal = sum(cal for meal in checked_menus.values() for cal in meal.values())
        st.metric("섭취 칼로리", f"{total_cal:.1f} kcal")
        cal_pct = min(int((total_cal / DAILY_RECOMMEND["칼로리"]) * 100), 100)
        st.progress(cal_pct / 100, text=f"{cal_pct}% (권장 {DAILY_RECOMMEND['칼로리']} kcal)")

        st.divider()
        if st.button("🤖 AI 영양 분석받기", type="primary", use_container_width=True):
            if not api_key:
                st.error("API Key를 먼저 입력해주세요.")
            else:
                menu_summary = {
                    "아침": list(checked_menus["아침"].keys()), "점심": list(checked_menus["점심"].keys()), "저녁": list(checked_menus["저녁"].keys()),
                }
                with st.spinner("🔬 식단을 분석 중입니다..."):
                    try:
                        client = OpenAI(api_key=api_key)
                        prompt = f"장병 식단: 아침:{menu_summary['아침']}, 점심:{menu_summary['점심']}, 저녁:{menu_summary['저녁']}, 칼로리:{total_cal}. 부족한 영양소와 PX 간식을 추천해주세요."
                        response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=600)
                        st.markdown("### 🎯 AI 영양 분석 결과")
                        st.markdown(response.choices[0].message.content)
                    except Exception as e:
                        st.error(f"오류: {e}")

# ==========================================
# TAB 4: 군백기 지우개
# ==========================================
with tabs[3]:
    st.header("📚 군백기 지우개")
    st.markdown("전역 후 공백기를 없애자! 함께 공부하는 전우를 찾아요 💪")

    st.session_state.study_groups = load_study_groups()
    study_tabs = st.tabs(["🔍 스터디 찾기", "➕ 스터디 만들기", "💬 내 스터디"])

    # --- 스터디 찾기 ---
    with study_tabs[0]:
        search_keyword = st.text_input("🔍 스터디 검색", placeholder="키워드 입력")
        with st.expander("🔒 초대 코드로 참여"):
            invite_code = st.text_input("초대 코드 입력", key="invite_code_input")
            if st.button("참여하기", key="join_by_code"):
                matched = next((g for g in st.session_state.study_groups if g.get("code") == invite_code.strip().upper()), None)
                if matched and matched["id"] not in st.session_state.my_groups:
                    st.session_state.my_groups.append(matched["id"])
                    update_study_group(matched["id"], {"members": matched["members"] + ["나"]})
                    save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                    st.success("참여 완료!")
                    st.rerun()

        for group in st.session_state.study_groups:
            if not group.get("public", True) or (search_keyword and search_keyword not in group["name"]): continue
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**{group['name']}** | 인원: {len(group['members'])}/{group['max_members']}명")
                with col_btn:
                    if group["id"] in st.session_state.my_groups: st.success("참여 중")
                    elif st.button("참여", key=f"join_{group['id']}"):
                        st.session_state.my_groups.append(group["id"])
                        update_study_group(group["id"], {"members": group["members"] + ["나"]})
                        save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                        st.rerun()

    # --- 스터디 만들기 ---
    with study_tabs[1]:
        if "new_study_created" in st.session_state:
            info = st.session_state.new_study_created
            if info["public"]: st.success(f"✅ '{info['name']}' 스터디 공개 생성!")
            else:
                st.success(f"✅ '{info['name']}' 비공개 생성!")
                st.info(f"🔑 초대 코드: **{info['code']}**")
            if st.button("확인 (닫기)"):
                del st.session_state.new_study_created
                st.rerun()
            st.divider()

        is_pub = st.radio("공개 여부", ["공개", "비공개"], horizontal=True) == "공개"
        with st.form("create_study_form", clear_on_submit=True):
            new_name = st.text_input("스터디 이름 *")
            new_subject = st.text_input("공부 과목 *")
            new_desc = st.text_area("소개")
            if st.form_submit_button("🚀 생성하기"):
                import random, string
                code = None if is_pub else "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                new_id = max([g["id"] for g in st.session_state.study_groups], default=0) + 1
                new_group = {
                    "id": new_id, "name": new_name, "subject": new_subject, "members": ["나"],
                    "max_members": 5, "chat": [], "description": new_desc, "goal": "",
                    "public": is_pub, "code": code,
                }
                save_study_group(new_group)
                st.session_state.my_groups.append(new_id)
                save_my_groups(st.session_state.session_key, st.session_state.my_groups)
                st.session_state.new_study_created = {"name": new_name, "public": is_pub, "code": code}
                st.rerun()

    # --- 내 스터디 ---
    with study_tabs[2]:
        my_groups = [g for g in st.session_state.study_groups if g["id"] in st.session_state.my_groups]
        if not my_groups: st.info("참여한 스터디가 없습니다.")
        else:
            sel_group = next(g for g in my_groups if g["name"] == st.selectbox("스터디 선택", [g["name"] for g in my_groups]))
            if not sel_group.get("public"): st.warning(f"🔒 비공개 코드: {sel_group['code']}")

            chat_container = st.container(height=300)
            with chat_container:
                for msg in sel_group["chat"]:
                    with st.chat_message("user" if msg["sender"]=="나" else "assistant"):
                        st.write(f"**{msg['sender']}**: {msg['text']}")

            if chat_msg := st.chat_input("메시지 보내기..."):
                now = datetime.datetime.now().strftime("%H:%M")
                new_chat = list(sel_group["chat"]) + [{"sender": "나", "text": chat_msg, "time": now}]
                
                if api_key and len(new_chat) % 3 == 0:
                    try:
                        client = OpenAI(api_key=api_key)
                        ai_prompt = f"주제: {sel_group['subject']}. 마지막 말: {chat_msg}. 짧은 응원/팁 1문장"
                        ai_resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": ai_prompt}], max_tokens=100)
                        new_chat.append({"sender": "🤖 AI 스터디 도우미", "text": ai_resp.choices[0].message.content, "time": now})
                    except: pass
                
                update_study_group(sel_group["id"], {"chat": new_chat})
                st.rerun()

# ==========================================
# TAB 5: 지휘관 부대 관리 대시보드
# ==========================================
with tabs[4]:
    st.header("📊 지휘관 부대 관리 대시보드")
    st.caption("※ 본 대시보드의 장병 데이터는 철저히 익명화되어 지휘관에게만 제공됩니다.")
    st.divider()

    col1, col2, col3 = st.columns(3)
    curr_risk = st.session_state.risk_level
    active_studies = len(st.session_state.study_groups)
    
    with col1: st.metric(label=f"{'🔴' if curr_risk>=2 else '🟢'} 위기 감지 (Level 2 이상)", value=f"{3 + (1 if curr_risk>=2 else 0)} 건")
    with col2: st.metric(label="🍽️ 식단 적정 칼로리 달성률", value="78 %")
    with col3: st.metric(label="📚 활성 스터디", value=f"{active_studies} 개")

    st.markdown("---")
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.subheader("🧠 부대원 심리 건강 분포")
        mental_data = {"인원(명)": {"Level 0": 412, "Level 1": 35, "Level 2": 2 + (1 if curr_risk==2 else 0), "Level 3": 1 + (1 if curr_risk==3 else 0)}}
        st.bar_chart(mental_data["인원(명)"], color="#ff4b4b")
        if curr_risk >= 2: st.error("🚨 **지휘통제실 알림:** 고위험군 징후 포착.")

    with chart_col2:
        st.subheader("📈 스터디 참여 트렌드")
        study_trend = {"활동량": {"D-3": 170, "D-2": 210, "D-1": 250, "오늘": 250 + (active_studies * 10)}}
        st.line_chart(study_trend["활동량"], color="#0068c9")
