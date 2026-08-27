import json
import os
import random
import time
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_save_v5.json"

st.set_page_config(
    page_title="AI 연동 동기화 파이썬 엔진 RPG", page_icon="⚔️", layout="wide"
)
st.title(
    "⚔️ AI 서사 + 파이썬 철저 밸런스 엔진 RPG (중복 방지 & 초고속 간결화 버전)"
)


# 📋 [Pydantic 스키마]
class GeneratedItem(BaseModel):
    item_type: str = Field(
        default="",
        description="아이템 종류: 'weapon', 'armor', 'magic', 'skill' 중 하나",
    )
    name: str = Field(
        default="", description="기존에 없는 완전히 새로운 유니크한 이름"
    )
    required_stat: int = Field(default=10, description="필요 능력치 또는 소모MP")


class GameResponse(BaseModel):
    narrative: str = Field(description="1~2문장으로 매우 간결하게 요약된 스토리 서사 묘사.")
    choices: list[str] = Field(
        default=["주변을 탐색한다", "안전한 곳으로 이동한다"],
        description="플레이어가 선택할 수 있는 정확히 2개의 선택지 리스트",
    )
    start_combat: bool = Field(default=False, description="전투 조우 여부")
    enemy_name: str = Field(default="", description="조우한 적의 이름")
    enemy_archetype: str = Field(
        default="beast", description="적의 유형 (beast, bandit, undead, mage)"
    )
    new_item: GeneratedItem = Field(
        default=None, description="새로운 아이템/마법/스킬 제안"
    )


# 🗑️ [AI 메시지 최근 2개 유지 및 히스토리 정리 함수]
def trim_ai_history():
    assistant_indices = [
        i
        for i, h in enumerate(st.session_state.history)
        if h.get("role") == "assistant"
    ]
    if len(assistant_indices) > 2:
        target_idx = assistant_indices[-2]
        if (
            target_idx > 0
            and st.session_state.history[target_idx - 1].get("role") == "user"
        ):
            st.session_state.history = st.session_state.history[
                target_idx - 1 :
            ]
        else:
            st.session_state.history = st.session_state.history[target_idx:]


# 💾 [세이브 및 로드 관리]
def save_game():
    trim_ai_history()
    data = {
        "stats": st.session_state.get("stats", {}),
        "history": st.session_state.get("history", []),
        "game_mode": st.session_state.get("game_mode", "EXPLORATION"),
        "current_enemy": st.session_state.get("current_enemy", None),
        "weapon_shop": st.session_state.get("weapon_shop", []),
        "armor_shop": st.session_state.get("armor_shop", []),
        "magic_guild": st.session_state.get("magic_guild", []),
        "combat_dojo": st.session_state.get("combat_dojo", []),
        "quest_board": st.session_state.get("quest_board", []),
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# 📊 [상태 초기화 및 JSON 키 복구]
saved_data = {}
if os.path.exists(SAVE_FILE):
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            content = json.load(f)
            if isinstance(content, dict):
                saved_data = content
                if "stats" in saved_data:
                    for p_key in ["hp_potions", "mp_potions"]:
                        if p_key in saved_data["stats"]:
                            saved_data["stats"][p_key] = {
                                int(k): v
                                for k, v in saved_data["stats"][p_key].items()
                            }
    except Exception:
        pass

if "weapon_shop" not in st.session_state:
    st.session_state.weapon_shop = saved_data.get(
        "weapon_shop",
        [
            {
                "name": "초보자의 단검",
                "damage": 13,
                "required_str": 10,
                "price": 50,
            },
            {"name": "철제 검", "damage": 26, "required_str": 20, "price": 120},
        ],
    )

if "armor_shop" not in st.session_state:
    st.session_state.armor_shop = saved_data.get(
        "armor_shop",
        [
            {
                "name": "여행자 가죽옷",
                "defense": 13,
                "required_con": 10,
                "price": 50,
            },
            {
                "name": "경비병 철갑옷",
                "defense": 26,
                "required_con": 20,
                "price": 120,
            },
        ],
    )

if "magic_guild" not in st.session_state:
    st.session_state.magic_guild = saved_data.get(
        "magic_guild",
        [
            {"name": "매직 미사일", "damage": 20, "mp_cost": 10, "price": 80},
            {"name": "파이어볼", "damage": 40, "mp_cost": 20, "price": 180},
        ],
    )

if "combat_dojo" not in st.session_state:
    st.session_state.combat_dojo = saved_data.get(
        "combat_dojo",
        [
            {"name": "내려치기", "damage": 15, "mp_cost": 10, "price": 80},
            {"name": "연속 베기", "damage": 30, "mp_cost": 20, "price": 180},
        ],
    )

if "quest_board" not in st.session_state:
    st.session_state.quest_board = saved_data.get(
        "quest_board",
        [
            {
                "id": 1,
                "title": "마을 주변 슬라임 소탕",
                "target_enemy": "슬라임",
                "reward_gold": 100,
                "reward_exp": 80,
                "completed": False,
            },
            {
                "id": 2,
                "title": "숲속의 고블린 도적단 퇴치",
                "target_enemy": "고블린 도적",
                "reward_gold": 250,
                "reward_exp": 180,
                "completed": False,
            },
        ],
    )

if "stats" not in st.session_state:
    st.session_state.stats = saved_data.get(
        "stats",
        {
            "hp": 100,
            "max_hp": 100,
            "mp": 50,
            "max_mp": 50,
            "gold": 300,
            "level": 1,
            "exp": 0,
            "max_exp": 100,
            "str": 10,
            "agi": 10,
            "con": 10,
            "int": 10,
            "stat_points": 10,
            "skill_points": 0,
            "hp_potions": {100: 2},
            "mp_potions": {100: 1},
            "equipped_weapon": st.session_state.weapon_shop[0],
            "equipped_armor": st.session_state.armor_shop[0],
            "inventory_weapons": [st.session_state.weapon_shop[0]],
            "inventory_armors": [st.session_state.armor_shop[0]],
            "learned_magic": [],
            "learned_skills": [],
            "active_quest": None,
        },
    )

if "hp_potions" not in st.session_state.stats:
    st.session_state.stats["hp_potions"] = {100: 1}
if "mp_potions" not in st.session_state.stats:
    st.session_state.stats["mp_potions"] = {100: 1}
if "active_quest" not in st.session_state.stats:
    st.session_state.stats["active_quest"] = None

if "history" not in st.session_state:
    st.session_state.history = saved_data.get("history", [])
    if not st.session_state.history:
        st.session_state.history.append({
            "role": "assistant",
            "narrative": (
                "모험의 세상에 오신 것을 환영합니다! 평화로운 마을에서 첫걸음을"
                " 내딛습니다."
            ),
            "choices": ["주변 숲으로 모험을 떠난다", "마을 상점과 시설을 둘러본다"],
        })

if "game_mode" not in st.session_state:
    st.session_state.game_mode = saved_data.get("game_mode", "EXPLORATION")

if "current_enemy" not in st.session_state:
    st.session_state.current_enemy = saved_data.get("current_enemy", None)

if "combat_sub_menu" not in st.session_state:
    st.session_state.combat_sub_menu = None


# 📈 [경험치 및 레벨업 처리]
def add_exp(amount):
    player = st.session_state.stats
    player["exp"] += amount
    leveled_up = False
    while player["exp"] >= player["max_exp"]:
        player["exp"] -= player["max_exp"]
        player["level"] += 1
        player["max_exp"] = int(player["max_exp"] * 1.4)
        player["stat_points"] += 10
        player["skill_points"] += 1
        player["max_hp"] += 20
        player["hp"] = player["max_hp"]
        player["max_mp"] += 15
        player["mp"] = player["max_mp"]
        leveled_up = True
    return leveled_up


# 🤖 [AI 마을 대사 생성 함수]
def append_ai_village_dialogue(facility_name, action_desc):
    api_key = api_key_input
    if not api_key:
        st.session_state.history.append({
            "role": "assistant",
            "narrative": f"[마을 시설: {facility_name}] {action_desc}",
            "choices": ["마을 광장으로 돌아간다", "다른 시설을 이용한다"],
        })
        trim_ai_history()
        return

    client = genai.Client(api_key=api_key)
    prompt = (
        f"판타지 RPG의 마을 시설인 '{facility_name}'에서 플레이어가 다음 행동을 수행했습니다: '{action_desc}'. "
        f"NPC의 개성 있는 대사와 현장감을 살린 서사를 **반드시 1~2문장 이내로 매우 간결하게** 묘사해주세요."
    )
    
    response_text = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=selected_model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.7),
            )
            response_text = response.text.strip() if response.text else None
            break
        except Exception:
            if attempt < 2:
                time.sleep(2)
            else:
                pass

    narrative = response_text if response_text else f"'{facility_name}'에서의 볼일을 마쳤습니다."
    st.session_state.history.append({
        "role": "assistant",
        "narrative": f"🏛️ **[{facility_name}]**\n{narrative}",
        "choices": ["모험을 계속한다", "마을에 머문다"],
    })
    trim_ai_history()


# ⚙️ [좌측 슬라이드 창 설정]
st.sidebar.header("⚙️ 게임 설정 및 메뉴")

api_key_input = DEFAULT_API_KEY
selected_model = "gemini-3.1-flash-lite"

with st.sidebar.expander("🔑 AI 모델 및 클라우드 세이브", expanded=True):
    api_key_input = st.text_input(
        "Google Gemini API 키", value=DEFAULT_API_KEY, type="password"
    )

    st.markdown("---")
    st.write(
        "클라우드 서버 초기화 방지를 위해 플레이 데이터를 파일로 백업하세요."
    )
    save_game()
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            save_data_str = f.read()
        st.download_button(
            label="📥 내 기기로 세이브 파일 백업",
            data=save_data_str,
            file_name="rpg_save_v5.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("---")
    uploaded_file = st.file_uploader(
        "📤 백업했던 세이브 파일 업로드", type=["json"]
    )
    if uploaded_file is not None:
        try:
            content = json.load(uploaded_file)
            if isinstance(content, dict):
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False)
                st.success(
                    "세이브 데이터가 성공적으로 복구되었습니다! 앱을 재시작합니다..."
                )
                st.rerun()
            else:
                st.error("올바르지 않은 세이브 파일 형식입니다.")
        except Exception as e:
            st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")

    st.markdown("---")
    flash_lite_models = [
        {
            "id": "gemini-3.1-flash-lite",
            "name": "Gemini 3.1 Flash-Lite (기본)",
            "desc": "고효율 멀티모달 저지연 모델",
        },
        {
            "id": "gemini-3.5-flash-lite",
            "name": "Gemini 3.5 Flash-Lite",
            "desc": "최신 상위 고성능 Flash-Lite 모델",
        },
        {
            "id": "gemini-2.5-flash-lite",
            "name": "Gemini 2.5 Flash-Lite",
            "desc": "안정적인 경제형 경량 모델",
        },
        {
            "id": "gemini-3.1-flash-lite-image",
            "name": "Gemini 3.1 Flash-Lite Image",
            "desc": "초저지연 이미지 생성 특화 모델",
        },
        {
            "id": "gemini-2.0-flash-lite",
            "name": "Gemini 2.0 Flash-Lite",
            "desc": "초고속 레거시 경량 모델",
        },
    ]
    st.subheader("🔍 Flash-Lite 모델 라인업 (5선)")
    for m in flash_lite_models:
        st.markdown(f"- **{m['name']}**\n  * `{m['id']}` : {m['desc']}")

    model_options = [m["id"] for m in flash_lite_models]
    selected_model = st.selectbox(
        "사용할 Gemini 모델 선택", options=model_options, index=0
    )

stats = st.session_state.stats

with st.sidebar.expander("⚔️ 전투력 및 장비 현황", expanded=True):
    current_atk = int(
        (stats["str"] * 0.8) + stats["equipped_weapon"].get("damage", 0)
    )
    current_def = int(
        stats["equipped_armor"].get("defense", 0) + (stats["con"] * 0.5)
    )
    st.write(f"- **총 공격력**: {current_atk}")
    st.write(f"- **총 방어력**: {current_def}")
    st.write(f"- **착용 무기**: {stats['equipped_weapon']['name']}")
    st.write(f"- **착용 갑옷**: {stats['equipped_armor']['name']}")

with st.sidebar.expander("🎒 인벤토리 & 보유 기술", expanded=True):
    st.markdown("**[무기 목록]**")
    for w in stats["inventory_weapons"]:
        st.write(f"- {w['name']} (공격력:{w['damage']})")
    st.markdown("**[방어구 목록]**")
    for a in stats["inventory_armors"]:
        st.write(f"- {a['name']} (방어력:{a['defense']})")

    st.markdown("---")
    st.markdown("**[체력 포션]**")
    total_hp_p = sum(stats["hp_potions"].values())
    if total_hp_p > 0:
        for p_price, p_count in stats["hp_potions"].items():
            if p_count > 0:
                heal_amt = int(p_price * 1.5)
                st.write(
                    f"- 체력 포션({p_price}G형, 회복+{heal_amt}): **{p_count}개**"
                )
    else:
        st.write("보유 중인 체력 포션이 없습니다.")

    st.markdown("**[마나 포션]**")
    total_mp_p = sum(stats["mp_potions"].values())
    if total_mp_p > 0:
        for p_price, p_count in stats["mp_potions"].items():
            if p_count > 0:
                heal_amt = int(p_price * 2.0)
                st.write(
                    f"- 마나 포션({p_price}G형, 회복+{heal_amt}): **{p_count}개**"
                )
    else:
        st.write("보유 중인 마나 포션이 없습니다.")

    st.markdown("---")
    st.markdown("**[마법 및 스킬]**")
    st.markdown("*마법:*")
    if stats["learned_magic"]:
        for mg in stats["learned_magic"]:
            st.write(f"- {mg['name']} (위력:{mg['damage']}, MP:{mg['mp_cost']})")
    else:
        st.write("습득한 마법 없음")
    st.markdown("*스킬:*")
    if stats["learned_skills"]:
        for sk in stats["learned_skills"]:
            st.write(f"- {sk['name']} (위력:{sk['damage']}, MP:{sk['mp_cost']})")
    else:
        st.write("습득한 스킬 없음")

with st.sidebar.expander("🏘️ 마을 시설 방문", expanded=True):
    tab_shop, tab_potion, tab_inn, tab_quest, tab_dojo, tab_magic = st.tabs(
        ["⚔️ 대장간", "🧪 포션상점", "🏨 여관", "📜 길드의뢰소", "🥋 훈련소", "🔮 마법길드"]
    )

    with tab_shop:
        st.write("장비를 구매하고 강화합니다.")
        st.markdown("**[무기 상점]**")
        for i, w in enumerate(st.session_state.weapon_shop):
            if st.button(
                f"구매: {w['name']} (공격:{w['damage']}, 필요힘:{w['required_str']}, {w['price']}G)",
                key=f"w_{w['name']}_{i}",
            ):
                if stats["gold"] >= w["price"]:
                    if stats["str"] >= w["required_str"]:
                        stats["gold"] -= w["price"]
                        if w not in stats["inventory_weapons"]:
                            stats["inventory_weapons"].append(w)
                        stats["equipped_weapon"] = w
                        append_ai_village_dialogue(
                            "대장간",
                            f"{w['name']} 무기를 구입하고 즉시 장착했습니다.",
                        )
                        save_game()
                        st.rerun()
                    else:
                        st.error("힘이 부족합니다!")
                else:
                    st.error("골드가 부족합니다!")

        st.markdown("**[방어구 상점]**")
        for i, a in enumerate(st.session_state.armor_shop):
            if st.button(
                f"구매: {a['name']} (방어:{a['defense']}, 필요체력:{a['required_con']}, {a['price']}G)",
                key=f"a_{a['name']}_{i}",
            ):
                if stats["gold"] >= a["price"]:
                    if stats["con"] >= a["required_con"]:
                        stats["gold"] -= a["price"]
                        if a not in stats["inventory_armors"]:
                            stats["inventory_armors"].append(a)
                        stats["equipped_armor"] = a
                        append_ai_village_dialogue(
                            "대장간",
                            f"{a['name']} 갑옷을 구입하고 즉시 착용했습니다.",
                        )
                        save_game()
                        st.rerun()
                    else:
                        st.error("체력이 부족합니다!")
                else:
                    st.error("골드가 부족합니다!")

    with tab_potion:
        st.write("포션을 구입합니다.")
        hp_tiers = [100, 200, 300, 500]
        st.markdown("**🧪 체력 포션**")
        for p_price in hp_tiers:
            heal_val = int(p_price * 1.5)
            if st.button(
                f"체력 포션 ({p_price}G) +{heal_val}", key=f"buy_hp_{p_price}"
            ):
                if stats["gold"] >= p_price:
                    stats["gold"] -= p_price
                    stats["hp_potions"][p_price] = (
                        stats["hp_potions"].get(p_price, 0) + 1
                    )
                    append_ai_village_dialogue(
                        "포션 상점", f"체력 포션({p_price}G) 구입."
                    )
                    save_game()
                    st.rerun()
                else:
                    st.error("골드 부족")

        st.markdown("**💙 마나 포션**")
        mp_tiers = [100, 200, 300, 500]
        for p_price in mp_tiers:
            heal_val = int(p_price * 2.0)
            if st.button(
                f"마나 포션 ({p_price}G) +{heal_val}", key=f"buy_mp_{p_price}"
            ):
                if stats["gold"] >= p_price:
                    stats["gold"] -= p_price
                    stats["mp_potions"][p_price] = (
                        stats["mp_potions"].get(p_price, 0) + 1
                    )
                    append_ai_village_dialogue(
                        "포션 상점", f"마나 포션({p_price}G) 구입."
                    )
                    save_game()
                    st.rerun()
                else:
                    st.error("골드 부족")

    with tab_inn:
        st.write("여관 (100G) 휴식")
        if st.button("🛏️ 여관 숙박하기 (100G)", use_container_width=True):
            if stats["gold"] >= 100:
                stats["gold"] -= 100
                stats["hp"] = stats["max_hp"]
                stats["mp"] = stats["max_mp"]
                append_ai_village_dialogue("여관", "체력/마나 완전 회복.")
                save_game()
                st.rerun()
            else:
                st.error("골드 부족 (100G 필요)")

    with tab_quest:
        st.write("길드 의뢰소")
        if stats["active_quest"]:
            q = stats["active_quest"]
            st.warning(f"진행 중: {q['title']}")
            if st.button("의뢰 포기하기", key="abandon_quest_btn"):
                stats["active_quest"] = None
                append_ai_village_dialogue("길드의뢰소", "의뢰 포기.")
                save_game()
                st.rerun()
        else:
            for q in st.session_state.quest_board:
                if not q["completed"]:
                    if st.button(f"수주: {q['title']}", key=f"q_{q['id']}"):
                        stats["active_quest"] = q
                        append_ai_village_dialogue(
                            "길드의뢰소", f"'{q['title']}' 수주."
                        )
                        save_game()
                        st.rerun()

    with tab_dojo:
        st.write("전투훈련소 (스킬 포인트로 습득)")
        st.info(f"보유 스킬 포인트: {stats.get('skill_points', 0)}P")
        for i, sk in enumerate(st.session_state.combat_dojo):
            is_learned = sk in stats["learned_skills"]
            st.markdown(
                f"- **{sk['name']}** | 위력: `{sk['damage']}` | 소모MP: `{sk['mp_cost']}`"
            )
            if not is_learned:
                if st.button(f"습득: {sk['name']}", key=f"sk_{sk['name']}_{i}"):
                    if stats.get("skill_points", 0) > 0:
                        stats["learned_skills"].append(sk)
                        stats["skill_points"] -= 1
                        append_ai_village_dialogue(
                            "훈련소", f"스킬 [{sk['name']}] 습득."
                        )
                        save_game()
                        st.rerun()
                    else:
                        st.error("스킬 포인트 부족!")
            else:
                st.text("✅ 습득 완료됨")
            st.markdown("---")

    with tab_magic:
        st.write("마법길드 연구 (골드로 마법 연구)")
        st.markdown(f"보유 골드: **{stats['gold']} G**")
        for i, mg in enumerate(st.session_state.magic_guild):
            is_learned = mg in stats["learned_magic"]
            st.markdown(
                f"- **{mg['name']}** | 위력: `{mg['damage']}` | 소모MP: `{mg['mp_cost']}` | 가격: `{mg['price']}G`"
            )
            if not is_learned:
                if st.button(f"연구: {mg['name']}", key=f"mg_{mg['name']}_{i}"):
                    if stats["gold"] >= mg["price"]:
                        stats["gold"] -= mg["price"]
                        stats["learned_magic"].append(mg)
                        append_ai_village_dialogue(
                            "마법길드", f"마법 [{mg['name']}] 연구 완료."
                        )
                        save_game()
                        st.rerun()
                    else:
                        st.error("골드 부족!")
            else:
                st.text("✅ 연구 완료됨")
            st.markdown("---")


# 🤖 [AI 턴 생성 함수: 기존 아이템 목록 전달 및 중복 생성 방지 규칙 추가]
def call_gemini_turn(user_action):
    client = genai.Client(api_key=api_key_input)
    
    # 💡 현재 등록된 모든 무기, 방어구, 마법, 스킬 이름 목록 수집
    existing_weapons = [w["name"] for w in st.session_state.get("weapon_shop", [])]
    existing_armors = [a["name"] for a in st.session_state.get("armor_shop", [])]
    existing_magics = [m["name"] for m in st.session_state.get("magic_guild", [])]
    existing_skills = [s["name"] for s in st.session_state.get("combat_dojo", [])]

    system_instruction = (
        "당신은 판타지 RPG의 게임 마스터(GM)입니다.\n"
        "모든 서사(narrative)는 반드시 1~2문장으로 매우 간결하고 핵심만 담아 작성하세요.\n"
        "플레이어의 탐험 행동에 따른 흥미진진한 상황을 빠르게 묘사하세요.\n"
        "반드시 플레이어가 다음에 선택할 수 있는 2개의 선택지(choices)를 문자열 리스트로 함께 제공하세요.\n"
        "전투가 필요하면 start_combat을 True로 설정하고 적 정보와 유형(beast, bandit, undead, mage)을 지정하세요.\n"
        "만약 플레이어가 현재 길드 의뢰(active_quest)와 관련된 적과 싸우거나 처치하도록 유도하는 상황이라면 적 이름을 퀘스트 목표에 맞게 설정해주세요.\n"
        "🚨 [중요: 중복 생성 절대 금지] 모험 도중 새로운 `new_item`(무기, 방어구, 마법, 스킬)을 제안할 때, **아래에 이미 존재하는 목록과 이름이나 효과가 단 1이라도 겹치거나 유사한 항목은 절대 생성하지 마세요.** 완전히 새롭고 유니크한 이름과 능력치를 가진 항목만 제안해야 합니다.\n"
        f"- 이미 등록된 무기 목록: {existing_weapons}\n"
        f"- 이미 등록된 방어구 목록: {existing_armors}\n"
        f"- 이미 등록된 마법 목록: {existing_magics}\n"
        f"- 이미 등록된 스킬 목록: {existing_skills}"
    )
    
    prompt = (
        f"[플레이어 상태]\n"
        f"- 레벨: {stats['level']} | HP: {stats['hp']}/{stats['max_hp']} | MP: {stats['mp']}/{stats['max_mp']}\n"
        f"- 장비: 무기({stats['equipped_weapon']['name']}), 방어구({stats['equipped_armor']['name']})\n"
        f"- 활성화된 퀘스트: {stats['active_quest']['title'] if stats['active_quest'] else '없음'}\n\n"
        f"최근 대화 기록:\n"
        + json.dumps(st.session_state.history[-4:], ensure_ascii=False)
        + f"\n\n플레이어의 행동: {user_action}"
    )

    for attempt in range(3):
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
            return GameResponse.model_validate_json(response.text)
        except Exception as e:
            if attempt < 2:
                time.sleep(2)
            else:
                st.error(f"Gemini API 오류 발생 (잠시 후 다시 시도해주세요): {e}")
                return None


def process_user_action(user_action):
    st.session_state.history.append({"role": "user", "narrative": user_action})

    with st.spinner("게임 마스터가 서사를 전개하는 중..."):
        res = call_gemini_turn(user_action)

        if res:
            narrative_text = res.narrative
            choices = (
                res.choices[:2]
                if res.choices and len(res.choices) >= 2
                else ["주변을 탐색한다", "안전한 곳으로 이동한다"]
            )

            # 🛡️ [파이썬 레벨 2중 중복 체크 및 추가 로직]
            if res.new_item and res.new_item.name and res.new_item.item_type:
                item = res.new_item
                t = item.item_type.lower()
                req = item.required_stat
                name = item.name.strip()

                if t == "weapon":
                    existing_names = [w["name"] for w in st.session_state.weapon_shop]
                    if name not in existing_names:
                        damage = int(req * 1.3)
                        price = req * 20
                        new_entry = {
                            "name": name,
                            "damage": damage,
                            "required_str": req,
                            "price": price,
                        }
                        st.session_state.weapon_shop.append(new_entry)
                        narrative_text += f"\n\n✨ **[발견]** 새로운 무기 [{name}]이(가) 대장간에 입고되었습니다!"

                elif t == "armor":
                    existing_names = [a["name"] for a in st.session_state.armor_shop]
                    if name not in existing_names:
                        defense = int(req * 1.3)
                        price = req * 20
                        new_entry = {
                            "name": name,
                            "defense": defense,
                            "required_con": req,
                            "price": price,
                        }
                        st.session_state.armor_shop.append(new_entry)
                        narrative_text += f"\n\n✨ **[발견]** 새로운 방어구 [{name}]이(가) 대장간에 입고되었습니다!"

                elif t == "magic":
                    existing_names = [m["name"] for m in st.session_state.magic_guild]
                    if name not in existing_names:
                        damage = int(req * 2.0)
                        price = req * 25
                        new_entry = {
                            "name": name,
                            "damage": damage,
                            "mp_cost": req,
                            "price": price,
                        }
                        st.session_state.magic_guild.append(new_entry)
                        narrative_text += f"\n\n🔮 **[발견]** 새로운 마법 [{name}]이(가) 마법길드에 연구되었습니다!"

                elif t == "skill":
                    existing_names = [s["name"] for s in st.session_state.combat_dojo]
                    if name not in existing_names:
                        damage = int(req * 1.5)
                        price = req * 25
                        new_entry = {
                            "name": name,
                            "damage": damage,
                            "mp_cost": req,
                            "price": price,
                        }
                        st.session_state.combat_dojo.append(new_entry)
                        narrative_text += f"\n\n🥋 **[발견]** 새로운 전투 기술 [{name}]이(가) 훈련소에 등록되었습니다!"

            st.session_state.history.append({
                "role": "assistant",
                "narrative": narrative_text,
                "choices": choices,
            })
            trim_ai_history()

            if res.start_combat:
                st.session_state.game_mode = "COMBAT"
                st.session_state.combat_sub_menu = None
                lvl = stats["level"]
                archetype = res.enemy_archetype
                hp_scale = 50 + (lvl * 25)
                atk_scale = 12 + (lvl * 4)
                def_scale = 5 + (lvl * 2)

                if archetype == "mage":
                    atk_scale *= 1.3
                    hp_scale *= 0.8
                elif archetype == "undead":
                    def_scale *= 1.5

                enemy_name = res.enemy_name or "야생의 괴물"
                if (
                    stats["active_quest"]
                    and stats["active_quest"]["target_enemy"] in enemy_name
                ):
                    enemy_name = stats["active_quest"]["target_enemy"]

                st.session_state.current_enemy = {
                    "name": enemy_name,
                    "level": lvl,
                    "hp": int(hp_scale),
                    "max_hp": int(hp_scale),
                    "atk": int(atk_scale),
                    "defense": int(def_scale),
                }

            save_game()
            st.rerun()


# 🖥️ [메인 화면 영역]
main_col, right_col = st.columns([3, 1])

with right_col:
    st.subheader("🛡️ 기본 능력치")
    st.metric(label="⭐ 레벨", value=f"Lv. {stats['level']}")
    st.metric(
        label="✨ 경험치", value=f"{stats['exp']} / {stats['max_exp']}"
    )
    st.metric(label="❤️ 체력", value=f"{stats['hp']} / {stats['max_hp']}")
    st.metric(label="💙 마나", value=f"{stats['mp']} / {stats['max_mp']}")
    st.metric(label="💰 골드", value=f"{stats['gold']} G")

    st.markdown("---")
    st.write(
        f"- **힘**: {stats['str']}\n- **민첩**: {stats['agi']}\n- **체력**: {stats['con']}\n- **지능**: {stats['int']}"
    )

    if stats.get("stat_points", 0) > 0:
        st.markdown("---")
        st.success(f"잔여 스탯: {stats['stat_points']} P")
        col_s1, col_s2 = st.columns(2)
        if col_s1.button("💪 힘+1", use_container_width=True, key="stat_str"):
            stats["str"] += 1
            stats["stat_points"] -= 1
            save_game()
            st.rerun()
        if col_s2.button(
            "⚡ 민첩+1", use_container_width=True, key="stat_agi"
        ):
            stats["agi"] += 1
            stats["stat_points"] -= 1
            save_game()
            st.rerun()
        col_s3, col_s4 = st.columns(2)
        if col_s3.button(
            "❤️ 체력+1", use_container_width=True, key="stat_con"
        ):
            stats["con"] += 1
            stats["max_hp"] += 3
            stats["hp"] = stats["max_hp"]
            stats["stat_points"] -= 1
            save_game()
            st.rerun()
        if col_s4.button(
            "🧠 지능+1", use_container_width=True, key="stat_int"
        ):
            stats["int"] += 1
            stats["max_mp"] += 2
            stats["mp"] = stats["max_mp"]
            stats["stat_points"] -= 1
            save_game()
            st.rerun()

with main_col:
    if not api_key_input:
        st.warning("⚠️ 사이드바에 Google Gemini API 키를 입력해 주세요.")
    else:
        if st.session_state.game_mode == "COMBAT":
            enemy = st.session_state.current_enemy
            st.error(f"🚨 **[전투 발생] 야생의 {enemy['name']}이(가) 나타났다!**")

            c_hp1, c_hp2, c_hp3 = st.columns(3)
            c_hp1.metric("내 HP", f"{stats['hp']} / {stats['max_hp']}")
            c_hp2.metric("내 MP", f"{stats['mp']} / {stats['max_mp']}")
            c_hp3.metric(
                f"적 HP ({enemy['name']})", f"{enemy['hp']} / {enemy['max_hp']}"
            )

            with st.expander("🧪 전투 중 포션 사용하기"):
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    st.markdown("**[체력 포션 사용]**")
                    for p_price, p_count in list(stats["hp_potions"].items()):
                        if p_count > 0:
                            heal_val = int(int(p_price) * 1.5)
                            if st.button(
                                f"체력 포션({p_price}G형, +{heal_val}) 사용 (보유:{p_count})",
                                key=f"combat_hp_{p_price}",
                            ):
                                stats["hp_potions"][p_price] -= 1
                                stats["hp"] = min(
                                    stats["max_hp"], stats["hp"] + heal_val
                                )
                                st.success(
                                    f"체력 포션을 사용하여 HP가 {heal_val} 회복되었습니다!"
                                )
                                save_game()
                                st.rerun()
                    if sum(stats["hp_potions"].values()) == 0:
                        st.write("체력 포션이 없습니다.")

                with p_col2:
                    st.markdown("**[마나 포션 사용]**")
                    for p_price, p_count in list(stats["mp_potions"].items()):
                        if p_count > 0:
                            heal_val = int(int(p_price) * 2.0)
                            if st.button(
                                f"마나 포션({p_price}G형, +{heal_val}) 사용 (보유:{p_count})",
                                key=f"combat_mp_{p_price}",
                            ):
                                stats["mp_potions"][p_price] -= 1
                                stats["mp"] = min(
                                    stats["max_mp"], stats["mp"] + heal_val
                                )
                                st.success(
                                    f"마나 포션을 사용하여 MP가 {heal_val} 회복되었습니다!"
                                )
                                save_game()
                                st.rerun()
                    if sum(stats["mp_potions"].values()) == 0:
                        st.write("마나 포션이 없습니다.")

            b_col1, b_col2, b_col3 = st.columns(3)

            if b_col1.button("🗡️ 기본 공격", use_container_width=True):
                st.session_state.combat_sub_menu = None
                base_atk = (stats["str"] * 0.8) + stats["equipped_weapon"][
                    "damage"
                ]
                crit = random.random() < (stats["agi"] * 0.005)
                mult = 1.5 if crit else 1.0
                p_dmg = max(
                    1, int((base_atk - (enemy["defense"] * 0.3)) * mult)
                )

                enemy["hp"] -= p_dmg
                log = f"플레이어의 공격! {'[크리티컬!] ' if crit else ''}{p_dmg}의 데미지를 입혔다."

                if enemy["hp"] <= 0:
                    gold_rew = enemy["level"] * 25
                    exp_rew = enemy["level"] * 40

                    if (
                        stats["active_quest"]
                        and stats["active_quest"]["target_enemy"] in enemy["name"]
                    ):
                        gold_rew += stats["active_quest"]["reward_gold"]
                        exp_rew += stats["active_quest"]["reward_exp"]
                        log += f"\n📜 **[길드 의뢰 달성!]** 보상(골드+{stats['active_quest']['reward_gold']}, EXP+{stats['active_quest']['reward_exp']}) 추가 획득!"
                        stats["active_quest"] = None

                    stats["gold"] += gold_rew
                    leveled = add_exp(exp_rew)
                    st.session_state.game_mode = "EXPLORATION"
                    st.session_state.current_enemy = None
                    log += f"\n🎉 승리! (보상: {gold_rew}G, {exp_rew} EXP){' [레벨 업!]' if leveled else ''}"
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": log,
                        "choices": ["마을로 돌아간다", "계속 탐험한다"],
                    })
                    trim_ai_history()
                else:
                    e_dmg = max(
                        1,
                        int(
                            enemy["atk"]
                            - (
                                stats["equipped_armor"]["defense"]
                                + (stats["con"] * 0.5)
                            )
                        ),
                    )
                    stats["hp"] = max(0, stats["hp"] - e_dmg)
                    log += f"\n적의 반격으로 {e_dmg}의 피해를 입었다!"
                    if stats["hp"] <= 0:
                        stats["hp"] = 20
                        st.session_state.game_mode = "EXPLORATION"
                        st.session_state.current_enemy = None
                        log += "\n💀 전투에서 패배하여 쓰러졌으나 겨우 정신을 차렸다."
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": log,
                        "choices": ["정비를 위해 마을로 간다", "다시 도전한다"],
                    })
                    trim_ai_history()
                save_game()
                st.rerun()

            if stats["learned_skills"] and b_col2.button(
                "⚡ 스킬 선택", use_container_width=True
            ):
                st.session_state.combat_sub_menu = (
                    "skill"
                    if st.session_state.combat_sub_menu != "skill"
                    else None
                )
                st.rerun()

            if stats["learned_magic"] and b_col3.button(
                "🔮 마법 선택", use_container_width=True
            ):
                st.session_state.combat_sub_menu = (
                    "magic"
                    if st.session_state.combat_sub_menu != "magic"
                    else None
                )
                st.rerun()

            if st.session_state.combat_sub_menu == "skill":
                st.markdown("---")
                st.markdown("### ⚡ 사용할 전투 스킬 선택")
                for sk in stats["learned_skills"]:
                    if st.button(
                        f"{sk['name']} (위력:{sk['damage']}, 소모MP: {sk['mp_cost']})",
                        key=f"combat_use_sk_{sk['name']}",
                    ):
                        if stats["mp"] >= sk["mp_cost"]:
                            stats["mp"] -= sk["mp_cost"]
                            skill_dmg = (
                                (stats["str"] * 0.5)
                                + sk["damage"]
                                + (stats["int"] * 0.3)
                            )
                            enemy["hp"] -= int(skill_dmg)
                            log = f"스킬 [{sk['name']}] 발동! {int(skill_dmg)}의 피해를 입혔다."

                            if enemy["hp"] <= 0:
                                gold_rew = enemy["level"] * 30
                                exp_rew = enemy["level"] * 50

                                if (
                                    stats["active_quest"]
                                    and stats["active_quest"]["target_enemy"]
                                    in enemy["name"]
                                ):
                                    gold_rew += stats["active_quest"][
                                        "reward_gold"
                                    ]
                                    exp_rew += stats["active_quest"][
                                        "reward_exp"
                                    ]
                                    log += f"\n📜 **[길드 의뢰 달성!]** 보상 추가 획득!"
                                    stats["active_quest"] = None

                                stats["gold"] += gold_rew
                                add_exp(exp_rew)
                                st.session_state.game_mode = "EXPLORATION"
                                st.session_state.current_enemy = None
                                log += "\n🎉 적을 격파했습니다!"
                            else:
                                e_dmg = max(
                                    1,
                                    int(
                                        enemy["atk"]
                                        - stats["equipped_armor"]["defense"]
                                    ),
                                )
                                stats["hp"] = max(0, stats["hp"] - e_dmg)
                                log += f"\n적의 반격! {e_dmg} 피해."

                            st.session_state.combat_sub_menu = None
                            st.session_state.history.append({
                                "role": "assistant",
                                "narrative": log,
                                "choices": ["마을로 돌아간다", "계속 탐험한다"],
                            })
                            trim_ai_history()
                            save_game()
                            st.rerun()
                        else:
                            st.error("마나가 부족합니다!")

            if st.session_state.combat_sub_menu == "magic":
                st.markdown("---")
                st.markdown("### 🔮 사용할 마법 선택")
                for mg in stats["learned_magic"]:
                    if st.button(
                        f"{mg['name']} (위력:{mg['damage']}, 소모MP: {mg['mp_cost']})",
                        key=f"combat_use_mg_{mg['name']}",
                    ):
                        if stats["mp"] >= mg["mp_cost"]:
                            stats["mp"] -= mg["mp_cost"]
                            mag_dmg = (stats["int"] * 1.5) + mg["damage"]
                            enemy["hp"] -= int(mag_dmg)
                            log = f"마법 [{mg['name']}] 시전! {int(mag_dmg)}의 마법 피해."

                            if enemy["hp"] <= 0:
                                gold_rew = enemy["level"] * 30
                                exp_rew = enemy["level"] * 50

                                if (
                                    stats["active_quest"]
                                    and stats["active_quest"]["target_enemy"]
                                    in enemy["name"]
                                ):
                                    gold_rew += stats["active_quest"][
                                        "reward_gold"
                                    ]
                                    exp_rew += stats["active_quest"][
                                        "reward_exp"
                                    ]
                                    log += f"\n📜 **[길드 의뢰 달성!]** 보상 추가 획득!"
                                    stats["active_quest"] = None

                                stats["gold"] += gold_rew
                                add_exp(exp_rew)
                                st.session_state.game_mode = "EXPLORATION"
                                st.session_state.current_enemy = None
                                log += "\n🎉 적을 격파했습니다!"
                            else:
                                e_dmg = max(
                                    1,
                                    int(
                                        enemy["atk"]
                                        - stats["equipped_armor"]["defense"]
                                    ),
                                )
                                stats["hp"] = max(0, stats["hp"] - e_dmg)
                                log += f"\n적의 반격! {e_dmg} 피해."

                            st.session_state.combat_sub_menu = None
                            st.session_state.history.append({
                                "role": "assistant",
                                "narrative": log,
                                "choices": ["마을로 돌아간다", "계속 탐험한다"],
                            })
                            trim_ai_history()
                            save_game()
                            st.rerun()
                        else:
                            st.error("마나가 부족합니다!")

            if st.session_state.history:
                st.info(st.session_state.history[-1].get("narrative", ""))

        else:
            for idx, h in enumerate(st.session_state.history):
                with st.chat_message(h["role"]):
                    st.markdown(h.get("narrative", ""))

                    if (
                        h["role"] == "assistant"
                        and idx == len(st.session_state.history) - 1
                        and "choices" in h
                        and h["choices"]
                    ):
                        st.markdown("---")
                        st.markdown("**💡 선택지:**")
                        c_btn1, c_btn2 = st.columns(2)
                        choices = h["choices"]
                        if len(choices) >= 1 and c_btn1.button(
                            f"1️⃣ {choices[0]}", key=f"choice_0_{idx}"
                        ):
                            process_user_action(choices[0])
                        if len(choices) >= 2 and c_btn2.button(
                            f"2️⃣ {choices[1]}", key=f"choice_1_{idx}"
                        ):
                            process_user_action(choices[1])

            chat_input = st.chat_input(
                "원하는 행동을 직접 입력하거나 위 선택지를 클릭하세요..."
            )
            if chat_input:
                process_user_action(chat_input)
