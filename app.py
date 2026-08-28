import json
import os
import random
import time
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_save_v8.json"

st.set_page_config(
    page_title="AI 연동 동기화 파이썬 엔진 RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ 반지의 제왕: AI 서사 + 즉발 전투 엔진 RPG")


# 📋 [Pydantic 스키마 - 게임 서사 전용 (아이템 생성 제거)]
class GameResponse(BaseModel):
    narrative: str = Field(
        description="1~2문장으로 매우 간결하게 요약된 스토리 서사 묘사."
    )
    choices: list[str] = Field(
        default=["주변을 탐색한다", "안전한 곳으로 이동한다"],
        description="플레이어가 선택할 수 있는 정확히 2개의 선택지 리스트",
    )
    start_combat: bool = Field(default=False, description="전투 조우 여부")
    enemy_name: str = Field(default="", description="조우한 적의 이름")
    enemy_archetype: str = Field(
        default="beast", description="적의 유형 (beast, bandit, undead, mage)"
    )


# 📋 [Pydantic 스키마 - 상점 리뉴얼 전용]
class ShopItemResponse(BaseModel):
    item_type: str = Field(description="'weapon', 'armor', 'magic', 'skill' 중 하나")
    name: str = Field(description="완전히 새롭고 유니크한 판타지 이름")
    required_stat: int = Field(description="장착 및 사용 요구 수치 (1 이상)")

class ShopRenewalResponse(BaseModel):
    items: list[ShopItemResponse] = Field(description="생성된 3~4개의 신규 장비/스킬 리스트")


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
            st.session_state.history = st.session_state.history[target_idx - 1 :]
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
            {"name": "녹슨 단검", "damage": 6, "required_str": 5, "price": 36},
            {"name": "초보자의 단검", "damage": 12, "required_str": 10, "price": 72},
        ],
    )

if "armor_shop" not in st.session_state:
    st.session_state.armor_shop = saved_data.get(
        "armor_shop",
        [
            {"name": "낡은 천옷", "defense": 4, "required_con": 5, "price": 28},
            {"name": "여행자 가죽옷", "defense": 8, "required_con": 10, "price": 56},
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
        ],
    )

if "stats" not in st.session_state:
    st.session_state.stats = saved_data.get(
        "stats",
        {
            "hp": 70, "max_hp": 70, "mp": 35, "max_mp": 35, "gold": 10,
            "level": 1, "exp": 0, "max_exp": 100,
            "str": 5, "agi": 5, "con": 5, "int": 5,
            "stat_points": 0, "skill_points": 0,
            "hp_potions": {100: 0}, "mp_potions": {100: 0},
            "equipped_weapon": st.session_state.weapon_shop[0],
            "equipped_armor": st.session_state.armor_shop[0],
            "inventory_weapons": [st.session_state.weapon_shop[0]],
            "inventory_armors": [st.session_state.armor_shop[0]],
            "learned_magic": [], "learned_skills": [],
            "active_quest": None,
        },
    )

if "history" not in st.session_state:
    st.session_state.history = saved_data.get("history", [])
    if not st.session_state.history:
        st.session_state.history.append({
            "role": "assistant",
            "narrative": "중간계의 평화로운 샤이어에서 모험이 시작됩니다. 어둠의 그림자가 서서히 드리우고 있습니다.",
            "choices": ["주변을 탐색한다", "안전한 곳으로 이동한다"],
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


# 🤖 [상점 리뉴얼 요청 (AI 호출)]
def renew_shop_via_ai(api_key, model_id, player_stats):
    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
        플레이어의 현재 스탯:
        - 힘(str): {player_stats['str']} (무기 요구치와 연관)
        - 체력(con): {player_stats['con']} (방어구 요구치와 연관)
        - 최대마나(mp): {player_stats['max_mp']} (마법/스킬 소모량과 연관)

        위 스탯을 바탕으로 플레이어가 **즉시 장착하거나 사용할 수 있는** 수준의 새로운 무기, 방어구, 마법, 기술을 총 3~4개 무작위로 생성해주세요.
        주의: 요구 스탯(required_stat)은 1 이상이며, **반드시 플레이어의 현재 스탯 이하**로 설정해야 플레이어가 바로 구매하여 장착할 수 있습니다.
        """
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ShopRenewalResponse,
                temperature=0.8,
            ),
        )
        data = ShopRenewalResponse.model_validate_json(response.text)
        
        added_count = 0
        for item in data.items:
            t = item.item_type.lower()
            req = max(1, item.required_stat)
            name = item.name.strip()
            
            if t == "weapon":
                damage = max(5, int(req * 1.5))
                st.session_state.weapon_shop.append({"name": name, "damage": damage, "required_str": req, "price": damage * 6})
                added_count += 1
            elif t == "armor":
                defense = max(3, int(req * 1.0))
                st.session_state.armor_shop.append({"name": name, "defense": defense, "required_con": req, "price": defense * 7})
                added_count += 1
            elif t == "magic":
                damage = max(15, int(req * 2.0))
                st.session_state.magic_guild.append({"name": name, "damage": damage, "mp_cost": req, "price": damage * 20})
                added_count += 1
            elif t == "skill":
                damage = max(10, int(req * 1.5))
                st.session_state.combat_dojo.append({"name": name, "damage": damage, "mp_cost": req})
                added_count += 1
        
        if added_count > 0:
            save_game()
            st.toast("✨ 플레이어 스탯에 맞춘 신규 장비와 스킬이 마을에 입고되었습니다!", icon="🎉")
    except Exception as e:
        st.toast("상점 리뉴얼에 실패했습니다. API 키나 네트워크를 확인해주세요.", icon="❌")


# ⚙️ [좌측 메뉴 및 설정]
st.sidebar.header("⚙️ 게임 설정 및 메뉴")

api_key_input = DEFAULT_API_KEY
selected_model = "gemini-3.1-flash-lite"

with st.sidebar.expander("🔑 AI 모델 및 클라우드 세이브", expanded=True):
    api_key_input = st.text_input("Google Gemini API 키", value=DEFAULT_API_KEY, type="password")
    st.markdown("---")
    if st.button("🔄 게임 데이터 초기화", use_container_width=True):
        if os.path.exists(SAVE_FILE):
            os.remove(SAVE_FILE)
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    st.markdown("---")
    save_game()
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            save_data_str = f.read()
        st.download_button(label="📥 세이브 파일 백업", data=save_data_str, file_name="rpg_save_v8.json", mime="application/json", use_container_width=True)

stats = st.session_state.stats

with st.sidebar.expander("🏘️ 마을 시설 방문 (장비/포션 구매)", expanded=True):
    tab_shop, tab_potion, tab_inn, tab_quest, tab_dojo, tab_magic = st.tabs([
        "⚔️대장간", "🧪포션", "🏨여관", "📜의뢰", "🥋훈련", "🔮마법"
    ])
    with tab_shop:
        for i, w in enumerate(st.session_state.weapon_shop):
            if st.button(f"무기: {w['name']} ({w['price']}G)", key=f"w_{i}"):
                if stats["gold"] >= w["price"] and stats["str"] >= w["required_str"]:
                    stats["gold"] -= w["price"]
                    if w not in stats["inventory_weapons"]:
                        stats["inventory_weapons"].append(w)
                    stats["equipped_weapon"] = w
                    save_game()
                    st.rerun()
        st.markdown("---")
        for i, a in enumerate(st.session_state.armor_shop):
            if st.button(f"방어구: {a['name']} ({a['price']}G)", key=f"a_{i}"):
                if stats["gold"] >= a["price"] and stats["con"] >= a["required_con"]:
                    stats["gold"] -= a["price"]
                    if a not in stats["inventory_armors"]:
                        stats["inventory_armors"].append(a)
                    stats["equipped_armor"] = a
                    save_game()
                    st.rerun()
    with tab_potion:
        if st.button("체력 포션 구매 (50G)"):
            if stats["gold"] >= 50:
                stats["gold"] -= 50
                stats["hp_potions"][50] = stats["hp_potions"].get(50, 0) + 1
                st.rerun()
        if st.button("마나 포션 구매 (50G)"):
            if stats["gold"] >= 50:
                stats["gold"] -= 50
                stats["mp_potions"][50] = stats["mp_potions"].get(50, 0) + 1
                st.rerun()
    with tab_inn:
        if st.button("숙박하기 (30G)"):
            if stats["gold"] >= 30:
                stats["gold"] -= 30
                stats["hp"], stats["mp"] = stats["max_hp"], stats["max_mp"]
                st.rerun()
    with tab_quest:
        if stats["active_quest"] and st.button("의뢰 포기하기"):
            stats["active_quest"] = None
            st.rerun()
        elif not stats["active_quest"]:
            for q in st.session_state.quest_board:
                if st.button(f"수주: {q['title']}"):
                    stats["active_quest"] = q
                    st.rerun()
    with tab_dojo:
        for i, sk in enumerate(st.session_state.combat_dojo):
            if sk not in stats["learned_skills"] and st.button(f"습득: {sk['name']}", key=f"sk_{i}"):
                if stats.get("skill_points", 0) > 0:
                    stats["learned_skills"].append(sk)
                    stats["skill_points"] -= 1
                    st.rerun()
    with tab_magic:
        for i, mg in enumerate(st.session_state.magic_guild):
            if mg not in stats["learned_magic"] and st.button(f"연구: {mg['name']}", key=f"mg_{i}"):
                if stats["gold"] >= mg["price"]:
                    stats["gold"] -= mg["price"]
                    stats["learned_magic"].append(mg)
                    st.rerun()


# 🤖 [AI 스토리 전개 턴 생성 함수 (아이템 생성 배제)]
def call_gemini_turn(user_action):
    client = genai.Client(api_key=api_key_input)
    system_instruction = (
        "당신은 판타지 RPG의 게임 마스터(GM)입니다. '반지의 제왕'의 세계관과 거대한 서사 흐름에만 온전히 집중하세요.\n"
        "모든 서사(narrative)는 1~2문장으로 간결하게 작성하고, 다음에 플레이어가 취할 행동 2가지를 선택지(choices)로 반드시 제공하세요.\n"
        "🚨 [중요: 아이템 발명 절대 금지] 서사를 전개하는 와중에 플레이어가 새로운 마법, 장비, 기술, 아이템을 발견했다거나 얻었다는 내용을 절대로 생성하지 마세요.\n"
        "전투가 필요한 이벤트라면 start_combat을 True로 설정하고 적의 정보를 지정하세요."
    )
    prompt = (
        f"[플레이어 상태]\n- 레벨: {stats['level']} | HP: {stats['hp']}/{stats['max_hp']} | 활성 퀘스트: {stats['active_quest']['title'] if stats['active_quest'] else '없음'}\n"
        f"최근 대화 기록:\n{json.dumps(st.session_state.history[-4:], ensure_ascii=False)}\n\n"
        f"플레이어의 행동: {user_action}"
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
            if attempt == 2: return None
            time.sleep(1)


def process_user_action(user_action):
    clean_action = str(user_action).strip()

    # 🛡️ 적 조우 상태(pending_enemy) 분기
    if st.session_state.get("pending_enemy"):
        if "싸운다" in clean_action or "1️⃣" in clean_action:
            st.session_state.history.append({"role": "user", "narrative": "싸운다"})
            st.session_state.current_enemy = st.session_state.pending_enemy
            st.session_state.pending_enemy = None
            st.session_state.game_mode = "COMBAT"
            save_game()
            st.rerun()  # COMBAT 모드로 전환하기 위해 한 번만 재실행
            return
        elif "도망" in clean_action or "2️⃣" in clean_action:
            st.session_state.history.append({"role": "user", "narrative": "도망친다"})
            st.session_state.pending_enemy = None
            clean_action = "적에게서 무사히 도망쳤다. 주변을 둘러본다."

    st.session_state.history.append({"role": "user", "narrative": clean_action})

    with st.spinner("중간계의 서사가 전개되는 중..."):
        res = call_gemini_turn(clean_action)
        if res:
            narrative_text = res.narrative
            choices = res.choices[:2] if res.choices and len(res.choices) >= 2 else ["주변을 탐색한다", "휴식을 취한다"]

            if res.start_combat:
                lvl = stats["level"]
                hp_scale, atk_scale, def_scale = 30 + (lvl * 15), 8 + (lvl * 2), 2 + (lvl * 1)
                enemy_name = res.enemy_name or "오르크 전사"
                if stats["active_quest"] and stats["active_quest"]["target_enemy"] in enemy_name:
                    enemy_name = stats["active_quest"]["target_enemy"]

                st.session_state.pending_enemy = {
                    "name": enemy_name, "level": lvl,
                    "hp": int(hp_scale), "max_hp": int(hp_scale),
                    "atk": int(atk_scale), "defense": int(def_scale),
                }
                narrative_text += f"\n\n⚔️ **[적 조우: {enemy_name}]** (HP: {int(hp_scale)}, 공격력: {int(atk_scale)})"
                choices = ["싸운다", "도망친다"]

            st.session_state.history.append({"role": "assistant", "narrative": narrative_text, "choices": choices})
            trim_ai_history()
            save_game()
            st.rerun()


# 🖥️ [메인 화면 UI 영역]
main_col, right_col = st.columns([3, 1])

# [우측 슬라이드 (상태 및 상점 리뉴얼)]
with right_col:
    st.subheader("🛡️ 기본 능력치")
    st.metric(label="⭐ 레벨", value=f"Lv. {stats['level']}")
    st.metric(label="❤️ 체력", value=f"{stats['hp']} / {stats['max_hp']}")
    st.metric(label="💙 마나", value=f"{stats['mp']} / {stats['max_mp']}")
    st.metric(label="💰 골드", value=f"{stats['gold']} G")
    
    st.markdown("---")
    st.write(f"- **힘**: {stats['str']} | **민첩**: {stats['agi']}\n- **체력**: {stats['con']} | **지능**: {stats['int']}")
    
    # 🔄 [상점 리뉴얼 버튼 (스토리에 섞이지 않고 여기서만 장비 획득 유도)]
    st.markdown("---")
    st.subheader("🛒 상점 리뉴얼")
    if st.button("🔄 착용 가능 신규 물품 입고 (AI)", use_container_width=True):
        if not api_key_input:
            st.error("API 키를 입력해주세요.")
        else:
            with st.spinner("상인들이 플레이어의 스탯에 맞춰 새 물품을 구하는 중..."):
                renew_shop_via_ai(api_key_input, selected_model, stats)
            st.rerun()

# [중앙 메인 화면 (전투/스토리 전개)]
with main_col:
    if not api_key_input:
        st.warning("⚠️ 사이드바에 Google Gemini API 키를 입력해 주세요.")
    else:
        # ⚔️ [전투 모드: 단일 루프로 즉시 계산 (로딩 스피너 제거, API 호출 없음)]
        if st.session_state.game_mode == "COMBAT":
            enemy = st.session_state.current_enemy
            
            # 한 번의 런타임 안에서 전투를 모두 연산하고 텍스트 로그로 저장
            combat_log = [f"### ⚔️ {enemy['name']} 와(과)의 전투 결과\n"]
            
            while enemy["hp"] > 0 and stats["hp"] > 0:
                # 1. 플레이어 공격 페이즈
                best_attack_name = "기본 공격"
                max_skill_dmg = -1
                best_skill = None
                
                for sk in stats.get("learned_skills", []):
                    if stats["mp"] >= sk["mp_cost"]:
                        s_dmg = int(sk["damage"] + (stats["str"] * 0.5))
                        if s_dmg > max_skill_dmg:
                            max_skill_dmg, best_skill = s_dmg, sk

                if best_skill:
                    best_attack_name = f"스킬 [{best_skill['name']}]"
                    stats["mp"] -= best_skill["mp_cost"]
                    crit = random.random() < (stats["agi"] * 0.005)
                    mult = 1.5 if crit else 1.0
                    p_dmg = max(1, int((max_skill_dmg - enemy["defense"]) * mult))
                else:
                    base_atk = stats["str"] + stats["equipped_weapon"].get("damage", 0)
                    crit = random.random() < (stats["agi"] * 0.005)
                    mult = 1.5 if crit else 1.0
                    p_dmg = max(1, int((base_atk - enemy["defense"]) * mult))

                enemy["hp"] -= p_dmg
                crit_str = " **[크리티컬!]**" if crit else ""
                combat_log.append(f"- 🗡️ 플레이어의 {best_attack_name}{crit_str}! 적에게 **{p_dmg}** 데미지 (적 HP: {max(0, enemy['hp'])})")

                if enemy["hp"] <= 0:
                    break

                # 2. 적 반격 페이즈
                total_player_def = stats["equipped_armor"].get("defense", 0) + stats["con"]
                e_dmg = max(1, enemy["atk"] - total_player_def)
                stats["hp"] -= e_dmg
                combat_log.append(f"- 🩸 적의 공격! 플레이어에게 **{e_dmg}** 데미지 (내 HP: {max(0, stats['hp'])})")

            # 3. 전투 종료 판정
            if enemy["hp"] <= 0:
                gold_rew = enemy["level"] * 20
                exp_rew = enemy["level"] * 35
                if stats["active_quest"] and stats["active_quest"]["target_enemy"] in enemy["name"]:
                    gold_rew += stats["active_quest"]["reward_gold"]
                    exp_rew += stats["active_quest"]["reward_exp"]
                    combat_log.append("\n📜 **길드 의뢰 목표 달성!**")
                    stats["active_quest"] = None
                
                stats["gold"] += gold_rew
                leveled = add_exp(exp_rew)
                combat_log.append(f"\n🎉 **전투 승리!** {gold_rew}G 및 {exp_rew}EXP 획득.")
                if leveled:
                    combat_log.append("🌟 **레벨 업! 스탯 포인트 획득!**")
            else:
                combat_log.append("\n💀 **전투 패배...** 의식을 잃고 간신히 목숨만 부지했습니다.")
                stats["hp"] = 15

            # 연산이 끝났으므로 채팅 내역에 전투 결과를 즉시 추가하고 탐색 모드로 복귀
            st.session_state.game_mode = "EXPLORATION"
            st.session_state.current_enemy = None
            
            choices = ["주변을 탐색한다", "안전한 곳으로 이동한다"] if stats["hp"] > 15 else ["서둘러 여관으로 향한다", "포션을 마신다"]
            
            st.session_state.history.append({
                "role": "assistant",
                "narrative": "\n".join(combat_log),
                "choices": choices
            })
            trim_ai_history()
            save_game()
            st.rerun()

        # 🗺️ [탐색/스토리 모드 (채팅 UI 렌더링)]
        else:
            for idx, h in enumerate(st.session_state.history):
                with st.chat_message(h["role"]):
                    st.markdown(h.get("narrative", ""))
                    if h["role"] == "assistant" and idx == len(st.session_state.history) - 1 and h.get("choices"):
                        st.markdown("---")
                        c_btn1, c_btn2 = st.columns(2)
                        choices = h["choices"]
                        if len(choices) >= 1 and c_btn1.button(f"1️⃣ {choices[0]}", key=f"c0_{idx}"):
                            process_user_action(choices[0])
                        if len(choices) >= 2 and c_btn2.button(f"2️⃣ {choices[1]}", key=f"c1_{idx}"):
                            process_user_action(choices[1])

            chat_input = st.chat_input("행동을 입력하거나 위 버튼을 클릭하세요...")
            if chat_input:
                process_user_action(chat_input)
