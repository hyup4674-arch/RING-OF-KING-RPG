import json
import os
import random
import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_save_v4.json"

st.set_page_config(
    page_title="AI 연동 동기화 파이썬 엔진 RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ AI 서사 + 파이썬 철저 밸런스 엔진 RPG")


# 📋 [Pydantic 스키마: AI가 서사, 적 정보, 그리고 새로운 아이템/마법/스킬을 제안 가능]
class GeneratedItem(BaseModel):
    item_type: str = Field(
        default="",
        description="아이템 종류: 'weapon', 'armor', 'magic', 'skill' 중 하나 (새로운 것이 없다면 빈 문자열)",
    )
    name: str = Field(default="", description="아이템, 마법 또는 스킬의 이름")
    required_stat: int = Field(
        default=10,
        description="무기면 필요힘, 방어구면 필요체력, 마법/스킬이면 소모MP (정수)",
    )


class GameResponse(BaseModel):
    narrative: str = Field(
        description="플레이어의 행동에 따른 상세하고 몰입감 넘치는 스토리 서사 묘사."
    )
    start_combat: bool = Field(
        default=False, description="적과의 조우가 발생하면 True"
    )
    enemy_name: str = Field(
        default="", description="조우한 적의 이름 (예: 숲속의 고블린 도적)"
    )
    enemy_archetype: str = Field(
        default="beast",
        description="적의 유형 (beast, bandit, undead, mage 중 택1)",
    )
    new_item: GeneratedItem = Field(
        default=None,
        description="탐험 중 발견하여 상점/훈련소/길드에 추가될 새로운 아이템/마법/스킬 제안",
    )


# 💾 [세이브 및 로드 관리]
def save_game():
    data = {
        "stats": st.session_state.get("stats", {}),
        "history": st.session_state.get("history", []),
        "game_mode": st.session_state.get("game_mode", "EXPLORATION"),
        "current_enemy": st.session_state.get("current_enemy", None),
        "weapon_shop": st.session_state.get("weapon_shop", []),
        "armor_shop": st.session_state.get("armor_shop", []),
        "magic_guild": st.session_state.get("magic_guild", []),
        "combat_dojo": st.session_state.get("combat_dojo", []),
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# 📊 [상태 초기화]
saved_data = {}
if os.path.exists(SAVE_FILE):
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as f:
            content = json.load(f)
            if isinstance(content, dict):
                saved_data = content
    except Exception:
        pass

# 상점 및 시설 데이터베이스를 session_state로 관리하여 AI가 추가한 항목이 유지되도록 함
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

if "stats" not in st.session_state:
    st.session_state.stats = saved_data.get(
        "stats",
        {
            "hp": 100,
            "max_hp": 100,
            "mp": 50,
            "max_mp": 50,
            "gold": 200,
            "level": 1,
            "exp": 0,
            "max_exp": 100,
            "str": 10,
            "agi": 10,
            "con": 10,
            "int": 10,
            "stat_points": 10,
            "skill_points": 0,
            "equipped_weapon": st.session_state.weapon_shop[0],
            "equipped_armor": st.session_state.armor_shop[0],
            "inventory_weapons": [st.session_state.weapon_shop[0]],
            "inventory_armors": [st.session_state.armor_shop[0]],
            "learned_magic": [],
            "learned_skills": [],
        },
    )

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
        player["max_exp"] = int(player["max_exp"] * 1.4)
        player["stat_points"] += 10
        player["skill_points"] += 1
        player["max_hp"] += 20
        player["hp"] = player["max_hp"]
        player["max_mp"] += 15
        player["mp"] = player["max_mp"]
        leveled_up = True
    return leveled_up


# ⚙️ [사이드바 상태창 및 마을 시설]
st.sidebar.header("⚙️ 캐릭터 상태 및 마을 시설")
api_key_input = st.sidebar.text_input(
    "Google Gemini API 키", value=DEFAULT_API_KEY, type="password"
)
selected_model = st.sidebar.selectbox(
    "Gemini 모델",
    options=[
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.5-pro",
    ],
    index=0,
)

stats = st.session_state.stats
st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 능력치 관리")
st.sidebar.metric(label="⭐ 레벨", value=f"Lv. {stats['level']}")
st.sidebar.metric(
    label="✨ 경험치", value=f"{stats['exp']} / {stats['max_exp']}"
)
st.sidebar.metric(label="❤️ 체력", value=f"{stats['hp']} / {stats['max_hp']}")
st.sidebar.metric(label="💙 마나", value=f"{stats['mp']} / {stats['max_mp']}")
st.sidebar.metric(label="💰 골드", value=f"{stats['gold']} G")

st.sidebar.write(
    f"- 힘: {stats['str']} | 민첩: {stats['agi']} | 체력: {stats['con']} | 지능: {stats['int']}"
)

# 스탯 분배 UI
if stats.get("stat_points", 0) > 0:
    st.sidebar.success(f"잔여 스탯 포인트: {stats['stat_points']} P")
    col1, col2 = st.sidebar.columns(2)
    if col1.button("💪 힘+1"):
        stats["str"] += 1
        stats["stat_points"] -= 1
        save_game()
        st.rerun()
    if col2.button("⚡ 민첩+1"):
        stats["agi"] += 1
        stats["stat_points"] -= 1
        save_game()
        st.rerun()
    col3, col4 = st.sidebar.columns(2)
    if col3.button("❤️ 체력+1"):
        stats["con"] += 1
        stats["max_hp"] += 3
        stats["hp"] = stats["max_hp"]
        stats["stat_points"] -= 1
        save_game()
        st.rerun()
    if col4.button("🧠 지능+1"):
        stats["int"] += 1
        stats["max_mp"] += 2
        stats["mp"] = stats["max_mp"]
        stats["stat_points"] -= 1
        save_game()
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🏘️ 마을 시설 방문 (상점/길드)")
tab_shop, tab_dojo, tab_magic = st.sidebar.tabs(
    ["⚔️ 대장간", "🥋 전투훈련소", "🔮 마법길드"]
)

with tab_shop:
    st.write("모험 중 발견되거나 상점에 입고된 장비들입니다.")
    st.markdown("**[무기 상점]**")
    for w in st.session_state.weapon_shop:
        if st.button(
            f"구매: {w['name']} (공격력:{w['damage']}, 필요힘:{w['required_str']}, {w['price']}G)",
            key=f"w_{w['name']}",
        ):
            if stats["gold"] >= w["price"]:
                if stats["str"] >= w["required_str"]:
                    stats["gold"] -= w["price"]
                    if w not in stats["inventory_weapons"]:
                        stats["inventory_weapons"].append(w)
                    stats["equipped_weapon"] = w
                    st.success(f"{w['name']} 장착 완료!")
                    save_game()
                    st.rerun()
                else:
                    st.error("힘이 부족합니다!")
            else:
                st.error("골드가 부족합니다!")

    st.markdown("**[방어구 상점]**")
    for a in st.session_state.armor_shop:
        if st.button(
            f"구매: {a['name']} (방어력:{a['defense']}, 필요체력:{a['required_con']}, {a['price']}G)",
            key=f"a_{a['name']}",
        ):
            if stats["gold"] >= a["price"]:
                if stats["con"] >= a["required_con"]:
                    stats["gold"] -= a["price"]
                    if a not in stats["inventory_armors"]:
                        stats["inventory_armors"].append(a)
                    stats["equipped_armor"] = a
                    st.success(f"{a['name']} 장착 완료!")
                    save_game()
                    st.rerun()
                else:
                    st.error("체력이 부족합니다!")
            else:
                st.error("골드가 부족합니다!")

with tab_dojo:
    st.write("스킬 포인트를 소비해 전투 스킬을 배웁니다.")
    if stats.get("skill_points", 0) > 0:
        st.info(f"사용 가능한 스킬 포인트: {stats['skill_points']} P")
        for sk in st.session_state.combat_dojo:
            if sk not in stats["learned_skills"]:
                if st.button(
                    f"습득: {sk['name']} (위력:{sk['damage']}, MP:{sk['mp_cost']})",
                    key=f"sk_{sk['name']}",
                ):
                    stats["learned_skills"].append(sk)
                    stats["skill_points"] -= 1
                    st.success(f"{sk['name']} 습득 완료!")
                    save_game()
                    st.rerun()
    else:
        st.write("레벨업을 통해 스킬 포인트를 획득하세요.")
    st.write("현재 습득한 스킬:")
    for sk in stats["learned_skills"]:
        st.write(f"- {sk['name']} (위력: {sk['damage']}, 소모MP: {sk['mp_cost']})")

with tab_magic:
    st.write("골드를 지불하고 마법을 연구합니다.")
    for mg in st.session_state.magic_guild:
        if mg not in stats["learned_magic"]:
            if st.button(
                f"연구: {mg['name']} (데미지:{mg['damage']}, MP:{mg['mp_cost']}, {mg['price']}G)",
                key=f"mg_{mg['name']}",
            ):
                if stats["gold"] >= mg["price"]:
                    stats["gold"] -= mg["price"]
                    stats["learned_magic"].append(mg)
                    st.success(f"{mg['name']} 마법 습득 완료!")
                    save_game()
                    st.rerun()
                else:
                    st.error("골드가 부족합니다!")
    st.write("현재 습득한 마법:")
    for mg in stats["learned_magic"]:
        st.write(
            f"- {mg['name']} (데미지: {mg['damage']}, 소모MP: {mg['mp_cost']})"
        )


# 🤖 [AI 호출 함수]
def call_gemini_turn(user_action):
    client = genai.Client(api_key=api_key_input)
    system_instruction = (
        "당신은 판타지 RPG의 게임 마스터(GM)입니다.\n"
        "플레이어의 탐험 행동에 따른 흥미진진한 서사를 묘사하세요.\n"
        "전투가 필요하면 start_combat을 True로 설정하고 적 정보와 유형(beast, bandit, undead, mage)을 지정하세요.\n"
        "모험 도중 특별한 보물이나 유물, 전설적인 무기/방어구/마법/스킬을 발견하게 된다면 `new_item` 필드를 통해 새롭게 추가할 장비나 마법 정보를 제안해주세요. (요구 스탯이나 소모 MP는 레벨에 맞게 적절히 지정하세요.)"
    )
    prompt = (
        f"[플레이어 상태]\n"
        f"- 레벨: {stats['level']} | HP: {stats['hp']}/{stats['max_hp']} | MP: {stats['mp']}/{stats['max_mp']}\n"
        f"- 장비: 무기({stats['equipped_weapon']['name']}), 방어구({stats['equipped_armor']['name']})\n\n"
        f"최근 대화 기록:\n"
        + json.dumps(st.session_state.history[-4:], ensure_ascii=False)
        + f"\n\n플레이어의 행동: {user_action}"
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
        return GameResponse.model_validate_json(response.text)
    except Exception as e:
        st.error(f"Gemini API 오류: {e}")
        return None


# 🎮 [메인 화면 분기: 탐험 vs 전투]
if not api_key_input:
    st.warning("⚠️ 사이드바에 Google Gemini API 키를 입력해 주세요.")
else:
    # 전투 모드 (파이썬 엔진 처리)
    if st.session_state.game_mode == "COMBAT":
        enemy = st.session_state.current_enemy
        st.error(f"🚨 **[전투 발생] 야생의 {enemy['name']}이(가) 나타났다!**")

        c_hp1, c_hp2 = st.columns(2)
        c_hp1.metric("내 HP", f"{stats['hp']} / {stats['max_hp']}")
        c_hp2.metric(
            f"적 HP ({enemy['name']})", f"{enemy['hp']} / {enemy['max_hp']}"
        )

        b_col1, b_col2, b_col3 = st.columns(3)

        # 1. 기본 공격
        if b_col1.button("🗡️ 기본 공격", use_container_width=True):
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
                stats["gold"] += gold_rew
                leveled = add_exp(exp_rew)
                st.session_state.game_mode = "EXPLORATION"
                st.session_state.current_enemy = None
                log += f"\n🎉 승리! (보상: {gold_rew}G, {exp_rew} EXP){' [레벨 업!]' if leveled else ''}"
                st.session_state.history.append(
                    {"role": "assistant", "narrative": log}
                )
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
                st.session_state.history.append(
                    {"role": "assistant", "narrative": log}
                )
            save_game()
            st.rerun()

        # 2. 스킬 사용
        if stats["learned_skills"] and b_col2.button(
            "⚡ 스킬 사용", use_container_width=True
        ):
            st.write("사용할 스킬을 선택하세요:")
            for sk in stats["learned_skills"]:
                if st.button(
                    f"{sk['name']} (소모MP: {sk['mp_cost']})",
                    key=f"use_sk_{sk['name']}",
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
                        st.session_state.history.append(
                            {"role": "assistant", "narrative": log}
                        )
                        save_game()
                        st.rerun()
                    else:
                        st.error("마나가 부족합니다!")

        # 3. 마법 사용
        if stats["learned_magic"] and b_col3.button(
            "🔮 마법 사용", use_container_width=True
        ):
            for mg in stats["learned_magic"]:
                if st.button(
                    f"{mg['name']} (소모MP: {mg['mp_cost']})",
                    key=f"use_mg_{mg['name']}",
                ):
                    if stats["mp"] >= mg["mp_cost"]:
                        stats["mp"] -= mg["mp_cost"]
                        mag_dmg = (stats["int"] * 1.5) + mg["damage"]
                        enemy["hp"] -= int(mag_dmg)
                        log = f"마법 [{mg['name']}] 시전! {int(mag_dmg)}의 마법 피해."

                        if enemy["hp"] <= 0:
                            gold_rew = enemy["level"] * 30
                            exp_rew = enemy["level"] * 50
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
                        st.session_state.history.append(
                            {"role": "assistant", "narrative": log}
                        )
                        save_game()
                        st.rerun()
                    else:
                        st.error("마나가 부족합니다!")

        if st.session_state.history:
            st.info(st.session_state.history[-1].get("narrative", ""))

    # 탐험 모드 (AI 서사 + 파이썬 규칙 기반 동적 아이템 추가 엔진)
    else:
        for h in st.session_state.history:
            with st.chat_message(h["role"]):
                st.markdown(h.get("narrative", ""))

        chat_input = st.chat_input("원하는 행동을 입력하세요... (예: 숲으로 이동한다)")

        if chat_input:
            st.session_state.history.append(
                {"role": "user", "narrative": chat_input}
            )
            with st.chat_message("user"):
                st.markdown(chat_input)

            with st.spinner("게임 마스터가 서사를 전개하는 중..."):
                res = call_gemini_turn(chat_input)

                if res:
                    narrative_text = res.narrative

                    # 💡 [핵심] AI가 새로운 아이템/마법을 제안한 경우, 파이썬이 공식을 적용하여 상점에 강제 추가
                    if (
                        res.new_item
                        and res.new_item.name
                        and res.new_item.item_type
                    ):
                        item = res.new_item
                        t = item.item_type.lower()
                        req = item.required_stat
                        name = item.name

                        if t == "weapon":
                            # 무기 데미지 공식 = 필요힘 * 1.3
                            damage = int(req * 1.3)
                            price = req * 20
                            new_entry = {
                                "name": name,
                                "damage": damage,
                                "required_str": req,
                                "price": price,
                            }
                            if (
                                new_entry
                                not in st.session_state.weapon_shop
                            ):
                                st.session_state.weapon_shop.append(new_entry)
                                narrative_text += f"\n\n✨ **[발견]** 새로운 무기 [{name}]이(가) 대장간에 입고되었습니다!"

                        elif t == "armor":
                            # 방어구 방어력 공식 = 필요체력 * 1.3
                            defense = int(req * 1.3)
                            price = req * 20
                            new_entry = {
                                "name": name,
                                "defense": defense,
                                "required_con": req,
                                "price": price,
                            }
                            if (
                                new_entry
                                not in st.session_state.armor_shop
                            ):
                                st.session_state.armor_shop.append(new_entry)
                                narrative_text += f"\n\n✨ **[발견]** 새로운 방어구 [{name}]이(가) 대장간에 입고되었습니다!"

                        elif t == "magic":
                            # 마법 데미지 공식 = 소모마나 * 2
                            damage = int(req * 2.0)
                            price = req * 25
                            new_entry = {
                                "name": name,
                                "damage": damage,
                                "mp_cost": req,
                                "price": price,
                            }
                            if (
                                new_entry
                                not in st.session_state.magic_guild
                            ):
                                st.session_state.magic_guild.append(new_entry)
                                narrative_text += f"\n\n🔮 **[발견]** 새로운 마법 [{name}]이(가) 마법길드에 연구되었습니다!"

                        elif t == "skill":
                            # 스킬 데미지 공식 = 소모마나 * 1.5
                            damage = int(req * 1.5)
                            price = req * 25
                            new_entry = {
                                "name": name,
                                "damage": damage,
                                "mp_cost": req,
                                "price": price,
                            }
                            if (
                                new_entry
                                not in st.session_state.combat_dojo
                            ):
                                st.session_state.combat_dojo.append(new_entry)
                                narrative_text += f"\n\n🥋 **[발견]** 새로운 전투 기술 [{name}]이(가) 훈련소에 등록되었습니다!"

                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": narrative_text,
                    })

                    # 전투 트리거 발생 시 파이썬이 레벨에 맞춰 적 능력치 자동 스케일링
                    if res.start_combat:
                        st.session_state.game_mode = "COMBAT"
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

                        st.session_state.current_enemy = {
                            "name": res.enemy_name or "야생의 괴물",
                            "level": lvl,
                            "hp": int(hp_scale),
                            "max_hp": int(hp_scale),
                            "atk": int(atk_scale),
                            "defense": int(def_scale),
                        }

                    if len(st.session_state.history) > 8:
                        st.session_state.history = st.session_state.history[
                            -8:
                        ]

                    save_game()
                    st.rerun()
