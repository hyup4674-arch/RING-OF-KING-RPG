import json
import os
import random
import time
import streamlit as st
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field
from streamlit_autorefresh import st_autorefresh

SAVE_FILE = "rpg_save_v10.json"

st.set_page_config(page_title="RPG Game Engine", page_icon="⚔️", layout="wide")

# ⏱️ 자동 갱신은 전투(COMBAT) 모드에서만 실행! (탐험 중 불필요한 새로고침 및 API 충돌 방지)[cite: 1]
if st.session_state.get("game_mode") == "COMBAT":
    st_autorefresh(interval=1000, limit=None, key="combat_refresh")


# 📋 [Pydantic 스키마]
class GameResponse(BaseModel):
    narrative: str = Field(
        description="상황을 몰입감 있게 설명하는 정확히 4줄 분량의 상세한 스토리 서사 묘사."
    )
    choices: list[str] = Field(
        default=[
            "첫 번째 길로 진행한다",
            "두 번째 길로 진행한다",
            "세 번째 길로 진행한다",
        ],
        description="플레이어가 선택할 수 있는 정확히 3가지 방향 또는 선택지 리스트",
    )
    start_combat: bool = Field(default=False, description="전투 조우 여부")
    enemy_name: str = Field(default="", description="조우한 적의 이름")


# 🛍️ [상점 진열 상품 생성 함수]
def generate_shop_catalog():
    # 1. 무기 20개 진열 (요구 힘 5, 10, 15 ... 100)
    weapon_shop = []
    for i in range(1, 21):
        req = i * 5
        weapon_shop.append({
            "name": f"단계 {i} 유니크 무기",
            "damage": int(req * 1.5),
            "required_str": req,
            "price": req * 15,
        })

    # 2. 방어구 20개 진열 (요구 체력 5, 10, 15 ... 100)
    armor_shop = []
    for i in range(1, 21):
        req = i * 5
        armor_shop.append({
            "name": f"단계 {i} 유니크 방어구",
            "defense": int(req * 1.0),
            "required_con": req,
            "price": req * 15,
        })

    # 3. 마법 20개 진열 (소모 MP 5, 10, 15 ... 100)
    magic_guild = []
    magic_types = ["frost", "fire"]
    for i in range(1, 21):
        mp_cost = i * 5
        m_type = magic_types[i % 2]
        m_name = (
            f"서리 얼음 마법 Lv.{i}"
            if m_type == "frost"
            else f"화염 폭발 마법 Lv.{i}"
        )
        magic_guild.append({
            "name": m_name,
            "damage": int(mp_cost * 2.0),
            "mp_cost": mp_cost,
            "type": m_type,
            "price": mp_cost * 20,
        })

    # 4. 스킬 10개 진열 (소모 MP 5, 10, 15 ... 50)
    combat_dojo = []
    for i in range(1, 11):
        mp_cost = i * 5
        combat_dojo.append({
            "name": f"특수 필살 스킬 Lv.{i}",
            "damage": int(mp_cost * 2.2),
            "mp_cost": mp_cost,
            "price": mp_cost * 25,
        })

    return weapon_shop, armor_shop, magic_guild, combat_dojo


# 🛠️ [캐릭터 초기 상태 생성]
def init_character_stats(job_type):
    weapon_shop, armor_shop, magic_guild, combat_dojo = generate_shop_catalog()

    base_stats = {
        "job": job_type,
        "hp": 100,
        "max_hp": 100,
        "mp": 50,
        "max_mp": 50,
        "gold": 5,  # 5원(골드)으로 시작
        "level": 1,
        "exp": 0,
        "max_exp": 100,
        "stat_points": 0,  # 💡 [추가] 사용 가능한 스탯 포인트
        "str": 10,
        "agi": 10,
        "con": 10,
        "int": 10,
        "equipped_weapon": weapon_shop[0],  # 요구 스탯 5 무기 착용
        "equipped_armor": armor_shop[0],  # 요구 스탯 5 방어구 착용
        "inventory_weapons": [weapon_shop[0]],
        "inventory_armors": [armor_shop[0]],
        "learned_magic": [magic_guild[0]],  # 요구 MP 5 마법 1개 기본 습득
        "learned_skills": [combat_dojo[0]],  # 요구 MP 5 스킬 1개 기본 습득
        "weapon_shop": weapon_shop,
        "armor_shop": armor_shop,
        "magic_guild": magic_guild,
        "combat_dojo": combat_dojo,
        "last_regen_time": time.time(),
    }

    if job_type == "전사":
        base_stats["equipped_shield"] = True
    elif job_type == "궁수":
        base_stats["evasion_rate"] = 0.20

    return base_stats


# 📈 [레벨업 체크 함수]
def check_level_up(player):
    leveled_up = False
    level_logs = []
    while player["exp"] >= player["max_exp"]:
        player["exp"] -= player["max_exp"]
        player["level"] += 1
        player["max_exp"] = int(player["max_exp"] * 1.5)
        player["stat_points"] = player.get("stat_points", 0) + 3  # 스탯 포인트 3증가
        leveled_up = True
        level_logs.append(
            f"🎉 레벨 업! Lv.{player['level']} 달성! (스탯 포인트 +3 획득)"
        )
    return leveled_up, level_logs


# 💾 [세이브/로드]
def save_game():
    data = {
        "stats": st.session_state.get("stats", {}),
        "history": st.session_state.get("history", []),
        "game_mode": st.session_state.get("game_mode", "EXPLORATION"),
        "current_enemy": st.session_state.get("current_enemy", None),
    }
    with open(SAVE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


# 🕹️ [직업 선택 모드 체크]
if "stats" not in st.session_state:
    st.session_state.game_mode = "CLASS_SELECT"

# ⏱️ [3초 마다 HP/MP 1 회복 로직]
if "stats" in st.session_state and st.session_state.stats:
    now = time.time()
    last_regen = st.session_state.stats.get("last_regen_time", now)
    if now - last_regen >= 3.0:
        regen_ticks = int((now - last_regen) // 3)
        st.session_state.stats["hp"] = min(
            st.session_state.stats["max_hp"],
            st.session_state.stats["hp"] + regen_ticks,
        )
        st.session_state.stats["mp"] = min(
            st.session_state.stats["max_mp"],
            st.session_state.stats["mp"] + regen_ticks,
        )
        st.session_state.stats["last_regen_time"] = now


# 🤖 [AI 호출 함수 - 유효성 및 네트워크/할당량 예외 처리 추가]
def call_gemini_turn(user_action):
    api_key = st.session_state.get("api_key", "")
    selected_model = st.session_state.get(
        "selected_model", "gemini-3.1-flash-lite"
    )

    if not api_key:
        st.error(
            "🔑 API Key가 입력되지 않았습니다! 사이드바에서 Gemini API Key를"
            " 입력해주세요."
        )
        return None

    try:
        client = genai.Client(api_key=api_key)
        system_instruction = (
            "당신은 판타지 RPG의 게임 마스터(GM)입니다.\n"
            "1. 모험 서사(narrative)는 반드시 줄바꿈을 포함하여 정확히 4줄로 몰입감 있게 서술하세요.\n"
            "2. 플레이어가 탐험/선택을 진행할 때 항상 3가지 방향 또는 선택지(choices)를 제시해야 합니다.\n"
            "3. 전투가 발생하면 start_combat을 True로 하고 적 이름을 제공하세요."
        )

        prompt = f"플레이어의 선택 및 행동: {user_action}"

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

    except APIError as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            st.error(
                "🚨 API 할당량(Quota) 초과 오류: 사용 한도를 초과했습니다."
                " 잠시 후 다시 시도해보세요."
            )
        elif "INVALID_ARGUMENT" in str(e) or "API_KEY_INVALID" in str(e):
            st.error(
                "🔑 API Key 유효성 오류: 입력하신 API Key가 올바르지 않습니다."
            )
        else:
            st.error(f"🌐 API 통신 에러 발생: {e}")
        return None
    except Exception as e:
        st.error(f"⚠️ 시스템 오류가 발생했습니다: {e}")
        return None


# ⚔️ [자동 전투 루프]
def process_auto_combat():
    player = st.session_state.stats
    enemy = st.session_state.current_enemy

    if not enemy or enemy["hp"] <= 0 or player["hp"] <= 0:
        return

    combat_log = []

    usable_magics = [
        m for m in player["learned_magic"] if m["mp_cost"] <= player["mp"]
    ]
    usable_skills = [
        s for s in player["learned_skills"] if s["mp_cost"] <= player["mp"]
    ]

    best_action = None
    max_dmg = player["str"] + player["equipped_weapon"]["damage"]

    for m in usable_magics:
        if m["damage"] > max_dmg:
            max_dmg = m["damage"]
            best_action = ("magic", m)

    for s in usable_skills:
        if s["damage"] > max_dmg:
            max_dmg = s["damage"]
            best_action = ("skill", s)

    if best_action and best_action[0] == "magic":
        mg = best_action[1]
        player["mp"] -= mg["mp_cost"]
        dmg = mg["damage"]

        if enemy.get("burn_status", False):
            dmg = int(dmg * 1.2)
            combat_log.append("🔥 화상 상태 적에게 20% 추가 데미지!")

        if mg.get("type") == "frost":
            enemy["frozen_turns"] = 1
            combat_log.append(
                f"❄️ 냉기 마법 [{mg['name']}] 시전! 적이 동결 상태가 됩니다."
            )
        elif mg.get("type") == "fire":
            enemy["burn_status"] = True
            combat_log.append(
                f"🔥 불 마법 [{mg['name']}] 시전! 적이 화상 상태가 됩니다."
            )

        enemy["hp"] -= dmg
        combat_log.append(
            f"🔮 마법 [{mg['name']}] 시전! {dmg}의 데미지를 입혔습니다."
        )

    elif best_action and best_action[0] == "skill":
        sk = best_action[1]
        player["mp"] -= sk["mp_cost"]
        dmg = sk["damage"]
        if enemy.get("burn_status", False):
            dmg = int(dmg * 1.2)
            combat_log.append("🔥 화상 상태 적에게 20% 추가 데미지!")
        enemy["hp"] -= dmg
        combat_log.append(
            f"⚡ 스킬 [{sk['name']}] 발동! {dmg}의 데미지를 입혔습니다."
        )

    else:
        dmg = max_dmg
        if enemy.get("burn_status", False):
            dmg = int(dmg * 1.2)
            combat_log.append("🔥 화상 상태 적에게 20% 추가 데미지!")
        enemy["hp"] -= dmg
        combat_log.append(f"🗡️ 기본 공격으로 {dmg}의 데미지를 입혔습니다.")

    if enemy["hp"] <= 0:
        player["gold"] += 150
        player["exp"] += 60
        combat_log.append("🎉 적을 무찔렀습니다! (보상: 150G, 60 EXP)")

        # 📈 레벨업 체크 실행
        _, level_logs = check_level_up(player)
        for l_log in level_logs:
            combat_log.append(l_log)

        st.session_state.game_mode = "EXPLORATION"
        st.session_state.current_enemy = None
        st.session_state.history.append({
            "role": "assistant",
            "narrative": "\n".join(combat_log),
            "choices": [
                "첫 번째 방향으로 계속 탐험한다",
                "두 번째 방향으로 진행한다",
                "세 번째 방향으로 진행한다",
            ],
        })
        save_game()
        return

    if enemy.get("frozen_turns", 0) > 0:
        enemy["frozen_turns"] -= 1
        if random.random() < 0.30:
            combat_log.append(
                "❄️ 적의 몸이 얼어붙어 다음 1턴 동안 근접 공격이 빗나갔습니다!"
            )
            st.session_state.combat_log = combat_log
            return

    e_dmg = enemy["atk"]
    if player["job"] == "전사" and random.random() < 0.20:
        combat_log.append(
            "🛡️ [전사 패시브] 방패 블럭 성공! 적의 공격을 완벽히 막았습니다."
        )
        e_dmg = 0
    elif player["job"] == "궁수" and random.random() < 0.20:
        combat_log.append(
            "🏹 [궁수 패시브] 재빠른 회피 성공! 피해를 입지 않았습니다."
        )
        e_dmg = 0

    if e_dmg > 0:
        actual_dmg = max(1, e_dmg - (player["equipped_armor"]["defense"] // 2))
        player["hp"] = max(0, player["hp"] - actual_dmg)
        combat_log.append(f"💥 적의 공격으로 {actual_dmg}의 피해를 입었습니다.")

    if player["hp"] <= 0:
        player["hp"] = 20
        st.session_state.game_mode = "EXPLORATION"
        st.session_state.current_enemy = None
        combat_log.append("💀 전투에서 패배하여 부상을 입고 후퇴했습니다.")
        st.session_state.history.append({
            "role": "assistant",
            "narrative": "\n".join(combat_log),
            "choices": [
                "안전한 경로 1로 후퇴한다",
                "안전한 경로 2로 후퇴한다",
                "안전한 경로 3으로 후퇴한다",
            ],
        })

    st.session_state.combat_log = combat_log
    save_game()


# --- 🖥️ UI 및 메인 로직 ---

st.sidebar.title("⚙️ 시스템 설정")

# 1. API Key 입력
st.session_state["api_key"] = st.sidebar.text_input(
    "Gemini API Key", type="password"
)

# 2. Gemini 모델 선택 대화상자 (3.1~3.6 flash-lite)
model_options = [f"gemini-3.{i}-flash-lite" for i in range(1, 7)]
st.session_state["selected_model"] = st.sidebar.selectbox(
    "🤖 Gemini 모델 선택", model_options, index=0
)

# 3. 글자 크기 조절 슬라이더 및 동적 CSS 적용
font_size = st.sidebar.slider("🔤 글자 크기 조절 (px)", 12, 28, 16)
st.markdown(
    f"""
    <style>
        html, body, [class*="css"], p, div, button, span {{
            font-size: {font_size}px !important;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# 1. 캐릭터 생성 (직업 선택)
if st.session_state.game_mode == "CLASS_SELECT":
    st.header("⚔️ 클래스를 선택하여 모험을 시작하세요")
    c1, c2, c3 = st.columns(3)

    if c1.button("🧙‍♂️ 마법사", use_container_width=True):
        st.session_state.stats = init_character_stats("마법사")
        st.session_state.game_mode = "EXPLORATION"
        st.session_state.history = [{
            "role": "assistant",
            "narrative": (
                "신비로운 마력을 품은 마법사로서 모험을 시작합니다.\n앞에"
                " 펼쳐진 세 갈래 길에는 서로 다른 시련이 기다리고 있습니다.\n마법의"
                " 힘으로 던전 깊은 곳의 비밀을 파헤치세요.\n당신은 어느"
                " 방향으로 발걸음을 옮기시겠습니까?"
            ),
            "choices": [
                "왼쪽 어두운 오솔길",
                "중앙의 오래된 석조 문",
                "오른쪽 덤불 숲길",
            ],
        }]
        st.rerun()

    if c2.button("🗡️ 전사", use_container_width=True):
        st.session_state.stats = init_character_stats("전사")
        st.session_state.game_mode = "EXPLORATION"
        st.session_state.history = [{
            "role": "assistant",
            "narrative": (
                "단단한 방패와 검을 든 든든한 전사로서 모험을 시작합니다.\n앞에"
                " 펼쳐진 세 갈래 길에는 서로 다른 시련이 기다리고 있습니다.\n강인한"
                " 체력과 방어력으로 적들을 격파하세요.\n당신은 어느 방향으로"
                " 발걸음을 옮기시겠습니까?"
            ),
            "choices": [
                "왼쪽 어두운 오솔길",
                "중앙의 오래된 석조 문",
                "오른쪽 덤불 숲길",
            ],
        }]
        st.rerun()

    if c3.button("🏹 궁수", use_container_width=True):
        st.session_state.stats = init_character_stats("궁수")
        st.session_state.game_mode = "EXPLORATION"
        st.session_state.history = [{
            "role": "assistant",
            "narrative": (
                "민첩한 움직임과 예리한 눈을 가진 궁수로 모험을 시작합니다.\n앞에"
                " 펼쳐진 세 갈래 길에는 서로 다른 시련이 기다리고 있습니다.\n높은"
                " 회피율로 적의 공격을 날카롭게 피하세요.\n당신은 어느 방향으로"
                " 발걸음을 옮기시겠습니까?"
            ),
            "choices": [
                "왼쪽 어두운 오솔길",
                "중앙의 오래된 석조 문",
                "오른쪽 덤불 숲길",
            ],
        }]
        st.rerun()

else:
    # 🏘️ 사이드바 마을 상점 및 시설
    p = st.session_state.stats

    with st.sidebar.expander("🏘️ 마을 상점 & 길드 방문", expanded=True):
        t_w, t_a, t_m, t_s, t_inn = st.tabs(
            ["🗡️무기", "🛡️방어구", "🔮마법", "🥋스킬", "🏨여관"]
        )

        with t_w:
            st.markdown("**[대장간 무기상점 (20종 진열)]**")
            for idx, w in enumerate(p["weapon_shop"]):
                if st.button(
                    f"구매: {w['name']} (공격:{w['damage']}, 필요힘:{w['required_str']}) - {w['price']}G",
                    key=f"buy_w_{idx}",
                ):
                    if p["gold"] >= w["price"]:
                        if p["str"] >= w["required_str"]:
                            p["gold"] -= w["price"]
                            p["inventory_weapons"].append(w)
                            p["equipped_weapon"] = w
                            st.success(
                                f"[{w['name']}] 구매 및 착용 완료!"
                            )
                            save_game()
                            st.rerun()
                        else:
                            st.error("요구 힘 스탯 부족!")
                    else:
                        st.error("골드 부족!")

        with t_a:
            st.markdown("**[대장간 방어구상점 (20종 진열)]**")
            for idx, a in enumerate(p["armor_shop"]):
                if st.button(
                    f"구매: {a['name']} (방어:{a['defense']}, 필요체력:{a['required_con']}) - {a['price']}G",
                    key=f"buy_a_{idx}",
                ):
                    if p["gold"] >= a["price"]:
                        if p["con"] >= a["required_con"]:
                            p["gold"] -= a["price"]
                            p["inventory_armors"].append(a)
                            p["equipped_armor"] = a
                            st.success(
                                f"[{a['name']}] 구매 및 착용 완료!"
                            )
                            save_game()
                            st.rerun()
                        else:
                            st.error("요구 체력 스탯 부족!")
                    else:
                        st.error("골드 부족!")

        with t_m:
            st.markdown("**[마법 길드 (20종 진열)]**")
            for idx, m in enumerate(p["magic_guild"]):
                is_learned = m in p["learned_magic"]
                btn_label = (
                    f"습득 완료: {m['name']}"
                    if is_learned
                    else f"연구: {m['name']} (위력:{m['damage']}, MP:{m['mp_cost']}) - {m['price']}G"
                )
                if st.button(
                    btn_label, key=f"buy_m_{idx}", disabled=is_learned
                ):
                    if p["gold"] >= m["price"]:
                        p["gold"] -= m["price"]
                        p["learned_magic"].append(m)
                        st.success(f"마법 [{m['name']}] 연구 완료!")
                        save_game()
                        st.rerun()
                    else:
                        st.error("골드 부족!")

        with t_s:
            st.markdown("**[전투 훈련소 (10종 진열)]**")
            for idx, s in enumerate(p["combat_dojo"]):
                is_learned = s in p["learned_skills"]
                btn_label = (
                    f"습득 완료: {s['name']}"
                    if is_learned
                    else f"전수: {s['name']} (위력:{s['damage']}, MP:{s['mp_cost']}) - {s['price']}G"
                )
                if st.button(
                    btn_label, key=f"buy_s_{idx}", disabled=is_learned
                ):
                    if p["gold"] >= s["price"]:
                        p["gold"] -= s["price"]
                        p["learned_skills"].append(s)
                        st.success(f"스킬 [{s['name']}] 전수 완료!")
                        save_game()
                        st.rerun()
                    else:
                        st.error("골드 부족!")

        with t_inn:
            if st.session_state.game_mode == "COMBAT":
                st.error("🚨 전투 중에는 여관에서 휴식할 수 없습니다!")
            else:
                if st.button("🛏️ 휴식하기 (30G - HP/MP 완전 회복)"):
                    if p["gold"] >= 30:
                        p["gold"] -= 30
                        p["hp"] = p["max_hp"]
                        p["mp"] = p["max_mp"]
                        st.success("휴식을 완료했습니다!")
                        save_game()
                        st.rerun()
                    else:
                        st.error("골드가 부족합니다.")

    # 메인 레이아웃
    main_col, side_col = st.columns([3, 1])

    with side_col:
        st.subheader("📊 캐릭터 정보")
        st.write(f"**직업**: {p['job']}")
        st.write(f"📈 **레벨**: {p['level']} (EXP: {p['exp']}/{p['max_exp']})")
        st.metric("❤️ HP", f"{p['hp']} / {p['max_hp']}")
        st.metric("💙 MP", f"{p['mp']} / {p['max_mp']}")
        st.write(f"💰 **골드**: {p['gold']} G")
        st.write(f"⚔️ **착용 무기**: {p['equipped_weapon']['name']}")
        st.write(f"🛡️ **착용 방어구**: {p['equipped_armor']['name']}")

        st.markdown("---")
        st.write("**[능력치 관리]**")
        st.write(f"✨ **사용 가능 스탯 포인트**: {p.get('stat_points', 0)} P")
        
        # 💡 [추가] 3씩 스탯을 올릴 수 있는 분배 UI 버튼
        can_upgrade = p.get('stat_points', 0) >= 3
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.text(f"힘: {p['str']}")
            if st.button("힘 +3", key="inc_str", disabled=not can_upgrade, use_container_width=True):
                p['stat_points'] -= 3
                p['str'] += 3
                save_game()
                st.rerun()
                
            st.text(f"체력: {p['con']}")
            if st.button("체력 +3", key="inc_con", disabled=not can_upgrade, use_container_width=True):
                p['stat_points'] -= 3
                p['con'] += 3
                p['max_hp'] += 15  # 체력 스탯 상승 시 최대 HP도 소폭 증가
                p['hp'] = min(p['max_hp'], p['hp'] + 15)
                save_game()
                st.rerun()
                
        with col_s2:
            st.text(f"민첩: {p['agi']}")
            if st.button("민첩 +3", key="inc_agi", disabled=not can_upgrade, use_container_width=True):
                p['stat_points'] -= 3
                p['agi'] += 3
                save_game()
                st.rerun()
                
            st.text(f"지능: {p['int']}")
            if st.button("지능 +3", key="inc_int", disabled=not can_upgrade, use_container_width=True):
                p['stat_points'] -= 3
                p['int'] += 3
                save_game()
                st.rerun()

        st.markdown("---")
        st.write("**[습득한 마법 목록]**")
        if p["learned_magic"]:
            for m in p["learned_magic"]:
                st.caption(f"- {m['name']} (MP:{m['mp_cost']})")
        else:
            st.caption("습득한 마법이 없습니다.")

        st.write("**[습득한 스킬 목록]**")
        if p["learned_skills"]:
            for s in p["learned_skills"]:
                st.caption(f"- {s['name']} (MP:{s['mp_cost']})")
        else:
            st.caption("습득한 스킬이 없습니다.")

    with main_col:
        # 자동 전투 진행 영역
        if st.session_state.game_mode == "COMBAT":
            st.error("⚔️ [자동 전투 진행 중 (1초 주기)]")
            process_auto_combat()

            enemy = st.session_state.current_enemy
            if enemy:
                st.write(
                    f"👾 **적**: {enemy['name']} (HP: {enemy['hp']} /"
                    f" {enemy['max_hp']})"
                )

            logs = st.session_state.get("combat_log", [])
            for log in logs:
                st.info(log)

        else:
            # 💡 [유지] AI 메시지 출력을 최신 2개까지만 제한 ([-2:])[cite: 1]
            for h in st.session_state.history[-2:]:
                with st.chat_message(h["role"]):
                    st.markdown(h.get("narrative", ""))

            last_turn = st.session_state.history[-1]

            # 💡 [유지] 사용자의 행동을 처리하는 공통 함수 (로딩 스피너 포함)[cite: 1]
            def handle_user_action(action_text, difficulty=None):
                if not st.session_state.get("api_key"):
                    st.error("⚠️ 사이드바에 Gemini API Key를 먼저 입력해주세요!")
                    return

                prompt_text = f"{action_text} (선택한 경로 난이도: {difficulty})" if difficulty else action_text
                
                with st.spinner("AI 게임 마스터가 다음 이야기를 생성하고 있습니다... 🎲"):
                    res = call_gemini_turn(prompt_text)
                
                if res:
                    narrative = res.narrative
                    if difficulty:
                        narrative += f"\n\n[선택한 경로 난이도: {difficulty}]"

                    if res.start_combat:
                        st.session_state.game_mode = "COMBAT"
                        scale = {"하 (쉬움)": 0.7, "중 (보통)": 1.0, "상 (매우 어려움)": 1.5}.get(difficulty, 1.0)
                        st.session_state.current_enemy = {
                            "name": (res.enemy_name or "던전 괴물"),
                            "hp": int(80 * scale),
                            "max_hp": int(80 * scale),
                            "atk": int(15 * scale),
                        }

                    st.session_state.history.append({
                        "role": "assistant",
                        "narrative": narrative,
                        "choices": (
                            res.choices if len(res.choices) == 3 else [
                                "1번 경로로 전진한다",
                                "2번 경로로 전진한다",
                                "3번 경로로 전진한다",
                            ]
                        ),
                    })
                    save_game()
                    st.rerun()

            current_turn = len(st.session_state.history)

            if "choices" in last_turn and last_turn["choices"]:
                st.markdown("---")
                st.write("🧭 **3가지 방향 중 어디로 가시겠습니까?**")
                c1, c2, c3 = st.columns(3)
                choices = last_turn["choices"]

                for idx, col in enumerate([c1, c2, c3]):
                    if idx < len(choices):
                        if col.button(f"방향 {idx+1}: {choices[idx]}", key=f"btn_{current_turn}_{idx}"):
                            difficulties = ["하 (쉬움)", "중 (보통)", "상 (매우 어려움)"]
                            random.shuffle(difficulties)
                            handle_user_action(choices[idx], difficulty=difficulties[idx])
            
            user_input = st.chat_input("원하는 행동을 직접 입력하세요 (예: 횃불을 켜고 조심스럽게 전진한다)")
            if user_input:
                handle_user_action(user_input)
