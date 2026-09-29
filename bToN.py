DEV_BUTTON_STYLES = ["danger", "success", "primary"]


class DeveloperButtonRotator:
    def __init__(self, dev_names: list, dev_styles: list = None):
        self.dev_names = dev_names
        self.dev_styles = dev_styles or DEV_BUTTON_STYLES
        self.dev_ids = []

        self.name_idx = 0
        self.style_idx = 0
        self.id_idx = 0

    def load_dev_ids(self, takeoff_env: str):
        if not takeoff_env:
            self.dev_ids = []
            return

        targets = [t.strip() for t in takeoff_env.split('/') if t.strip()]
        parsed_ids = []
        for target in targets:
            try:
                parsed_ids.append(int(target))
            except ValueError:
                pass
        self.dev_ids = parsed_ids

    def get_next_dev_info(self, takeoff_env: str):
        self.load_dev_ids(takeoff_env)

        if not self.dev_ids:
            return None

        current_id = self.dev_ids[self.id_idx % len(self.dev_ids)]
        current_name = self.dev_names[self.name_idx % len(self.dev_names)]
        current_style_str = self.dev_styles[self.style_idx % len(self.dev_styles)]

        self.id_idx = (self.id_idx + 1) % len(self.dev_ids)
        self.name_idx = (self.name_idx + 1) % len(self.dev_names)
        self.style_idx = (self.style_idx + 1) % len(self.dev_styles)

        return {
            "id": current_id,
            "name": current_name,
            "style_str": current_style_str,
            "url": f"tg://user?id={current_id}"
        }

    def build_dev_keyboard(
        self,
        inline_keyboard_markup,
        inline_keyboard_button,
        btn_style,
        takeoff_env: str
    ):
        info = self.get_next_dev_info(takeoff_env)
        if not info:
            return None

        style_map = {
            "danger": btn_style.DANGER,
            "success": btn_style.SUCCESS,
            "primary": btn_style.PRIMARY
        }
        chosen_style = style_map.get(info["style_str"], btn_style.PRIMARY)

        dev_btn = inline_keyboard_button(
            text=info["name"],
            url=info["url"],
            style=chosen_style
        )
        return inline_keyboard_markup(inline_keyboard=[[dev_btn]])


class UserReactionManager:
    def __init__(self, emojis: list, delays: list):
        self.emojis = emojis
        self.delays = delays
        self.user_states = {}

    def _ensure_user(self, user_id: int):
        if user_id not in self.user_states:
            self.user_states[user_id] = {
                "delay_idx": 0,
                "emoji_idx": 0
            }

    def get_next_delay(self, user_id: int) -> float:
        self._ensure_user(user_id)
        state = self.user_states[user_id]
        delay = self.delays[state["delay_idx"]]
        state["delay_idx"] = (state["delay_idx"] + 1) % len(self.delays)
        return delay

    def get_next_emoji(self, user_id: int) -> str:
        self._ensure_user(user_id)
        state = self.user_states[user_id]
        emoji = self.emojis[state["emoji_idx"]]
        state["emoji_idx"] = (state["emoji_idx"] + 1) % len(self.emojis)
        return emoji


def get_edit_keyboard(
    inline_keyboard_markup,
    inline_keyboard_button,
    btn_style,
    btn_voice_label,
    btn_normal_label,
    current_mode: str
):
    is_voice = (current_mode == "voice")
    voice_btn = inline_keyboard_button(
        text=btn_voice_label,
        callback_data="toggle_voice",
        style=btn_style.SUCCESS if is_voice else btn_style.DANGER
    )
    normal_btn = inline_keyboard_button(
        text=btn_normal_label,
        callback_data="toggle_normal",
        style=btn_style.DANGER if is_voice else btn_style.SUCCESS
    )
    return inline_keyboard_markup(inline_keyboard=[[voice_btn, normal_btn]])
