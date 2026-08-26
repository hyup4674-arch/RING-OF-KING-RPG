import json
import os
import random
import re
import streamlit as st
from google import genai
from google.genai import types

# 🔑 [API 키 입력 설정]
DEFAULT_API_KEY = ""
SAVE_FILE = "rpg_save.json"

st.set_page_config(
    page_title="에델가르드 패권전 - 판타지 RPG", page_icon="⚔️", layout="wide"
)
st.title("⚔️ 에델가르드: 4대 종족 대륙 패권전")
st.markdown(
    "오크, 인간, 엘프, 드워프가 대륙의 영토를 두고 다투는 역사의 소용돌이 속에서"
    " 파이썬 엔진 기반의 안정적인 전투와 AI 서사를 즐겨보세요."
)

# 🎨 [스크롤 튕김 완벽 방지 및 세션 스토리지 위치 복원 JS]
st.markdown(
    """
    <script>
        (function() {
            const pWin = window.parent || window;
            const pDoc = pWin.document;
            const SCROLL_KEY = 'rpg_scroll_pos_lock';

            function getScrollContainer() {
                return pDoc.querySelector('[data-testid="stAppViewContainer"]') || pDoc.querySelector('.main') || pWin;
            }

            const container = getScrollContainer();
            const savePos = function() {
                const pos = (container !== pWin) ? container.scrollTop : (pWin.pageYOffset || pDoc.documentElement.scrollTop);
                pWin.sessionStorage.setItem(SCROLL_KEY, pos);
            };

            if (container !== pWin) {
                container.addEventListener('scroll', savePos, { passive: true });
            } else {
                pWin.addEventListener('scroll', savePos, { passive: true });
            }

            function restoreScroll() {
                const saved = pWin.sessionStorage.getItem(SCROLL_KEY);
                if (saved !== null) {
                    const targetPos = parseInt(saved, 10);
                    const cont = getScrollContainer();
                    if (cont !== pWin) {
                        cont.scrollTop = targetPos;
                    } else {
                        pWin.scrollTo(0, targetPos);
                    }
                }
            }

            pWin.addEventListener('DOMContentLoaded', restoreScroll);
            setTimeout(restoreScroll, 10);
            setTimeout(restoreScroll, 50);
            setTimeout(restoreScroll, 150);
            setTimeout(restoreScroll, 300);
        })();
    </script>
    """,
    unsafe_allow_html=True,
)


# 💾 [세이브 파일 통합 저장 함수]
def save_game():
  data = {
      "stats": st.session_state.get("stats", {}),
      "messages": st.session_state.get("messages", []),
      "game_mode": st.session_state.get("game_mode", "EXPLORATION"),
      "current_enemy": st.session_state.get("current_enemy", None),
  }
  with open(SAVE_FILE, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)


# 🛡️ [장비 자동 장착 및 정화 함수]
def auto_equip_items():
  player = st.session_state.stats
  if "equipment" not in player:
    player["equipment"] = {"무기": "초보자의 무기", "갑옷": "여행자 가죽옷"}
  if "inventory" not in player:
    player["inventory"] = []

  inventory = player["inventory"]
  weapon_keywords = [
      "검",
      "창",
      "활",
      "지팡이",
      "도끼",
      "단검",
      "메이스",
      "완드",
      "무기",
      "블레이드",
      "소드",
      "스태프",
      "대검",
  ]
  armor_keywords = [
      "갑옷",
      "로브",
      "옷",
      "갑주",
      "플레이트",
      "가죽옷",
      "튜닉",
  ]

  new_inventory = []
  for item in inventory:
    is_weapon = any(kw in item for kw in weapon_keywords)
    is_armor = any(kw in item for kw in armor_keywords)

    if is_weapon:
      old_weapon = player["equipment"].get("무기", "초보자의 무기")
      player["equipment"]["무기"] = item
      if old_weapon != "초보자의 무기":
        new_inventory.append(old_weapon)
    elif is_armor:
      old_armor = player["equipment"].get("갑옷", "여행자 가죽옷")
      player["equipment"]["갑옷"] = item
      if old_armor != "여행자 가죽옷":
        new_inventory.append(old_armor)
    else:
      new_inventory.append(item)
  player["inventory"] = new_inventory
  save_game()


# 🧹 [스킬 구조화 및 규격 정화 함수]
def normalize_skills(skills_list):
  normalized = []
  for item in skills_list:
    if isinstance(item, dict):
      normalized.append({
          "name": item.get("name", "기본 공격"),
          "effect": item.get("effect", "기본 기술"),
          "power": item.get("power", 15),
          "mp_cost": item.get("mp_cost", 0),
      })
  return normalized


# 📊 [세이브 데이터 로드 및 초기화]
saved_data = None
loaded_messages = []

if os.path.exists(SAVE_FILE):
  try:
    with open(SAVE_FILE, "r", encoding="utf-8") as f:
      save_content = json.load(f)
      if isinstance(save_content, dict):
        saved_data = save_content
        loaded_messages = save_content.get("messages", [])
  except Exception:
    pass

if "stats" not in st.session_state:
  if saved_data and "stats" in saved_data:
    st.session_state.stats = saved_data["stats"]
  else:
    st.session_state.stats = {
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
        "reputation": {"인간": 0, "엘프": 0, "드워프": 0, "오크": 0},
        "equipment": {"무기": "초보자의 무기", "갑옷": "여행자 가죽옷"},
        "inventory": ["체력 포션 (소)", "체력 포션 (소)", "건포도 빵"],
        "skills": [],
    }

if "messages" not in st.session_state:
  st.session_state.messages = loaded_messages

if "game_mode" not in st.session_state:
  st.session_state.game_mode = (
      saved_data.get("game_mode", "EXPLORATION") if saved_data else "EXPLORATION"
  )

if "current_enemy" not in st.session_state:
  st.session_state.current_enemy = (
      saved_data.get("current_enemy", None) if saved_data else None
  )

# ⚙️ [좌측 사이드바: 게임 설정 및 상태창]
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

available_models = [
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.1-flash",
]
default_index = (
    available_models.index("gemini-3.1-flash-lite")
    if "gemini-3.1-flash-lite" in available_models
    else 0
)

selected_model = st.sidebar.selectbox(
    "Gemini 모델 선택", options=available_models, index=default_index
)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 캐릭터 상태창")
stats = st.session_state.stats

st.sidebar.markdown(
    f"👤 **종족**: `{stats['race']}` | **직업**: `{stats['class_name']}`"
)
st.sidebar.metric(label="⭐ 레벨", value=f"Lv. {stats['level']}")
st.sidebar.metric(
    label="✨ 경험치 (EXP)", value=f"{stats['exp']} / {stats['max_exp']}"
)
st.sidebar.metric(
    label="❤️ 체력 (HP)", value=f"{stats['hp']} / {stats['max_hp']}"
)
st.sidebar.metric(
    label="💙 마나 (MP)", value=f"{stats['mp']} / {stats['max_mp']}"
)
st.sidebar.metric(label="💰 보유 골드", value=f"{stats['gold']} G")

st.sidebar.markdown("##### 📊 능력치")
st.sidebar.write(f"- 💪 **힘**: {stats['str']}")
st.sidebar.write(f"- 🧠 **지능**: {stats['int']}")
st.sidebar.write(f"- ❤️ **체력**: {stats['con']}")
st.sidebar.write(f"- ⚡ **민첩**: {stats['agi']}")

# 스탯 포인트 분배
if stats.get("stat_points", 0) > 0:
  st.sidebar.success(f"🎉 스탯 포인트: {stats['stat_points']} P")
  c1, c2 = st.sidebar.columns(2)
  if c1.button("💪 힘+5"):
    stats["str"] += 5
    stats["stat_points"] -= 5
    save_game()
    st.rerun()
  if c1.button("❤️ 체력+5"):
    stats["con"] += 5
    stats["max_hp"] += 10
    stats["hp"] += 10
    stats["stat_points"] -= 5
    save_game()
    st.rerun()
  if c2.button("🧠 지능+5"):
    stats["int"] += 5
    stats["max_mp"] += 10
    stats["mp"] += 10
    stats["stat_points"] -= 5
    save_game()
    st.rerun()
  if c2.button("⚡ 민첩+5"):
    stats["agi"] += 5
    stats["stat_points"] -= 5
    save_game()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("✨ 보유 스킬")
stats["skills"] = normalize_skills(stats.get("skills", []))
for sk in stats["skills"]:
  st.sidebar.markdown(
      f"🗡️ **{sk['name']}** (위력:{sk['power']}, MP:{sk['mp_cost']})"
  )

# 🛡️ [장착 장비 및 인벤토리 표시 섹션]
st.sidebar.markdown("---")
st.sidebar.subheader("⚔️ 장착 장비")
equipment = stats.get(
    "equipment", {"무기": "초보자의 무기", "갑옷": "여행자 가죽옷"}
)
for slot, gear_name in equipment.items():
  st.sidebar.write(f"- **{slot}**: {gear_name}")

st.sidebar.subheader("🎒 인벤토리")
inventory = stats.get("inventory", [])
if inventory:
  for inv_item in inventory:
    st.sidebar.write(f"- {inv_item}")
else:
  st.sidebar.write("- 텅 비어 있음")

st.sidebar.markdown("---")

# 📁 [세이브 파일 업로드 및 관리 메뉴]
uploaded_file = st.sidebar.file_uploader(
    "📁 저장된 파일(.json) 불러오기", type=["json"]
)
if uploaded_file is not None:
  try:
    loaded_json = json.load(uploaded_file)
    if isinstance(loaded_json, dict) and "stats" in loaded_json:
      st.session_state.stats = loaded_json["stats"]
      st.session_state.messages = loaded_json.get("messages", [])
      st.session_state.game_mode = loaded_json.get("game_mode", "EXPLORATION")
      st.session_state.current_enemy = loaded_json.get("current_enemy", None)
      save_game()
      st.sidebar.success("세이브 파일이 성공적으로 적용되었습니다!")
      st.rerun()
  except Exception as e:
    st.sidebar.error(f"파일 로드 실패: {e}")

if st.sidebar.button("💾 현재 상태 게임 수동 저장"):
  save_game()
  st.sidebar.success("게임이 성공적으로 저장되었습니다!")

if st.sidebar.button("🧹 스토리 기록 초기화 (대화 리셋)"):
  st.session_state.messages = []
  if "chat_session" in st.session_state:
    del st.session_state["chat_session"]
  if "client" in st.session_state:
    del st.session_state["client"]
  st.session_state.game_mode = "EXPLORATION"
  st.session_state.current_enemy = None
  save_game()
  st.success("스토리 기록이 초기화되었습니다!")
  st.rerun()

if st.sidebar.button("🔄 새 게임 시작 (캐릭터 포함 전체 초기화)"):
  if os.path.exists(SAVE_FILE):
    os.remove(SAVE_FILE)
  for key in list(st.session_state.keys()):
    del st.session_state[key]
  st.rerun()


# 🧹 [태그 정화 함수]
def clean_tags(text):
  text = re.sub(r"\[START_COMBAT:\s*(\{.*?\})\s*\]", "", text, flags=re.DOTALL)
  text = re.sub(r"\[CHOICES:\s*(\[.*?\])\s*\]", "", text, flags=re.DOTALL)
  text = re.sub(r"\[ITEM_GAIN:\s*\"(.*?)\"\s*\]", "", text, flags=re.DOTALL)
  return text.strip()


# 📈 [경험치 및 레벨업 함수]
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
  save_game()
  return leveled_up


# ⚔️ [파이썬 완벽 주도형 턴제 전투 로직]
def process_combat_turn(action_type, skill_obj=None):
  player = st.session_state.stats
  enemy = st.session_state.current_enemy

  log_parts = []
  victory = False
  defeat = False

  if action_type == "skill" and skill_obj:
    if player["mp"] < skill_obj["mp_cost"]:
      return "마나가 부족하여 스킬을 사용할 수 없습니다!", False, False
    player["mp"] -= skill_obj["mp_cost"]
    base_pow = skill_obj["power"]

    if skill_obj["name"] == "치유":
      heal = base_pow + (player["int"] // 2)
      player["hp"] = min(player["max_hp"], player["hp"] + heal)
      log_parts.append(
          f"✨ [{skill_obj['name']}] 발동! 체력이 +{heal} 회복되었습니다."
      )
    else:
      dmg = (
          random.randint(base_pow - 3, base_pow + 5)
          + player["str"]
          + (player["int"] // 3)
      )
      enemy["hp"] = max(0, enemy["hp"] - dmg)
      log_parts.append(
          f"✨ [{skill_obj['name']}]로 **{enemy['name']}**에게 {dmg}의 피해를"
          f" 입혔습니다!"
      )

  elif action_type == "item":
    if "체력 포션 (소)" in player["inventory"]:
      player["inventory"].remove("체력 포션 (소)")
      heal = 30
      player["hp"] = min(player["max_hp"], player["hp"] + heal)
      log_parts.append(
          f"🧪 포션을 사용해 체력이 {heal} 회복되었습니다! (현재 HP:"
          f" {player['hp']}/{player['max_hp']})"
      )
    else:
      log_parts.append("인벤토리에 '체력 포션 (소)'가 없습니다!")

  elif action_type == "attack":
    dmg = random.randint(8, 15) + player["str"]
    enemy["hp"] = max(0, enemy["hp"] - dmg)
    log_parts.append(
        f"⚔️ 기본 공격으로 **{enemy['name']}**에게 {dmg}의 피해를 입혔습니다."
    )

  if enemy["hp"] <= 0:
    reward_gold = random.randint(15, 30)
    reward_exp = random.randint(40, 60)
    player["gold"] += reward_gold
    leveled = add_exp(reward_exp)

    log_parts.append(
        f"\n🎉 **[전투 승리!]** 적을 처치했습니다! (보상: {reward_gold}G,"
        f" {reward_exp} EXP)"
    )
    if leveled:
      log_parts.append(
          f"🎊 **[레벨 업!]** Lv.{player['level']} 달성! 스탯 포인트 5P 획득!"
      )
    victory = True
  else:
    evasion = player["agi"] * 1
    if random.randint(1, 100) <= evasion:
      log_parts.append(
          f"💨 민첩한 회피로 **{enemy['name']}**의 공격을 피해냈습니다!"
      )
    else:
      edmg = max(1, random.randint(enemy["atk"] - 2, enemy["atk"] + 3))
      player["hp"] = max(0, player["hp"] - edmg)
      log_parts.append(
          f"💥 **{enemy['name']}**의 반격! {edmg}의 피해를 입었습니다. (내 HP:"
          f" {player['hp']}/{player['max_hp']})"
      )

    if player["hp"] <= 0:
      player["hp"] = 10
      log_parts.append(
          "\n💀 **[전투 패배]** 쓰러졌으나 간신히 목숨을 건져 마을로"
          " 후퇴했습니다."
      )
      defeat = True

  save_game()
  return "\n".join(log_parts), victory, defeat


# 🖥️ [메인 화면 로직]
if not api_key_input:
  st.warning("⚠️ 좌측 사이드바에 Google Gemini API 키를 입력해 주세요.")
else:
  # 1단계: 종족 선택
  if stats["race"] == "미정":
    st.info("🌍 **[캐릭터 생성 - 1단계]** 당신의 **종족**을 선택하세요.")
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
    st.info(f"✨ **[캐릭터 생성 - 2단계]** 종족: **{stats['race']}** | 직업 선택")
    c1, c2, c3, c4, c5 = st.columns(5)
    c_choice = None
    if c1.button("전사"):
      c_choice = "전사"
    if c2.button("마법사"):
      c_choice = "마법사"
    if c3.button("궁수"):
      c_choice = "궁수"
    if c4.button("도적"):
      c_choice = "도적"
    if c5.button("성직자"):
      c_choice = "성직자"

    if c_choice:
      stats["class_name"] = c_choice
      if c_choice == "전사":
        stats["skills"] = [
            {
                "name": "기본 베기",
                "effect": "기본 물리 타격",
                "power": 15,
                "mp_cost": 0,
            },
            {
                "name": "강력한 일격",
                "effect": "강한 물리 강타",
                "power": 30,
                "mp_cost": 8,
            },
        ]
      elif c_choice == "마법사":
        stats["skills"] = [
            {
                "name": "마력 화살",
                "effect": "기본 마법",
                "power": 15,
                "mp_cost": 0,
            },
            {
                "name": "화염구",
                "effect": "화염 마법",
                "power": 35,
                "mp_cost": 12,
            },
        ]
      elif c_choice == "궁수":
        stats["skills"] = [
            {
                "name": "정밀 사격",
                "effect": "원거리 사격",
                "power": 15,
                "mp_cost": 0,
            },
            {
                "name": "연사",
                "effect": "연속 사격",
                "power": 32,
                "mp_cost": 9,
            },
        ]
      elif c_choice == "도적":
        stats["skills"] = [
            {
                "name": "기습",
                "effect": "허점 찌르기",
                "power": 15,
                "mp_cost": 0,
            },
            {
                "name": "독침 베기",
                "effect": "독 단검",
                "power": 33,
                "mp_cost": 10,
            },
        ]
      elif c_choice == "성직자":
        stats["skills"] = [
            {
                "name": "신성한 타격",
                "effect": "신력 공격",
                "power": 15,
                "mp_cost": 0,
            },
            {"name": "치유", "effect": "체력 회복", "power": 35, "mp_cost": 10},
        ]
      save_game()
      st.rerun()

  else:
    # 💬 [챗 세션 및 클라이언트 세션 상태 보존 설정]
    if (
        "client" not in st.session_state
        or "chat_session" not in st.session_state
        or st.session_state.get("current_model") != selected_model
    ):
      st.session_state.client = genai.Client(api_key=api_key_input)
      st.session_state.current_model = selected_model

      # 🚨 [시스템 지시문: 좌측 상태창과 완벽한 동기화 강제 규정]
      sys_inst = (
          "당신은 에델가르드 대륙의 게임 마스터(GM)입니다.\n"
          "플레이어의 탐험, 마을 활동, 상점 거래 등에 대해 서사를 제공합니다.\n\n"
          "🚨 [매우 중요 규칙 - 상태 완벽 동기화]:\n"
          "1. 매 턴 제공되는 '[현재 캐릭터 상태 동기화 정보]'에 포함된 레벨, HP, MP, 골드, 장비, 인벤토리 등 모든 수치는 좌측 상태창과 100% 동일합니다.\n"
          "2. 플레이어의 레벨이나 스탯을 절대 임의로 변경하거나 왜곡해서 서사하지 마세요. (상태창의 레벨과 수치를 절대적인 진실로 따르세요.)\n"
          "3. 플레이어가 아이템을 획득하는 경우 응답에 반드시 [ITEM_GAIN: \"아이템이름\"] 태그를 포함하세요.\n"
          "4. 플레이어가 전투를 유발하는 행동을 하면 응답 끝에 반드시 [START_COMBAT: {\"name\": \"적 이름\", \"hp\": 45, \"atk\": 11}] 태그를 넣어 적을 생성하세요.\n"
          "5. 항상 응답 마지막에 3~4개의 행동 선택지를 [CHOICES: [\"선택지1\", \"선택지2\"]] 형태로 제시하세요."
      )

      api_history = [
          types.Content(
              role=(
                  "model"
                  if m.get("role") == "assistant"
                  else ("user" if m.get("role") == "user" else None)
              ),
              parts=[types.Part.from_text(text=m.get("content", ""))],
          )
          for m in st.session_state.messages
          if m.get("role") in ["user", "assistant"]
      ]

      st.session_state.chat_session = st.session_state.client.chats.create(
          model=selected_model,
          history=api_history if api_history else None,
          config=types.GenerateContentConfig(
              system_instruction=sys_inst, temperature=0.7
          ),
      )

      if not st.session_state.messages:
        init_context = (
            f"[현재 캐릭터 상태 동기화 정보]\n"
            f"- 종족: {stats['race']}\n"
            f"- 직업: {stats['class_name']}\n"
            f"- 레벨: {stats['level']} (경험치: {stats['exp']}/{stats['max_exp']})\n"
            f"- 체력(HP): {stats['hp']}/{stats['max_hp']}\n"
            f"- 마나(MP): {stats['mp']}/{stats['max_mp']}\n"
            f"- 골드: {stats['gold']}G\n"
            f"- 장착 장비: {json.dumps(stats.get('equipment', {}), ensure_ascii=False)}\n"
            f"- 인벤토리: {json.dumps(stats['inventory'], ensure_ascii=False)}\n\n"
            f"플레이어가 {stats['race']} 종족 {stats['class_name']} 직업으로 크로스로드 도시 여관에서 모험을 시작합니다. 서막을 열어주세요."
        )
        init_res = st.session_state.chat_session.send_message(init_context)
        st.session_state.messages.append(
            {"role": "assistant", "content": init_res.text}
        )
        save_game()

    # ==========================================
    # ⚔️ [전투 모드 UI]
    # ==========================================
    if st.session_state.game_mode == "COMBAT":
      enemy = st.session_state.current_enemy
      st.error(f"🚨 **[긴급 교전 중]** 상대: {enemy['name']}")

      col_hp1, col_hp2 = st.columns(2)
      col_hp1.metric("내 HP", f"{stats['hp']} / {stats['max_hp']}")
      col_hp2.metric(
          f"적 ({enemy['name']}) HP", f"{enemy['hp']} / {enemy['max_hp']}"
      )

      st.markdown("---")
      st.markdown("##### ⚔️ 전투 행동 선택")
      c_b1, c_b2, c_b3, c_b4 = st.columns(4)

      def execute_combat_action(action_type, skill=None):
        log_text, victory, defeat = process_combat_turn(action_type, skill)

        full_turn_log = f"⚔️ **[전투 턴 결과]**\n{log_text}"
        st.session_state.messages.append(
            {"role": "assistant", "content": full_turn_log}
        )

        if victory:
          st.session_state.game_mode = "EXPLORATION"
          st.session_state.current_enemy = None
          victory_log = (
              "🎉 **[탐험 복귀]** 전투에서 승리했습니다! 평화로운 상태로"
              " 돌아갑니다."
          )
          st.session_state.messages.append(
              {"role": "assistant", "content": victory_log}
          )
        elif defeat:
          st.session_state.game_mode = "EXPLORATION"
          st.session_state.current_enemy = None
          defeat_log = (
              "💀 **[마을 후퇴]** 패배하여 안전한 곳으로 후퇴했습니다."
          )
          st.session_state.messages.append(
              {"role": "assistant", "content": defeat_log}
          )

        if len(st.session_state.messages) > 2:
          st.session_state.messages = st.session_state.messages[-2:]

        save_game()
        st.rerun()

      if c_b1.button("🗡️ 기본 공격", use_container_width=True):
        execute_combat_action("attack")

      skills = stats.get("skills", [])
      if len(skills) > 0 and c_b2.button(
          f"✨ {skills[0]['name']}", use_container_width=True
      ):
        execute_combat_action("skill", skills[0])

      if len(skills) > 1 and c_b3.button(
          f"🔥 {skills[1]['name']}", use_container_width=True
      ):
        execute_combat_action("skill", skills[1])

      if c_b4.button("🧪 포션 사용", use_container_width=True):
        execute_combat_action("item")

    # ==========================================
    # 🌍 [일반 탐험 모드 UI]
    # ==========================================
    else:
      for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
          st.markdown(clean_tags(msg["content"]))

      current_choices = []
      if st.session_state.messages:
        last_msg = st.session_state.messages[-1]
        if last_msg["role"] == "assistant":
          c_match = re.search(
              r"\[CHOICES:\s*(\[.*?\])\s*\]", last_msg["content"], re.DOTALL
          )
          if c_match:
            try:
              current_choices = json.loads(c_match.group(1))
            except Exception:
              pass

      selected_choice = None
      if current_choices:
        st.markdown("##### 🎯 행동 선택")
        for idx, choice in enumerate(current_choices):
          if st.button(
              f"👉 {choice}",
              key=f"choice_{len(st.session_state.messages)}_{idx}",
              use_container_width=True,
          ):
            selected_choice = choice

      # 🔽 [하단 빈칸 공백 완전히 제거 완료]

      chat_input = st.chat_input("행동을 입력하세요...")
      user_input = selected_choice or chat_input

      if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
          st.markdown(user_input)

        with st.chat_message("assistant"):
          with st.spinner("게임 마스터가 처리 중입니다..."):
            try:
              # 🔄 매 턴 현재 상태를 AI에게 정확하게 주입하여 동기화
              context_prompt = (
                  f"[현재 캐릭터 상태 동기화 정보]\n"
                  f"- 종족: {stats['race']}\n"
                  f"- 직업: {stats['class_name']}\n"
                  f"- 레벨: {stats['level']} (경험치: {stats['exp']}/{stats['max_exp']})\n"
                  f"- 체력(HP): {stats['hp']}/{stats['max_hp']}\n"
                  f"- 마나(MP): {stats['mp']}/{stats['max_mp']}\n"
                  f"- 골드: {stats['gold']}G\n"
                  f"- 장착 장비: {json.dumps(stats.get('equipment', {}), ensure_ascii=False)}\n"
                  f"- 인벤토리: {json.dumps(stats['inventory'], ensure_ascii=False)}\n\n"
                  f"플레이어 행동: {user_input}"
              )
              response = st.session_state.chat_session.send_message(
                  context_prompt
              )
              bot_reply = response.text

              # 🎁 [아이템 획득 태그 감지 및 자동 장착 처리]
              item_gain_match = re.search(
                  r"\[ITEM_GAIN:\s*\"(.*?)\"\s*\]", bot_reply
              )
              if item_gain_match:
                acquired_item = item_gain_match.group(1)
                stats["inventory"].append(acquired_item)
                auto_equip_items()  # 좋은 장비 자동 장착 검사
                bot_reply += f"\n\n✨ **[획득 및 장착 완료]** '{acquired_item}'을(를) 획득하여 자동 장착되거나 인벤토리에 보관되었습니다!"

              combat_match = re.search(
                  r"\[START_COMBAT:\s*(\{.*?\})\s*\]", bot_reply, re.DOTALL
              )
              if combat_match:
                try:
                  edata = json.loads(combat_match.group(1))
                  st.session_state.game_mode = "COMBAT"
                  st.session_state.current_enemy = {
                      "name": edata.get("name", "야생의 적"),
                      "hp": edata.get("hp", 40),
                      "max_hp": edata.get("hp", 40),
                      "atk": edata.get("atk", 10),
                  }
                  bot_reply += f"\n\n🚨 **[경고]** {st.session_state.current_enemy['name']}과의 전투가 시작되었습니다! 상단 전투 메뉴를 확인하세요."
                except Exception:
                  pass

              st.markdown(clean_tags(bot_reply))
              st.session_state.messages.append(
                  {"role": "assistant", "content": bot_reply}
              )

              if len(st.session_state.messages) > 2:
                st.session_state.messages = st.session_state.messages[-2:]

              save_game()
              st.rerun()

            except Exception as e:
              st.error(f"오류 발생: {e}")
