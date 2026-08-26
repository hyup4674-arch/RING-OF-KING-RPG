import json
import os
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 🔑 [API 키 입력 설정]
DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_freeform_save.json"

st.set_page_config(
    page_title="에델가르드 패권전 - 자유형 AI RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ 에델가르드: 자유형 AI 판타지 RPG")
st.markdown(
    "고정된 스탯과 형식 없이, AI가 모든 상태와 스킬을 자유롭게 빚어내는 온전한 서사 중심 RPG입니다."
)

# 🎨 [스크롤 위치 복원 JS]
st.markdown(
    """
    <script>
        (function() {
            const pWin = window.parent || window;
            const pDoc = pWin.document;
            const SCROLL_KEY = 'rpg_scroll_freeform';
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


# 📋 [AI가 자유롭게 상태와 스킬을 정의할 수 있는 Pydantic 스키마]
class FreeformRPGResponse(BaseModel):
    narrative: str = Field(
        description="플레이어의 행동에 따른 상세하고 흥미진진한 스토리 서사 묘사."
    )
    sidebar_status_text: str = Field(
        description=(
            "사이드바에 그대로 표시될 캐릭터의 현재 상태 요약 (예: 체력 상태,"
            " 입은 옷, 현재 기분, 소지품 등 AI가 자유롭게 서술)"
        )
    )
    current_skills: list[str] = Field(
        description=(
            "현재 캐릭터가 사용할 수 있거나 새롭게 깨달은 스킬, 특기, 마법의"
            " 목록 (AI가 자유롭게 추가/수정 가능)"
        )
    )
    choices: list[str] = Field(
        description="플레이어가 다음에 선택할 수 있는 행동 지침 3~4가지"
    )


# 💾 [세이브 및 로드 관리]
def save_game():
    data = {
        "sidebar_status": st.session_state.get(
            "sidebar_status", "모험을 준비 중입니다."
        ),
        "skills_list": st.session_state.get("skills_list", ["기본 주먹질"]),
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

if "sidebar_status" not in st.session_state:
    st.session_state.sidebar_status = (
        saved_data.get("sidebar_status", "아직 여정을 시작하지 않았습니다.")
        if saved_data
        else "아직 여정을 시작하지 않았습니다."
    )

if "skills_list" not in st.session_state:
    st.session_state.skills_list = (
        saved_data.get("skills_list", ["기본 주먹질"])
        if saved_data
        else ["기본 주먹질"]
    )

if "history" not in st.session_state:
    st.session_state.history = (
        saved_data.get("history", []) if saved_data else []
    )


# ⚙️ [사이드바 상태창 UI (고정 형식 제거, AI 출력 내용 반영)]
st.sidebar.header("⚙️ 게임 설정 및 AI 상태창")
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
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.5-pro",
    ],
    index=0,
)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ AI가 기록하는 캐릭터 상태")
st.sidebar.info(st.session_state.sidebar_status)

st.sidebar.markdown("---")
st.sidebar.subheader("✨ 현재 보유 스킬 및 특기")
for sk in st.session_state.skills_list:
    st.sidebar.markdown(f"- 🗡️ {sk}")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 전체 초기화 및 새 게임"):
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# 🤖 [AI 호출 함수]
def call_gemini_freeform(user_action):
    client = genai.Client(api_key=api_key_input)

    system_instruction = (
        "당신은 에델가르드 판타지 RPG의 창의적인 게임 마스터(GM)입니다.\n"
        "고정된 수치나 스탯 규칙에 얽매이지 말고, 플레이어의 행동에 따라 서사를 풍부하게 전개하세요.\n"
        "현재 캐릭터 상태(sidebar_status_text)와 보유 스킬(current_skills)을 상황에 맞게 자유롭게 갱신하고 수정해주세요."
    )

    prompt = (
        f"[현재 사이드바에 표시 중인 상태]\n{st.session_state.sidebar_status}\n\n"
        f"[현재 보유 중인 스킬 목록]\n{st.session_state.skills_list}\n\n"
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
                response_schema=FreeformRPGResponse,
                temperature=0.8,
            ),
        )
        return FreeformRPGResponse.model_validate_json(response.text)
    except Exception as e:
        st.error(f"Gemini API 호출 오류: {e}")
        return None


# 🎮 [메인 화면 로직]
if not api_key_input:
    st.warning("⚠️ 좌측 사이드바에 Google Gemini API 키를 입력해 주세요.")
else:
    # 아직 시작 대화가 없다면 오프닝 생성 트리거
    if not st.session_state.history:
        with st.spinner("에델가르드 대륙의 세계를 여는 중..."):
            res = call_gemini_freeform(
                "에델가르드 대륙의 크로스로드 도시 여관에서 모험을 시작하려고 한다. 캐릭터의 첫 설정과 오프닝을 자유롭게 열어줘."
            )
            if res:
                st.session_state.sidebar_status = res.sidebar_status_text
                st.session_state.skills_list = res.current_skills
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

        # 마지막 응답의 선택지 버튼 제공
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

            with st.spinner("게임 마스터가 서사를 구상하는 중..."):
                res = call_gemini_freeform(final_input)

                if res:
                    # AI가 입력해준 상태와 스킬을 그대로 사이드바에 반영
                    st.session_state.sidebar_status = res.sidebar_status_text
                    st.session_state.skills_list = res.current_skills

                    # 스토리 기록 추가
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": res.narrative,
                        "choices": res.choices,
                    })

                    # 최근 기록 유지
                    if len(st.session_state.history) > 6:
                        st.session_state.history = st.session_state.history[
                            -6:
                        ]

                    save_game()
                    st.rerun()
