import json
import os
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 🔑 [API 키 입력 설정]
DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_sync_text_save.json"

st.set_page_config(
    page_title="에델가르드 패권전 - 동기화 텍스트 RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ 에델가르드: 상태 텍스트 실시간 동기화 RPG")
st.markdown(
    "AI가 매 턴마다 갱신하는 캐릭터 상태 정보 블록을 좌측 슬라이드바에 그대로 반영하는 판타지 RPG입니다."
)

# 🎨 [스크롤 위치 복원 JS]
st.markdown(
    """
    <script>
        (function() {
            const pWin = window.parent || window;
            const pDoc = pWin.document;
            const SCROLL_KEY = 'rpg_sync_text_scroll';
            function getScrollContainer() {
                return pDoc.querySelector('[data-testid="stAppViewContainer"]') || pDoc.querySelector('.main') || pWin;
            }
            const container = getScrollContainer();
            const savePos = function() {
                const pos = (container !== pWin) ? container.scrollTop : (pWin.pageYOffset || pDoc.documentElement.scrollTop);
                pWin.sessionStorage.setItem(SCROLL_KEY, pos);
            };
            if (container !== pWin) { container.addEventListener('scroll', savePos, { passive: true }); }
            else { pWin.addEventListener('scroll', savePos, { passive: true }); }
            function restoreScroll() {
                const saved = pWin.sessionStorage.getItem(SCROLL_KEY);
                if (saved !== null) {
                    const targetPos = parseInt(saved, 10);
                    const cont = getScrollContainer();
                    if (cont !== pWin) { cont.scrollTop = targetPos; } else { pWin.scrollTo(0, targetPos); }
                }
            }
            setTimeout(restoreScroll, 50);
            setTimeout(restoreScroll, 200);
        })();
    </script>
    """,
    unsafe_allow_html=True,
)


# 📋 [AI 응답 스키마: 서사와 상태 동기화 텍스트를 함께 반환]
class SyncTextRPGResponse(BaseModel):
    narrative: str = Field(
        description="플레이어의 행동에 따른 상세하고 몰입감 있는 스토리 서사 묘사."
    )
    status_sync_text: str = Field(
        description=(
            "현재 캐릭터의 상태를 보여주는 텍스트 블록. 예시 형식:\n"
            "종족: 엘프\n"
            "직업: 마법사\n"
            "레벨: 1 (경험치: 0/100)\n"
            "체력(HP): 60/60\n"
            "마나(MP): 30/30\n"
            "골드: 20G\n"
            "장착 장비: {\"무기\": \"초보자의 무기\", \"갑옷\": \"여행자 가죽옷\"}\n"
            "인벤토리: [\"체력 포션 (소)\", \"마력 회복의 반지\"]\n"
            "변동 사항이 생길 때마다 수치, 골드, 인벤토리를 정확하게 갱신하여 작성하세요."
        )
    )
    choices: list[str] = Field(
        description="플레이어가 다음에 선택할 수 있는 행동지침 3~4가지"
    )


# 💾 [세이브 및 로드 관리]
def save_game():
    data = {
        "status_sync_text": st.session_state.get(
            "status_sync_text",
            "종족: 미정\n직업: 미정\n레벨: 1 (경험치: 0/100)\n체력(HP):"
            " 60/60\n마나(MP): 30/30\n골드: 50G\n장착 장비: {\"무기\": \"초보자의"
            ' 무기", "갑옷": "여행자 가죽옷"}\n인벤토리: ["체력 포션 (소)", "체력 포션'
            ' (소)"]',
        ),
        "history": st.session_state.get("history", []),
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# 📊 [세션 초기화]
saved_data = None
if os.path.exists(SAVE_FILE):
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
    except Exception:
        pass

default_sync_text = (
    "종족: 미정\n"
    "직업: 미정\n"
    "레벨: 1 (경험치: 0/100)\n"
    "체력(HP): 60/60\n"
    "마나(MP): 30/30\n"
    "골드: 50G\n"
    '장착 장비: {"무기": "초보자의 무기", "갑옷": "여행자 가죽옷"}\n'
    '인벤토리: ["체력 포션 (소)", "체력 포션 (소)"]'
)

if "status_sync_text" not in st.session_state:
    st.session_state.status_sync_text = (
        saved_data.get("status_sync_text", default_sync_text)
        if saved_data
        else default_sync_text
    )

if "history" not in st.session_state:
    st.session_state.history = (
        saved_data.get("history", []) if saved_data else []
    )


# ⚙️ [사이드바 UI: AI가 전달한 동기화 텍스트를 그대로 출력]
st.sidebar.header("⚙️ 게임 설정 및 상태창")
api_key_input = st.sidebar.text_input(
    "Google Gemini API 키 입력", value=DEFAULT_API_KEY, type="password"
)
font_size = st.sidebar.slider("🔤 글자 크기", 12, 26, 16, 1)

st.markdown(
    f"""
    <style>
        .stChatMessage p, .stChatMessage div {{ font-size: {font_size}px !important; line-height: 1.6 !important; }}
    </style>
    """,
    unsafe_allow_html=True,
)

selected_model = st.sidebar.selectbox(
    "Gemini 모델 선택",
    options=[
        "gemini-3.1-flash-lite",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 현재 캐릭터 상태 동기화 정보")

# 사용자가 요청한 대로 AI가 제공한 동기화 내용을 코드 가공 없이 그대로 표시
st.sidebar.text(st.session_state.status_sync_text)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 전체 초기화 및 새 게임"):
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# 🤖 [AI 호출 함수]
def call_gemini_sync_text(user_action):
    client = genai.Client(api_key=api_key_input)

    system_instruction = (
        "당신은 에델가르드 판타지 RPG의 게임 마스터(GM)입니다.\n"
        "플레이어의 행동에 따라 서사를 진행하고, 하단의 형식에 맞춰 캐릭터의 상태 동기화 텍스트(status_sync_text)를 반드시 최신 상태로 갱신하여 제공하세요.\n\n"
        "status_sync_text 형식 예시:\n"
        "종족: 엘프\n"
        "직업: 마법사\n"
        "레벨: 1 (경험치: 0/100)\n"
        "체력(HP): 60/60\n"
        "마나(MP): 30/30\n"
        "골드: 20G\n"
        "장착 장비: {\"무기\": \"초보자의 무기\", \"갑옷\": \"여행자 가죽옷\"}\n"
        "인벤토리: [\"체력 포션 (소)\", \"마력 회복의 반지\"]\n\n"
        "아이템 구매, 골드 변동, 체력/마나 소모, 아이템 획득 등이 발생할 때마다 status_sync_text 내부의 수치와 리스트를 정확하게 반영해 주세요."
    )

    prompt = (
        f"[현재 캐릭터 상태 동기화 정보]\n{st.session_state.status_sync_text}\n\n"
        f"최근 대화 기록:\n"
        + json.dumps(st.session_state.history[-6:], ensure_ascii=False)
        + f"\n\n플레이어의 행동 또는 선택: {user_action}"
    )

    try:
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=SyncTextRPGResponse,
                temperature=0.7,
            ),
        )
        return SyncTextRPGResponse.model_validate_json(response.text)
    except Exception as e:
        st.error(f"Gemini API 호출 오류: {e}")
        return None


# 🎮 [메인 화면 로직]
if not api_key_input:
    st.warning("⚠️ 좌측 사이드바에 Google Gemini API 키를 입력해 주세요.")
else:
    # 아직 기록이 없으면 오프닝 생성 트리거
    if not st.session_state.history:
        with st.spinner("에델가르드 대륙의 세계를 여는 중..."):
            res = call_gemini_sync_text(
                "엘프 종족 마법사 직업으로 크로스로드 도시 여관에서 모험을 시작하려고 한다. 첫 오프닝을 열어줘."
            )
            if res:
                st.session_state.status_sync_text = res.status_sync_text
                st.session_state.history.append({
                    "role": "assistant",
                    "narrative": res.narrative,
                    "choices": res.choices,
                })
                save_game()
                st.rerun()

    else:
        # 대화 기록 출력
        for h in st.session_state.history:
            with st.chat_message(h["role"]):
                st.markdown(h.get("narrative", ""))

        # 선택지 버튼 제공
        current_choices = []
        if st.session_state.history:
            last_h = st.session_state.history[-1]
            current_choices = last_h.get("choices", [])

        user_action = None
        if current_choices:
            st.markdown("##### 🎯 행동 선택")
            for idx, ch in enumerate(current_choices):
                if st.button(
                    f"👉 {ch}",
                    key=f"ch_{len(st.session_state.history)}_{idx}",
                    use_container_width=True,
                ):
                    user_action = ch

        chat_input = st.chat_input("원하는 행동을 자유롭게 입력하세요...")
        final_input = user_action or chat_input

        if final_input:
            st.session_state.history.append(
                {"role": "user", "narrative": final_input}
            )
            with st.chat_message("user"):
                st.markdown(final_input)

            with st.spinner("게임 마스터가 처리 중..."):
                res = call_gemini_sync_text(final_input)

                if res:
                    # AI가 생성한 동기화 텍스트 블록을 그대로 세션에 반영
                    st.session_state.status_sync_text = res.status_sync_text

                    # 스토리 기록 추가
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": res.narrative,
                        "choices": res.choices,
                    })

                    # 최근 6개 기록만 유지
                    if len(st.session_state.history) > 6:
                        st.session_state.history = st.session_state.history[
                            -6:
                        ]

                    save_game()
                    st.rerun()
