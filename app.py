import json
import os
import random
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# 🔑 [API 키 입력 설정]
DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_save_v2.json"

st.set_page_config(
    page_title="에델가르드 패권전 - 완벽 동기화 RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ 에델가르드: 완벽 동기화 판타지 RPG")
st.markdown(
    "Pydantic 구조화 출력 엔진을 탑재하여 상태창과 서사가 100% 일치하는 차세대 AI RPG입니다."
)

# 🎨 [스크롤 위치 복원 JS]
st.markdown(
    """
    <script>
        (function() {
            const pWin = window.parent || window;
            const pDoc = pWin.document;
            const SCROLL_KEY = 'rpg_scroll_pos_lock_v2';
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


# 📋 [Pydantic 기반 강제 구조화 스키마 설정]
class GameResponse(BaseModel):
    narrative: str = Field(
        description="플레이어의 행동에 따른 상세하고 흥미진진한 스토리 서사 묘사."
    )
    hp_change: int = Field(
        default=0,
        description="체력(HP) 변동치 (함정, 피격, 휴식 등으로 깎인 체력은 음수, 회복은 양수)",
    )
    mp_change: int = Field(
        default=0, description="마나(MP) 변동치 (스킬 사용 또는 회복)"
    )
    gold_change: int = Field(
        default=0,
        description="골드 변동치 (보상 획득은 양수, 상점 구매는 음수)",
    )
    exp_change: int = Field(
        default=0, description="획득한 경험치(EXP) 양 (기본 10~30)"
    )
    item_gained: str = Field(
        default="", description="새로 획득한 아이템 이름 (없으면 빈 문자열)"
    )
    start_combat: bool = Field(
        default=False, description="적과의 전투가 시작되면 True"
    )
    enemy_name: str = Field(
        default="", description="전투 시작 시 적의 이름"
    )
    enemy_hp: int = Field(default=0, description="전투 시작 시 적의 체력")
    enemy_atk: int = Field(default=0, description="전투 시작 시 적의 공격력")
    choices: list[str] = Field(
        description=(
            "플레이어가 다음에 선택할 수 있는 행동지침 3~4가지 (예: ['앞으로"
            " 전진한다', '주변을 수색한다'])"
        )
    )


# 💾 [세이브 및 로드 관리]
def save_game():
    data = {
        "stats": st.session_state.get("stats", {}),
        "history": st.session_state.get("history", []),
        "game_mode": st.session_state.get("game_mode", "EXPLORATION"),
        "current_enemy": st.session_state.get("current_enemy", None),
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# 📊 [상태 초기화]
saved_data = None
if os.path.exists(SAVE_FILE):
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            saved_data = json.load(f)
    except Exception:
        pass

if "stats" not in st.session_state:
    st.session_state.stats = saved_data.get("stats", {
        "race": "미정",
        "class_name": "미정",
        "hp": 60,
        "max_hp": 60,
        "mp": 30,
        "max_mp": 30,
        "gold": 50,
        "level": 1,
        "exp": 0,
        "max_exp": 100,
        "str": 10,
        "int": 10,
        "con": 10,
        "agi": 10,
        "stat_points": 0,
        "equipment": {"무기": "초보자의 무기", "갑옷": "여행자 가죽옷"},
        "inventory": ["체력 포션 (소)", "체력 포션 (소)"],
        "skills": [],
    })

if "history" not in st.session_state:
    st.session_state.history = saved_data.get("history", [])

if "game_mode" not in st.session_state:
    st.session_state.game_mode = saved_data.get("game_mode", "EXPLORATION")

if "current_enemy" not in st.session_state:
    st.session_state.current_enemy = saved_data.get("current_enemy", None)


# 📈 [경험치 및 레벨업 처리]
def add_exp(amount):
    player = st.session_state.stats
    player["exp"] += amount
    leveled_up = False
    while player["exp"] >= player["max_exp"]:
        player["exp"] -= player["max_exp"]
        player["level"] += 1
        player["max_exp"] = int(player["max_exp"] * 1.5)
        player["stat_points"] += 5
        player["max_hp"] += 10
        player["hp"] = player["max_hp"]
        player["max_mp"] += 10
        player["mp"] = player["max_mp"]
        leveled_up = True
    return leveled_up


# ⚙️ [사이드바 상태창 UI]
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
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.5-pro",
    ],
    index=0,
)

st.sidebar.markdown("---")
stats = st.session_state.stats
st.sidebar.subheader("🛡️ 캐릭터 상태")
st.sidebar.markdown(
    f"👤 **종족**: `{stats['race']}` | **직업**: `{stats['class_name']}`"
)
st.sidebar.metric(label="⭐ 레벨", value=f"Lv. {stats['level']}")
st.sidebar.metric(
    label="✨ 경험치", value=f"{stats['exp']} / {stats['max_exp']}"
)
st.sidebar.metric(label="❤️ 체력", value=f"{stats['hp']} / {stats['max_hp']}")
st.sidebar.metric(label="💙 마나", value=f"{stats['mp']} / {stats['max_mp']}")
st.sidebar.metric(label="💰 골드", value=f"{stats['gold']} G")

st.sidebar.markdown("##### 📊 능력치")
st.sidebar.write(
    f"- 💪 힘: {stats['str']} | 🧠 지능: {stats['int']} | ❤️ 체력: {stats['con']}"
    f" | ⚡ 민첩: {stats['agi']}"
)

if stats.get("stat_points", 0) > 0:
    st.sidebar.success(f"🎉 스탯 포인트: {stats['stat_points']} P")
    c1, c2 = st.sidebar.columns(2)
    if c1.button("💪 힘+5"):
        stats["str"] += 5
        stats["stat_points"] -= 5
        save_game()
        st.rerun()
    if c2.button("❤️ 체력+5"):
        stats["con"] += 5
        stats["max_hp"] += 10
        stats["hp"] = stats["max_hp"]
        stats["stat_points"] -= 5
        save_game()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🎒 장비 및 인벤토리")
st.sidebar.write(
    f"- **무기**: {stats['equipment'].get('무기', '초보자의 무기')}"
)
st.sidebar.write(
    f"- **갑옷**: {stats['equipment'].get('갑옷', '여행자 가죽옷')}"
)
for item in stats.get("inventory", []):
    st.sidebar.write(f"- 📦 {item}")

if st.sidebar.button("🔄 새 게임 시작 (초기화)"):
    if os.path.exists(SAVE_FILE):
        os.remove(SAVE_FILE)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# 🤖 [AI 호출 핵심 함수 (Structured Output 적용)]
def call_gemini_turn(user_action):
    client = genai.Client(api_key=api_key_input)

    # 누적 대화 기록 및 현재 스탯 주입
    system_instruction = (
        "당신은 에델가르드 판타지 RPG의 게임 마스터(GM)입니다.\n"
        "플레이어의 행동에 따라 서사를 진행하고, 체력/마나/골드/경험치 변동 사항을 정확한 숫자로 함께 산출하세요.\n"
        "적과의 조우가 필요하면 start_combat을 True로 설정하고 적 정보를 입력하세요."
    )

    prompt = (
        f"[현재 플레이어 상태]\n"
        f"- 종족/직업: {stats['race']} {stats['class_name']} (Lv.{stats['level']})\n"
        f"- HP: {stats['hp']}/{stats['max_hp']} | MP: {stats['mp']}/{stats['max_mp']}\n"
        f"- 골드: {stats['gold']}G | 인벤토리: {stats['inventory']}\n\n"
        f"대화 기록:\n"
        + json.dumps(st.session_state.history[-6:], ensure_ascii=False)
        + f"\n\n플레이어의 다음 행동: {user_action}"
    )

    try:
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=GameResponse,
                temperature=0.7,
            ),
        )
        # Pydantic 모델로 파싱된 결과 반환
        return GameResponse.model_validate_json(response.text)
    except Exception as e:
        st.error(f"Gemini API 호출 오류: {e}")
        return None


# 🎮 [메인 화면 분기 처리]
if not api_key_input:
    st.warning("⚠️ 좌측 사이드바에 Google Gemini API 키를 입력해 주세요.")
else:
    # 1단계: 종족 선택
    if stats["race"] == "미정":
        st.info("🌍 **[캐릭터 생성 - 1단계] 종족을 선택하세요.**")
        c1, c2 = st.columns(2)
        if c1.button("👑 인간", use_container_width=True):
            stats["race"] = "인간"
            save_game()
            st.rerun()
        if c1.button("🌿 엘프", use_container_width=True):
            stats["race"] = "엘프"
            save_game()
            st.rerun()
        if c2.button("⚒️ 드워프", use_container_width=True):
            stats["race"] = "드워프"
            save_game()
            st.rerun()
        if c2.button("🪓 오크", use_container_width=True):
            stats["race"] = "오크"
            save_game()
            st.rerun()

    # 2단계: 직업 선택
    elif stats["class_name"] == "미정":
        st.info(f"✨ **[캐릭터 생성 - 2단계] 종족: {stats['race']} | 직업 선택**")
        c1, c2, c3, c4 = st.columns(4)
        chosen = None
        if c1.button("전사"):
            chosen = "전사"
        if c2.button("마법사"):
            chosen = "마법사"
        if c3.button("궁수"):
            chosen = "궁수"
        if c4.button("도적"):
            chosen = "도적"

        if chosen:
            stats["class_name"] = chosen
            stats["skills"] = [{"name": "기본 공격", "power": 15, "mp_cost": 0}]
            # 첫 시작 스토리 트리거
            with st.spinner("모험의 세계를 생성하는 중..."):
                res = call_gemini_turn(
                    f"나는 {stats['race']} 종족 {stats['class_name']}"
                    " 직업으로 여관에서 모험을 시작한다. 오프닝을 열어줘."
                )
                if res:
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": res.narrative,
                        "choices": res.choices,
                    })
                    save_game()
            st.rerun()

    else:
        # 전투 모드
        if st.session_state.game_mode == "COMBAT":
            enemy = st.session_state.current_enemy
            st.error(f"🚨 **[긴급 전투] {enemy['name']}과(와) 교전 중!**")
            c_hp1, c_hp2 = st.columns(2)
            c_hp1.metric("내 HP", f"{stats['hp']} / {stats['max_hp']}")
            c_hp2.metric(
                f"적 HP ({enemy['name']})", f"{enemy['hp']} / {enemy['max_hp']}"
            )

            c_b1, c_b2, c_b3 = st.columns(3)
            if c_b1.button("🗡️ 공격하기", use_container_width=True):
                dmg = random.randint(10, 20) + stats["str"]
                enemy["hp"] -= dmg
                edmg = random.randint(5, 12)
                stats["hp"] = max(0, stats["hp"] - edmg)

                if enemy["hp"] <= 0:
                    gold_rew = random.randint(20, 40)
                    exp_rew = 50
                    stats["gold"] += gold_rew
                    leveled = add_exp(exp_rew)
                    st.session_state.game_mode = "EXPLORATION"
                    st.session_state.current_enemy = None
                    msg = (
                        f"🎉 적을 처치했습니다! (보상: {gold_rew}G, {exp_rew}"
                        f" EXP){' [레벨 업!]' if leveled else ''}"
                    )
                    st.session_state.history.append(
                        {"role": "assistant", "narrative": msg, "choices": ["마을로 돌아간다", "계속 탐험한다"]}
                    )
                elif stats["hp"] <= 0:
                    stats["hp"] = 10
                    st.session_state.game_mode = "EXPLORATION"
                    st.session_state.current_enemy = None
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": "💀 전투에서 패배하여 쓰러졌으나, 의식을 차려 간신히 살아났다.",
                        "choices": ["여관으로 간다"],
                    })
                save_game()
                st.rerun()

        # 탐험 모드
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

            chat_input = st.chat_input("원하는 행동을 직접 입력하세요...")
            final_input = user_action or chat_input

            if final_input:
                st.session_state.history.append(
                    {"role": "user", "narrative": final_input}
                )
                with st.chat_message("user"):
                    st.markdown(final_input)

                with st.spinner("게임 마스터가 판정 중..."):
                    res = call_gemini_turn(final_input)

                    if res:
                        # 🔒 [핵심 동기화] AI가 계산한 수치를 파이썬 변수에 100% 안전하게 즉시 반영
                        stats["hp"] = max(
                            0,
                            min(
                                stats["max_hp"],
                                stats["hp"] + res.hp_change,
                            ),
                        )
                        stats["mp"] = max(
                            0,
                            min(
                                stats["max_mp"],
                                stats["mp"] + res.mp_change,
                            ),
                        )
                        stats["gold"] = max(
                            0, stats["gold"] + res.gold_change
                        )

                        if res.exp_change > 0:
                            add_exp(res.exp_change)

                        if res.item_gained:
                            stats["inventory"].append(res.item_gained)

                        # 전투 시작 여부 판단
                        if res.start_combat:
                            st.session_state.game_mode = "COMBAT"
                            st.session_state.current_enemy = {
                                "name": res.enemy_name or "괴물",
                                "hp": res.enemy_hp if res.enemy_hp > 0 else 40,
                                "max_hp": (
                                    res.enemy_hp if res.enemy_hp > 0 else 40
                                ),
                                "atk": (
                                    res.enemy_atk if res.enemy_atk > 0 else 10
                                ),
                            }

                        # 스토리 기록 추가
                        st.session_state.history.append({
                            "role": "assistant",
                            "narrative": res.narrative,
                            "choices": res.choices,
                        })

                        # 최근 6개 기록만 유지
                        if len(st.session_state.history) > 6:
                            st.session_state.history = (
                                st.session_state.history[-6:]
                            )

                        save_game()
                        st.rerun()
