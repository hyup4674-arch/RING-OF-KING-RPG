import json
import os
import random
import time
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_save_v7.json"

st.set_page_config(
    page_title="AI 연동 동기화 파이썬 엔진 RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ 반지의 제왕: AI 서사 + 철저 밸런스 감산식 엔진 RPG")


# 📋 [Pydantic 스키마]
class GeneratedItem(BaseModel):
    item_type: str = Field(
        default="",
        description="아이템 종류: 'weapon', 'armor', 'magic', 'skill' 중 하나",
    )
    name: str = Field(
        default="", description="기존에 없는 완전히 새로운 유니크한 이름"
    )
    required_stat: int = Field(default=5, description="필요 능력치 또는 소모MP")


class StatUpItemResponse(BaseModel):
    item_type: str = Field(
        description="'weapon', 'armor', 'magic', 'skill' 중 하나 선택"
    )
    name: str = Field(description="완전히 새롭고 유니크한 판타지 이름")
    required_stat: int = Field(
        description="요구 힘/체력 또는 소모MP 수치 (현재 스탯에 맞는 적절한 값)"
    )


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
        "pending_enemy": st.session_state.get("pending_enemy", None),
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
                "name": "녹슨 단검",
                "damage": 6,
                "required_str": 5,
                "price": 36,
            },
            {
                "name": "초보자의 단검",
                "damage": 12,
                "required_str": 10,
                "price": 72,
            },
        ],
    )

if "armor_shop" not in st.session_state:
    st.session_state.armor_shop = saved_data.get(
        "armor_shop",
        [
            {
                "name": "낡은 천옷",
                "defense": 4,
                "required_con": 5,
                "price": 28,
            },
            {
                "name": "여행자 가죽옷",
                "defense": 8,
                "required_con": 10,
                "price": 56,
            },
        ],
    )

if "magic_guild" not in st.session_state:
    st.session_state.magic_guild = saved_data.get(
        "magic_guild",
        [
            {"name": "매직 미사일", "damage": 15, "mp_cost": 15, "price": 375},
            {"name": "파이어볼", "damage": 30, "mp_cost": 27, "price": 750},
        ],
    )

if "combat_dojo" not in st.session_state:
    st.session_state.combat_dojo = saved_data.get(
        "combat_dojo",
        [
            {"name": "내려치기", "damage": 12, "mp_cost": 13},
            {"name": "연속 베기", "damage": 24, "mp_cost": 17},
        ],
    )

if "quest_board" not in st.session_state:
    st.session_state.quest_board = saved_data.get(
        "quest_board",
        [
            {
                "id": 1,
                "title": "샤이어 주변 오르크 정찰병 소탕",
                "target_enemy": "오르크 정찰병",
                "reward_gold": 50,
                "reward_exp": 60,
                "completed": False,
            },
            {
                "id": 2,
                "title": "모리아 광산의 고블린 척살",
                "target_enemy": "모리아 고블린",
                "reward_gold": 120,
                "reward_exp": 120,
                "completed": False,
            },
        ],
    )

if "stats" not in st.session_state:
    st.session_state.stats = saved_data.get(
        "stats",
        {
            "hp": 70,
            "max_hp": 70,
            "mp": 35,
            "max_mp": 35,
            "gold": 10,
            "level": 1,
            "exp": 0,
            "max_exp": 100,
            "str": 5,
            "agi": 5,
            "con": 5,
            "int": 5,
            "stat_points": 0,
            "skill_points": 0,
            "hp_potions": {100: 0},
            "mp_potions": {100: 0},
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
    st.session_state.stats["hp_potions"] = {100: 0}
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
                "중간계의 평화로운 샤이어에서 모험이 시작됩니다. 어둠의 그림자가"
                " 서서히 드리우고 있습니다."
            ),
            "choices": ["브리 마을을 향해 길을 떠난다", "주변 숲에서 정비한다"],
        })

if "game_mode" not in st.session_state:
    st.session_state.game_mode = saved_data.get("game_mode", "EXPLORATION")

if "current_enemy" not in st.session_state:
    st.session_state.current_enemy = saved_data.get("current_enemy", None)

if "pending_enemy" not in st.session_state:
    st.session_state.pending_enemy = saved_data.get("pending_enemy", None)


# 📈 [경험치 및 레벨업 처리]
def add_exp(amount):
    player = st.session_state.stats
    player["exp"] += amount
    leveled_up = False
    while player["exp"] >= player["max_exp"]:
        player["exp"] -= player["max_exp"]
        player["level"] += 1
        player["max_exp"] = int(player["max_exp"] * 1.4)
        player["stat_points"] += 2
        player["skill_points"] += 1
        player["max_hp"] += 10
        player["hp"] = player["max_hp"]
        player["max_mp"] += 10
        player["mp"] = player["max_mp"]
        leveled_up = True
    return leveled_up


# 🤖 [스탯 마일스톤 보상 생성]
def generate_stat_milestone_reward(
    api_key, selected_model, stat_name, stat_val
):
    if not api_key:
        return
    try:
        client = genai.Client(api_key=api_key)
        existing_weapons = [
            w["name"] for w in st.session_state.get("weapon_shop", [])
        ]
        existing_armors = [
            a["name"] for a in st.session_state.get("armor_shop", [])
        ]
        existing_magics = [
            m["name"] for m in st.session_state.get("magic_guild", [])
        ]
        existing_skills = [
            s["name"] for s in st.session_state.get("combat_dojo", [])
        ]

        prompt = (
            f"현재 플레이어 레벨: {stats['level']}\n"
            f"성장한 스탯: {stat_name} (도달 수치: {stat_val})\n"
            f"이미 등록된 무기: {existing_weapons}\n"
            f"이미 등록된 방어구: {existing_armors}\n"
            f"이미 등록된 마법: {existing_magics}\n"
            f"이미 등록된 스킬: {existing_skills}\n"
            "반지의 제왕 세계관에 걸맞으며 기존 목록과 겹치지 않는 유니크한 장비, 마법 또는 기술 하나를 생성해주세요."
        )
        response = client.models.generate_content(
            model=selected_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StatUpItemResponse,
                temperature=0.8,
            ),
        )
        item_data = StatUpItemResponse.model_validate_json(response.text)

        t = item_data.item_type.lower()
        name = item_data.name.strip()
        req = item_data.required_stat

        if t == "weapon" and name not in existing_weapons:
            damage = int(req * 1.2)
            price = damage * 6
            st.session_state.weapon_shop.append({
                "name": name,
                "damage": damage,
                "required_str": req,
                "price": price,
            })
            st.toast(f"✨ 중간계의 명검 [{name}]이(가) 대장간에 입고되었습니다!")
        elif t == "armor" and name not in existing_armors:
            defense = int(req * 0.8)
            price = defense * 7
            st.session_state.armor_shop.append({
                "name": name,
                "defense": defense,
                "required_con": req,
                "price": price,
            })
            st.toast(
                f"✨ 중간계의 방어구 [{name}]이(가) 대장간에 입고되었습니다!"
            )
        elif t == "magic" and name not in existing_magics:
            damage = int(req * 1.5)
            mp_cost = req
            price = damage * 25
            st.session_state.magic_guild.append({
                "name": name,
                "damage": damage,
                "mp_cost": mp_cost,
                "price": price,
            })
            st.toast(
                f"🔮 고대의 마법 [{name}]이(가) 마법 길드에 연구되었습니다!"
            )
        elif t == "skill" and name not in existing_skills:
            damage = int(req * 1.2)
            mp_cost = int(10 + (damage * 0.3))
            st.session_state.combat_dojo.append({
                "name": name,
                "damage": damage,
                "mp_cost": mp_cost,
            })
            st.toast(f"🥋 전설의 전투 기술 [{name}]이(가) 훈련소에 등록되었습니다!")
    except Exception:
        pass


# ⚙️ [좌측 슬라이드 창 설정]
st.sidebar.header("⚙️ 게임 설정 및 메뉴")

api_key_input = DEFAULT_API_KEY
selected_model = "gemini-3.1-flash-lite"

with st.sidebar.expander("🔑 AI 모델 및 클라우드 세이브", expanded=True):
    api_key_input = st.text_input(
        "Google Gemini API 키", value=DEFAULT_API_KEY, type="password"
    )

    st.markdown("---")
    if st.button("🔄 게임 데이터 초기화", use_container_width=True):
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("게임이 초기화되었습니다. 새로고침 중...")
        st.rerun()

    st.markdown("---")
    save_game()
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            save_data_str = f.read()
        st.download_button(
            label="📥 세이브 파일 백업",
            data=save_data_str,
            file_name="rpg_save_v7.json",
            mime="application/json",
            use_container_width=True,
        )

    st.markdown("---")
    uploaded_file = st.file_uploader("📤 세이브 파일 업로드", type=["json"])
    if uploaded_file is not None:
        try:
            content = json.load(uploaded_file)
            if isinstance(content, dict):
                with open(SAVE_FILE, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False)
                st.success("세이브 데이터 복구 완료! 앱 재시작...")
                st.rerun()
        except Exception:
            st.error("오류 발생")

    st.markdown("---")
    flash_lite_models = [
        {
            "id": "gemini-3.1-flash-lite",
            "name": "Gemini 3.1 Flash-Lite (기본)",
        },
        {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash-Lite"},
        {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash-Lite"},
    ]
    selected_model = st.selectbox(
        "사용할 Gemini 모델 선택",
        options=[m["id"] for m in flash_lite_models],
        index=0,
    )

stats = st.session_state.stats

with st.sidebar.expander("⚔️ 전투력 및 장비 현황", expanded=True):
    current_atk = stats["str"] + stats["equipped_weapon"].get("damage", 0)
    current_def = stats["equipped_armor"].get("defense", 0) + stats["con"]
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
    st.markdown("**[포션]**")
    total_hp_p = sum(stats["hp_potions"].values())
    if total_hp_p > 0:
        for p_price, p_count in stats["hp_potions"].items():
            if p_count > 0:
                st.write(f"- 체력 포션: **{p_count}개**")
    else:
        st.write("체력 포션 없음")

    total_mp_p = sum(stats["mp_potions"].values())
    if total_mp_p > 0:
        for p_price, p_count in stats["mp_potions"].items():
            if p_count > 0:
                st.write(f"- 마나 포션: **{p_count}개**")
    else:
        st.write("마나 포션 없음")

# 🏘️ [마을 시설 방문 - API 호출 없이 즉시 처리]
with st.sidebar.expander("🏘️ 마을 시설 방문", expanded=True):
    tab_shop, tab_potion, tab_inn, tab_quest, tab_dojo, tab_magic = st.tabs([
        "⚔️ 대장간",
        "🧪 포션상점",
        "🏨 여관",
        "📜 길드의뢰소",
        "🥋 훈련소",
        "🔮 마법길드",
    ])

    with tab_shop:
        st.write("장비 구매 및 강화")
        st.markdown("**[무기 상점]**")
        for i, w in enumerate(st.session_state.weapon_shop):
            if st.button(
                f"구매: {w['name']} ({w['price']}G)", key=f"w_{w['name']}_{i}"
            ):
                if stats["gold"] >= w["price"]:
                    if stats["str"] >= w["required_str"]:
                        stats["gold"] -= w["price"]
                        if w not in stats["inventory_weapons"]:
                            stats["inventory_weapons"].append(w)
                        stats["equipped_weapon"] = w
                        save_game()
                        st.rerun()
                    else:
                        st.error("힘 부족")
                else:
                    st.error("골드 부족")

        st.markdown("**[방어구 상점]**")
        for i, a in enumerate(st.session_state.armor_shop):
            if st.button(
                f"구매: {a['name']} ({a['price']}G)", key=f"a_{a['name']}_{i}"
            ):
                if stats["gold"] >= a["price"]:
                    if stats["con"] >= a["required_con"]:
                        stats["gold"] -= a["price"]
                        if a not in stats["inventory_armors"]:
                            stats["inventory_armors"].append(a)
                        stats["equipped_armor"] = a
                        save_game()
                        st.rerun()
                    else:
                        st.error("체력 부족")
                else:
                    st.error("골드 부족")

    with tab_potion:
        st.write("포션 구입")
        if st.button("체력 포션 구매 (50G)", key="buy_hp_50"):
            if stats["gold"] >= 50:
                stats["gold"] -= 50
                stats["hp_potions"][50] = stats["hp_potions"].get(50, 0) + 1
                save_game()
                st.rerun()
            else:
                st.error("골드 부족")
        if st.button("마나 포션 구매 (50G)", key="buy_mp_50"):
            if stats["gold"] >= 50:
                stats["gold"] -= 50
                stats["mp_potions"][50] = stats["mp_potions"].get(50, 0) + 1
                save_game()
                st.rerun()
            else:
                st.error("골드 부족")

    with tab_inn:
        st.write("여관 휴식 (30G)")
        if st.button("숙박하기", use_container_width=True):
            if stats["gold"] >= 30:
                stats["gold"] -= 30
                stats["hp"] = stats["max_hp"]
                stats["mp"] = stats["max_mp"]
                save_game()
                st.rerun()
            else:
                st.error("골드 부족")

    with tab_quest:
        st.write("의뢰 수주")
        if stats["active_quest"]:
            if st.button("의뢰 포기하기"):
                stats["active_quest"] = None
                save_game()
                st.rerun()
        else:
            for q in st.session_state.quest_board:
                if not q["completed"]:
                    if st.button(f"수주: {q['title']}", key=f"q_{q['id']}"):
                        stats["active_quest"] = q
                        save_game()
                        st.rerun()

    with tab_dojo:
        st.write("스킬 습득")
        for i, sk in enumerate(st.session_state.combat_dojo):
            if sk not in stats["learned_skills"]:
                if st.button(f"습득: {sk['name']}", key=f"sk_{sk['name']}_{i}"):
                    if stats.get("skill_points", 0) > 0:
                        stats["learned_skills"].append(sk)
                        stats["skill_points"] -= 1
                        save_game()
                        st.rerun()
                    else:
                        st.error("포인트 부족")
            else:
                st.text(f"✅ {sk['name']} (습득됨)")

    with tab_magic:
        st.write("마법 연구")
        for i, mg in enumerate(st.session_state.magic_guild):
            if mg not in stats["learned_magic"]:
                if st.button(f"연구: {mg['name']}", key=f"mg_{mg['name']}_{i}"):
                    if stats["gold"] >= mg["price"]:
                        stats["gold"] -= mg["price"]
                        stats["learned_magic"].append(mg)
                        save_game()
                        st.rerun()
                    else:
                        st.error("골드 부족")
            else:
                st.text(f"✅ {mg['name']} (연구됨)")


# 🤖 [AI 턴 생성 함수 - 반지의 제왕 스토리 기반]
def call_gemini_turn(user_action):
    client = genai.Client(api_key=api_key_input)

    existing_weapons = [
        w["name"] for w in st.session_state.get("weapon_shop", [])
    ]
    existing_armors = [
        a["name"] for a in st.session_state.get("armor_shop", [])
    ]
    existing_magics = [
        m["name"] for m in st.session_state.get("magic_guild", [])
    ]
    existing_skills = [
        s["name"] for s in st.session_state.get("combat_dojo", [])
    ]

    system_instruction = (
        "당신은 판타지 RPG의 게임 마스터(GM)이며, 전체 세계관과 스토리는 '반지의 제왕' (The Lord of the Rings)의 서사를 기반으로 진행됩니다.\n"
        "중간계(Middle-earth)의 배경(샤이어, 리븐델, 모르도르 등)과 원작의 거대한 서사 흐름(절대반지 파괴를 향한 여정, 사루만과 사우론의 위협 등)을 충실히 반영하세요.\n"
        "플레이어는 이 세계 속에서 성장하며 주변 사건에 참여하고 기여할 수 있지만, '반지의 제왕'의 거대한 역사적 흐름이나 핵심 운명을 왜곡하거나 방해해서는 안 됩니다.\n"
        "모든 서사(narrative)는 반드시 1~2문장으로 매우 간결하고 핵심만 담아 작성하세요.\n"
        "반드시 플레이어가 다음에 선택할 수 있는 2개의 선택지(choices)를 문자열 리스트로 함께 제공하세요.\n"
        "전투가 필요하면 start_combat을 True로 설정하고 적 정보와 유형(beast, bandit, undead, mage)을 지정하세요.\n"
        "🚨 [중요: 중복 생성 절대 금지] 모험 도중 새로운 `new_item`을 제안할 때, 이미 등록된 목록과 이름이나 효과가 단 1이라도 겹치거나 유사한 항목은 절대 생성하지 마세요.\n"
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
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1)


def process_user_action(user_action):
    # 적과 조우한 상태(pending_enemy)에서 선택지를 골랐을 경우 처리
    if st.session_state.get("pending_enemy"):
        if user_action == "싸운다":
            st.session_state.history.append({"role": "user", "narrative": user_action})
            st.session_state.current_enemy = st.session_state.pending_enemy
            st.session_state.pending_enemy = None
            st.session_state.game_mode = "COMBAT"
            save_game()
            st.rerun()
            return
        elif user_action == "도망친다":
            st.session_state.history.append({"role": "user", "narrative": user_action})
            st.session_state.pending_enemy = None
            # 도망친 후에는 전투가 시작되지 않고, '도망친다' 행동을 AI에게 전달하여 다음 AI 메시지가 나오도록 처리

    else:
        st.session_state.history.append({"role": "user", "narrative": user_action})

    with st.spinner("중간계의 운명이 전개되는 중..."):
        res = call_gemini_turn(user_action)

        if res:
            narrative_text = res.narrative
            choices = (
                res.choices[:2]
                if res.choices and len(res.choices) >= 2
                else ["주변을 탐색한다", "안전한 곳으로 이동한다"]
            )

            if res.new_item and res.new_item.name and res.new_item.item_type:
                item = res.new_item
                t = item.item_type.lower()
                req = item.required_stat
                name = item.name.strip()

                if t == "weapon":
                    existing_names = [
                        w["name"] for w in st.session_state.weapon_shop
                    ]
                    if name not in existing_names:
                        damage = int(req * 1.2)
                        price = damage * 6
                        st.session_state.weapon_shop.append({
                            "name": name,
                            "damage": damage,
                            "required_str": req,
                            "price": price,
                        })
                        narrative_text += (
                            f"\n\n✨ 새로운 무기 [{name}]이(가) 발견되었습니다!"
                        )
                elif t == "armor":
                    existing_names = [
                        a["name"] for a in st.session_state.armor_shop
                    ]
                    if name not in existing_names:
                        defense = int(req * 0.8)
                        price = defense * 7
                        st.session_state.armor_shop.append({
                            "name": name,
                            "defense": defense,
                            "required_con": req,
                            "price": price,
                        })
                        narrative_text += (
                            f"\n\n✨ 새로운 방어구 [{name}]이(가) 발견되었습니다!"
                        )
                elif t == "magic":
                    existing_names = [
                        m["name"] for m in st.session_state.magic_guild
                    ]
                    if name not in existing_names:
                        damage = int(req * 1.5)
                        mp_cost = req
                        price = damage * 25
                        st.session_state.magic_guild.append({
                            "name": name,
                            "damage": damage,
                            "mp_cost": mp_cost,
                            "price": price,
                        })
                        narrative_text += (
                            f"\n\n🔮 새로운 마법 [{name}]이(가) 연구되었습니다!"
                        )
                elif t == "skill":
                    existing_names = [
                        s["name"] for s in st.session_state.combat_dojo
                    ]
                    if name not in existing_names:
                        damage = int(req * 1.2)
                        mp_cost = int(10 + (damage * 0.3))
                        st.session_state.combat_dojo.append({
                            "name": name,
                            "damage": damage,
                            "mp_cost": mp_cost,
                        })
                        narrative_text += (
                            f"\n\n🥋 새로운 전투 기술 [{name}]이(가) 등록되었습니다!"
                        )

            if res.start_combat:
                lvl = stats["level"]
                archetype = res.enemy_archetype
                hp_scale = 30 + (lvl * 15)
                atk_scale = 8 + (lvl * 2)
                def_scale = 2 + (lvl * 1)

                enemy_name = res.enemy_name or "오르크 전사"
                if (
                    stats["active_quest"]
                    and stats["active_quest"]["target_enemy"] in enemy_name
                ):
                    enemy_name = stats["active_quest"]["target_enemy"]

                st.session_state.pending_enemy = {
                    "name": enemy_name,
                    "level": lvl,
                    "hp": int(hp_scale),
                    "max_hp": int(hp_scale),
                    "atk": int(atk_scale),
                    "defense": int(def_scale),
                }

                # 전투가 시작되기 전 AI 메시지의 마지막 부분에 적의 HP와 공격력 표시
                narrative_text += f"\n\n⚔️ **[적 조우: {enemy_name}]** (HP: {int(hp_scale)}, 공격력: {int(atk_scale)})"
                choices = ["싸운다", "도망친다"]
                st.session_state.game_mode = "EXPLORATION"

            st.session_state.history.append({
                "role": "assistant",
                "narrative": narrative_text,
                "choices": choices,
            })
            trim_ai_history()
            save_game()
            st.rerun()


# 🖥️ [메인 화면 영역]
main_col, right_col = st.columns([3, 1])

with right_col:
    st.subheader("🛡️ 기본 능력치")
    st.metric(label="⭐ 레벨", value=f"Lv. {stats['level']}")
    st.metric(label="✨ 경험치", value=f"{stats['exp']} / {stats['max_exp']}")
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
            if stats["str"] % 3 == 0:
                generate_stat_milestone_reward(
                    api_key_input, selected_model, "힘(str)", stats["str"]
                )
            save_game()
            st.rerun()
        if col_s2.button("⚡ 민첩+1", use_container_width=True, key="stat_agi"):
            stats["agi"] += 1
            stats["stat_points"] -= 1
            if stats["agi"] % 3 == 0:
                generate_stat_milestone_reward(
                    api_key_input, selected_model, "민첩(agi)", stats["agi"]
                )
            save_game()
            st.rerun()
        col_s3, col_s4 = st.columns(2)
        if col_s3.button("❤️ 체력+1", use_container_width=True, key="stat_con"):
            stats["con"] += 1
            stats["max_hp"] += 3
            stats["hp"] = stats["max_hp"]
            stats["stat_points"] -= 1
            if stats["con"] % 3 == 0:
                generate_stat_milestone_reward(
                    api_key_input, selected_model, "체력(con)", stats["con"]
                )
            save_game()
            st.rerun()
        if col_s4.button("🧠 지능+1", use_container_width=True, key="stat_int"):
            stats["int"] += 1
            stats["max_mp"] += 2
            stats["mp"] = stats["max_mp"]
            stats["stat_points"] -= 1
            if stats["int"] % 3 == 0:
                generate_stat_milestone_reward(
                    api_key_input, selected_model, "지능(int)", stats["int"]
                )
            save_game()
            st.rerun()

with main_col:
    if not api_key_input:
        st.warning("⚠️ 사이드바에 Google Gemini API 키를 입력해 주세요.")
    else:
        if st.session_state.game_mode == "COMBAT":
            enemy = st.session_state.current_enemy

            # 붉은색 HP 막대 (왼쪽) 및 푸른색 HP 막대 (오른쪽) 가로로 크게 배치
            st.markdown(
                f"""
                <div style="display: flex; justify-content: space-between; gap: 20px; margin-bottom: 25px; background-color: #1e1e1e; padding: 20px; border-radius: 10px; border: 1px solid #444;">
                    <div style="flex: 1; text-align: center;">
                        <h3 style="color: #ff4b4b; margin-bottom: 8px;">❤️ 플레이어</h3>
                        <div style="background-color: #333; border-radius: 8px; height: 35px; width: 100%; border: 2px solid #ff4b4b; overflow: hidden; position: relative;">
                            <div style="background-color: #ff4b4b; width: {max(0, min(100, (stats['hp']/stats['max_hp'])*100))}%; height: 100%; transition: width 0.3s;"></div>
                            <div style="position: absolute; width: 100%; top: 0; left: 0; text-align: center; color: white; font-weight: bold; line-height: 31px; font-size: 16px; text-shadow: 1px 1px 2px black;">
                                {stats['hp']} / {stats['max_hp']}
                            </div>
                        </div>
                    </div>
                    <div style="flex: 1; text-align: center;">
                        <h3 style="color: #4b88ff; margin-bottom: 8px;">💙 {enemy['name']}</h3>
                        <div style="background-color: #333; border-radius: 8px; height: 35px; width: 100%; border: 2px solid #4b88ff; overflow: hidden; position: relative;">
                            <div style="background-color: #4b88ff; width: {max(0, min(100, (enemy['hp']/enemy['max_hp'])*100))}%; height: 100%; transition: width 0.3s;"></div>
                            <div style="position: absolute; width: 100%; top: 0; left: 0; text-align: center; color: white; font-weight: bold; line-height: 31px; font-size: 16px; text-shadow: 1px 1px 2px black;">
                                {enemy['hp']} / {enemy['max_hp']}
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            msg_slot = st.empty()

            # 🤖 [자동 전투 턴 계산: API 호출 없이 파이썬 내부 연산만 수행]
            best_attack_name = "기본 공격"
            p_dmg = 0
            best_skill = None
            max_skill_dmg = -1

            for sk in stats.get("learned_skills", []):
                if stats["mp"] >= sk["mp_cost"]:
                    s_dmg = int(sk["damage"] + (stats["str"] * 0.5))
                    if s_dmg > max_skill_dmg:
                        max_skill_dmg = s_dmg
                        best_skill = sk

            if best_skill:
                best_attack_name = f"스킬 [{best_skill['name']}]"
                stats["mp"] -= best_skill["mp_cost"]
                crit = random.random() < (stats["agi"] * 0.005)
                mult = 1.5 if crit else 1.0
                p_dmg = max(1, int((max_skill_dmg - enemy["defense"]) * mult))
            else:
                base_atk = stats["str"] + stats["equipped_weapon"]["damage"]
                crit = random.random() < (stats["agi"] * 0.005)
                mult = 1.5 if crit else 1.0
                p_dmg = max(1, int((base_atk - enemy["defense"]) * mult))

            enemy["hp"] -= p_dmg
            log = f"플레이어의 {best_attack_name}! {'[크리티컬!] ' if crit else ''}{p_dmg}의 데미지를 입혔다."

            if enemy["hp"] <= 0:
                gold_rew = enemy["level"] * 20
                exp_rew = enemy["level"] * 35
                if (
                    stats["active_quest"]
                    and stats["active_quest"]["target_enemy"] in enemy["name"]
                ):
                    gold_rew += stats["active_quest"]["reward_gold"]
                    exp_rew += stats["active_quest"]["reward_exp"]
                    log += f"\n📜 길드 의뢰 달성!"
                    stats["active_quest"] = None
                stats["gold"] += gold_rew
                leveled = add_exp(exp_rew)
                st.session_state.game_mode = "EXPLORATION"
                st.session_state.current_enemy = None
                log += f"\n🎉 승리! 보상 획득 ({gold_rew}G){' [레벨 업!]' if leveled else ''}"
                st.session_state.history.append({
                    "role": "assistant",
                    "narrative": log,
                    "choices": ["원정길을 계속 간다", "안전한 곳으로 이동한다"],
                })
                trim_ai_history()
                msg_slot.info(log)
                time.sleep(3)
                msg_slot.empty()
                save_game()
                st.rerun()
            else:
                total_player_def = (
                    stats["equipped_armor"]["defense"] + stats["con"]
                )
                e_dmg = max(1, enemy["atk"] - total_player_def)
                stats["hp"] = max(0, stats["hp"] - e_dmg)
                log += f"\n적의 반격으로 {e_dmg}의 피해를 입었다!"

                if stats["hp"] <= 0:
                    stats["hp"] = 15
                    st.session_state.game_mode = "EXPLORATION"
                    st.session_state.current_enemy = None
                    log += f"\n💀 전투에서 쓰러졌으나 간신히 정신을 차렸다."
                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": log,
                        "choices": ["정비 후 다시 나선다", "휴식을 취한다"],
                    })
                    trim_ai_history()
                    msg_slot.info(log)
                    time.sleep(3)
                    msg_slot.empty()
                    save_game()
                    st.rerun()

            msg_slot.info(log)
            time.sleep(3)
            msg_slot.empty()
            save_game()
            st.rerun()

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
                "중간계에서의 행동을 입력하거나 위 선택지를 클릭하세요..."
            )
            if chat_input:
                process_user_action(chat_input)
